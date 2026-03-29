"""LLM provider factory.

Provider and model selection via environment variables:
    LLM_PROVIDER  — "anthropic" (default), "openai", or "openai-codex"
    LLM_MODEL     — main model name (provider-specific default if unset)
"""

from __future__ import annotations

import os

from agent.providers.base import LLMError, LLMProvider, LLMResponse, ToolCall, Usage

# Default models per provider.
_DEFAULTS: dict[str, dict[str, str]] = {
    "anthropic": {
        "model": "claude-sonnet-4-20250514",
        "small_model": "claude-haiku-4-5-20251001",
    },
    "openai": {
        "model": "gpt-4o",
        "small_model": "gpt-4o-mini",
    },
    "openai-codex": {
        "model": "codex-mini-latest",
        "small_model": "codex-mini-latest",
    },
}

_provider_instance: LLMProvider | None = None


def get_provider() -> LLMProvider:
    """Return the singleton LLM provider (created on first call)."""
    global _provider_instance
    if _provider_instance is None:
        name = os.environ.get("LLM_PROVIDER", "anthropic").lower()
        if name == "openai-codex":
            from agent.providers.openai_codex import OpenAICodexProvider

            _provider_instance = OpenAICodexProvider()
        elif name == "openai":
            from agent.providers.openai import OpenAIProvider

            _provider_instance = OpenAIProvider()
        else:
            from agent.providers.anthropic import AnthropicProvider

            _provider_instance = AnthropicProvider()
    return _provider_instance


def get_model() -> str:
    """Return the main model name from env or provider default."""
    name = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    return os.environ.get("LLM_MODEL", _DEFAULTS.get(name, _DEFAULTS["anthropic"])["model"])


def get_small_model() -> str:
    """Return the small/cheap model for auxiliary tasks (compression, promotion)."""
    name = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    return os.environ.get(
        "LLM_SMALL_MODEL",
        _DEFAULTS.get(name, _DEFAULTS["anthropic"])["small_model"],
    )


__all__ = [
    "LLMError",
    "LLMProvider",
    "LLMResponse",
    "ToolCall",
    "Usage",
    "get_model",
    "get_provider",
    "get_small_model",
]
