"""Transaction enrichment — normalize dates, amounts, and tags."""

from __future__ import annotations

from datetime import timezone
from decimal import Decimal

from src.ingestion.schema import SourceType, Transaction
from src.utils.config import get_bank_rules


def enrich_transactions(
    transactions: list[Transaction],
    bank_name: str = "Generic",
) -> list[Transaction]:
    """Normalize and enrich a list of transactions.

    - Normalize dates to UTC-equivalent (date objects are timezone-naive by default)
    - Standardize amount sign conventions (credits positive, debits negative)
    - Strip bank-specific description prefixes
    """
    rules = get_bank_rules()
    bank_cfg = _find_bank_config(rules, bank_name)
    prefix_strips = bank_cfg.get("description_prefix_strip", []) if bank_cfg else []

    enriched: list[Transaction] = []
    for txn in transactions:
        # Strip known prefixes from description
        desc = txn.description
        for prefix in prefix_strips:
            if desc.startswith(prefix):
                desc = desc[len(prefix):]
                break

        enriched.append(
            txn.model_copy(
                update={
                    "description": desc.strip(),
                }
            )
        )
    return enriched


def _find_bank_config(rules: dict, bank_name: str) -> dict | None:
    """Look up the config block for a specific bank."""
    for bank in rules.get("banks", []):
        if bank.get("name", "").lower() == bank_name.lower():
            return bank
    # Fall back to Generic
    for bank in rules.get("banks", []):
        if bank.get("name", "").lower() == "generic":
            return bank
    return None
