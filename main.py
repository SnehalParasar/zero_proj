"""FastAPI entry point — webhook trigger and pipeline orchestration."""

from __future__ import annotations

import asyncio
from typing import Any

import docker
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import JSONResponse

from agents.agent0_researcher import run as run_researcher
from agents.agent1_architect import ExploitArchitect
from agents.agent2_executor import SandboxExecutor
from agents.agent3_critic import LogCritic
from state import SharedState, get_state, set_state
from tools.github_tool import open_github_pr
from tracing.omium import trace_workflow

load_dotenv()

MAX_RETRIES = 5

DEFAULT_BATTLE_PLAN = """
Target: Vulnerable Flask application in Docker at http://localhost:5001
Vulnerability: OS command injection via POST /run JSON field "command"
  (subprocess shell=True, no sanitization)
Objective: Achieve command execution; read /etc/passwd or create a proof file
Constraints: Exploit must use Python requests library from the host against localhost:5001
"""

app = FastAPI(
    title="Project Zero-Day",
    description="Multi-agent autonomous security pipeline",
    version="0.2.0",
)


@trace_workflow("zero_day_pipeline")
async def run_pipeline(state: SharedState) -> SharedState:
    """Core retry loop: architect → executor → critic until success or max retries."""
    state.status = "running"
    state.log_feed("pipeline", f"Pipeline started — run_id={state.run_id}")

    # Phase 0: researcher stub (battle plan may be enriched later)
    state = run_researcher(state)
    if not state.battle_plan.strip():
        state.battle_plan = DEFAULT_BATTLE_PLAN.strip()
        state.log_feed("pipeline", "Using default battle plan (researcher pending).")

    executor = SandboxExecutor(state)
    architect = ExploitArchitect(state)
    critic = LogCritic(state)

    previous_failure: str | None = None
    container_logs = ""

    try:
        state.log_feed("pipeline", "Starting sandbox container.")
        executor.build_and_run_container()

        attempt = 0
        while attempt < MAX_RETRIES:
            state.exploit_attempt_number = attempt + 1
            state.log_feed(
                "pipeline",
                f"Exploit attempt {state.exploit_attempt_number}/{MAX_RETRIES}",
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
            state.log_feed("pipeline", f"Attempt failed — retrying. Reason: {previous_failure}")
            attempt += 1
        else:
            state.exploit_success = False
            state.log_feed("pipeline", f"All {MAX_RETRIES} exploit attempts exhausted.")

    except docker.errors.DockerException as exc:
        state.exploit_success = False
        state.status = "failed"
        state.log_feed("pipeline", f"Docker error: {exc}")
    finally:
        executor.cleanup()

    if state.exploit_success:
        try:
            state.log_feed("pipeline", "Opening GitHub pull request.")
            open_github_pr(state)
            state.status = "success"
            state.log_feed("pipeline", "Pipeline completed successfully.")
        except Exception as exc:  # noqa: BLE001 — surface GitHub failures on state
            state.status = "failed"
            state.log_feed("pipeline", f"GitHub PR failed: {exc}")
    elif state.status != "failed":
        state.status = "failed"
        state.log_feed("pipeline", "Pipeline failed — no successful exploit.")

    return state


def _run_pipeline_sync(state: SharedState) -> None:
    """Background task wrapper for the async pipeline."""
    asyncio.run(run_pipeline(state))


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/state")
async def read_state() -> dict[str, Any]:
    return get_state().to_dict()


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks) -> JSONResponse:
    """Receive external trigger (e.g. GitHub, manual) and start the pipeline."""
    payload: dict[str, Any] = await request.json()

    state = SharedState(trigger=payload)
    set_state(state)
    state.log_feed("webhook", f"Webhook received — run_id={state.run_id}")

    background_tasks.add_task(_run_pipeline_sync, state)

    return JSONResponse(
        status_code=202,
        content={"accepted": True, "run_id": state.run_id, "status": state.status},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
