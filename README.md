# inkagent

A lightweight personal AI agent that runs locally on your machine. Powered by Claude, driven by Markdown memory.

Inspired by [OpenClaw](https://github.com/nichochar/open-claw). Built in Python.

## Features

- **Agentic tool-use loop** — sends your message to Claude, executes tools, feeds results back, repeats until done
- **Markdown memory** — persona, user profile, long-term memory, daily logs — all plain `.md` files you can read and edit
- **Auto memory promotion** — daily logs are curated into long-term memory overnight via Haiku
- **Self-registering skills** — add capabilities by dropping in a decorated Python function
- **Two interfaces** — CLI (`main.py`) or Telegram bot (`bot.py`)
- **Observability** — optional [Langfuse](https://langfuse.com) tracing for all LLM calls and tool executions

## Quick Start

Requires **Python 3.11+** and an [Anthropic API key](https://console.anthropic.com/).

```bash
git clone https://github.com/yourname/inkagent.git
cd inkagent

# Option A: setup script (creates venv, installs deps, generates .env)
./setup.sh          # macOS / Linux
setup.bat           # Windows

# Option B: manual
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and fill in your API key:

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

Run:

```bash
source .venv/bin/activate
python main.py          # CLI mode
python bot.py           # Telegram bot (requires TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_ID in .env)
```

## How It Works

```
you> remember that I prefer dark mode

agent> [calls update_user_profile] → saves to memory/USER.md
agent> [calls log_daily] → appends to memory/daily/2025-03-21.md
agent> Got it, noted your preference for dark mode.

# Next day, the promotion system reviews yesterday's log
# and decides if anything is worth keeping in MEMORY.md
```

## Memory System

All memory lives in `memory/` as plain Markdown:

| File | Purpose | Updated by |
|------|---------|------------|
| `SOUL.md` | Agent persona — name, tone, language, behavior rules | `update_soul` tool |
| `USER.md` | User profile — name, role, interests | `update_user_profile` tool |
| `MEMORY.md` | Long-term memory — curated facts and decisions | Automatic promotion |
| `daily/YYYY-MM-DD.md` | Daily log — ephemeral notes, one file per day | `log_daily` tool |

The agent sees `SOUL.md`, `USER.md`, `MEMORY.md`, and the last two days of daily logs in every conversation.

## Architecture

```
inkagent/
├── main.py              # CLI entry point
├── bot.py               # Telegram bot entry point
├── agent/
│   ├── brain.py         # Agentic loop (tool_use)
│   ├── memory.py        # Markdown memory (read/write)
│   └── registry.py      # Skill registration
├── skills/
│   ├── shell.py         # run_shell
│   ├── profile.py       # update_soul, update_user_profile
│   └── memory_skill.py  # log_daily, recall_memory
└── memory/              # All memory (gitignored)
    ├── SOUL.md
    ├── USER.md
    ├── MEMORY.md
    └── daily/
```

Key design: `brain.py` has zero knowledge of individual skills. Skills register via `@registry.register(...)` — adding one never touches core code.

## Built-in Skills

| Skill | Description |
|-------|-------------|
| `run_shell` | Execute shell commands (30s timeout, output capped at 3k chars) |
| `update_soul` | Update agent persona — name, tone, language, behavior rules |
| `update_user_profile` | Update user info — name, role, location, interests |
| `log_daily` | Jot a note in today's daily log; important entries auto-promote to long-term memory |
| `recall_memory` | Keyword search across MEMORY.md and daily logs |

## Adding a Skill

Create `skills/my_skill.py`:

```python
from agent.registry import register

@register(
    name="my_skill",
    description="What this skill does",
    input_schema={
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "..."},
        },
        "required": ["param"],
    },
)
def my_skill(param: str) -> str:
    return "result"
```

Add to `skills/__init__.py`:

```python
from skills import my_skill  # noqa: F401
```

Done. The agent picks it up automatically.

## Docker (optional)

```bash
docker build -t inkagent .
docker run --env-file .env -v ./memory:/app/memory inkagent
```

Note: `run_shell` executes inside the container, not on your host machine.

## Configuration

All config lives in `.env` (gitignored). See [`.env.example`](.env.example) for the full list:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API key |
| `TELEGRAM_BOT_TOKEN` | For bot | Telegram bot token from @BotFather |
| `TELEGRAM_OWNER_ID` | For bot | Your numeric Telegram user ID |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse observability |
| `LANGFUSE_SECRET_KEY` | No | Langfuse observability |
| `LANGFUSE_HOST` | No | Langfuse host URL |

## Roadmap

- [x] CLI + shell skill + Markdown memory
- [x] Langfuse observability
- [x] Telegram bot interface
- [x] Long-term memory + daily logs + auto-promotion
- [ ] Scheduled tasks / daily briefing
- [ ] Web search skill
- [ ] Gmail / Google Calendar skills

## License

MIT
