"""Telegram bot entry point for inkagent."""

import asyncio
import logging
import os

from dotenv import load_dotenv
load_dotenv()

from telegram import BotCommand, Update  # noqa: E402
from telegram.constants import ChatAction  # noqa: E402
from telegram.ext import (  # noqa: E402
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from agent.brain import run_agent  # noqa: E402
from agent.compression import force_compress  # noqa: E402
from agent.providers import LLMError  # noqa: E402
from agent.scheduler import run_scheduler  # noqa: E402
from agent.session import get_conversation, reset_conversation, save_conversation  # noqa: E402
from agent.telegram_format import markdown_to_telegram_html  # noqa: E402

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
    """Send a message as Telegram HTML, splitting into chunks if needed."""
    html = markdown_to_telegram_html(text)
    for i in range(0, len(html), MAX_MSG_LEN):
        await update.message.reply_text(html[i:i + MAX_MSG_LEN], parse_mode="HTML")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    if not _is_owner(update, _get_owner_id()):
        return
    await update.message.reply_text("inkagent is online.")


async def new_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /new — reset conversation and start fresh."""
    if not _is_owner(update, _get_owner_id()):
        return
    session_id = f"tg_{update.effective_chat.id}"
    count = reset_conversation(session_id)
    await update.message.reply_text(f"New session started. ({count} messages archived)")


async def compact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /compact — force-compress conversation history."""
    if not _is_owner(update, _get_owner_id()):
        return
    session_id = f"tg_{update.effective_chat.id}"
    conversation = get_conversation(session_id)
    if len(conversation) <= 1:
        await update.message.reply_text("Nothing to compact.")
        return
    before, after = await asyncio.to_thread(force_compress, conversation)
    save_conversation(session_id)
    await update.message.reply_text(f"Compacted: {before} messages → {after}")


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
    app.add_handler(CommandHandler("new", new_command))
    app.add_handler(CommandHandler("compact", compact_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # --- Scheduler integration ---
    async def _send_scheduled_message(session_id: str, text: str) -> None:
        """Deliver a scheduled task reply to the right Telegram chat."""
        if not session_id.startswith("tg_"):
            logger.warning("Scheduler: skipping non-Telegram session %s", session_id)
            return
        chat_id = int(session_id.removeprefix("tg_"))
        html = markdown_to_telegram_html(text)
        for i in range(0, len(html), MAX_MSG_LEN):
            await app.bot.send_message(chat_id=chat_id, text=html[i:i + MAX_MSG_LEN], parse_mode="HTML")

    async def _post_init(_app) -> None:
        """Set bot command menu and start the cron scheduler."""
        await _app.bot.set_my_commands([
            BotCommand("new", "Start a new conversation"),
            BotCommand("compact", "Compress conversation history"),
        ])
        asyncio.create_task(run_scheduler(_send_scheduled_message))
        logger.info("Cron scheduler started")

    app.post_init = _post_init

    logger.info("Bot started — listening for messages from owner %s", owner_id)
    app.run_polling()


if __name__ == "__main__":
    main()
