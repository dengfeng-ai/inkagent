"""LLM provider factory.

Provider and model selection via environment variables:
    LLM_PROVIDER  — "anthropic" (default), "openai", "openai-codex", or "openai-compatible"
    LLM_MODEL     — main model name (provider-specific default if unset; required for openai-compatible)
"""

from __future__ import annotations

import os

from inkagent.providers.base import LLMError, LLMProvider, LLMResponse, ToolCall, Usage

# Default models per provider.
_DEFAULTS: dict[str, dict[str, str]] = {
    "anthropic": {
        "model": "claude-opus-4-6",
        "small_model": "claude-sonnet-4-6",
    },
    "openai": {
        "model": "gpt-5.4",
        "small_model": "gpt-5.4-mini",
    },
    "openai-codex": {
        "model": "gpt-5.4",
        "small_model": "gpt-5.4-mini",
    },
}

_provider_instance: LLMProvider | None = None


def get_provider_name() -> str:
    """Return the configured provider name (no instantiation)."""
    return os.environ.get("LLM_PROVIDER", "anthropic").lower()


def get_provider() -> LLMProvider:
    """Return the singleton LLM provider (created on first call)."""
    global _provider_instance
    if _provider_instance is None:
        name = get_provider_name()
        if name == "openai-codex":
            from inkagent.providers.openai_codex import OpenAICodexProvider

            _provider_instance = OpenAICodexProvider()
        elif name == "openai-compatible":
            from inkagent.providers.openai_compatible import OpenAICompatibleProvider

            _provider_instance = OpenAICompatibleProvider()
        elif name == "openai":
            from inkagent.providers.openai import OpenAIProvider

            _provider_instance = OpenAIProvider()
        else:
            from inkagent.providers.anthropic import AnthropicProvider

            _provider_instance = AnthropicProvider()
    return _provider_instance


def _require_model_env(name: str, var: str) -> str:
    value = os.environ.get(var)
    if not value:
        raise RuntimeError(
            f"LLM_PROVIDER={name} requires {var} to be set "
            "(model names are gateway-specific, e.g. 'azure/gpt-5.4-mini')."
        )
    return value


def get_model() -> str:
    """Return the main model name from env or provider default."""
    name = get_provider_name()
    if name == "openai-compatible":
        return _require_model_env(name, "LLM_MODEL")
    return os.environ.get("LLM_MODEL", _DEFAULTS.get(name, _DEFAULTS["anthropic"])["model"])


def get_small_model() -> str:
    """Return the small/cheap model for auxiliary tasks (compression, promotion)."""
    name = get_provider_name()
    if name == "openai-compatible":
        # Fall back to main model when small model is not configured; gateways
        # don't have a one-size-fits-all small-model name.
        return os.environ.get("LLM_SMALL_MODEL") or get_model()
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
    "get_provider_name",
    "get_small_model",
]
