"""Conversation session management and JSON persistence."""

import contextvars
import json
import threading
from datetime import datetime
from pathlib import Path

from inkagent.config import CONVERSATIONS_DIR as _CONVERSATIONS_DIR_STR

CONVERSATIONS_DIR = Path(_CONVERSATIONS_DIR_STR)

# Per-session conversation history and file paths.
_sessions: dict[str, list[dict]] = {}
_session_files: dict[str, Path] = {}

# Tracks the session_id of the currently running agent turn.
# Uses ContextVar so each thread gets its own value — safe under concurrency.
current_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_session_id", default="cli"
)

# Per-session locks to serialize conversation mutations.
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def get_session_lock(session_id: str) -> threading.Lock:
    """Return (or create) a lock for the given session_id."""
    with _locks_guard:
        if session_id not in _locks:
            _locks[session_id] = threading.Lock()
        return _locks[session_id]


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
    follow-up questions have context.  Acquires the session lock to avoid
    racing with a concurrent agent turn on the same session.
    """
    with get_session_lock(session_id):
        conversation = get_conversation(session_id)
        conversation.append(make_message(role, content))
        save_conversation(session_id)
