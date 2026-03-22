"""Conversation session management and JSON persistence."""

import json
from datetime import datetime
from pathlib import Path

CONVERSATIONS_DIR = Path(__file__).resolve().parent.parent / "conversations"

# Per-session conversation history and file paths.
_sessions: dict[str, list[dict]] = {}
_session_files: dict[str, Path] = {}

# Tracks the session_id of the currently running agent turn.
# Skills can read this to bind actions to the active session.
current_session_id: str = "cli"


def get_conversation(session_id: str) -> list[dict]:
    """Get or create conversation history for a session."""
    if session_id not in _sessions:
        _sessions[session_id] = []
    return _sessions[session_id]


def make_message(role: str, content: str) -> dict:
    """Create a conversation message dict with a timestamp."""
    return {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }


def save_conversation(session_id: str) -> None:
    """Save conversation to the session JSON file."""
    if session_id not in _session_files:
        CONVERSATIONS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        _session_files[session_id] = CONVERSATIONS_DIR / f"{timestamp}_{session_id}.json"
    conversation = _sessions.get(session_id, [])
    _session_files[session_id].write_text(
        json.dumps(conversation, ensure_ascii=False, indent=2)
    )


def reset_conversation(session_id: str) -> int:
    """Save current conversation, clear it, and start fresh.

    Returns the number of messages that were archived.
    """
    count = len(_sessions.get(session_id, []))
    if count:
        save_conversation(session_id)
        _session_files.pop(session_id, None)
    _sessions[session_id] = []
    return count


def inject_message(session_id: str, role: str, content: str) -> None:
    """Inject a message into a session's conversation history and persist it.

    Used to bridge scheduled task replies into the user's main session so
    follow-up questions have context.
    """
    conversation = get_conversation(session_id)
    conversation.append(make_message(role, content))
    save_conversation(session_id)
