"""Tests for Markdown skill loader — discovery and parsing."""

import os

import pytest

from inkagent.skill_loader import (
    _check_requirements,
    _parse_skill,
    build_skill_prompt,
    load_skills,
)
import inkagent.skill_loader as skill_loader


pytestmark = pytest.mark.usefixtures("tmp_memory_dir")

VALID_SKILL = """\
---
name: test_skill
description: A test skill
---

Do something useful.
"""


def _create_skill(base_dir, name: str, content: str) -> None:
    """Write a SKILL.md inside base_dir/name/."""
    skill_dir = base_dir / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(content)


# ---------------------------------------------------------------------------
# _check_requirements
# ---------------------------------------------------------------------------

class TestCheckRequirements:
    def test_empty_requirements(self):
        assert _check_requirements({}) is True

    def test_env_present(self, monkeypatch):
        monkeypatch.setenv("MY_TEST_KEY", "value")
        assert _check_requirements({"env": ["MY_TEST_KEY"]}) is True

    def test_env_missing(self, monkeypatch):
        monkeypatch.delenv("MY_TEST_KEY", raising=False)
        assert _check_requirements({"env": ["MY_TEST_KEY"]}) is False

    def test_bin_present(self):
        # 'python' should exist on PATH in test environments
        assert _check_requirements({"bins": ["python3"]}) is True

    def test_bin_missing(self):
        assert _check_requirements({"bins": ["nonexistent_bin_xyz_123"]}) is False

    def test_mixed_all_met(self, monkeypatch):
        monkeypatch.setenv("MY_TEST_KEY", "v")
        assert _check_requirements({"env": ["MY_TEST_KEY"], "bins": ["python3"]}) is True

    def test_mixed_partial(self, monkeypatch):
        monkeypatch.delenv("MY_TEST_KEY", raising=False)
        assert _check_requirements({"env": ["MY_TEST_KEY"], "bins": ["python3"]}) is False


# ---------------------------------------------------------------------------
# _parse_skill
# ---------------------------------------------------------------------------

class TestParseSkill:
    def test_valid_skill(self, tmp_path):
        _create_skill(tmp_path, "good", VALID_SKILL)
        result = _parse_skill(tmp_path / "good" / "SKILL.md")
        assert result is not None
        assert result["name"] == "test_skill"
        assert result["description"] == "A test skill"

    def test_no_frontmatter(self, tmp_path):
        _create_skill(tmp_path, "bad", "Just plain text, no frontmatter.")
        assert _parse_skill(tmp_path / "bad" / "SKILL.md") is None

    def test_malformed_yaml(self, tmp_path):
        _create_skill(tmp_path, "bad_yaml", "---\n: [invalid\n---\nbody")
        assert _parse_skill(tmp_path / "bad_yaml" / "SKILL.md") is None

    def test_missing_name(self, tmp_path):
        content = "---\ndescription: no name field\n---\nbody"
        _create_skill(tmp_path, "no_name", content)
        assert _parse_skill(tmp_path / "no_name" / "SKILL.md") is None

    def test_unmet_env_requirement(self, tmp_path, monkeypatch):
        content = "---\nname: gated\ndescription: x\nrequires:\n  env: [MISSING_KEY_XYZ]\n---\nbody"
        monkeypatch.delenv("MISSING_KEY_XYZ", raising=False)
        _create_skill(tmp_path, "gated", content)
        assert _parse_skill(tmp_path / "gated" / "SKILL.md") is None

    def test_nonexistent_file(self, tmp_path):
        assert _parse_skill(tmp_path / "nope" / "SKILL.md") is None


# ---------------------------------------------------------------------------
# load_skills — discovery and override priority
# ---------------------------------------------------------------------------

class TestLoadSkills:
    def test_discovers_skills(self):
        _create_skill(skill_loader.SKILLS_DIR, "alpha", VALID_SKILL)
        skills = load_skills()
        names = [s["name"] for s in skills]
        assert "test_skill" in names

    def test_empty_directory(self):
        skills = load_skills()
        assert skills == []

    def test_sorted_by_name(self):
        _create_skill(
            skill_loader.SKILLS_DIR, "zz",
            "---\nname: zeta\ndescription: z\n---\nbody",
        )
        _create_skill(
            skill_loader.SKILLS_DIR, "aa",
            "---\nname: alpha\ndescription: a\n---\nbody",
        )
        skills = load_skills()
        names = [s["name"] for s in skills]
        assert names == sorted(names)

    def test_skips_non_directory_files(self):
        """Files directly in skills/ (not in subdirectories) are ignored."""
        (skill_loader.SKILLS_DIR / "stray_file.md").write_text("junk")
        skills = load_skills()
        assert skills == []

    def test_skips_directory_without_skill_md(self):
        (skill_loader.SKILLS_DIR / "empty_dir").mkdir()
        skills = load_skills()
        assert skills == []


# ---------------------------------------------------------------------------
# build_skill_prompt
# ---------------------------------------------------------------------------

class TestBuildSkillPrompt:
    def test_empty_list(self):
        assert build_skill_prompt([]) == ""

    def test_format(self):
        skills = [
            {"name": "foo", "description": "does foo", "path": "/p/foo/SKILL.md"},
            {"name": "bar", "description": "does bar", "path": "/p/bar/SKILL.md"},
        ]
        result = build_skill_prompt(skills)
        assert "- foo: does foo" in result
        assert "- bar: does bar" in result
        assert "/p/foo/SKILL.md" in result
