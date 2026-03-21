"""Ledger ↔ Bank aligner — runs matchers in priority order."""

from src.ingestion.schema import Transaction
from src.matching_engine.algorithms.exact_matcher import exact_match
from src.matching_engine.algorithms.rule_matcher import rule_match
from src.matching_engine.algorithms.tolerance_matcher import tolerance_match
from src.matching_engine.models import MatchResult


def align(
    ledger: list[Transaction],
    bank: list[Transaction],
    bank_name: str = "Generic",
) -> dict:
    """Run deterministic matchers in priority order: exact → rule → tolerance.

    Returns dict with:
        matched_pairs: list[MatchResult]
        unmatched_ledger: list[Transaction]
        unmatched_bank: list[Transaction]
    """
    all_matches: list[MatchResult] = []

    # 1. Exact matching
    exact_matches, remaining_ledger, remaining_bank = exact_match(ledger, bank)
    all_matches.extend(exact_matches)

    # 2. Rule-based matching on remaining
    if remaining_ledger and remaining_bank:
        rule_matches, remaining_ledger, remaining_bank = rule_match(
            remaining_ledger, remaining_bank, bank_name=bank_name
        )
        all_matches.extend(rule_matches)

    # 3. Tolerance-based matching on remaining
    if remaining_ledger and remaining_bank:
        tol_matches, remaining_ledger, remaining_bank = tolerance_match(
            remaining_ledger, remaining_bank
        )
        all_matches.extend(tol_matches)

    return {
        "matched_pairs": all_matches,
        "unmatched_ledger": remaining_ledger,
        "unmatched_bank": remaining_bank,
    }
