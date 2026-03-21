"""Unit tests for the output / report layer (Phase 8)."""

import json

import pytest

from src.matching_engine.models import MatchResult
from src.output.report_generator import (
    build_report,
    export_audit_text,
    export_csv_unmatched,
    export_json,
)


@pytest.fixture()
def sample_report():
    matches = [
        MatchResult(ledger_id="L1", bank_id="B1", confidence=1.0, method="exact"),
        MatchResult(ledger_id="L2", bank_id="B2", confidence=0.85, method="tolerance"),
    ]
    unmatched_ledger = [
        {"id": "L3", "date": "2024-01-03", "amount": "300.00", "description": "Unmatched", "reference": "REF3"},
    ]
    unmatched_bank = [
        {"id": "B4", "date": "2024-01-04", "amount": "400.00", "description": "Bank only", "reference": "REF4"},
    ]
    exceptions = [
        {"transaction_id": "L3", "category": "missing", "explanation": "Not found on bank statement"},
    ]
    audit_entries = [
        {"timestamp": "2024-01-01T00:00:00Z", "transaction_id": "L1", "match_method": "exact", "confidence": 1.0, "decision": "auto_approved"},
    ]
    return build_report(
        run_id="TEST-001",
        bank_name="Chase",
        matches=matches,
        unmatched_ledger=unmatched_ledger,
        unmatched_bank=unmatched_bank,
        exceptions=exceptions,
        audit_entries=audit_entries,
    )


class TestBuildReport:
    def test_report_structure(self, sample_report):
        assert sample_report["run_id"] == "TEST-001"
        assert sample_report["bank"] == "Chase"
        assert sample_report["matched_count"] == 2
        assert sample_report["unmatched_count"] == 2
        assert "generated_at" in sample_report

    def test_match_rate(self, sample_report):
        # 2 matched / (2 + 1 + 1) = 50%
        assert sample_report["match_rate_pct"] == 50.0


class TestExportJson:
    def test_valid_json(self, sample_report):
        json_str = export_json(sample_report)
        parsed = json.loads(json_str)
        assert parsed["run_id"] == "TEST-001"
        assert len(parsed["matches"]) == 2


class TestExportCsv:
    def test_csv_output(self):
        unmatched = [
            {"id": "L3", "date": "2024-01-03", "amount": "300.00", "description": "X", "reference": "R3"},
        ]
        csv_str = export_csv_unmatched(unmatched, source_label="ledger")
        assert "source" in csv_str
        assert "L3" in csv_str
        assert "ledger" in csv_str

    def test_empty_csv(self):
        assert export_csv_unmatched([]) == ""


class TestExportAuditText:
    def test_contains_sections(self, sample_report):
        text = export_audit_text(sample_report)
        assert "BANK RECONCILIATION AUDIT DOCUMENT" in text
        assert "TEST-001" in text
        assert "MATCHED PAIRS" in text
        assert "EXCEPTIONS" in text
        assert "AUDIT TRAIL" in text
        assert "END OF AUDIT DOCUMENT" in text

    def test_immutable_format(self, sample_report):
        text = export_audit_text(sample_report)
        # Should contain the match details
        assert "L1 <-> B1" in text
        assert "exact" in text
