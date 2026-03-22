"""web_fetch skill — fetch a URL and extract readable text content."""

import httpx
import trafilatura

from agent.config import WEB_FETCH_MAX_CHARS, WEB_FETCH_TIMEOUT
from agent.registry import register


@register(
    name="web_fetch",
    description=(
        "Fetch a web page and extract its main text content. "
        "Use this after web_search to read a full article or page."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch",
            },
        },
        "required": ["url"],
    },
)
def web_fetch(url: str) -> str:
    try:
        resp = httpx.get(
            url,
            timeout=WEB_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; inkagent/1.0; "
                    "+https://github.com/user/inkagent)"
                ),
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"Error: failed to fetch {url} — {e}"

    content_type = resp.headers.get("content-type", "")
    if "text/html" not in content_type and "text/plain" not in content_type:
        return f"Error: unsupported content type '{content_type}'"

    html = resp.text
    text = trafilatura.extract(html, include_links=True, include_tables=True)
    if not text:
        return "Error: could not extract readable content from this page"

    if len(text) > WEB_FETCH_MAX_CHARS:
        text = text[:WEB_FETCH_MAX_CHARS] + "\n\n... (content truncated)"

    return text
