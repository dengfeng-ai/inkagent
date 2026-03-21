#!/usr/bin/env bash
set -e

echo "==> Setting up inkagent..."

# Check Python version
if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is not installed."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    echo "Error: Python 3.11+ is required (found $PY_VERSION)"
    exit 1
fi

echo "    Python $PY_VERSION ✓"

# Create venv
if [ ! -d ".venv" ]; then
    echo "==> Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate and install
echo "==> Installing dependencies..."
source .venv/bin/activate
pip install -q -r requirements.txt

# Create .env if missing
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "==> Created .env from template — edit it with your API keys."
else
    echo "    .env already exists, skipping."
fi

# Create memory directory
mkdir -p memory/daily

echo ""
echo "Done! Next steps:"
echo "  1. Edit .env with your API keys"
echo "  2. source .venv/bin/activate"
echo "  3. python main.py        (CLI mode)"
echo "     python bot.py         (Telegram bot)"
