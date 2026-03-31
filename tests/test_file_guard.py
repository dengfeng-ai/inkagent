"""Tests for file write path restrictions in tools/files.py."""

import pytest

from tools.files import _check_writable


class TestCheckWritable:
    """Within project: only memory/, conversations/, user_skills/ are writable.
    Outside project: no restrictions.
    """

    # --- allowed: writable project dirs ---

    @pytest.mark.parametrize("path", [
        "memory/MEMORY.md",
        "memory/daily/2026-03-31.md",
        "conversations/session_123.json",
        "user_skills/heartbeat/SKILL.md",
    ])
    def test_allowed_project_paths(self, path):
        assert _check_writable(path) is None

    # --- allowed: outside project ---

    @pytest.mark.parametrize("path", [
        "/tmp/some_file.txt",
        "/Users/derek/Documents/notes.md",
    ])
    def test_allowed_outside_project(self, path):
        assert _check_writable(path) is None

    # --- blocked: other project dirs ---

    @pytest.mark.parametrize("path", [
        "agent/brain.py",
        "tools/files.py",
        "skills/heartbeat/SKILL.md",
        "main.py",
        "bot.py",
        "requirements.txt",
        ".env",
    ])
    def test_blocked_project_paths(self, path):
        err = _check_writable(path)
        assert err is not None
        assert "restricted" in err

    # --- blocked: .db files even in allowed dirs ---

    def test_blocked_db_in_memory(self):
        err = _check_writable("memory/memory.db")
        assert err is not None
        assert "database" in err

    # --- blocked: traversal back into project root ---

    def test_blocked_traversal_to_project_root(self):
        # memory/../main.py resolves to <project>/main.py — should be blocked
        err = _check_writable("memory/../main.py")
        assert err is not None
        assert "restricted" in err

    def test_traversal_outside_project_allowed(self):
        # memory/../../ goes above the project — outside project, so allowed
        assert _check_writable("memory/../../anything.txt") is None
