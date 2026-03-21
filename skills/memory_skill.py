"""Memory skills — long-term memory and daily logs."""

from agent.registry import register
from agent.memory import save_memory as _save_memory
from agent.memory import recall_memory as _recall_memory
from agent.memory import append_daily_log as _append_daily_log


@register(
    name="save_memory",
    description="Save a piece of information to long-term memory (MEMORY.md). Use this when the user shares a durable fact, preference, decision, or notable event worth remembering across sessions. Do NOT save transient or session-specific info.",
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The memory content to save",
            },
            "category": {
                "type": "string",
                "enum": ["fact", "preference", "decision", "event"],
                "description": "Memory category: fact (about user/world), preference (likes/dislikes), decision (choices made), event (something that happened)",
            },
        },
        "required": ["content", "category"],
    },
)
def save_memory(content: str, category: str) -> str:
    return _save_memory(content, category)


@register(
    name="recall_memory",
    description="Search long-term memory (MEMORY.md) by keyword. Use this to look up previously stored facts, preferences, decisions, or events.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keyword or phrase to search for in memories",
            },
        },
        "required": ["query"],
    },
)
def recall_memory(query: str) -> str:
    return _recall_memory(query)


@register(
    name="log_daily",
    description="Jot down a note in today's daily log. Use this for noteworthy things during conversation — decisions made, problems solved, topics discussed, action items. These are short-lived notes (kept for a few days), NOT long-term memory. For durable facts/preferences, use save_memory instead.",
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The note to log (one line, concise)",
            },
        },
        "required": ["content"],
    },
)
def log_daily(content: str) -> str:
    return _append_daily_log(content)
