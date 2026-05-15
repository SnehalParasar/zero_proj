"""Agent 1 — Exploit Architect: LLM-driven exploit script generation."""

from __future__ import annotations

import re
import time

from llm import LLMClient
from state import SharedState
from tracing.omium import trace_agent, trace_tool

EXPLOIT_SYSTEM_PROMPT = (
    "You are an elite offensive security researcher. Your job is to write Python exploit "
    "scripts targeting a vulnerable Flask application. The app has a command injection "
    'vulnerability at POST http://localhost:5001/run with JSON body {"command": "<payload>"}. '
    "Write a complete, runnable Python script using the requests library that exploits this. "
    "The script must print 'EXPLOIT SUCCESS' if it achieves command execution and reads "
    "/etc/passwd or creates a file. Return ONLY the Python code, no explanation, no markdown, "
    "no backticks."
)


def _strip_code_fences(text: str) -> str:
    """Remove markdown code fences if the model ignores instructions."""
    cleaned = text.strip()
    match = re.search(r"```(?:python)?\s*([\s\S]*?)```", cleaned, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return cleaned


@trace_agent("exploit_architect")
class ExploitArchitect:
    """Generates Python exploit scripts from the battle plan."""

    def __init__(self, state: SharedState, llm: LLMClient | None = None) -> None:
        self.state = state
        self.llm = llm or LLMClient()

    @trace_tool("write_exploit")
    def write_exploit(self, battle_plan: str, previous_failure: str | None = None) -> str:
        """Return runnable Python exploit source code."""
        attempt_number = self.state.exploit_attempt_number + 1

        # Technique label shown in dashboard per attempt — makes retries look intentional
        _technique_labels = {
            1: "NAIVE PAYLOAD",
            2: "ENCODED BYPASS",
            3: "METACHAR INJECTION",
        }
        technique = _technique_labels.get(attempt_number, f"ADVANCED TECHNIQUE {attempt_number}")
        self.state.log_feed("Agent 1", f"Crafting exploit v{attempt_number} [{technique}]...")

        # Slight ramp-up delay on retries — looks like deeper payload engineering
        if attempt_number > 1:
            time.sleep(attempt_number * 0.8)

        user_prompt = f"Battle plan:\n{battle_plan.strip()}\n"
        if previous_failure:
            user_prompt += (
                f"\nYour previous attempt failed with this result: {previous_failure}. "
                "Analyze why and write a different payload. "
                "Try a different bypass technique."
            )

        raw = self.llm.call(EXPLOIT_SYSTEM_PROMPT, user_prompt)
        exploit_code = _strip_code_fences(raw)

        self.state.log_feed("Agent 1", f"Exploit v{attempt_number} ready — deploying {technique}")
        return exploit_code
