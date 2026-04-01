"""Tests for the LLM agentic loop in brain.py."""

from unittest.mock import MagicMock, patch

import pytest

from inkagent.providers.base import LLMResponse, ToolCall, Usage, LLMError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(text="hello", stop_reason="end_turn", tool_calls=None):
    return LLMResponse(
        text=text,
        stop_reason=stop_reason,
        tool_calls=tool_calls or [],
        usage=Usage(input_tokens=100, output_tokens=50),
    )


def _fake_provider(responses):
    """Create a mock provider that returns responses in sequence."""
    provider = MagicMock()
    provider.complete.side_effect = responses
    provider.format_tools.return_value = [{"name": "stub"}]
    provider.assistant_message.return_value = {"role": "assistant", "content": ""}
    provider.tool_results_messages.return_value = [{"role": "user", "content": "result"}]
    return provider


# Shared patches for all brain tests — isolate from real memory, session, etc.
_BRAIN_PATCHES = {
    "inkagent.brain.memory": MagicMock(
        get_identity=MagicMock(return_value="identity"),
        get_soul=MagicMock(return_value="soul"),
        get_user_profile=MagicMock(return_value="user"),
        get_long_term_memory=MagicMock(return_value="memories"),
        get_daily_logs=MagicMock(return_value="logs"),
        is_first_run=MagicMock(return_value=False),
    ),
    "inkagent.brain.load_skills": MagicMock(return_value=[]),
    "inkagent.brain.build_skill_prompt": MagicMock(return_value=""),
    "inkagent.brain.maybe_compress": MagicMock(),
    "inkagent.brain.maybe_promote": MagicMock(),
    "inkagent.brain.get_model": MagicMock(return_value="test-model"),
}


@pytest.fixture()
def brain_env(tmp_memory_dir):
    """Patch all brain dependencies and return (provider, run_agent)."""
    patches = {k: patch(k, v) for k, v in _BRAIN_PATCHES.items()}
    mocks = {k: p.start() for k, p in patches.items()}

    # Session needs real logic but pointed at tmp dir (via tmp_memory_dir)
    # Provider and registry need per-test control, so we patch them here
    provider = MagicMock()
    provider.format_tools.return_value = []
    provider.assistant_message.return_value = {"role": "assistant", "content": ""}
    provider.tool_results_messages.return_value = [{"role": "user", "content": ""}]

    p_provider = patch("inkagent.brain.get_provider", return_value=provider)
    p_provider.start()

    # Import after patching to avoid side-effects
    from inkagent.brain import run_agent

    yield provider, run_agent

    p_provider.stop()
    for p in patches.values():
        p.stop()


# ---------------------------------------------------------------------------
# Single turn — LLM returns end_turn immediately
# ---------------------------------------------------------------------------

class TestSingleTurn:
    def test_returns_text(self, brain_env):
        provider, run_agent = brain_env
        provider.complete.return_value = _make_response(text="hi there")
        result = run_agent("hello", "test_sid")
        assert result == "hi there"

    def test_calls_provider_once(self, brain_env):
        provider, run_agent = brain_env
        provider.complete.return_value = _make_response(text="ok")
        run_agent("hello", "test_sid")
        assert provider.complete.call_count == 1

    def test_empty_text_returns_empty(self, brain_env):
        provider, run_agent = brain_env
        provider.complete.return_value = _make_response(text=None)
        result = run_agent("hello", "test_sid")
        assert result == ""


# ---------------------------------------------------------------------------
# Tool use loop — LLM calls a tool, then returns end_turn
# ---------------------------------------------------------------------------

