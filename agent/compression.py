"""Context window management — token estimation and conversation compression."""

import json
import logging

from agent.config import (
    CHARS_PER_TOKEN,
    COMPRESS_THRESHOLD,
    KEEP_RECENT_MESSAGES,
    MAX_CONTEXT_TOKENS,
)
from agent.prompts import SUMMARY_PROMPT
from agent.providers import get_provider, get_small_model, LLMError
from agent.session import make_message
from agent.tracing import observe, get_langfuse

logger = logging.getLogger(__name__)


def estimate_tokens(system: str, messages: list[dict], tools: list[dict]) -> int:
    """Rough token estimate based on character count."""
    total_chars = len(system) + len(json.dumps(tools, ensure_ascii=False))
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        elif isinstance(content, list):
            total_chars += len(json.dumps(content, ensure_ascii=False))
    return total_chars // CHARS_PER_TOKEN


def _format_messages_for_summary(messages: list[dict]) -> str:
    """Format conversation messages into readable text for summarization."""
    lines = []
    for msg in messages:
        role = msg["role"].capitalize()
        content = msg.get("content", "")
        if isinstance(content, str):
            lines.append(f"{role}: {content}")
        elif isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_result":
                    parts.append(f"[tool result: {item.get('content', '')[:200]}]")
                elif isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            if parts:
                lines.append(f"{role}: {' '.join(parts)}")
    return "\n".join(lines)


@observe(as_type="generation")
def _summarize_messages(messages: list[dict]) -> str:
    """Use a small model to summarize old conversation messages."""
    text = _format_messages_for_summary(messages)
    prompt = SUMMARY_PROMPT.format(conversation=text)
    model = get_small_model()

    logger.info("Summarizing %d messages for context compression", len(messages))
    lf = get_langfuse()
    lf.update_current_generation(
        name="compression",
        model=model,
        input=prompt,
        model_parameters={"max_tokens": 1024},
    )
    try:
        result = get_provider().simple_complete(
            model=model,
            prompt=prompt,
            max_tokens=1024,
        )
        lf.update_current_generation(output=result)
        return result
    except LLMError as e:
        logger.error("Summarization API call failed: %s", e)
        return f"[Summary unavailable — earlier conversation context was dropped]\n{text[:500]}"


def force_compress(conversation: list[dict]) -> tuple[int, int]:
    """Force-compress conversation regardless of token threshold.

    Returns (before_count, after_count).
    """
    before = len(conversation)
    if before <= KEEP_RECENT_MESSAGES:
        return before, before

    split_idx = before - KEEP_RECENT_MESSAGES
    if split_idx > 0 and conversation[split_idx].get("role") != "user":
        split_idx -= 1
    if split_idx <= 0:
        return before, before

    old_messages = conversation[:split_idx]
    kept_messages = conversation[split_idx:]

    summary = _summarize_messages(old_messages)

    conversation.clear()
    conversation.append(make_message(
        "user",
        f"[Summary of previous conversation]\n{summary}",
    ))
    conversation.append(make_message(
        "assistant",
        "Got it, I have the context from our earlier conversation.",
    ))
    conversation.extend(kept_messages)

    logger.info("Force-compressed: %d messages → %d", before, len(conversation))
    return before, len(conversation)


def maybe_compress(conversation: list[dict], system: str, tools: list[dict]) -> None:
    """Compress conversation history if approaching context window limit.

    Replaces old messages with a summary, keeping recent messages intact.
    Modifies conversation list in place.
    """
    estimated = estimate_tokens(system, conversation, tools)
    if estimated < COMPRESS_THRESHOLD:
        return

    if len(conversation) <= KEEP_RECENT_MESSAGES:
        return

    # Split: old messages to summarize, recent messages to keep
    split_idx = len(conversation) - KEEP_RECENT_MESSAGES
    # Ensure split lands on a user message boundary so alternation is preserved
    if split_idx > 0 and conversation[split_idx].get("role") != "user":
        split_idx -= 1

    if split_idx <= 0:
        return

    old_messages = conversation[:split_idx]
    kept_messages = conversation[split_idx:]

    summary = _summarize_messages(old_messages)

    # Rebuild conversation: summary pair + recent messages
    conversation.clear()
    conversation.append(make_message(
        "user",
        f"[Summary of previous conversation]\n{summary}",
    ))
    conversation.append(make_message(
        "assistant",
        "Got it, I have the context from our earlier conversation.",
    ))
    conversation.extend(kept_messages)

    logger.info(
        "Compressed conversation: %d messages → %d (summarized %d old messages)",
        split_idx + len(kept_messages), len(conversation), len(old_messages),
    )
