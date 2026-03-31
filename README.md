# inkagent

A lightweight personal AI agent that runs locally on your machine. Powered by Claude or OpenAI, driven by Markdown memory.

Inspired by [OpenClaw](https://github.com/nichochar/open-claw). Built in Python.

## Documentation

- [User Guide (English)](docs/guide-en.md)
- [用户手册 (中文)](docs/guide-zh.md)

## Features

- **Agentic tool-use loop** — sends your message to the LLM, executes tools, feeds results back, repeats until done
- **Markdown memory** — persona, user profile, long-term memory, daily logs — all plain `.md` files you can read and edit
- **Auto memory promotion** — daily logs are curated into long-term memory overnight via a small model
- **Memory search** — daily logs indexed with sqlite-vec for vector search (requires OpenAI API key for embeddings, falls back to keyword search)
- **Multi-provider** — supports Anthropic (Claude), OpenAI, and ChatGPT subscription (Codex OAuth), switchable via env var
- **Self-registering tools** — shell, file ops, web search, Gmail, cron, and more
- **Instruction skills** — teach the agent new workflows with just a Markdown file, no code needed
- **Scheduled tasks & heartbeat** — cron-based scheduler for proactive notifications; heartbeat mode for silent background checks
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
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### Docker (recommended)

```bash
docker build -t inkagent .

docker run -it --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  -v $(pwd)/skills:/app/skills \
  inkagent
```

### Local

Requires **Python 3.11+**.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

For Telegram bot, provider options, Gmail, web search, scheduled tasks, and more — see the [User Guide](docs/guide-en.md).

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
│   ├── vector_store.py  # sqlite-vec vector store for memory search
│   └── providers/       # Pluggable LLM providers
│       ├── base.py      # LLMProvider ABC + shared types
│       ├── anthropic.py # Anthropic (Claude)
│       ├── openai.py    # OpenAI
│       └── openai_codex.py # OpenAI Codex (ChatGPT subscription)
├── tools/               # Self-registering Python tools
├── skills/              # Markdown instruction skills
└── memory/              # All memory (gitignored)
```

Key design: `brain.py` has zero knowledge of individual tools or skills. Tools register via `@registry.register(...)`, instruction skills are auto-discovered from `skills/` — adding either never touches core code.

## Roadmap

- [x] CLI + shell tool + Markdown memory
- [x] Langfuse observability
- [x] Telegram bot interface
- [x] Long-term memory + daily logs + auto-promotion
- [x] File operation tools (read, write, edit, list)
- [x] Scheduled tasks (cron scheduler + tools)
- [x] Web search + page fetch tools
- [x] Memory search (sqlite-vec + OpenAI embeddings, graceful degradation)
- [x] Instruction skills — Markdown-based workflow definitions, separated from tools
- [x] Gmail tools (IMAP/SMTP + App Password)
- [x] Heartbeat — periodic proactive check-in (reviews `HEARTBEAT.md` checklist, alerts only when needed)

## License

MIT
