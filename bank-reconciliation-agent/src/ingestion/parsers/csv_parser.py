"""CSV transaction parser with configurable column mapping."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pandas as pd

from src.ingestion.schema import SourceType, Transaction

# Default column mapping — can be overridden per bank
DEFAULT_COLUMN_MAP = {
    "id": "id",
    "date": "date",
    "posting_date": "posting_date",
    "amount": "amount",
    "description": "description",
    "reference": "reference",
    
}


def parse_csv(
    file_path: str,
    column_map: dict[str, str] | None = None,
) -> list[Transaction]:
    """Parse a CSV file into Transaction objects.

    Args:
        file_path: Path to the CSV file.
        column_map: Mapping from Transaction field names to CSV column names.
    """
    cmap = {**DEFAULT_COLUMN_MAP, **(column_map or {})}
    df = pd.read_csv(file_path, dtype=str)
    df.columns = df.columns.str.strip()

    transactions: list[Transaction] = []
    for idx, row in df.iterrows():
        raw_date = row.get(cmap["date"], "")
        txn_date = pd.to_datetime(raw_date, dayfirst=False, errors="coerce")
        if pd.isna(txn_date):
            continue

        posting_raw = row.get(cmap.get("posting_date", ""), "")
        posting_date = None
        if posting_raw and str(posting_raw).strip():
            pd_posting = pd.to_datetime(posting_raw, errors="coerce")
            if not pd.isna(pd_posting):
                posting_date = pd_posting.date()

        raw_amount = row.get(cmap["amount"], "0")
        amount = Decimal(str(raw_amount).replace(",", "").strip())

        txn_id = row.get(cmap["id"], "") or f"CSV-{idx}"
        description = row.get(cmap["description"], "") or ""
        reference = row.get(cmap["reference"], "") or ""

        transactions.append(
            Transaction(
                id=str(txn_id).strip(),
                date=txn_date.date(),
                posting_date=posting_date,
                amount=amount,
                description=str(description).strip(),
                reference=str(reference).strip(),
                source_type=SourceType.CSV,
                raw_metadata={"row_index": idx},
            )
        )
    return transactions
