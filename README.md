# inkagent

A lightweight personal AI agent that runs locally on your machine. Powered by Claude or OpenAI, driven by Markdown memory.

Inspired by [OpenClaw](https://github.com/nichochar/open-claw). Built in Python.

## Features

- **Agentic tool-use loop** — sends your message to the LLM, executes tools, feeds results back, repeats until done
- **Markdown memory** — persona, user profile, long-term memory, daily logs — all plain `.md` files you can read and edit
- **Auto memory promotion** — daily logs are curated into long-term memory overnight via a small model
- **Multi-provider** — supports Anthropic (Claude) and OpenAI out of the box, switchable via env var
- **Self-registering skills** — add capabilities by dropping in a decorated Python function
- **Two interfaces** — CLI (`main.py`) or Telegram bot (`bot.py`)
- **Observability** — optional [Langfuse](https://langfuse.com) tracing for all LLM calls and tool executions

## Quick Start

```bash
git clone https://github.com/dengfeng-ai/inkagent
cd inkagent
cp .env.example .env
```

Edit `.env` and fill in your API key:

```bash
# Anthropic (default)
ANTHROPIC_API_KEY=sk-ant-xxxxx

# — or OpenAI —
# OPENAI_API_KEY=sk-xxxxx
# LLM_PROVIDER=openai
```

### Option A: Docker (recommended)

Docker 更安全 — `run_shell` 等工具在容器内执行，不会影响宿主机。

```bash
docker build -t inkagent .

# CLI mode (default)
docker run -it --env-file .env inkagent

# Telegram bot mode
docker run --env-file .env inkagent python bot.py
```

持久化 `memory/` 和 `conversations/`，避免容器重启后数据丢失：

```bash
# CLI mode
docker run -it --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  inkagent

# Telegram bot mode
docker run --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  inkagent python bot.py
```

### Option B: Local

Requires **Python 3.11+**.

```bash
# setup script (creates venv, installs deps)
./setup.sh          # macOS / Linux
setup.bat           # Windows

# — or manual —
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
source .venv/bin/activate
python main.py          # CLI mode
python bot.py           # Telegram bot (requires TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_ID in .env)
```

Note: 本地运行时 `run_shell` 直接在你的机器上执行命令，请注意安全。

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
│   ├── brain.py         # Agentic loop (provider-agnostic)
│   ├── config.py        # Shared constants (limits, timeouts)
│   ├── memory.py        # Markdown memory (read/write)
│   ├── registry.py      # Skill registration
│   ├── prompts.py       # Prompt templates
│   ├── session.py       # Conversation history + persistence
│   ├── compression.py   # Context window compression
│   ├── promotion.py     # Daily log → long-term memory promotion
│   └── providers/       # Pluggable LLM providers
│       ├── base.py      # LLMProvider ABC + shared types
│       ├── anthropic.py # Anthropic (Claude)
│       └── openai.py    # OpenAI
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

## Configuration

All config lives in `.env` (gitignored). See [`.env.example`](.env.example) for the full list:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For Anthropic | Claude API key |
| `OPENAI_API_KEY` | For OpenAI | OpenAI API key |
| `LLM_PROVIDER` | No | `anthropic` (default) or `openai` |
| `LLM_MODEL` | No | Main model (default: `claude-sonnet-4-20250514` / `gpt-4o`) |
| `LLM_SMALL_MODEL` | No | Cheap model for compression/promotion (default: `claude-haiku-4-5-20251001` / `gpt-4o-mini`) |
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
