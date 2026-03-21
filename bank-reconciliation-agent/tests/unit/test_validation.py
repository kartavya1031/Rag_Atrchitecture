"""Unit tests for validation & guardrails (Phase 6)."""

from decimal import Decimal

import pytest

from src.validation.hallucination_guard import check_amounts, check_transaction_ids, guard
from src.validation.confidence_scorer import normalize_confidence, needs_human_review
from src.validation.audit_trail import AuditTrail


# ---------- hallucination_guard ----------

class TestHallucinationGuardAmounts:
    def test_valid_amount_passes(self):
        output = {"amount": "100.00"}
        valid = {Decimal("100.00")}
        violations = check_amounts(output, valid)
        assert violations == []

    def test_invented_amount_rejected(self):
        output = {"amount": "999.99"}
        valid = {Decimal("100.00"), Decimal("200.00")}
        violations = check_amounts(output, valid)
        assert len(violations) == 1
        assert "Hallucinated" in violations[0]

    def test_negative_amount_matches_positive(self):
        output = {"amount": "-100.00"}
        valid = {Decimal("100.00")}
        violations = check_amounts(output, valid)
        assert violations == []

    def test_nested_amounts(self):
        output = {"matches": [{"ledger_amount": "50.00"}, {"bank_amount": "77.77"}]}
        valid = {Decimal("50.00")}
        violations = check_amounts(output, valid)
        assert len(violations) == 1
        assert "77.77" in violations[0]


class TestHallucinationGuardIds:
    def test_valid_id_passes(self):
        output = {"transaction_id": "TXN-001"}
        valid = {"TXN-001", "TXN-002"}
        violations = check_transaction_ids(output, valid)
        assert violations == []

    def test_invented_id_rejected(self):
        output = {"transaction_id": "FAKE-999"}
        valid = {"TXN-001"}
        violations = check_transaction_ids(output, valid)
        assert len(violations) == 1
        assert "FAKE-999" in violations[0]

    def test_nested_ids(self):
        output = {"proposed": [{"ledger_id": "L1", "bank_id": "BFAKE"}]}
        valid = {"L1", "B1"}
        violations = check_transaction_ids(output, valid)
        assert len(violations) == 1
        assert "BFAKE" in violations[0]


class TestGuardCombined:
    def test_clean_output(self):
        output = {"transaction_id": "T1", "amount": "100.00"}
        is_clean, violations = guard(output, {Decimal("100.00")}, {"T1"})
        assert is_clean is True
        assert violations == []

    def test_dirty_output(self):
        output = {"transaction_id": "FAKE", "amount": "999.99"}
        is_clean, violations = guard(output, {Decimal("100.00")}, {"T1"})
        assert is_clean is False
        assert len(violations) == 2


# ---------- confidence_scorer ----------

class TestConfidenceScorer:
    def test_normalize_exact(self):
        score = normalize_confidence(1.0, "exact")
        assert score == 1.0

    def test_normalize_capped(self):
        score = normalize_confidence(0.99, "tolerance")
        assert 0.0 <= score <= 1.0

    def test_needs_review_low(self):
        assert needs_human_review(0.5) is True

    def test_no_review_high(self):
        assert needs_human_review(0.95) is False

    def test_threshold_boundary(self):
        # 0.70 is the configured threshold; equal should NOT trigger
        assert needs_human_review(0.70) is False

    def test_just_below_threshold(self):
        assert needs_human_review(0.69) is True


# ---------- audit_trail ----------

class TestAuditTrail:
    def test_record_and_read(self, tmp_path):
        trail = AuditTrail(log_path=tmp_path / "audit.jsonl")
        entry = trail.record(
            run_id="RUN-001",
            transaction_id="TXN-001",
            match_method="exact",
            confidence=1.0,
            decision="auto_approved",
        )
        assert entry["run_id"] == "RUN-001"
        entries = trail.read_all()
        assert len(entries) == 1
        assert entries[0]["transaction_id"] == "TXN-001"

    def test_append_only(self, tmp_path):
        trail = AuditTrail(log_path=tmp_path / "audit.jsonl")
        trail.record(run_id="R1", transaction_id="T1", match_method="exact", confidence=1.0, decision="approved")
        trail.record(run_id="R1", transaction_id="T2", match_method="soft", confidence=0.8, decision="review")
        entries = trail.read_all()
        assert len(entries) == 2

    def test_empty_log(self, tmp_path):
        trail = AuditTrail(log_path=tmp_path / "nonexistent.jsonl")
        assert trail.read_all() == []
