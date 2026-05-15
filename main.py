"""FastAPI entry point — webhook trigger and pipeline orchestration."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any

import docker
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from agents.agent0_researcher import ThreatResearcher
from agents.agent1_architect import ExploitArchitect
from agents.agent2_executor import SandboxExecutor
from agents.agent3_critic import LogCritic
from state import SharedState, get_state, set_state
from tools.github_tool import open_github_pr
from tracing.omium import set_current_state, trace_workflow

load_dotenv()

MAX_RETRIES = 5

# All in-flight and completed runs keyed by run_id
active_runs: dict[str, SharedState] = {}

BANNER = r"""
  ____            _       ____            __   ______        __
 |  _ \ ___  __ _| | __  |  _ \  _____  _\ \ / /  _ \  ___  \ \
 | |_) / _ \/ _` | |/ /  | | | |/ _ \ \/ /\ V /| | | |/ _ \  \ \
 |  __/  __/ (_| |   <   | |_| |  __/>  <  | | | |_| | (_) | / /
 |_|   \___|\__,_|_|\_\  |____/ \___/_/\_\ |_| |____/ \___/ /_/
                    Project Zero-Day — Autonomous Security Pipeline
"""


def _print_startup_info() -> None:
    print(BANNER)
    provider = os.getenv("LLM_PROVIDER", "groq").strip().lower()
    print(f"[startup] LLM provider: {provider}")
    if provider == "gemini":
        print(f"[startup] Gemini model: {os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')}")
    else:
        print(f"[startup] Groq model: {os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')}")
    print(f"[startup] GitHub target repo: {os.getenv('GITHUB_REPO', '(not set)')}")
    print(f"[startup] Tavily configured: {bool(os.getenv('TAVILY_API_KEY'))}")
    print(f"[startup] Omium configured: {bool(os.getenv('OMIUM_API_KEY'))}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _print_startup_info()
    yield


app = FastAPI(
    title="Project Zero-Day",
    description="Multi-agent autonomous security pipeline",
    version="0.3.0",
    lifespan=lifespan,
)


@trace_workflow("zero_day_pipeline")
async def run_pipeline(state: SharedState) -> SharedState:
    """
    Full pipeline:
    0. Threat research → battle_plan
    1. Architect → exploit code (retry loop with critic)
    2. Executor → Docker sandbox
    3. Critic → success / retry
    4. GitHub PR on success
    """
    set_current_state(state)
    state.status = "running"
    state.log_feed("pipeline", f"Pipeline started — run_id={state.run_id}")

    researcher = ThreatResearcher(state)
    architect = ExploitArchitect(state)
    executor = SandboxExecutor(state)
    critic = LogCritic(state)

    try:
        # Agent 0 — research
        state.log_feed("pipeline", "Agent 0: threat research starting.")
        state.battle_plan = researcher.research(state.trigger)

        # Agent 2 — container (once per run)
        state.log_feed("pipeline", "Agent 2: starting sandbox container.")
        executor.build_and_run_container()

        previous_failure: str | None = None
        container_logs = ""

        # Agents 1 + 2 + 3 — retry loop
        attempt = 0
        while attempt < MAX_RETRIES:
            state.exploit_attempt_number = attempt + 1
            state.log_feed(
                "pipeline",
                f"Attempt {state.exploit_attempt_number}/{MAX_RETRIES}",
            )

            exploit_code = architect.write_exploit(state.battle_plan, previous_failure)
            state.current_exploit_code = exploit_code

            execution_result = executor.execute_exploit(state.current_exploit_code)
            container_logs = executor.get_container_logs()

            analysis = critic.analyze(execution_result, container_logs)
            state.log_feed("Agent 3", f"next_action: {analysis.get('next_action', '')}")

            if analysis.get("success"):
                state.exploit_success = True
                state.log_feed("pipeline", "Exploit succeeded — stopping retry loop.")
                break

            previous_failure = analysis.get("reason", "Unknown failure")
            state.log_feed(
                "pipeline",
                f"Attempt failed — retrying. Reason: {previous_failure}",
            )
            attempt += 1
        else:
            state.exploit_success = False
            state.log_feed("pipeline", f"All {MAX_RETRIES} exploit attempts exhausted.")

    except docker.errors.DockerException as exc:
        state.exploit_success = False
        state.status = "failed"
        state.log_feed("pipeline", f"Docker error: {exc}")
    except Exception as exc:  # noqa: BLE001 — research / LLM failures
        state.exploit_success = False
        state.status = "failed"
        state.log_feed("pipeline", f"Pipeline error: {exc}")
    finally:
        executor.cleanup()

    if state.exploit_success:
        try:
            state.log_feed("pipeline", "Opening GitHub pull request.")
            open_github_pr(state)
            state.status = "success"
            state.log_feed("pipeline", "Pipeline completed successfully.")
        except Exception as exc:  # noqa: BLE001
            state.status = "failed"
            state.log_feed("pipeline", f"GitHub PR failed: {exc}")
    elif state.status != "failed":
        state.status = "failed"
        state.log_feed("pipeline", "Pipeline failed — no successful exploit.")

    active_runs[state.run_id] = state
    return state


def _run_pipeline_sync(state: SharedState) -> None:
    """Background task wrapper for the async pipeline."""
    asyncio.run(run_pipeline(state))


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "ok", "active_runs": len(active_runs)}


@app.get("/status/{run_id}")
async def get_run_status(run_id: str) -> dict[str, Any]:
    """Poll agent feed and outcome for a specific pipeline run."""
    state = active_runs.get(run_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return {
        "run_id": state.run_id,
        "status": state.status,
        "exploit_success": state.exploit_success,
        "pr_url": state.pr_url,
        "agent_feed": state.agent_feed,
        "battle_plan": state.battle_plan,
        "exploit_attempt_number": state.exploit_attempt_number,
    }


@app.get("/state")
async def read_state() -> dict[str, Any]:
    """Return the most recently triggered run (backward compatible)."""
    return get_state().to_dict()


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """
    Trigger the pipeline.

    Body example:
    {"cve_id": "CVE-2024-1234", "target": "flask-app", "description": "..."}
    """
    payload: dict[str, Any] = await request.json()

    state = SharedState(trigger=payload, status="started")
    active_runs[state.run_id] = state
    set_state(state)
    set_current_state(state)

    state.log_feed(
        "webhook",
        f"Pipeline initiated — cve={payload.get('cve_id', 'n/a')} "
        f"target={payload.get('target', 'n/a')}",
    )

    background_tasks.add_task(_run_pipeline_sync, state)

    return JSONResponse(
        status_code=202,
        content={
            "run_id": state.run_id,
            "status": "started",
            "message": "Pipeline initiated",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
