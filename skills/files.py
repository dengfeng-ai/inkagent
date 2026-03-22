"""File operation skills — read, write, edit, and list files."""

import os

from agent.config import TOOL_OUTPUT_CAP
from agent.registry import register


@register(
    name="read_file",
    description="Read the contents of a file. Returns the text content (truncated if too large).",
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file to read",
            },
        },
        "required": ["path"],
    },
)
def read_file(path: str) -> str:
    path = os.path.expanduser(path)
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except IsADirectoryError:
        return f"Error: path is a directory, use list_directory instead: {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"

    if len(content) > TOOL_OUTPUT_CAP:
        return content[:TOOL_OUTPUT_CAP] + f"\n\n... (truncated, {len(content)} chars total)"
    return content if content else "(empty file)"


@register(
    name="write_file",
    description="Write content to a file. Creates the file (and parent directories) if they don't exist, or overwrites if they do.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "The text content to write to the file",
            },
        },
        "required": ["path", "content"],
    },
)
def write_file(path: str, content: str) -> str:
    path = os.path.expanduser(path)
    try:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote {len(content)} chars to {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"
    except IsADirectoryError:
        return f"Error: path is a directory: {path}"


@register(
    name="edit_file",
    description="Edit a file by replacing an exact string match with new content. Use read_file first to see the current content.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": "The exact string to find and replace (must appear exactly once in the file)",
            },
            "new_string": {
                "type": "string",
                "description": "The replacement string",
            },
        },
        "required": ["path", "old_string", "new_string"],
    },
)
def edit_file(path: str, old_string: str, new_string: str) -> str:
    path = os.path.expanduser(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"

    count = content.count(old_string)
    if count == 0:
        return "Error: old_string not found in file"
    if count > 1:
        return f"Error: old_string appears {count} times — must be unique. Provide more context to disambiguate."

    new_content = content.replace(old_string, new_string, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    return f"Edited {path} (replaced 1 occurrence)"


@register(
    name="list_directory",
    description="List files and directories at the given path. Returns names with '/' suffix for directories.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the directory to list (default: current directory)",
                "default": ".",
            },
        },
        "required": [],
    },
)
def list_directory(path: str = ".") -> str:
    path = os.path.expanduser(path)
    try:
        entries = sorted(os.listdir(path))
    except FileNotFoundError:
        return f"Error: directory not found: {path}"
    except NotADirectoryError:
        return f"Error: not a directory: {path}"
    except PermissionError:
        return f"Error: permission denied: {path}"

    if not entries:
        return "(empty directory)"

    lines = []
    for entry in entries:
        full = os.path.join(path, entry)
        suffix = "/" if os.path.isdir(full) else ""
        lines.append(f"{entry}{suffix}")

    result = "\n".join(lines)
    if len(result) > TOOL_OUTPUT_CAP:
        return result[:TOOL_OUTPUT_CAP] + "\n... (truncated)"
    return result
