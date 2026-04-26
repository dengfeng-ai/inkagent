# inkagent

A lightweight personal AI agent that runs locally, powered by Claude, OpenAI, or ChatGPT subscription (via Codex OAuth) and driven by Markdown memory.
Inspired by OpenClaw. Built in Python.

## Architecture

```
project root/
├── inkagent/                # Python package
│   ├── __init__.py
│   ├── __main__.py          # python -m inkagent
│   ├── cli.py               # CLI entry point
│   ├── bot.py               # Telegram bot entry point
│   ├── brain.py             # LLM agentic loop (tool_use) — provider-agnostic
│   ├── config.py            # Shared constants (token limits, timeouts, caps)
│   ├── memory.py            # Markdown-based memory (read/write)
│   ├── registry.py          # Tool registration system (Python tools)
│   ├── skill_loader.py      # Markdown skill loader
│   ├── prompts.py           # Prompt templates (system, promotion, summary)
│   ├── session.py           # Conversation history management + JSON persistence
│   ├── compression.py       # Context window estimation + small-model summarization
│   ├── promotion.py         # Daily log → MEMORY.md promotion via LLM
│   ├── scheduler.py         # Cron scheduler (asyncio loop + croniter)
│   ├── telegram_format.py   # Markdown → Telegram HTML converter
│   ├── vector_store.py      # sqlite-vec vector store for semantic search over daily logs
│   ├── codex_auth.py        # OAuth 2.0 + PKCE auth for OpenAI Codex (ChatGPT subscription)
│   ├── tracing/             # Optional Langfuse tracing (no-op when not configured)
│   │   └── __init__.py      # track decorator + update_current_span/generation + flush
│   ├── providers/           # Pluggable LLM provider abstraction
│   │   ├── __init__.py      # Factory: get_provider(), get_model(), get_small_model()
│   │   ├── base.py          # LLMProvider ABC + LLMResponse/ToolCall/LLMError types
│   │   ├── anthropic.py     # Anthropic (Claude) provider
│   │   ├── openai.py        # OpenAI provider
│   │   └── openai_codex.py  # OpenAI Codex provider (ChatGPT subscription via OAuth)
│   └── tools/               # Self-registering Python tools
│       ├── __init__.py      # Auto-imports all tools so they self-register
│       ├── shell.py         # run_shell tool
│       ├── files.py         # read_file, write_file, edit_file, list_directory tools
│       ├── profile.py       # update_identity + update_soul + update_user_profile tools
│       ├── memory_skill.py  # recall_memory, log_daily, save_memory tools
│       ├── cron.py          # create_cron, list_crons, delete_cron tools
│       ├── web_search.py    # web_search tool (Brave Search API)
│       ├── web_fetch.py     # web_fetch tool (HTTP + trafilatura)
│       └── gmail.py         # gmail_search, gmail_read, gmail_send tools (Gmail API)
├── skills/                  # Instruction skills (git-tracked, user-edited)
│   └── skill_name/
│       └── SKILL.md
├── config/                  # Agent behavior config (git-tracked, user-edited)
│   └── AGENTS.md
├── memory/                  # All memory (gitignored)
│   ├── IDENTITY.md
│   ├── SOUL.md
│   ├── USER.md
│   ├── MEMORY.md
│   ├── HEARTBEAT.md
│   └── daily/
│       └── YYYY-MM-DD.md
├── pyproject.toml           # Package metadata + dependencies
└── Dockerfile
```

Key design principle: `brain.py` has zero knowledge of individual tools or skills.
Tools register themselves via `@registry.register(...)` — adding a tool never touches core code.
Instruction skills are auto-discovered from `skills/` — adding a skill is just creating a Markdown directory with a `SKILL.md` file.

## Tech Stack

