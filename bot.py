"""Telegram bot entry point for inkagent."""

import asyncio
import logging
import os

from dotenv import load_dotenv
load_dotenv()

from telegram import Update  # noqa: E402
from telegram.constants import ChatAction  # noqa: E402
from telegram.ext import (  # noqa: E402
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from agent.brain import run_agent  # noqa: E402
from agent.providers import LLMError  # noqa: E402

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Telegram message length limit.
MAX_MSG_LEN = 4096


def _get_owner_id() -> int:
    raw = os.environ.get("TELEGRAM_OWNER_ID")
    if not raw:
        raise SystemExit("Error: TELEGRAM_OWNER_ID is not set. Check your .env file.")
    return int(raw)


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

    async def keep_typing() -> None:
        """Send typing action every 4s until cancelled."""
        while True:
            await update.effective_chat.send_action(ChatAction.TYPING)
            await asyncio.sleep(4)

    typing_task = asyncio.create_task(keep_typing())
    try:
        reply = await asyncio.to_thread(run_agent, user_text, session_id)
    except LLMError as e:
        logger.error("API call failed in session %s: %s", session_id, e)
        reply = f"[API error: {e}]"
    finally:
        typing_task.cancel()

    await _send_long_message(update, reply)


def main() -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise SystemExit("Error: TELEGRAM_BOT_TOKEN is not set. Check your .env file.")
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Error: OPENAI_API_KEY is not set. Check your .env file.")
    elif provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Error: ANTHROPIC_API_KEY is not set. Check your .env file.")
    owner_id = _get_owner_id()

    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started — listening for messages from owner %s", owner_id)
    app.run_polling()


if __name__ == "__main__":
    main()
