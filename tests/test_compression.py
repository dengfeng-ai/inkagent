"""Tests for context window estimation and conversation compression."""

from unittest.mock import patch

import pytest

from inkagent.compression import (
    _format_messages_for_summary,
    estimate_tokens,
    force_compress,
    maybe_compress,
)
from inkagent.config import (
    CHARS_PER_TOKEN,
    COMPRESS_THRESHOLD,
    KEEP_RECENT_MESSAGES,
)
from inkagent.session import make_message


# ---------------------------------------------------------------------------
# estimate_tokens
# ---------------------------------------------------------------------------

class TestEstimateTokens:
    def test_basic_estimation(self):
        system = "a" * 100
        messages = [{"content": "b" * 200}]
        tools = [{"name": "t", "desc": "d"}]
        result = estimate_tokens(system, messages, tools)
        # 100 chars system + 200 chars message + tools JSON / CHARS_PER_TOKEN
        assert result > 0
        assert isinstance(result, int)

    def test_empty_inputs(self):
        assert estimate_tokens("", [], []) == 0

    def test_list_content(self):
        """Messages with list content (tool results) should be counted."""
        messages = [{"content": [{"type": "text", "text": "x" * 400}]}]
        result = estimate_tokens("", messages, [])
        assert result > 0

    def test_scales_with_content(self):
        small = estimate_tokens("a" * 100, [], [])
        large = estimate_tokens("a" * 10000, [], [])
        assert large > small


# ---------------------------------------------------------------------------
# _format_messages_for_summary
# ---------------------------------------------------------------------------

class TestFormatMessagesForSummary:
    def test_string_content(self):
        msgs = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi there"},
        ]
        result = _format_messages_for_summary(msgs)
        assert "User: hello" in result
        assert "Assistant: hi there" in result

    def test_list_content_with_text(self):
        msgs = [{"role": "assistant", "content": [
            {"type": "text", "text": "some text"},
        ]}]
        result = _format_messages_for_summary(msgs)
        assert "some text" in result

    def test_list_content_with_tool_result(self):
        msgs = [{"role": "user", "content": [
            {"type": "tool_result", "content": "long " * 100},
        ]}]
        result = _format_messages_for_summary(msgs)
        assert "[tool result:" in result
        # tool result content is truncated to 200 chars
        assert len(result) < 300

    def test_empty_messages(self):
        assert _format_messages_for_summary([]) == ""


# ---------------------------------------------------------------------------
# force_compress
# ---------------------------------------------------------------------------

class TestForceCompress:
    def _make_conversation(self, n: int) -> list[dict]:
        """Build a conversation with n alternating user/assistant messages."""
        conv = []
        for i in range(n):
            role = "user" if i % 2 == 0 else "assistant"
            conv.append(make_message(role, f"msg {i}"))
        return conv

    @patch("inkagent.compression._summarize_messages", return_value="summary of old stuff")
    def test_compresses_long_conversation(self, mock_summarize):
        conv = self._make_conversation(20)
        before, after = force_compress(conv)
        assert before == 20
        assert after < before
        # First two messages are the summary pair
        assert "Summary of previous conversation" in conv[0]["content"]
        assert "summary of old stuff" in conv[0]["content"]
        assert conv[1]["role"] == "assistant"
        # Recent messages preserved
        assert len(conv) == KEEP_RECENT_MESSAGES + 2  # summary pair + kept

    def test_no_compress_when_few_messages(self):
        conv = self._make_conversation(KEEP_RECENT_MESSAGES)
        before, after = force_compress(conv)
        assert before == after
        assert len(conv) == KEEP_RECENT_MESSAGES

    @patch("inkagent.compression._summarize_messages", return_value="compressed")
    def test_split_aligns_to_user_boundary(self, mock_summarize):
        # Build conversation where naive split would land on assistant
        conv = self._make_conversation(KEEP_RECENT_MESSAGES + 3)
        # The kept portion starts from the end; if split lands on assistant,
        # it should shift back by 1.
        force_compress(conv)
        # After compression: summary_user, summary_assistant, then kept messages.
        # The first kept message (index 2) should be a user message.
        assert conv[2]["role"] == "user"


# ---------------------------------------------------------------------------
# maybe_compress
# ---------------------------------------------------------------------------

class TestMaybeCompress:
    def test_no_compress_below_threshold(self):
        conv = [make_message("user", "short")]
        original_len = len(conv)
        maybe_compress(conv, "sys", [])
        assert len(conv) == original_len

    @patch("inkagent.compression._summarize_messages", return_value="summarized")
    def test_compresses_above_threshold(self, mock_summarize):
        # Build conversation large enough to trigger compression
        big_content = "x" * (COMPRESS_THRESHOLD * CHARS_PER_TOKEN)
        conv = [
            make_message("user", big_content),
            make_message("assistant", "ok"),
        ]
        # Add enough messages to exceed KEEP_RECENT_MESSAGES
        for i in range(KEEP_RECENT_MESSAGES + 2):
            role = "user" if i % 2 == 0 else "assistant"
            conv.append(make_message(role, f"msg {i}"))
        before_len = len(conv)
        maybe_compress(conv, "", [])
        assert len(conv) < before_len
        assert "Summary" in conv[0]["content"]

    def test_no_compress_when_few_messages_even_if_large(self):
        """Even if tokens are high, don't compress if not enough messages."""
        big = "x" * (COMPRESS_THRESHOLD * CHARS_PER_TOKEN)
        conv = [make_message("user", big)]
        maybe_compress(conv, "", [])
        assert len(conv) == 1
