"""Tests for the Markdown-based memory system."""

import os
from datetime import date, timedelta
from unittest.mock import patch

import pytest

from inkagent import memory
from inkagent.memory import (
    IDENTITY_TEMPLATE,
    MEMORY_TEMPLATE,
    PROMOTED_MARKER,
    SOUL_TEMPLATE,
    USER_TEMPLATE,
)


# All tests that touch the filesystem need the tmp_memory_dir fixture.
pytestmark = pytest.mark.usefixtures("tmp_memory_dir")


# ---------------------------------------------------------------------------
# Template seeding — get_* creates file from template when missing
# ---------------------------------------------------------------------------

class TestTemplateSeeding:
    def test_get_identity_seeds_template(self):
        result = memory.get_identity()
        assert result == IDENTITY_TEMPLATE.strip()
        # file was created
        assert os.path.exists(memory.IDENTITY_PATH)

    def test_get_soul_seeds_template(self):
        result = memory.get_soul()
        assert result == SOUL_TEMPLATE.strip()

    def test_get_user_profile_seeds_template(self):
        result = memory.get_user_profile()
        assert result == USER_TEMPLATE.strip()

    def test_get_long_term_memory_seeds_template(self):
        result = memory.get_long_term_memory()
        assert result == MEMORY_TEMPLATE.strip()


# ---------------------------------------------------------------------------
# Read existing content
# ---------------------------------------------------------------------------

class TestReadExisting:
    def test_get_identity_returns_existing(self):
        with open(memory.IDENTITY_PATH, "w") as f:
            f.write("custom identity")
        assert memory.get_identity() == "custom identity"

    def test_get_soul_returns_existing(self):
        with open(memory.SOUL_PATH, "w") as f:
            f.write("custom soul")
        assert memory.get_soul() == "custom soul"

    def test_get_user_profile_returns_existing(self):
        with open(memory.USER_PATH, "w") as f:
            f.write("custom user")
        assert memory.get_user_profile() == "custom user"

    def test_get_long_term_memory_returns_existing(self):
        with open(memory.LONG_TERM_PATH, "w") as f:
            f.write("some memories")
        assert memory.get_long_term_memory() == "some memories"


# ---------------------------------------------------------------------------
# Update / write
# ---------------------------------------------------------------------------

class TestUpdate:
    def test_update_identity(self):
        memory.update_identity("new identity")
        with open(memory.IDENTITY_PATH) as f:
            assert f.read() == "new identity"

    def test_update_soul(self):
        memory.update_soul("new soul")
        with open(memory.SOUL_PATH) as f:
            assert f.read() == "new soul"

    def test_update_user_profile(self):
        memory.update_user_profile("new user")
        with open(memory.USER_PATH) as f:
            assert f.read() == "new user"


# ---------------------------------------------------------------------------
# is_first_run
# ---------------------------------------------------------------------------

class TestIsFirstRun:
    def test_true_when_no_files(self):
        assert memory.is_first_run() is True

    def test_true_when_template_only(self):
        memory.get_identity()  # seeds template
        memory.get_soul()
        memory.get_user_profile()
        assert memory.is_first_run() is True

    def test_false_when_identity_customised(self):
        memory.update_identity("I am Ink")
        memory.get_soul()
        memory.get_user_profile()
        assert memory.is_first_run() is False


# ---------------------------------------------------------------------------
# save_memory — append to MEMORY.md
# ---------------------------------------------------------------------------

class TestSaveMemory:
    def test_appends_with_date_header(self):
        memory.save_memory("important fact")
        content = memory.get_long_term_memory()
        today = date.today().isoformat()
        assert f"## {today} | saved" in content
        assert "important fact" in content

    def test_multiple_saves_append(self):
        memory.save_memory("first")
        memory.save_memory("second")
        content = memory.get_long_term_memory()
        assert "first" in content
        assert "second" in content
        # both entries present, second after first
        assert content.index("first") < content.index("second")


# ---------------------------------------------------------------------------
# Daily log
# ---------------------------------------------------------------------------

