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
  <a href="#why-inkagent">Why inkagent?</a> &nbsp;&middot;&nbsp;
  <a href="#choose-your-setup">Setup</a> &nbsp;&middot;&nbsp;
  <a href="#quick-start">Quick Start</a> &nbsp;&middot;&nbsp;
  <a href="#roadmap">Roadmap</a>
</p>


## Why inkagent?

- **Runs locally** — your data stays on your machine, not in someone else's cloud
- **Markdown memory** — persona, user profile, long-term memory, daily logs — all plain `.md` files you own and can read
- **Grows with you** — start with a CLI chat, add Telegram, web search, Gmail, scheduled tasks as you need them
- **Multi-provider** — Claude, OpenAI, or ChatGPT subscription (no API key needed), switchable via one env var
- **Extensible** — teach the agent new workflows with a Markdown file, no code needed

## Choose Your Setup

Start simple, add capabilities as you need them. Each level builds on the previous one.

| Level | What You Get | What to Configure | Guide |
|-------|-------------|-------------------|-------|
| **Start here** | CLI chat with AI | One API key | [Quick Start](#quick-start) |
| **Mobile access** | Chat via Telegram on your phone | + Telegram bot token | [Telegram](docs/guide-en.md#4-telegram-bot) |
| **Web-connected** | Agent can search the internet | + Brave API key | [Web Search](docs/guide-en.md#5-web-search) |
| **Email assistant** | Agent reads and sends Gmail | + Gmail App Password | [Gmail](docs/guide-en.md#6-gmail-integration) |
| **Proactive assistant** | Scheduled tasks, background checks, auto-pilot | Telegram + heartbeat setup | [Scheduled Tasks](docs/guide-en.md#7-scheduled-tasks--heartbeat) |
| **Better memory** | Semantic search over past conversations | + OpenAI API key (for embeddings) | [Memory Search](docs/guide-en.md#3-memory-system) |

> **No API key?** Use `LLM_PROVIDER=openai-codex` to run on your ChatGPT Plus/Pro subscription. See the [Provider Guide](docs/guide-en.md#2-choosing-an-llm-provider).

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

## How It Works

inkagent is an agentic loop: you send a message → the LLM decides which tools to call → tools execute → results go back to the LLM → repeat until done. All memory is stored as Markdown files in `memory/` that you can read anytime.

For architecture details and development info, see [CLAUDE.md](CLAUDE.md).

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
