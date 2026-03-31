"""LLM agentic loop using pluggable provider."""

import logging
import time

from datetime import date

from agent import registry, memory
from agent.config import MAX_REPLY_TOKENS, MAX_TOOL_ROUNDS
from agent.prompts import SYSTEM_PROMPT, ONBOARDING_HINT
from agent.skill_loader import load_skills, build_skill_prompt
import agent.session as _session
from agent.session import get_conversation, save_conversation, make_message
from agent.compression import maybe_compress
from agent.promotion import maybe_promote
from agent.providers import get_provider, get_model, LLMError

logger = logging.getLogger(__name__)

from agent.tracing import observe as _observe, get_langfuse as _get_langfuse

# Import the tools package to trigger tool auto-registration via @register decorators.
import tools  # noqa: F401


@_observe()
def run_agent(user_input: str, session_id: str = "cli") -> str:
    """Run one full agentic turn: send message, loop on tool calls, return final text."""
    _get_langfuse().update_current_span(input=user_input)

    t_start = time.time()
    _session.current_session_id = session_id
    maybe_promote()

    conversation = get_conversation(session_id)
    conversation.append(make_message("user", user_input))

    identity = memory.get_identity()
    soul = memory.get_soul()
    user_profile = memory.get_user_profile()
    long_term_memory = memory.get_long_term_memory()
    daily_logs = memory.get_daily_logs()
    instruction_skills = load_skills()
    skill_prompt = build_skill_prompt(instruction_skills)

    system = SYSTEM_PROMPT.format(
        current_date=date.today().isoformat(),
        identity=identity,
        soul=soul,
        user_profile=user_profile,
        long_term_memory=long_term_memory if long_term_memory else "(no memories yet)",
        daily_logs=daily_logs if daily_logs else "(no daily logs yet)",
        skills=skill_prompt,
    )

    if memory.is_first_run():
        system += ONBOARDING_HINT

    provider = get_provider()
    model = get_model()
    raw_tools = registry.get_tools()
    tools = provider.format_tools(raw_tools)

    # Compress conversation if approaching context window limit.
    maybe_compress(conversation, system, tools)

    # Strip extra fields (e.g. timestamp) before sending to the LLM.
    messages = [{"role": m["role"], "content": m["content"]} for m in conversation]

    collected_text: list[str] = []
    loop_count = 0

    try:
        while True:
            loop_count += 1

            # On the last allowed round, drop tools to force a text reply.
            current_tools = tools if loop_count <= MAX_TOOL_ROUNDS else []

            t_llm = time.time()
            response = _call_llm(system, messages, current_tools, model)
            logger.info("LLM call #%d took %.1fs", loop_count, time.time() - t_llm)

            if response.stop_reason == "tool_use":
                if response.text:
                    collected_text.append(response.text)

                messages.append(provider.assistant_message(response))

                tool_results = []
                for tc in response.tool_calls:
                    t_tool = time.time()
                    result = _execute_tool(tc.name, tc.input)
                    logger.info("Tool %s took %.1fs", tc.name, time.time() - t_tool)
                    tool_results.append({
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                messages.extend(provider.tool_results_messages(tool_results))
            else:
                # end_turn — combine collected text with final response text.
                parts = collected_text + ([response.text] if response.text else [])
                reply = "\n".join(parts).strip()
                conversation.append(make_message("assistant", reply))
                save_conversation(session_id)
                _get_langfuse().update_current_span(output=reply)
                logger.info("Total agent turn took %.1fs (%d LLM calls)", time.time() - t_start, loop_count)
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
        model_parameters={"max_tokens": MAX_REPLY_TOKENS},
    )
    response = provider.complete(
        model=model,
        system=system,
        messages=messages,
        tools=tools,
        max_tokens=MAX_REPLY_TOKENS,
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
