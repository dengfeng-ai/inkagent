"""OpenAI LLM provider."""

from __future__ import annotations

import json
import uuid

from openai import OpenAI, APIError

from agent.providers.base import LLMError, LLMProvider, LLMResponse, ToolCall, Usage


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

        try:
            raw = self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=full_messages,
                tools=tools if tools else None,
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

    def simple_complete(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int,
    ) -> str:
        try:
            raw = self._client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
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
