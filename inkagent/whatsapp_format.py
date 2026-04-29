"""Convert standard Markdown to WhatsApp-compatible formatting.

WhatsApp markup:
- *bold*
- _italic_
- ~strikethrough~
- `inline code`
- ```code block```
"""

import re

_PH = "\x00"


def markdown_to_whatsapp(text: str) -> str:
    """Convert Markdown text to WhatsApp formatting.

    Handles: headings, bold, italic, strike, code (inline + fenced), links.
    Lists, blockquotes, and other unsupported elements are left as-is.
    """
    # Preserve fenced code blocks first (WhatsApp uses the same triple-backtick).
    blocks: list[str] = []

    def _save_block(m: re.Match) -> str:
        blocks.append(m.group(0))
        return f"{_PH}B{len(blocks) - 1}{_PH}"

    text = re.sub(r"```[\s\S]*?```", _save_block, text)

    # Preserve inline code spans.
    spans: list[str] = []

    def _save_span(m: re.Match) -> str:
        spans.append(m.group(0))
        return f"{_PH}S{len(spans) - 1}{_PH}"

    text = re.sub(r"`[^`\n]+`", _save_span, text)

    # Bold first, save as placeholder so the italic pass below doesn't grab
    # the inner asterisks of **x**.
    bolds: list[str] = []

    def _save_bold(m: re.Match) -> str:
        bolds.append(m.group(1))
        return f"{_PH}D{len(bolds) - 1}{_PH}"

    text = re.sub(r"\*\*(.+?)\*\*", _save_bold, text)
    text = re.sub(r"__(.+?)__", _save_bold, text)

    # Strikethrough: ~~x~~ -> ~x~
    text = re.sub(r"~~(.+?)~~", r"~\1~", text)

    # Markdown italic *x* -> WhatsApp italic _x_. Skip word-internal asterisks.
    text = re.sub(r"(?<!\w)\*([^*\n]+?)\*(?!\w)", r"_\1_", text)
    # Markdown italic _x_ already matches WhatsApp italic, leave as-is.

    # Headings: # / ## / ### ... -> *bolded text*
    def _heading(m: re.Match) -> str:
        return f"*{m.group(2).strip()}*"

    text = re.sub(r"^(#{1,6})\s+(.+)$", _heading, text, flags=re.MULTILINE)

    # Links: [text](url) -> text (url). WhatsApp auto-linkifies bare URLs.
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)

    for idx, body in enumerate(bolds):
        text = text.replace(f"{_PH}D{idx}{_PH}", f"*{body}*")
    for idx, span in enumerate(spans):
        text = text.replace(f"{_PH}S{idx}{_PH}", span)
    for idx, block in enumerate(blocks):
        text = text.replace(f"{_PH}B{idx}{_PH}", block)

    return text
