"""Unit tests for metrics (Phase 10)."""

import pytest

from src.utils.metrics import (
    _confusion_matrix,
    precision,
    recall,
    f1_score,
    false_positive_rate,
    mcc,
    exception_detection_rate,
    human_fallback_rate,
    amount_variance_pct,
    confidence_ece,
    evaluate_run,
)


@pytest.fixture()
def perfect_cm():
    return {"tp": 10, "fp": 0, "fn": 0, "tn": 5}


@pytest.fixture()
def mixed_cm():
    return {"tp": 8, "fp": 2, "fn": 1, "tn": 5}


class TestConfusionMatrix:
    def test_perfect_match(self):
        predicted = [{"ledger_id": "L1", "bank_id": "B1"}]
        gt = [{"ledger_id": "L1", "bank_id": "B1", "should_match": True}]
        cm = _confusion_matrix(predicted, gt)
        assert cm["tp"] == 1
        assert cm["fp"] == 0
        assert cm["fn"] == 0

    def test_false_positive(self):
        predicted = [{"ledger_id": "L1", "bank_id": "B1"}, {"ledger_id": "L2", "bank_id": "B3"}]
        gt = [{"ledger_id": "L1", "bank_id": "B1", "should_match": True}]
        cm = _confusion_matrix(predicted, gt)
        assert cm["tp"] == 1
        assert cm["fp"] == 1

    def test_false_negative(self):
        predicted = []
        gt = [{"ledger_id": "L1", "bank_id": "B1", "should_match": True}]
        cm = _confusion_matrix(predicted, gt)
        assert cm["fn"] == 1


class TestPrecisionRecall:
    def test_perfect_precision(self, perfect_cm):
        assert precision(perfect_cm) == 1.0

    def test_perfect_recall(self, perfect_cm):
        assert recall(perfect_cm) == 1.0

    def test_mixed_precision(self, mixed_cm):
        assert precision(mixed_cm) == 0.8  # 8 / (8+2)

    def test_mixed_recall(self, mixed_cm):
        p = recall(mixed_cm)
        assert abs(p - 8 / 9) < 0.001  # 8 / (8+1)


class TestF1:
    def test_perfect_f1(self, perfect_cm):
        assert f1_score(perfect_cm) == 1.0

    def test_zero_denominator(self):
        cm = {"tp": 0, "fp": 0, "fn": 0, "tn": 0}
        assert f1_score(cm) == 0.0


class TestFPR:
    def test_zero_fpr(self, perfect_cm):
        assert false_positive_rate(perfect_cm) == 0.0

    def test_positive_fpr(self, mixed_cm):
        fpr = false_positive_rate(mixed_cm)
        assert abs(fpr - 2 / 7) < 0.001


class TestMCC:
    def test_perfect_mcc(self, perfect_cm):
        assert mcc(perfect_cm) == 1.0

    def test_mcc_in_range(self, mixed_cm):
        m = mcc(mixed_cm)
        assert -1.0 <= m <= 1.0


class TestExceptionDetection:
    def test_all_detected(self):
        assert exception_detection_rate(["E1", "E2"], ["E1", "E2"]) == 1.0

    def test_partial_detection(self):
        rate = exception_detection_rate(["E1"], ["E1", "E2"])
        assert rate == 0.5

    def test_no_exceptions(self):
        assert exception_detection_rate([], []) == 1.0


class TestHumanFallbackRate:
    def test_no_fallback(self):
        assert human_fallback_rate(0, 100) == 0.0

    def test_some_fallback(self):
        assert human_fallback_rate(5, 100) == 0.05


class TestAmountVariance:
    def test_exact_match(self):
        assert amount_variance_pct(1000.0, 1000.0, 1000.0) == 0.0

    def test_small_variance(self):
        v = amount_variance_pct(1000.0, 1000.01, 1000.0)
        assert v < 0.01


class TestConfidenceECE:
    def test_perfect_calibration(self):
        # All predictions with confidence 1.0 are correct
        preds = [(1.0, True)] * 10
        assert confidence_ece(preds) == 0.0

    def test_poor_calibration(self):
        # High confidence but all wrong
        preds = [(0.9, False)] * 10
        ece = confidence_ece(preds)
        assert ece > 0.5


class TestEvaluateRun:
    def test_full_evaluation(self):
        predicted = [{"ledger_id": "L1", "bank_id": "B1"}]
        gt = [{"ledger_id": "L1", "bank_id": "B1", "should_match": True}]
        metrics = evaluate_run(predicted, gt)
        assert metrics["precision"] == 1.0
        assert metrics["recall"] == 1.0
        assert metrics["f1_score"] == 1.0
        assert "mcc" in metrics
