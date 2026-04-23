"""Tracing — Langfuse if installed and configured, no-op otherwise.

Set ``LANGFUSE_PUBLIC_KEY`` (and friends) in env to enable. Without the
key — or without the ``langfuse`` package installed — every call here
becomes a no-op, and the rest of the codebase doesn't need to care.

Public API:
    track(as_type=...)              decorator wrapping a function as a span
    update_current_span(**kwargs)   enrich the current span
    update_current_generation(**kwargs)
    flush()                         flush pending traces
"""

import logging
import os
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _noop_track(*, as_type: str | None = None) -> Callable:
    def decorator(fn: Callable) -> Callable:
        return fn
    return decorator


def _noop(**kwargs: Any) -> None:
    pass


_enabled = False
if os.environ.get("LANGFUSE_PUBLIC_KEY"):
    try:
        from langfuse import observe as _observe, get_client as _get_client
        _enabled = True
        logger.info("Tracing backend: Langfuse")
    except ImportError:
        logger.warning("langfuse package not installed — tracing disabled")


if _enabled:
    def track(*, as_type: str | None = None) -> Callable:
        kwargs: dict[str, Any] = {}
        if as_type is not None:
            kwargs["as_type"] = as_type
        return _observe(**kwargs)

    def update_current_span(**kwargs: Any) -> None:
        _get_client().update_current_span(**kwargs)

    def update_current_generation(**kwargs: Any) -> None:
        _get_client().update_current_generation(**kwargs)

    def flush() -> None:
        _get_client().flush()
else:
    track = _noop_track
    update_current_span = _noop
    update_current_generation = _noop
    flush = _noop
