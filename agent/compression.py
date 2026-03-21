"""Context window management — token estimation and conversation compression."""

import json
import logging

import anthropic

from agent.prompts import SUMMARY_PROMPT

logger = logging.getLogger(__name__)

# Context window management.
MAX_CONTEXT_TOKENS = 200_000
COMPRESS_THRESHOLD = 160_000  # trigger compression at 80% capacity
CHARS_PER_TOKEN = 4  # rough estimate
KEEP_RECENT_MESSAGES = 6  # preserve last 3 turns (user+assistant pairs)

COMPRESSION_MODEL = "claude-haiku-4-5-20251001"

_client = anthropic.Anthropic()


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


def _summarize_messages(messages: list[dict]) -> str:
    """Use Haiku to summarize old conversation messages."""
    text = _format_messages_for_summary(messages)
    prompt = SUMMARY_PROMPT.format(conversation=text)

    logger.info("Summarizing %d messages for context compression", len(messages))
    try:
        response = _client.messages.create(
            model=COMPRESSION_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()
    except anthropic.APIError as e:
        logger.error("Summarization API call failed: %s", e)
        return f"[Summary unavailable — earlier conversation context was dropped]\n{text[:500]}"


def maybe_compress(conversation: list[dict], system: str, tools: list[dict]) -> None:
    """Compress conversation history if approaching context window limit.

    Replaces old messages with a Haiku-generated summary, keeping recent
    messages intact. Modifies conversation list in place.
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

    old_messages = conversation[:split_idx]
    kept_messages = conversation[split_idx:]

    summary = _summarize_messages(old_messages)

    # Rebuild conversation: summary pair + recent messages
    conversation.clear()
    conversation.append({
        "role": "user",
        "content": f"[Summary of previous conversation]\n{summary}",
    })
    conversation.append({
        "role": "assistant",
        "content": "Got it, I have the context from our earlier conversation.",
    })
    conversation.extend(kept_messages)

    logger.info(
        "Compressed conversation: %d messages → %d (summarized %d old messages)",
        split_idx + len(kept_messages), len(conversation), len(old_messages),
    )
