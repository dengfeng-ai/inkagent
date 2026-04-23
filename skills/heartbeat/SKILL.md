---
name: heartbeat
description: Periodic heartbeat check — read HEARTBEAT.md checklist, run checks, notify only when something needs attention
---

# Heartbeat

When triggered as a heartbeat job, follow this workflow:

## 1. Read the checklist

Read `memory/HEARTBEAT.md`. This file contains a user-maintained checklist of things to check (e.g. unread emails, upcoming events). If the file doesn't exist or is empty, reply with `HEARTBEAT_OK`.

## 2. Run checklist checks

Go through the checklist items. Use the appropriate tools (gmail_search, web_search, web_fetch, etc.) to perform each check. Note anything that needs the user's attention.

## 3. Decide whether to notify

**Notify the user** (reply with a concise summary) when:
- An important or urgent email arrived
- An upcoming event is within 2 hours
- Something noteworthy was found in any check

**Stay silent** (reply with exactly `HEARTBEAT_OK`) when:
- Nothing new or important
- All checks came back empty
- It's late night (23:00–08:00 local time) and nothing is urgent

## 4. Quiet hours

Respect quiet hours (23:00–08:00 local time). During quiet hours, only notify for genuinely urgent items. Otherwise reply `HEARTBEAT_OK`.

## Setup

To create a heartbeat job, use create_cron with `silent_ok=true`:
```
create_cron(id="heartbeat", cron="*/30 * * * *", prompt="Run heartbeat check. Read the heartbeat skill instructions first.", silent_ok=true)
```

The user can edit `memory/HEARTBEAT.md` at any time to add or remove checks.

## HEARTBEAT.md format

When creating `memory/HEARTBEAT.md`, use this format:

```markdown
# HEARTBEAT.md

_Checklist for periodic heartbeat checks._

- [ ] Check item one
- [ ] Check item two
```
