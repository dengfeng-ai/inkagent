"""Markdown-based memory system.

Single file:
- profile.md  — persistent user profile, updated by LLM
"""

import os

MEMORY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "memory")
PROFILE_PATH = os.path.join(MEMORY_DIR, "profile.md")


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

    if profile.strip():
        return f"## User Profile\n{profile.strip()}"

    return "(no memory yet)"


def update_profile(content: str) -> str:
    """Overwrite profile.md with new content. Called by the update_profile skill."""
    _write_file(PROFILE_PATH, content)
    return "Profile updated."
