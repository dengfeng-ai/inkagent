---
name: autopilot
description: Autonomous task execution — read TASKS.md, pick the highest-priority task, execute it, log results
---

# Autopilot

When triggered by a cron job, follow this workflow:

## 1. Read the task list

Read `memory/TASKS.md`. If the file doesn't exist or has no pending tasks, reply with `HEARTBEAT_OK`.

## 2. Pick a task

**Only work on ONE task per heartbeat cycle.**

If a task is marked `- [~]` (in progress), resume that task first.

Otherwise, select the highest-priority pending task (`- [ ]`). Priority order: critical > high > medium > low. Among equal priority, pick the one listed first.

## 3. Assess task size

Before executing, evaluate if the task is too large for a single cycle.

**If the task is large** (e.g. "add dark mode", "refactor auth system", "build a new feature"):
- Do NOT attempt to execute it directly
- Break it into small, concrete sub-tasks and write them back to TASKS.md using `update_task` to mark the original as completed with a note, then `add_task` for each sub-task
- Each sub-task should be completable in one cycle (a few file changes + tests)
- Stop here — the sub-tasks will be picked up in subsequent cycles

**If the task is small enough** (a few file edits, one focused change): proceed to step 4.

## 4. Understand the task

Read the task's context. If a `project` path is specified:
- Use `list_directory` and `read_file` to understand the project structure
- Read relevant source files to understand the codebase
- Check for existing tests, README, or documentation

If resuming an in-progress task (`[~]`), read the `progress` note to understand what's already done.

## 5. Execute

Make the changes:
- Use `read_file` to read relevant code
- Use `edit_file` or `write_file` to make changes
- Use `run_shell` to run tests, linters, or build commands
- Verify each change works before moving on

Guidelines:
- **Stay focused** — only work on the one task you picked, don't fix unrelated things
- Make small, incremental changes — don't rewrite entire files
- Run tests after each meaningful change
- If a step fails, diagnose and fix before moving on
- If stuck after 3 attempts on the same issue, mark the task as blocked and move on
- Always work in a git branch: create a branch named `autopilot/{task-id}` before making changes
- Commit after each meaningful step with a clear commit message
- **If running low on tool rounds**, stop early, commit your progress, and mark the task as `[~]` with a progress note — don't rush to finish

## 6. Update task status

After execution, update `memory/TASKS.md` via `update_task`:
- Success: mark as `completed` with a result note
- In progress (partially done, will continue next cycle): mark as `in_progress` with a progress note
- Blocked (stuck, needs user input): mark as `blocked` with a blocker note

## 7. Log results

Use `log_daily` to record what was done:
- Which task was worked on
- What changes were made (files modified, branch name)
- Test results
- Any issues encountered

## 8. Notify or stay silent

**Notify the user** (reply with a summary) when:
- A task was completed
- A task is blocked and needs user input
- Something unexpected was found

**Stay silent** (reply with `HEARTBEAT_OK`) when:
- No pending tasks
- A task is in progress and progressing normally (partial work done, will continue next cycle)

## Setup

To enable autopilot, create a cron job with `silent_ok=true`:
```
create_cron(id="autopilot", cron="*/30 * * * *", prompt="Run autopilot. Read the autopilot skill instructions first.", silent_ok=true)
```

## TASKS.md format

When creating or updating `memory/TASKS.md`, use this format:

```markdown
# TASKS.md

_Autonomous task queue. Agent picks and executes tasks on each autopilot cycle._

## Tasks

- [ ] Task description (priority: high)
  - project: /path/to/project
  - context: Additional context, requirements, or constraints
  - branch: autopilot/task-id (filled by agent when work starts)

- [~] In-progress task (priority: medium)
  - project: /path/to/project
  - context: What needs to be done
  - progress: What's been done so far

- [x] Completed task (priority: low)
  - completed: 2026-04-01
  - result: Brief summary of what was done

- [!] Blocked task (priority: high)
  - blocker: Description of what's blocking this task
```

Status markers:
- `[ ]` — pending
- `[~]` — in progress
- `[x]` — completed
- `[!]` — blocked, needs user input
