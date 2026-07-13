from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI


def main() -> None:
    """Verify that the platform can connect to the OpenAI API."""

    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()

    print()
    print("=" * 80)
    print("OPENAI CONNECTION TEST")
    print("=" * 80)

    if not api_key:
        print("OPENAI_API_KEY was not found in the .env file.")
        return

    if not model:
        print("OPENAI_MODEL was not found in the .env file.")
        return

    client = OpenAI(
        api_key=api_key,
        timeout=60.0,
        max_retries=2,
    )

    print(f"Model configured: {model}")
    print("Connecting to OpenAI...")

    try:
        response = client.responses.create(
            model=model,
            instructions=(
                "You are testing the connection for a read-only "
                "Polymarket research platform."
            ),
            input=(
                "Respond with exactly this sentence: "
                "OpenAI is connected to the Polymarket platform."
            ),
            max_output_tokens=80,
        )

        print()
        print(response.output_text.strip())

    except Exception as error:
        print()
        print("OpenAI connection failed.")
        print(f"Error type: {type(error).__name__}")
        print(f"Details: {error}")


if __name__ == "__main__":
    main()