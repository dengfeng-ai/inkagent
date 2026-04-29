"""Tests for the WhatsApp markdown converter."""

from inkagent.whatsapp_format import markdown_to_whatsapp


def test_plain_text_unchanged():
    assert markdown_to_whatsapp("hello world") == "hello world"


def test_bold_double_asterisk():
    assert markdown_to_whatsapp("**bold**") == "*bold*"


def test_bold_double_underscore():
    assert markdown_to_whatsapp("__bold__") == "*bold*"


def test_italic_single_asterisk():
    assert markdown_to_whatsapp("*italic*") == "_italic_"


def test_italic_single_underscore_unchanged():
    # markdown _x_ matches WhatsApp _x_ already.
    assert markdown_to_whatsapp("_italic_") == "_italic_"


def test_bold_inside_italic_pass_does_not_corrupt():
    # **bold** must not be re-processed into *_bold_*.
    assert markdown_to_whatsapp("**bold** and *italic*") == "*bold* and _italic_"


def test_word_internal_asterisk_left_alone():
    # x*y*z mid-word should not become italicized.
    assert markdown_to_whatsapp("foo*bar*baz") == "foo*bar*baz"


def test_strikethrough():
    assert markdown_to_whatsapp("~~gone~~") == "~gone~"


def test_inline_code_preserved():
    assert markdown_to_whatsapp("call `foo()` here") == "call `foo()` here"


def test_inline_code_protects_inner_markup():
    # Asterisks inside code must NOT be converted.
    assert markdown_to_whatsapp("`**not bold**`") == "`**not bold**`"


def test_fenced_code_block_preserved():
    src = "```\n*not bold*\n```"
    assert markdown_to_whatsapp(src) == src


def test_fenced_code_block_with_language():
    src = "```python\nprint('hi')\n```"
    assert markdown_to_whatsapp(src) == src


def test_heading_becomes_bold():
    assert markdown_to_whatsapp("# Title") == "*Title*"
    assert markdown_to_whatsapp("### Sub") == "*Sub*"


def test_heading_inline_only():
    out = markdown_to_whatsapp("# Title\nbody")
    assert out == "*Title*\nbody"


def test_link_to_text_with_url():
    assert markdown_to_whatsapp("[Google](https://google.com)") == "Google (https://google.com)"


def test_complex_paragraph():
    src = "**Hi** _there_, see `code` or [docs](https://x.com)."
    assert markdown_to_whatsapp(src) == "*Hi* _there_, see `code` or docs (https://x.com)."


def test_empty_string():
    assert markdown_to_whatsapp("") == ""
