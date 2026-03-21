"""update_profile skill — persists user info to memory/profile.md."""

from agent.registry import register
from agent.memory import update_profile as _update_profile


@register(
    name="update_profile",
    description="Update the persistent user profile with new information learned about the user. Pass the full updated profile content.",
    input_schema={
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The full updated profile content in Markdown",
            },
        },
        "required": ["content"],
    },
)
def update_profile(content: str) -> str:
    return _update_profile(content)
