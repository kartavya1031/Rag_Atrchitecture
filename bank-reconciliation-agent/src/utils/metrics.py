"""Metrics computation for reconciliation accuracy measurement."""

import math
from typing import Any


def _confusion_matrix(
    predicted_matches: list[dict[str, str]],
    ground_truth: list[dict[str, Any]],
) -> dict[str, int]:
    """Compute TP, FP, FN, TN from predicted vs. ground-truth labels.

    predicted_matches: list of {"ledger_id": ..., "bank_id": ...}
    ground_truth: list of {"ledger_id": ..., "bank_id": ..., "should_match": bool}
    """
    gt_positive = {
        (g["ledger_id"], g["bank_id"])
        for g in ground_truth
        if g.get("should_match") and g.get("ledger_id") and g.get("bank_id")
    }
    gt_negative_ids = {
        g["ledger_id"] or g.get("bank_id", "")
        for g in ground_truth
        if not g.get("should_match")
    }

    pred_set = {(p["ledger_id"], p["bank_id"]) for p in predicted_matches}

    tp = len(pred_set & gt_positive)
    fp = len(pred_set - gt_positive)
    fn = len(gt_positive - pred_set)
    tn = len(gt_negative_ids)  # approximation: unmatched items that should be unmatched

    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def precision(cm: dict[str, int]) -> float:
    denom = cm["tp"] + cm["fp"]
    return cm["tp"] / denom if denom > 0 else 0.0


def recall(cm: dict[str, int]) -> float:
    denom = cm["tp"] + cm["fn"]
    return cm["tp"] / denom if denom > 0 else 0.0


def f1_score(cm: dict[str, int]) -> float:
    p, r = precision(cm), recall(cm)
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def false_positive_rate(cm: dict[str, int]) -> float:
    denom = cm["fp"] + cm["tn"]
    return cm["fp"] / denom if denom > 0 else 0.0


def mcc(cm: dict[str, int]) -> float:
    """Matthews Correlation Coefficient."""
    tp, fp, fn, tn = cm["tp"], cm["fp"], cm["fn"], cm["tn"]
    num = tp * tn - fp * fn
    denom = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    return num / denom if denom > 0 else 0.0


def exception_detection_rate(
    detected_exceptions: list[str],
    total_exceptions: list[str],
) -> float:
    """Rate of detected exceptions vs. total known exceptions."""
    if not total_exceptions:
        return 1.0
    found = len(set(detected_exceptions) & set(total_exceptions))
    return found / len(total_exceptions)


def human_fallback_rate(
    human_review_count: int,
    total_transactions: int,
) -> float:
    if total_transactions == 0:
        return 0.0
    return human_review_count / total_transactions


def amount_variance_pct(
    matched_ledger_total: float,
    matched_bank_total: float,
    ledger_total: float,
) -> float:
    """Amount variance as percentage of ledger total."""
    if ledger_total == 0:
        return 0.0
    return abs(matched_ledger_total - matched_bank_total) / abs(ledger_total) * 100


def confidence_ece(
    predictions: list[tuple[float, bool]],
    n_bins: int = 10,
) -> float:
    """Expected Calibration Error for confidence scores.

    predictions: list of (confidence, was_correct) tuples.
    """
    if not predictions:
        return 0.0

    bins: list[list[tuple[float, bool]]] = [[] for _ in range(n_bins)]
    for conf, correct in predictions:
        idx = min(int(conf * n_bins), n_bins - 1)
        bins[idx].append((conf, correct))

    ece = 0.0
    total = len(predictions)
    for bin_items in bins:
        if not bin_items:
            continue
        avg_conf = sum(c for c, _ in bin_items) / len(bin_items)
        avg_acc = sum(1 for _, correct in bin_items if correct) / len(bin_items)
        ece += len(bin_items) / total * abs(avg_conf - avg_acc)

    return ece


def evaluate_run(
    predicted_matches: list[dict[str, str]],
    ground_truth: list[dict[str, Any]],
    detected_exceptions: list[str] | None = None,
    total_exceptions: list[str] | None = None,
    human_review_count: int = 0,
    total_transactions: int = 0,
    matched_ledger_total: float = 0.0,
    matched_bank_total: float = 0.0,
    ledger_total: float = 0.0,
    confidence_predictions: list[tuple[float, bool]] | None = None,
) -> dict[str, float]:
    """Evaluate a full reconciliation run and return all metrics."""
    cm = _confusion_matrix(predicted_matches, ground_truth)

    report = {
        "precision": round(precision(cm), 4),
        "recall": round(recall(cm), 4),
        "f1_score": round(f1_score(cm), 4),
        "false_positive_rate": round(false_positive_rate(cm), 4),
        "mcc": round(mcc(cm), 4),
        "exception_detection_rate": round(
            exception_detection_rate(detected_exceptions or [], total_exceptions or []),
            4,
        ),
        "human_fallback_rate": round(
            human_fallback_rate(human_review_count, total_transactions),
            4,
        ),
        "amount_variance_pct": round(
            amount_variance_pct(matched_ledger_total, matched_bank_total, ledger_total),
            6,
        ),
        "confidence_ece": round(
            confidence_ece(confidence_predictions or []),
            4,
        ),
        "tp": cm["tp"],
        "fp": cm["fp"],
        "fn": cm["fn"],
        "tn": cm["tn"],
    }
    return report
