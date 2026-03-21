"""BAI2 bank statement parser."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from bai2 import bai2_parser

from src.ingestion.schema import SourceType, Transaction


def parse_bai2(file_path: str) -> list[Transaction]:
    """Parse a BAI2 file and return a list of Transaction objects."""
    with open(file_path, "r") as f:
        raw = f.read()

    parsed = bai2_parser.parse(raw)
    transactions: list[Transaction] = []

    for group in getattr(parsed, "children", []):
        for account in getattr(group, "children", []):
            for detail in getattr(account, "children", []):
                row = detail.rows[0] if hasattr(detail, "rows") and detail.rows else detail
                type_code = getattr(row, "type_code", None)
                amount_raw = getattr(row, "amount", 0)
                # BAI2 amounts are in cents
                amount = Decimal(str(amount_raw)) / Decimal("100")

                # Determine sign from type code if available
                # Type codes 1xx–3xx are credits, 4xx–5xx are debits
                if type_code and str(type_code).startswith(("4", "5")):
                    amount = -abs(amount)
                elif type_code and str(type_code).startswith(("1", "2", "3")):
                    amount = abs(amount)

                ref = getattr(row, "bank_reference", "") or getattr(row, "customer_reference", "") or ""
                text = getattr(row, "text", "") or ""

                txn_date_raw = getattr(row, "value_date", None)
                if txn_date_raw and isinstance(txn_date_raw, str):
                    txn_date = date.fromisoformat(txn_date_raw)
                elif isinstance(txn_date_raw, date):
                    txn_date = txn_date_raw
                else:
                    txn_date = date.today()

                txn_id = f"BAI2-{ref or id(row)}-{amount}"

                transactions.append(
                    Transaction(
                        id=txn_id,
                        date=txn_date,
                        posting_date=None,
                        amount=amount,
                        description=text,
                        reference=str(ref),
                        source_type=SourceType.BAI2,
                        raw_metadata={"type_code": str(type_code) if type_code else None},
                    )
                )
    return transactions
