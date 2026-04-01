"""Tests for the tool registration system."""

from inkagent.registry import register, get_tools, call_tool, _skills
from inkagent.config import TOOL_OUTPUT_CAP


# ---------------------------------------------------------------------------
# register decorator
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_adds_tool(self):
        @register(
            name="test_echo",
            description="echoes input",
            input_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
        )
        def echo(msg: str) -> str:
            return msg

        assert "test_echo" in _skills
        assert _skills["test_echo"]["func"] is echo

    def test_decorated_function_unchanged(self):
        """The decorator should return the original function."""
        @register(name="test_identity", description="x", input_schema={})
        def original():
            return "ok"

        assert original() == "ok"


# ---------------------------------------------------------------------------
# get_tools
# ---------------------------------------------------------------------------

class TestGetTools:
    def test_returns_schema_without_func(self):
        @register(
            name="test_gt",
            description="desc",
            input_schema={"type": "object"},
        )
        def dummy():
            return ""

        tools = get_tools()
        match = [t for t in tools if t["name"] == "test_gt"]
        assert len(match) == 1
        assert match[0] == {
            "name": "test_gt",
            "description": "desc",
            "input_schema": {"type": "object"},
        }
        assert "func" not in match[0]


# ---------------------------------------------------------------------------
# call_tool
# ---------------------------------------------------------------------------

class TestCallTool:
    def test_call_returns_result(self):
        @register(name="test_add", description="add", input_schema={})
        def add(a: int, b: int) -> str:
            return str(a + b)

        assert call_tool("test_add", {"a": 1, "b": 2}) == "3"

    def test_unknown_tool(self):
        result = call_tool("nonexistent_tool_xyz", {})
        assert "unknown tool" in result.lower()

    def test_output_truncated_when_exceeds_cap(self):
        @register(name="test_long", description="long", input_schema={})
        def long_output() -> str:
            return "x" * (TOOL_OUTPUT_CAP + 500)

        result = call_tool("test_long", {})
        assert len(result) < TOOL_OUTPUT_CAP + 500
        assert result.startswith("x" * TOOL_OUTPUT_CAP)
        assert "truncated" in result

    def test_output_not_truncated_when_within_cap(self):
        @register(name="test_short", description="short", input_schema={})
        def short_output() -> str:
            return "y" * 10

        assert call_tool("test_short", {}) == "y" * 10

    def test_exception_returns_error_string(self):
        @register(name="test_boom", description="boom", input_schema={})
        def boom() -> str:
            raise RuntimeError("kaboom")

        result = call_tool("test_boom", {})
        assert "Error running test_boom" in result
        assert "kaboom" in result
