"""Tool registration system.

Tools register themselves via the @register decorator.
brain.py reads registered tools without knowing individual tool implementations.
"""

from typing import Any, Callable

from inkagent.config import TOOL_OUTPUT_CAP

_skills: dict[str, dict[str, Any]] = {}


def register(name: str, description: str, input_schema: dict[str, Any]) -> Callable:
    """Decorator that registers a function as a tool for Claude."""

    def decorator(func: Callable) -> Callable:
        _skills[name] = {
            "name": name,
            "description": description,
            "input_schema": input_schema,
            "func": func,
        }
        return func

    return decorator


def get_tools() -> list[dict[str, Any]]:
    """Return tool definitions in Claude API format."""
    return [
        {
            "name": s["name"],
            "description": s["description"],
            "input_schema": s["input_schema"],
        }
        for s in _skills.values()
    ]


def call_tool(name: str, args: dict[str, Any]) -> str:
    """Execute a registered tool by name and return its output."""
    if name not in _skills:
        return f"Error: unknown tool '{name}'"
    try:
        result = _skills[name]["func"](**args)
        if len(result) > TOOL_OUTPUT_CAP:
            result = result[:TOOL_OUTPUT_CAP] + "\n... (output truncated)"
        return result
    except Exception as e:
        return f"Error running {name}: {e}"