- Python 3.11+
- `anthropic` SDK + `openai` SDK — pluggable via `inkagent/providers/`
- Markdown files — all memory storage
- `sqlite-vec` — vector storage for semantic search over daily logs (`memory/memory.db`)
- `python-telegram-bot` — Telegram bot interface (`inkagent/bot.py`)
- `httpx` — HTTP client for web search and fetch
- `trafilatura` — HTML content extraction for `web_fetch`
- `PyYAML` — YAML frontmatter parsing for instruction skills
- `croniter` — Cron expression parsing for scheduled tasks
- `langfuse` — Optional observability tracing for LLM calls and tool executions (no-op when not installed/configured)

## Common Commands

```bash
# Install (editable mode for development)
pip install -e .

# Install with optional Langfuse tracing
pip install -e ".[langfuse]"

# Run the CLI (default: Anthropic Claude)
python -m inkagent
# or: inkagent

# Run the Telegram bot
python -m inkagent.bot
# or: inkagent-bot

# Run with ChatGPT subscription (Codex OAuth — no API key needed)
python -m inkagent.codex_auth           # one-time login via browser

# View memory
cat memory/IDENTITY.md
cat memory/SOUL.md
cat memory/USER.md
```

### Provider Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `openai`, or `openai-codex` |
| `LLM_MODEL` | per-provider | Main model (e.g. `claude-opus-4-6`, `gpt-5.4`) |
| `LLM_SMALL_MODEL` | per-provider | Cheap model for compression/promotion (e.g. `claude-sonnet-4-6`, `gpt-5.4-mini`) |
| `LANGFUSE_PUBLIC_KEY` | — | Enables Langfuse tracing when set (also needs `LANGFUSE_SECRET_KEY`). Requires `pip install -e ".[langfuse]"`. No-op when unset. |
| `BRAVE_API_KEY` | — | Brave Search API key (required for `web_search` tool) |
| `GMAIL_ADDRESS` | — | Gmail address (required for Gmail tools) |
| `GMAIL_APP_PASSWORD` | — | Gmail App Password (required for Gmail tools, generate at myaccount.google.com/apppasswords) |

## Memory System

Markdown memory files in `memory/`, injected as bootstrap context into the system prompt on every turn:

- **`config/AGENTS.md`** — Agent behavior rules and working guidelines (profile rules, memory rules, file safety rules, email rules). Injected into the system prompt `<instructions>` block. Git-tracked — edit directly to customize how the agent operates.
- **`IDENTITY.md`** — Agent identity metadata (name, creature type, vibe, emoji, avatar). Injected into the system prompt. Updated by the LLM via `update_identity` tool when the user sets the agent's name, emoji, or avatar.
- **`SOUL.md`** — Agent behavioral rules (core truths, boundaries, tone, continuity). Injected into the system prompt instruction area. Updated by the LLM via `update_soul` tool when the user sets behavior rules (tone, language, boundaries).
- **`USER.md`** — User profile. Injected into the system prompt context area. Updated by the LLM via `update_user_profile` tool when it learns personal info (name, role, location, interests).
- **`MEMORY.md`** — Long-term curated memory. Injected into system prompt. Auto-seeded with a `# MEMORY.md` header template on first access. Writable via `save_memory` tool (for explicit "remember this" requests) and via the automatic promotion system.
- **`daily/YYYY-MM-DD.md`** — Daily logs. Append-only, one file per day. Today's + yesterday's logs injected into system prompt. Updated via `log_daily` tool for transient notes (decisions, topics, action items). Each entry is also indexed into the vector store for semantic search.
- **`memory.db`** — sqlite-vec database for semantic search over daily logs. Auto-created when an embedding provider is available. Not required — system degrades to keyword search without it.

**Vector search**: `recall_memory` uses semantic search (sqlite-vec + OpenAI embeddings) for daily logs when `OPENAI_API_KEY` is set. Falls back to keyword search otherwise. MEMORY.md is not searched by `recall_memory` — it's already injected into the system prompt, so the LLM can see it directly.

**Memory promotion**: On the first conversation turn each day, the system checks if yesterday's daily log exists and hasn't been promoted. If so, it sends the log + current MEMORY.md to the small model (`LLM_SMALL_MODEL`), which decides what's worth keeping long-term. Promoted entries are appended to MEMORY.md; the daily log is marked `<!-- promoted -->` to prevent re-processing.

