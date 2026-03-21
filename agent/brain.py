"""LLM agentic loop using Claude tool_use."""

import anthropic
from langfuse import observe, get_client as get_langfuse

from agent import registry, memory

# Import skills so they self-register — never import skills directly here.
import skills  # noqa: F401

SYSTEM_PROMPT = """\
You are inkagent, a helpful personal AI assistant running locally on the user's machine.
You have access to tools — use them when appropriate.
When you learn something new about the user, use the update_profile tool to persist it.
Be concise and direct.

# Memory
{memory_context}
"""

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-20250514"

# In-memory conversation history for the current session.
_conversation: list[dict] = []


@observe()
def run_agent(user_input: str) -> str:
    """Run one full agentic turn: send message, loop on tool calls, return final text."""
    get_langfuse().update_current_span(input=user_input)

    _conversation.append({"role": "user", "content": user_input})

    system = SYSTEM_PROMPT.format(memory_context=memory.build_context())
    messages = list(_conversation)
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
            _conversation.append({"role": "assistant", "content": reply})
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
