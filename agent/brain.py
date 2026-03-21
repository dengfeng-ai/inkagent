"""LLM agentic loop using pluggable provider."""

import logging
import os

from agent import registry, memory
from agent.prompts import SYSTEM_PROMPT
from agent.session import get_conversation, save_conversation
from agent.compression import maybe_compress
from agent.promotion import maybe_promote
from agent.providers import get_provider, get_model, LLMError

logger = logging.getLogger(__name__)

# Langfuse is optional — only enable when credentials are configured.
_langfuse_enabled = bool(os.environ.get("LANGFUSE_PUBLIC_KEY"))

if _langfuse_enabled:
    from langfuse import observe as _observe, get_client as _get_langfuse
else:
    # No-op replacements when Langfuse is not configured.
    def _observe(**kwargs):
        """No-op decorator."""
        def decorator(fn):
            return fn
        return decorator

    class _NullLangfuse:
        """Stub that silently ignores all method calls."""
        def __getattr__(self, _name):
            return lambda *a, **kw: None

    _null_lf = _NullLangfuse()

    def _get_langfuse():
        return _null_lf

# Import skills so they self-register — never import skills directly here.
import skills  # noqa: F401


@_observe()
def run_agent(user_input: str, session_id: str = "cli") -> str:
    """Run one full agentic turn: send message, loop on tool calls, return final text."""
    _get_langfuse().update_current_span(input=user_input)

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

    provider = get_provider()
    model = get_model()
    raw_tools = registry.get_tools()
    tools = provider.format_tools(raw_tools)

    # Compress conversation if approaching context window limit.
    maybe_compress(conversation, system, tools)

    messages = list(conversation)

    collected_text: list[str] = []

    try:
        while True:
            response = _call_llm(system, messages, tools, model)

            if response.stop_reason == "tool_use":
                if response.text:
                    collected_text.append(response.text)

                messages.append(provider.assistant_message(response))

                tool_results = []
                for tc in response.tool_calls:
                    result = _execute_tool(tc.name, tc.input)
                    tool_results.append({
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                messages.extend(provider.tool_results_messages(tool_results))
            else:
                # end_turn — combine collected text with final response text.
                parts = collected_text + ([response.text] if response.text else [])
                reply = "\n".join(parts).strip()
                conversation.append({"role": "assistant", "content": reply})
                save_conversation(session_id)
                _get_langfuse().update_current_span(output=reply)
                return reply
    except LLMError as e:
        logger.error("API call failed: %s", e)
        if conversation and conversation[-1].get("role") == "user":
            conversation.pop()
        raise


@_observe(as_type="generation")
def _call_llm(system: str, messages: list, tools: list, model: str):
    """Call LLM via provider — tracked as a generation span in Langfuse."""
    provider = get_provider()
    lf = _get_langfuse()
    lf.update_current_generation(
        model=model,
        input={"system": system, "messages": messages, "tools": tools},
        model_parameters={"max_tokens": 4096},
    )
    response = provider.complete(
        model=model,
        system=system,
        messages=messages,
        tools=tools,
        max_tokens=4096,
    )
    lf.update_current_generation(
        output=response.text,
        usage_details={
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
        },
    )
    return response


@_observe(as_type="tool")
def _execute_tool(name: str, tool_input: dict) -> str:
    """Execute a tool — tracked as a tool span in Langfuse."""
    lf = _get_langfuse()
    lf.update_current_span(input={"tool": name, **tool_input})
    result = registry.call_tool(name, tool_input)
    lf.update_current_span(output=result)
    return result
