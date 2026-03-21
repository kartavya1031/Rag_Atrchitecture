"""Reconciliation graph state shared across all LangGraph nodes."""

from typing import Any, TypedDict

from src.ingestion.schema import Transaction
from src.matching_engine.models import MatchResult


class ExceptionItem(TypedDict, total=False):
    transaction_id: str
    source: str  # "ledger" | "bank"
    category: str  # timing_diff | rounding | duplicate | missing | unknown | reversal | partial_payment
    confidence: float
    explanation: str
    rag_context: list[dict[str, Any]]
    soft_match_candidate: str | None  # bank/ledger id of proposed soft match
    soft_match_confidence: float


class ReconciliationState(TypedDict, total=False):
    # Inputs
    ledger_transactions: list[Transaction]
    bank_transactions: list[Transaction]
    bank_name: str

    # Deterministic matching outputs
    matches: list[MatchResult]
    unmatched_ledger: list[Transaction]
    unmatched_bank: list[Transaction]

    # LLM / RAG outputs
    exceptions: list[ExceptionItem]
    soft_match_candidates: list[MatchResult]
    explanations: dict[str, str]  # transaction_id → explanation

    # Validation
    validation_results: dict[str, Any]
    confidence_scores: dict[str, float]

    # Workflow
    human_review_queue: list[ExceptionItem]
    audit_log: list[dict[str, Any]]

    # Output
    final_report: dict[str, Any]
