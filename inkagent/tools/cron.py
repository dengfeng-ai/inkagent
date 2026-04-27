"""Cron skills — create, list, and delete scheduled tasks."""

import inkagent.session as _session
from inkagent.config import DEFAULT_TIMEZONE
from inkagent.memory import get_heartbeat, heartbeat_needs_setup
from inkagent.registry import register
from inkagent.scheduler import add_job, remove_job, list_jobs


@register(
    name="create_cron",
    description=(
        "Create a scheduled task that runs on a cron schedule. "
        "The prompt will be sent to the agent at each trigger time, "
        "and the reply delivered to the current chat session. "
        "Cron format: minute hour day month weekday (e.g. '0 9 * * *' = daily at 9 AM). "
        f"Times are interpreted in the user's timezone (default: {DEFAULT_TIMEZONE}). "
        "Set silent_ok=true for heartbeat-style jobs — if the agent replies "
        "with only HEARTBEAT_OK, no message is sent to the user."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "Unique job ID (short, slug-like, e.g. 'morning-briefing')",
            },
            "cron": {
                "type": "string",
                "description": "Cron expression: minute hour day month weekday (e.g. '0 9 * * *')",
            },
            "prompt": {
                "type": "string",
                "description": "The message to send to the agent when the job fires",
            },
            "timezone": {
                "type": "string",
                "description": f"IANA timezone (e.g. 'Asia/Singapore', 'America/New_York'). Default: {DEFAULT_TIMEZONE}",
            },
            "silent_ok": {
                "type": "boolean",
                "description": "If true, suppress notification when the agent replies with HEARTBEAT_OK (for heartbeat jobs). Default: false",
            },
        },
        "required": ["id", "cron", "prompt"],
    },
)
def create_cron(id: str, cron: str, prompt: str, timezone: str = DEFAULT_TIMEZONE, silent_ok: bool = False) -> str:
    try:
        session_id = _session.current_session_id.get()
        job = add_job(job_id=id, cron_expr=cron, prompt=prompt, session_id=session_id, tz=timezone, silent_ok=silent_ok)
        mode = " (heartbeat mode)" if job.get("silent_ok") else ""
        result = (
            f"Created scheduled task '{job['id']}'{mode}.\n"
            f"Schedule: {job['cron']} ({job['timezone']})\n"
            f"Prompt: {job['prompt']}\n"
            f"Session: {job['session_id']}"
        )
        if silent_ok:
            get_heartbeat()  # seed memory/HEARTBEAT.md with default template if missing
            if heartbeat_needs_setup():
                result += (
                    "\n\nHeartbeat checklist (memory/HEARTBEAT.md) is empty. "
                    "Ask the user what they want to check periodically, "
                    "then append `- [ ] ...` items under the Checklist section. "
                    "Keep the reply short."
                )
        return result
    except ValueError as e:
        return f"Error: {e}"


@register(
    name="list_crons",
    description="List all scheduled tasks (cron jobs).",
    input_schema={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
def list_crons() -> str:
    jobs = list_jobs()
    if not jobs:
        return "No scheduled tasks."
    lines = []
    for j in jobs:
        status = "enabled" if j.get("enabled", True) else "disabled"
        if j.get("silent_ok"):
            status += ", heartbeat"
        tz = j.get("timezone", "UTC")
        lines.append(
            f"- **{j['id']}** [{status}]\n"
            f"  Schedule: `{j['cron']}` ({tz})\n"
            f"  Prompt: {j['prompt']}\n"
            f"  Session: {j['session_id']}"
        )
    return "\n".join(lines)


@register(
    name="delete_cron",
    description="Delete a scheduled task by its ID.",
    input_schema={
        "type": "object",
        "properties": {
            "id": {
                "type": "string",
                "description": "The job ID to delete",
            },
        },
        "required": ["id"],
    },
)
def delete_cron(id: str) -> str:
    if remove_job(id):
        return f"Deleted scheduled task '{id}'."
    return f"Error: no task found with ID '{id}'."
