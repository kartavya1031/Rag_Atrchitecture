"""Confidence scorer — normalizes scores and triggers human fallback."""

from src.utils.config import get_thresholds


def normalize_confidence(raw_score: float, method: str) -> float:
    """Normalize a raw confidence score to [0.0, 1.0] based on method ceilings."""
    cfg = get_thresholds()["confidence"]
    ceiling = cfg.get(f"{method}_match", cfg.get(method, 1.0))
    score = min(raw_score, ceiling)
    return max(0.0, min(1.0, score))


def needs_human_review(confidence: float) -> bool:
    """Return True if confidence is below the human fallback threshold."""
    cfg = get_thresholds()["confidence"]
    return confidence < cfg["human_fallback"]
