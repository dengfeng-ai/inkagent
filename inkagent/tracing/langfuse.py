"""Langfuse tracing provider."""

from typing import Any, Callable

from inkagent.tracing.base import TracingProvider


class LangfuseTracingProvider(TracingProvider):
    """Thin adapter around the ``langfuse`` SDK."""

    def __init__(self) -> None:
        from langfuse import observe, get_client
        self._observe = observe
        self._get_client = get_client

    def track(self, *, as_type: str | None = None) -> Callable:
        kwargs: dict[str, Any] = {}
        if as_type is not None:
            kwargs["as_type"] = as_type
        return self._observe(**kwargs)

    def update_current_span(self, **kwargs: Any) -> None:
        self._get_client().update_current_span(**kwargs)

    def update_current_generation(self, **kwargs: Any) -> None:
        self._get_client().update_current_generation(**kwargs)

    def flush(self) -> None:
        self._get_client().flush()
