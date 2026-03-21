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
    ├── profile.md       # Persistent user profile (LLM-maintained)
    └── history.md       # Rolling conversation history (last 20 turns)
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
pip install anthropic

# View memory
cat memory/profile.md
cat memory/history.md
```

## Memory System

Two Markdown files in `memory/`:

- **`profile.md`** — User profile. Updated by the LLM via `update_profile` tool when it learns something new. Never truncated.
- **`history.md`** — Conversation history. Append-only per turn, trimmed to last `HISTORY_LIMIT` (default: 20) turns by `_trim_history()`.

Both files are injected into the system prompt on every turn via `memory.build_context()`.
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
- `update_profile` — rewrites `memory/profile.md` with new user info

## Agentic Loop

`brain.py` runs a standard tool_use loop:
1. Build messages: system prompt (fixed instructions + memory context) + user message
2. Call Claude API with all registered tools
3. If `stop_reason == "tool_use"`: execute tools, append results, loop
4. If `stop_reason == "end_turn"`: extract text, save turn to history, return

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