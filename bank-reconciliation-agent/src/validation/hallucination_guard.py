"""Hallucination guard — verifies LLM outputs contain only real data."""

from decimal import Decimal, InvalidOperation
from typing import Any


def check_amounts(
    llm_output: dict[str, Any],
    valid_amounts: set[Decimal],
    amount_keys: tuple[str, ...] = ("amount", "matched_amount", "ledger_amount", "bank_amount"),
) -> list[str]:
    """Verify every amount in an LLM output exists in the source data.

    Returns a list of violation descriptions (empty if clean).
    """
    violations: list[str] = []
    _walk_for_amounts(llm_output, valid_amounts, amount_keys, violations, path="")
    return violations


def _walk_for_amounts(
    obj: Any,
    valid_amounts: set[Decimal],
    keys: tuple[str, ...],
    violations: list[str],
    path: str,
) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            current_path = f"{path}.{k}" if path else k
            if k in keys:
                try:
                    val = Decimal(str(v))
                except (InvalidOperation, TypeError, ValueError):
                    violations.append(f"Non-numeric amount at {current_path}: {v!r}")
                    continue
                if val not in valid_amounts and -val not in valid_amounts:
                    violations.append(
                        f"Hallucinated amount at {current_path}: {val} not in source data"
                    )
            else:
                _walk_for_amounts(v, valid_amounts, keys, violations, current_path)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _walk_for_amounts(item, valid_amounts, keys, violations, f"{path}[{i}]")


def check_transaction_ids(
    llm_output: dict[str, Any],
    valid_ids: set[str],
    id_keys: tuple[str, ...] = ("transaction_id", "ledger_id", "bank_id"),
) -> list[str]:
    """Verify every transaction ID in an LLM output exists in the source data.

    Returns a list of violation descriptions (empty if clean).
    """
    violations: list[str] = []
    _walk_for_ids(llm_output, valid_ids, id_keys, violations, path="")
    return violations


def _walk_for_ids(
    obj: Any,
    valid_ids: set[str],
    keys: tuple[str, ...],
    violations: list[str],
    path: str,
) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            current_path = f"{path}.{k}" if path else k
            if k in keys:
                if isinstance(v, str) and v not in valid_ids:
                    violations.append(
                        f"Hallucinated ID at {current_path}: {v!r} not in source data"
                    )
            else:
                _walk_for_ids(v, valid_ids, keys, violations, current_path)
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            _walk_for_ids(item, valid_ids, keys, violations, f"{path}[{i}]")


def guard(
    llm_output: dict[str, Any],
    valid_amounts: set[Decimal],
    valid_ids: set[str],
) -> tuple[bool, list[str]]:
    """Run all hallucination checks.

    Returns (is_clean, list_of_violations).
    """
    violations = check_amounts(llm_output, valid_amounts) + check_transaction_ids(llm_output, valid_ids)
    return len(violations) == 0, violations
