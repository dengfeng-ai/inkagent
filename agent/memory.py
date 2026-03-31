"""Markdown-based memory system.

Files:
- IDENTITY.md          — agent identity metadata (name, creature, vibe, emoji, avatar)
- SOUL.md              — agent behavioral rules (core truths, boundaries, tone, continuity)
- USER.md              — user personal info (name, role, preferences)
- MEMORY.md            — long-term memory (facts, preferences, decisions, events)
- daily/YYYY-MM-DD.md  — daily logs (ephemeral, append-only)
"""

import logging
import os
import re
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

PROMOTED_MARKER = "<!-- promoted -->"

MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory")
DAILY_DIR = os.path.join(MEMORY_DIR, "daily")
IDENTITY_PATH = os.path.join(MEMORY_DIR, "IDENTITY.md")
SOUL_PATH = os.path.join(MEMORY_DIR, "SOUL.md")
USER_PATH = os.path.join(MEMORY_DIR, "USER.md")
LONG_TERM_PATH = os.path.join(MEMORY_DIR, "MEMORY.md")

IDENTITY_TEMPLATE = """\
# IDENTITY.md

_Update these fields when the user sets your name, persona, or appearance._

- **Name:**
- **Creature:** (AI, robot, familiar, spirit, etc.)
- **Vibe:** (sharp, warm, chaotic, calm, playful, etc.)
- **Emoji:**
- **Avatar:** (file path, URL, or data URI)
"""

SOUL_TEMPLATE = """\
# SOUL.md

_Update these sections when the user sets behavior rules, tone, or boundaries._

## Core truths

## Boundaries

## Tone

## Continuity
"""

USER_TEMPLATE = """\
# USER.md

_Update these fields as you learn about the user. Only record durable info, not session context._

## Basics
- **Name:**
- **What to call them:**
- **Timezone:**
- **Role / occupation:**

## Interests & preferences

## Notes
"""

MEMORY_TEMPLATE = """\
# MEMORY.md

_Long-term memory. Important facts, preferences, and decisions are saved here — either explicitly via save_memory or automatically promoted from daily logs._
"""


def _ensure_dir() -> None:
    os.makedirs(MEMORY_DIR, exist_ok=True)


def _read_file(path: str) -> str:
    try:
        if os.path.exists(path):
            with open(path, "r") as f:
                return f.read()
    except OSError as e:
        logger.error("Failed to read %s: %s", path, e)
    return ""


def _write_file(path: str, content: str) -> None:
    try:
        _ensure_dir()
        with open(path, "w") as f:
            f.write(content)
    except OSError as e:
        logger.error("Failed to write %s: %s", path, e)
        raise


def _is_template(path: str, template: str) -> bool:
    """Check if a memory file is still the default template (or missing)."""
    content = _read_file(path).strip()
    return not content or content == template.strip()


def is_first_run() -> bool:
    """Check if all three profile files are still untouched default templates."""
    return (
        _is_template(IDENTITY_PATH, IDENTITY_TEMPLATE)
        and _is_template(SOUL_PATH, SOUL_TEMPLATE)
        and _is_template(USER_PATH, USER_TEMPLATE)
    )


def get_identity() -> str:
    """Return the agent identity metadata for the system prompt.

    Seeds IDENTITY.md with a default template on first access so the LLM
    sees the expected structure and preserves it on updates.
    """
    content = _read_file(IDENTITY_PATH).strip()
    if not content:
        _write_file(IDENTITY_PATH, IDENTITY_TEMPLATE)
        return IDENTITY_TEMPLATE.strip()
    return content


def get_soul() -> str:
    """Return the agent behavioral rules for the system prompt.

    Seeds SOUL.md with a default template on first access so the LLM
    sees the expected structure and preserves it on updates.
    """
    content = _read_file(SOUL_PATH).strip()
    if not content:
        _write_file(SOUL_PATH, SOUL_TEMPLATE)
        return SOUL_TEMPLATE.strip()
    return content


def get_user_profile() -> str:
    """Return the user profile content for the system prompt context area.

    Seeds USER.md with a default template on first access so the LLM
    sees the expected structure and preserves it on updates.
    """
    content = _read_file(USER_PATH).strip()
    if not content:
        _write_file(USER_PATH, USER_TEMPLATE)
        return USER_TEMPLATE.strip()
    return content


def update_identity(content: str) -> str:
    """Overwrite IDENTITY.md with new identity metadata."""
    _write_file(IDENTITY_PATH, content)
    return "Identity updated."


def update_soul(content: str) -> str:
    """Overwrite SOUL.md with new behavioral rules."""
    _write_file(SOUL_PATH, content)
    return "Soul updated."


def update_user_profile(content: str) -> str:
    """Overwrite USER.md with new user info."""
    _write_file(USER_PATH, content)
    return "User profile updated."


def _ensure_memory_file() -> None:
    """Seed MEMORY.md with the default template if it doesn't exist or is empty."""
    content = _read_file(LONG_TERM_PATH).strip()
    if not content:
        _write_file(LONG_TERM_PATH, MEMORY_TEMPLATE)


