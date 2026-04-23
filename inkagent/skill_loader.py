"""Markdown skill loader.

Scans ``skills/`` for SKILL.md files. Skills are user-maintained
markdown files — edit them directly in your editor.

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

from inkagent.config import SKILLS_DIR as _SKILLS_DIR_STR

logger = logging.getLogger(__name__)

SKILLS_DIR = Path(_SKILLS_DIR_STR)


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


def load_skills() -> list[dict[str, Any]]:
    """Discover and parse all eligible skills under ``skills/``."""
    if not SKILLS_DIR.is_dir():
        return []

    skills: list[dict[str, Any]] = []
    for child in sorted(SKILLS_DIR.iterdir()):
        if not child.is_dir():
            continue
        skill_file = child / "SKILL.md"
        if not skill_file.is_file():
            continue
        parsed = _parse_skill(skill_file)
        if parsed is not None:
            skills.append(parsed)

    skills.sort(key=lambda s: s["name"])
    logger.info("Loaded %d instruction skill(s)", len(skills))
    return skills


def build_skill_prompt(skills: list[dict[str, Any]]) -> str:
    """Build the skill section for the system prompt.

    Only emits skill name, description, and file path. The LLM uses
    ``read_file`` to load the full instructions on demand.
    """
    if not skills:
        return ""

    return "\n".join(
        f"- {s['name']}: {s['description']} → `{s['path']}`"
        for s in skills
    )
