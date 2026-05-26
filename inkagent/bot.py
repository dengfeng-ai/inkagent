"""Telegram bot entry point for inkagent."""

import asyncio
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass

# Windows console defaults to cp1252 / charmap, which can't encode emoji
# in log messages (e.g. avatar from IDENTITY.md). Force UTF-8.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

from telegram import BotCommand, Message, Update  # noqa: E402
from telegram.constants import ChatAction  # noqa: E402
from telegram.error import BadRequest, RetryAfter  # noqa: E402
from telegram.ext import (  # noqa: E402
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from inkagent.brain import run_agent, stream_agent  # noqa: E402
from inkagent.compression import force_compress  # noqa: E402
from inkagent.providers import LLMError  # noqa: E402
from inkagent.scheduler import run_scheduler  # noqa: E402
from inkagent.session import get_conversation, reset_conversation, save_conversation  # noqa: E402
from inkagent.telegram_format import markdown_to_telegram_html  # noqa: E402

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Telegram message length limit.
MAX_MSG_LEN = 4096
# Each streamed chunk is bounded below MAX_MSG_LEN so HTML markup expansion
# (markdown -> <b>/<i>/<pre> tags) doesn't push us over the wire limit.
CHUNK_SIZE = 3500
STREAM_THROTTLE_SECONDS = 1.5
TYPING_INTERVAL_SECONDS = 1.0
STREAM_PLACEHOLDER = "…"


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


@dataclass
class _Chunk:
    message: Message
    text: str
    sealed: bool = False


class TelegramStreamBuffer:
    """Stream text into Telegram across one-or-more chunked messages.

    Edits are confined to the trailing ("active") chunk; once content spills
    into a new chunk, the previous one is sealed and never edited again. This
    bounds the per-message edit rate, which is what Telegram flood-controls.
    """

    def __init__(self, update: Update) -> None:
        self._update = update
        self._chunks: list[_Chunk] = []
        self._latest_text = ""
        self._last_flushed_text = ""
        self._last_sent_at = 0.0
        self._lock = threading.Lock()

    def push(self, text: str) -> None:
        with self._lock:
            self._latest_text = text

    def should_flush(self, *, force: bool = False) -> bool:
        with self._lock:
            text = self._latest_text
        if not text:
            return False
        if text == self._last_flushed_text and not force:
            return False
        if force:
            return True
        return (time.monotonic() - self._last_sent_at) >= STREAM_THROTTLE_SECONDS

    async def flush(self, *, force: bool = False) -> None:
        with self._lock:
            text = self._latest_text
        if not text:
            text = STREAM_PLACEHOLDER
        if text == self._last_flushed_text and not force:
            return

        html = markdown_to_telegram_html(text) or STREAM_PLACEHOLDER
        slices = [html[i:i + CHUNK_SIZE] for i in range(0, len(html), CHUNK_SIZE)]

        for i, slice_html in enumerate(slices):
            if i < len(self._chunks):
                chunk = self._chunks[i]
                if chunk.sealed or chunk.text == slice_html:
                    continue
                await self._edit_with_retry(chunk.message, slice_html)
                chunk.text = slice_html
            else:
                if self._chunks:
                    self._chunks[-1].sealed = True
                msg = await self._send_with_retry(slice_html)
                self._chunks.append(_Chunk(message=msg, text=slice_html))

        self._last_flushed_text = text
        self._last_sent_at = time.monotonic()

    async def finalize(self, text: str) -> None:
        self.push(text or STREAM_PLACEHOLDER)
        await self.flush(force=True)

    async def _edit_with_retry(self, message: Message, html: str) -> None:
        while True:
            try:
                await message.edit_text(html, parse_mode="HTML")
                return
            except BadRequest as exc:
                if "message is not modified" in str(exc).lower():
                    return
                raise
            except RetryAfter as exc:
                logger.warning("Telegram edit flood-controlled, sleeping %.1fs", exc.retry_after)
                await asyncio.sleep(exc.retry_after + 0.5)

    async def _send_with_retry(self, html: str) -> Message:
        while True:
            try:
                return await self._update.message.reply_text(html, parse_mode="HTML")
            except RetryAfter as exc:
                logger.warning("Telegram send flood-controlled, sleeping %.1fs", exc.retry_after)
                await asyncio.sleep(exc.retry_after + 0.5)


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
    from inkagent.providers import get_model
    await update.message.reply_text(f"New session started. Model: {get_model()}")


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
    stream = TelegramStreamBuffer(update)
    stop_typing = asyncio.Event()

    async def keep_typing() -> None:
        """Send typing action and flush stream buffer until stopped."""
        while not stop_typing.is_set():
            await update.effective_chat.send_action(ChatAction.TYPING)
            if stream.should_flush():
                await stream.flush()
            try:
                await asyncio.wait_for(stop_typing.wait(), timeout=TYPING_INTERVAL_SECONDS)
            except asyncio.TimeoutError:
                pass

    typing_task = asyncio.create_task(keep_typing())
    try:
        reply = await asyncio.to_thread(stream_agent, user_text, session_id, stream.push)
    except LLMError as e:
        logger.error("API call failed in session %s: %s", session_id, e)
        reply = f"[API error: {e}]"
    finally:
        stop_typing.set()
        await typing_task

    if stream.should_flush(force=True) or reply:
        await stream.finalize(reply)
    else:
        await _send_long_message(update, reply)


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors in the telegram bot — log and continue instead of crashing."""
    logger.error("Exception while handling an update: %s", context.error)


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
    app.add_error_handler(_error_handler)

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
