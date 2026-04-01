"""Unified LLM provider interface and data types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class LLMError(Exception):
    """Common exception for LLM API errors across providers."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        super().__init__(message)
        self.original = original


@dataclass
class ToolCall:
    """A tool invocation requested by the LLM."""

    id: str
    name: str
    input: dict[str, Any]


@dataclass
class Usage:
    input_tokens: int
    output_tokens: int


@dataclass
class LLMResponse:
    """Provider-agnostic LLM response."""

    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"  # "end_turn" or "tool_use"
    usage: Usage = field(default_factory=lambda: Usage(0, 0))
    raw: Any = None  # provider-specific raw response for building messages


class LLMProvider(ABC):
    """Abstract base for LLM providers."""

    @abstractmethod
    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> LLMResponse:
        """Run a completion with tool support. Returns unified LLMResponse."""

    @abstractmethod
    def simple_complete(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int,
    ) -> str:
        """Run a simple completion (no tools). Returns text."""

    @abstractmethod
    def format_tools(self, tools: list[dict]) -> list:
        """Convert registry tools (Anthropic-style schema) to provider format."""

    @abstractmethod
    def assistant_message(self, response: LLMResponse) -> dict:
        """Build a message dict for the assistant's response (for the message history)."""

    @abstractmethod
    def tool_results_messages(
        self, results: list[dict[str, str]]
    ) -> list[dict]:
        """Build message(s) for tool results.

        Each result dict has keys: tool_call_id, content.
        Returns a list of message dicts to extend into the messages list.
        """
