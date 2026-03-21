"""RAG retriever — queries ChromaDB collections with metadata filters."""

from typing import Any, Optional

import chromadb

from src.rag.collection_manager import get_chroma_client, get_or_create_collection
from src.utils.config import get_thresholds


def retrieve(
    collection_name: str,
    query_text: str,
    n_results: Optional[int] = None,
    where: Optional[dict[str, Any]] = None,
    client: Optional[chromadb.ClientAPI] = None,
    min_score: Optional[float] = None,
) -> list[dict]:
    """Query a ChromaDB collection and return top-N results with scores.

    Args:
        collection_name: Name of the ChromaDB collection.
        query_text: The query string.
        n_results: Number of results (defaults to config rag.top_k).
        where: Optional metadata filter dict.
        client: Optional ChromaDB client (creates one if not passed).

    Returns:
        List of dicts with keys: id, document, metadata, distance.
    """
    cfg = get_thresholds()
    top_k = n_results or cfg["rag"]["top_k"]
    effective_min_score = min_score if min_score is not None else cfg["rag"]["min_relevance_score"]

    if client is None:
        client = get_chroma_client()

    collection = get_or_create_collection(client, collection_name)

    query_params: dict[str, Any] = {
        "query_texts": [query_text],
        "n_results": top_k,
    }
    if where:
        query_params["where"] = where

    results = collection.query(**query_params)

    output = []
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i, doc_id in enumerate(ids):
        # ChromaDB returns L2 distances; convert to a similarity score
        # Lower distance = more similar; rough conversion: score = 1/(1+distance)
        distance = distances[i] if i < len(distances) else 999
        similarity = 1.0 / (1.0 + distance)

        if similarity < effective_min_score:
            continue

        output.append({
            "id": doc_id,
            "document": docs[i] if i < len(docs) else "",
            "metadata": metadatas[i] if i < len(metadatas) else {},
            "distance": distance,
            "similarity": round(similarity, 4),
        })

    return output
