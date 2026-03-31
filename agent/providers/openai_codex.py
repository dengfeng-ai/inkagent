"""OpenAI Codex provider — uses ChatGPT subscription via OAuth.

Targets the Codex Responses API endpoint at chatgpt.com, authenticated with
an OAuth token obtained through ``agent.codex_auth``.

The Responses API format differs from Chat Completions:
- System prompt goes in ``instructions`` (not a system message).
- Tool calls / results are flat items in the ``input`` array.
- Response ``output`` contains typed items (message, function_call, …).
"""

from __future__ import annotations

import json
import logging
import time

import httpx

from agent.codex_auth import get_codex_auth
from agent.providers.base import LLMError, LLMProvider, LLMResponse, ToolCall, Usage

logger = logging.getLogger(__name__)

CODEX_API_URL = "https://chatgpt.com/backend-api/codex/responses"

# Retry config for transient errors (429, 5xx).
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0  # seconds, doubled each retry
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class OpenAICodexProvider(LLMProvider):

    def __init__(self) -> None:
        self._auth = get_codex_auth()
        if not self._auth.is_logged_in():
            raise LLMError(
                "Codex not authenticated. Run `python -m agent.codex_auth` to log in."
            )

    # ── Core interface ───────────────────────────────────────────────

    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> LLMResponse:
        input_items = self._build_input(messages)

        payload: dict = {
            "model": model,
            "instructions": system,
            "input": input_items,
            "store": False,
        }
        if tools:
            payload["tools"] = tools

        raw = self._request(payload)
        return self._parse_response(raw)

    def simple_complete(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int,
    ) -> str:
        payload = {
            "model": model,
            "instructions": "You are a helpful assistant.",
            "input": [{"role": "user", "content": prompt}],
            "store": False,
        }
        raw = self._request(payload)
        return self._extract_text(raw)

    def format_tools(self, tools: list[dict]) -> list:
        """Convert Anthropic-style tool defs to Responses API function format."""
        return [
            {
                "type": "function",
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            }
            for t in tools
        ]

    def assistant_message(self, response: LLMResponse) -> dict:
        """Pack the assistant's output items into a carrier dict.

        The agentic loop in brain.py appends this to the messages list.
        When ``complete()`` is called again, ``_build_input()`` unpacks
        ``_codex_items`` back into the flat Responses API ``input`` array.
        """
        items: list[dict] = []
        if response.text:
            items.append({
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": response.text}],
            })
        for tc in response.tool_calls:
            items.append({
                "type": "function_call",
                "call_id": tc.id,
                "name": tc.name,
                "arguments": json.dumps(tc.input),
            })
        return {"_codex_items": items}

    def tool_results_messages(self, results: list[dict[str, str]]) -> list[dict]:
        """Pack tool results as function_call_output items."""
        items = [
            {
                "type": "function_call_output",
                "call_id": r["tool_call_id"],
                "output": r["content"],
            }
            for r in results
        ]
        return [{"_codex_items": items}]

    # ── Internal helpers ─────────────────────────────────────────────

    def _request(self, payload: dict) -> dict:
        """Send a streaming request to the Codex Responses API with retry.

        The Codex endpoint requires ``stream: true``.  We consume SSE events
        and return the final ``response.completed`` payload, which has the
        same shape as a non-streaming Responses API response.

        Retries up to ``_MAX_RETRIES`` times on transient HTTP errors
        (429, 5xx) with exponential backoff.
        """
        payload["stream"] = True
        token = self._auth.get_access_token()
        account_id = self._auth.get_account_id()

        headers: dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "OpenAI-Beta": "responses=experimental",
        }
        if account_id:
            headers["chatgpt-account-id"] = account_id

        last_error: LLMError | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                with httpx.stream(
                    "POST",
                    CODEX_API_URL,
                    headers=headers,
                    json=payload,
                    timeout=120,
                ) as resp:
                    if resp.status_code >= 400:
                        error_body = resp.read().decode()
                        err = LLMError(
                            f"Codex API error {resp.status_code}: {error_body}"
                        )
                        if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                            delay = _RETRY_BASE_DELAY * (2 ** attempt)
                            logger.warning(
                                "Codex %d error, retrying in %.1fs (%d/%d)",
                                resp.status_code, delay, attempt + 1, _MAX_RETRIES,
                            )
                            last_error = err
                            time.sleep(delay)
                            continue
                        raise err
                    return self._consume_sse(resp)
            except httpx.RequestError as e:
                err = LLMError(f"Codex request failed: {e}", original=e)
                if attempt < _MAX_RETRIES:
                    delay = _RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "Codex request error, retrying in %.1fs (%d/%d): %s",
                        delay, attempt + 1, _MAX_RETRIES, e,
                    )
                    last_error = err
                    time.sleep(delay)
                    continue
                raise err from e

        # Should not reach here, but just in case.
        raise last_error or LLMError("Codex request failed after retries.")

    @staticmethod
    def _consume_sse(resp: httpx.Response) -> dict:
        """Read SSE lines and return the ``response.completed`` data payload.

        Also handles ``response.failed`` and ``error`` events from the stream.
        """
        completed: dict = {}
        for line in resp.iter_lines():
            if not line.startswith("data: "):
                continue
            data_str = line[6:]
            if data_str == "[DONE]":
                break
            try:
                event = json.loads(data_str)
            except json.JSONDecodeError:
                continue

            event_type = event.get("type", "")

            if event_type == "response.completed":
                completed = event.get("response", event)
            elif event_type == "response.failed":
                error_info = event.get("response", {}).get("error", {})
                msg = error_info.get("message", "Unknown error")
                code = error_info.get("code", "")
                raise LLMError(f"Codex response failed ({code}): {msg}")
            elif event_type == "error":
                msg = event.get("message", event.get("error", "Unknown stream error"))
                raise LLMError(f"Codex stream error: {msg}")

        if not completed:
            raise LLMError("Codex stream ended without a response.completed event.")
        return completed

    @staticmethod
    def _build_input(messages: list[dict]) -> list[dict]:
        """Convert the message list into a flat Responses API ``input`` array.

        Regular role/content dicts pass through as-is.  Carrier dicts
        created by ``assistant_message`` / ``tool_results_messages`` are
        expanded via the ``_codex_items`` key.
        """
        items: list[dict] = []
        for m in messages:
            if "_codex_items" in m:
                items.extend(m["_codex_items"])
            else:
                items.append({"role": m["role"], "content": m.get("content", "")})
        return items

    @staticmethod
    def _parse_response(raw: dict) -> LLMResponse:
        """Parse a Responses API response dict into an ``LLMResponse``."""
        output = raw.get("output", [])

        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for item in output:
            item_type = item.get("type")
            if item_type == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        text_parts.append(part.get("text", ""))
            elif item_type == "function_call":
                try:
                    args = json.loads(item.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(
                    ToolCall(
                        id=item.get("call_id", ""),
                        name=item.get("name", ""),
                        input=args,
                    )
                )

        text = "\n".join(text_parts) if text_parts else None
        stop_reason = "tool_use" if tool_calls else "end_turn"

        usage_data = raw.get("usage", {})
        usage = Usage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
        )

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
            raw=raw,
        )

    @staticmethod
    def _extract_text(raw: dict) -> str:
        """Extract plain text from a Responses API response."""
        parts: list[str] = []
        for item in raw.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        parts.append(content.get("text", ""))
        return "\n".join(parts).strip()
