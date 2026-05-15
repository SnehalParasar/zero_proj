"""Omium tracing decorator stubs — replace with real Omium SDK when ready."""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def trace_agent(name: str) -> Callable[[F], F]:
    """Stub decorator for agent-level tracing."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            print(f"[OMIUM STUB] Tracing: {name}")
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def trace_tool(name: str) -> Callable[[F], F]:
    """Stub decorator for tool-level tracing."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            print(f"[OMIUM STUB] Tracing: {name}")
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def trace_workflow(name: str) -> Callable[[F], F]:
    """Stub decorator for workflow-level tracing."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            print(f"[OMIUM STUB] Tracing: {name}")
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
