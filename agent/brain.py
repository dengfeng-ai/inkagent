"""LLM agentic loop using Claude tool_use."""

import json
from datetime import datetime
from pathlib import Path

import anthropic
from langfuse import observe, get_client as get_langfuse

from agent import registry, memory

# Import skills so they self-register — never import skills directly here.
import skills  # noqa: F401

CONVERSATIONS_DIR = Path(__file__).resolve().parent.parent / "conversations"

SYSTEM_PROMPT = """\
You are a helpful personal AI assistant running locally on the user's machine.
{soul}
You have access to tools — use them when appropriate.
When the user tells you how to behave (name, tone, language, rules), use the update_soul tool to persist it.
When you learn something about the user's identity (name, role, location, interests), use the update_user_profile tool to persist it.
When the user shares a durable fact, preference, decision, or notable event, use the save_memory tool to persist it. Use recall_memory to look up past memories when relevant.
Do NOT save transient info (current tasks, project stats, session context) to any memory file.

# User
{user_profile}

# Long-term Memory
{long_term_memory}
"""

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-20250514"

# Per-session conversation history and file paths.
_sessions: dict[str, list[dict]] = {}
_session_files: dict[str, Path] = {}


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


@observe()
def run_agent(user_input: str, session_id: str = "cli") -> str:
    """Run one full agentic turn: send message, loop on tool calls, return final text."""
    get_langfuse().update_current_span(input=user_input)

    conversation = _get_conversation(session_id)
    conversation.append({"role": "user", "content": user_input})

    soul = memory.get_soul()
    user_profile = memory.get_user_profile()
    long_term_memory = memory.get_long_term_memory()
    system = SYSTEM_PROMPT.format(
        soul=soul if soul else "",
        user_profile=user_profile if user_profile else "(no user info yet)",
        long_term_memory=long_term_memory if long_term_memory else "(no memories yet)",
    )
    messages = list(conversation)
    tools = registry.get_tools()

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
