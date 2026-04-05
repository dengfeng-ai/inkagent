"""Tracing provider factory.

Selection via environment variables::

    TRACING_PROVIDER  — "langfuse", "opik", or "none" (default: auto-detect)

Auto-detection checks for provider-specific env keys:

* ``LANGFUSE_PUBLIC_KEY``  → langfuse
* ``OPIK_API_KEY``         → opik
* neither                  → noop
"""

import logging
import os
from typing import Any, Callable

from inkagent.tracing.base import TracingProvider

logger = logging.getLogger(__name__)

_instance: TracingProvider | None = None


def get_tracer() -> TracingProvider:
    """Return the singleton tracing provider (lazy-initialized)."""
    global _instance
    if _instance is not None:
        return _instance

    name = os.environ.get("TRACING_PROVIDER", "").lower()
    if not name:
        # Auto-detect from provider-specific env keys.
        if os.environ.get("LANGFUSE_PUBLIC_KEY"):
            name = "langfuse"
        elif os.environ.get("OPIK_API_KEY"):
            name = "opik"
        else:
            name = "none"

    if name == "langfuse":
        try:
            from inkagent.tracing.langfuse import LangfuseTracingProvider
            _instance = LangfuseTracingProvider()
            logger.info("Tracing backend: Langfuse")
        except ImportError:
            logger.warning("langfuse package not installed — tracing disabled")
            _instance = _make_noop()
    elif name == "opik":
        try:
            from inkagent.tracing.opik import OpikTracingProvider
            _instance = OpikTracingProvider()
            logger.info("Tracing backend: Opik")
        except ImportError:
            logger.warning("opik package not installed — tracing disabled")
            _instance = _make_noop()
    else:
        _instance = _make_noop()

    return _instance


def _make_noop() -> TracingProvider:
    from inkagent.tracing.noop import NoopTracingProvider
    return NoopTracingProvider()


# ---------------------------------------------------------------------------
# Convenience functions — the public API used by consumer modules.
# ---------------------------------------------------------------------------

def track(*, as_type: str | None = None) -> Callable:
    """Decorator: trace a function as a span."""
    return get_tracer().track(as_type=as_type)


def update_current_span(**kwargs: Any) -> None:
    """Enrich the current span with metadata."""
    get_tracer().update_current_span(**kwargs)


def update_current_generation(**kwargs: Any) -> None:
    """Enrich the current generation span with metadata."""
    get_tracer().update_current_generation(**kwargs)


def flush() -> None:
    """Flush pending traces to the backend."""
    get_tracer().flush()
