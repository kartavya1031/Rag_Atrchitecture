"""Excel (.xlsx) transaction parser with multi-sheet support."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import openpyxl

from src.ingestion.schema import SourceType, Transaction

DEFAULT_COLUMN_MAP = {
    "id": "id",
    "date": "date",
    "posting_date": "posting_date",
    "amount": "amount",
    "description": "description",
    "reference": "reference",
}


def parse_excel(
    file_path: str,
    sheet_name: str | None = None,
    column_map: dict[str, str] | None = None,
) -> list[Transaction]:
    """Parse an Excel file into Transaction objects.

    Args:
        file_path: Path to the .xlsx file.
        sheet_name: Specific sheet to parse; None means first sheet.
        column_map: Mapping from Transaction field names to Excel column names.
    """
    cmap = {**DEFAULT_COLUMN_MAP, **(column_map or {})}
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb[sheet_name] if sheet_name else wb.active

    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        wb.close()
        return []

    headers = [str(h).strip().lower() if h else "" for h in rows[0]]
    cmap_lower = {k: v.lower() for k, v in cmap.items()}

    def col_idx(field: str) -> int | None:
        col_name = cmap_lower.get(field, field)
        try:
            return headers.index(col_name)
        except ValueError:
            return None

    transactions: list[Transaction] = []
    for row_num, row in enumerate(rows[1:], start=1):
        date_idx = col_idx("date")
        if date_idx is None:
            continue
        raw_date = row[date_idx]
        if raw_date is None:
            continue
        if isinstance(raw_date, date):
            txn_date = raw_date
        else:
            from datetime import datetime
            try:
                txn_date = datetime.strptime(str(raw_date).strip(), "%Y-%m-%d").date()
            except ValueError:
                continue

        amount_idx = col_idx("amount")
        raw_amount = row[amount_idx] if amount_idx is not None else 0
        amount = Decimal(str(raw_amount).replace(",", "").strip())

        id_idx = col_idx("id")
        txn_id = str(row[id_idx]).strip() if id_idx is not None and row[id_idx] else f"XLS-{row_num}"

        desc_idx = col_idx("description")
        description = str(row[desc_idx]).strip() if desc_idx is not None and row[desc_idx] else ""

        ref_idx = col_idx("reference")
        reference = str(row[ref_idx]).strip() if ref_idx is not None and row[ref_idx] else ""

        posting_idx = col_idx("posting_date")
        posting_date = None
        if posting_idx is not None and row[posting_idx]:
            pd_raw = row[posting_idx]
            if isinstance(pd_raw, date):
                posting_date = pd_raw
            else:
                try:
                    from datetime import datetime
                    posting_date = datetime.strptime(str(pd_raw).strip(), "%Y-%m-%d").date()
                except ValueError:
                    pass

        transactions.append(
            Transaction(
                id=txn_id,
                date=txn_date if isinstance(txn_date, date) else txn_date,
                posting_date=posting_date,
                amount=amount,
                description=description,
                reference=reference,
                source_type=SourceType.EXCEL,
                raw_metadata={"sheet": ws.title, "row": row_num + 1},
            )
        )

    wb.close()
    return transactions
