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
