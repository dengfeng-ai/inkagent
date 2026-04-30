# inkagent

A lightweight personal AI agent that runs locally, powered by Claude, OpenAI, or ChatGPT subscription (via Codex OAuth) and driven by Markdown memory.
Inspired by OpenClaw. Built in Python.

## Architecture

```
inkagent/        # Python package — CLI, Telegram bot, agentic loop, providers, tools
skills/          # Instruction skills (Markdown, git-tracked, user-edited)
config/          # Agent behavior config (AGENTS.md, git-tracked, user-edited)
memory/          # All runtime memory (gitignored)
conversations/   # Per-session conversation history as JSON (gitignored)
tests/
pyproject.toml
Dockerfile
```

Key design principles:
- `brain.py` has zero knowledge of individual tools, skills, or LLM providers — it loops through `provider.complete()` and dispatches via the registry.
- Tools register themselves via `@registry.register(...)` — adding a tool never touches core code.
- Instruction skills are auto-discovered from `skills/` — adding one is just creating a directory with a `SKILL.md` file.

## Tech Stack

- Python 3.11+
- `anthropic` SDK + `openai` SDK — pluggable via `inkagent/providers/`
- Markdown files — all memory storage
- `sqlite-vec` — vector storage for semantic search over daily logs (`memory/memory.db`)
- `python-telegram-bot` — Telegram bot interface
- `httpx` + `trafilatura` — web search/fetch
- `PyYAML` — YAML frontmatter parsing for instruction skills
- `croniter` — cron expression parsing for scheduled tasks
- `langfuse` — optional observability tracing (no-op when not installed/configured)

## Common Commands

```bash
pip install -e .                         # install (editable)
pip install -e ".[langfuse]"             # with optional Langfuse tracing

python -m inkagent                       # CLI (alias: inkagent)
python -m inkagent.bot                   # Telegram bot (alias: inkagent-bot)

python -m inkagent.codex_auth            # one-time browser OAuth login (Codex)
```

### Provider Configuration (env vars)

