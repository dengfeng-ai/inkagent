"""Daily log → MEMORY.md promotion via LLM curation."""

import logging

from inkagent import memory
from inkagent.prompts import PROMOTION_PROMPT
from inkagent.providers import get_provider, get_small_model, LLMError
from inkagent.tracing import track, update_current_span, update_current_generation

logger = logging.getLogger(__name__)


@track(as_type="generation")
def _promote_llm(prompt: str, model: str) -> str:
    """Call LLM for promotion — tracked as a generation span."""
    update_current_generation(
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
    update_current_generation(output=result)
    return result


def maybe_promote() -> None:
    """Gate: only enter the traced promotion routine when work is needed."""
    if not memory.needs_promotion():
        return
    _run_promotion()


@track(name="promotion")
def _run_promotion() -> None:
    ctx = memory.get_promotion_context()
    prompt = PROMOTION_PROMPT.format(**ctx)
    model = get_small_model()

    logger.info("Running memory promotion for %s", ctx["date"])
    update_current_span(input={"date": ctx["date"]})
    try:
        text = _promote_llm(prompt, model)
    except LLMError as e:
        logger.error("Memory promotion API call failed: %s", e)
        return

    update_current_span(output=text)

    if text == "NOTHING":
        result = memory.apply_promotion("")
    else:
        result = memory.apply_promotion(text)
    logger.info("Promotion result: %s", result)
