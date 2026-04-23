"""Shared constants for the agent package."""

import os

__version__ = "0.1.0"

# ---------------------------------------------------------------------------
# Directory layout — centralised so a future migration to ~/.inkagent/ only
# touches this block.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = _PROJECT_ROOT  # will become ~/.inkagent/ when packaged

MEMORY_DIR = os.path.join(DATA_DIR, "memory")
DAILY_DIR = os.path.join(MEMORY_DIR, "daily")
CONVERSATIONS_DIR = os.path.join(DATA_DIR, "conversations")
CRONS_PATH = os.path.join(MEMORY_DIR, "crons.json")

# Memory files
AGENTS_PATH = os.path.join(MEMORY_DIR, "AGENTS.md")
IDENTITY_PATH = os.path.join(MEMORY_DIR, "IDENTITY.md")
SOUL_PATH = os.path.join(MEMORY_DIR, "SOUL.md")
USER_PATH = os.path.join(MEMORY_DIR, "USER.md")
LONG_TERM_PATH = os.path.join(MEMORY_DIR, "MEMORY.md")
HEARTBEAT_PATH = os.path.join(MEMORY_DIR, "HEARTBEAT.md")
DB_PATH = os.path.join(MEMORY_DIR, "memory.db")

# Skills directory (markdown instruction skills, edited by the user directly)
SKILLS_DIR = os.path.join(_PROJECT_ROOT, "skills")

# Writable directories (relative names, checked against project root)
WRITABLE_DIRS = ("memory", "conversations")

# ---------------------------------------------------------------------------
# LLM generation
# ---------------------------------------------------------------------------
MAX_REPLY_TOKENS = 4096  # max tokens per LLM response
MAX_TOOL_ROUNDS = 30  # max tool-use loop iterations per agent turn

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
