"""Conditional routing logic for the reconciliation graph."""

from src.graph.state import ReconciliationState
from src.utils.config import get_thresholds


def after_deterministic(state: ReconciliationState) -> str:
    """Route after deterministic matching.

    If there are unmatched transactions, go to exception_classifier.
    Otherwise, skip to output.
    """
    unmatched_l = state.get("unmatched_ledger", [])
    unmatched_b = state.get("unmatched_bank", [])
    if unmatched_l or unmatched_b:
        return "exception_classifier"
    return "output"


def after_classification(state: ReconciliationState) -> str:
    """Route after exception classification.

    Always proceed to parallel soft_match + edge_case reasoning.
    """
    return "soft_match_and_reason"


def after_validation(state: ReconciliationState) -> str:
    """Route after validation — always proceed to output."""
    return "output"
