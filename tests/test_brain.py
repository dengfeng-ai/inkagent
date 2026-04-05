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
    "inkagent.brain.registry.get_tools": MagicMock(return_value=[]),
}


@pytest.fixture()
def brain_env(tmp_memory_dir):
    """Patch all brain dependencies and return provider module bindings."""
    patches = {k: patch(k, v) for k, v in _BRAIN_PATCHES.items()}
    for p in patches.values():
        p.start()

    provider = MagicMock()
    provider.format_tools.return_value = []
    provider.assistant_message.return_value = {"role": "assistant", "content": ""}
    provider.tool_results_messages.return_value = [{"role": "user", "content": ""}]

    p_provider = patch("inkagent.brain.get_provider", return_value=provider)
    p_provider.start()

    from inkagent.brain import run_agent, stream_agent

    yield provider, run_agent, stream_agent

    p_provider.stop()
    for p in patches.values():
        p.stop()


class TestSingleTurn:
    def test_returns_text(self, brain_env):
        provider, run_agent, _ = brain_env
        provider.complete.return_value = _make_response(text="hello world")

        assert run_agent("Hi") == "hello world"

    def test_empty_text_returns_empty_string(self, brain_env):
        provider, run_agent, _ = brain_env
        provider.complete.return_value = _make_response(text=None)

        assert run_agent("Hi") == ""


class TestToolLoop:
    @patch("inkagent.brain.registry.call_tool", return_value="42")
    def test_tool_then_final_text(self, mock_tool, brain_env):
        provider, run_agent, _ = brain_env
        provider.complete.side_effect = [
            _make_response(
                text="Thinking...",
                stop_reason="tool_use",
                tool_calls=[ToolCall(id="1", name="calc", input={"x": 1})],
            ),
            _make_response(text="Answer: 42", stop_reason="end_turn"),
        ]

        reply = run_agent("What is 6*7?")

        assert reply == "Thinking...\nAnswer: 42"
        mock_tool.assert_called_once_with("calc", {"x": 1})
        assert provider.complete.call_count == 2


class TestStreaming:
    def test_stream_agent_invokes_callback_with_final_reply(self, brain_env):
        provider, _, stream_agent = brain_env

        def fake_stream_complete(*, model, system, messages, tools, max_tokens, on_text):
            on_text("hello ")
            on_text("world")
            return _make_response(text="hello world")

        provider.stream_complete = MagicMock(side_effect=fake_stream_complete)
        seen = []

        reply = stream_agent("Hi", on_stream=seen.append)

        assert reply == "hello world"
        # Should receive incremental snapshots from deltas, plus the final push.
        assert "hello" in seen[0]
        assert "hello world" in seen[-1]

    @patch("inkagent.brain.registry.call_tool", return_value="42")
    def test_stream_agent_accumulates_tool_round_text(self, mock_tool, brain_env):
        provider, _, stream_agent = brain_env

        call_count = 0

        def fake_stream_complete(*, model, system, messages, tools, max_tokens, on_text):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                on_text("Thinking...")
                return _make_response(
                    text="Thinking...",
                    stop_reason="tool_use",
                    tool_calls=[ToolCall(id="1", name="calc", input={"x": 1})],
                )
            else:
                on_text("Answer: 42")
                return _make_response(text="Answer: 42", stop_reason="end_turn")

        provider.stream_complete = MagicMock(side_effect=fake_stream_complete)
        seen = []

        reply = stream_agent("What is 6*7?", on_stream=seen.append)

        assert reply == "Thinking...\nAnswer: 42"
        # Second round should include text from both rounds.
        assert any("Thinking..." in s and "Answer: 42" in s for s in seen)
        mock_tool.assert_called_once_with("calc", {"x": 1})


class TestErrors:
    def test_llm_error_bubbles_up(self, brain_env):
        provider, run_agent, _ = brain_env
        provider.complete.side_effect = LLMError("boom")

        with pytest.raises(LLMError, match="boom"):
            run_agent("Hi")
