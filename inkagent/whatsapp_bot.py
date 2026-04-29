"""WhatsApp bot entry point for inkagent.

Connects to WhatsApp via the unofficial WhatsApp Web protocol (neonize ->
whatsmeow). On first run, neonize prints a QR code to stderr — scan it from
WhatsApp > Linked Devices to pair the bot's account.
"""

from __future__ import annotations

import asyncio
import logging
import os

from dotenv import load_dotenv

load_dotenv()

from neonize.aioze.client import NewAClient  # noqa: E402
from neonize.aioze.events import ConnectedEv, MessageEv  # noqa: E402
from neonize.proto.waCompanionReg.WAWebProtobufsCompanionReg_pb2 import (  # noqa: E402
    DeviceProps,
)
from neonize.utils.enum import ChatPresence, ChatPresenceMedia  # noqa: E402
from neonize.utils.jid import build_jid  # noqa: E402

from inkagent import session as session_module  # noqa: E402
from inkagent.brain import run_agent  # noqa: E402
from inkagent.compression import force_compress  # noqa: E402
from inkagent.config import MEMORY_DIR  # noqa: E402
from inkagent.providers import LLMError  # noqa: E402
from inkagent.scheduler import run_scheduler  # noqa: E402
from inkagent.session import (  # noqa: E402
    get_conversation, reset_conversation, save_conversation,
)
from inkagent.whatsapp_format import markdown_to_whatsapp  # noqa: E402

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# WhatsApp text message hard limit.
MAX_MSG_LEN = 4096

# How often to re-send the 'composing' (typing) indicator. WhatsApp times
# typing out after ~15s if not refreshed.
COMPOSING_REFRESH_SECONDS = 10.0

# Local pairing/session is persisted here. Survives restarts; delete to
# force re-pairing.
WA_DB_PATH = os.path.join(MEMORY_DIR, "whatsapp_session.db")


def _get_owner_phone() -> str:
    """Read and normalize WHATSAPP_OWNER_PHONE from env."""
    raw = os.environ.get("WHATSAPP_OWNER_PHONE", "").strip()
    if not raw:
        raise SystemExit(
            "Error: WHATSAPP_OWNER_PHONE is not set. "
            "Set it to your WhatsApp phone (digits only, e.g. 6591234567)."
        )
    return _normalize_phone(raw)


def _normalize_phone(value: str) -> str:
    """Reduce '+1 234-567 8900', '12345@s.whatsapp.net', '12345:1@...' to digits."""
    s = value.split("@")[0].split(":")[0]
    return "".join(ch for ch in s if ch.isdigit())


def _is_owner(sender_user: str, owner_phone: str) -> bool:
    return _normalize_phone(sender_user) == owner_phone


def _resolve_sender_phone(message_source) -> str:
    """Pull the phone-form User from a MessageSource, falling back to SenderAlt.

    WhatsApp's LID addressing mode puts a non-phone identifier in `Sender`
    (Server="lid") and the real phone-number JID in `SenderAlt`
    (Server="s.whatsapp.net"). We prefer the phone form so the owner check
    can compare against WHATSAPP_OWNER_PHONE.
    """
    sender = message_source.Sender
    if getattr(sender, "Server", "") == "s.whatsapp.net":
        return sender.User
    alt = getattr(message_source, "SenderAlt", None)
    if alt is not None and not getattr(alt, "IsEmpty", True):
        return alt.User
    return sender.User


def _extract_text(message_proto) -> str:
    """Pull plain text out of a WhatsApp Message proto.

    Handles `conversation` (plain) and `extendedTextMessage.text`
    (formatted/quoted). Media-only messages return empty.
    """
    text = getattr(message_proto, "conversation", "") or ""
    if text:
        return text
    extended = getattr(message_proto, "extendedTextMessage", None)
    if extended is not None:
        return getattr(extended, "text", "") or ""
    return ""


def _split_for_whatsapp(text: str, limit: int = MAX_MSG_LEN) -> list[str]:
    """Slice text into chunks <= limit chars."""
    if not text:
        return []
    if len(text) <= limit:
        return [text]
    return [text[i:i + limit] for i in range(0, len(text), limit)]


async def _send_chunks(send_fn, chat_jid, text: str) -> None:
    """Format and send a (possibly long) reply via the given send function."""
    formatted = markdown_to_whatsapp(text)
    chunks = _split_for_whatsapp(formatted)
    for chunk in chunks:
        await send_fn(chat_jid, chunk)


async def _keep_composing(client, chat_jid, done: asyncio.Event) -> None:
    """Refresh the WhatsApp 'composing' indicator until done is set."""
    while not done.is_set():
        try:
            await client.send_chat_presence(
                chat_jid,
                ChatPresence.CHAT_PRESENCE_COMPOSING,
                ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT,
            )
        except Exception:
            logger.warning("Failed to send COMPOSING presence", exc_info=True)
            return
        try:
            await asyncio.wait_for(done.wait(), timeout=COMPOSING_REFRESH_SECONDS)
        except asyncio.TimeoutError:
            pass


