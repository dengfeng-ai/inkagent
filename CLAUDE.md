# inkagent

A lightweight personal AI agent that runs locally, powered by Claude, OpenAI, or ChatGPT subscription (via Codex OAuth) and driven by Markdown memory.
Inspired by OpenClaw. Built in Python.

## Architecture

```
inkagent/
├── main.py              # CLI entry point
├── bot.py               # Telegram bot entry point
├── agent/
│   ├── brain.py         # LLM agentic loop (tool_use) — provider-agnostic
│   ├── config.py        # Shared constants (token limits, timeouts, caps)
│   ├── memory.py        # Markdown-based memory (read/write)
│   ├── registry.py      # Tool registration system (Python tools)
│   ├── skill_loader.py  # Markdown skill loader (instruction skills)
│   ├── prompts.py       # Prompt templates (system, promotion, summary)
│   ├── session.py       # Conversation history management + JSON persistence
│   ├── compression.py   # Context window estimation + small-model summarization
│   ├── promotion.py     # Daily log → MEMORY.md promotion via LLM
│   ├── scheduler.py     # Cron scheduler (asyncio loop + croniter)
│   ├── telegram_format.py # Markdown → Telegram HTML converter
│   ├── vector_store.py  # sqlite-vec vector store for semantic search over daily logs
│   ├── codex_auth.py    # OAuth 2.0 + PKCE auth for OpenAI Codex (ChatGPT subscription)
│   └── providers/       # Pluggable LLM provider abstraction
│       ├── __init__.py  # Factory: get_provider(), get_model(), get_small_model()
│       ├── base.py      # LLMProvider ABC + LLMResponse/ToolCall/LLMError types
│       ├── anthropic.py # Anthropic (Claude) provider
│       ├── openai.py    # OpenAI provider
│       └── openai_codex.py # OpenAI Codex provider (ChatGPT subscription via OAuth)
├── skills/
│   ├── __init__.py      # Auto-imports all tool skills
│   ├── shell.py         # run_shell tool
│   ├── files.py         # read_file, write_file, edit_file, list_directory tools (write/edit block .db files)
│   ├── profile.py       # update_identity + update_soul + update_user_profile tools
│   ├── memory_skill.py  # recall_memory, log_daily, save_memory tools
│   ├── cron.py          # create_cron, list_crons, delete_cron tools
│   ├── web_search.py    # web_search tool (Brave Search API)
│   ├── web_fetch.py     # web_fetch tool (HTTP + trafilatura)
│   ├── gmail.py         # gmail_search, gmail_read, gmail_send tools (Gmail API)
│   └── instructions/    # Markdown instruction skills (no code needed)
│       └── skill_name/  # One directory per skill
│           └── SKILL.md # YAML frontmatter + Markdown body
└── memory/
    ├── IDENTITY.md      # Agent identity metadata (name, creature, vibe, emoji, avatar)
    ├── SOUL.md          # Agent behavioral rules (core truths, boundaries, tone, continuity)
    ├── USER.md          # User personal info (name, role, interests)
    ├── MEMORY.md        # Long-term memory (curated, durable)
    └── daily/           # Daily logs (ephemeral, append-only)
        └── YYYY-MM-DD.md
```

Key design principle: `brain.py` has zero knowledge of individual tools or skills.
Tools register themselves via `@registry.register(...)` — adding a tool never touches core code.
Instruction skills are auto-discovered from `skills/instructions/` — adding a skill is just creating a Markdown file.

## Tech Stack

- Python 3.11+
- `anthropic` SDK + `openai` SDK — pluggable via `agent/providers/`
- Markdown files — all memory storage
- `sqlite-vec` — vector storage for semantic search over daily logs (`memory/vectors.db`)
- `python-telegram-bot` — Telegram bot interface (`bot.py`)
- `httpx` — HTTP client for web search and fetch
- `trafilatura` — HTML content extraction for `web_fetch`
- `PyYAML` — YAML frontmatter parsing for instruction skills
- `croniter` — Cron expression parsing for scheduled tasks
- `langfuse` — Optional observability tracing for LLM calls and tool executions

