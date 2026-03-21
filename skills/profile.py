"""Memory skills — persist agent persona and user info."""

from agent.registry import register
from agent.memory import update_soul as _update_soul
from agent.memory import update_user_profile as _update_user_profile


@register(
    name="update_soul",
    description="Update the agent's persona (SOUL.md). Store identity, name, tone, language preference, and behavior rules the user sets for you. Pass the full updated content.",
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The full updated persona content in Markdown",
            },
        },
        "required": ["content"],
    },
)
def update_soul(content: str) -> str:
    return _update_soul(content)


@register(
    name="update_user_profile",
    description="Update the user's personal profile (USER.md). Store identity info about the user: name, role, location, interests, habits. Never store transient context like current tasks or session-specific details. Pass the full updated content.",
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The full updated user profile content in Markdown",
            },
        },
        "required": ["content"],
    },
)
def update_user_profile(content: str) -> str:
    return _update_user_profile(content)
