"""Convert standard Markdown to Telegram-compatible HTML."""

import re
from html import escape


def markdown_to_telegram_html(text: str) -> str:
    """Convert Markdown text to Telegram HTML.

    Handles: headings, bold, italic, inline code, code blocks, links.
    Unsupported elements (lists, etc.) are left as-is.
    """
    lines = text.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Fenced code blocks: ```lang ... ```
        if line.strip().startswith("```"):
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            code_body = escape("\n".join(code_lines))
            result.append(f"<pre>{code_body}</pre>")
            continue

        # Headings: # / ## / ### etc. → bold
        heading_match = re.match(r"^(#{1,6})\s+(.*)", line)
        if heading_match:
            heading_text = _convert_inline(heading_match.group(2))
            result.append(f"<b>{heading_text}</b>")
            i += 1
            continue

        # Normal line: convert inline formatting
        result.append(_convert_inline(line))
        i += 1

    return "\n".join(result)


def _convert_inline(text: str) -> str:
    """Convert inline Markdown elements to HTML."""
    # Escape HTML entities first, but preserve Markdown syntax chars.
    # We process in a specific order to avoid double-conversion.

    # Step 1: extract and protect inline code spans
    code_spans: list[str] = []

    def _save_code(m: re.Match) -> str:
        code_spans.append(f"<code>{escape(m.group(1))}</code>")
        return f"\x00CODE{len(code_spans) - 1}\x00"

    text = re.sub(r"`([^`]+)`", _save_code, text)

    # Step 2: escape HTML in the remaining text
    text = escape(text)

    # Step 3: bold **text** or __text__
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"__(.+?)__", r"<b>\1</b>", text)

    # Step 4: italic *text* or _text_ (but not inside words like file_name_here)
    text = re.sub(r"(?<!\w)\*([^*]+?)\*(?!\w)", r"<i>\1</i>", text)
    text = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", r"<i>\1</i>", text)

    # Step 5: links [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    # Step 6: restore code spans
    for idx, code_html in enumerate(code_spans):
        text = text.replace(f"\x00CODE{idx}\x00", code_html)

    return text
