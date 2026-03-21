"""Unit tests for data ingestion layer — parsers, validator, enricher."""

import csv
import json
import tempfile
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from src.ingestion.schema import SourceType, Transaction
from src.ingestion.parsers.csv_parser import parse_csv
from src.ingestion.parsers.excel_parser import parse_excel
from src.ingestion.parsers.api_parser import parse_api_response
from src.ingestion.validators.validator import validate_transactions
from src.ingestion.enricher import enrich_transactions


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

def _write_csv(path: Path, rows: list[dict]):
    headers = rows[0].keys()
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def _write_excel(path: Path, rows: list[dict]):
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row[h] for h in headers])
    wb.save(path)
    wb.close()


SAMPLE_ROWS = [
    {"id": "TXN-001", "date": "2026-03-01", "posting_date": "2026-03-01", "amount": "1500.00", "description": "ACH CREDIT PayrollCo", "reference": "REF-001"},
    {"id": "TXN-002", "date": "2026-03-02", "posting_date": "2026-03-02", "amount": "-250.50", "description": "WIRE OUT Vendor", "reference": "REF-002"},
    {"id": "TXN-003", "date": "2026-03-03", "posting_date": "", "amount": "89.99", "description": "CHECK DEP", "reference": "REF-003"},
]


# ---------------------------------------------------------------------------
# CSV parser tests
# ---------------------------------------------------------------------------

class TestCSVParser:
    def test_parse_csv_returns_transaction_list(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        _write_csv(csv_file, SAMPLE_ROWS)
        result = parse_csv(str(csv_file))
        assert isinstance(result, list)
        assert all(isinstance(t, Transaction) for t in result)
        assert len(result) == 3

    def test_parse_csv_amounts(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        _write_csv(csv_file, SAMPLE_ROWS)
        result = parse_csv(str(csv_file))
        assert result[0].amount == Decimal("1500.00")
        assert result[1].amount == Decimal("-250.50")

    def test_parse_csv_source_type(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        _write_csv(csv_file, SAMPLE_ROWS)
        result = parse_csv(str(csv_file))
        assert all(t.source_type == SourceType.CSV for t in result)

    def test_parse_csv_custom_column_map(self, tmp_path):
        csv_file = tmp_path / "custom.csv"
        rows = [{"txn_id": "C1", "txn_date": "2026-01-01", "amt": "100", "desc": "Test", "ref": "R1"}]
        headers = rows[0].keys()
        with open(csv_file, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=headers)
            w.writeheader()
            w.writerows(rows)

        result = parse_csv(
            str(csv_file),
            column_map={"id": "txn_id", "date": "txn_date", "amount": "amt", "description": "desc", "reference": "ref"},
        )
        assert len(result) == 1
        assert result[0].id == "C1"
        assert result[0].amount == Decimal("100")


# ---------------------------------------------------------------------------
# Excel parser tests
# ---------------------------------------------------------------------------

class TestExcelParser:
    def test_parse_excel_returns_transaction_list(self, tmp_path):
        xls_file = tmp_path / "test.xlsx"
        _write_excel(xls_file, SAMPLE_ROWS)
        result = parse_excel(str(xls_file))
        assert isinstance(result, list)
        assert all(isinstance(t, Transaction) for t in result)
        assert len(result) == 3

    def test_parse_excel_amounts(self, tmp_path):
        xls_file = tmp_path / "test.xlsx"
        _write_excel(xls_file, SAMPLE_ROWS)
        result = parse_excel(str(xls_file))
        assert result[0].amount == Decimal("1500.00")
        assert result[1].amount == Decimal("-250.50")

    def test_parse_excel_source_type(self, tmp_path):
        xls_file = tmp_path / "test.xlsx"
        _write_excel(xls_file, SAMPLE_ROWS)
        result = parse_excel(str(xls_file))
        assert all(t.source_type == SourceType.EXCEL for t in result)


# ---------------------------------------------------------------------------
# API parser tests
# ---------------------------------------------------------------------------

class TestAPIParser:
    def test_parse_api_response_basic(self):
        data = [
            {"id": "A1", "date": "2026-03-01", "amount": "500.00", "description": "Transfer", "reference": "R-A1"},
            {"id": "A2", "date": "2026-03-02", "amount": "-100.00", "description": "Fee", "reference": "R-A2"},
        ]
        result = parse_api_response(data)
        assert len(result) == 2
        assert result[0].source_type == SourceType.API
        assert result[0].amount == Decimal("500.00")


# ---------------------------------------------------------------------------
# Validator tests
# ---------------------------------------------------------------------------

class TestValidator:
    def test_valid_transactions_pass(self):
        txns = [
            Transaction(id="V1", date=date(2026, 3, 1), amount=Decimal("100"), source_type=SourceType.CSV),
            Transaction(id="V2", date=date(2026, 3, 2), amount=Decimal("-50"), source_type=SourceType.CSV),
        ]
        result = validate_transactions(txns)
        assert result.is_valid
        assert len(result.valid) == 2

    def test_zero_amount_rejected(self):
        txns = [
            Transaction(id="Z1", date=date(2026, 3, 1), amount=Decimal("0"), source_type=SourceType.CSV),
        ]
        result = validate_transactions(txns)
        assert not result.is_valid
        assert len(result.rejected) == 1

    def test_future_date_rejected(self):
        far_future = date.today() + timedelta(days=30)
        txns = [
            Transaction(id="F1", date=far_future, amount=Decimal("100"), source_type=SourceType.CSV),
        ]
        result = validate_transactions(txns)
        assert not result.is_valid

    def test_near_future_date_accepted(self):
        near_future = date.today() + timedelta(days=3)
        txns = [
            Transaction(id="NF1", date=near_future, amount=Decimal("100"), source_type=SourceType.CSV),
        ]
        result = validate_transactions(txns)
        assert result.is_valid

    def test_duplicate_id_rejected(self):
        txns = [
            Transaction(id="D1", date=date(2026, 3, 1), amount=Decimal("100"), source_type=SourceType.CSV),
            Transaction(id="D1", date=date(2026, 3, 2), amount=Decimal("200"), source_type=SourceType.CSV),
        ]
        result = validate_transactions(txns)
        assert not result.is_valid
        assert len(result.rejected) == 1  # second one is the duplicate
        assert len(result.valid) == 1


# ---------------------------------------------------------------------------
# Enricher tests
# ---------------------------------------------------------------------------

class TestEnricher:
    def test_strips_bank_prefix(self):
        txns = [
            Transaction(
                id="E1", date=date(2026, 3, 1), amount=Decimal("100"),
                description="ACH CREDIT Payroll", source_type=SourceType.CSV,
            ),
        ]
        enriched = enrich_transactions(txns, bank_name="BankOfAmerica")
        assert enriched[0].description == "Payroll"

    def test_generic_bank_no_strip(self):
        txns = [
            Transaction(
                id="E2", date=date(2026, 3, 1), amount=Decimal("100"),
                description="Regular payment", source_type=SourceType.CSV,
            ),
        ]
        enriched = enrich_transactions(txns, bank_name="Generic")
        assert enriched[0].description == "Regular payment"

    def test_chase_prefix_strip(self):
        txns = [
            Transaction(
                id="E3", date=date(2026, 3, 1), amount=Decimal("500"),
                description="INCOMING TRANSFER - Wire from Client", source_type=SourceType.CSV,
            ),
        ]
        enriched = enrich_transactions(txns, bank_name="Chase")
        assert enriched[0].description == "Wire from Client"
