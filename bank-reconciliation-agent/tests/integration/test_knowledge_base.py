"""Tests for knowledge base CRUD + document loader + KB API endpoints."""

import io
import textwrap

import chromadb
import pytest
from fastapi.testclient import TestClient

from src.rag.collection_manager import get_or_create_collection
from src.rag.document_loader import chunk_text, extract_text, file_content_hash
from src.rag.knowledge_base import (
    COLLECTION_NAME,
    delete_document,
    ingest_document,
    list_documents,
    query_knowledge_base,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def chroma(tmp_path):
    return chromadb.EphemeralClient()


# ---------------------------------------------------------------------------
# Document loader tests
# ---------------------------------------------------------------------------

class TestDocumentLoader:

    def test_extract_text_from_bytes(self):
        buf = io.BytesIO(b"Hello, world!\nSecond line.")
        text = extract_text(buf)
        assert "Hello" in text
        assert "Second line" in text

    def test_chunk_text_basic(self):
        text = "A" * 2500
        chunks = chunk_text(text, chunk_size=1000, overlap=200)
        assert len(chunks) >= 2
        # All text should be covered
        total_unique = set()
        for c in chunks:
            total_unique.update(range(len(c)))
        assert len(chunks[0]) <= 1100  # roughly chunk_size

    def test_chunk_empty_text(self):
        assert chunk_text("") == []
        assert chunk_text("   ") == []

    def test_chunk_small_text(self):
        chunks = chunk_text("Short text.", chunk_size=1000, overlap=200)
        assert len(chunks) == 1
        assert chunks[0] == "Short text."

    def test_file_content_hash_deterministic(self):
        data = b"test content"
        h1 = file_content_hash(data)
        h2 = file_content_hash(data)
        assert h1 == h2
        assert len(h1) == 16

    def test_file_content_hash_differs(self):
        assert file_content_hash(b"aaa") != file_content_hash(b"bbb")


# ---------------------------------------------------------------------------
# Knowledge base CRUD tests
# ---------------------------------------------------------------------------

class TestKnowledgeBase:

    def test_ingest_text_document(self, chroma):
        content = "This is a test document about bank reconciliation procedures."
        buf = io.BytesIO(content.encode())
        result = ingest_document(
            "test.txt", buf, content_bytes=content.encode(), client=chroma
        )
        assert result["status"] == "ingested"
        assert result["chunk_count"] >= 1
        assert result["filename"] == "test.txt"

    def test_ingest_duplicate_blocked(self, chroma):
        content = b"Same content twice"
        r1 = ingest_document("dup.txt", io.BytesIO(content), content_bytes=content, client=chroma)
        assert r1["status"] == "ingested"

        r2 = ingest_document("dup.txt", io.BytesIO(content), content_bytes=content, client=chroma)
        assert r2["status"] == "already_exists"

    def test_ingest_empty_document(self, chroma):
        buf = io.BytesIO(b"   ")
        result = ingest_document("empty.txt", buf, content_bytes=b"   ", client=chroma)
        assert result["status"] == "empty_document"

    def test_list_documents(self, chroma):
        content = b"List test document content."
        ingest_document("list_test.txt", io.BytesIO(content), content_bytes=content, client=chroma)
        docs = list_documents(client=chroma)
        assert len(docs) >= 1
        assert any(d["filename"] == "list_test.txt" for d in docs)

    def test_delete_document(self, chroma):
        content = b"Document to be deleted."
        result = ingest_document("delete_me.txt", io.BytesIO(content), content_bytes=content, client=chroma)
        chash = result["content_hash"]

        deleted = delete_document("delete_me.txt", content_hash=chash, client=chroma)
        assert deleted >= 1

        docs = list_documents(client=chroma)
        assert not any(d["filename"] == "delete_me.txt" for d in docs)

    def test_query_knowledge_base(self, chroma):
        content = (
            "The transformer architecture relies on self-attention mechanisms "
            "and dispensed with recurrence entirely. Multi-head attention allows "
            "the model to jointly attend to information from different representation "
            "subspaces."
        ).encode()
        ingest_document("transformer.txt", io.BytesIO(content), content_bytes=content, client=chroma)

        hits = query_knowledge_base("attention mechanism", n_results=3, client=chroma)
        assert len(hits) >= 1
        assert "attention" in hits[0]["document"].lower()

    def test_query_with_filename_filter(self, chroma):
        c1 = b"Document about banking rules and compliance."
        c2 = b"Document about transformer neural network models."
        ingest_document("banking.txt", io.BytesIO(c1), content_bytes=c1, client=chroma)
        ingest_document("neural.txt", io.BytesIO(c2), content_bytes=c2, client=chroma)

        hits = query_knowledge_base(
            "bank rules",
            n_results=5,
            filename_filter="banking.txt",
            client=chroma,
        )
        assert all(h["metadata"]["filename"] == "banking.txt" for h in hits)

    def test_ingest_large_document_chunks(self, chroma):
        """A larger document should produce multiple chunks."""
        content = ("This is a paragraph about topic X. " * 200).encode()
        result = ingest_document(
            "large.txt", io.BytesIO(content), content_bytes=content, client=chroma, chunk_size=500
        )
        assert result["status"] == "ingested"
        assert result["chunk_count"] > 1


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

class TestKnowledgeBaseAPI:

    @pytest.fixture()
    def client(self, chroma, monkeypatch):
        """TestClient with patched ChromaDB."""
        import src.rag.knowledge_base as kb_mod

        monkeypatch.setattr(kb_mod, "get_chroma_client", lambda: chroma)
        from src.workflow.api import app

        return TestClient(app)

    def test_upload_text_file(self, client):
        content = b"Test document for API upload."
        resp = client.post(
            "/knowledge-base/upload",
            files={"file": ("test_api.txt", content, "text/plain")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ingested"
        assert data["filename"] == "test_api.txt"

    def test_upload_unsupported_type(self, client):
        resp = client.post(
            "/knowledge-base/upload",
            files={"file": ("bad.exe", b"binary", "application/octet-stream")},
        )
        assert resp.status_code == 400

    def test_upload_empty_file(self, client):
        resp = client.post(
            "/knowledge-base/upload",
            files={"file": ("empty.txt", b"", "text/plain")},
        )
        assert resp.status_code == 400

    def test_list_documents_api(self, client):
        # Upload first
        client.post(
            "/knowledge-base/upload",
            files={"file": ("list_api.txt", b"Some content here.", "text/plain")},
        )
        resp = client.get("/knowledge-base/documents")
        assert resp.status_code == 200
        docs = resp.json()
        assert any(d["filename"] == "list_api.txt" for d in docs)

    def test_delete_document_api(self, client):
        # Upload
        up = client.post(
            "/knowledge-base/upload",
            files={"file": ("del_api.txt", b"Delete me via API.", "text/plain")},
        )
        chash = up.json()["content_hash"]

        # Delete
        resp = client.delete(
            f"/knowledge-base/documents/del_api.txt",
            params={"content_hash": chash},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted_chunks"] >= 1

    def test_delete_nonexistent(self, client):
        resp = client.delete("/knowledge-base/documents/nonexistent.pdf")
        assert resp.status_code == 404

    def test_search_api(self, client):
        client.post(
            "/knowledge-base/upload",
            files={"file": ("search_api.txt", b"Attention is all you need paper summary.", "text/plain")},
        )
        resp = client.get("/knowledge-base/search", params={"q": "attention"})
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 1
