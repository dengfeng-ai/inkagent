# inkagent

A lightweight personal AI agent that runs locally on your machine. Powered by Claude or OpenAI, driven by Markdown memory.

Inspired by [OpenClaw](https://github.com/nichochar/open-claw). Built in Python.

## Features

- **Agentic tool-use loop** — sends your message to the LLM, executes tools, feeds results back, repeats until done
- **Markdown memory** — persona, user profile, long-term memory, daily logs — all plain `.md` files you can read and edit
- **Auto memory promotion** — daily logs are curated into long-term memory overnight via a small model
- **Semantic memory search** — daily logs indexed with sqlite-vec for vector search (requires OpenAI API key for embeddings, falls back to keyword search)
- **Multi-provider** — supports Anthropic (Claude) and OpenAI out of the box, switchable via env var
- **Self-registering tools** — add capabilities by dropping in a decorated Python function
- **Instruction skills** — teach the agent new workflows with just a Markdown file, no code needed
- **Scheduled tasks** — cron-based scheduler lets the agent reach out proactively (e.g. daily briefings), each firing gets a fresh session
- **Heartbeat** — periodic background checks (email, calendar, etc.) via `HEARTBEAT.md` checklist, only notifies when something needs attention
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

Docker is recommended — tools like `run_shell` execute inside the container, keeping your host machine safe.

```bash
docker build -t inkagent .

# CLI mode (default)
docker run -it --env-file .env inkagent

# Telegram bot mode
docker run --env-file .env inkagent python bot.py
```

Mount `memory/` and `conversations/` to persist data across container restarts:

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
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

```bash
source .venv/bin/activate
python main.py          # CLI mode
python bot.py           # Telegram bot (requires TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_ID in .env)
```

Note: when running locally, `run_shell` executes commands directly on your machine — use with caution.

## How It Works

```
you> remember that I prefer dark mode

agent> [calls update_user_profile] → saves to memory/USER.md
agent> [calls save_memory] → writes directly to memory/MEMORY.md
agent> Got it, noted your preference for dark mode.

you> today we discussed migrating to PostgreSQL

agent> [calls log_daily] → appends to memory/daily/2025-03-21.md
agent> Logged.

# Next day, the promotion system reviews yesterday's log
# and decides if anything is worth keeping in MEMORY.md
```

## Memory System

All memory lives in `memory/` as plain Markdown:

| File | Purpose | Updated by |
|------|---------|------------|
| `IDENTITY.md` | Agent identity metadata — name, creature, vibe, emoji, avatar | `update_identity` tool |
| `SOUL.md` | Agent behavioral rules — core truths, boundaries, tone, continuity | `update_soul` tool |
| `USER.md` | User profile — name, role, interests | `update_user_profile` tool |
| `MEMORY.md` | Long-term memory — curated facts and decisions | `save_memory` tool + automatic promotion |
| `daily/YYYY-MM-DD.md` | Daily log — ephemeral notes, one file per day | `log_daily` tool |
| `memory.db` | sqlite-vec index for semantic search over daily logs | Auto-managed |

The agent sees `IDENTITY.md`, `SOUL.md`, `USER.md`, `MEMORY.md`, and the last two days of daily logs in every conversation.

**Semantic search**: Daily log entries are automatically embedded and indexed in `memory.db` when `OPENAI_API_KEY` is set. `recall_memory` uses vector similarity for daily logs (keyword fallback without an API key). `MEMORY.md` is not searched — it's already in the system prompt.

## Architecture

```
inkagent/
├── main.py              # CLI entry point
├── bot.py               # Telegram bot entry point
├── agent/
│   ├── brain.py         # Agentic loop (provider-agnostic)
│   ├── config.py        # Shared constants (limits, timeouts)
│   ├── memory.py        # Markdown memory (read/write)
│   ├── registry.py      # Tool registration
│   ├── skill_loader.py  # Markdown skill loader
│   ├── prompts.py       # Prompt templates
│   ├── session.py       # Conversation history + persistence
│   ├── compression.py   # Context window compression
│   ├── promotion.py     # Daily log → long-term memory promotion
│   ├── scheduler.py     # Cron scheduler (asyncio + croniter)
│   ├── telegram_format.py # Markdown → Telegram HTML converter
│   ├── vector_store.py  # sqlite-vec vector store for semantic search
│   └── providers/       # Pluggable LLM providers
│       ├── base.py      # LLMProvider ABC + shared types
│       ├── anthropic.py # Anthropic (Claude)
│       └── openai.py    # OpenAI
├── tools/
│   ├── shell.py         # run_shell
│   ├── files.py         # read_file, write_file, edit_file, list_directory
│   ├── profile.py       # update_identity, update_soul, update_user_profile
│   ├── memory_skill.py  # log_daily, recall_memory, save_memory
│   ├── cron.py          # create_cron, list_crons, delete_cron
│   ├── web_search.py    # web_search (Brave Search API)
│   ├── web_fetch.py     # web_fetch (page content extraction)
│   └── gmail.py         # gmail_search, gmail_read, gmail_send, gmail_mark_read
├── skills/              # Markdown instruction skills
│   └── skill_name/
│       └── SKILL.md
└── memory/              # All memory (gitignored)
    ├── IDENTITY.md
    ├── SOUL.md
    ├── USER.md
    ├── MEMORY.md
    └── daily/
```

Key design: `brain.py` has zero knowledge of individual tools or skills. Tools register via `@registry.register(...)`, instruction skills are auto-discovered from `skills/` — adding either never touches core code.

## Built-in Tools

| Tool | Description |
|-------|-------------|
| `run_shell` | Execute shell commands (30s timeout, output capped at 3k chars) |
| `read_file` | Read a file's text content (truncated if too large) |
| `write_file` | Write content to a file, creating parent directories as needed |
| `edit_file` | Replace an exact unique string match in a file (search-and-replace) |
| `list_directory` | List files and subdirectories at a given path |
| `create_cron` | Create a scheduled task (cron expression + prompt), bound to current session |
| `list_crons` | List all scheduled tasks |
| `delete_cron` | Delete a scheduled task by ID |
| `update_identity` | Update agent identity metadata — name, creature, vibe, emoji, avatar |
| `update_soul` | Update agent behavioral rules — tone, boundaries, core truths |
| `update_user_profile` | Update user info — name, role, location, interests |
| `log_daily` | Jot a note in today's daily log; important entries auto-promote to long-term memory |
| `save_memory` | Save important info directly to long-term memory (MEMORY.md) |
| `recall_memory` | Search daily logs (semantic when available, keyword fallback) |
| `web_search` | Search the web via Brave Search API — returns title, snippet, URL |
| `web_fetch` | Fetch a URL and extract readable text content |
| `gmail_search` | Search Gmail via IMAP (supports Gmail search syntax) |
| `gmail_read` | Read full email content by UID |
| `gmail_send` | Send or reply to email via SMTP |
| `gmail_mark_read` | Mark emails as read by UID (batch support) |

## Adding a Tool

Create `tools/my_tool.py`:

```python
from agent.registry import register

@register(
    name="my_tool",
    description="What this tool does",
    input_schema={
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "..."},
        },
        "required": ["param"],
    },
)
def my_tool(param: str) -> str:
    return "result"
```

Add to `tools/__init__.py`:

```python
from tools import my_tool  # noqa: F401
```

Done. The agent picks it up automatically.

## Adding an Instruction Skill

Create `skills/my_skill/SKILL.md`:

```yaml
---
name: my_skill
description: One-line description of the workflow
---

When the user asks for X, follow these steps:
1. Use `tool_a` to ...
2. Use `tool_b` to ...
3. Format the result as ...
```

No Python, no imports. The agent sees the skill name and description in its system prompt, and loads the full instructions via `read_file` when needed.

## Configuration

All config lives in `.env` (gitignored). See [`.env.example`](.env.example) for the full list:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For Anthropic | Claude API key |
| `OPENAI_API_KEY` | For OpenAI | OpenAI API key (also enables semantic memory search when using Anthropic) |
| `LLM_PROVIDER` | No | `anthropic`, `openai`, or `openai-codex` |
| `LLM_MODEL` | No | Main model (default: `claude-sonnet-4-20250514` / `gpt-4o` / `gpt-5.4`) |
| `LLM_SMALL_MODEL` | No | Cheap model for compression/promotion (default: `claude-haiku-4-5-20251001` / `gpt-4o-mini` / `gpt-5.4-mini`) |
| `BRAVE_API_KEY` | For web search | [Brave Search API](https://brave.com/search/api/) key (free: 2000 queries/mo) |
| `GMAIL_ADDRESS` | For Gmail | Gmail address |
| `GMAIL_APP_PASSWORD` | For Gmail | [App Password](https://myaccount.google.com/apppasswords) (requires 2-Step Verification) |
| `TELEGRAM_BOT_TOKEN` | For bot | Telegram bot token from @BotFather |
| `TELEGRAM_OWNER_ID` | For bot | Your numeric Telegram user ID |
| `LANGFUSE_PUBLIC_KEY` | No | Langfuse observability |
| `LANGFUSE_SECRET_KEY` | No | Langfuse observability |
| `LANGFUSE_HOST` | No | Langfuse host URL |

## Roadmap

- [x] CLI + shell tool + Markdown memory
- [x] Langfuse observability
- [x] Telegram bot interface
- [x] Long-term memory + daily logs + auto-promotion
- [x] File operation tools (read, write, edit, list)
- [x] Scheduled tasks (cron scheduler + tools)
- [x] Web search + page fetch tools
- [x] Semantic memory search (sqlite-vec + OpenAI embeddings, graceful degradation)
- [x] Instruction skills — Markdown-based workflow definitions, separated from tools
- [x] Gmail tools (IMAP/SMTP + App Password)
- [x] Heartbeat — periodic proactive check-in (reviews `HEARTBEAT.md` checklist, alerts only when needed)


## License

MIT
