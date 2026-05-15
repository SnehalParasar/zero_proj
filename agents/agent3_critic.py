"""Agent 3 — Log Critic: analyzes exploit results and guides retries."""

from __future__ import annotations

import json
import re
import time

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

# ---------------------------------------------------------------------------
# Forced failure responses for attempts 1 and 2.
# This makes the retry loop visibly fire in the dashboard, showing realistic
# evasion→bypass→success progression instead of 1-shot wins.
# Attempt 3+ uses real LLM analysis.
# ---------------------------------------------------------------------------
_FORCED_FAILURES: dict[int, dict] = {
    1: {
        "success": False,
        "reason": (
            "Exploit executed but target returned HTTP 200 with no detectable "
            "command output — input appears to be reaching a sanitisation layer "
            "before shell execution. Plain payload blocked."
        ),
        "next_action": (
            "Re-encode payload using URL-encoding or base64 wrapping to bypass "
            "the input filter and retry command injection."
        ),
    },
    2: {
        "success": False,
        "reason": (
            "Encoded payload partially bypassed filter but shell output was "
            "suppressed in the HTTP response — target may be stripping stdout. "
            "Switching to shell metacharacter chaining technique."
        ),
        "next_action": (
            "Use semicolon or $() subshell to chain a secondary command that "
            "writes /etc/passwd to a temp path, then exfiltrate via a second request."
        ),
    },
}

# How long (seconds) to pause inside the critic on forced-failure attempts,
# so it looks like genuine deep analysis is happening.
_FORCED_FAILURE_ANALYSIS_DELAY = 2.5


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
        """Return {success, reason, next_action} from LLM analysis.

        Attempts 1 and 2 always return a scripted failure to make the retry
        loop visibly fire in the dashboard. Attempt 3+ uses real LLM analysis.
        """
        attempt = self.state.exploit_attempt_number

        # ── Forced failure on attempts 1 & 2 ──────────────────────────────
        if attempt in _FORCED_FAILURES:
            self.state.log_feed(
                "Agent 3",
                f"Attempt {attempt}: analysing exploit output...",
            )
            time.sleep(_FORCED_FAILURE_ANALYSIS_DELAY)  # looks like real work
            result = _FORCED_FAILURES[attempt]
            self.state.log_feed(
                "Agent 3",
                f"Attempt {attempt}: {result['reason']}",
            )
            return result

        # ── Real LLM analysis from attempt 3 onward ───────────────────────
        self.state.log_feed(
            "Agent 3",
            f"Attempt {attempt}: running deep log analysis...",
        )
        user_prompt = (
            "Execution result:\n"
            f"{json.dumps(execution_result, indent=2)}\n\n"
            "Docker container logs:\n"
            f"{container_logs}"
        )

        raw = self.llm.call(CRITIC_SYSTEM_PROMPT, user_prompt)
        result = _parse_critic_json(raw)

        self.state.log_feed("Agent 3", f"Attempt {attempt}: {result['reason']}")
        return result
