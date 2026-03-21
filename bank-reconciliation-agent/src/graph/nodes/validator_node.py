"""Validator node — enforces Pydantic schemas on all LLM outputs."""

from typing import Any

from src.graph.state import ReconciliationState
from src.matching_engine.models import MatchResult
from src.utils.config import get_thresholds


def validator_node(state: ReconciliationState) -> dict[str, Any]:
    """Validate all LLM-proposed matches and exceptions.

    - Verify MatchResult schemas
    - Flag schema violations → route to human fallback
    - Build confidence_scores map
    - Build human_review_queue for low-confidence items
    """
    cfg = get_thresholds()
    fallback_threshold = cfg["confidence"]["human_fallback"]

    validation_results: dict[str, Any] = {"valid": [], "invalid": []}
    confidence_scores: dict[str, float] = dict(state.get("confidence_scores", {}))
    human_review_queue = list(state.get("human_review_queue", []))

    # Validate soft match candidates
    for match in state.get("soft_match_candidates", []):
        try:
            if isinstance(match, MatchResult):
                m = match
            else:
                m = MatchResult(**match)
            validation_results["valid"].append(m.model_dump())
            confidence_scores[f"{m.ledger_id}:{m.bank_id}"] = m.confidence
        except Exception as e:
            validation_results["invalid"].append({"data": str(match), "error": str(e)})

    # Route low-confidence exceptions to human review
    for exc in state.get("exceptions", []):
        txn_id = exc.get("transaction_id", "")
        conf = exc.get("confidence", 0.0)
        confidence_scores[txn_id] = conf
        if conf < fallback_threshold:
            human_review_queue.append(exc)

    return {
        "validation_results": validation_results,
        "confidence_scores": confidence_scores,
        "human_review_queue": human_review_queue,
    }
