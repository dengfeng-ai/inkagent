# inkagent

A lightweight personal AI agent that runs locally, powered by Claude and driven by Markdown memory.
Inspired by OpenClaw. Built in Python.

## Architecture

```
inkagent/
├── main.py              # CLI entry point
├── agent/
│   ├── brain.py         # LLM agentic loop (tool_use)
│   ├── memory.py        # Markdown-based memory (read/write)
│   └── registry.py      # Skill registration system
├── skills/
│   ├── __init__.py      # Auto-imports all skills
│   └── shell.py         # run_shell skill
└── memory/
    ├── SOUL.md          # Agent persona (name, tone, behavior rules)
    ├── USER.md          # User personal info (name, role, interests)
    ├── MEMORY.md        # Long-term memory (curated, durable)
    └── daily/           # Daily logs (ephemeral, append-only)
        └── YYYY-MM-DD.md
```

Key design principle: `brain.py` has zero knowledge of individual skills.
Skills register themselves via `@registry.register(...)` — adding a skill never touches core code.

## Tech Stack

- Python 3.11+
- `anthropic` SDK — Claude Sonnet, tool_use agentic loop
- Markdown files — all memory storage, no database
- `python-telegram-bot` — when adding bot interface (not yet implemented)

## Common Commands

```bash
# Run the CLI
python main.py

# Install dependencies
pip install -r requirements.txt

# View memory
cat memory/SOUL.md
cat memory/USER.md
```

## Memory System

Three-tier Markdown memory in `memory/`:

- **`SOUL.md`** — Agent persona. Injected into the system prompt instruction area. Updated by the LLM via `update_soul` tool when the user sets behavior rules (name, tone, language, style).
- **`USER.md`** — User profile. Injected into the system prompt context area. Updated by the LLM via `update_user_profile` tool when it learns personal info (name, role, location, interests).
- **`MEMORY.md`** — Long-term curated memory. Injected into system prompt. Updated via `save_memory` tool for durable facts, preferences, decisions, events.
- **`daily/YYYY-MM-DD.md`** — Daily logs. Append-only, one file per day. Today's + yesterday's logs injected into system prompt. Updated via `log_daily` tool for transient notes (decisions, topics, action items). `recall_memory` searches across both MEMORY.md and daily logs.

Conversation history is kept in-memory for the current session, auto-saved to `conversations/` as JSON.
The `memory/` directory is gitignored — never commit it.

## Skill System

Each skill is a Python function decorated with `@registry.register(...)`.
The decorator takes `name`, `description`, and `input_schema` (JSON Schema format for Claude tool_use).

To add a new skill:
1. Create `skills/your_skill.py`
2. Import `registry` from `agent.registry`
3. Decorate your function with `@registry.register(...)`
4. Add `from skills import your_skill` in `skills/__init__.py`

That's it. `brain.py` picks it up automatically.

Built-in skills:
- `run_shell` — executes shell commands, 30s timeout, output capped at 3000 chars
- `update_soul` — rewrites `memory/SOUL.md` with agent persona settings
- `update_user_profile` — rewrites `memory/USER.md` with user personal info
- `save_memory` — appends durable entry to `memory/MEMORY.md`
- `recall_memory` — keyword search across MEMORY.md and daily logs
- `log_daily` — appends a note to today's daily log (`memory/daily/YYYY-MM-DD.md`)

## Agentic Loop

`brain.py` runs a standard tool_use loop:
1. Build system prompt (instructions + SOUL.md + USER.md + MEMORY.md + daily logs) + conversation messages
2. Call Claude API with all registered tools
3. If `stop_reason == "tool_use"`: execute tools, append results, loop
4. If `stop_reason == "end_turn"`: extract text, append to in-memory conversation, return

No recursion limit is set — rely on Claude's natural termination behavior.

## Code Style

- Type hints on all function signatures
- No global state except `registry` singleton and `memory` instance in `brain.py`
- Cap tool output at 3000 chars before returning to avoid context explosion
- IMPORTANT: Never import skills directly in `brain.py` — always go through `registry`

## Roadmap (in order)

1. ~~CLI + shell skill + Markdown memory~~ (Phase 1)
2. Telegram bot interface — wrap `run_agent()` in a message handler
3. Heartbeat / scheduled tasks — APScheduler, daily briefing
4. Web search skill
5. Gmail / Google Calendar skills