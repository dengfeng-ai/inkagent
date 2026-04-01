"""Daily log → MEMORY.md promotion via LLM curation."""

import logging

from inkagent import memory
from inkagent.prompts import PROMOTION_PROMPT
from inkagent.providers import get_provider, get_small_model, LLMError
from inkagent.tracing import observe, get_langfuse

logger = logging.getLogger(__name__)


@observe(as_type="generation")
def _promote_llm(prompt: str, model: str) -> str:
    """Call LLM for promotion — tracked as a generation span."""
    lf = get_langfuse()
    lf.update_current_generation(
        name="promotion-llm",
        model=model,
        input=prompt,
        model_parameters={"max_tokens": 1024},
    )
    result = get_provider().simple_complete(
        model=model,
        prompt=prompt,
        max_tokens=1024,
    )
    lf.update_current_generation(output=result)
    return result


@observe()
def maybe_promote() -> None:
    """Check if yesterday's daily log needs promotion; if so, ask LLM to curate."""
    if not memory.needs_promotion():
        return

    ctx = memory.get_promotion_context()
    prompt = PROMOTION_PROMPT.format(**ctx)
    model = get_small_model()

    logger.info("Running memory promotion for %s", ctx["date"])
    lf = get_langfuse()
    lf.update_current_span(name="promotion", input={"date": ctx["date"]})
    try:
        text = _promote_llm(prompt, model)
    except LLMError as e:
        logger.error("Memory promotion API call failed: %s", e)
        return

    lf.update_current_span(output=text)

    if text == "NOTHING":
        result = memory.apply_promotion("")
    else:
        result = memory.apply_promotion(text)
    logger.info("Promotion result: %s", result)
