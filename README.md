# inkagent

A lightweight personal AI agent that runs locally, powered by Claude and driven by Markdown memory.

Inspired by [OpenClaw](https://github.com/nichochar/open-claw). Built in Python.

## How it works

inkagent runs an agentic tool-use loop: it sends your message to Claude, executes any tools Claude requests (shell commands, memory updates, etc.), feeds the results back, and repeats until Claude produces a final response. All memory is stored as plain Markdown files — no database required.

Skills are self-registering. Adding a new capability is just writing a decorated Python function — the core loop never needs to change.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
```

All config lives in `.env` (gitignored). See `.env.example` for the full list of variables.

### Observability (Langfuse)

All LLM calls and tool executions are traced via [Langfuse](https://langfuse.com). Add your Langfuse keys to `.env` to enable it. Each user request creates a trace containing nested spans for every Claude API call (with token usage) and tool execution.

If the Langfuse variables are not set, tracing is a no-op — the agent runs normally.

## Usage

```bash
python main.py
```

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
    └── USER.md          # User personal info (name, role, interests)
```

## Adding a skill

1. Create `skills/your_skill.py`
2. Decorate your function with `@registry.register(name, description, input_schema)`
3. Import it in `skills/__init__.py`

The agentic loop picks it up automatically.

## Built-in skills

| Skill | Description |
|-------|-------------|
| `run_shell` | Execute shell commands (30s timeout, output capped at 3k chars) |
| `update_soul` | Update agent persona — name, tone, language, behavior rules |
| `update_user_profile` | Update user info — name, role, location, interests |

## Roadmap

- [x] CLI + shell skill + Markdown memory
- [x] Langfuse observability
- [ ] Telegram bot interface
- [ ] Scheduled tasks / daily briefing
- [ ] Web search skill
- [ ] Gmail / Google Calendar skills
