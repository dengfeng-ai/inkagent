"""Abstract base class for tracing providers."""

from abc import ABC, abstractmethod
from typing import Any, Callable


class TracingProvider(ABC):
    """Provider-agnostic tracing interface.

    Each backend (Langfuse, Opik, ...) implements these three methods.
    """

    @abstractmethod
    def track(self, *, as_type: str | None = None) -> Callable:
        """Return a decorator that wraps a function as a tracing span.

        *as_type*: ``None`` (plain span), ``"generation"`` (LLM call),
        or ``"tool"`` (tool execution).
        """

    @abstractmethod
    def update_current_span(self, **kwargs: Any) -> None:
        """Enrich the current span with metadata.

        Common kwargs: *input*, *output*, *name*.
        """

    @abstractmethod
    def update_current_generation(self, **kwargs: Any) -> None:
        """Enrich the current generation span with metadata.

        Common kwargs: *model*, *input*, *output*, *usage_details*,
        *model_parameters*, *name*.
        """

    @abstractmethod
    def flush(self) -> None:
        """Flush pending traces to the backend."""
