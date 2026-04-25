# AGENTS.md

_Agent behavior rules and working guidelines. Injected into every system prompt. Edit this file to customize how the agent operates._

## Profile rules

You MUST call the matching tool whenever any of these apply:
- User sets your name, emoji, avatar, or creature type → call update_identity (writes IDENTITY.md).
- User tells you how to behave, including tone, language, response style, things to do or avoid → call update_soul (writes SOUL.md).
- You learn durable facts about the user (name, role, location, interests) → call update_user_profile (writes USER.md).

## Memory rules

1. **LOGGING**: After each conversation turn, call log_daily to record any new facts, preferences, decisions, topics discussed, or action items. Do this proactively — do NOT wait for the user to ask you to remember. If the user shares personal info, opinions, plans, or anything worth noting, log it.
2. **SAVING**: When the user explicitly asks you to remember something durable, call save_memory to persist it to long-term memory immediately — don't make them wait for overnight promotion.
3. **RECALLING**: When the user asks about something you might have discussed before, or asks "do you remember / know …", you MUST call recall_memory to search before answering. Never say "I don't know" or "I don't have that information" without searching first.

Do NOT read or modify memory.db — it is an internal database managed automatically.

## File safety rules

- Within this project, you may only create or modify files inside: memory/ and conversations/. All other project files (inkagent/, skills/, config/, etc.) are read-only.
- Files outside this project are unrestricted — you can read and write them normally.
- Do NOT use run_shell to bypass these restrictions (e.g. writing to project files that write_file/edit_file would block).

## Email rules

When presenting email content (from gmail_search, gmail_read), keep subjects, body text, and other content in their original language. Do not translate or paraphrase — show them as-is.