Both the CLI and the bot call `load_dotenv()` at startup, so set these in a project-root `.env` file (see `.env.example`).

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic`, `openai`, or `openai-codex` |
| `LLM_MODEL` | per-provider | Main model (defaults: `claude-opus-4-6`, `gpt-5.4`) |
| `LLM_SMALL_MODEL` | per-provider | Cheap model for compression/promotion (defaults: `claude-sonnet-4-6`, `gpt-5.4-mini`) |
| `INKAGENT_TIMEZONE` | system local, else `Asia/Singapore` | IANA timezone used for cron jobs and prompt time injection |
| `LANGFUSE_PUBLIC_KEY` | — | Enables Langfuse tracing when set (also needs `LANGFUSE_SECRET_KEY` and the `[langfuse]` extra). No-op when unset. |
| `BRAVE_API_KEY` | — | Required for `web_search` tool |
| `GMAIL_ADDRESS` | — | Required for Gmail tools |
| `GMAIL_APP_PASSWORD` | — | Required for Gmail tools (generate at myaccount.google.com/apppasswords) |

## Memory System

Markdown memory files in `memory/`, injected as bootstrap context into the system prompt on every turn:

- **`config/AGENTS.md`** — Agent behavior rules and working guidelines. Injected into the system prompt `<instructions>` block. Git-tracked.
- **`IDENTITY.md`** — Agent identity metadata (name, creature, vibe, emoji, avatar). Updated via `update_identity` tool.
- **`SOUL.md`** — Agent behavioral rules (core truths, boundaries, tone). Updated via `update_soul` tool.
- **`USER.md`** — User profile. Updated via `update_user_profile` tool.
- **`MEMORY.md`** — Long-term curated memory. Auto-seeded with a header template on first access. Writable via `save_memory` tool and via the automatic promotion system.
- **`daily/YYYY-MM-DD.md`** — Daily logs. Append-only, one file per day. Today's + yesterday's logs injected into system prompt. Each entry is also indexed into the vector store.
- **`memory.db`** — sqlite-vec database for semantic search over daily logs. Auto-created when an embedding provider is available; system degrades to keyword search without it.

**Vector search**: `recall_memory` uses semantic search (sqlite-vec + OpenAI embeddings) for daily logs when `OPENAI_API_KEY` is set. Falls back to keyword search otherwise. MEMORY.md is not searched by `recall_memory` — it's already in the system prompt.

**Memory promotion**: On the first conversation turn each day, if yesterday's daily log exists and isn't promoted, the system sends the log + current MEMORY.md to the small model, which decides what's worth keeping long-term. Promoted entries are appended to MEMORY.md; the daily log is marked `<!-- promoted -->` to prevent re-processing.

Conversation history is kept in-memory for the current session, auto-saved to `conversations/` as JSON.
The `memory/` directory is gitignored — never commit it.

## Scheduler (Cron)

`inkagent/scheduler.py` provides a cron-based task scheduler. Jobs are persisted in `memory/crons.json`.

- Runs as an asyncio background task, checking every 60 seconds.
- When a job fires, it calls `run_agent(prompt, session_id)` with a fresh session (timestamped session ID) and delivers the reply via a callback.
- In Telegram bot mode, the scheduler starts automatically and sends replies to the bound chat.
- In CLI mode, the scheduler does not run (no persistent event loop), but cron tools still work — jobs created in CLI take effect when a bot starts.
- Jobs are bound to a `session_id` (e.g. `tg_123456`) at creation time via `session.current_session_id`. The scheduler callback only delivers jobs whose session_id matches its own prefix.
- **Timezone-aware**: each job stores an IANA timezone (default from `INKAGENT_TIMEZONE` / system / `Asia/Singapore`). Cron expressions are interpreted in the job's timezone.
- **Heartbeat mode**: jobs with `silent_ok: true` suppress notification when the agent replies with exactly `HEARTBEAT_OK`.

### Heartbeat

Heartbeat is a special use of the cron system for periodic background checks (email, calendar, etc.) that only notify the user when something needs attention:

- **`memory/HEARTBEAT.md`** — checklist of things to check periodically. User- and agent-editable.
- **`skills/heartbeat/SKILL.md`** — instruction skill teaching the workflow.
- **`silent_ok` flag on cron jobs** — replies of `HEARTBEAT_OK` are swallowed silently.

Setup: create a cron job with `silent_ok=true` whose prompt tells the agent to run the heartbeat skill.

## Session Control Commands

User-facing commands handled locally (not sent to the LLM):

- `/new` — archive current conversation and start a fresh session (`session.reset_conversation()`)
- `/compact` — force-compress conversation history (`compression.force_compress()`)

In Telegram, these are native bot commands. In CLI, they are intercepted in the input loop.

## Skill System

Two types of skills, separated by design.

### Tools (Python functions)

Each tool is a Python function decorated with `@registry.register(...)`.
The decorator takes `name`, `description`, and `input_schema` (JSON Schema).

To add a new tool:
1. Create `inkagent/tools/your_tool.py`
2. Decorate your function with `@register(...)`
3. Add `from inkagent.tools import your_tool` in `inkagent/tools/__init__.py`

Built-in tools (see `inkagent/tools/`):

| File | Tools |
|---|---|
| `shell.py` | `run_shell` (30s timeout, output capped at `TOOL_OUTPUT_CAP`) |
| `files.py` | `read_file`, `write_file`, `edit_file`, `list_directory` (writes path-guarded — see File Safety) |
| `profile.py` | `update_identity`, `update_soul`, `update_user_profile` |
| `memory_skill.py` | `recall_memory` (semantic over daily logs), `log_daily`, `save_memory` |
| `cron.py` | `create_cron`, `list_crons`, `delete_cron` |
| `web_search.py` / `web_fetch.py` | `web_search` (Brave), `web_fetch` (trafilatura) |
| `gmail.py` | `gmail_search`, `gmail_read`, `gmail_send`, `gmail_mark_read` |

### Instruction Skills (Markdown files)

Pure Markdown files that teach the LLM workflows without writing Python — they guide the LLM on *when and how* to combine existing tools for specific tasks.

`skill_loader.py` scans `skills/` for subdirectories containing a `SKILL.md` file. The agent does not modify skills — edit them directly.

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

- Only skill meta (name, description, path) is injected into the system prompt — the LLM uses `read_file` to load full instructions on demand.
- Skills with unmet `requires` are silently skipped.

## Agentic Loop

`brain.py` runs a provider-agnostic tool_use loop:
1. Build system prompt (instructions + IDENTITY.md + SOUL.md + USER.md + MEMORY.md + daily logs + instruction skills) + conversation messages.
2. Call LLM via `provider.complete()` with all registered tools (auto-formatted per provider).
3. If `stop_reason == "tool_use"`: execute tools, append results via `provider.tool_results_messages()`, loop.
4. If `stop_reason == "end_turn"`: extract text, append to in-memory conversation, return.

The loop is capped at `MAX_TOOL_ROUNDS` (see `inkagent/config.py`). Once exceeded, the next call passes `tools=[]`, which forces the model to produce a text reply and exit cleanly.

## Provider System

`inkagent/providers/` contains a pluggable abstraction layer. `LLMProvider` (ABC) defines the interface:
- `complete()` — full completion with tool support, returns `LLMResponse`
- `simple_complete()` — text-only completion (used by compression/promotion)
- `format_tools()` — converts registry tool schemas to provider-native format
- `assistant_message()` / `tool_results_messages()` — builds provider-native message dicts for the agentic loop

Adding a new provider means implementing `LLMProvider` and registering it in `providers/__init__.py`.

### OpenAI Codex Provider

The `openai-codex` provider runs inkagent using a **ChatGPT Plus/Pro subscription** instead of paid API credits. It uses OAuth 2.0 + PKCE against OpenAI's Codex endpoint.

- **Auth module**: `inkagent/codex_auth.py` — OAuth login, token storage (`~/.inkagent/codex-auth.json`), automatic refresh.
- **API endpoint**: `https://chatgpt.com/backend-api/codex/responses` (Responses API format).
- **Login**: `python -m inkagent.codex_auth` opens a browser for one-time consent.
- **Limitations**: subject to ChatGPT subscription usage quotas; no embeddings (vector search still needs `OPENAI_API_KEY`).

