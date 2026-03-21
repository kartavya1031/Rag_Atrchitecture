"""Test ingestion and retrieval of the Attention paper PDF.

This test requires the PDF file to be present at the expected path.
Skipped automatically if the file is not found.
"""

from pathlib import Path

import chromadb
import pytest

from src.rag.knowledge_base import (
    delete_document,
    ingest_document,
    list_documents,
    query_knowledge_base,
)

PDF_PATH = Path(r"D:\personal_project\NIPS-2017-attention-is-all-you-need-Paper.pdf")

pytestmark = pytest.mark.skipif(
    not PDF_PATH.exists(),
    reason=f"Attention paper PDF not found at {PDF_PATH}",
)


@pytest.fixture()
def chroma(tmp_path):
    return chromadb.PersistentClient(path=str(tmp_path / "chroma"))


class TestAttentionPaperIngestion:

    def test_ingest_pdf(self, chroma):
        result = ingest_document(PDF_PATH.name, PDF_PATH, client=chroma)
        assert result["status"] == "ingested"
        assert result["chunk_count"] > 5  # Paper should produce many chunks
        assert result["doc_type"] == ".pdf"

    def test_query_attention_mechanism(self, chroma):
        ingest_document(PDF_PATH.name, PDF_PATH, client=chroma)
        hits = query_knowledge_base("multi-head attention mechanism", n_results=5, client=chroma)
        assert len(hits) >= 1
        combined = " ".join(h["document"].lower() for h in hits)
        assert "attention" in combined

    def test_query_transformer_architecture(self, chroma):
        ingest_document(PDF_PATH.name, PDF_PATH, client=chroma)
        hits = query_knowledge_base("transformer encoder decoder architecture", n_results=5, client=chroma)
        assert len(hits) >= 1
        combined = " ".join(h["document"].lower() for h in hits)
        assert any(word in combined for word in ["encoder", "decoder", "transformer", "layer"])

    def test_query_positional_encoding(self, chroma):
        ingest_document(PDF_PATH.name, PDF_PATH, client=chroma)
        hits = query_knowledge_base("positional encoding sinusoidal", n_results=5, client=chroma)
        assert len(hits) >= 1

    def test_duplicate_ingestion_blocked(self, chroma):
        r1 = ingest_document(PDF_PATH.name, PDF_PATH, client=chroma)
        assert r1["status"] == "ingested"
        r2 = ingest_document(PDF_PATH.name, PDF_PATH, client=chroma)
        assert r2["status"] == "already_exists"

    def test_delete_pdf(self, chroma):
        result = ingest_document(PDF_PATH.name, PDF_PATH, client=chroma)
        deleted = delete_document(PDF_PATH.name, content_hash=result["content_hash"], client=chroma)
        assert deleted == result["chunk_count"]
        docs = list_documents(client=chroma)
        assert not any(d["filename"] == PDF_PATH.name for d in docs)

    def test_list_shows_ingested_pdf(self, chroma):
        ingest_document(PDF_PATH.name, PDF_PATH, client=chroma)
        docs = list_documents(client=chroma)
        assert any(d["filename"] == PDF_PATH.name for d in docs)
        doc = next(d for d in docs if d["filename"] == PDF_PATH.name)
        assert doc["doc_type"] == ".pdf"
        assert doc["chunk_count"] > 0