def get_long_term_memory() -> str:
    """Return full MEMORY.md content for system prompt injection.

    Seeds MEMORY.md with a default template on first access so the file
    starts with a consistent header.
    """
    _ensure_memory_file()
    return _read_file(LONG_TERM_PATH).strip()


def save_memory(content: str) -> str:
    """Append an entry directly to MEMORY.md. Used for explicit 'remember this' requests."""
    _ensure_memory_file()
    today = date.today().isoformat()
    entry = f"\n## {today} | saved\n{content.strip()}\n"
    try:
        with open(LONG_TERM_PATH, "a") as f:
            f.write(entry)
    except OSError as e:
        logger.error("Failed to save memory: %s", e)
        return f"Error saving memory: {e}"
    return "Saved to long-term memory."


def keyword_search_daily(query: str) -> list[str]:
    """Keyword search across daily log files. Returns list of formatted matches."""
    results: list[str] = []
    query_lower = query.lower()
    if os.path.isdir(DAILY_DIR):
        for filename in sorted(os.listdir(DAILY_DIR), reverse=True):
            if not filename.endswith(".md"):
                continue
            path = os.path.join(DAILY_DIR, filename)
            content = _read_file(path)
            if query_lower in content.lower():
                results.append(f"[{filename}] {content.strip()}")
    return results


def recall_memory(query: str) -> str:
    """Search daily logs: vector search if available, keyword fallback otherwise."""
    results: list[str] = []

    # Try vector search for daily logs.
    vector_results: list[dict] = []
    try:
        from agent.vector_store import get_vector_store

        vs = get_vector_store()
        if vs.is_available():
            vector_results = vs.search(query)
    except Exception as e:
        logger.debug("Vector search failed, falling back to keyword: %s", e)

    if vector_results:
        for r in vector_results:
            results.append(f"[{r['source']}] {r['content']}")
    else:
        # Fallback: keyword search daily logs.
        results.extend(keyword_search_daily(query))

    if not results:
        return f"No memories found matching '{query}'."
    return "\n\n---\n\n".join(results)


# --- Daily log functions ---


def _daily_log_path(d: date) -> str:
    """Return the file path for a given date's daily log."""
    return os.path.join(DAILY_DIR, f"{d.isoformat()}.md")


def get_daily_logs() -> str:
    """Return today's and yesterday's daily logs for system prompt injection."""
    today = date.today()
    yesterday = today - timedelta(days=1)
    parts: list[str] = []

    for d, label in [(yesterday, "Yesterday"), (today, "Today")]:
        content = _read_file(_daily_log_path(d)).strip()
        if content:
            parts.append(f"### {label} ({d.isoformat()})\n{content}")

    return "\n\n".join(parts) if parts else ""


def append_daily_log(content: str) -> str:
    """Append an entry to today's daily log."""
    os.makedirs(DAILY_DIR, exist_ok=True)
    today = date.today()
    path = _daily_log_path(today)

    timestamp = datetime.now().strftime("%H:%M")
    entry = f"- [{timestamp}] {content}\n"

    try:
        with open(path, "a") as f:
            f.write(entry)
    except OSError as e:
        logger.error("Failed to append daily log: %s", e)
        return f"Error writing daily log: {e}"

    # Index into vector store (silent failure).
    try:
        from agent.vector_store import get_vector_store

        vs = get_vector_store()
        if vs.is_available():
            vs.index_daily_entry(today.isoformat(), entry.strip())
    except Exception as e:
        logger.debug("Vector indexing skipped: %s", e)

    return "Daily log updated."


# --- Memory promotion ---


def needs_promotion() -> bool:
    """Check if yesterday's daily log exists and hasn't been promoted yet."""
    yesterday = date.today() - timedelta(days=1)
    path = _daily_log_path(yesterday)
    content = _read_file(path)
    return bool(content.strip()) and PROMOTED_MARKER not in content


def get_promotion_context() -> dict[str, str]:
    """Return yesterday's daily log and current MEMORY.md for the promotion prompt."""
    yesterday = date.today() - timedelta(days=1)
    return {
        "daily_log": _read_file(_daily_log_path(yesterday)).strip(),
        "date": yesterday.isoformat(),
        "long_term_memory": get_long_term_memory(),
    }


def apply_promotion(entries: str) -> str:
    """Append promoted entries to MEMORY.md and mark the daily log as processed."""
    yesterday = date.today() - timedelta(days=1)
    path = _daily_log_path(yesterday)

    try:
        # Append to MEMORY.md if there's anything to promote
        if entries.strip():
            _ensure_memory_file()
            with open(LONG_TERM_PATH, "a") as f:
                f.write(f"\n{entries.strip()}\n")
            logger.info("Promoted entries from %s to MEMORY.md", yesterday.isoformat())

        # Mark daily log as promoted
        with open(path, "a") as f:
            f.write(f"\n{PROMOTED_MARKER}\n")
    except OSError as e:
        logger.error("Failed during memory promotion: %s", e)
        return f"promotion_error: {e}"

    return "promoted" if entries.strip() else "nothing_to_promote"
