"""Live E2E tests — require a running OpenAI API key.

Skipped automatically when OPENAI_API_KEY is not set or invalid.
Run with:  pytest tests/e2e/ -v
"""

import os
import io
import tempfile

import pytest

# Skip entire module if no API key
_api_key = os.environ.get("OPENAI_API_KEY", "")
pytestmark = pytest.mark.skipif(
    not _api_key or _api_key.startswith("sk-PLACEHOLDER"),
    reason="OPENAI_API_KEY not set or is placeholder",
)


# ------------------------------------------------------------------
# Embedding tests
# ------------------------------------------------------------------

class TestLiveEmbeddings:
    """Test real OpenAI embedding generation."""

    def test_embed_single_text(self):
        from openai import OpenAI

        client = OpenAI()
        model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        resp = client.embeddings.create(input=["bank reconciliation"], model=model)
        assert len(resp.data) == 1
        vec = resp.data[0].embedding
        assert len(vec) > 0
        assert all(isinstance(v, float) for v in vec[:10])

    def test_embed_batch(self):
        from openai import OpenAI

        client = OpenAI()
        model = os.environ.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        texts = [
            "daily bank statement reconciliation",
            "attention is all you need transformer architecture",
            "company expense policy guidelines",
        ]
        resp = client.embeddings.create(input=texts, model=model)
        assert len(resp.data) == 3
        # Vectors should differ from each other
        v1 = resp.data[0].embedding
        v2 = resp.data[1].embedding
        assert v1 != v2


# ------------------------------------------------------------------
# Chat / Classification tests
# ------------------------------------------------------------------

class TestLiveChatCompletion:
    """Test real GPT-4o chat completions."""

    def test_simple_completion(self):
        from openai import OpenAI

        client = OpenAI()
        model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is 2 + 2? Reply with just the number."},
            ],
            max_tokens=10,
        )
        answer = resp.choices[0].message.content.strip()
        assert "4" in answer

    def test_exception_classification(self):
        from openai import OpenAI

        client = OpenAI()
        model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a bank reconciliation expert. "
                        "Classify the following transaction exception into one of: "
                        "TIMING_DIFFERENCE, MISSING_TRANSACTION, DUPLICATE_ENTRY, "
                        "AMOUNT_MISMATCH, BANK_FEE, REVERSAL, OTHER. "
                        "Reply with ONLY the classification label."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "A payment of $500 appears in the ledger on Jan 1 but "
                        "the bank shows $500 clearing on Jan 3."
                    ),
                },
            ],
            max_tokens=20,
        )
        label = resp.choices[0].message.content.strip().upper()
        assert label in {
            "TIMING_DIFFERENCE",
            "MISSING_TRANSACTION",
            "DUPLICATE_ENTRY",
            "AMOUNT_MISMATCH",
            "BANK_FEE",
            "REVERSAL",
            "OTHER",
        }

    def test_explanation_generation(self):
        from openai import OpenAI

        client = OpenAI()
        model = os.environ.get("OPENAI_CHAT_MODEL", "gpt-4o")
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a bank reconciliation assistant. "
                        "Explain why two transactions match or don't match. "
                        "Be concise."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Ledger: $1000 payment to Vendor A on 2024-01-15. "
                        "Bank: $1000 debit on 2024-01-16 ref VENDOR-A. "
                        "These were matched with 95% confidence."
                    ),
                },
            ],
            max_tokens=150,
        )
        explanation = resp.choices[0].message.content.strip()
        assert len(explanation) > 20  # Should be a meaningful explanation


# ------------------------------------------------------------------
# Knowledge Base + RAG tests
# ------------------------------------------------------------------

class TestLiveKnowledgeBase:
    """Test document ingestion and retrieval with real embeddings (or default)."""

    @pytest.fixture()
    def _chroma_client(self, tmp_path):
        import chromadb
        return chromadb.EphemeralClient()

    def test_ingest_and_query_text_doc(self, _chroma_client):
        from src.rag.knowledge_base import ingest_document, query_knowledge_base

        content = (
            "The Transformer model architecture relies entirely on attention mechanisms, "
            "dispensing with recurrence and convolutions. It uses multi-head self-attention "
            "to compute representations of its input and output."
        )
        content_bytes = content.encode("utf-8")
        buf = io.BytesIO(content_bytes)

        result = ingest_document(
            "transformer_overview.txt",
            buf,
            content_bytes=content_bytes,
            client=_chroma_client,
        )
        assert result["status"] == "ingested"
        assert result["chunk_count"] >= 1

        # Query
        hits = query_knowledge_base(
            "attention mechanism in transformers",
            n_results=3,
            client=_chroma_client,
        )
        assert len(hits) >= 1
        assert "attention" in hits[0]["document"].lower()

    def test_ingest_pdf_if_available(self, _chroma_client):
        """Test with the attention paper PDF if it exists on disk."""
        from pathlib import Path
        from src.rag.knowledge_base import ingest_document, query_knowledge_base

        pdf_path = Path(r"D:\personal_project\NIPS-2017-attention-is-all-you-need-Paper.pdf")
        if not pdf_path.exists():
            pytest.skip("Attention paper PDF not found at expected path")

        result = ingest_document(
            pdf_path.name,
            pdf_path,
            client=_chroma_client,
        )
        assert result["status"] == "ingested"
        assert result["chunk_count"] > 0

        # Query for transformer concepts
        hits = query_knowledge_base(
            "multi-head attention mechanism",
            n_results=5,
            client=_chroma_client,
        )
        assert len(hits) >= 1
        # At least one result should mention attention
        texts = " ".join(h["document"].lower() for h in hits)
        assert "attention" in texts


# ------------------------------------------------------------------
# Full graph integration with real LLM
# ------------------------------------------------------------------

class TestLiveGraph:
    """Test the full LangGraph agent with real OpenAI calls."""

    def test_graph_classify_and_explain(self):
        """Run a small reconciliation through the graph with real LLM."""
        from src.graph.state import ReconciliationState
        from src.graph.graph_builder import build_graph
        from src.ingestion.schema import Transaction, SourceType
        import datetime

        ledger = [
            Transaction(
                id="L001",
                date=datetime.date(2024, 1, 15),
                amount=1000.00,
                description="Payment to Vendor A",
                reference="REF001",
                source_type=SourceType.CSV,
            )
        ]
        bank = [
            Transaction(
                id="B001",
                date=datetime.date(2024, 1, 16),
                amount=1000.00,
                description="VENDOR-A PAYMENT",
                reference="REF001",
                source_type=SourceType.CSV,
            )
        ]

        state: ReconciliationState = {
            "ledger_transactions": ledger,
            "bank_transactions": bank,
            "matched_pairs": [],
            "unmatched_ledger": [],
            "unmatched_bank": [],
            "exceptions": [],
            "explanations": {},
            "confidence_scores": {},
            "needs_human_review": [],
            "audit_log": [],
            "bank_name": "Generic",
        }

        graph = build_graph().compile()
        result = graph.invoke(state)

        # We should get some output — matched or exception
        assert isinstance(result, dict)
        # The graph should produce audit entries
        assert "audit_log" in result
