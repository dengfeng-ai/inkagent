"""Cron scheduler — runs scheduled tasks and delivers results via callback.

Jobs are persisted in memory/crons.json. The scheduler is an asyncio loop
that checks every 60 seconds whether any job is due, then calls run_agent()
and pushes the reply through a callback (e.g. Telegram send_message).
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Awaitable
from zoneinfo import ZoneInfo

from croniter import croniter

from inkagent.config import CRONS_PATH, DEFAULT_TIMEZONE

logger = logging.getLogger(__name__)

# In-memory job list, synced with crons.json.
_jobs: list[dict[str, Any]] = []


def _load_jobs() -> None:
    """Load jobs from disk into memory."""
    global _jobs
    if os.path.exists(CRONS_PATH):
        with open(CRONS_PATH, "r", encoding="utf-8") as f:
            _jobs = json.load(f)
    else:
        _jobs = []


def _save_jobs() -> None:
    """Persist jobs to disk."""
    os.makedirs(os.path.dirname(CRONS_PATH), exist_ok=True)
    with open(CRONS_PATH, "w", encoding="utf-8") as f:
        json.dump(_jobs, f, indent=2, ensure_ascii=False)


HEARTBEAT_OK = "HEARTBEAT_OK"


def add_job(
    job_id: str,
    cron_expr: str,
    prompt: str,
    session_id: str,
    tz: str = DEFAULT_TIMEZONE,
    silent_ok: bool = False,
) -> dict[str, Any]:
    """Add a new cron job. Returns the created job dict.

    If silent_ok is True, the callback is skipped when the agent reply
    contains only HEARTBEAT_OK (used for heartbeat-style jobs).
    """
    _load_jobs()

    # Validate cron expression.
    if not croniter.is_valid(cron_expr):
        raise ValueError(f"Invalid cron expression: {cron_expr}")

    # Validate timezone.
    try:
        ZoneInfo(tz)
    except (KeyError, ValueError):
        raise ValueError(f"Invalid timezone: {tz}")

    # Reject duplicate IDs.
    if any(j["id"] == job_id for j in _jobs):
        raise ValueError(f"Job ID already exists: {job_id}")

    job = {
        "id": job_id,
        "cron": cron_expr,
        "prompt": prompt,
        "session_id": session_id,
        "timezone": tz,
        "enabled": True,
        "silent_ok": silent_ok,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _jobs.append(job)
    _save_jobs()
    logger.info("Created cron job %s: %s (%s)", job_id, cron_expr, tz)
    return job


def remove_job(job_id: str) -> bool:
    """Remove a job by ID. Returns True if found and removed."""
    _load_jobs()
    before = len(_jobs)
    _jobs[:] = [j for j in _jobs if j["id"] != job_id]
    if len(_jobs) < before:
        _save_jobs()
        logger.info("Removed cron job %s", job_id)
        return True
    return False


def list_jobs() -> list[dict[str, Any]]:
    """Return all jobs (without internal state)."""
    _load_jobs()
    return [
        {k: v for k, v in j.items()}
        for j in _jobs
    ]


# ---------------------------------------------------------------------------
# Async scheduler loop
# ---------------------------------------------------------------------------

# Callback type: async function(session_id, reply_text) -> None
SendCallback = Callable[[str, str], Awaitable[None]]


async def run_scheduler(send_callback: SendCallback) -> None:
    """Run the cron check loop. Call this as an asyncio task.

    Every 60 seconds, check each enabled job. If the job was due since the
    last check, run the agent and deliver the reply via send_callback.
    """
    from inkagent.brain import run_agent
    from inkagent.providers import LLMError
    from inkagent.session import inject_message

    logger.info("Scheduler started")
    # Track last check per timezone so each job fires in its own local time.
    last_check_utc = datetime.now(timezone.utc)

    while True:
        await asyncio.sleep(60)
        now_utc = datetime.now(timezone.utc)
        _load_jobs()

        for job in _jobs:
            if not job.get("enabled", True):
                continue
            try:
                tz = ZoneInfo(job.get("timezone", DEFAULT_TIMEZONE))
                last_local = last_check_utc.astimezone(tz)
                now_local = now_utc.astimezone(tz)

                cron = croniter(job["cron"], last_local)
                next_fire = cron.get_next(datetime)
                if next_fire <= now_local:
                    logger.info("Firing cron job %s (tz=%s)", job["id"], tz)
                    # Each firing gets a fresh session — cron jobs are
                    # independent tasks, not ongoing conversations.
                    ts = now_utc.strftime("%Y%m%d%H%M%S")
                    cron_session_id = f"{job['session_id']}_cron_{job['id']}_{ts}"
                    try:
                        reply = await asyncio.to_thread(
                            run_agent, job["prompt"], cron_session_id
                        )
                    except LLMError as e:
                        reply = f"[Scheduled task '{job['id']}' failed: {e}]"
                    # If silent_ok and the agent says nothing important,
                    # skip notification entirely.
                    is_silent = (
                        job.get("silent_ok", False)
                        and reply.strip() == HEARTBEAT_OK
                    )
                    if is_silent:
                        logger.info(
                            "Heartbeat job %s: nothing to report, staying silent",
                            job["id"],
                        )
                    else:
                        # Bridge the final reply into the user's main session
                        # so follow-up questions have context.
                        inject_message(
                            job["session_id"], "user",
                            f"[Scheduled task '{job['id']}' triggered]",
                        )
                        inject_message(job["session_id"], "assistant", reply)
                        await send_callback(job["session_id"], reply)
            except Exception:
                logger.exception("Error processing cron job %s", job["id"])

        last_check_utc = now_utc
