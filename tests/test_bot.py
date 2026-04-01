"""Tests for the Telegram bot adapter."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from inkagent.bot import _is_owner, _send_long_message, handle_message, start_command, MAX_MSG_LEN


# --- Helpers ---

def _make_update(user_id: int, text: str = "hello", chat_id: int = 999) -> MagicMock:
    """Build a fake Telegram Update with the given user/chat/text."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = chat_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    return update


# --- _is_owner ---

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


# --- _send_long_message ---

@pytest.mark.asyncio
async def test_send_short_message():
    update = _make_update(user_id=1)
    await _send_long_message(update, "short reply")
    update.message.reply_text.assert_awaited_once_with("short reply")


@pytest.mark.asyncio
async def test_send_long_message_splits():
    update = _make_update(user_id=1)
    long_text = "a" * (MAX_MSG_LEN + 100)
    await _send_long_message(update, long_text)

    calls = update.message.reply_text.await_args_list
    assert len(calls) == 2
    assert calls[0].args[0] == "a" * MAX_MSG_LEN
    assert calls[1].args[0] == "a" * 100


@pytest.mark.asyncio
async def test_send_exact_limit():
    update = _make_update(user_id=1)
    text = "b" * MAX_MSG_LEN
    await _send_long_message(update, text)
    update.message.reply_text.assert_awaited_once_with(text)


# --- handle_message ---

@pytest.mark.asyncio
@patch("inkagent.bot._get_owner_id", return_value=123)
@patch("inkagent.bot.run_agent", return_value="agent reply")
async def test_handle_message_owner(mock_agent, mock_owner):
    update = _make_update(user_id=123, text="hi", chat_id=42)
    await handle_message(update, MagicMock())

    mock_agent.assert_called_once_with("hi", "tg_42")
    update.message.reply_text.assert_awaited_once_with("agent reply")


@pytest.mark.asyncio
@patch("inkagent.bot._get_owner_id", return_value=123)
@patch("inkagent.bot.run_agent")
async def test_handle_message_stranger_ignored(mock_agent, mock_owner):
    update = _make_update(user_id=999, text="hi")
    await handle_message(update, MagicMock())

    mock_agent.assert_not_called()
    update.message.reply_text.assert_not_awaited()


@pytest.mark.asyncio
@patch("inkagent.bot._get_owner_id", return_value=123)
@patch("inkagent.bot.run_agent")
async def test_handle_message_empty_text(mock_agent, mock_owner):
    update = _make_update(user_id=123)
    update.message.text = None
    await handle_message(update, MagicMock())

    mock_agent.assert_not_called()


# --- start_command ---

@pytest.mark.asyncio
@patch("inkagent.bot._get_owner_id", return_value=123)
async def test_start_command_owner(mock_owner):
    update = _make_update(user_id=123)
    await start_command(update, MagicMock())
    update.message.reply_text.assert_awaited_once_with("inkagent is online.")


@pytest.mark.asyncio
@patch("inkagent.bot._get_owner_id", return_value=123)
async def test_start_command_stranger(mock_owner):
    update = _make_update(user_id=999)
    await start_command(update, MagicMock())
    update.message.reply_text.assert_not_awaited()
