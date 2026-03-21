"""Exact matcher — matches on amount + date + reference."""

from src.ingestion.schema import Transaction
from src.matching_engine.models import MatchResult


def exact_match(
    ledger: list[Transaction],
    bank: list[Transaction],
) -> tuple[list[MatchResult], list[Transaction], list[Transaction]]:
    """Find exact matches: amount == amount AND date == date AND reference == reference.

    Returns:
        (matched_pairs, unmatched_ledger, unmatched_bank)
    """
    matched: list[MatchResult] = []
    used_bank_ids: set[str] = set()
    unmatched_ledger: list[Transaction] = []

    # Index bank transactions by (amount, date, reference) for O(n) lookup
    bank_index: dict[tuple, list[Transaction]] = {}
    for b in bank:
        key = (b.amount, b.date, b.reference)
        bank_index.setdefault(key, []).append(b)

    for ltxn in ledger:
        key = (ltxn.amount, ltxn.date, ltxn.reference)
        candidates = bank_index.get(key, [])
        found = False
        for btxn in candidates:
            if btxn.id not in used_bank_ids:
                matched.append(
                    MatchResult(
                        ledger_id=ltxn.id,
                        bank_id=btxn.id,
                        confidence=1.0,
                        method="exact",
                    )
                )
                used_bank_ids.add(btxn.id)
                found = True
                break
        if not found:
            unmatched_ledger.append(ltxn)

    unmatched_bank = [b for b in bank if b.id not in used_bank_ids]
    return matched, unmatched_ledger, unmatched_bank
