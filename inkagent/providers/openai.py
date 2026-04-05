"""OpenAI LLM provider."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable

from openai import OpenAI, APIError

from inkagent.providers.base import LLMError, LLMProvider, LLMResponse, ToolCall, Usage

# Models that require max_completion_tokens instead of max_tokens.
_COMPLETION_TOKENS_PREFIXES = ("o1", "o3", "o4", "gpt-5")


def _needs_completion_tokens(model: str) -> bool:
    return any(model.startswith(p) for p in _COMPLETION_TOKENS_PREFIXES)


class OpenAIProvider(LLMProvider):

    def __init__(self) -> None:
        self._client = OpenAI()

    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> LLMResponse:
        # Prepend system message.
        full_messages = [{"role": "system", "content": system}] + messages

        # GPT-5.x and o-series require max_completion_tokens instead of max_tokens.
        token_param = "max_completion_tokens" if _needs_completion_tokens(model) else "max_tokens"

        try:
            raw = self._client.chat.completions.create(
                model=model,
                messages=full_messages,
                tools=tools if tools else None,
                **{token_param: max_tokens},
            )
        except APIError as e:
            raise LLMError(str(e), original=e) from e

        choice = raw.choices[0]
        message = choice.message

        # Parse tool calls.
        tool_calls: list[ToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(
                    ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        input=args,
                    )
                )

        stop_reason = (
            "tool_use" if choice.finish_reason == "tool_calls" else "end_turn"
        )

        usage_obj = raw.usage
        usage = Usage(
            input_tokens=usage_obj.prompt_tokens if usage_obj else 0,
            output_tokens=usage_obj.completion_tokens if usage_obj else 0,
        )

        return LLMResponse(
            text=message.content if message.content else None,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
            raw=message,
        )

    def stream_complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
        on_text: Callable[[str], None],
    ) -> LLMResponse:
        full_messages = [{"role": "system", "content": system}] + messages
        token_param = "max_completion_tokens" if _needs_completion_tokens(model) else "max_tokens"

        try:
            stream = self._client.chat.completions.create(
                model=model,
                messages=full_messages,
                tools=tools if tools else None,
                stream=True,
                stream_options={"include_usage": True},
                **{token_param: max_tokens},
            )
        except APIError as e:
            raise LLMError(str(e), original=e) from e

        text_parts: list[str] = []
        tool_calls_by_index: dict[int, dict] = {}
        finish_reason: str | None = None
        usage = Usage(0, 0)

        try:
            for chunk in stream:
                if not chunk.choices:
                    # Final chunk with usage only.
                    if chunk.usage:
                        usage = Usage(
                            input_tokens=chunk.usage.prompt_tokens or 0,
                            output_tokens=chunk.usage.completion_tokens or 0,
                        )
                    continue

                choice = chunk.choices[0]
                delta = choice.delta

                if delta and delta.content:
                    on_text(delta.content)
                    text_parts.append(delta.content)

                if delta and delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_by_index:
                            tool_calls_by_index[idx] = {
                                "id": tc_delta.id or "",
                                "name": "",
                                "arguments": "",
                            }
                        if tc_delta.id:
                            tool_calls_by_index[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls_by_index[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_calls_by_index[idx]["arguments"] += tc_delta.function.arguments

                if choice.finish_reason:
                    finish_reason = choice.finish_reason
        except APIError as e:
            raise LLMError(str(e), original=e) from e

        tool_calls: list[ToolCall] = []
        for _idx in sorted(tool_calls_by_index):
            tc_data = tool_calls_by_index[_idx]
            try:
                args = json.loads(tc_data["arguments"])
            except (json.JSONDecodeError, TypeError):
                args = {}
            tool_calls.append(ToolCall(id=tc_data["id"], name=tc_data["name"], input=args))

        text = "".join(text_parts) if text_parts else None
        stop_reason = "tool_use" if finish_reason == "tool_calls" else "end_turn"

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            usage=usage,
            raw=None,
        )

    def simple_complete(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int,
    ) -> str:
        token_param = "max_completion_tokens" if _needs_completion_tokens(model) else "max_tokens"

        try:
            raw = self._client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                **{token_param: max_tokens},
            )
        except APIError as e:
            raise LLMError(str(e), original=e) from e
        content = raw.choices[0].message.content
        return content.strip() if content else ""

    def format_tools(self, tools: list[dict]) -> list:
        """Convert Anthropic-style tool defs to OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

    def assistant_message(self, response: LLMResponse) -> dict:
        """Rebuild OpenAI-format assistant message from LLMResponse."""
        msg: dict = {"role": "assistant"}

        if response.text:
            msg["content"] = response.text

        if response.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.input),
                    },
                }
                for tc in response.tool_calls
            ]

        return msg

    def tool_results_messages(self, results: list[dict[str, str]]) -> list[dict]:
        """Each tool result is a separate message in OpenAI format."""
        return [
            {
                "role": "tool",
                "tool_call_id": r["tool_call_id"],
                "content": r["content"],
            }
            for r in results
        ]
