"""Shared OpenAI client singleton — avoids recreating per graph node."""

from openai import OpenAI

from src.utils.config import get_env

_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    """Return a singleton OpenAI client."""
    global _client
    if _client is None:
        _client = OpenAI(api_key=get_env("OPENAI_API_KEY"))
    return _client


def get_model() -> str:
    """Return the configured model name."""
    return get_env("OPENAI_MODEL", "gpt-4o")
