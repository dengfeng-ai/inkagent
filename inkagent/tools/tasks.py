"""Task management tools — add, list, and update tasks in TASKS.md."""

import logging
import os
import re
from datetime import date, timedelta

from inkagent.config import TASKS_ARCHIVE_DIR
from inkagent.memory import read_tasks, write_tasks
from inkagent.registry import register

logger = logging.getLogger(__name__)

# Completed tasks older than this many days are archived
_ARCHIVE_AFTER_DAYS = 3


def _archive_completed_tasks() -> None:
    """Move completed tasks older than _ARCHIVE_AFTER_DAYS to monthly archive files."""
    content = read_tasks()
    lines = content.split("\n")
    cutoff = date.today() - timedelta(days=_ARCHIVE_AFTER_DAYS)

    keep_lines: list[str] = []
    # Bucket: year-month -> list of task block lines
    archive_buckets: dict[str, list[str]] = {}

    i = 0
    while i < len(lines):
        line = lines[i]
        # Detect a completed task line
        if re.match(r"^- \[x\]", line):
            # Collect the full task block (task line + indented detail lines)
            block = [line]
            j = i + 1
            while j < len(lines) and lines[j].startswith("  - "):
                block.append(lines[j])
                j += 1

            # Find the completion date in the block
            completed_date = None
            for bl in block:
                m = re.match(r"^\s+- completed:\s*(\d{4}-\d{2}-\d{2})", bl)
                if m:
                    try:
                        completed_date = date.fromisoformat(m.group(1))
                    except ValueError:
                        pass
                    break

            if completed_date and completed_date < cutoff:
                # Archive this task
                month_key = completed_date.strftime("%Y-%m")
                archive_buckets.setdefault(month_key, []).extend(block)
                i = j
                continue

        keep_lines.append(line)
        i += 1

    if not archive_buckets:
        return

    # Write archived tasks to monthly files
    os.makedirs(TASKS_ARCHIVE_DIR, exist_ok=True)
    for month_key, task_lines in archive_buckets.items():
        archive_path = os.path.join(TASKS_ARCHIVE_DIR, f"{month_key}.md")
        header = f"# Completed Tasks — {month_key}\n\n"
        existing = ""
        if os.path.exists(archive_path):
            with open(archive_path, "r") as f:
                existing = f.read()
        if not existing:
            existing = header
        with open(archive_path, "w") as f:
            f.write(existing.rstrip() + "\n" + "\n".join(task_lines) + "\n")
        logger.info("Archived %d task lines to %s", len(task_lines), archive_path)

    # Rewrite TASKS.md without the archived tasks
    write_tasks("\n".join(keep_lines))


@register(
    name="add_task",
    description=(
        "Add a new task to the autopilot task queue (memory/TASKS.md). "
        "Tasks are executed automatically by the heartbeat cron cycle."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "What needs to be done",
            },
            "priority": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
                "description": "Task priority. Default: medium",
            },
            "repo": {
                "type": "string",
                "description": "GitHub repo in owner/repo format (optional)",
            },
            "context": {
                "type": "string",
                "description": "Additional context, requirements, or constraints (optional)",
            },
        },
        "required": ["description"],
    },
)
def add_task(
    description: str,
    priority: str = "medium",
    repo: str = "",
    context: str = "",
) -> str:
    _archive_completed_tasks()
    content = read_tasks()

    today = date.today().isoformat()
    entry = f"\n- [ ] {description} (priority: {priority})"
    entry += f"\n  - created: {today}"
    if repo:
        entry += f"\n  - repo: {repo}"
    if context:
        entry += f"\n  - context: {context}"
    entry += "\n"

    content = content.rstrip() + "\n" + entry
    write_tasks(content)
    return f"Task added: {description} (priority: {priority})"


@register(
    name="list_tasks",
    description="List all tasks from the autopilot task queue (memory/TASKS.md).",
    input_schema={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "enum": ["all", "pending", "in_progress", "completed", "blocked"],
                "description": "Filter by status. Default: all",
            },
        },
        "required": [],
    },
)
def list_tasks(status: str = "all") -> str:
    _archive_completed_tasks()
    content = read_tasks().strip()

    # Check if there are any actual task lines
    task_lines = [l for l in content.split("\n") if re.match(r"^- \[[ x~!]\]", l)]
    if not task_lines:
        return "No tasks in the queue."

    status_map = {
        "pending": "[ ]",
        "in_progress": "[~]",
        "completed": "[x]",
        "blocked": "[!]",
    }

    if status == "all":
        return content

    marker = status_map.get(status)
    if not marker:
        return content

    # Extract task blocks (task line + indented detail lines)
    lines = content.split("\n")
    filtered: list[str] = []
    in_match = False
    for line in lines:
        if re.match(r"^- \[", line):
            in_match = marker in line
        if in_match:
            filtered.append(line)

    if not filtered:
        return f"No {status} tasks."
    return "\n".join(filtered)


@register(
    name="update_task",
    description=(
        "Update a task's status in the autopilot task queue (memory/TASKS.md). "
        "Use this to mark tasks as in-progress, completed, or blocked."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "The task description (or unique substring) to match",
            },
            "status": {
                "type": "string",
                "enum": ["pending", "in_progress", "completed", "blocked"],
                "description": "New status for the task",
            },
            "note": {
                "type": "string",
                "description": "Optional note to append (e.g. progress, blocker, result)",
            },
        },
        "required": ["task", "status"],
    },
)
def update_task(task: str, status: str, note: str = "") -> str:
    content = read_tasks()

    status_markers = {
        "pending": "[ ]",
        "in_progress": "[~]",
        "completed": "[x]",
        "blocked": "[!]",
    }
    new_marker = status_markers.get(status)
    if not new_marker:
        return f"Error: invalid status '{status}'"

    # Find the line containing the task description
    lines = content.split("\n")
    found = False
    for i, line in enumerate(lines):
        if re.match(r"^- \[[ x~!]\]", line) and task.lower() in line.lower():
            lines[i] = re.sub(r"^- \[[ x~!]\]", f"- {new_marker}", line)
            insert_at = i + 1
            while insert_at < len(lines) and lines[insert_at].startswith("  - "):
                insert_at += 1
            today = date.today().isoformat()
            if status == "completed":
                # Auto-add completion date
                lines.insert(insert_at, f"  - completed: {today}")
                insert_at += 1
            else:
                # Auto-add update timestamp for non-completed status changes
                lines.insert(insert_at, f"  - updated: {today}")
                insert_at += 1
            if note:
                note_key = {
                    "in_progress": "progress",
                    "completed": "result",
                    "blocked": "blocker",
                    "pending": "note",
                }[status]
                lines.insert(insert_at, f"  - {note_key}: {note}")
            found = True
            break

    if not found:
        return f"Error: no task matching '{task}'"

    write_tasks("\n".join(lines))
    return f"Task updated to {status}: {task}"
