"""Omium tracing — HTTP span export with silent failure (never breaks pipeline)."""

from __future__ import annotations

import asyncio
import functools
import inspect
import os
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, TypeVar

import requests

# TODO: Replace with real Omium SDK once docs are received at event.
# Docs reference: https://api.omium.ai/api/v1 — placeholder below for hackathon wiring.
OMIUM_TRACES_URL = os.getenv("OMIUM_API_URL", "https://api.omium.dev/v1/traces").strip()
OMIUM_WORKFLOW_ID = os.getenv("OMIUM_WORKFLOW_ID", "zero-day-pipeline")

_current_state: Any | None = None

F = TypeVar("F", bound=Callable[..., Any])


def set_current_state(state: Any | None) -> None:
    """Set the active pipeline state for trace metadata."""
    global _current_state
    _current_state = state


def get_current_state() -> Any | None:
    return _current_state


def _resolve_state(args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any | None:
    if _current_state is not None:
        return _current_state
    for arg in args:
        if hasattr(arg, "run_id") and hasattr(arg, "exploit_attempt_number"):
            return arg
        if hasattr(arg, "state") and hasattr(arg.state, "run_id"):
            return arg.state
    state_kw = kwargs.get("state")
    if state_kw is not None and hasattr(state_kw, "run_id"):
        return state_kw
    try:
        from state import get_state

        return get_state()
    except Exception:  # noqa: BLE001
        return None


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _send_trace_event(
    span_type: str,
    span_name: str,
    start_time: str,
    end_time: str,
    duration_ms: int,
    state: Any | None,
) -> None:
    """POST trace to Omium API; failures are swallowed."""
    api_key = os.getenv("OMIUM_API_KEY", "").strip()
    if not api_key:
        return

    run_id = getattr(state, "run_id", "unknown") if state else "unknown"
    attempt_number = int(getattr(state, "exploit_attempt_number", 0) or 0) if state else 0
    success = bool(getattr(state, "exploit_success", False)) if state else False

    payload = {
        "workflow_id": OMIUM_WORKFLOW_ID,
        "run_id": run_id,
        "span_type": span_type,
        "span_name": span_name,
        "start_time": start_time,
        "end_time": end_time,
        "duration_ms": duration_ms,
        "metadata": {
            "attempt_number": attempt_number,
            "success": success,
        },
    }

    try:
        requests.post(
            OMIUM_TRACES_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=5,
        )
    except Exception:  # noqa: BLE001 — tracing must never break the pipeline
        return


def _trace_wrapper(span_type: str, name: str, func: F) -> F:
    # If decorating a class (e.g. @trace_agent on ThreatResearcher), return it
    # unchanged — wrapping a class constructor breaks instantiation. The
    # @trace_tool decorators on individual methods handle per-operation timing.
    if inspect.isclass(func):
        print(f"[Omium] registered {span_type}:{name}")
        return func  # type: ignore[return-value]

    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            state = _resolve_state(args, kwargs)
            start = _iso_now()
            t0 = datetime.now(timezone.utc)
            try:
                return await func(*args, **kwargs)
            finally:
                t1 = datetime.now(timezone.utc)
                end = t1.isoformat()
                duration_ms = int((t1 - t0).total_seconds() * 1000)
                _send_trace_event(span_type, name, start, end, duration_ms, state)
                print(f"[Omium] {span_type}:{name} ({duration_ms}ms)")

        return async_wrapper  # type: ignore[return-value]

    @functools.wraps(func)
    def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
        state = _resolve_state(args, kwargs)
        start = _iso_now()
        t0 = datetime.now(timezone.utc)
        try:
            return func(*args, **kwargs)
        finally:
            t1 = datetime.now(timezone.utc)
            end = t1.isoformat()
            duration_ms = int((t1 - t0).total_seconds() * 1000)
            _send_trace_event(span_type, name, start, end, duration_ms, state)
            print(f"[Omium] {span_type}:{name} ({duration_ms}ms)")

    return sync_wrapper  # type: ignore[return-value]


def trace_agent(name: str) -> Callable[[F], F]:
    """Trace agent-level spans (classes or functions)."""

    def decorator(func: F) -> F:
        return _trace_wrapper("agent", name, func)

    return decorator


def trace_tool(name: str) -> Callable[[F], F]:
    """Trace tool-level spans."""

    def decorator(func: F) -> F:
        return _trace_wrapper("tool", name, func)

    return decorator


def trace_workflow(name: str) -> Callable[[F], F]:
    """Trace workflow-level spans."""

    def decorator(func: F) -> F:
        return _trace_wrapper("workflow", name, func)

    return decorator
