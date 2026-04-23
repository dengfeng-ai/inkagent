"""Shared test fixtures."""

import os

import pytest

from inkagent import registry
from inkagent import session


# ---------------------------------------------------------------------------
# tmp_memory_dir — redirect all filesystem paths to a temp directory
# ---------------------------------------------------------------------------

# Modules that copy config path constants at import time.
# Each entry: (module_path, attribute_name)
_PATH_ATTRS = [
    # inkagent.config (canonical source)
    ("inkagent.config", "DATA_DIR"),
    ("inkagent.config", "MEMORY_DIR"),
    ("inkagent.config", "DAILY_DIR"),
    ("inkagent.config", "CONVERSATIONS_DIR"),
    ("inkagent.config", "CRONS_PATH"),
    ("inkagent.config", "IDENTITY_PATH"),
    ("inkagent.config", "SOUL_PATH"),
    ("inkagent.config", "USER_PATH"),
    ("inkagent.config", "LONG_TERM_PATH"),
    ("inkagent.config", "HEARTBEAT_PATH"),
    ("inkagent.config", "TASKS_PATH"),
    ("inkagent.config", "TASKS_ARCHIVE_DIR"),
    ("inkagent.config", "DB_PATH"),
    ("inkagent.config", "SKILLS_DIR"),
    # inkagent.memory (imports from config at module level)
    ("inkagent.memory", "MEMORY_DIR"),
    ("inkagent.memory", "DAILY_DIR"),
    ("inkagent.memory", "IDENTITY_PATH"),
    ("inkagent.memory", "SOUL_PATH"),
    ("inkagent.memory", "USER_PATH"),
    ("inkagent.memory", "LONG_TERM_PATH"),
    ("inkagent.memory", "TASKS_PATH"),
    # inkagent.scheduler
    ("inkagent.scheduler", "CRONS_PATH"),
    # inkagent.tools.tasks
    ("inkagent.tools.tasks", "TASKS_ARCHIVE_DIR"),
]


@pytest.fixture()
def tmp_memory_dir(tmp_path, monkeypatch):
    """Create a temporary directory tree mirroring the real layout and
    monkeypatch every path constant so all modules write there."""
    mem = tmp_path / "memory"
    mem.mkdir()
    (mem / "daily").mkdir()
    (tmp_path / "conversations").mkdir()
    (tmp_path / "skills").mkdir()

    path_map = {
        "DATA_DIR": str(tmp_path),
        "MEMORY_DIR": str(mem),
        "DAILY_DIR": str(mem / "daily"),
        "CONVERSATIONS_DIR": str(tmp_path / "conversations"),
        "CRONS_PATH": str(mem / "crons.json"),
        "IDENTITY_PATH": str(mem / "IDENTITY.md"),
        "SOUL_PATH": str(mem / "SOUL.md"),
        "USER_PATH": str(mem / "USER.md"),
        "LONG_TERM_PATH": str(mem / "MEMORY.md"),
        "HEARTBEAT_PATH": str(mem / "HEARTBEAT.md"),
        "TASKS_PATH": str(mem / "TASKS.md"),
        "TASKS_ARCHIVE_DIR": str(mem / "tasks_archive"),
        "DB_PATH": str(mem / "memory.db"),
        "SKILLS_DIR": str(tmp_path / "skills"),
    }

    for module, attr in _PATH_ATTRS:
        if attr in path_map:
            monkeypatch.setattr(f"{module}.{attr}", path_map[attr])

    # session.py stores CONVERSATIONS_DIR as a Path object
    from pathlib import Path
    monkeypatch.setattr(
        "inkagent.session.CONVERSATIONS_DIR",
        Path(path_map["CONVERSATIONS_DIR"]),
    )

    # skill_loader.py stores dir as a Path object
    monkeypatch.setattr(
        "inkagent.skill_loader.SKILLS_DIR",
        Path(path_map["SKILLS_DIR"]),
    )

    return tmp_path


# ---------------------------------------------------------------------------
# clean_registry — isolate registry state between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_registry():
    """Save and restore the tool registry around each test."""
    saved = dict(registry._skills)
    yield
    registry._skills.clear()
    registry._skills.update(saved)


# ---------------------------------------------------------------------------
# clean_session — isolate session state between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_session():
    """Clear session global state after each test."""
    yield
    session._sessions.clear()
    session._session_files.clear()
    session._locks.clear()
    session.current_session_id.set("cli")
