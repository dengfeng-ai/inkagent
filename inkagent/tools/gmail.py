"""Gmail skills — search, read, and send email via IMAP/SMTP with App Password.

Requires GMAIL_ADDRESS and GMAIL_APP_PASSWORD env vars.
If missing, no tools are registered.
"""

import os

_GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
_GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

if not _GMAIL_ADDRESS or not _GMAIL_APP_PASSWORD:
    # No credentials — skip all tool registration.
    pass
else:
    # ---- imports only when credentials are present ----
    import email as _email
    import email.header
    import email.utils
    import imaplib
    import smtplib
    import time
    from email.mime.text import MIMEText
    from typing import Callable, TypeVar

    from inkagent.registry import register

    IMAP_HOST = "imap.gmail.com"
    SMTP_HOST = "smtp.gmail.com"
    SMTP_PORT = 587

    _T = TypeVar("_T")

    def _imap_with_retry(
        folder: str,
        readonly: bool,
        op: "Callable[[imaplib.IMAP4_SSL], _T]",
        attempts: int = 3,
        base_delay: float = 0.3,
    ) -> "_T":
        """Run an IMAP operation with retries on transient server failures.

        Reconnects (fresh login + select) on each attempt. Auth failures are
        permanent and raised immediately; other IMAP/socket errors back off
        exponentially before the next try.
        """
        last_exc: Exception | None = None
        for i in range(attempts):
            try:
                with imaplib.IMAP4_SSL(IMAP_HOST) as imap:
                    imap.login(_GMAIL_ADDRESS, _GMAIL_APP_PASSWORD)
                    imap.select(folder, readonly=readonly)
                    return op(imap)
            except (imaplib.IMAP4.error, OSError) as e:
                last_exc = e
                if "authenticationfailed" in str(e).lower():
                    raise
                if i < attempts - 1:
                    time.sleep(base_delay * (2**i))
        assert last_exc is not None
        raise last_exc

    def _decode_header(raw: str) -> str:
        """Decode RFC 2047 encoded header value."""
        parts = email.header.decode_header(raw)
        decoded: list[str] = []
        for data, charset in parts:
            if isinstance(data, bytes):
                decoded.append(data.decode(charset or "utf-8", errors="replace"))
            else:
                decoded.append(data)
        return " ".join(decoded)

    def _extract_text(msg: _email.message.Message) -> str:
        """Extract plain text body from an email message."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
            for part in msg.walk():
                if part.get_content_type() == "text/html" and not part.get("Content-Disposition"):
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        return payload.decode(charset, errors="replace")
            return "(no text content)"
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace")
            return "(no content)"

    def _list_attachments(msg: _email.message.Message) -> list[str]:
        """List attachment filenames from an email message."""
        attachments: list[str] = []
        for part in msg.walk():
            disp = part.get("Content-Disposition")
            if disp and "attachment" in disp:
                filename = part.get_filename()
                if filename:
                    attachments.append(_decode_header(filename))
        return attachments

    # -------------------------------------------------------------------
    # gmail_search
    # -------------------------------------------------------------------

    @register(
        name="gmail_search",
        description=(
            "Search Gmail and return a list of matching emails with sender, "
            "subject, date, and snippet. Use Gmail IMAP search syntax "
            "(e.g. 'FROM alice SUBJECT invoice UNSEEN'). "
            "Common criteria: FROM, TO, SUBJECT, SINCE 01-Jan-2026, "
            "BEFORE 01-Feb-2026, UNSEEN, SEEN, ALL."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "IMAP search query. Examples: "
                        "'FROM alice', 'SUBJECT invoice UNSEEN', "
                        "'SINCE 01-Mar-2026', 'ALL'"
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 10, max 20)",
                },
                "folder": {
                    "type": "string",
                    "description": "Mailbox folder to search (default INBOX)",
                },
            },
            "required": ["query"],
        },
    )
    def gmail_search(query: str, max_results: int = 10, folder: str = "INBOX") -> str:
        max_results = min(max_results, 20)

        def _op(imap: imaplib.IMAP4_SSL) -> str:
            status, data = imap.search(None, query)
            if status != "OK" or not data[0]:
                return "No emails found."

            msg_ids = data[0].split()
            msg_ids = list(reversed(msg_ids[-max_results:]))

            lines: list[str] = []
            for uid in msg_ids:
                status, msg_data = imap.fetch(uid, "(FLAGS BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])")
                if status != "OK" or not msg_data[0]:
                    continue

                raw_header = msg_data[0][1]
                header_msg = _email.message_from_bytes(raw_header)

                from_val = _decode_header(header_msg.get("From", "?"))
                subject_val = _decode_header(header_msg.get("Subject", "(no subject)"))
                date_val = header_msg.get("Date", "?")

                flags_raw = msg_data[0][0].decode() if msg_data[0][0] else ""
                unread = "\\Seen" not in flags_raw

                lines.append(
                    f"{'[UNREAD] ' if unread else ''}"
                    f"UID: {uid.decode()}\n"
                    f"  From: {from_val}\n"
                    f"  Subject: {subject_val}\n"
                    f"  Date: {date_val}"
                )

            if not lines:
                return "No emails found."
            return "\n\n".join(lines)

        try:
            return _imap_with_retry(folder, readonly=True, op=_op)
        except imaplib.IMAP4.error as e:
            return f"Error: Gmail IMAP failed — {e}"
        except Exception as e:
            return f"Error: {e}"

    # -------------------------------------------------------------------
    # gmail_read
    # -------------------------------------------------------------------

    @register(
        name="gmail_read",
        description=(
            "Read the full content of a specific email by its UID. "
            "Use gmail_search first to find UIDs."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "uid": {
                    "type": "string",
                    "description": "Email UID (from gmail_search results)",
                },
                "folder": {
                    "type": "string",
                    "description": "Mailbox folder (default INBOX)",
                },
            },
            "required": ["uid"],
        },
    )
    def gmail_read(uid: str, folder: str = "INBOX") -> str:
        def _op(imap: imaplib.IMAP4_SSL) -> str:
            status, msg_data = imap.fetch(uid.encode(), "(RFC822)")
            if status != "OK" or not msg_data[0]:
                return f"Error: Email UID {uid} not found."

            msg = _email.message_from_bytes(msg_data[0][1])

            from_val = _decode_header(msg.get("From", "?"))
            to_val = _decode_header(msg.get("To", "?"))
            cc_val = _decode_header(msg.get("Cc", ""))
            subject_val = _decode_header(msg.get("Subject", "(no subject)"))
            date_val = msg.get("Date", "?")
            message_id = msg.get("Message-ID", "")

            body = _extract_text(msg)
            attachments = _list_attachments(msg)

            result = (
                f"From: {from_val}\n"
                f"To: {to_val}\n"
            )
            if cc_val:
                result += f"Cc: {cc_val}\n"
            result += (
                f"Subject: {subject_val}\n"
                f"Date: {date_val}\n"
                f"Message-ID: {message_id}\n"
            )

            if attachments:
                result += "Attachments:\n" + "\n".join(f"  - {a}" for a in attachments) + "\n"

            result += f"\n{body}"
            return result

        try:
            return _imap_with_retry(folder, readonly=True, op=_op)
        except imaplib.IMAP4.error as e:
            return f"Error: Gmail IMAP failed — {e}"
        except Exception as e:
            return f"Error: {e}"

    # -------------------------------------------------------------------
    # gmail_send
    # -------------------------------------------------------------------

    @register(
        name="gmail_send",
        description=(
            "Send an email or reply to an existing email. "
            "To reply, provide in_reply_to (the Message-ID header from gmail_read)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address",
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line",
                },
                "body": {
                    "type": "string",
                    "description": "Email body (plain text)",
                },
                "cc": {
                    "type": "string",
                    "description": "CC recipient(s), comma-separated (optional)",
                },
                "bcc": {
                    "type": "string",
                    "description": "BCC recipient(s), comma-separated (optional)",
                },
                "in_reply_to": {
                    "type": "string",
                    "description": "Message-ID header of the email being replied to (optional)",
                },
            },
            "required": ["to", "subject", "body"],
        },
    )
    def gmail_send(
        to: str,
        subject: str,
        body: str,
        cc: str | None = None,
        bcc: str | None = None,
        in_reply_to: str | None = None,
    ) -> str:
        mime_msg = MIMEText(body)
        mime_msg["From"] = _GMAIL_ADDRESS
        mime_msg["To"] = to
        mime_msg["Subject"] = subject

        if cc:
            mime_msg["Cc"] = cc

        if in_reply_to:
            mime_msg["In-Reply-To"] = in_reply_to
            mime_msg["References"] = in_reply_to

        # Build recipient list for SMTP envelope (BCC not in headers)
        recipients = [addr.strip() for addr in to.split(",")]
        if cc:
            recipients += [addr.strip() for addr in cc.split(",")]
        if bcc:
            recipients += [addr.strip() for addr in bcc.split(",")]

        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
                smtp.starttls()
                smtp.login(_GMAIL_ADDRESS, _GMAIL_APP_PASSWORD)
                smtp.sendmail(_GMAIL_ADDRESS, recipients, mime_msg.as_string())
        except smtplib.SMTPException as e:
            return f"Error: Failed to send email — {e}"
        except Exception as e:
            return f"Error: {e}"

        sent_info = f"Email sent to {to}."
        if cc:
            sent_info += f" CC: {cc}"
        if bcc:
            sent_info += f" BCC: {bcc}"
        return sent_info

    # -------------------------------------------------------------------
    # gmail_mark_read
    # -------------------------------------------------------------------

    @register(
        name="gmail_mark_read",
        description="Mark one or more emails as read by their UIDs.",
        input_schema={
            "type": "object",
            "properties": {
                "uids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of email UIDs to mark as read",
                },
                "folder": {
                    "type": "string",
                    "description": "Mailbox folder (default INBOX)",
                },
            },
            "required": ["uids"],
        },
    )
    def gmail_mark_read(uids: list[str], folder: str = "INBOX") -> str:
        def _op(imap: imaplib.IMAP4_SSL) -> None:
            for uid in uids:
                imap.store(uid.encode(), "+FLAGS", "\\Seen")

        try:
            _imap_with_retry(folder, readonly=False, op=_op)
        except imaplib.IMAP4.error as e:
            return f"Error: Gmail IMAP failed — {e}"
        except Exception as e:
            return f"Error: {e}"

        count = len(uids)
        return f"Marked {count} email{'s' if count > 1 else ''} as read."
