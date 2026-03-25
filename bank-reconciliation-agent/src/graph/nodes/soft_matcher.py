"""Soft matcher node — rapidfuzz-based fuzzy matching with composite scoring."""

from datetime import date as d_type
from typing import Any

from rapidfuzz import fuzz

from src.graph.state import ReconciliationState
from src.matching_engine.models import MatchResult
from src.utils.config import get_thresholds


def soft_matcher(state: ReconciliationState) -> dict[str, Any]:
    """Attempt soft matches between remaining unmatched transactions."""
    cfg = get_thresholds()
    min_confidence = cfg["confidence"]["soft_match_min"]
    weights = cfg["matching"]["weights"]
    date_tol_days = cfg["matching"]["date_tolerance_days"]

    unmatched_ledger = list(state.get("unmatched_ledger", []))
    unmatched_bank = list(state.get("unmatched_bank", []))
    soft_matches: list[MatchResult] = list(state.get("soft_match_candidates", []))

    used_bank_ids: set[str] = set()

    for ledger_txn in unmatched_ledger:
        l_dict = ledger_txn.model_dump(mode="json") if hasattr(ledger_txn, "model_dump") else dict(ledger_txn)
        best_score = 0.0
        best_bank_id = None

        for bank_txn in unmatched_bank:
            b_dict = bank_txn.model_dump(mode="json") if hasattr(bank_txn, "model_dump") else dict(bank_txn)
            if b_dict["id"] in used_bank_ids:
                continue

            # Amount similarity
            l_amt = abs(float(l_dict["amount"]))
            b_amt = abs(float(b_dict["amount"]))
            max_amt = max(l_amt, b_amt, 0.01)
            amt_score = max(0.0, 1.0 - abs(l_amt - b_amt) / max_amt)

            # Description similarity
            desc_score = fuzz.token_set_ratio(
                l_dict.get("description", ""),
                b_dict.get("description", ""),
            ) / 100.0

            # Date similarity — use config tolerance window
            l_date = l_dict.get("date")
            b_date = b_dict.get("date")
            if isinstance(l_date, str):
                l_date = d_type.fromisoformat(l_date)
            if isinstance(b_date, str):
                b_date = d_type.fromisoformat(b_date)
            if l_date and b_date:
                day_diff = abs((l_date - b_date).days)
                if day_diff == 0:
                    date_score = 1.0
                elif day_diff <= date_tol_days:
                    date_score = 1.0 - (day_diff / (date_tol_days + 1))
                else:
                    date_score = max(0.0, 1.0 - day_diff / (date_tol_days * 5))
            else:
                date_score = 0.0

            composite = (
                weights["amount"] * amt_score
                + weights["date"] * date_score
                + weights["description"] * desc_score
            )

            if composite > best_score:
                best_score = composite
                best_bank_id = b_dict["id"]

        if best_bank_id and best_score >= min_confidence:
            soft_matches.append(MatchResult(
                ledger_id=l_dict["id"],
                bank_id=best_bank_id,
                confidence=round(best_score, 4),
                method="soft",
                details="Soft match via rapidfuzz + composite scoring",
            ))
            used_bank_ids.add(best_bank_id)

    return {"soft_match_candidates": soft_matches}
