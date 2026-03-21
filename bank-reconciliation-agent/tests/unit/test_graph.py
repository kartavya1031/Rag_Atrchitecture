"""Unit tests for graph nodes and graph builder — no OpenAI API key required."""

import datetime
from decimal import Decimal
from unittest.mock import patch, MagicMock

import pytest

from src.graph.graph_builder import (
    build_graph,
    deterministic_match_node,
    output_node,
)
from src.graph.nodes.soft_matcher import soft_matcher
from src.graph.nodes.validator_node import validator_node
from src.graph.routes import after_deterministic
from src.graph.state import ExceptionItem, ReconciliationState
from src.ingestion.schema import SourceType, Transaction
from src.matching_engine.models import MatchResult


def _txn(id: str, amount: float, date_str: str, desc: str = "", ref: str = "") -> Transaction:
    return Transaction(
        id=id,
        date=datetime.date.fromisoformat(date_str),
        amount=Decimal(str(amount)),
        description=desc,
        reference=ref,
        source_type=SourceType.CSV,
    )


# ---------- deterministic_match_node ----------

class TestDeterministicMatchNode:
    def test_all_exact_match(self):
        state: ReconciliationState = {
            "ledger_transactions": [_txn("L1", 100.0, "2024-01-01", ref="REF1")],
            "bank_transactions": [_txn("B1", 100.0, "2024-01-01", ref="REF1")],
            "bank_name": "Generic",
        }
        result = deterministic_match_node(state)
        assert len(result["matches"]) == 1
        assert len(result["unmatched_ledger"]) == 0
        assert len(result["unmatched_bank"]) == 0

    def test_unmatched_remain(self):
        state: ReconciliationState = {
            "ledger_transactions": [
                _txn("L1", 100.0, "2024-01-01", ref="REF1"),
                _txn("L2", 999.0, "2024-06-01", ref="REF_NONE"),
            ],
            "bank_transactions": [_txn("B1", 100.0, "2024-01-01", ref="REF1")],
            "bank_name": "Generic",
        }
        result = deterministic_match_node(state)
        assert len(result["matches"]) == 1
        assert len(result["unmatched_ledger"]) == 1
        assert result["unmatched_ledger"][0].id == "L2"


# ---------- routes ----------

class TestRoutes:
    def test_route_to_classifier_when_unmatched(self):
        state: ReconciliationState = {
            "unmatched_ledger": [_txn("L1", 100.0, "2024-01-01")],
            "unmatched_bank": [],
        }
        assert after_deterministic(state) == "exception_classifier"

    def test_route_to_output_when_all_matched(self):
        state: ReconciliationState = {
            "unmatched_ledger": [],
            "unmatched_bank": [],
        }
        assert after_deterministic(state) == "output"


# ---------- soft_matcher ----------

class TestSoftMatcher:
    def test_soft_match_found(self):
        state: ReconciliationState = {
            "unmatched_ledger": [_txn("L1", 100.0, "2024-01-01", desc="PAYMENT ABC")],
            "unmatched_bank": [_txn("B1", 100.0, "2024-01-02", desc="PAYMENT ABC CORP")],
            "soft_match_candidates": [],
        }
        result = soft_matcher(state)
        assert len(result["soft_match_candidates"]) == 1
        m = result["soft_match_candidates"][0]
        assert m.ledger_id == "L1"
        assert m.bank_id == "B1"
        assert m.method == "soft"

    def test_no_soft_match_when_amounts_differ(self):
        state: ReconciliationState = {
            "unmatched_ledger": [_txn("L1", 100.0, "2024-01-01", desc="PAYMENT")],
            "unmatched_bank": [_txn("B1", 9999.0, "2024-06-15", desc="TOTALLY DIFFERENT")],
            "soft_match_candidates": [],
        }
        result = soft_matcher(state)
        assert len(result["soft_match_candidates"]) == 0


# ---------- validator_node ----------

class TestValidatorNode:
    def test_valid_match_passes(self):
        state: ReconciliationState = {
            "soft_match_candidates": [
                MatchResult(ledger_id="L1", bank_id="B1", confidence=0.9, method="soft"),
            ],
            "exceptions": [],
        }
        result = validator_node(state)
        assert len(result["validation_results"]["valid"]) == 1
        assert len(result["validation_results"]["invalid"]) == 0

    def test_low_confidence_exception_goes_to_review(self):
        state: ReconciliationState = {
            "soft_match_candidates": [],
            "exceptions": [
                ExceptionItem(
                    transaction_id="L1",
                    source="ledger",
                    category="unknown",
                    confidence=0.3,
                    explanation="Cannot classify",
                ),
            ],
        }
        result = validator_node(state)
        assert len(result["human_review_queue"]) == 1
        assert result["human_review_queue"][0]["transaction_id"] == "L1"

    def test_high_confidence_exception_no_review(self):
        state: ReconciliationState = {
            "soft_match_candidates": [],
            "exceptions": [
                ExceptionItem(
                    transaction_id="L1",
                    source="ledger",
                    category="timing_diff",
                    confidence=0.95,
                    explanation="Timing delay",
                ),
            ],
        }
        result = validator_node(state)
        assert len(result["human_review_queue"]) == 0


# ---------- output_node ----------

class TestOutputNode:
    def test_report_counts(self):
        state: ReconciliationState = {
            "matches": [
                MatchResult(ledger_id="L1", bank_id="B1", confidence=1.0, method="exact"),
            ],
            "soft_match_candidates": [
                MatchResult(ledger_id="L2", bank_id="B2", confidence=0.8, method="soft"),
            ],
            "unmatched_ledger": [_txn("L3", 50.0, "2024-01-01")],
            "unmatched_bank": [],
            "exceptions": [ExceptionItem(transaction_id="L3", source="ledger", category="missing", confidence=0.9)],
            "human_review_queue": [],
        }
        result = output_node(state)
        report = result["final_report"]
        assert report["matched_count"] == 2
        assert report["unmatched_ledger_count"] == 1
        assert report["unmatched_bank_count"] == 0
        assert report["exception_count"] == 1
        assert report["human_review_count"] == 0


# ---------- graph_builder ----------

class TestGraphBuilder:
    def test_graph_compiles(self):
        graph = build_graph()
        compiled = graph.compile()
        assert compiled is not None
