"""Tests for the Telegram bot adapter."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from inkagent.bot import (
    _is_owner,
    _send_long_message,
    handle_message,
    start_command,
    MAX_MSG_LEN,
    TelegramStreamBuffer,
)


def _make_update(user_id: int, text: str = "hello", chat_id: int = 999) -> MagicMock:
    """Build a fake Telegram Update with the given user/chat/text."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = chat_id
    update.effective_chat.send_action = AsyncMock()
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


def test_is_owner_true():
    update = _make_update(user_id=123)
    assert _is_owner(update, owner_id=123) is True


def test_is_owner_false():
    update = _make_update(user_id=456)
    assert _is_owner(update, owner_id=123) is False


def test_is_owner_no_user():
    update = MagicMock()
    update.effective_user = None
    assert _is_owner(update, owner_id=123) is False


def test_send_short_message():
    update = _make_update(user_id=1)
    asyncio.run(_send_long_message(update, "short reply"))
    update.message.reply_text.assert_awaited_once_with("short reply", parse_mode="HTML")


def test_send_long_message_splits():
    update = _make_update(user_id=1)
    long_text = "a" * (MAX_MSG_LEN + 100)
    asyncio.run(_send_long_message(update, long_text))

    calls = update.message.reply_text.await_args_list
    assert len(calls) == 2
    assert calls[0].args[0] == "a" * MAX_MSG_LEN
    assert calls[1].args[0] == "a" * 100


def test_send_exact_limit():
    update = _make_update(user_id=1)
    text = "b" * MAX_MSG_LEN
    asyncio.run(_send_long_message(update, text))
    update.message.reply_text.assert_awaited_once_with(text, parse_mode="HTML")


def test_stream_buffer_sends_then_edits():
    update = _make_update(user_id=1)
    sent_message = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=sent_message)
    buffer = TelegramStreamBuffer(update)

    buffer.push("hello")
    asyncio.run(buffer.flush(force=True))
    sent_message.edit_text.reset_mock()

    buffer.push("hello world")
    asyncio.run(buffer.flush(force=True))

    sent_message.edit_text.assert_awaited_once_with("hello world", parse_mode="HTML")


@patch("inkagent.bot._get_owner_id", return_value=123)
@patch("inkagent.bot.stream_agent", return_value="agent reply")
def test_handle_message_owner(mock_agent, mock_owner):
    update = _make_update(user_id=123, text="hi", chat_id=42)
    sent_message = AsyncMock()
    update.message.reply_text = AsyncMock(return_value=sent_message)

    asyncio.run(handle_message(update, MagicMock()))

    mock_agent.assert_called_once()
    args = mock_agent.call_args.args
    assert args[0] == "hi"
    assert args[1] == "tg_42"
    assert callable(args[2])
    update.message.reply_text.assert_awaited_once_with("agent reply", parse_mode="HTML")
    sent_message.edit_text.assert_not_awaited()


@patch("inkagent.bot._get_owner_id", return_value=123)
@patch("inkagent.bot.stream_agent")
def test_handle_message_stranger_ignored(mock_agent, mock_owner):
    update = _make_update(user_id=999, text="hi")
    asyncio.run(handle_message(update, MagicMock()))

    mock_agent.assert_not_called()
    update.message.reply_text.assert_not_awaited()


@patch("inkagent.bot._get_owner_id", return_value=123)
@patch("inkagent.bot.stream_agent")
def test_handle_message_empty_text(mock_agent, mock_owner):
    update = _make_update(user_id=123)
    update.message.text = None
    asyncio.run(handle_message(update, MagicMock()))

    mock_agent.assert_not_called()
    update.message.reply_text.assert_not_awaited()


@patch("inkagent.bot._get_owner_id", return_value=123)
@patch("inkagent.bot.stream_agent", side_effect=Exception("boom"))
def test_handle_message_error_propagates(mock_agent, mock_owner):
    update = _make_update(user_id=123, text="hi", chat_id=42)
    try:
        asyncio.run(handle_message(update, MagicMock()))
        assert False, "expected exception"
    except Exception as exc:
        assert "boom" in str(exc)


@patch("inkagent.bot._get_owner_id", return_value=123)
def test_start_owner(mock_owner):
    update = _make_update(user_id=123)
    asyncio.run(start_command(update, MagicMock()))
    update.message.reply_text.assert_awaited_once_with("inkagent is online.")


@patch("inkagent.bot._get_owner_id", return_value=123)
def test_start_stranger_ignored(mock_owner):
    update = _make_update(user_id=999)
    asyncio.run(start_command(update, MagicMock()))
    update.message.reply_text.assert_not_awaited()
