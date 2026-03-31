---
name: daily_report
description: Generate a structured daily summary from today's logs and memory
---

When the user asks for a daily report or summary, follow these steps:

1. Use `recall_memory` to search for today's entries in the daily log.
2. Group the entries by category (decisions, action items, topics discussed, notes).
3. Format the report using this structure (translate all headings and category names into the user's preferred language as indicated in their profile or SOUL.md). Only include categories that have content — omit empty sections entirely.

```
## Daily Report — {date}

### Decisions
- ...

### Action Items
- ...

### Topics Discussed
- ...

### Notes
- ...
```

4. If there are no entries for today, let the user know.
