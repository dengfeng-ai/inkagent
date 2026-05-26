"""Tests for the LLM provider factory and the openai-compatible provider."""

from __future__ import annotations

import pytest

from inkagent import providers
from inkagent.providers.openai import _needs_completion_tokens
from inkagent.providers.openai_compatible import OpenAICompatibleProvider


@pytest.fixture(autouse=True)
def reset_provider_singleton(monkeypatch):
    """Clear the cached singleton + any LLM_* env between tests."""
    monkeypatch.setattr(providers, "_provider_instance", None)
    for var in (
        "LLM_PROVIDER",
        "LLM_MODEL",
        "LLM_SMALL_MODEL",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_VERIFY_SSL",
        "LLM_EXTRA_HEADERS",
    ):
        monkeypatch.delenv(var, raising=False)
    yield
    providers._provider_instance = None


# ---------------------------------------------------------------------------
# _needs_completion_tokens — strips routing prefixes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "model,expected",
    [
        ("gpt-5", True),
        ("gpt-5.4-mini", True),
        ("o1-mini", True),
        ("gpt-4-turbo", False),
        ("azure/gpt-5.4-mini", True),
        ("openrouter/openai/gpt-5", True),
        ("openrouter/anthropic/claude-3", False),
        ("litellm/anything/gpt-4", False),
    ],
)
def test_needs_completion_tokens_handles_prefixes(model, expected):
    assert _needs_completion_tokens(model) is expected


# ---------------------------------------------------------------------------
# OpenAICompatibleProvider — env-var parsing
# ---------------------------------------------------------------------------

def test_missing_base_url_raises(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    with pytest.raises(RuntimeError, match="LLM_BASE_URL"):
        OpenAICompatibleProvider()


def test_base_url_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example.com/")
    p = OpenAICompatibleProvider()
    # OpenAI SDK appends its own path components — assert the configured base
    # has no trailing slash.
    assert str(p._client.base_url).rstrip("/") == "https://gw.example.com"


def test_default_api_key_when_unset(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example.com")
    p = OpenAICompatibleProvider()
    assert p._client.api_key == "sk-noauth"


def test_explicit_api_key(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example.com")
    monkeypatch.setenv("LLM_API_KEY", "sk-real-token")
    p = OpenAICompatibleProvider()
    assert p._client.api_key == "sk-real-token"


def _spy_httpx_client(monkeypatch):
    """Spy on httpx.Client to capture the kwargs the provider passes in.

    Subclasses the real class so the OpenAI SDK's isinstance check still passes.
    """
    import httpx

    captured: dict = {}

    class SpyClient(httpx.Client):
        def __init__(self, *args, **kwargs):
            captured.update(kwargs)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(
        "inkagent.providers.openai_compatible.httpx.Client", SpyClient
    )
    return captured


def test_verify_ssl_defaults_true(monkeypatch):
    captured = _spy_httpx_client(monkeypatch)
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example.com")
    OpenAICompatibleProvider()
    assert captured["verify"] is True


def test_verify_ssl_disabled(monkeypatch):
    captured = _spy_httpx_client(monkeypatch)
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example.com")
    monkeypatch.setenv("LLM_VERIFY_SSL", "false")
    OpenAICompatibleProvider()
    assert captured["verify"] is False


def test_verify_ssl_case_insensitive(monkeypatch):
    captured = _spy_httpx_client(monkeypatch)
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example.com")
    monkeypatch.setenv("LLM_VERIFY_SSL", "FALSE")
    OpenAICompatibleProvider()
    assert captured["verify"] is False


def test_extra_headers_parsed(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example.com")
    monkeypatch.setenv("LLM_EXTRA_HEADERS", '{"x-tenant":"team-a","x-trace":"abc"}')
    p = OpenAICompatibleProvider()
    headers = {k.lower(): v for k, v in p._client._client.headers.items()}
    assert headers.get("x-tenant") == "team-a"
    assert headers.get("x-trace") == "abc"


def test_extra_headers_invalid_json_raises(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example.com")
    monkeypatch.setenv("LLM_EXTRA_HEADERS", "not-json")
    with pytest.raises(RuntimeError, match="JSON object"):
        OpenAICompatibleProvider()


def test_extra_headers_non_object_raises(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example.com")
    monkeypatch.setenv("LLM_EXTRA_HEADERS", '["x-tenant", "team-a"]')
    with pytest.raises(RuntimeError, match="JSON object"):
        OpenAICompatibleProvider()


# ---------------------------------------------------------------------------
# Factory wiring + model name resolution
# ---------------------------------------------------------------------------

def test_factory_returns_openai_compatible(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example.com")
    p = providers.get_provider()
    assert isinstance(p, OpenAICompatibleProvider)


def test_factory_singleton(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_BASE_URL", "https://gw.example.com")
    assert providers.get_provider() is providers.get_provider()


def test_get_model_requires_llm_model_for_compatible(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    with pytest.raises(RuntimeError, match="LLM_MODEL"):
        providers.get_model()


def test_get_model_returns_env_value(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_MODEL", "azure/gpt-5.4-mini")
    assert providers.get_model() == "azure/gpt-5.4-mini"


def test_get_small_model_falls_back_to_main(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_MODEL", "azure/gpt-5.4-mini")
    assert providers.get_small_model() == "azure/gpt-5.4-mini"


def test_get_small_model_uses_env_when_set(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("LLM_MODEL", "azure/gpt-5.4")
    monkeypatch.setenv("LLM_SMALL_MODEL", "azure/gpt-5.4-mini")
    assert providers.get_small_model() == "azure/gpt-5.4-mini"
