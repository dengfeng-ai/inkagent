"""Markdown skill loader.

Scans skills/ (built-in, git-tracked) and user_skills/ (user overrides,
gitignored) for SKILL.md files.  When both directories contain a skill
with the same name, the user version wins.

Skill file format (YAML frontmatter + Markdown body)::

    ---
    name: daily_report
    description: Generate a daily summary from logs
    requires:
      env: [BRAVE_API_KEY]
      bins: [ffmpeg]
    ---

    Instructions for the LLM …
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILTIN_SKILLS_DIR = _PROJECT_ROOT / "skills"
USER_SKILLS_DIR = _PROJECT_ROOT / "user_skills"


def _check_requirements(requires: dict[str, Any]) -> bool:
    """Return True if all requirements are satisfied."""
    for var in requires.get("env", []):
        if not os.environ.get(var):
            return False
    for binary in requires.get("bins", []):
        if shutil.which(binary) is None:
            return False
    return True


def _parse_skill(path: Path) -> dict[str, Any] | None:
    """Parse a SKILL.md file into a skill dict.  Returns None on failure."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("Cannot read %s: %s", path, e)
        return None

    # Split YAML frontmatter from body.
    if not text.startswith("---"):
        logger.warning("No frontmatter in %s, skipping", path)
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        logger.warning("Malformed frontmatter in %s, skipping", path)
        return None

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        logger.warning("Bad YAML in %s: %s", path, e)
        return None

    name = meta.get("name")
    description = meta.get("description", "")
    if not name:
        logger.warning("Missing 'name' in %s, skipping", path)
        return None

    requires = meta.get("requires", {})
    if not _check_requirements(requires):
        logger.info("Skill '%s' skipped — unmet requirements", name)
        return None

    return {
        "name": name,
        "description": description,
        "path": str(path),
    }


def _scan_dir(directory: Path) -> dict[str, dict[str, Any]]:
    """Scan a single skills directory, returning {name: skill_dict}."""
    if not directory.is_dir():
        return {}

    found: dict[str, dict[str, Any]] = {}
    for child in sorted(directory.iterdir()):
        if not child.is_dir():
            continue
        skill_file = child / "SKILL.md"
        if not skill_file.is_file():
            continue
        skill = _parse_skill(skill_file)
        if skill is not None:
            found[skill["name"]] = skill
    return found


def load_skills() -> list[dict[str, Any]]:
    """Discover and parse all eligible skills.

    Scans built-in ``skills/`` first, then ``user_skills/``.
    User skills override built-in ones with the same name.
    """
    skills_by_name = _scan_dir(BUILTIN_SKILLS_DIR)
    user_skills = _scan_dir(USER_SKILLS_DIR)

    for name, skill in user_skills.items():
        if name in skills_by_name:
            logger.info("User skill '%s' overrides built-in", name)
        skills_by_name[name] = skill

    skills = sorted(skills_by_name.values(), key=lambda s: s["name"])
    logger.info("Loaded %d instruction skill(s)", len(skills))
    return skills


def build_skill_prompt(skills: list[dict[str, Any]]) -> str:
    """Build the skill section for the system prompt.

    Only includes skill name, description, and file path.
    The LLM uses read_file to load the full instructions when needed,
    and edit_skill to modify them (copy-on-write to user_skills/).
    """
    if not skills:
        return ""

    lines: list[str] = []
    for s in skills:
        lines.append(f"- {s['name']}: {s['description']} → `{s['path']}`")
    lines.append("")
    lines.append(
        "To modify a skill, use the edit_skill tool (not edit_file). "
        "It handles copy-on-write to user_skills/ automatically."
    )

    return "\n".join(lines)
