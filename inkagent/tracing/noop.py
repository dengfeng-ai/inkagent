"""No-op tracing provider — used when no backend is configured."""

from typing import Any, Callable

from inkagent.tracing.base import TracingProvider


class NoopTracingProvider(TracingProvider):
    """Silently ignores all tracing calls."""

    def track(self, *, as_type: str | None = None) -> Callable:
        def decorator(fn: Callable) -> Callable:
            return fn
        return decorator

    def update_current_span(self, **kwargs: Any) -> None:
        pass

    def update_current_generation(self, **kwargs: Any) -> None:
        pass

    def flush(self) -> None:
        pass