Conversation history is kept in-memory for the current session, auto-saved to `conversations/` as JSON.
The `memory/` directory is gitignored — never commit it.

## Scheduler (Cron)

`inkagent/scheduler.py` provides a cron-based task scheduler. Jobs are persisted in `memory/crons.json`.

- The scheduler runs as an asyncio background task, checking every 60 seconds
- When a job fires, it calls `run_agent(prompt, session_id)` with a fresh session (timestamped session ID) and delivers the reply via a callback
- In Telegram bot mode (`inkagent/bot.py`), the scheduler starts automatically and sends replies to the bound chat
- In CLI mode, the scheduler does not run (no persistent event loop), but cron tools still work — jobs created in CLI take effect when the bot starts
- Jobs are bound to a `session_id` (e.g. `tg_123456`) at creation time via `session.current_session_id`
- **Timezone-aware**: each job stores an IANA timezone (default: `Asia/Shanghai`). Cron expressions are interpreted in the job's timezone, so "0 9 * * *" means 9 AM local time
- Uses `croniter` for cron expression parsing, no heavy scheduler framework
- **Heartbeat mode**: Jobs with `silent_ok: true` suppress notification when the agent replies with exactly `HEARTBEAT_OK`. This enables periodic checks that only notify when something needs attention.

### Heartbeat

Heartbeat is a special use of the cron system for periodic background checks (email, calendar, etc.) that only notify the user when something needs attention. Implemented as:

- **`memory/HEARTBEAT.md`** — Checklist of things to check periodically. User- and agent-editable (agent can add/remove items on request via `write_file`/`edit_file`)
- **`skills/heartbeat/SKILL.md`** — Instruction skill teaching the agent the heartbeat workflow
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
1. Create `inkagent/tools/your_tool.py`
2. Import `register` from `inkagent.registry`
3. Decorate your function with `@register(...)`
4. Add `from inkagent.tools import your_tool` in `inkagent/tools/__init__.py`

Built-in tools:
- `run_shell` — executes shell commands, 30s timeout, output capped at 3000 chars
- `update_identity` — rewrites `memory/IDENTITY.md` with agent identity metadata (name, creature, vibe, emoji, avatar)
- `update_soul` — rewrites `memory/SOUL.md` with agent behavioral rules (tone, boundaries, core truths)
- `update_user_profile` — rewrites `memory/USER.md` with user personal info
- `recall_memory` — semantic search over daily logs (via sqlite-vec, when OpenAI embedding available); falls back to keyword search. Only searches daily logs — MEMORY.md is already in the system prompt
- `log_daily` — appends a note to today's daily log (`memory/daily/YYYY-MM-DD.md`); important entries are auto-promoted to MEMORY.md overnight
- `save_memory` — saves important information directly to long-term memory (`MEMORY.md`); use for explicit "remember this" requests
- `read_file` — reads a file's text content (truncated at `TOOL_OUTPUT_CAP` chars)
- `write_file` — writes content to a file, creating parent directories as needed. Within the project, writes are restricted to `memory/` and `conversations/`; files outside the project are unrestricted
- `edit_file` — replaces an exact unique string match in a file (search-and-replace). Same write restrictions as `write_file`
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

Instruction skills are pure Markdown files that teach the LLM workflows without writing Python code. They guide the LLM on *when and how* to combine existing tools for specific tasks.

`skill_loader.py` scans `skills/` for subdirectories containing a `SKILL.md` file. The agent does not modify skills — edit them directly in your editor.

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

To add a new skill, create a directory under `skills/` with a `SKILL.md` file. No Python, no imports. The skill loader discovers it automatically.

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

`inkagent/providers/` contains a pluggable abstraction layer. `LLMProvider` (ABC) defines the interface:
- `complete()` — full completion with tool support, returns `LLMResponse`
- `simple_complete()` — text-only completion (used by compression/promotion)
- `format_tools()` — converts registry tool schemas to provider-native format
- `assistant_message()` / `tool_results_messages()` — builds provider-native message dicts for the agentic loop

