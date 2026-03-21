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
export ANTHROPIC_API_KEY="your-key"
```

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
    ├── profile.md       # Persistent user profile (LLM-maintained)
    └── history.md       # Rolling conversation history (last 20 turns)
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
| `update_profile` | Rewrite the user profile in memory |

## Roadmap

- [x] CLI + shell skill + Markdown memory
- [ ] Telegram bot interface
- [ ] Scheduled tasks / daily briefing
- [ ] Web search skill
- [ ] Gmail / Google Calendar skills