## Common Commands

```bash
# Run the CLI (default: Anthropic Claude)
python main.py

# Run with OpenAI API
LLM_PROVIDER=openai LLM_MODEL=gpt-4o python main.py

# Run with ChatGPT subscription (Codex OAuth — no API key needed)
python -m agent.codex_auth              # one-time login via browser
LLM_PROVIDER=openai-codex LLM_MODEL=codex-mini-latest python main.py

# Run the Telegram bot
python bot.py

# Install dependencies
pip install -r requirements.txt

# View memory
cat memory/IDENTITY.md
cat memory/SOUL.md
cat memory/USER.md
```

### Provider Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `openai`, or `openai-codex` |
| `LLM_MODEL` | per-provider | Main model (e.g. `claude-sonnet-4-20250514`, `gpt-4o`) |
| `LLM_SMALL_MODEL` | per-provider | Cheap model for compression/promotion (e.g. `claude-haiku-4-5-20251001`, `gpt-4o-mini`) |
| `BRAVE_API_KEY` | — | Brave Search API key (required for `web_search` tool) |
| `GMAIL_ADDRESS` | — | Gmail address (required for Gmail tools) |
| `GMAIL_APP_PASSWORD` | — | Gmail App Password (required for Gmail tools, generate at myaccount.google.com/apppasswords) |

## Memory System

Four-tier Markdown memory in `memory/`:

- **`IDENTITY.md`** — Agent identity metadata (name, creature type, vibe, emoji, avatar). Injected into the system prompt. Updated by the LLM via `update_identity` tool when the user sets the agent's name, emoji, or avatar.
- **`SOUL.md`** — Agent behavioral rules (core truths, boundaries, tone, continuity). Injected into the system prompt instruction area. Updated by the LLM via `update_soul` tool when the user sets behavior rules (tone, language, boundaries).
- **`USER.md`** — User profile. Injected into the system prompt context area. Updated by the LLM via `update_user_profile` tool when it learns personal info (name, role, location, interests).
- **`MEMORY.md`** — Long-term curated memory. Injected into system prompt. Writable via `save_memory` tool (for explicit "remember this" requests) and via the automatic promotion system.
- **`daily/YYYY-MM-DD.md`** — Daily logs. Append-only, one file per day. Today's + yesterday's logs injected into system prompt. Updated via `log_daily` tool for transient notes (decisions, topics, action items). Each entry is also indexed into the vector store for semantic search.
- **`vectors.db`** — sqlite-vec database for semantic search over daily logs. Auto-created when an embedding provider is available. Not required — system degrades to keyword search without it.

**Vector search**: `recall_memory` uses semantic search (sqlite-vec + OpenAI embeddings) for daily logs when `OPENAI_API_KEY` is set. Falls back to keyword search otherwise. MEMORY.md is not searched by `recall_memory` — it's already injected into the system prompt, so the LLM can see it directly.

**Memory promotion**: On the first conversation turn each day, the system checks if yesterday's daily log exists and hasn't been promoted. If so, it sends the log + current MEMORY.md to the small model (`LLM_SMALL_MODEL`), which decides what's worth keeping long-term. Promoted entries are appended to MEMORY.md; the daily log is marked `<!-- promoted -->` to prevent re-processing.

Conversation history is kept in-memory for the current session, auto-saved to `conversations/` as JSON.
The `memory/` directory is gitignored — never commit it.

## Scheduler (Cron)

`agent/scheduler.py` provides a cron-based task scheduler. Jobs are persisted in `memory/crons.json`.

- The scheduler runs as an asyncio background task, checking every 60 seconds
- When a job fires, it calls `run_agent(prompt, session_id)` with a fresh session (timestamped session ID) and delivers the reply via a callback
- In Telegram bot mode (`bot.py`), the scheduler starts automatically and sends replies to the bound chat
- In CLI mode, the scheduler does not run (no persistent event loop), but cron tools still work — jobs created in CLI take effect when the bot starts
- Jobs are bound to a `session_id` (e.g. `tg_123456`) at creation time via `session.current_session_id`
- **Timezone-aware**: each job stores an IANA timezone (default: `Asia/Shanghai`). Cron expressions are interpreted in the job's timezone, so "0 9 * * *" means 9 AM local time
- Uses `croniter` for cron expression parsing, no heavy scheduler framework
- **Heartbeat mode**: Jobs with `silent_ok: true` suppress notification when the agent replies with exactly `HEARTBEAT_OK`. This enables periodic checks that only notify when something needs attention.

