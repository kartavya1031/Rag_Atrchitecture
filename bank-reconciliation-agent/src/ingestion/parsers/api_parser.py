"""Stub parser for core banking JSON API responses."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from src.ingestion.schema import SourceType, Transaction


def parse_api_response(data: list[dict[str, Any]]) -> list[Transaction]:
    """Parse a list of JSON dicts (from a banking API) into Transactions.

    Expected dict keys: id, date, posting_date, amount, description, reference.
    """
    transactions: list[Transaction] = []
    for idx, record in enumerate(data):
        raw_date = record.get("date", "")
        if isinstance(raw_date, date):
            txn_date = raw_date
        else:
            txn_date = date.fromisoformat(str(raw_date))

        posting_date = None
        if record.get("posting_date"):
            pd_raw = record["posting_date"]
            posting_date = pd_raw if isinstance(pd_raw, date) else date.fromisoformat(str(pd_raw))

        transactions.append(
            Transaction(
                id=str(record.get("id", f"API-{idx}")),
                date=txn_date,
                posting_date=posting_date,
                amount=Decimal(str(record.get("amount", 0))),
                description=str(record.get("description", "")),
                reference=str(record.get("reference", "")),
                source_type=SourceType.API,
                raw_metadata={k: v for k, v in record.items() if k not in ("id", "date", "posting_date", "amount", "description", "reference")},
            )
        )
    return transactions
