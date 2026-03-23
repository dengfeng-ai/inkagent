"""Shared constants for the agent package."""

# LLM generation
MAX_REPLY_TOKENS = 4096  # max tokens per LLM response
MAX_TOOL_ROUNDS = 10  # max tool-use loop iterations per agent turn

# Context window management
MAX_CONTEXT_TOKENS = 200_000
COMPRESS_THRESHOLD = 160_000  # trigger compression at 80% capacity
CHARS_PER_TOKEN = 4  # rough estimate
KEEP_RECENT_MESSAGES = 6  # preserve last 3 turns (user+assistant pairs)

# Tool output
TOOL_OUTPUT_CAP = 3000  # max chars returned from a tool call

# Shell skill
SHELL_TIMEOUT = 30  # seconds

# Web search / fetch
WEB_SEARCH_COUNT = 5  # number of search results to return
WEB_FETCH_TIMEOUT = 15  # seconds
WEB_FETCH_MAX_CHARS = 20_000  # max chars extracted from a page (before TOOL_OUTPUT_CAP)

# Vector search
EMBEDDING_MODEL = "text-embedding-3-small"
VECTOR_SEARCH_TOP_K = 5
