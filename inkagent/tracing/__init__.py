"""Tracing — Langfuse if installed and configured, no-op otherwise.

Set ``LANGFUSE_PUBLIC_KEY`` (and friends) in env to enable. Without the
key — or without the ``langfuse`` package installed — every call here
becomes a no-op, and the rest of the codebase doesn't need to care.

Public API:
    track(as_type=..., name=...)    decorator wrapping a function as a span
    update_current_span(**kwargs)   enrich the current span
    update_current_generation(**kwargs)
    trace_attributes(**kwargs)      context manager — propagate session_id / user_id /
                                    tags / metadata to the active span and its children
    flush()                         flush pending traces
"""

import logging
import os
from contextlib import contextmanager
from typing import Any, Callable, Iterator

logger = logging.getLogger(__name__)


def _noop_track(*, as_type: str | None = None, name: str | None = None) -> Callable:
    def decorator(fn: Callable) -> Callable:
        return fn
    return decorator


def _noop(**kwargs: Any) -> None:
    pass


@contextmanager
def _noop_ctx(**kwargs: Any) -> Iterator[None]:
    yield


_enabled = False
if os.environ.get("LANGFUSE_PUBLIC_KEY"):
    try:
        from langfuse import (
            observe as _observe,
            get_client as _get_client,
            propagate_attributes as _propagate_attributes,
        )
        _enabled = True
        logger.info("Tracing backend: Langfuse")
    except ImportError:
        logger.warning("langfuse package not installed — tracing disabled")


if _enabled:
    def track(*, as_type: str | None = None, name: str | None = None) -> Callable:
        kwargs: dict[str, Any] = {}
        if as_type is not None:
            kwargs["as_type"] = as_type
        if name is not None:
            kwargs["name"] = name
        return _observe(**kwargs)

    def update_current_span(**kwargs: Any) -> None:
        _get_client().update_current_span(**kwargs)

    def update_current_generation(**kwargs: Any) -> None:
        _get_client().update_current_generation(**kwargs)

    def trace_attributes(**kwargs: Any):
        """Propagate trace-level fields to the current span and its children.

        Drops keys whose values are ``None`` so callers can pass them
        unconditionally.
        """
        clean = {k: v for k, v in kwargs.items() if v is not None}
        return _propagate_attributes(**clean)

    def flush() -> None:
        _get_client().flush()
else:
    track = _noop_track
    update_current_span = _noop
    update_current_generation = _noop
    trace_attributes = _noop_ctx
    flush = _noop
