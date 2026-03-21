"""Markdown-based memory system.

Two files:
- SOUL.md  — agent persona (identity, tone, behavior rules)
- USER.md  — user personal info (name, role, preferences)
"""

import os

MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory")
SOUL_PATH = os.path.join(MEMORY_DIR, "SOUL.md")
USER_PATH = os.path.join(MEMORY_DIR, "USER.md")


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
