"""Telegram bot entry point for inkagent."""

import asyncio
import logging
import os

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from agent.brain import run_agent

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Telegram message length limit.
MAX_MSG_LEN = 4096


def _get_owner_id() -> int:
    return int(os.environ["TELEGRAM_OWNER_ID"])


def _is_owner(update: Update, owner_id: int) -> bool:
    """Check if the message is from the bot owner."""
    return update.effective_user is not None and update.effective_user.id == owner_id


async def _send_long_message(update: Update, text: str) -> None:
    """Send a message, splitting into chunks if it exceeds Telegram's limit."""
    for i in range(0, len(text), MAX_MSG_LEN):
        await update.message.reply_text(text[i:i + MAX_MSG_LEN])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not _is_owner(update, _get_owner_id()):
        return
    await update.message.reply_text("inkagent is online.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming text messages."""
    if not _is_owner(update, _get_owner_id()):
        return

    user_text = update.message.text
    if not user_text:
        return

    session_id = f"tg_{update.effective_chat.id}"

    # Run the synchronous agent in a thread to avoid blocking the event loop.
    reply = await asyncio.to_thread(run_agent, user_text, session_id)
    await _send_long_message(update, reply)


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()

    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    owner_id = _get_owner_id()

    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started — listening for messages from owner %s", owner_id)
    app.run_polling()


if __name__ == "__main__":
    main()