### Heartbeat

Heartbeat is a special use of the cron system for periodic background checks (email, calendar, etc.) that only notify the user when something needs attention. Implemented as:

- **`memory/HEARTBEAT.md`** — User-editable checklist of things to check periodically
- **`skills/instructions/heartbeat/SKILL.md`** — Instruction skill teaching the agent the heartbeat workflow
- **`silent_ok` flag on cron jobs** — When set, replies of `HEARTBEAT_OK` are swallowed silently

Setup: create a cron job with `silent_ok=true` whose prompt tells the agent to run the heartbeat skill. The agent reads the checklist, runs the checks, and either reports findings or replies `HEARTBEAT_OK` to stay silent.

## Session Control Commands

User-facing commands handled locally (not sent to the LLM):

- `/new` — archive current conversation and start a fresh session
- `/compact` — force-compress conversation history (summarize old messages, keep recent ones)

In Telegram, these are native bot commands (`CommandHandler`). In CLI, they are intercepted in the input loop.
Implementation: `session.reset_conversation()` for `/new`, `compression.force_compress()` for `/compact`.

## Skill System

Two types of skills, separated by design:

### Tools (Python functions)

Each tool is a Python function decorated with `@registry.register(...)`.
The decorator takes `name`, `description`, and `input_schema` (JSON Schema format for Claude tool_use).

To add a new tool:
1. Create `skills/your_tool.py`
2. Import `register` from `agent.registry`
3. Decorate your function with `@register(...)`
4. Add `from skills import your_tool` in `skills/__init__.py`

Built-in tools:
- `run_shell` — executes shell commands, 30s timeout, output capped at 3000 chars
- `update_identity` — rewrites `memory/IDENTITY.md` with agent identity metadata (name, creature, vibe, emoji, avatar)
- `update_soul` — rewrites `memory/SOUL.md` with agent behavioral rules (tone, boundaries, core truths)
- `update_user_profile` — rewrites `memory/USER.md` with user personal info
- `recall_memory` — semantic search over daily logs (via sqlite-vec, when OpenAI embedding available); falls back to keyword search. Only searches daily logs — MEMORY.md is already in the system prompt
- `log_daily` — appends a note to today's daily log (`memory/daily/YYYY-MM-DD.md`); important entries are auto-promoted to MEMORY.md overnight
- `save_memory` — saves important information directly to long-term memory (`MEMORY.md`); use for explicit "remember this" requests
- `read_file` — reads a file's text content (truncated at `TOOL_OUTPUT_CAP` chars)
- `write_file` — writes content to a file, creating parent directories as needed
- `edit_file` — replaces an exact unique string match in a file (search-and-replace)
- `list_directory` — lists files and subdirectories at a given path
- `create_cron` — creates a scheduled task with a cron expression + prompt; binds to the current session. Supports `silent_ok` flag for heartbeat-style jobs (suppresses notification when agent replies `HEARTBEAT_OK`)
- `list_crons` — lists all scheduled tasks
- `delete_cron` — deletes a scheduled task by ID
- `web_search` — searches the web via Brave Search API, returns title + snippet + URL list
- `web_fetch` — fetches a URL and extracts readable text content via `trafilatura`
- `gmail_search` — searches Gmail via IMAP, returns sender/subject/date list (IMAP search syntax)
- `gmail_read` — reads full email content by UID (includes attachments list, Message-ID for replies)
- `gmail_send` — sends or replies to email via SMTP (supports In-Reply-To threading)
- `gmail_mark_read` — marks one or more emails as read by UID (batch support)

### Instruction Skills (Markdown files)

