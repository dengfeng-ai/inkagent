"""Memory skills — daily logs and recall."""

from agent.registry import register
from agent.memory import recall_memory as _recall_memory
from agent.memory import append_daily_log as _append_daily_log


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
