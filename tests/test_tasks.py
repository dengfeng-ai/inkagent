"""Tests for task management tools — add, list, update, archive."""

import os
from datetime import date, timedelta

import pytest

from inkagent import memory
from inkagent.tools.tasks import (
    _ARCHIVE_AFTER_DAYS,
    _archive_completed_tasks,
    add_task,
    list_tasks,
    update_task,
)
import inkagent.tools.tasks as tasks_mod


pytestmark = pytest.mark.usefixtures("tmp_memory_dir")


# ---------------------------------------------------------------------------
# add_task
# ---------------------------------------------------------------------------

class TestAddTask:
    def test_adds_pending_task(self):
        result = add_task(description="write tests", priority="high")
        assert "write tests" in result
        content = memory.read_tasks()
        assert "- [ ] write tests (priority: high)" in content

    def test_includes_created_date(self):
        add_task(description="dated task")
        content = memory.read_tasks()
        assert f"created: {date.today().isoformat()}" in content

    def test_includes_repo(self):
        add_task(description="repo task", repo="owner/repo")
        content = memory.read_tasks()
        assert "repo: owner/repo" in content

    def test_includes_context(self):
        add_task(description="ctx task", context="extra info")
        content = memory.read_tasks()
        assert "context: extra info" in content

    def test_default_priority_medium(self):
        add_task(description="default prio")
        content = memory.read_tasks()
        assert "priority: medium" in content

    def test_multiple_tasks(self):
        add_task(description="task one")
        add_task(description="task two")
        content = memory.read_tasks()
        assert "task one" in content
        assert "task two" in content


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------

class TestListTasks:
    def test_empty_queue(self):
        result = list_tasks()
        assert "No tasks" in result

    def test_list_all(self):
        add_task(description="alpha")
        add_task(description="beta")
        result = list_tasks(status="all")
        assert "alpha" in result
        assert "beta" in result

    def test_filter_pending(self):
        add_task(description="pending one")
        add_task(description="pending two")
        result = list_tasks(status="pending")
        assert "pending one" in result

    def test_filter_no_match(self):
        add_task(description="only pending")
        result = list_tasks(status="completed")
        assert "No completed tasks" in result


# ---------------------------------------------------------------------------
# update_task
# ---------------------------------------------------------------------------

class TestUpdateTask:
    def test_mark_in_progress(self):
        add_task(description="wip task")
        result = update_task(task="wip task", status="in_progress")
        assert "in_progress" in result
        content = memory.read_tasks()
        assert "- [~] wip task" in content
        assert f"updated: {date.today().isoformat()}" in content

    def test_mark_completed(self):
        add_task(description="done task")
        result = update_task(task="done task", status="completed")
        assert "completed" in result
        content = memory.read_tasks()
        assert "- [x] done task" in content
        assert f"completed: {date.today().isoformat()}" in content

    def test_mark_blocked(self):
        add_task(description="stuck task")
        update_task(task="stuck task", status="blocked", note="waiting on API")
        content = memory.read_tasks()
        assert "- [!] stuck task" in content
        assert "blocker: waiting on API" in content

    def test_add_note(self):
        add_task(description="noted task")
        update_task(task="noted task", status="in_progress", note="halfway done")
        content = memory.read_tasks()
        assert "progress: halfway done" in content

    def test_no_match(self):
        add_task(description="existing")
        result = update_task(task="nonexistent xyz", status="completed")
        assert "Error" in result

    def test_case_insensitive_match(self):
        add_task(description="Case Sensitive Task")
        result = update_task(task="case sensitive task", status="completed")
        assert "completed" in result

    def test_invalid_status(self):
        add_task(description="bad status")
        result = update_task(task="bad status", status="invalid_xyz")
        assert "Error" in result


# ---------------------------------------------------------------------------
# _archive_completed_tasks
# ---------------------------------------------------------------------------

class TestArchive:
    def _write_tasks_with_old_completed(self) -> None:
        """Seed TASKS.md with a completed task older than the archive cutoff."""
        old_date = (date.today() - timedelta(days=_ARCHIVE_AFTER_DAYS + 1)).isoformat()
        content = (
            "# TASKS.md\n\n## Tasks\n\n"
            f"- [x] old done task (priority: low)\n"
            f"  - created: 2026-01-01\n"
            f"  - completed: {old_date}\n"
            "- [ ] still pending (priority: medium)\n"
            "  - created: 2026-03-01\n"
        )
        memory.write_tasks(content)

    def test_archives_old_completed(self):
        self._write_tasks_with_old_completed()
        _archive_completed_tasks()
        # Archived task removed from TASKS.md
        content = memory.read_tasks()
        assert "old done task" not in content
        assert "still pending" in content
        # Archive file created
        archive_files = os.listdir(tasks_mod.TASKS_ARCHIVE_DIR)
        assert len(archive_files) == 1
        archive_path = os.path.join(tasks_mod.TASKS_ARCHIVE_DIR, archive_files[0])
        with open(archive_path) as f:
            archive_content = f.read()
        assert "old done task" in archive_content

    def test_keeps_recent_completed(self):
        recent_date = date.today().isoformat()
        content = (
            "# TASKS.md\n\n## Tasks\n\n"
            f"- [x] recent done (priority: low)\n"
            f"  - completed: {recent_date}\n"
        )
        memory.write_tasks(content)
        _archive_completed_tasks()
        # Should still be in TASKS.md
        assert "recent done" in memory.read_tasks()

    def test_no_archive_when_nothing_to_archive(self):
        add_task(description="just pending")
        _archive_completed_tasks()
        assert not os.path.exists(tasks_mod.TASKS_ARCHIVE_DIR)