Instruction skills are pure Markdown files in `skills/instructions/` that teach the LLM workflows without writing Python code. They guide the LLM on *when and how* to combine existing tools for specific tasks.

File format — YAML frontmatter + Markdown body:
```yaml
---
name: skill_name
description: One-line description shown in the system prompt
requires:            # optional eligibility gating
  env: [API_KEY]     # skip if env var missing
  bins: [ffmpeg]     # skip if binary not on PATH
---

Instructions for the LLM describing the workflow…
```

To add a new instruction skill: create a directory in `skills/instructions/` with a `SKILL.md` file (e.g. `skills/instructions/daily_report/SKILL.md`). No Python, no imports. The skill loader (`agent/skill_loader.py`) discovers it automatically.

- Only skill meta (name, description, path) is injected into the system prompt — the LLM uses `read_file` to load full instructions on demand
- Skills with unmet `requires` are silently skipped

## Agentic Loop

`brain.py` runs a provider-agnostic tool_use loop:
1. Build system prompt (instructions + IDENTITY.md + SOUL.md + USER.md + MEMORY.md + daily logs + instruction skills) + conversation messages
2. Call LLM via `provider.complete()` with all registered tools (auto-formatted per provider)
3. If `stop_reason == "tool_use"`: execute tools, append results via `provider.tool_results_messages()`, loop
4. If `stop_reason == "end_turn"`: extract text, append to in-memory conversation, return

No recursion limit is set — rely on the LLM's natural termination behavior.

## Provider System

`agent/providers/` contains a pluggable abstraction layer. `LLMProvider` (ABC) defines the interface:
- `complete()` — full completion with tool support, returns `LLMResponse`
- `simple_complete()` — text-only completion (used by compression/promotion)
- `format_tools()` — converts registry tool schemas to provider-native format
- `assistant_message()` / `tool_results_messages()` — builds provider-native message dicts for the agentic loop

`brain.py` has zero knowledge of specific providers. Adding a new provider means implementing `LLMProvider` and registering it in `providers/__init__.py`.
IMPORTANT: Never import `anthropic` or `openai` directly in `brain.py` — always go through `providers`.

### OpenAI Codex Provider

The `openai-codex` provider allows running inkagent using a **ChatGPT Plus/Pro subscription** instead of paying for API credits. It uses OAuth 2.0 + PKCE to authenticate against OpenAI's Codex endpoint.

- **Auth module**: `agent/codex_auth.py` — handles OAuth login, token storage (`~/.inkagent/codex-auth.json`), and automatic refresh
- **API endpoint**: `https://chatgpt.com/backend-api/codex/responses` (Responses API format, not Chat Completions)
- **Login**: `python -m agent.codex_auth` opens a browser for one-time OAuth consent
- **No API key needed** — authentication uses the ChatGPT subscription session
- **Limitations**: subject to ChatGPT subscription usage quotas; no embeddings (vector search still needs `OPENAI_API_KEY`)

## Code Style

- Type hints on all function signatures
- No global state except `registry` singleton and provider singleton; module-level state is scoped to `session.py`, `compression.py`, `promotion.py`, `scheduler.py`, `vector_store.py`, `codex_auth.py`, and `providers/__init__.py`. Shared constants live in `agent/config.py`
- Cap tool output at `TOOL_OUTPUT_CAP` chars (see `agent/config.py`) before returning to avoid context explosion
- IMPORTANT: Never import individual tool modules in `brain.py` — only import the `skills` package which auto-registers all tools
- IMPORTANT: Never import `anthropic` or `openai` directly in `brain.py` — always go through `providers`

## Roadmap (in order)

1. ~~CLI + shell tool + Markdown memory~~ (Phase 1)
2. ~~Telegram bot interface~~ — `bot.py`, owner-only, typing indicator
3. ~~Scheduled tasks~~ — cron scheduler (`croniter` + asyncio), `create_cron` / `list_crons` / `delete_cron` tools
4. ~~Web search tool~~ — `web_search` (Brave) + `web_fetch` (trafilatura)
5. ~~Gmail~~ — `gmail_search`, `gmail_read`, `gmail_send` tools (IMAP/SMTP + App Password)
