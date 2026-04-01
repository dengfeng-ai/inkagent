"""Task management tools — add, list, and update tasks in TASKS.md."""

import re

from agent.memory import read_tasks, write_tasks
from agent.registry import register


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
            "project": {
                "type": "string",
                "description": "Absolute path to the project directory (optional)",
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
    project: str = "",
    context: str = "",
) -> str:
    content = read_tasks()

    entry = f"\n- [ ] {description} (priority: {priority})"
    if project:
        entry += f"\n  - project: {project}"
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
            if note:
                note_key = {
                    "in_progress": "progress",
                    "completed": "result",
                    "blocked": "blocker",
                    "pending": "note",
                }[status]
                note_line = f"  - {note_key}: {note}"
                insert_at = i + 1
                while insert_at < len(lines) and lines[insert_at].startswith("  - "):
                    insert_at += 1
                lines.insert(insert_at, note_line)
            found = True
            break

    if not found:
        return f"Error: no task matching '{task}'"

    write_tasks("\n".join(lines))
    return f"Task updated to {status}: {task}"
