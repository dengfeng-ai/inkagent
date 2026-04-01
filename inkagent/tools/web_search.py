"""web_search skill — search the web via Brave Search API."""

import os

import httpx

from inkagent.config import WEB_SEARCH_COUNT
from inkagent.registry import register


BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"


@register(
    name="web_search",
    description=(
        "Search the web using Brave Search and return a list of results. "
        "Each result includes title, URL, and a short snippet. "
        "Use web_fetch to read a full page if a snippet is not enough."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "count": {
                "type": "integer",
                "description": f"Number of results (default {WEB_SEARCH_COUNT})",
            },
        },
        "required": ["query"],
    },
)
def web_search(query: str, count: int = WEB_SEARCH_COUNT) -> str:
    api_key = os.environ.get("BRAVE_API_KEY")
    if not api_key:
        return "Error: BRAVE_API_KEY not set in environment"

    try:
        resp = httpx.get(
            BRAVE_ENDPOINT,
            params={"q": query, "count": min(count, 20)},
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            timeout=10,
        )
        resp.raise_for_status()
    except httpx.HTTPError as e:
        return f"Error: Brave Search request failed — {e}"

    data = resp.json()
    results = data.get("web", {}).get("results", [])
    if not results:
        return "No results found."

    lines: list[str] = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        url = r.get("url", "")
        snippet = r.get("description", "")
        lines.append(f"{i}. [{title}]({url})\n   {snippet}")

    return "\n\n".join(lines)
