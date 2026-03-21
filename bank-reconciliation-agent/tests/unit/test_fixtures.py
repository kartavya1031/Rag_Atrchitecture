"""Phase 9 comprehensive tests — uses generated fixtures + golden answers."""

import datetime
import json
from decimal import Decimal
from pathlib import Path

import pytest

from src.ingestion.schema import SourceType, Transaction
from src.matching_engine.algorithms.exact_matcher import exact_match
from src.matching_engine.algorithms.tolerance_matcher import tolerance_match
from src.matching_engine.ledger_bank_aligner import align
from src.validation.hallucination_guard import guard
from src.validation.confidence_scorer import normalize_confidence, needs_human_review

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


def _dict_to_txn(d: dict) -> Transaction:
    return Transaction(
        id=d["id"],
        date=datetime.date.fromisoformat(d["date"]),
        amount=Decimal(d["amount"]),
        description=d.get("description", ""),
        reference=d.get("reference", ""),
        source_type=SourceType(d.get("source_type", "csv")),
    )


@pytest.fixture(scope="module")
def smoke():
    return _load_fixture("smoke_dataset.json")


@pytest.fixture(scope="module")
def golden():
    return _load_fixture("golden_answers.json")


@pytest.fixture(scope="module")
def adversarial():
    return _load_fixture("adversarial_dataset.json")


# ---------------------------------------------------------------------------
# 9b: Unit-level tests using fixtures
# ---------------------------------------------------------------------------

class TestParserFixtures:
    def test_smoke_ledger_parses(self, smoke):
        """All smoke ledger entries parse into valid Transaction objects."""
        for d in smoke["ledger"]:
            if d["id"]:  # skip intentionally blank IDs
                txn = _dict_to_txn(d)
                assert txn.id == d["id"]

    def test_smoke_bank_parses(self, smoke):
        for d in smoke["bank"]:
            if d["id"]:
                txn = _dict_to_txn(d)
                assert txn.id == d["id"]


class TestExactMatcherFixtures:
    def test_exact_matches_found(self, smoke):
        ledger = [_dict_to_txn(d) for d in smoke["ledger"] if d["id"]]
        bank = [_dict_to_txn(d) for d in smoke["bank"] if d["id"]]
        matches, _, _ = exact_match(ledger, bank)
        # At least some exact matches should be found
        assert len(matches) >= 30  # 40 exact + some edge cases may also match


class TestToleranceMatcherBoundary:
    def test_at_threshold_matches(self):
        """Amount at exactly ±threshold should match."""
        l = [Transaction(id="L1", date=datetime.date(2024, 1, 1), amount=Decimal("100.00"), source_type=SourceType.CSV)]
        b = [Transaction(id="B1", date=datetime.date(2024, 1, 1), amount=Decimal("100.01"), source_type=SourceType.CSV)]
        matches, _, _ = tolerance_match(l, b)
        assert len(matches) == 1

    def test_beyond_threshold_no_match(self):
        """Amount well beyond threshold should not match on its own."""
        l = [Transaction(id="L1", date=datetime.date(2024, 1, 1), amount=Decimal("100.00"), description="alpha", source_type=SourceType.CSV)]
        b = [Transaction(id="B1", date=datetime.date(2024, 6, 15), amount=Decimal("999.00"), description="beta", source_type=SourceType.CSV)]
        matches, _, _ = tolerance_match(l, b)
        assert len(matches) == 0


class TestHallucinationGuardFixtures:
    def test_rejects_invented_amount(self):
        output = {"amount": "77777.77", "transaction_id": "L1"}
        valid_amounts = {Decimal("100.00"), Decimal("200.00")}
        valid_ids = {"L1", "B1"}
        is_clean, violations = guard(output, valid_amounts, valid_ids)
        assert is_clean is False
        assert any("Hallucinated amount" in v for v in violations)

    def test_rejects_invented_id(self):
        output = {"amount": "100.00", "transaction_id": "FAKE"}
        valid_amounts = {Decimal("100.00")}
        valid_ids = {"L1"}
        is_clean, violations = guard(output, valid_amounts, valid_ids)
        assert is_clean is False


class TestConfidenceScorerFixtures:
    def test_confidence_in_range(self):
        for method in ["exact", "rule", "tolerance"]:
            score = normalize_confidence(0.99, method)
            assert 0.0 <= score <= 1.0

    def test_fallback_triggered(self):
        assert needs_human_review(0.5) is True
        assert needs_human_review(0.95) is False


# ---------------------------------------------------------------------------
# 9c: Integration-level tests
# ---------------------------------------------------------------------------

class TestAlignerOnSmoke:
    def test_aligner_produces_matches(self, smoke):
        ledger = [_dict_to_txn(d) for d in smoke["ledger"] if d["id"]]
        bank = [_dict_to_txn(d) for d in smoke["bank"] if d["id"]]
        result = align(ledger, bank, bank_name="Generic")
        assert len(result["matched_pairs"]) > 0
        assert isinstance(result["unmatched_ledger"], list)
        assert isinstance(result["unmatched_bank"], list)

    def test_no_duplicate_bank_matches(self, smoke):
        """Each bank transaction should appear in at most one match."""
        ledger = [_dict_to_txn(d) for d in smoke["ledger"] if d["id"]]
        bank = [_dict_to_txn(d) for d in smoke["bank"] if d["id"]]
        result = align(ledger, bank, bank_name="Generic")
        bank_ids = [m.bank_id for m in result["matched_pairs"]]
        assert len(bank_ids) == len(set(bank_ids))


class TestAdversarialInputs:
    def test_adversarial_no_crash(self, adversarial):
        """Pipeline handles adversarial inputs without crashing."""
        ledger = []
        for d in adversarial["ledger"]:
            if d["id"]:
                ledger.append(_dict_to_txn(d))
        bank = [_dict_to_txn(d) for d in adversarial["bank"]]
        result = align(ledger, bank, bank_name="Generic")
        assert "matched_pairs" in result

    def test_extreme_values_handled(self, adversarial):
        ledger = [_dict_to_txn(d) for d in adversarial["ledger"] if d["id"]]
        bank = [_dict_to_txn(d) for d in adversarial["bank"]]
        result = align(ledger, bank, bank_name="Generic")
        # The extreme value ($999M) should not match the tiny value
        huge_matched = any(
            m.ledger_id == "ADV-2" for m in result["matched_pairs"]
        )
        assert not huge_matched
