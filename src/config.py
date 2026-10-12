"""Shared settings for our Groq model."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GROQ_MODEL = "openai/gpt-oss-20b"
GROQ_MAX_COMPLETION_TOKENS = 512
GROQ_TIMEOUT_SECONDS = 60
