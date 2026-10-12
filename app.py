"""Command-line interface for asking questions about the Chinook database."""
from __future__ import annotations

from agent.assistant import ask
from agent.llm import create_provider


def main() -> None:
    # Load local settings when python-dotenv is installed. It never prints them.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    provider = create_provider()
    print(f"Chinook SQL assistant ({provider.model}). Type 'quit' to stop.")
    while True:
        try:
            question = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if question.lower() in {"quit", "exit"}:
            break
        if not question:
            continue
        try:
            response = ask(question, provider)
            print(f"assistant> {response['answer']}")
        except Exception as exc:
            print(f"Could not get an answer: {exc}")


if __name__ == "__main__":
    main()