class TestDailyLog:
    def test_append_creates_file(self):
        result = memory.append_daily_log("test entry")
        assert result == "Daily log updated."
        today = date.today().isoformat()
        path = os.path.join(memory.DAILY_DIR, f"{today}.md")
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "test entry" in content

    def test_append_has_timestamp_prefix(self):
        memory.append_daily_log("timed note")
        today = date.today().isoformat()
        path = os.path.join(memory.DAILY_DIR, f"{today}.md")
        with open(path) as f:
            content = f.read()
        # format: - [HH:MM] note
        assert content.startswith("- [")
        assert "] timed note\n" in content

    def test_multiple_appends(self):
        memory.append_daily_log("entry one")
        memory.append_daily_log("entry two")
        today = date.today().isoformat()
        path = os.path.join(memory.DAILY_DIR, f"{today}.md")
        with open(path) as f:
            content = f.read()
        assert "entry one" in content
        assert "entry two" in content

    def test_get_daily_logs_today(self):
        memory.append_daily_log("today note")
        result = memory.get_daily_logs()
        assert "Today" in result
        assert "today note" in result

    def test_get_daily_logs_yesterday(self):
        yesterday = date.today() - timedelta(days=1)
        path = os.path.join(memory.DAILY_DIR, f"{yesterday.isoformat()}.md")
        with open(path, "w") as f:
            f.write("- [10:00] yesterday note\n")
        result = memory.get_daily_logs()
        assert "Yesterday" in result
        assert "yesterday note" in result

    def test_get_daily_logs_empty(self):
        assert memory.get_daily_logs() == ""


# ---------------------------------------------------------------------------
# Keyword search
# ---------------------------------------------------------------------------

class TestKeywordSearch:
    def _write_daily(self, d: date, content: str) -> None:
        path = os.path.join(memory.DAILY_DIR, f"{d.isoformat()}.md")
        with open(path, "w") as f:
            f.write(content)

    def test_finds_match(self):
        self._write_daily(date(2026, 1, 1), "bought apples today")
        results = memory.keyword_search_daily("apples")
        assert len(results) == 1
        assert "apples" in results[0]

    def test_case_insensitive(self):
        self._write_daily(date(2026, 1, 2), "Bought APPLES today")
        results = memory.keyword_search_daily("apples")
        assert len(results) == 1

    def test_no_match(self):
        self._write_daily(date(2026, 1, 3), "nothing here")
        results = memory.keyword_search_daily("bananas")
        assert results == []

    def test_results_sorted_reverse(self):
        self._write_daily(date(2026, 1, 1), "alpha search term")
        self._write_daily(date(2026, 1, 3), "beta search term")
        self._write_daily(date(2026, 1, 2), "gamma search term")
        results = memory.keyword_search_daily("search term")
        assert len(results) == 3
        # newest first
        assert "2026-01-03" in results[0]
        assert "2026-01-02" in results[1]
        assert "2026-01-01" in results[2]


# ---------------------------------------------------------------------------
# recall_memory — falls back to keyword search without vector store
# ---------------------------------------------------------------------------

class TestRecallMemory:
    def test_no_results(self):
        result = memory.recall_memory("nonexistent query xyz")
        assert "No memories found" in result

    def test_keyword_fallback(self):
        d = date(2026, 2, 1)
        path = os.path.join(memory.DAILY_DIR, f"{d.isoformat()}.md")
        with open(path, "w") as f:
            f.write("meeting with Alice about project X")
        result = memory.recall_memory("Alice")
        assert "Alice" in result


# ---------------------------------------------------------------------------
# Memory promotion
# ---------------------------------------------------------------------------

class TestPromotion:
    def _write_yesterday_log(self, content: str) -> str:
        yesterday = date.today() - timedelta(days=1)
        path = os.path.join(memory.DAILY_DIR, f"{yesterday.isoformat()}.md")
        with open(path, "w") as f:
            f.write(content)
        return path

    def test_needs_promotion_true(self):
        self._write_yesterday_log("some log content")
        assert memory.needs_promotion() is True

    def test_needs_promotion_false_no_file(self):
        assert memory.needs_promotion() is False

    def test_needs_promotion_false_already_promoted(self):
        self._write_yesterday_log(f"some log content\n{PROMOTED_MARKER}\n")
        assert memory.needs_promotion() is False

    def test_get_promotion_context(self):
        self._write_yesterday_log("yesterday stuff")
        ctx = memory.get_promotion_context()
        yesterday = date.today() - timedelta(days=1)
        assert ctx["date"] == yesterday.isoformat()
        assert "yesterday stuff" in ctx["daily_log"]
        assert "long_term_memory" in ctx

    def test_apply_promotion_appends_to_memory(self):
        path = self._write_yesterday_log("log content")
        result = memory.apply_promotion("## Promoted entry\nkey fact")
        assert result == "promoted"
        # MEMORY.md has the promoted entry
        ltm = memory.get_long_term_memory()
        assert "key fact" in ltm
        # daily log is marked promoted
        with open(path) as f:
            assert PROMOTED_MARKER in f.read()

    def test_apply_promotion_empty_entries(self):
        path = self._write_yesterday_log("log content")
        result = memory.apply_promotion("  ")
        assert result == "nothing_to_promote"
        # MEMORY.md not modified with empty content
        ltm = memory.get_long_term_memory()
        assert ltm.strip() == MEMORY_TEMPLATE.strip()
        # daily log still marked promoted
        with open(path) as f:
            assert PROMOTED_MARKER in f.read()
