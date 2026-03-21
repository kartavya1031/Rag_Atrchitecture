"""Tolerance-based matcher — fuzzy matching with composite scoring."""

from datetime import timedelta
from decimal import Decimal

from rapidfuzz import fuzz

from src.ingestion.schema import Transaction
from src.matching_engine.models import MatchResult
from src.utils.config import get_thresholds


def tolerance_match(
    ledger: list[Transaction],
    bank: list[Transaction],
) -> tuple[list[MatchResult], list[Transaction], list[Transaction]]:
    """Find matches using tolerance-based composite scoring.

    Composite score = amount_weight * amount_score + date_weight * date_score
                      + desc_weight * description_score

    Returns:
        (matched_pairs, unmatched_ledger, unmatched_bank)
    """
    cfg = get_thresholds()
    matching = cfg["matching"]
    confidence_cfg = cfg["confidence"]

    amount_tol = Decimal(str(matching["amount_tolerance"]))
    date_tol_days = matching["date_tolerance_days"]
    fuzzy_min = matching["description_fuzzy_score"]
    weights = matching["weights"]
    min_confidence = confidence_cfg["soft_match_min"]

    matched: list[MatchResult] = []
    used_bank_ids: set[str] = set()
    unmatched_ledger: list[Transaction] = []

    for ltxn in ledger:
        best_score = 0.0
        best_bank: Transaction | None = None

        for btxn in bank:
            if btxn.id in used_bank_ids:
                continue

            # Amount score: 1.0 if within tolerance, else scaled down
            amount_diff = abs(ltxn.amount - btxn.amount)
            if amount_diff <= amount_tol:
                amount_score = 1.0
            elif amount_diff <= amount_tol * 100:
                amount_score = max(0.0, 1.0 - float(amount_diff / (amount_tol * 100)))
            else:
                continue  # Too far apart

            # Date score: 1.0 if same day, scaled down within tolerance
            day_diff = abs((ltxn.date - btxn.date).days)
            if day_diff == 0:
                date_score = 1.0
            elif day_diff <= date_tol_days:
                date_score = 1.0 - (day_diff / (date_tol_days + 1))
            else:
                continue  # Too far apart

            # Description score: rapidfuzz token_set_ratio
            desc_score = fuzz.token_set_ratio(ltxn.description, btxn.description) / 100.0

            # Composite score
            composite = (
                weights["amount"] * amount_score
                + weights["date"] * date_score
                + weights["description"] * desc_score
            )

            if composite > best_score:
                best_score = composite
                best_bank = btxn

        if best_bank and best_score >= min_confidence:
            matched.append(
                MatchResult(
                    ledger_id=ltxn.id,
                    bank_id=best_bank.id,
                    confidence=round(best_score, 4),
                    method="tolerance",
                    details=f"composite_score={best_score:.4f}",
                )
            )
            used_bank_ids.add(best_bank.id)
        else:
            unmatched_ledger.append(ltxn)

    unmatched_bank = [b for b in bank if b.id not in used_bank_ids]
    return matched, unmatched_ledger, unmatched_bank
