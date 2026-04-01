"""Tests for Markdown → Telegram HTML conversion."""

from inkagent.telegram_format import markdown_to_telegram_html


class TestHeadings:
    def test_h1(self):
        assert markdown_to_telegram_html("# Hello") == "<b>Hello</b>"

    def test_h3(self):
        assert markdown_to_telegram_html("### Sub") == "<b>Sub</b>"

    def test_heading_with_inline(self):
        assert markdown_to_telegram_html("## **Bold** title") == "<b><b>Bold</b> title</b>"


class TestBold:
    def test_double_asterisk(self):
        assert markdown_to_telegram_html("**hello**") == "<b>hello</b>"

    def test_double_underscore(self):
        assert markdown_to_telegram_html("__hello__") == "<b>hello</b>"

    def test_bold_mid_sentence(self):
        result = markdown_to_telegram_html("say **yes** now")
        assert result == "say <b>yes</b> now"


class TestItalic:
    def test_single_asterisk(self):
        assert markdown_to_telegram_html("*hello*") == "<i>hello</i>"

    def test_single_underscore(self):
        assert markdown_to_telegram_html("_hello_") == "<i>hello</i>"

    def test_underscore_inside_word_not_converted(self):
        """file_name_here should NOT be italicised."""
        result = markdown_to_telegram_html("file_name_here")
        assert "<i>" not in result


class TestInlineCode:
    def test_backtick(self):
        assert markdown_to_telegram_html("`code`") == "<code>code</code>"

    def test_html_inside_code_escaped(self):
        result = markdown_to_telegram_html("`<div>`")
        assert result == "<code>&lt;div&gt;</code>"

    def test_bold_syntax_inside_code_preserved(self):
        """Markdown syntax inside backticks should not be converted."""
        result = markdown_to_telegram_html("`**not bold**`")
        assert "<b>" not in result
        assert "**not bold**" in result


class TestCodeBlock:
    def test_fenced_block(self):
        md = "```python\nprint('hi')\n```"
        result = markdown_to_telegram_html(md)
        assert result == "<pre>print(&#x27;hi&#x27;)</pre>"

    def test_fenced_block_html_escaped(self):
        md = "```\n<script>alert(1)</script>\n```"
        result = markdown_to_telegram_html(md)
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_multiline_block(self):
        md = "```\nline1\nline2\nline3\n```"
        result = markdown_to_telegram_html(md)
        assert result == "<pre>line1\nline2\nline3</pre>"


class TestLinks:
    def test_basic_link(self):
        result = markdown_to_telegram_html("[click](https://example.com)")
        assert result == '<a href="https://example.com">click</a>'


class TestHtmlEscaping:
    def test_angle_brackets_escaped(self):
        result = markdown_to_telegram_html("a < b > c")
        assert "&lt;" in result
        assert "&gt;" in result

    def test_ampersand_escaped(self):
        result = markdown_to_telegram_html("a & b")
        assert "&amp;" in result


class TestMixed:
    def test_normal_line_unchanged(self):
        assert markdown_to_telegram_html("just text") == "just text"

    def test_multiline_mixed(self):
        md = "# Title\n\nsome **bold** and `code`"
        result = markdown_to_telegram_html(md)
        lines = result.split("\n")
        assert lines[0] == "<b>Title</b>"
        assert "<b>bold</b>" in lines[2]
        assert "<code>code</code>" in lines[2]

    def test_empty_string(self):
        assert markdown_to_telegram_html("") == ""

    def test_list_items_passthrough(self):
        """Lists are not converted — left as-is per docstring."""
        md = "- item one\n- item two"
        result = markdown_to_telegram_html(md)
        assert "- item one" in result
        assert "- item two" in result
