"""OpenAI embeddings wrapper for RAG."""

from openai import OpenAI

from src.utils.config import get_env


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a list of texts using OpenAI."""
    client = OpenAI(api_key=get_env("OPENAI_API_KEY"))
    model = get_env("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    response = client.embeddings.create(input=texts, model=model)
    return [item.embedding for item in response.data]


def get_single_embedding(text: str) -> list[float]:
    """Generate an embedding for a single text."""
    return get_embeddings([text])[0]
