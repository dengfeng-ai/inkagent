"""Skill editing tool with copy-on-write to user_skills/."""

import os
import shutil

from inkagent.registry import register
from inkagent.skill_loader import BUILTIN_SKILLS_DIR, USER_SKILLS_DIR


def _resolve_skill_path(skill_name: str) -> tuple[str | None, str]:
    """Return (existing_source_or_None, user_target) for a skill name."""
    user_path = USER_SKILLS_DIR / skill_name / "SKILL.md"
    builtin_path = BUILTIN_SKILLS_DIR / skill_name / "SKILL.md"

    if user_path.is_file():
        return str(user_path), str(user_path)
    if builtin_path.is_file():
        return str(builtin_path), str(user_path)
    return None, str(user_path)


def _ensure_user_copy(skill_name: str) -> str:
    """Ensure the skill exists in user_skills/, copying from built-in if needed.

    Returns the user_skills path.
    """
    user_dir = USER_SKILLS_DIR / skill_name
    user_path = user_dir / "SKILL.md"

    if user_path.is_file():
        return str(user_path)

    builtin_dir = BUILTIN_SKILLS_DIR / skill_name
    if builtin_dir.is_dir():
        shutil.copytree(builtin_dir, user_dir)
        return str(user_path)

    # New skill — create directory
    os.makedirs(user_dir, exist_ok=True)
    return str(user_path)


@register(
    name="edit_skill",
    description=(
        "Create or edit an instruction skill. For built-in skills, automatically "
        "copies to user_skills/ before editing (copy-on-write). "
        "Use mode='write' to write full content, or mode='edit' to do a "
        "search-and-replace on the existing content."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "skill_name": {
                "type": "string",
                "description": "Skill directory name (e.g. 'heartbeat', 'daily_report')",
            },
            "mode": {
                "type": "string",
                "enum": ["write", "edit"],
                "description": "'write' to replace full content, 'edit' for search-and-replace",
            },
            "content": {
                "type": "string",
                "description": "Full SKILL.md content (required for mode='write')",
            },
            "old_string": {
                "type": "string",
                "description": "Exact string to find (required for mode='edit')",
            },
            "new_string": {
                "type": "string",
                "description": "Replacement string (required for mode='edit')",
            },
        },
        "required": ["skill_name", "mode"],
    },
)
def edit_skill(
    skill_name: str,
    mode: str,
    content: str = "",
    old_string: str = "",
    new_string: str = "",
) -> str:
    if mode == "write":
        if not content:
            return "Error: 'content' is required for mode='write'"
        target = _ensure_user_copy(skill_name)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Wrote skill '{skill_name}' to {target}"

    if mode == "edit":
        if not old_string:
            return "Error: 'old_string' is required for mode='edit'"
        target = _ensure_user_copy(skill_name)
        try:
            with open(target, "r", encoding="utf-8") as f:
                current = f.read()
        except FileNotFoundError:
            return f"Error: skill '{skill_name}' not found"

        count = current.count(old_string)
        if count == 0:
            return "Error: old_string not found in skill"
        if count > 1:
            return f"Error: old_string appears {count} times — must be unique"

        new_content = current.replace(old_string, new_string, 1)
        with open(target, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"Edited skill '{skill_name}' in {target}"

    return f"Error: unknown mode '{mode}', use 'write' or 'edit'"
