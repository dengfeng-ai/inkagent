"""Markdown skill loader.

Scans skills/ for SKILL.md files and builds skill sections
for the system prompt.

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

INSTRUCTIONS_DIR = Path(__file__).resolve().parent.parent / "skills"


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


def load_skills() -> list[dict[str, Any]]:
    """Discover and parse all eligible skills from the instructions directory."""
    if not INSTRUCTIONS_DIR.is_dir():
        return []

    skills: list[dict[str, Any]] = []
    for child in sorted(INSTRUCTIONS_DIR.iterdir()):
        if not child.is_dir():
            continue
        skill_file = child / "SKILL.md"
        if not skill_file.is_file():
            continue
        skill = _parse_skill(skill_file)
        if skill is not None:
            skills.append(skill)

    logger.info("Loaded %d instruction skill(s)", len(skills))
    return skills


def build_skill_prompt(skills: list[dict[str, Any]]) -> str:
    """Build the skill section for the system prompt.

    Only includes skill name, description, and file path.
    The LLM uses read_file to load the full instructions when needed.
    """
    if not skills:
        return ""

    lines: list[str] = []
    for s in skills:
        lines.append(f"- {s['name']}: {s['description']} → `{s['path']}`")

    return "\n".join(lines)
