"""Integration tests for RAG layer — ingest + retrieval round-trip."""

import chromadb
import pytest

from src.rag.collection_manager import initialize_all_collections
from src.rag.ingest import (
    ingest_bank_rules,
    ingest_exception_catalog,
    ingest_historical_cases,
    ingest_sops,
)
from src.rag.retriever import retrieve


@pytest.fixture()
def chroma_client(tmp_path):
    """Ephemeral in-memory ChromaDB client for tests."""
    return chromadb.EphemeralClient()


@pytest.fixture()
def collections(chroma_client):
    return initialize_all_collections(chroma_client)


@pytest.fixture()
def seeded(collections, chroma_client):
    """Seed all collections and yield (collections, client)."""
    ingest_sops(collections)
    ingest_historical_cases(collections)
    ingest_exception_catalog(collections)
    ingest_bank_rules(collections)
    return collections, chroma_client


# --- SOP retrieval ---

def test_sop_retrieval(seeded):
    cols, client = seeded
    results = retrieve(
        collection_name="policies_sops",
        query_text="How to handle daily bank reconciliation?",
        n_results=3,
        client=client,
        min_score=0.0,
    )
    assert len(results) >= 1
    assert any("reconciliation" in r["document"].lower() for r in results)


# --- Historical cases retrieval ---

def test_historical_timing_diff(seeded):
    cols, client = seeded
    results = retrieve(
        collection_name="prior_reconciliations",
        query_text="ACH payment timing delay between ledger and bank",
        n_results=5,
        client=client,
        min_score=0.0,
    )
    assert len(results) >= 1
    assert any(r["metadata"]["exception_type"] == "timing_diff" for r in results)


def test_historical_duplicate(seeded):
    cols, client = seeded
    results = retrieve(
        collection_name="prior_reconciliations",
        query_text="duplicate transaction same reference number",
        n_results=5,
        client=client,
        min_score=0.0,
    )
    assert len(results) >= 1
    assert any(r["metadata"]["exception_type"] == "duplicate" for r in results)


def test_historical_filter_by_bank(seeded):
    cols, client = seeded
    results = retrieve(
        collection_name="prior_reconciliations",
        query_text="transaction exception",
        n_results=10,
        where={"bank": "Chase"},
        client=client,
        min_score=0.0,
    )
    assert all(r["metadata"]["bank"] == "Chase" for r in results)


# --- Exception catalog retrieval ---

def test_exception_catalog_timing(seeded):
    cols, client = seeded
    results = retrieve(
        collection_name="exception_catalog",
        query_text="date mismatch timing offset",
        n_results=3,
        client=client,
        min_score=0.0,
    )
    assert len(results) >= 1
    assert any(r["metadata"]["category"] == "timing_diff" for r in results)


def test_exception_catalog_rounding(seeded):
    cols, client = seeded
    results = retrieve(
        collection_name="exception_catalog",
        query_text="amount rounding small difference tolerance",
        n_results=3,
        client=client,
        min_score=0.0,
    )
    assert len(results) >= 1
    assert any(r["metadata"]["category"] == "rounding" for r in results)


# --- Bank rules retrieval ---

def test_bank_rules_retrieval(seeded):
    cols, client = seeded
    results = retrieve(
        collection_name="bank_rules",
        query_text="Chase timing offset days",
        n_results=3,
        client=client,
        min_score=0.0,
    )
    assert len(results) >= 1
    assert any("Chase" in r["document"] for r in results)


# --- Ingest counts ---

def test_ingest_counts(collections):
    assert ingest_sops(collections) == 3
    assert ingest_historical_cases(collections) == 20
    assert ingest_exception_catalog(collections) == 7
    assert ingest_bank_rules(collections) >= 3
