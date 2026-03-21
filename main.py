"""CLI entry point for inkagent."""

import logging
import os
import sys

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

from agent.brain import run_agent  # noqa: E402
from agent.providers import LLMError  # noqa: E402


def main() -> None:
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if provider == "openai" and not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY is not set. Check your .env file.")
        sys.exit(1)
    elif provider == "anthropic" and not os.environ.get("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY is not set. Check your .env file.")
        sys.exit(1)

    print("inkagent — type 'quit' to exit\n")
    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("bye!")
            break

        try:
            response = run_agent(user_input)
        except LLMError as e:
            print(f"\n[API error: {e}]\n")
            continue

        print(f"\nagent> {response}\n")


if __name__ == "__main__":
    main()
