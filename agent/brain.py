"""LLM agentic loop using Claude tool_use."""

import logging

import anthropic
from langfuse import observe, get_client as get_langfuse

from agent import registry, memory
from agent.prompts import SYSTEM_PROMPT
from agent.session import get_conversation, save_conversation
from agent.compression import maybe_compress
from agent.promotion import maybe_promote

logger = logging.getLogger(__name__)

# Import skills so they self-register — never import skills directly here.
import skills  # noqa: F401

client = anthropic.Anthropic()
MODEL = "claude-sonnet-4-20250514"


@observe()
def run_agent(user_input: str, session_id: str = "cli") -> str:
    """Run one full agentic turn: send message, loop on tool calls, return final text."""
    get_langfuse().update_current_span(input=user_input)

    maybe_promote()

    conversation = get_conversation(session_id)
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
    maybe_compress(conversation, system, tools)

    messages = list(conversation)

    collected_text: list[str] = []

    try:
        while True:
            response = _call_llm(system, messages, tools)

            if response.stop_reason == "tool_use":
                assistant_content = response.content

                # Capture text blocks before processing tools.
                for block in assistant_content:
                    if block.type == "text" and block.text.strip():
                        collected_text.append(block.text)

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
                # end_turn — combine collected text with final response text.
                text_parts = [b.text for b in response.content if b.type == "text"]
                reply = "\n".join(collected_text + text_parts).strip()
                conversation.append({"role": "assistant", "content": reply})
                save_conversation(session_id)
                get_langfuse().update_current_span(output=reply)
                return reply
    except anthropic.APIError as e:
        logger.error("API call failed: %s", e)
        if conversation and conversation[-1].get("role") == "user":
            conversation.pop()
        raise


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
