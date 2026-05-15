"""Shared pipeline state for Project Zero-Day."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _default_agent_feed() -> list[dict[str, Any]]:
    return []


def _default_sandbox_logs() -> list[str]:
    return []


@dataclass
class SharedState:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trigger: dict[str, Any] = field(default_factory=dict)
    battle_plan: str = ""
    current_exploit_code: str = ""
    exploit_attempt_number: int = 0
    sandbox_logs: list[str] = field(default_factory=_default_sandbox_logs)
    exploit_success: bool = False
    patch_code: str = ""
    pr_url: str = ""
    agent_feed: list[dict[str, Any]] = field(default_factory=_default_agent_feed)
    status: str = "running"  # "running" | "success" | "failed"

    def log_feed(self, agent: str, message: str) -> None:
        """Append an agent activity entry with UTC timestamp."""
        self.agent_feed.append(
            {
                "agent": agent,
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )

    def reset(self) -> None:
        """Reset mutable fields to defaults while preserving run_id."""
        preserved_run_id = self.run_id
        self.trigger = {}
        self.battle_plan = ""
        self.current_exploit_code = ""
        self.exploit_attempt_number = 0
        self.sandbox_logs = []
        self.exploit_success = False
        self.patch_code = ""
        self.pr_url = ""
        self.agent_feed = []
        self.status = "running"
        self.run_id = preserved_run_id

    def to_dict(self) -> dict[str, Any]:
        """Serialize state for API responses and dashboard."""
        return {
            "run_id": self.run_id,
            "trigger": self.trigger,
            "battle_plan": self.battle_plan,
            "current_exploit_code": self.current_exploit_code,
            "exploit_attempt_number": self.exploit_attempt_number,
            "sandbox_logs": self.sandbox_logs,
            "exploit_success": self.exploit_success,
            "patch_code": self.patch_code,
            "pr_url": self.pr_url,
            "agent_feed": self.agent_feed,
            "status": self.status,
        }


# Module-level singleton for the current pipeline run
_pipeline_state: SharedState | None = None


def get_state() -> SharedState:
    """Return the active pipeline state, creating one if needed."""
    global _pipeline_state
    if _pipeline_state is None:
        _pipeline_state = SharedState()
    return _pipeline_state


def set_state(state: SharedState) -> None:
    """Replace the active pipeline state."""
    global _pipeline_state
    _pipeline_state = state
