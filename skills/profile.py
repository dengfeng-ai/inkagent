"""Memory skills — persist agent identity, behavioral rules, and user info."""

from agent.registry import register
from agent.memory import update_identity as _update_identity
from agent.memory import update_soul as _update_soul
from agent.memory import update_user_profile as _update_user_profile


@register(
    name="update_identity",
    description="Update the agent's identity metadata (IDENTITY.md). Store name, creature type, vibe, emoji, and avatar. Merge changes into the current IDENTITY.md content (already visible in the system prompt), then pass the full updated Markdown.",
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The full updated identity content in Markdown",
            },
        },
        "required": ["content"],
    },
)
def update_identity(content: str) -> str:
    return _update_identity(content)


@register(
    name="update_soul",
    description="Update the agent's behavioral rules (SOUL.md). MUST be called whenever the user tells you how to behave — tone, language, response style, things to do or avoid. Merge the new rule into the current SOUL.md content (already visible in the system prompt), then pass the full updated Markdown.",
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The full updated behavioral rules content in Markdown",
            },
        },
        "required": ["content"],
    },
)
def update_soul(content: str) -> str:
    return _update_soul(content)


@register(
    name="update_user_profile",
    description="Update the user's personal profile (USER.md). Store identity info about the user: name, role, location, interests, habits. Never store transient context like current tasks or session-specific details. IMPORTANT: read the current USER.md first, preserve its existing structure and sections, and only update the fields that changed.",
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
