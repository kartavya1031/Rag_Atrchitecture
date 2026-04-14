"""Cross-encoder reranker — reranks retrieved chunks using OpenAI for relevance scoring."""

import json
from typing import Any

from src.llm.client import get_openai_client, get_model


def rerank(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Rerank retrieved chunks using an LLM-based cross-encoder approach.

    Sends the query and each chunk to GPT for relevance scoring,
    then re-sorts by relevance score descending.

    Args:
        query: The user query.
        chunks: List of chunk dicts (must have 'document' key).
        top_k: Number of top results to return after reranking.

    Returns:
        Reranked list of chunk dicts with added 'rerank_score' field.
    """
    if not chunks or len(chunks) <= 1:
        return chunks[:top_k]

    client = get_openai_client()
    model = get_model()

    # Build a batch scoring prompt
    passages = []
    for i, chunk in enumerate(chunks):
        doc_text = chunk.get("document", "")[:500]  # Truncate to save tokens
        passages.append(f"[Passage {i}]: {doc_text}")

    passages_block = "\n\n".join(passages)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a relevance scoring engine. Given a query and a list of passages, "
                    "score each passage for relevance to the query on a scale of 0.0 to 1.0. "
                    "Return ONLY a JSON object with a 'scores' array of numbers, one per passage, "
                    "in the same order as the passages. Example: {\"scores\": [0.9, 0.3, 0.7]}"
                ),
            },
            {
                "role": "user",
                "content": f"Query: {query}\n\nPassages:\n{passages_block}",
            },
        ],
        temperature=0.0,
        max_tokens=200,
        response_format={"type": "json_object"},
    )

    try:
        result = json.loads(response.choices[0].message.content)
        scores = result.get("scores", [])
    except (json.JSONDecodeError, KeyError):
        # Fallback: return original order
        return chunks[:top_k]

    # Attach rerank scores
    for i, chunk in enumerate(chunks):
        chunk["rerank_score"] = float(scores[i]) if i < len(scores) else 0.0

    # Sort by rerank score descending
    reranked = sorted(chunks, key=lambda c: c.get("rerank_score", 0.0), reverse=True)

    return reranked[:top_k]
