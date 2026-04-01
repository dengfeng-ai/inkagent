"""Tests for cron scheduler — job CRUD and persistence."""

import json
import os

import pytest

from inkagent import scheduler
from inkagent.scheduler import add_job, list_jobs, remove_job


pytestmark = pytest.mark.usefixtures("tmp_memory_dir")


@pytest.fixture(autouse=True)
def clean_scheduler_jobs():
    """Clear in-memory job list before each test."""
    scheduler._jobs.clear()
    yield
    scheduler._jobs.clear()


# ---------------------------------------------------------------------------
# add_job
# ---------------------------------------------------------------------------

class TestAddJob:
    def test_creates_job(self):
        job = add_job("j1", "*/5 * * * *", "check email", "tg_123")
        assert job["id"] == "j1"
        assert job["cron"] == "*/5 * * * *"
        assert job["prompt"] == "check email"
        assert job["session_id"] == "tg_123"
        assert job["enabled"] is True

    def test_persists_to_disk(self):
        add_job("j2", "0 9 * * *", "morning", "tg_1")
        assert os.path.exists(scheduler.CRONS_PATH)
        with open(scheduler.CRONS_PATH) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["id"] == "j2"

    def test_invalid_cron_expression(self):
        with pytest.raises(ValueError, match="Invalid cron"):
            add_job("bad", "not a cron", "x", "s1")

    def test_invalid_timezone(self):
        with pytest.raises(ValueError, match="Invalid timezone"):
            add_job("bad_tz", "* * * * *", "x", "s1", tz="Fake/Zone")

    def test_duplicate_id_rejected(self):
        add_job("dup", "* * * * *", "first", "s1")
        with pytest.raises(ValueError, match="already exists"):
            add_job("dup", "* * * * *", "second", "s1")

    def test_custom_timezone(self):
        job = add_job("tz", "0 9 * * *", "x", "s1", tz="America/New_York")
        assert job["timezone"] == "America/New_York"

    def test_silent_ok_flag(self):
        job = add_job("hb", "*/10 * * * *", "heartbeat", "s1", silent_ok=True)
        assert job["silent_ok"] is True

    def test_silent_ok_default_false(self):
        job = add_job("normal", "* * * * *", "x", "s1")
        assert job["silent_ok"] is False


# ---------------------------------------------------------------------------
# remove_job
# ---------------------------------------------------------------------------

class TestRemoveJob:
    def test_removes_existing(self):
        add_job("rm1", "* * * * *", "x", "s1")
        assert remove_job("rm1") is True
        assert list_jobs() == []

    def test_returns_false_for_nonexistent(self):
        assert remove_job("nope") is False

    def test_persists_removal(self):
        add_job("rm2", "* * * * *", "x", "s1")
        remove_job("rm2")
        with open(scheduler.CRONS_PATH) as f:
            data = json.load(f)
        assert len(data) == 0


# ---------------------------------------------------------------------------
# list_jobs
# ---------------------------------------------------------------------------

class TestListJobs:
    def test_empty(self):
        assert list_jobs() == []

    def test_returns_all_jobs(self):
        add_job("a", "* * * * *", "x", "s1")
        add_job("b", "* * * * *", "y", "s1")
        jobs = list_jobs()
        assert len(jobs) == 2
        ids = {j["id"] for j in jobs}
        assert ids == {"a", "b"}

    def test_roundtrip_via_disk(self):
        """Jobs saved by add_job should be loadable after clearing memory."""
        add_job("rt", "0 12 * * *", "noon", "s1", tz="UTC")
        scheduler._jobs.clear()  # simulate fresh process
        jobs = list_jobs()  # triggers _load_jobs from disk
        assert len(jobs) == 1
        assert jobs[0]["id"] == "rt"
        assert jobs[0]["timezone"] == "UTC"