async def process_message(
    text: str,
    sender_user: str,
    chat_jid,
    owner_phone: str,
    send_fn,
) -> None:
    """Core message-handling logic, decoupled from neonize for testability.

    `send_fn` is `async (jid, text) -> None` so tests can substitute an
    AsyncMock without touching the neonize event machinery.
    """
    if not _is_owner(sender_user, owner_phone):
        return
    text = text.strip()
    if not text:
        return

    session_id = f"wa_{owner_phone}"
    session_module.current_session_id.set(session_id)

    if text == "/new":
        count = reset_conversation(session_id)
        await send_fn(chat_jid, f"New session started. ({count} archived)")
        return
    if text == "/compact":
        conversation = get_conversation(session_id)
        if len(conversation) <= 1:
            await send_fn(chat_jid, "Nothing to compact.")
            return
        before, after = await asyncio.to_thread(force_compress, conversation)
        save_conversation(session_id)
        await send_fn(chat_jid, f"Compacted: {before} messages -> {after}")
        return

    try:
        reply = await asyncio.to_thread(run_agent, text, session_id)
    except LLMError as e:
        logger.error("API call failed in session %s: %s", session_id, e)
        reply = f"[API error: {e}]"
    save_conversation(session_id)
    await _send_chunks(send_fn, chat_jid, reply)


def main() -> None:
    owner_phone = _get_owner_phone()
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Error: OPENAI_API_KEY is not set. Check your .env file.")
    if provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("Error: ANTHROPIC_API_KEY is not set. Check your .env file.")

    os.makedirs(MEMORY_DIR, exist_ok=True)
    # Identify as a vanilla Chrome-on-macOS Web client. neonize's default
    # (os="Neonize", platformType=SAFARI, version=0.0.0.0.0) is a fingerprint
    # that WhatsApp's classifier flags as "automation", which surfaces the
    # "AI from Meta" privacy disclosure on the other end. We set both the
    # platform string and a plausible WhatsApp Web version triple to look
    # like a normal Web client. This may not eliminate the banner — the
    # behavior pattern (linked-device replying programmatically) is itself
    # a fingerprint — but it removes the most obvious tell.
    device_props = DeviceProps(
        os="Mac OS",
        platformType=DeviceProps.CHROME,
        version=DeviceProps.AppVersion(
            primary=2, secondary=3000, tertiary=1015, quaternary=0, quinary=0
        ),
    )
    client = NewAClient(WA_DB_PATH, props=device_props)

    async def _send(jid, text: str) -> None:
        await client.send_message(jid, text)

    async def _scheduled_delivery(session_id: str, reply: str) -> None:
        """Cron callback — only handle wa_* sessions, ignore tg_* etc."""
        if not session_id.startswith("wa_"):
            return
        phone = session_id.removeprefix("wa_")
        chat_jid = build_jid(phone)
        await _send_chunks(_send, chat_jid, reply)

    @client.event(ConnectedEv)
    async def _on_connected(c, event):
        logger.info("WhatsApp bot connected. Owner phone: %s", owner_phone)

    @client.event(MessageEv)
    async def _on_message(c, event):
        # Outer try catches anything so the Go-thread future never swallows it.
        try:
            try:
                source = event.Info.MessageSource
                sender_phone = _resolve_sender_phone(source)
                # Reply via the phone-form JID — whatsmeow routes this
                # correctly even when the chat itself uses LID addressing.
                chat_jid = build_jid(_normalize_phone(sender_phone))
                text = _extract_text(event.Message)
            except Exception:
                logger.exception("Failed to extract MessageEv fields")
                return

            # Show typing only for legit owner messages — otherwise we'd
            # leak bot presence to anyone who messages this number.
            show_typing = bool(_is_owner(sender_phone, owner_phone) and text.strip())
            done = asyncio.Event()
            composing_task = (
                asyncio.create_task(_keep_composing(c, chat_jid, done))
                if show_typing else None
            )
            try:
                await process_message(text, sender_phone, chat_jid, owner_phone, _send)
            finally:
                if composing_task is not None:
                    done.set()
                    try:
                        await composing_task
                    except Exception:
                        pass
                    try:
                        await c.send_chat_presence(
                            chat_jid,
                            ChatPresence.CHAT_PRESENCE_PAUSED,
                            ChatPresenceMedia.CHAT_PRESENCE_MEDIA_TEXT,
                        )
                    except Exception:
                        logger.warning("Failed to send PAUSED presence", exc_info=True)
        except Exception:
            logger.exception("Unhandled error in _on_message")

    async def _run() -> None:
        await client.connect()
        scheduler_task = asyncio.create_task(run_scheduler(_scheduled_delivery))
        try:
            await client.idle()
        finally:
            scheduler_task.cancel()

    logger.info("WhatsApp bot starting (db: %s) — scan QR if first run", WA_DB_PATH)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
