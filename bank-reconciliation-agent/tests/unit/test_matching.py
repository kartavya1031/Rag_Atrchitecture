"""Unit tests for deterministic matching engine."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from src.ingestion.schema import SourceType, Transaction
from src.matching_engine.algorithms.exact_matcher import exact_match
from src.matching_engine.algorithms.rule_matcher import rule_match
from src.matching_engine.algorithms.tolerance_matcher import tolerance_match
from src.matching_engine.ledger_bank_aligner import align
from src.matching_engine.models import MatchResult


def _txn(id: str, dt: date, amount: str, desc: str = "", ref: str = "", source: SourceType = SourceType.CSV) -> Transaction:
    return Transaction(id=id, date=dt, amount=Decimal(amount), description=desc, reference=ref, source_type=source)


class TestExactMatcher:
    def test_perfect_match(self):
        ledger = [_txn("L1", date(2026, 3, 1), "100.00", ref="R1")]
        bank = [_txn("B1", date(2026, 3, 1), "100.00", ref="R1")]
        matched, ul, ub = exact_match(ledger, bank)
        assert len(matched) == 1
        assert matched[0].confidence == 1.0
        assert matched[0].method == "exact"
        assert len(ul) == 0
        assert len(ub) == 0

    def test_no_match_different_amount(self):
        ledger = [_txn("L1", date(2026, 3, 1), "100.00", ref="R1")]
        bank = [_txn("B1", date(2026, 3, 1), "100.01", ref="R1")]
        matched, ul, ub = exact_match(ledger, bank)
        assert len(matched) == 0
        assert len(ul) == 1
        assert len(ub) == 1

    def test_no_match_different_date(self):
        ledger = [_txn("L1", date(2026, 3, 1), "100.00", ref="R1")]
        bank = [_txn("B1", date(2026, 3, 2), "100.00", ref="R1")]
        matched, ul, ub = exact_match(ledger, bank)
        assert len(matched) == 0

    def test_multiple_matches(self):
        ledger = [
            _txn("L1", date(2026, 3, 1), "100.00", ref="R1"),
            _txn("L2", date(2026, 3, 2), "200.00", ref="R2"),
        ]
        bank = [
            _txn("B1", date(2026, 3, 1), "100.00", ref="R1"),
            _txn("B2", date(2026, 3, 2), "200.00", ref="R2"),
        ]
        matched, ul, ub = exact_match(ledger, bank)
        assert len(matched) == 2
        assert len(ul) == 0


class TestRuleMatcher:
    def test_timing_offset_chase(self):
        """Chase has 1-day timing offset; same-amount txn 1 day apart should match."""
        ledger = [_txn("L1", date(2026, 3, 1), "500.00", ref="R1")]
        bank = [_txn("B1", date(2026, 3, 2), "500.00", ref="R1")]
        matched, ul, ub = rule_match(ledger, bank, bank_name="Chase")
        assert len(matched) == 1
        assert matched[0].method == "rule"

    def test_timing_offset_too_large(self):
        """Chase offset is 1 day; 3 days apart should NOT match."""
        ledger = [_txn("L1", date(2026, 3, 1), "500.00", ref="R1")]
        bank = [_txn("B1", date(2026, 3, 4), "500.00", ref="R1")]
        matched, ul, ub = rule_match(ledger, bank, bank_name="Chase")
        assert len(matched) == 0


class TestToleranceMatcher:
    def test_amount_within_tolerance(self):
        """$0.01 difference should match with tolerance."""
        ledger = [_txn("L1", date(2026, 3, 1), "100.00", desc="Payment to vendor")]
        bank = [_txn("B1", date(2026, 3, 1), "100.01", desc="Payment to vendor")]
        matched, ul, ub = tolerance_match(ledger, bank)
        assert len(matched) == 1
        assert matched[0].method == "tolerance"

    def test_amount_at_exact_boundary(self):
        """$0.01 tolerance boundary — exactly $0.01 diff should still match."""
        ledger = [_txn("L1", date(2026, 3, 1), "100.00", desc="Monthly rent")]
        bank = [_txn("B1", date(2026, 3, 1), "100.01", desc="Monthly rent")]
        matched, ul, ub = tolerance_match(ledger, bank)
        assert len(matched) == 1

    def test_amount_beyond_tolerance_no_fuzzy(self):
        """$10 difference with dissimilar descriptions should NOT match."""
        ledger = [_txn("L1", date(2026, 3, 1), "100.00", desc="Alpha")]
        bank = [_txn("B1", date(2026, 3, 1), "110.00", desc="Beta")]
        matched, ul, ub = tolerance_match(ledger, bank)
        assert len(matched) == 0

    def test_date_within_tolerance(self):
        """2 days apart should match when descriptions are similar."""
        ledger = [_txn("L1", date(2026, 3, 1), "100.00", desc="ACH Payroll")]
        bank = [_txn("B1", date(2026, 3, 3), "100.00", desc="ACH Payroll")]
        matched, ul, ub = tolerance_match(ledger, bank)
        assert len(matched) == 1

    def test_date_beyond_tolerance(self):
        """5 days apart with same amount should NOT match (date tolerance = 2)."""
        ledger = [_txn("L1", date(2026, 3, 1), "100.00", desc="Wire")]
        bank = [_txn("B1", date(2026, 3, 6), "100.00", desc="Wire")]
        matched, ul, ub = tolerance_match(ledger, bank)
        assert len(matched) == 0


class TestLedgerBankAligner:
    def test_full_alignment_mixed(self):
        """Test the full priority-order alignment: exact → rule → tolerance."""
        ledger = [
            _txn("L1", date(2026, 3, 1), "1000.00", desc="Exact match", ref="R1"),
            _txn("L2", date(2026, 3, 1), "500.00", desc="Timing diff", ref="R2"),
            _txn("L3", date(2026, 3, 1), "250.00", desc="Fuzzy match payment"),
        ]
        bank = [
            _txn("B1", date(2026, 3, 1), "1000.00", desc="Exact match", ref="R1"),  # exact
            _txn("B2", date(2026, 3, 2), "500.00", desc="Timing diff", ref="R2"),   # rule (Chase 1d offset)
            _txn("B3", date(2026, 3, 1), "250.01", desc="Fuzzy match payment"),     # tolerance
        ]
        result = align(ledger, bank, bank_name="Chase")
        assert len(result["matched_pairs"]) == 3
        methods = {m.method for m in result["matched_pairs"]}
        assert "exact" in methods
        assert len(result["unmatched_ledger"]) == 0
        assert len(result["unmatched_bank"]) == 0

    def test_unmatched_remain(self):
        """Transactions with no match remain unmatched."""
        ledger = [_txn("L1", date(2026, 3, 1), "9999.00", desc="Orphan")]
        bank = [_txn("B1", date(2026, 3, 1), "1.00", desc="Different")]
        result = align(ledger, bank)
        assert len(result["matched_pairs"]) == 0
        assert len(result["unmatched_ledger"]) == 1
        assert len(result["unmatched_bank"]) == 1
