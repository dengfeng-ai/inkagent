@echo off
echo ==^> Setting up inkagent...

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: python is not installed.
    exit /b 1
)

python -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"
if %errorlevel% neq 0 (
    echo Error: Python 3.11+ is required.
    exit /b 1
)

if not exist ".venv" (
    echo ==^> Creating virtual environment...
    python -m venv .venv
)

echo ==^> Installing dependencies...
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt

if not exist ".env" (
    copy .env.example .env
    echo ==^> Created .env from template — edit it with your API keys.
) else (
    echo     .env already exists, skipping.
)

if not exist "memory\daily" mkdir memory\daily

echo.
echo Done! Next steps:
echo   1. Edit .env with your API keys
echo   2. .venv\Scripts\activate
echo   3. python main.py        (CLI mode)
echo      python bot.py         (Telegram bot)
