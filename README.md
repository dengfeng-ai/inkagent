<p align="right">
  <b>English</b> &nbsp;·&nbsp; <a href="README_zh.md">中文</a>
</p>

<p align="center">
  <img src="assets/logo.svg" width="360" alt="inkagent"/>
</p>

<p align="center">
  <b>A lightweight personal AI agent that runs locally, powered by Markdown memory.</b>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=flat" alt="License"></a>
  <img src="https://img.shields.io/badge/Python-%E2%89%A53.11-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Docker-lightgrey?style=flat" alt="Platform">
  <img src="https://img.shields.io/badge/LLM-Claude%20%7C%20OpenAI%20%7C%20ChatGPT-green?style=flat" alt="LLM Providers">
</p>

<p align="center">
  <a href="docs/guide-en.md">User Guide</a> &nbsp;&middot;&nbsp;
  <a href="#features">Features</a> &nbsp;&middot;&nbsp;
  <a href="#quick-start">Quick Start</a> &nbsp;&middot;&nbsp;
  <a href="#architecture">Architecture</a> &nbsp;&middot;&nbsp;
  <a href="#roadmap">Roadmap</a>
</p>


## Features

- **Agentic tool-use loop** — sends your message to the LLM, executes tools, feeds results back, repeats until done
- **Markdown memory** — persona, user profile, long-term memory, daily logs — all plain `.md` files you can read and edit
- **Auto memory promotion** — daily logs are curated into long-term memory overnight via a small model
- **Memory search** — daily logs indexed with sqlite-vec for vector search (requires OpenAI API key for embeddings, falls back to keyword search)
- **Multi-provider** — supports Anthropic (Claude), OpenAI, and ChatGPT subscription (Codex OAuth), switchable via env var
- **Self-registering tools** — shell, file ops, web search, Gmail, cron, and more
- **Instruction skills** — teach the agent new workflows with just a Markdown file, no code needed
- **Scheduled tasks & heartbeat** — cron-based scheduler for proactive notifications; heartbeat mode for silent background checks
- **Autopilot** — autonomous task queue; agent picks, executes, and archives tasks on each heartbeat cycle
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
  -v $(pwd)/user_skills:/app/user_skills \
  inkagent
```

To run the Telegram bot:

```bash
docker run -it --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  -v $(pwd)/user_skills:/app/user_skills \
  inkagent python -m inkagent.bot
```

### Local

Requires **Python 3.11+**.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python -m inkagent

# Run Telegram bot
python -m inkagent.bot
```

For Telegram bot, provider options, Gmail, web search, scheduled tasks, and more — see the [User Guide](docs/guide-en.md).

## Architecture

```
project root/
├── inkagent/            # Python package
│   ├── cli.py           # CLI entry point
│   ├── bot.py           # Telegram bot entry point
│   ├── brain.py         # Agentic loop (provider-agnostic)
│   ├── config.py        # Shared constants
│   ├── memory.py        # Markdown memory (read/write)
│   ├── providers/       # Pluggable LLM providers
│   └── tools/           # Self-registering Python tools
├── skills/              # Built-in instruction skills (git-tracked)
├── user_skills/         # User skill overrides (gitignored)
├── memory/              # All memory (gitignored)
└── pyproject.toml       # Package metadata + dependencies
```

Key design: `brain.py` has zero knowledge of individual tools or skills. Tools register via `@registry.register(...)`, instruction skills are auto-discovered from `skills/` and `user_skills/` — adding either never touches core code. User skills in `user_skills/` override built-in ones with the same name, so upgrades via `git pull` never conflict with customizations.

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
- [x] Autopilot — autonomous task queue with auto-archiving
- [ ] Publish to PyPI

## License

MIT
