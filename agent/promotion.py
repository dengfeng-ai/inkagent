"""Daily log → MEMORY.md promotion via LLM curation."""

import logging

from agent import memory
from agent.prompts import PROMOTION_PROMPT
from agent.providers import get_provider, get_small_model, LLMError

logger = logging.getLogger(__name__)


def maybe_promote() -> None:
    """Check if yesterday's daily log needs promotion; if so, ask LLM to curate."""
    if not memory.needs_promotion():
        return

    ctx = memory.get_promotion_context()
    prompt = PROMOTION_PROMPT.format(**ctx)

    logger.info("Running memory promotion for %s", ctx["date"])
    try:
        text = get_provider().simple_complete(
            model=get_small_model(),
            prompt=prompt,
            max_tokens=1024,
        )
    except LLMError as e:
        logger.error("Memory promotion API call failed: %s", e)
        return

    if text == "NOTHING":
        result = memory.apply_promotion("")
    else:
        result = memory.apply_promotion(text)
    logger.info("Promotion result: %s", result)
