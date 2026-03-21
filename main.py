"""CLI entry point for inkagent."""

from agent.brain import run_agent


def main() -> None:
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

        response = run_agent(user_input)
        print(f"\nagent> {response}\n")


if __name__ == "__main__":
    main()