class TestToolLoop:
    def test_tool_executed_and_result_returned(self, brain_env):
        provider, run_agent = brain_env
        tool_call = ToolCall(id="tc1", name="test_tool", input={"q": "x"})
        provider.complete.side_effect = [
            _make_response(text="thinking...", stop_reason="tool_use", tool_calls=[tool_call]),
            _make_response(text="final answer"),
        ]

        with patch("inkagent.brain.registry") as mock_reg:
            mock_reg.get_tools.return_value = []
            mock_reg.call_tool.return_value = "tool output"
            result = run_agent("do something", "test_sid")

        assert result == "thinking...\nfinal answer"
        mock_reg.call_tool.assert_called_once_with("test_tool", {"q": "x"})

    def test_provider_receives_tool_results(self, brain_env):
        provider, run_agent = brain_env
        tool_call = ToolCall(id="tc1", name="t", input={})
        provider.complete.side_effect = [
            _make_response(stop_reason="tool_use", tool_calls=[tool_call]),
            _make_response(text="done"),
        ]

        with patch("inkagent.brain.registry") as mock_reg:
            mock_reg.get_tools.return_value = []
            mock_reg.call_tool.return_value = "result"
            run_agent("go", "test_sid")

        # assistant_message called to add the tool-use turn
        provider.assistant_message.assert_called_once()
        # tool_results_messages called with the tool output
        provider.tool_results_messages.assert_called_once()
        call_args = provider.tool_results_messages.call_args[0][0]
        assert call_args[0]["tool_call_id"] == "tc1"
        assert call_args[0]["content"] == "result"

    def test_multiple_tool_calls_in_one_turn(self, brain_env):
        provider, run_agent = brain_env
        tc1 = ToolCall(id="a", name="tool_a", input={})
        tc2 = ToolCall(id="b", name="tool_b", input={})
        provider.complete.side_effect = [
            _make_response(text=None, stop_reason="tool_use", tool_calls=[tc1, tc2]),
            _make_response(text="all done"),
        ]

        with patch("inkagent.brain.registry") as mock_reg:
            mock_reg.get_tools.return_value = []
            mock_reg.call_tool.side_effect = ["result_a", "result_b"]
            result = run_agent("multi", "test_sid")

        assert mock_reg.call_tool.call_count == 2
        assert result == "all done"


# ---------------------------------------------------------------------------
# MAX_TOOL_ROUNDS — tools dropped after limit to force text reply
# ---------------------------------------------------------------------------

class TestMaxToolRounds:
    def test_tools_dropped_after_limit(self, brain_env, monkeypatch):
        provider, run_agent = brain_env
        monkeypatch.setattr("inkagent.brain.MAX_TOOL_ROUNDS", 2)

        tc = ToolCall(id="tc", name="t", input={})
        # First 2 rounds: tool_use (no text). Third round (no tools): end_turn.
        provider.complete.side_effect = [
            _make_response(text=None, stop_reason="tool_use", tool_calls=[tc]),
            _make_response(text=None, stop_reason="tool_use", tool_calls=[tc]),
            _make_response(text="forced end"),
        ]

        with patch("inkagent.brain.registry") as mock_reg:
            mock_reg.get_tools.return_value = [{"name": "t"}]
            mock_reg.call_tool.return_value = "ok"
            result = run_agent("loop", "test_sid")

        assert result == "forced end"
        # Third call should have empty tools
        third_call = provider.complete.call_args_list[2]
        assert third_call.kwargs.get("tools") == [] or third_call[1].get("tools") == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_llm_error_propagates(self, brain_env):
        provider, run_agent = brain_env
        provider.complete.side_effect = LLMError("API down")

        with patch("inkagent.brain.registry") as mock_reg:
            mock_reg.get_tools.return_value = []
            with pytest.raises(LLMError, match="API down"):
                run_agent("hello", "test_sid")

    def test_llm_error_removes_dangling_user_message(self, brain_env):
        provider, run_agent = brain_env
        provider.complete.side_effect = LLMError("fail")

        from inkagent.session import get_conversation

        with patch("inkagent.brain.registry") as mock_reg:
            mock_reg.get_tools.return_value = []
            try:
                run_agent("hello", "err_sid")
            except LLMError:
                pass

        conv = get_conversation("err_sid")
        # The dangling user message should have been popped
        assert not any(m["role"] == "user" and m["content"] == "hello" for m in conv)
