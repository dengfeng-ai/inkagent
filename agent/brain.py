"""LLM agentic loop using Claude tool_use."""

import json
import logging
from datetime import datetime
from pathlib import Path

import anthropic
from langfuse import observe, get_client as get_langfuse

from agent import registry, memory

logger = logging.getLogger(__name__)

# Import skills so they self-register — never import skills directly here.
import skills  # noqa: F401

CONVERSATIONS_DIR = Path(__file__).resolve().parent.parent / "conversations"

SYSTEM_PROMPT = """\
You are a helpful personal AI assistant running locally on the user's machine.
{soul}
You have access to tools — use them when appropriate.
When the user tells you how to behave (name, tone, language, rules), use the update_soul tool to persist it.
When you learn something about the user's identity (name, role, location, interests), use the update_user_profile tool to persist it.
Use log_daily to jot down anything worth remembering — facts, preferences, decisions, topics discussed, action items. Important entries will be automatically promoted to long-term memory overnight. Use recall_memory to search past memories when relevant.
Do NOT write to MEMORY.md directly — it is managed by the promotion system.

# User
{user_profile}

# Long-term Memory
{long_term_memory}

# Daily Log
{daily_logs}
"""

PROMOTION_PROMPT = """\
You are a memory curator. Review yesterday's daily log and decide what (if anything) \
is worth keeping in long-term memory.

Current long-term memory (MEMORY.md):
{long_term_memory}

Yesterday's daily log ({date}):
{daily_log}

Rules:
- Only promote durable facts, preferences, decisions, or notable events.
- Skip anything transient, redundant with existing memory, or too trivial.
- Use the same format as existing MEMORY.md entries: ## YYYY-MM-DD | category
- If nothing is worth promoting, respond with exactly: NOTHING
- Do NOT repeat entries already in MEMORY.md.
- Be concise. Output ONLY the entries to append (or NOTHING). No explanation.
"""

SUMMARY_PROMPT = """\
Summarize the following conversation between a user and an AI assistant. \
Preserve all important facts, decisions, preferences, action items, and context. \
Be concise but do not lose key details. Output only the summary, no preamble.

Conversation:
{conversation}
"""

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-20250514"
PROMOTION_MODEL = "claude-haiku-4-5-20251001"

# Context window management.
MAX_CONTEXT_TOKENS = 200_000
COMPRESS_THRESHOLD = 160_000  # trigger compression at 80% capacity
CHARS_PER_TOKEN = 4  # rough estimate
KEEP_RECENT_MESSAGES = 6  # preserve last 3 turns (user+assistant pairs)

# Per-session conversation history and file paths.
_sessions: dict[str, list[dict]] = {}
_session_files: dict[str, Path] = {}


def _estimate_tokens(system: str, messages: list[dict], tools: list[dict]) -> int:
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
            # Tool results or multi-part content — extract text
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
    response = client.messages.create(
        model=PROMOTION_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def _maybe_compress(conversation: list[dict], system: str, tools: list[dict]) -> None:
    """Compress conversation history if approaching context window limit.

    Replaces old messages with a Haiku-generated summary, keeping recent
    messages intact. Modifies conversation list in place.
    """
    estimated = _estimate_tokens(system, conversation, tools)
    if estimated < COMPRESS_THRESHOLD:
        return

    if len(conversation) <= KEEP_RECENT_MESSAGES:
        return  # nothing to compress

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


def _get_conversation(session_id: str) -> list[dict]:
    """Get or create conversation history for a session."""
    if session_id not in _sessions:
        _sessions[session_id] = []
    return _sessions[session_id]


def _save_conversation(session_id: str) -> None:
    """Save conversation to the session JSON file."""
    if session_id not in _session_files:
        CONVERSATIONS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        _session_files[session_id] = CONVERSATIONS_DIR / f"{timestamp}_{session_id}.json"
    conversation = _sessions.get(session_id, [])
    _session_files[session_id].write_text(
        json.dumps(conversation, ensure_ascii=False, indent=2)
    )


def _maybe_promote() -> None:
    """Check if yesterday's daily log needs promotion; if so, ask LLM to curate."""
    if not memory.needs_promotion():
        return

    ctx = memory.get_promotion_context()
    prompt = PROMOTION_PROMPT.format(**ctx)

    logger.info("Running memory promotion for %s", ctx["date"])
    response = client.messages.create(
        model=PROMOTION_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    if text == "NOTHING":
        result = memory.apply_promotion("")
    else:
        result = memory.apply_promotion(text)
    logger.info("Promotion result: %s", result)


@observe()
def run_agent(user_input: str, session_id: str = "cli") -> str:
    """Run one full agentic turn: send message, loop on tool calls, return final text."""
    get_langfuse().update_current_span(input=user_input)

    _maybe_promote()

    conversation = _get_conversation(session_id)
    conversation.append({"role": "user", "content": user_input})

    soul = memory.get_soul()
    user_profile = memory.get_user_profile()
    long_term_memory = memory.get_long_term_memory()
    daily_logs = memory.get_daily_logs()
    system = SYSTEM_PROMPT.format(
        soul=soul if soul else "",
        user_profile=user_profile if user_profile else "(no user info yet)",
        long_term_memory=long_term_memory if long_term_memory else "(no memories yet)",
        daily_logs=daily_logs if daily_logs else "(no daily logs yet)",
    )
    tools = registry.get_tools()

    # Compress conversation if approaching context window limit.
    _maybe_compress(conversation, system, tools)

    messages = list(conversation)

    while True:
        response = _call_llm(system, messages, tools)

        if response.stop_reason == "tool_use":
            # Collect all tool_use blocks and execute them
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    result = _execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            # end_turn — extract text and return
            text_parts = [b.text for b in response.content if hasattr(b, "text")]
            reply = "\n".join(text_parts)
            conversation.append({"role": "assistant", "content": reply})
            _save_conversation(session_id)
            get_langfuse().update_current_span(output=reply)
            return reply


@observe(as_type="generation")
def _call_llm(system: str, messages: list, tools: list) -> anthropic.types.Message:
    """Call Claude API — tracked as a generation span in Langfuse."""
    lf = get_langfuse()
    lf.update_current_generation(
        model=MODEL,
        input={"system": system, "messages": messages, "tools": tools},
        model_parameters={"max_tokens": 4096},
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system,
        messages=messages,
        tools=tools,
    )
    lf.update_current_generation(
        output=response.content,
        usage_details={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )
    return response


@observe(as_type="tool")
def _execute_tool(name: str, tool_input: dict) -> str:
    """Execute a tool — tracked as a tool span in Langfuse."""
    lf = get_langfuse()
    lf.update_current_span(input={"tool": name, **tool_input})
    result = registry.call_tool(name, tool_input)
    lf.update_current_span(output=result)
    return result
