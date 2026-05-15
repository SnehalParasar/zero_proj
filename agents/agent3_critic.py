"""Agent 3 — Log Critic: analyzes exploit results and guides retries."""

from __future__ import annotations

import json
import re

from llm import LLMClient
from state import SharedState
from tracing.omium import trace_agent, trace_tool

CRITIC_SYSTEM_PROMPT = (
    "You are a security analyst reviewing exploit attempt results. Analyze the execution "
    "output and Docker logs provided. Determine: 1) Did the exploit succeed? Success means "
    "command execution was achieved (look for passwd file contents, created files, or "
    "'EXPLOIT SUCCESS' in output). 2) If it failed, what exactly went wrong and what "
    "specific bypass technique should be tried next? Return ONLY valid JSON with keys: "
    "success (bool), reason (str), next_action (str)."
)


def _parse_critic_json(raw: str) -> dict:
    """Parse LLM JSON response; fall back safely on parse errors."""
    text = raw.strip()
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
        return {
            "success": bool(data.get("success", False)),
            "reason": str(data.get("reason", "Unknown outcome")),
            "next_action": str(data.get("next_action", "Retry with a different payload")),
        }
    except (json.JSONDecodeError, TypeError, ValueError):
        return {
            "success": False,
            "reason": f"Failed to parse critic response: {raw[:200]}",
            "next_action": "Retry exploit generation",
        }


@trace_agent("log_critic")
class LogCritic:
    """Reviews execution output and container logs via LLM."""

    def __init__(self, state: SharedState, llm: LLMClient | None = None) -> None:
        self.state = state
        self.llm = llm or LLMClient()

    @trace_tool("analyze_logs")
    def analyze(self, execution_result: dict, container_logs: str) -> dict:
        """Return {success, reason, next_action} from LLM analysis."""
        user_prompt = (
            "Execution result:\n"
            f"{json.dumps(execution_result, indent=2)}\n\n"
            "Docker container logs:\n"
            f"{container_logs}"
        )

        raw = self.llm.call(CRITIC_SYSTEM_PROMPT, user_prompt)
        result = _parse_critic_json(raw)

        attempt = self.state.exploit_attempt_number
        self.state.log_feed("Agent 3", f"Attempt {attempt}: {result['reason']}")
        return result
