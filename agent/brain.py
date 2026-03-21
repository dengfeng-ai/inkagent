"""LLM agentic loop using Claude tool_use."""

import anthropic

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


def run_agent(user_input: str) -> str:
    """Run one full agentic turn: send message, loop on tool calls, return final text."""
    memory.save_turn("user", user_input)

    system = SYSTEM_PROMPT.format(memory_context=memory.build_context())
    messages = [{"role": "user", "content": user_input}]
    tools = registry.get_tools()

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            messages=messages,
            tools=tools,
        )

        if response.stop_reason == "tool_use":
            # Collect all tool_use blocks and execute them
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    result = registry.call_tool(block.name, block.input)
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
            memory.save_turn("assistant", reply)
            return reply