`brain.py` has zero knowledge of specific providers. Adding a new provider means implementing `LLMProvider` and registering it in `providers/__init__.py`.
IMPORTANT: Never import `anthropic` or `openai` directly in `brain.py` — always go through `providers`.

### OpenAI Codex Provider

The `openai-codex` provider allows running inkagent using a **ChatGPT Plus/Pro subscription** instead of paying for API credits. It uses OAuth 2.0 + PKCE to authenticate against OpenAI's Codex endpoint.

- **Auth module**: `inkagent/codex_auth.py` — handles OAuth login, token storage (`~/.inkagent/codex-auth.json`), and automatic refresh
- **API endpoint**: `https://chatgpt.com/backend-api/codex/responses` (Responses API format, not Chat Completions)
- **Login**: `python -m inkagent.codex_auth` opens a browser for one-time OAuth consent
- **No API key needed** — authentication uses the ChatGPT subscription session
- **Limitations**: subject to ChatGPT subscription usage quotas; no embeddings (vector search still needs `OPENAI_API_KEY`)

## File Safety

The agent's `write_file` and `edit_file` tools enforce a path allowlist for writes within the project directory:
- **Writable**: `memory/`, `conversations/`
- **Read-only**: all other project files (`inkagent/`, `skills/`, etc.)
- **Outside the project**: no restrictions — the agent can freely read and write external files
- **Always blocked**: `.db` / `.sqlite` files (managed databases)

This is enforced at the tool level (`_check_writable` in `inkagent/tools/files.py`). The system prompt also instructs the LLM not to use `run_shell` to bypass these restrictions (soft limit).

## Testing

### Run Tests

```bash
pytest                      # all tests
pytest tests/test_memory.py # single file
pytest -x                   # stop on first failure
```

### Strategy

This is an IO-heavy glue project — most code interfaces with external services (LLM APIs, Telegram, Gmail, filesystem). The testing strategy prioritizes layers by ROI:

**Layer 1 — Pure logic unit tests (highest ROI, test first)**

Modules with clear input/output and no external dependencies. Use `tmp_path` to isolate the filesystem.

| Module | What to test |
|---|---|
| `memory.py` | Read/write memory files, daily log append, template seeding, promotion marker, keyword search |
| `session.py` | Conversation history CRUD, JSON persistence, reset |
| `compression.py` | Token estimation, message truncation logic |
| `telegram_format.py` | Markdown → Telegram HTML conversion |
| `skill_loader.py` | YAML frontmatter parsing, skill discovery |
| `registry.py` | Tool registration, schema validation, duplicate handling |
| `tools/files.py` | Path guard `_check_writable` (already tested) |

**Layer 2 — Interface contract tests (mock external dependencies)**

| Module | What to test |
|---|---|
| `brain.py` | Agentic loop control flow: end_turn in one call, tool_use → execute → end_turn, MAX_TOOL_ROUNDS forces text |
| `bot.py` | Telegram handler routing (already tested) |
| `scheduler.py` | Cron trigger logic, job persistence, timezone handling |
| `providers/*.py` | `format_tools()`, `assistant_message()`, `tool_results_messages()` output format |

**Layer 3 — Integration smoke tests (optional, CI with API keys)**

Mark with `@pytest.mark.slow`, skip by default. Verify "send message → get reply" end-to-end with a real LLM.

### Conventions

