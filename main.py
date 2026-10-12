"""Stage 2: send one question to Groq using LangChain."""

import os
import time

from dotenv import load_dotenv
from groq import APIConnectionError, APIStatusError
from langchain_core.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq

from src.config import (
    GROQ_MAX_COMPLETION_TOKENS,
    GROQ_MODEL,
    GROQ_TIMEOUT_SECONDS,
    PROJECT_ROOT,
)


def main():
    # Load the project's settings; existing environment variables take priority.
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key or api_key == "your_groq_api_key_here":
        print("Add your Groq API key to .env using .env.example as the template.")
        return 1

    # Fill the template with the question we want to send.
    template = ChatPromptTemplate.from_messages([
        ("system", "Answer briefly in plain English."),
        ("human", "{question}"),
    ])
    prompt = template.format_messages(
        question="In one sentence, what is a customer relationship management (CRM) system?"
    )

    try:
        model = ChatGroq(
            api_key=api_key,
            model=GROQ_MODEL,
            temperature=0.2,
            timeout=GROQ_TIMEOUT_SECONDS,
            max_retries=0,
            reasoning_effort="low",
            model_kwargs={
                "max_completion_tokens": GROQ_MAX_COMPLETION_TOKENS,
                "include_reasoning": False,
            },
        )
        start = time.perf_counter()
        result = model.invoke(prompt)
        elapsed = time.perf_counter() - start

        # Empty or cut-off answers should not count as successful checks.
        if result.response_metadata.get("finish_reason") != "stop":
            print("The model did not finish its answer. Check the completion limit and try again.")
            return 1
        if not isinstance(result.content, str) or not result.content.strip():
            print("The model returned no text answer.")
            return 1

        print(f"Answer: {result.content.strip()}")
        print(f"Request time: {elapsed:.2f} seconds (includes network and model processing)")
        if result.usage_metadata:
            print(f"Input tokens: {result.usage_metadata.get('input_tokens', 'unavailable')}")
            print(f"Output tokens: {result.usage_metadata.get('output_tokens', 'unavailable')} (may include reasoning)")
        return 0
    except APIStatusError as error:
        # Omit raw provider errors, which may contain request details.
        print(f"Groq HTTP {error.status_code}: check your key (401), permissions (403), account limits (429), or model settings.")
        return 1
    except APIConnectionError:
        print("Could not connect to Groq. Check your internet connection and retry.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
