"""Anthropic (Claude) LLM provider."""

from __future__ import annotations

import anthropic

from inkagent.providers.base import LLMError, LLMProvider, LLMResponse, ToolCall, Usage


class AnthropicProvider(LLMProvider):

    def __init__(self) -> None:
        self._client = anthropic.Anthropic()

    def complete(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
    ) -> LLMResponse:
        try:
            raw = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                tools=tools,
            )
        except anthropic.APIError as e:
            raise LLMError(str(e), original=e) from e

        # Parse text and tool calls from content blocks.
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []
        for block in raw.content:
            if block.type == "text" and block.text.strip():
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=block.input)
                )

        return LLMResponse(
            text="\n".join(text_parts) if text_parts else None,
            tool_calls=tool_calls,
            stop_reason="tool_use" if raw.stop_reason == "tool_use" else "end_turn",
            usage=Usage(raw.usage.input_tokens, raw.usage.output_tokens),
            raw=raw,
        )

    def simple_complete(
        self,
        *,
        model: str,
        prompt: str,
        max_tokens: int,
    ) -> str:
        try:
            raw = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as e:
            raise LLMError(str(e), original=e) from e
        return raw.content[0].text.strip()

    def format_tools(self, tools: list[dict]) -> list:
        # Registry already returns Anthropic-native format.
        return tools

    def assistant_message(self, response: LLMResponse) -> dict:
        # Use the raw Anthropic content blocks directly.
        return {"role": "assistant", "content": response.raw.content}

    def tool_results_messages(self, results: list[dict[str, str]]) -> list[dict]:
        return [
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": r["tool_call_id"],
                        "content": r["content"],
                    }
                    for r in results
                ],
            }
        ]
