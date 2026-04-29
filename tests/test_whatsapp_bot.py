"""Tests for the WhatsApp bot adapter.

Exercise the platform-agnostic process_message() and helpers without
spinning up neonize — the neonize event machinery is mocked away by
calling process_message() directly with a fake send_fn.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inkagent.whatsapp_bot import (
    MAX_MSG_LEN,
    _extract_text,
    _is_owner,
    _keep_composing,
    _normalize_phone,
    _resolve_sender_phone,
    _split_for_whatsapp,
    process_message,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def test_normalize_phone_strips_plus_and_punctuation():
    assert _normalize_phone("+1 234-567 8900") == "12345678900"


def test_normalize_phone_strips_jid_suffix():
    assert _normalize_phone("6591234567@s.whatsapp.net") == "6591234567"


def test_normalize_phone_strips_device_suffix():
    assert _normalize_phone("6591234567:1@s.whatsapp.net") == "6591234567"


def test_is_owner_match():
    assert _is_owner("6591234567", "6591234567") is True


def test_is_owner_match_with_jid_form():
    assert _is_owner("6591234567:1@s.whatsapp.net", "6591234567") is True


def test_is_owner_mismatch():
    assert _is_owner("6599999999", "6591234567") is False


def test_split_short_text_single_chunk():
    assert _split_for_whatsapp("hello") == ["hello"]


def test_split_empty_text_returns_empty_list():
    assert _split_for_whatsapp("") == []


def test_split_long_text_splits_at_limit():
    text = "a" * (MAX_MSG_LEN + 100)
    chunks = _split_for_whatsapp(text)
    assert len(chunks) == 2
    assert chunks[0] == "a" * MAX_MSG_LEN
    assert chunks[1] == "a" * 100


def test_split_exactly_at_limit():
    text = "b" * MAX_MSG_LEN
    assert _split_for_whatsapp(text) == [text]


def test_resolve_sender_phone_when_sender_is_phone():
    source = MagicMock()
    source.Sender.Server = "s.whatsapp.net"
    source.Sender.User = "6586833896"
    assert _resolve_sender_phone(source) == "6586833896"


def test_resolve_sender_phone_falls_back_to_alt_for_lid():
    """When WhatsApp routes via LID addressing, Sender carries the LID and
    the real phone-number JID is in SenderAlt."""
    source = MagicMock()
    source.Sender.Server = "lid"
    source.Sender.User = "186972861677582"  # LID, not a phone
    source.SenderAlt.IsEmpty = False
    source.SenderAlt.User = "6586833896"
    source.SenderAlt.Server = "s.whatsapp.net"
    assert _resolve_sender_phone(source) == "6586833896"


def test_resolve_sender_phone_returns_sender_when_alt_is_empty():
    source = MagicMock()
    source.Sender.Server = "lid"
    source.Sender.User = "186972861677582"
    source.SenderAlt.IsEmpty = True
    assert _resolve_sender_phone(source) == "186972861677582"


def test_extract_text_from_conversation():
    msg = MagicMock()
    msg.conversation = "hello"
    msg.extendedTextMessage = None
    assert _extract_text(msg) == "hello"


def test_extract_text_from_extended():
    msg = MagicMock()
    msg.conversation = ""
    msg.extendedTextMessage.text = "extended hi"
    assert _extract_text(msg) == "extended hi"


def test_extract_text_returns_empty_for_no_text():
    msg = MagicMock(spec=[])  # no attributes
    assert _extract_text(msg) == ""


# ---------------------------------------------------------------------------
# process_message routing
# ---------------------------------------------------------------------------

OWNER = "6591234567"
CHAT_JID = MagicMock(name="chat_jid")


def _run(coro):
    return asyncio.run(coro)


def test_stranger_is_ignored():
    send = AsyncMock()
    _run(process_message("hi", "6599999999", CHAT_JID, OWNER, send))
    send.assert_not_awaited()


def test_empty_text_is_ignored():
    send = AsyncMock()
    _run(process_message("   ", OWNER, CHAT_JID, OWNER, send))
    send.assert_not_awaited()


@patch("inkagent.whatsapp_bot.run_agent", return_value="agent reply")
def test_owner_message_invokes_agent(mock_agent):
    send = AsyncMock()
    _run(process_message("hello", OWNER, CHAT_JID, OWNER, send))

    mock_agent.assert_called_once()
    args = mock_agent.call_args.args
    assert args[0] == "hello"
    assert args[1] == f"wa_{OWNER}"
    send.assert_awaited_once_with(CHAT_JID, "agent reply")


@patch("inkagent.whatsapp_bot.run_agent", return_value="**bold** message")
def test_reply_is_formatted_for_whatsapp(mock_agent):
    send = AsyncMock()
    _run(process_message("hi", OWNER, CHAT_JID, OWNER, send))
    send.assert_awaited_once_with(CHAT_JID, "*bold* message")


@patch("inkagent.whatsapp_bot.run_agent", return_value="x" * (MAX_MSG_LEN + 50))
def test_long_reply_is_chunked(mock_agent):
    send = AsyncMock()
    _run(process_message("hi", OWNER, CHAT_JID, OWNER, send))
    assert send.await_count == 2
    first = send.await_args_list[0].args[1]
    second = send.await_args_list[1].args[1]
    assert len(first) == MAX_MSG_LEN
    assert len(second) == 50


@patch("inkagent.providers.get_model", return_value="claude-opus-4-7")
@patch("inkagent.whatsapp_bot.reset_conversation", return_value=3)
def test_new_command_resets_session(mock_reset, mock_get_model):
    send = AsyncMock()
    _run(process_message("/new", OWNER, CHAT_JID, OWNER, send))
    mock_reset.assert_called_once_with(f"wa_{OWNER}")
    send.assert_awaited_once_with(
        CHAT_JID, "New session started. Model: claude-opus-4-7"
    )


@patch("inkagent.whatsapp_bot.get_conversation", return_value=[{"role": "user"}])
def test_compact_with_nothing_to_do(mock_get):
    send = AsyncMock()
    _run(process_message("/compact", OWNER, CHAT_JID, OWNER, send))
    send.assert_awaited_once_with(CHAT_JID, "Nothing to compact.")


@patch("inkagent.whatsapp_bot.save_conversation")
@patch("inkagent.whatsapp_bot.force_compress", return_value=(10, 4))
@patch(
    "inkagent.whatsapp_bot.get_conversation",
    return_value=[{"role": "user"}, {"role": "assistant"}],
)
def test_compact_runs_compression(mock_get, mock_compress, mock_save):
    send = AsyncMock()
    _run(process_message("/compact", OWNER, CHAT_JID, OWNER, send))
    mock_compress.assert_called_once()
    mock_save.assert_called_once_with(f"wa_{OWNER}")
    send.assert_awaited_once()
    assert "Compacted: 10 messages -> 4" in send.await_args.args[1]


@patch("inkagent.whatsapp_bot.run_agent", side_effect=Exception("boom"))
def test_unexpected_error_propagates(mock_agent):
    """process_message lets non-LLMError exceptions bubble up; the
    neonize handler in main() catches and logs them."""
    send = AsyncMock()
    with pytest.raises(Exception, match="boom"):
        _run(process_message("hi", OWNER, CHAT_JID, OWNER, send))


@patch("inkagent.whatsapp_bot.save_conversation")
@patch("inkagent.whatsapp_bot.run_agent")
def test_llm_error_is_reported_to_user(mock_agent, mock_save):
    from inkagent.providers import LLMError
    mock_agent.side_effect = LLMError("rate limited")
    send = AsyncMock()
    _run(process_message("hi", OWNER, CHAT_JID, OWNER, send))
    send.assert_awaited_once()
    assert "[API error: rate limited]" in send.await_args.args[1]


# ---------------------------------------------------------------------------
# Typing indicator (composing presence)
# ---------------------------------------------------------------------------

def test_keep_composing_sends_at_least_once_then_exits():
    from neonize.utils.enum import ChatPresence, ChatPresenceMedia
    client = MagicMock()
    client.send_chat_presence = AsyncMock()

    async def _scenario():
        done = asyncio.Event()
        task = asyncio.create_task(_keep_composing(client, CHAT_JID, done))
        # Yield control so the task sends its first presence.
        await asyncio.sleep(0)
        done.set()
        await task

    _run(_scenario())

    assert client.send_chat_presence.await_count >= 1
    args = client.send_chat_presence.await_args_list[0].args
    assert args[0] is CHAT_JID
    assert args[1] is ChatPresence.CHAT_PRESENCE_COMPOSING
    assert args[2] is ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT


def test_keep_composing_stops_on_send_error():
    client = MagicMock()
    client.send_chat_presence = AsyncMock(side_effect=RuntimeError("ws closed"))

    async def _scenario():
        done = asyncio.Event()
        await asyncio.wait_for(
            _keep_composing(client, CHAT_JID, done), timeout=1.0
        )

    _run(_scenario())  # should not hang or raise — error swallowed
    client.send_chat_presence.assert_awaited_once()
