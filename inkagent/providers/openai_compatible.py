"""OpenAI-compatible LLM provider.

Targets any gateway/proxy that speaks the OpenAI Chat Completions protocol
(LiteLLM, OpenRouter, Together, Fireworks, Ollama, vLLM, ...). Inherits the
message/tool-call handling from OpenAIProvider and only swaps the HTTP client
configuration (base URL, auth header, TLS verification, extra headers).

Env vars:
    LLM_BASE_URL        — required, e.g. https://litellm.example.com
    LLM_API_KEY         — bearer token (defaults to "sk-noauth" for open gateways)
    LLM_VERIFY_SSL      — "false" to skip TLS verification (default: true)
    LLM_EXTRA_HEADERS   — JSON object of extra request headers (optional)
"""

from __future__ import annotations

import json
import os

import httpx
from openai import OpenAI

from inkagent.providers.openai import OpenAIProvider


class OpenAICompatibleProvider(OpenAIProvider):

    def __init__(self) -> None:
        base_url = os.environ.get("LLM_BASE_URL")
        if not base_url:
            raise RuntimeError(
                "LLM_PROVIDER=openai-compatible requires LLM_BASE_URL to be set."
            )

        api_key = os.environ.get("LLM_API_KEY", "sk-noauth")
        verify = os.environ.get("LLM_VERIFY_SSL", "true").strip().lower() != "false"

        raw_headers = os.environ.get("LLM_EXTRA_HEADERS", "").strip()
        extra_headers: dict[str, str] = {}
        if raw_headers:
            try:
                parsed = json.loads(raw_headers)
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"LLM_EXTRA_HEADERS must be a JSON object: {e}"
                ) from e
            if not isinstance(parsed, dict):
                raise RuntimeError("LLM_EXTRA_HEADERS must be a JSON object.")
            extra_headers = {str(k): str(v) for k, v in parsed.items()}

        http_client = httpx.Client(verify=verify, headers=extra_headers or None)
        self._client = OpenAI(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            http_client=http_client,
        )
