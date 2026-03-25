"""ChromaDB collection manager — creates and manages all RAG collections."""

import chromadb

from src.utils.config import get_env

COLLECTIONS = {
    "policies_sops": {
        "description": "Reconciliation SOPs and policies",
        "metadata_fields": ["bank", "type", "effective_date", "version"],
    },
    "prior_reconciliations": {
        "description": "Historical reconciliation outcomes",
        "metadata_fields": ["outcome", "exception_type", "bank", "date_range"],
    },
    "exception_catalog": {
        "description": "Known exception types and resolutions",
        "metadata_fields": ["exception_id", "category", "frequency", "resolution"],
    },
    "bank_rules": {
        "description": "Bank-specific matching rules",
        "metadata_fields": ["bank_name", "rule_type", "priority"],
    },
    "audit_logs": {
        "description": "Audit trail of matching decisions",
        "metadata_fields": ["transaction_id", "match_confidence", "validated"],
    },
    "knowledge_base": {
        "description": "General documents: PDFs, Word, Excel — research papers, guidelines, SOPs, any reference material",
        "metadata_fields": ["filename", "doc_type", "content_hash", "chunk_index", "total_chunks", "uploaded_at"],
    },
}


_chroma_client: chromadb.ClientAPI | None = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Return a singleton persistent ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        path = get_env("CHROMA_PATH", "./data/chroma_db")
        _chroma_client = chromadb.PersistentClient(path=path)
    return _chroma_client


def get_or_create_collection(
    client: chromadb.ClientAPI,
    name: str,
) -> chromadb.Collection:
    """Get or create a named collection."""
    return client.get_or_create_collection(name=name)


def initialize_all_collections(client: chromadb.ClientAPI) -> dict[str, chromadb.Collection]:
    """Create all defined collections and return them as a dict."""
    result = {}
    for name in COLLECTIONS:
        result[name] = get_or_create_collection(client, name)
    return result
