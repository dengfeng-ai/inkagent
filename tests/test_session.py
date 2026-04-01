"""Tests for conversation session management and JSON persistence."""

import json

import pytest

from inkagent import session
from inkagent.session import (
    get_conversation,
    inject_message,
    make_message,
    reset_conversation,
    save_conversation,
)


pytestmark = pytest.mark.usefixtures("tmp_memory_dir")


# ---------------------------------------------------------------------------
# make_message
# ---------------------------------------------------------------------------

class TestMakeMessage:
    def test_has_role_and_content(self):
        msg = make_message("user", "hello")
        assert msg["role"] == "user"
        assert msg["content"] == "hello"

    def test_has_timestamp(self):
        msg = make_message("assistant", "hi")
        assert "timestamp" in msg
        # ISO format: YYYY-MM-DDTHH:MM:SS...
        assert "T" in msg["timestamp"]


# ---------------------------------------------------------------------------
# get_conversation
# ---------------------------------------------------------------------------

class TestGetConversation:
    def test_returns_empty_list_for_new_session(self):
        conv = get_conversation("new_sid")
        assert conv == []

    def test_returns_same_list_on_second_call(self):
        conv1 = get_conversation("sid_a")
        conv1.append(make_message("user", "hi"))
        conv2 = get_conversation("sid_a")
        assert conv2 is conv1
        assert len(conv2) == 1

    def test_different_sessions_are_isolated(self):
        get_conversation("s1").append(make_message("user", "a"))
        get_conversation("s2").append(make_message("user", "b"))
        assert len(get_conversation("s1")) == 1
        assert len(get_conversation("s2")) == 1
        assert get_conversation("s1")[0]["content"] == "a"


# ---------------------------------------------------------------------------
# save_conversation
# ---------------------------------------------------------------------------

class TestSaveConversation:
    def test_creates_json_file(self):
        conv = get_conversation("save_test")
        conv.append(make_message("user", "ping"))
        conv.append(make_message("assistant", "pong"))
        save_conversation("save_test")

        files = list(session.CONVERSATIONS_DIR.glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert len(data) == 2
        assert data[0]["content"] == "ping"
        assert data[1]["content"] == "pong"

    def test_overwrites_same_file_on_second_save(self):
        conv = get_conversation("save2")
        conv.append(make_message("user", "first"))
        save_conversation("save2")
        conv.append(make_message("assistant", "second"))
        save_conversation("save2")

        files = list(session.CONVERSATIONS_DIR.glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert len(data) == 2


# ---------------------------------------------------------------------------
# reset_conversation
# ---------------------------------------------------------------------------

class TestResetConversation:
    def test_returns_message_count(self):
        conv = get_conversation("reset_test")
        conv.append(make_message("user", "a"))
        conv.append(make_message("assistant", "b"))
        count = reset_conversation("reset_test")
        assert count == 2

    def test_clears_conversation(self):
        conv = get_conversation("reset2")
        conv.append(make_message("user", "x"))
        reset_conversation("reset2")
        assert get_conversation("reset2") == []

    def test_saves_before_clearing(self):
        conv = get_conversation("reset3")
        conv.append(make_message("user", "saved"))
        reset_conversation("reset3")
        files = list(session.CONVERSATIONS_DIR.glob("*.json"))
        assert len(files) == 1

    def test_returns_zero_for_empty_session(self):
        count = reset_conversation("empty_session")
        assert count == 0


# ---------------------------------------------------------------------------
# inject_message
# ---------------------------------------------------------------------------

class TestInjectMessage:
    def test_appends_to_conversation(self):
        inject_message("inj_test", "user", "injected")
        conv = get_conversation("inj_test")
        assert len(conv) == 1
        assert conv[0]["content"] == "injected"
        assert conv[0]["role"] == "user"

    def test_persists_to_disk(self):
        inject_message("inj_persist", "assistant", "reply")
        files = list(session.CONVERSATIONS_DIR.glob("*.json"))
        assert len(files) == 1
        data = json.loads(files[0].read_text())
        assert data[0]["content"] == "reply"
