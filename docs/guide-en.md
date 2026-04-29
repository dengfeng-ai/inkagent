# inkagent User Guide

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Choosing an LLM Provider](#2-choosing-an-llm-provider)
3. [Memory System](#3-memory-system)
4. [Telegram Bot](#4-telegram-bot)
4.5. [WhatsApp Bot](#45-whatsapp-bot)
5. [Web Search](#5-web-search)
6. [Gmail Integration](#6-gmail-integration)
7. [Scheduled Tasks & Heartbeat](#7-scheduled-tasks--heartbeat)
8. [Custom Skills](#8-custom-skills)
9. [Session Control](#9-session-control)
10. [Environment Variables Reference](#10-environment-variables-reference)

---

## 1. Quick Start

Get inkagent running with minimal configuration.

### Prerequisites

- Python 3.11+
- An LLM API key (Anthropic or OpenAI), or a ChatGPT Plus/Pro subscription

### Installation

```bash
git clone https://github.com/dengfeng-ai/inkagent
cd inkagent
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Minimal Configuration

```bash
cp .env.example .env
```

Edit `.env`, uncomment and fill in your API key:

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx
```

### Launch

```bash
python -m inkagent
```

Once you see the prompt, type a message to start chatting. The agent will automatically use tools and manage memory.

### Docker (Recommended)

Docker is safer — the `run_shell` tool executes inside the container, keeping your host machine safe.

```bash
docker build -t inkagent .

# CLI mode
docker run -it --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  inkagent

# Telegram bot mode
docker run --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  inkagent python -m inkagent.bot

# WhatsApp bot mode (also requires libmagic in the image; see Section 4.5)
docker run -it --env-file .env \
  -v $(pwd)/memory:/app/memory \
  -v $(pwd)/conversations:/app/conversations \
  inkagent python -m inkagent.whatsapp_bot
```

Mount `memory/` and `conversations/` to persist data across container restarts.

### File Safety

Within the project directory, the agent can only write to `memory/` and `conversations/`. All other project files (source code, configs, skills, etc.) are read-only to the agent. Files outside the project directory are unrestricted.

This is enforced at the tool level for `write_file` and `edit_file`. The `run_shell` tool is not hard-restricted but the agent is instructed via its system prompt not to use it to bypass file write restrictions.

### Verify

After launching, type any message. If the agent replies normally, the setup is complete.

---

## 2. Choosing an LLM Provider

inkagent supports three LLM providers, switchable via `LLM_PROVIDER` in `.env`.

### Option A: Anthropic

Requires an Anthropic API key.

```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx
LLM_PROVIDER=anthropic
```

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | API key (required) |
| `LLM_MODEL` | `claude-opus-4-6` | Main model |
| `LLM_SMALL_MODEL` | `claude-sonnet-4-6` | Small model (for compression and memory promotion) |

### Option B: OpenAI

Requires an OpenAI API key.

```bash
OPENAI_API_KEY=sk-xxxxx
LLM_PROVIDER=openai
```

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | — | API key (required) |
| `LLM_MODEL` | `gpt-5.4` | Main model |
| `LLM_SMALL_MODEL` | `gpt-5.4-mini` | Small model |

### Option C: ChatGPT Subscription (Codex OAuth)

Run with a ChatGPT Plus/Pro subscription — no API key needed, no extra charges.

**Step 1: Authenticate (one-time)**

```bash
python -m inkagent.codex_auth
```

A browser window will open to the OpenAI authorization page. After authorizing, the token is saved to `~/.inkagent/codex-auth.json` and refreshed automatically.

**Step 2: Configure `.env`**

```bash
LLM_PROVIDER=openai-codex
```

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `gpt-5.4` | Main model |
| `LLM_SMALL_MODEL` | `gpt-5.4-mini` | Small model |

**Check login status:**

```bash
python -m inkagent.codex_auth status
```

**Note:** Codex mode is subject to ChatGPT subscription usage limits. It does not support embeddings — memory search still requires `OPENAI_API_KEY`.

### Provider Comparison

| Feature | Anthropic | OpenAI | Codex |
|---------|-----------|--------|-------|
| Requires API key | Yes | Yes | No |
| Pay-per-use | Yes | Yes | No (subscription) |
| Memory search | Requires separate `OPENAI_API_KEY` | Available automatically | Requires separate `OPENAI_API_KEY` |
| Tool calling | Supported | Supported | Supported |

---

## 3. Memory System

All of inkagent's memory is stored as Markdown files in the `memory/` directory. You can view them at any time. It is recommended to let the agent modify them through conversation rather than editing the files directly.

### Memory Files

| File | Purpose | How to Update |
|------|---------|---------------|
| `IDENTITY.md` | Agent identity — name, creature type, vibe, emoji, avatar | Tell the agent in conversation, e.g. "Your name is Inky" |
| `SOUL.md` | Agent behavior rules — tone, boundaries, core beliefs | Tell the agent, e.g. "Reply in English" |
| `USER.md` | User profile — name, role, interests | The agent learns automatically from conversation |
| `MEMORY.md` | Long-term memory — important facts and decisions (auto-created with header template on first access) | `save_memory` tool + automatic promotion |
| `daily/YYYY-MM-DD.md` | Daily log — ephemeral notes, one file per day | `log_daily` tool |
| `memory.db` | Vector index (for memory search) | Auto-managed |

### Memory Lifecycle

```
Information in conversation
  ↓ log_daily
Daily log (daily/YYYY-MM-DD.md)
  ↓ Auto-promoted next day
Long-term memory (MEMORY.md)
```

1. During conversation, the agent uses `log_daily` to write noteworthy content to today's log
2. When you say "remember this", the agent uses `save_memory` to write directly to long-term memory
3. On the first conversation each day, the system automatically reviews yesterday's log and promotes valuable content to `MEMORY.md`

### Memory Search

Memory search uses OpenAI embeddings to index daily logs into a vector store (`memory.db`). The agent's `recall_memory` tool searches logs by vector similarity. This means even if you use Anthropic or Codex as the LLM provider, memory search still requires a separate `OPENAI_API_KEY`:

```bash
OPENAI_API_KEY=sk-xxxxx
```

Without `OPENAI_API_KEY`, memory search falls back to keyword matching. Core functionality is not affected.

**Note:** `MEMORY.md` is not searched — its content is already injected into the agent's system prompt, so the agent can see it in every conversation.

### Customizing the Agent Persona

Just tell the agent in conversation:

- "Your name is Inky" → updates `IDENTITY.md`
- "Reply in English" → updates `SOUL.md`
- "My name is Derek, I'm an AI engineer" → updates `USER.md`

It is recommended to let the agent update these files itself to keep the format consistent.

---

## 4. Telegram Bot

Chat with the agent via Telegram, accessible anywhere.

### Prerequisites

- A configured LLM provider (see [Section 2](#2-choosing-an-llm-provider))
- A Telegram account

### Setup

**Step 1: Create a Telegram Bot**

1. Find [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot` and follow the prompts to set a name
3. Note the bot token returned (format: `123456:ABC-DEF...`)

**Step 2: Get Your User ID**

1. Find [@userinfobot](https://t.me/userinfobot) on Telegram
2. Send any message — it will return your numeric ID

**Step 3: Configure `.env`**

```bash
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
TELEGRAM_OWNER_ID=987654321
```

**Step 4: Launch**

```bash
python -m inkagent.bot
```

### Verify

Send any message to your bot on Telegram. If it replies, the setup is complete.

### Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Confirm the bot is online |
| `/new` | Archive current conversation and start a new session |
| `/compact` | Compress conversation history (use when context gets too long) |

### Notes

- Only the user matching `TELEGRAM_OWNER_ID` can interact with the bot (security restriction)
- In Telegram mode, scheduled tasks (cron) start automatically and send triggered messages to the corresponding chat
- Single message limit is 4096 characters; longer replies are automatically split

---

## 4.5 WhatsApp Bot

Chat with the agent via WhatsApp from any device — phone, web, or desktop.

Connects via the unofficial WhatsApp Web protocol (`neonize` → `whatsmeow`),
so **no Meta Business approval, no public webhook, no message-template
gymnastics**. The bot pairs as a Linked Device on a WhatsApp account you
control.

### Prerequisites

- A configured LLM provider (see [Section 2](#2-choosing-an-llm-provider))
- A **dedicated WhatsApp number** for the bot (strongly recommended — see "About the bot account" below)
- `libmagic` installed on the host

### Setup

**Step 1: Install libmagic**

```bash
brew install libmagic                  # macOS
sudo apt install libmagic1             # Debian / Ubuntu
```

`neonize` dlopens `libmagic` at startup; without it the import fails.

**Step 2: Configure `.env`**

```bash
# Your OWN phone (the one you'll message the bot from), digits only
# with country code, no '+'. Example: 6591234567 (Singapore +65 91234567).
WHATSAPP_OWNER_PHONE=6591234567
```

**Step 3: Launch and pair**

```bash
python -m inkagent.whatsapp_bot
```

A QR code prints in the terminal. On the **bot's phone** (the dedicated
account, not your main number):

1. Open WhatsApp → **Linked Devices**
2. Tap **Link a device**
3. Scan the terminal QR

After ~5–10 seconds you'll see `WhatsApp bot connected. Owner phone: ...`.
Pairing state is persisted to `memory/whatsapp_session.db`; subsequent
launches reuse it (no QR needed).

### Verify

From your **main number**, message the bot's WhatsApp number with `hi`.
It should reply within seconds.

### Bot Commands

| Command | Description |
|---------|-------------|
| `/new` | Archive current conversation and start a new session |
| `/compact` | Compress conversation history |

### About the bot account

The bot pairs as a Linked Device on **one** WhatsApp account, and any
message that account receives is visible to the bot. Three reasons to
use a dedicated number rather than your main one:

1. **Self-chat is awkward.** WhatsApp has no `@inkagent_bot` handle —
   to "talk to the bot" you message its number from another number.
   You can't easily message yourself.
2. **The bot sees every chat.** If paired to your main number, every
   message anyone sends you becomes a bot event.
3. **The bot replies as you.** Any bug in the agent could send messages
   under your identity to real people.

Get a dedicated number via dual-SIM, the WhatsApp Business app
(coexists with regular WhatsApp on the same phone), or a virtual number.

### Known: "AI from Meta" disclosure banner

When you message the bot, WhatsApp shows a privacy banner like *"AI from
Meta receives messages to improve AI quality and generate messages for
this business"* and labels each bot reply with an "AI ✦" badge. **This
is unavoidable** — WhatsApp's classifier flags messages from any
non-mobile-app linked device that exhibits automated reply patterns,
even when the bot account is regular (non-Business) WhatsApp.

The disclosure is misleading: end-to-end encryption still applies and
Meta does not actually see message content (the bot runs on your
machine via a direct whatsmeow socket). It's purely a UI warning that
WhatsApp now shows for any third-party automation client.

### Notes

- Only the sender matching `WHATSAPP_OWNER_PHONE` is processed; messages from anyone else are dropped silently
- LID addressing is handled — when WhatsApp routes via LID, the phone-form JID in `SenderAlt` is used for the owner check
- Scheduler (cron) starts automatically in WhatsApp mode and only delivers jobs whose session ID starts with `wa_`; if a Telegram bot is also running, each delivers its own
- Replies show a "typing…" indicator (refreshed every 10s) while the agent is composing
- Single message limit is 4096 characters; longer replies are split

---

## 5. Web Search

Give the agent the ability to search the internet.

### Prerequisites

- Brave Search API key (free tier: 2,000 queries/month)

### Setup

**Step 1: Get an API Key**

1. Visit [Brave Search API](https://brave.com/search/api/)
2. Sign up and create an API key

**Step 2: Configure `.env`**

```bash
BRAVE_API_KEY=BSA-xxxxx
```

### Verify

After launching, tell the agent "search for today's news". The agent will call the `web_search` tool and return results.

### Related Tools

| Tool | Description |
|------|-------------|
| `web_search` | Search via Brave, returns title, snippet, and link (default 5 results, max 20) |
| `web_fetch` | Fetch a URL and extract readable content (15s timeout) |

`web_fetch` requires no additional configuration and works out of the box.

---

## 6. Gmail Integration

Let the agent search, read, and send Gmail messages.

### Prerequisites

- A Gmail account
- 2-Step Verification enabled

### Setup

**Step 1: Generate an App Password**

1. Visit [Google App Passwords](https://myaccount.google.com/apppasswords) (requires 2-Step Verification)
2. Enter `inkagent` as the app name (or any name)
3. Note the generated 16-character password (format: `xxxx xxxx xxxx xxxx`)

**Step 2: Configure `.env`**

```bash
GMAIL_ADDRESS=your@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

### Verify

After launching, tell the agent "check my unread emails". The agent will call the `gmail_search` tool.

### Related Tools

| Tool | Description |
|------|-------------|
| `gmail_search` | Search emails (IMAP search syntax), returns sender, subject, date |
| `gmail_read` | Read full email content (includes attachment list) |
| `gmail_send` | Send or reply to email (supports `In-Reply-To` threading) |
| `gmail_mark_read` | Batch mark emails as read |

### IMAP Search Syntax Examples

| Syntax | Description |
|--------|-------------|
| `UNSEEN` | Unread emails |
| `FROM alice` | Emails from alice |
| `SUBJECT invoice` | Subject contains "invoice" |
| `SINCE 01-Jan-2026` | Emails after a specific date |
| `SUBJECT invoice UNSEEN` | Can be combined |

### Notes

- Uses an App Password, not your Gmail password
- App Passwords require 2-Step Verification to be enabled on your Gmail account
- Email operations use IMAP (reading) and SMTP (sending), not the Gmail API

---

## 7. Scheduled Tasks & Heartbeat

Let the agent execute tasks on a schedule and proactively notify you.

### Prerequisites

- Telegram or WhatsApp bot mode (scheduled tasks require a long-running process; tasks created in CLI mode only fire when a bot is running)

### Usage

Just tell the agent in conversation:

```
you> Send me a weather and email summary every day at 9 AM
you> Remind me to write a weekly report every Monday at 10 AM
you> Cancel that weather task
```

The agent will automatically call the `create_cron` / `list_crons` / `delete_cron` tools.

### Cron Expression Reference

| Expression | Meaning |
|------------|---------|
| `0 9 * * *` | Daily at 9:00 AM |
| `0 9 * * 1-5` | Weekdays at 9:00 AM |
| `*/30 * * * *` | Every 30 minutes |
| `0 10 * * 1` | Every Monday at 10:00 AM |
| `0 9,18 * * *` | Daily at 9:00 AM and 6:00 PM |

Format: `minute hour day month weekday`

Default timezone is `Asia/Shanghai`. You can specify a different IANA timezone when creating a task.

### Heartbeat

Heartbeat is a special type of scheduled task: it runs periodic background checks (email, calendar, etc.) and only notifies you when something needs attention — stays silent otherwise.

**Setup:**

**Step 1: Edit the Checklist**

Create or edit `memory/HEARTBEAT.md` with the items you want the agent to check periodically:

```markdown
## Checklist

- [ ] Check unread emails and notify me if anything important
- [ ] Check calendar for any upcoming meetings today
```

**Step 2: Create a Heartbeat Task**

Tell the agent in conversation:

```
you> Create a heartbeat task that checks every 30 minutes
```

The agent will create a cron job with `silent_ok=true`. When there's nothing noteworthy, the agent replies `HEARTBEAT_OK` and the notification is silently suppressed.

**Step 3: Verify**

```
you> List all scheduled tasks
```

Confirm the heartbeat task has been created.

### Notes

- Each scheduled task is bound to the session (Telegram chat or WhatsApp owner) where it was created; triggered messages are sent to the same chat. Each bot's scheduler only delivers jobs for its own prefix (`tg_*` or `wa_*`)
- Each trigger uses an independent session (timestamped session ID), so it won't interfere with ongoing conversations
- Heartbeat quiet hours are 23:00-08:00 (defined in `skills/heartbeat/SKILL.md`); only urgent items are notified during quiet hours

---

## 8. Custom Skills

Teach the agent new workflows through Markdown files — no code required. Skills guide the agent on how to combine existing tools to accomplish specific tasks.

All skills live in `skills/`. Edit them directly in your editor — the agent does not modify skills.

### Creating a New Skill

Create a directory and `SKILL.md` file under `skills/`:

```
skills/
└── daily_report/
    └── SKILL.md
```

Write the `SKILL.md`:

```yaml
---
name: daily_report
description: Generate a daily work summary
---

When the user asks for a daily report:

1. Use `recall_memory` to search today's logs
2. Group content into: Decisions, Action Items, Topics, Notes
3. Output the summary in Markdown format
```

Once placed, the agent discovers the skill automatically on next startup. The agent sees the skill name and description in its system prompt, and loads the full instructions via `read_file` when needed.

### Customizing an Existing Skill

Open the relevant `skills/<name>/SKILL.md` in your editor and edit it. Changes take effect on the next agent startup.

### Conditional Loading

You can use `requires` in the frontmatter to specify prerequisites. Skills with unmet requirements are silently skipped:

```yaml
---
name: audio_transcribe
description: Transcribe audio files
requires:
  env: [OPENAI_API_KEY]       # Required environment variables
  bins: [ffmpeg]              # Required command-line tools
---
```

### Bundled Skills

The repo ships with one skill under `skills/`:

| Skill | Description |
|-------|-------------|
| `heartbeat` | Periodic background check workflow (used with cron) |

---

## 9. Session Control

### CLI Mode

| Command | Description |
|---------|-------------|
| `/new` | Archive current conversation and start a new session |
| `/compact` | Compress conversation history (summarize old messages, keep last 3 turns) |
| `quit` or `exit` | Exit |

### Telegram Mode

| Command | Description |
|---------|-------------|
| `/start` | Confirm the bot is online |
| `/new` | Archive current conversation and start a new session |
| `/compact` | Compress conversation history |

### WhatsApp Mode

| Command | Description |
|---------|-------------|
| `/new` | Archive current conversation and start a new session |
| `/compact` | Compress conversation history |

### When to Use `/compact`

Use when conversations get long, the agent responds slowly, or you're approaching the context window limit. The system also triggers compression automatically when context reaches 80% (~160k tokens).

### Conversation Persistence

Conversation history is automatically saved in the `conversations/` directory (JSON format). After using `/new`, the old conversation is archived and a new one starts fresh (but memory files remain unchanged).

---

## 10. Environment Variables Reference

A summary of all environment variables. See `.env.example` in the project root for the full template.

### LLM Provider

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `LLM_PROVIDER` | No | `anthropic` | `anthropic`, `openai`, or `openai-codex` |
| `LLM_MODEL` | No | Varies by provider | Main model name |
| `LLM_SMALL_MODEL` | No | Varies by provider | Small model (for compression/memory promotion) |
| `ANTHROPIC_API_KEY` | For Anthropic | — | Anthropic API key |
| `OPENAI_API_KEY` | For OpenAI | — | OpenAI API key |

### Memory Search

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | No | — | Enables embedding-based memory search (required even when using Anthropic/Codex as LLM provider; falls back to keyword matching without it) |

### Telegram

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | For bot mode | Bot token from BotFather |
| `TELEGRAM_OWNER_ID` | For bot mode | Your numeric Telegram user ID |

### WhatsApp

| Variable | Required | Description |
|----------|----------|-------------|
| `WHATSAPP_OWNER_PHONE` | For WhatsApp bot mode | Your phone number (digits only with country code, no `+`, e.g. `6591234567`). The bot accepts messages only from this number; pair the bot to a *different* WhatsApp account on first run. |

### Web Search

| Variable | Required | Description |
|----------|----------|-------------|
| `BRAVE_API_KEY` | For web_search | [Brave Search API](https://brave.com/search/api/) key |

### Gmail

| Variable | Required | Description |
|----------|----------|-------------|
| `GMAIL_ADDRESS` | For Gmail | Gmail email address |
| `GMAIL_APP_PASSWORD` | For Gmail | [App Password](https://myaccount.google.com/apppasswords) (requires 2-Step Verification) |

### Observability (Optional)

Langfuse tracing — `pip install -e ".[langfuse]"`

| Variable | Required | Description |
|----------|----------|-------------|
| `LANGFUSE_PUBLIC_KEY` | No | [Langfuse](https://langfuse.com) public key |
| `LANGFUSE_SECRET_KEY` | No | Langfuse secret key |
| `LANGFUSE_HOST` | No | Langfuse host URL (default: `https://cloud.langfuse.com`) |

Tracing activates automatically when `LANGFUSE_PUBLIC_KEY` is set and the package is installed. Otherwise every tracing call is a no-op.
