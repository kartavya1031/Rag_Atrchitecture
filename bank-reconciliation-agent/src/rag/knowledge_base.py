"""Knowledge base document manager — ingest, list, delete documents in ChromaDB."""

import datetime
from pathlib import Path
from typing import Any, BinaryIO

import chromadb

from src.rag.collection_manager import get_chroma_client, get_or_create_collection
from src.rag.document_loader import (
    chunk_text,
    detect_and_extract,
    file_content_hash,
    generate_chunk_id,
)

COLLECTION_NAME = "knowledge_base"


def ingest_document(
    filename: str,
    source: str | Path | BinaryIO,
    content_bytes: bytes | None = None,
    client: chromadb.ClientAPI | None = None,
    chunk_size: int = 1000,
    overlap: int = 200,
) -> dict[str, Any]:
    """Extract text from a document, chunk it, and upsert into ChromaDB.

    Args:
        filename: Original filename (used for format detection + metadata).
        source: File path or file-like object.
        content_bytes: Raw bytes for hashing (if source is a path, reads it).
        client: Optional ChromaDB client.
        chunk_size: Characters per chunk.
        overlap: Overlap between chunks.

    Returns:
        Dict with filename, chunk_count, content_hash, doc_type.
    """
    if client is None:
        client = get_chroma_client()

    col = get_or_create_collection(client, COLLECTION_NAME)

    # Extract text
    text = detect_and_extract(filename, source)

    # Compute content hash
    if content_bytes is None:
        if isinstance(source, (str, Path)):
            content_bytes = Path(source).read_bytes()
        else:
            content_bytes = text.encode("utf-8")
    chash = file_content_hash(content_bytes)

    # Check for duplicate
    existing = _get_doc_chunks(col, filename, chash)
    if existing:
        return {
            "filename": filename,
            "chunk_count": len(existing),
            "content_hash": chash,
            "doc_type": Path(filename).suffix.lower(),
            "status": "already_exists",
        }

    # Chunk
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return {
            "filename": filename,
            "chunk_count": 0,
            "content_hash": chash,
            "doc_type": Path(filename).suffix.lower(),
            "status": "empty_document",
        }

    # Prepare IDs, documents, metadata
    ids = []
    docs = []
    metas = []
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ext = Path(filename).suffix.lower()

    for i, chunk in enumerate(chunks):
        chunk_id = generate_chunk_id(filename, i, chash)
        ids.append(chunk_id)
        docs.append(chunk)
        metas.append({
            "filename": filename,
            "doc_type": ext,
            "content_hash": chash,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "uploaded_at": now,
        })

    col.upsert(ids=ids, documents=docs, metadatas=metas)

    return {
        "filename": filename,
        "chunk_count": len(chunks),
        "content_hash": chash,
        "doc_type": ext,
        "status": "ingested",
    }


def list_documents(client: chromadb.ClientAPI | None = None) -> list[dict[str, Any]]:
    """List all unique documents in the knowledge base.

    Returns list of dicts: filename, doc_type, content_hash, chunk_count, uploaded_at.
    """
    if client is None:
        client = get_chroma_client()

    col = get_or_create_collection(client, COLLECTION_NAME)

    # Get all metadata
    result = col.get(include=["metadatas"])
    if not result or not result.get("metadatas"):
        return []

    # Group by (filename, content_hash)
    seen: dict[str, dict[str, Any]] = {}
    for meta in result["metadatas"]:
        key = f"{meta['filename']}:{meta['content_hash']}"
        if key not in seen:
            seen[key] = {
                "filename": meta["filename"],
                "doc_type": meta.get("doc_type", ""),
                "content_hash": meta["content_hash"],
                "chunk_count": meta.get("total_chunks", 1),
                "uploaded_at": meta.get("uploaded_at", ""),
            }

    return sorted(seen.values(), key=lambda d: d["filename"])


def delete_document(
    filename: str,
    content_hash: str | None = None,
    client: chromadb.ClientAPI | None = None,
) -> int:
    """Delete all chunks of a document from the knowledge base.

    Returns count of deleted chunks.
    """
    if client is None:
        client = get_chroma_client()

    col = get_or_create_collection(client, COLLECTION_NAME)

    # Build where filter
    where: dict[str, Any] = {"filename": filename}
    if content_hash:
        where = {"$and": [{"filename": filename}, {"content_hash": content_hash}]}

    # Get matching IDs
    results = col.get(where=where, include=[])
    ids = results.get("ids", [])

    if ids:
        col.delete(ids=ids)

    return len(ids)


def query_knowledge_base(
    query_text: str,
    n_results: int = 5,
    filename_filter: str | None = None,
    client: chromadb.ClientAPI | None = None,
) -> list[dict[str, Any]]:
    """Query the knowledge base with optional filename filter."""
    if client is None:
        client = get_chroma_client()

    col = get_or_create_collection(client, COLLECTION_NAME)

    query_params: dict[str, Any] = {
        "query_texts": [query_text],
        "n_results": n_results,
    }
    if filename_filter:
        query_params["where"] = {"filename": filename_filter}

    results = col.query(**query_params)

    output = []
    ids = results.get("ids", [[]])[0]
    docs = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for i, doc_id in enumerate(ids):
        distance = distances[i] if i < len(distances) else 999
        similarity = 1.0 / (1.0 + distance)
        output.append({
            "id": doc_id,
            "document": docs[i] if i < len(docs) else "",
            "metadata": metadatas[i] if i < len(metadatas) else {},
            "distance": distance,
            "similarity": round(similarity, 4),
        })

    return output


def _get_doc_chunks(col: chromadb.Collection, filename: str, content_hash: str) -> list[str]:
    """Check if a document with the same hash already exists."""
    try:
        results = col.get(
            where={"$and": [{"filename": filename}, {"content_hash": content_hash}]},
            include=[],
        )
        return results.get("ids", [])
    except Exception:
        return []
