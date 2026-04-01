"""Memory skills — daily logs and recall."""

from inkagent.registry import register
from inkagent.memory import recall_memory as _recall_memory
from inkagent.memory import append_daily_log as _append_daily_log
from inkagent.memory import save_memory as _save_memory


@register(
    name="recall_memory",
    description="Search daily logs — uses semantic search when available, keyword search otherwise. Use this to look up past conversations, decisions, or events. Note: MEMORY.md is already in context, so this only searches daily logs.",
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
    description="Jot down a note in today's daily log. Use this for anything worth remembering — facts, preferences, decisions, topics discussed, action items. Important entries will be automatically promoted to long-term memory.",
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


@register(
    name="save_memory",
    description="Save important information directly to long-term memory (MEMORY.md). Use this when the user explicitly asks you to remember something durable — facts, preferences, decisions, or reference info that should persist beyond today. For transient notes, use log_daily instead.",
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The information to save (concise, factual)",
            },
        },
        "required": ["content"],
    },
)
def save_memory(content: str) -> str:
    return _save_memory(content)
