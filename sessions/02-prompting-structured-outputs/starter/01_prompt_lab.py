"""Session 2 baseline: compare two prompt versions on the same input."""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


def run_prompt(prompt_name: str, message: str) -> str:
    """Run one named prompt version with the same user message."""
    instructions = (PROMPTS_DIR / prompt_name).read_text(encoding="utf-8")
    client = OpenAI()
    response = client.responses.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        instructions=instructions,
        input=message,
    )
    return response.output_text


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY in your local .env file first.")

    message = input("Write a support request: ").strip()
    if not message:
        raise ValueError("Please enter a support request.")

    prompt_names = [
        "support_assistant_v1.txt",
        "support_assistant_v2.txt",
        "support_assistant_v3_few_shot.txt",
    ]
    for prompt_name in prompt_names:
        print(f"\n--- {prompt_name} ---\n")
        print(run_prompt(prompt_name, message))


if __name__ == "__main__":
    main()
