"""Comet Opik tracing provider."""

import os
from typing import Any, Callable

from inkagent.tracing.base import TracingProvider

# Opik type names differ from our abstract interface.
_TYPE_MAP = {"generation": "llm", "tool": "tool"}


def _ensure_dict(value: Any) -> dict[str, Any] | None:
    """Opik requires input/output to be dicts — wrap scalars."""
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return {"value": value}


class OpikTracingProvider(TracingProvider):
    """Adapter that maps the tracing interface to Opik's ``track`` API."""

    def __init__(self) -> None:
        import opik
        self._opik = opik
        self._project_name = os.environ.get("OPIK_PROJECT_NAME", "inkagent")

    def track(self, *, as_type: str | None = None) -> Callable:
        kwargs: dict[str, Any] = {"project_name": self._project_name}
        if as_type is not None:
            kwargs["type"] = _TYPE_MAP.get(as_type, as_type)
        return self._opik.track(**kwargs)

    def update_current_span(self, **kwargs: Any) -> None:
        self._coerce_io(kwargs)
        self._opik.opik_context.update_current_span(**kwargs)

    def update_current_generation(self, **kwargs: Any) -> None:
        """Map generation-style kwargs to Opik span kwargs.

        Opik has no separate "generation" concept — everything is a span.
        We remap Langfuse-style keys to Opik equivalents.
        """
        mapped: dict[str, Any] = {}
        for key in ("input", "output", "name", "model"):
            if key in kwargs:
                mapped[key] = kwargs[key]
        if "usage_details" in kwargs:
            mapped["usage"] = kwargs["usage_details"]
        if "model_parameters" in kwargs:
            mapped.setdefault("metadata", {}).update(kwargs["model_parameters"])
        self._coerce_io(mapped)
        self._opik.opik_context.update_current_span(**mapped)

    def flush(self) -> None:
        self._opik.flush_tracker()

    @staticmethod
    def _coerce_io(kwargs: dict[str, Any]) -> None:
        """Ensure input/output values are dicts (Opik requirement)."""
        for key in ("input", "output"):
            if key in kwargs:
                kwargs[key] = _ensure_dict(kwargs[key])
