"""Daily log → MEMORY.md promotion via LLM curation."""

import logging

import anthropic

from agent import memory
from agent.prompts import PROMOTION_PROMPT

logger = logging.getLogger(__name__)

PROMOTION_MODEL = "claude-haiku-4-5-20251001"

_client = anthropic.Anthropic()


def maybe_promote() -> None:
    """Check if yesterday's daily log needs promotion; if so, ask LLM to curate."""
    if not memory.needs_promotion():
        return

    ctx = memory.get_promotion_context()
    prompt = PROMOTION_PROMPT.format(**ctx)

    logger.info("Running memory promotion for %s", ctx["date"])
    try:
        response = _client.messages.create(
            model=PROMOTION_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as e:
        logger.error("Memory promotion API call failed: %s", e)
        return

    text = response.content[0].text.strip()
    if text == "NOTHING":
        result = memory.apply_promotion("")
    else:
        result = memory.apply_promotion(text)
    logger.info("Promotion result: %s", result)