- **Test behavior, not implementation** — assert on outputs and side effects, not internal calls
- **Isolate the filesystem with `tmp_path`** — monkeypatch path constants to point at `tmp_path`. Paths need to be patched in **both** `inkagent.config` and in modules that import them at module level (e.g. `inkagent.memory.MEMORY_DIR`, `inkagent.session.CONVERSATIONS_DIR`, `inkagent.skill_loader.SKILLS_DIR`)
- **Clean up module-level global state between tests** — several modules use global dicts/lists: `registry._skills`, `session._sessions` + `session._session_files`, `scheduler._jobs`. Use fixtures that save/restore or clear these between tests
- **Mock at the outermost boundary** — mock LLM HTTP calls and external APIs, not internal functions
- **Tracing** — `inkagent/tracing/` resolves to no-op functions when `LANGFUSE_PUBLIC_KEY` is unset. No fixture needed — just don't set tracing env vars in tests
- **Vector store** — `recall_memory` and `append_daily_log` lazy-import `vector_store` with try/except fallback. No special handling needed in tests — they degrade to keyword search naturally
- **No API keys required** — all Layer 1 and Layer 2 tests must run without any env vars. Tests requiring keys use `@pytest.mark.slow`

### conftest.py Fixtures

- **`tmp_memory_dir`** — creates `memory/`, `memory/daily/`, `conversations/` under `tmp_path`; monkeypatches all path constants in `inkagent.config` AND in consumer modules (`inkagent.memory`, `inkagent.session`, `inkagent.skill_loader`, `inkagent.scheduler`)
- **`clean_registry`** — saves and restores `registry._skills` around each test
- **`clean_session`** — clears `session._sessions` and `session._session_files` after each test

### Implementation Order

Each step is independently runnable and committable:

1. **`conftest.py` + `test_telegram_format.py`** — set up shared fixtures; start with the zero-dependency pure function module
2. **`test_registry.py`** — register/call/truncation/error handling
3. **`test_memory.py`** — template seeding, read/write, daily log, promotion marker, keyword search
4. **`test_session.py`** — conversation CRUD, JSON persistence, reset, inject
5. **`test_compression.py`** — `estimate_tokens` pure logic; `maybe_compress`/`force_compress` with mocked `_summarize_messages`
6. **`test_skill_loader.py`** — frontmatter parsing, requirements gating, skill discovery
7. **`test_scheduler.py`** — job CRUD + persistence; async `run_scheduler` can be deferred
8. **`test_brain.py`** — agentic loop with fake provider: direct end_turn, tool_use loop, MAX_TOOL_ROUNDS cap

### File Layout

```
tests/
├── conftest.py              # Shared fixtures: tmp memory dir, clean_registry, clean_session
├── test_bot.py              # ✅ exists
├── test_file_guard.py       # ✅ exists
├── test_telegram_format.py  # format conversion (pure functions)
├── test_registry.py         # tool registration
├── test_memory.py           # memory read/write/promotion
├── test_session.py          # conversation management
├── test_compression.py      # token estimation, truncation
├── test_skill_loader.py     # skill discovery
├── test_scheduler.py        # cron job CRUD & trigger logic
└── test_brain.py            # agentic loop (mock provider)
```

## Code Style

- Type hints on all function signatures
- No global state except `registry` singleton and provider singleton; module-level state is scoped to `session.py`, `compression.py`, `promotion.py`, `scheduler.py`, `vector_store.py`, `codex_auth.py`, and `providers/__init__.py`. Shared constants live in `inkagent/config.py`
- Cap tool output at `TOOL_OUTPUT_CAP` chars (see `inkagent/config.py`) before returning to avoid context explosion
- IMPORTANT: Never import individual tool modules in `brain.py` — only import the `inkagent.tools` package which auto-registers all tools
- IMPORTANT: Never import `anthropic` or `openai` directly in `brain.py` — always go through `providers`

## Roadmap (in order)

1. ~~CLI + shell tool + Markdown memory~~ (Phase 1)
2. ~~Telegram bot interface~~ — `inkagent/bot.py`, owner-only, typing indicator
3. ~~Scheduled tasks~~ — cron scheduler (`croniter` + asyncio), `create_cron` / `list_crons` / `delete_cron` tools
4. ~~Web search tool~~ — `web_search` (Brave) + `web_fetch` (trafilatura)
5. ~~Gmail~~ — `gmail_search`, `gmail_read`, `gmail_send` tools (IMAP/SMTP + App Password)
