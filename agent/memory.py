"""Markdown-based memory system.

Two files:
- profile.md  — persistent user profile, updated by LLM
- history.md  — rolling conversation history, trimmed to HISTORY_LIMIT turns
"""

import os
import re

MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory")
PROFILE_PATH = os.path.join(MEMORY_DIR, "profile.md")
HISTORY_PATH = os.path.join(MEMORY_DIR, "history.md")
HISTORY_LIMIT = 20


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


def build_context() -> str:
    """Build the memory context string injected into the system prompt."""
    profile = _read_file(PROFILE_PATH)
    history = _read_file(HISTORY_PATH)

    parts: list[str] = []
    if profile.strip():
        parts.append(f"## User Profile\n{profile.strip()}")
    if history.strip():
        parts.append(f"## Conversation History\n{history.strip()}")

    return "\n\n".join(parts) if parts else "(no memory yet)"


def save_turn(role: str, content: str) -> None:
    """Append a single turn to history.md, then trim to HISTORY_LIMIT."""
    _ensure_dir()
    entry = f"### {role}\n{content}\n\n"
    with open(HISTORY_PATH, "a") as f:
        f.write(entry)
    _trim_history()


def _trim_history() -> None:
    """Keep only the last HISTORY_LIMIT turns in history.md."""
    raw = _read_file(HISTORY_PATH)
    if not raw.strip():
        return
    turns = re.split(r"(?=^### )", raw, flags=re.MULTILINE)
    turns = [t for t in turns if t.strip()]
    if len(turns) > HISTORY_LIMIT:
        turns = turns[-HISTORY_LIMIT:]
        _write_file(HISTORY_PATH, "".join(turns))


def update_profile(content: str) -> str:
    """Overwrite profile.md with new content. Called by the update_profile skill."""
    _write_file(PROFILE_PATH, content)
    return "Profile updated."