## File Safety

The agent's `write_file` and `edit_file` tools enforce a path allowlist for writes within the project directory:
- **Writable**: `memory/`, `conversations/`
- **Read-only**: all other project files (`inkagent/`, `skills/`, etc.)
- **Outside the project**: no restrictions
- **Always blocked**: `.db` / `.sqlite` files (managed databases)

Enforced by `_check_writable` in `inkagent/tools/files.py`. The system prompt also instructs the LLM not to use `run_shell` to bypass these restrictions (soft limit).

## Testing

```bash
pytest                       # all tests
pytest tests/test_memory.py  # single file
pytest -x                    # stop on first failure
```

This is an IO-heavy glue project. Tests are layered by ROI:

- **Layer 1 — pure logic** (`memory`, `session`, `compression`, `telegram_format`, `skill_loader`, `registry`, `tools/files` path guard): use `tmp_path`, no external deps.
- **Layer 2 — interface contracts** (`brain` agentic loop, `bot` handler routing, `scheduler` cron triggers, `providers/*` message formatting): mock external deps (LLM HTTP, Telegram).
- **Layer 3 — integration smoke** (optional, real LLM): mark with `@pytest.mark.slow`, skip by default.

### Conventions

- **Test behavior, not implementation** — assert on outputs and side effects, not internal calls.
- **Isolate the filesystem with `tmp_path`** — patch path constants in **both** `inkagent.config` AND in modules that import them at module level (`inkagent.memory.MEMORY_DIR`, `inkagent.session.CONVERSATIONS_DIR`, `inkagent.skill_loader.SKILLS_DIR`, etc.). The `tmp_memory_dir` fixture in `conftest.py` already handles this.
- **Reset module-level globals between tests** — `registry._skills`, `session._sessions` + `session._session_files`, `scheduler._jobs`. Use the `clean_registry` / `clean_session` fixtures.
- **Mock at the outermost boundary** — mock LLM HTTP calls and external APIs, not internal functions.
- **No API keys required** — Layer 1 and Layer 2 tests must run without env vars. Tracing (`inkagent/tracing/`) and `vector_store` both no-op gracefully when their deps are missing, so no special handling needed.

## Code Style

- snake_case, type hints on all function signatures.
- No global state except the `registry` singleton and the provider singleton; module-level state is scoped to `session.py`, `compression.py`, `promotion.py`, `scheduler.py`, `vector_store.py`, `codex_auth.py`, and `providers/__init__.py`. Shared constants live in `inkagent/config.py`.
- Cap tool output at `TOOL_OUTPUT_CAP` chars before returning, to avoid context explosion.
- **IMPORTANT — `brain.py` boundaries**:
  - Never import individual tool modules — only `inkagent.tools` (the package auto-registers all tools).
  - Never import `anthropic` or `openai` directly — always go through `inkagent.providers`.
