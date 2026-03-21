"""Metrics runner — runs reconciliation on fixtures and evaluates accuracy.

Usage:
    python -m src.utils.metrics_runner
"""

import datetime
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from src.ingestion.schema import SourceType, Transaction
from src.matching_engine.ledger_bank_aligner import align
from src.utils.metrics import evaluate_run

FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures"
METRICS_LOG = Path(__file__).resolve().parent.parent.parent / "data" / "metrics.jsonl"

# CI gate thresholds from PLAN.md
CI_GATES = {
    "precision": 0.95,
    "recall": 0.98,
    "f1_score": 0.96,
}


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


def run_on_fixture(fixture_name: str) -> dict[str, Any]:
    """Run the aligner on a fixture and compute metrics."""
    data = _load_fixture(fixture_name)
    golden = _load_fixture("golden_answers.json")

    ledger = [_dict_to_txn(d) for d in data["ledger"] if d.get("id")]
    bank = [_dict_to_txn(d) for d in data["bank"] if d.get("id")]

    result = align(ledger, bank, bank_name="Generic")

    predicted = [
        {"ledger_id": m.ledger_id, "bank_id": m.bank_id}
        for m in result["matched_pairs"]
    ]

    gt_key = fixture_name.replace("_dataset.json", "")
    ground_truth = golden.get(gt_key, data.get("labels", []))

    total_exceptions = [
        g["ledger_id"] or g.get("bank_id", "")
        for g in ground_truth
        if not g.get("should_match")
    ]
    detected_exceptions = [
        t.id for t in result["unmatched_ledger"]
    ] + [
        t.id for t in result["unmatched_bank"]
    ]

    metrics = evaluate_run(
        predicted_matches=predicted,
        ground_truth=ground_truth,
        detected_exceptions=detected_exceptions,
        total_exceptions=total_exceptions,
        human_review_count=0,
        total_transactions=len(ledger) + len(bank),
    )
    metrics["fixture"] = fixture_name
    metrics["matched_count"] = len(result["matched_pairs"])
    metrics["unmatched_ledger"] = len(result["unmatched_ledger"])
    metrics["unmatched_bank"] = len(result["unmatched_bank"])

    return metrics


def check_ci_gates(metrics: dict[str, float]) -> list[str]:
    """Check metrics against CI gate thresholds. Returns list of failures."""
    failures = []
    for metric, threshold in CI_GATES.items():
        actual = metrics.get(metric, 0.0)
        if actual < threshold:
            failures.append(f"{metric}: {actual:.4f} < {threshold:.4f}")
    return failures


def run_all():
    """Run metrics on all fixtures and print results."""
    METRICS_LOG.parent.mkdir(parents=True, exist_ok=True)

    fixtures = ["smoke_dataset.json"]
    all_pass = True

    for fixture_name in fixtures:
        print(f"\n{'='*60}")
        print(f"Running metrics on: {fixture_name}")
        print("=" * 60)

        metrics = run_on_fixture(fixture_name)

        # Log to metrics.jsonl
        with open(METRICS_LOG, "a") as f:
            f.write(json.dumps(metrics, default=str) + "\n")

        # Print metrics
        for key, val in metrics.items():
            if isinstance(val, float):
                print(f"  {key:30s}: {val:.4f}")
            else:
                print(f"  {key:30s}: {val}")

        # Check CI gates
        failures = check_ci_gates(metrics)
        if failures:
            print("\n  CI GATE FAILURES:")
            for f in failures:
                print(f"    FAIL: {f}")
            all_pass = False
        else:
            print("\n  All CI gates PASSED")

    return all_pass


if __name__ == "__main__":
    success = run_all()
    if not success:
        print("\nSome CI gates failed.")
    else:
        print("\nAll metrics passed.")
