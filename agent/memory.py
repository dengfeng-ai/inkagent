"""Markdown-based memory system.

Files:
- SOUL.md              — agent persona (identity, tone, behavior rules)
- USER.md              — user personal info (name, role, preferences)
- MEMORY.md            — long-term memory (facts, preferences, decisions, events)
- daily/YYYY-MM-DD.md  — daily logs (ephemeral, append-only)
"""

import logging
import os
import re
from datetime import date, timedelta

logger = logging.getLogger(__name__)

PROMOTED_MARKER = "<!-- promoted -->"

MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory")
DAILY_DIR = os.path.join(MEMORY_DIR, "daily")
SOUL_PATH = os.path.join(MEMORY_DIR, "SOUL.md")
USER_PATH = os.path.join(MEMORY_DIR, "USER.md")
LONG_TERM_PATH = os.path.join(MEMORY_DIR, "MEMORY.md")


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


def get_soul() -> str:
    """Return the agent persona content for the system prompt instruction area."""
    return _read_file(SOUL_PATH).strip()


def get_user_profile() -> str:
    """Return the user profile content for the system prompt context area."""
    return _read_file(USER_PATH).strip()


def update_soul(content: str) -> str:
    """Overwrite SOUL.md with new persona content."""
    _write_file(SOUL_PATH, content)
    return "Persona updated."


def update_user_profile(content: str) -> str:
    """Overwrite USER.md with new user info."""
    _write_file(USER_PATH, content)
    return "User profile updated."


def get_long_term_memory() -> str:
    """Return full MEMORY.md content for system prompt injection."""
    return _read_file(LONG_TERM_PATH).strip()



def recall_memory(query: str) -> str:
    """Search MEMORY.md and daily logs by keyword. Returns matching entries."""
    results: list[str] = []
    query_lower = query.lower()

    # Search MEMORY.md
    raw = _read_file(LONG_TERM_PATH)
    if raw.strip():
        entries = re.split(r"(?=^## )", raw, flags=re.MULTILINE)
        entries = [e.strip() for e in entries if e.strip()]
        for e in entries:
            if query_lower in e.lower():
                results.append(f"[MEMORY.md] {e}")

    # Search daily logs
    if os.path.isdir(DAILY_DIR):
        for filename in sorted(os.listdir(DAILY_DIR), reverse=True):
            if not filename.endswith(".md"):
                continue
            path = os.path.join(DAILY_DIR, filename)
            content = _read_file(path)
            if query_lower in content.lower():
                results.append(f"[{filename}] {content.strip()}")

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

    timestamp = __import__("datetime").datetime.now().strftime("%H:%M")
    entry = f"- [{timestamp}] {content}\n"

    try:
        with open(path, "a") as f:
            f.write(entry)
    except OSError as e:
        logger.error("Failed to append daily log: %s", e)
        return f"Error writing daily log: {e}"
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
            _ensure_dir()
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
