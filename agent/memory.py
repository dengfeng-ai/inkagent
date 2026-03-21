"""Markdown-based memory system.

Three files:
- SOUL.md    — agent persona (identity, tone, behavior rules)
- USER.md    — user personal info (name, role, preferences)
- MEMORY.md  — long-term memory (facts, preferences, decisions, events)
"""

import os
import re
from datetime import date

MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory")
SOUL_PATH = os.path.join(MEMORY_DIR, "SOUL.md")
USER_PATH = os.path.join(MEMORY_DIR, "USER.md")
LONG_TERM_PATH = os.path.join(MEMORY_DIR, "MEMORY.md")


def _ensure_dir() -> None:
    os.makedirs(MEMORY_DIR, exist_ok=True)


def _read_file(path: str) -> str:
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read()
    return ""


def _write_file(path: str, content: str) -> None:
    _ensure_dir()
    with open(path, "w") as f:
        f.write(content)


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


def save_memory(content: str, category: str) -> str:
    """Append a memory entry to MEMORY.md."""
    _ensure_dir()
    today = date.today().isoformat()
    entry = f"\n## {today} | {category}\n{content}\n"
    with open(LONG_TERM_PATH, "a") as f:
        f.write(entry)
    return "Memory saved."


def recall_memory(query: str) -> str:
    """Search MEMORY.md entries by keyword. Returns matching entries."""
    raw = _read_file(LONG_TERM_PATH)
    if not raw.strip():
        return "No memories stored yet."

    # Split into entries by ## headings
    entries = re.split(r"(?=^## )", raw, flags=re.MULTILINE)
    entries = [e.strip() for e in entries if e.strip()]

    query_lower = query.lower()
    matches = [e for e in entries if query_lower in e.lower()]

    if not matches:
        return f"No memories found matching '{query}'."
    return "\n\n".join(matches)
