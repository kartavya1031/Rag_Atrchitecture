"""Integration tests for FastAPI workflow endpoints."""

import io

import pytest
from fastapi.testclient import TestClient

from src.workflow.api import app, _runs


@pytest.fixture(autouse=True)
def _clear_stores():
    """Clear in-memory stores between tests."""
    _runs.clear()
    yield
    _runs.clear()


@pytest.fixture()
def client():
    return TestClient(app)


def _make_csv(rows: list[list[str]]) -> bytes:
    """Build a CSV file from header + data rows."""
    buf = io.StringIO()
    for row in rows:
        buf.write(",".join(row) + "\n")
    return buf.getvalue().encode()


BANK_CSV = _make_csv([
    ["id", "date", "amount", "description", "reference"],
    ["B1", "2024-01-01", "100.00", "Payment A", "REF1"],
    ["B2", "2024-01-02", "200.00", "Payment B", "REF2"],
    ["B3", "2024-01-03", "300.00", "Unmatched Bank", "REF3"],
])

LEDGER_CSV = _make_csv([
    ["id", "date", "amount", "description", "reference"],
    ["L1", "2024-01-01", "100.00", "Payment A", "REF1"],
    ["L2", "2024-01-02", "200.00", "Payment B", "REF2"],
    ["L4", "2024-01-04", "400.00", "Unmatched Ledger", "REF4"],
])


class TestReconcileEndpoint:
    def test_reconcile_returns_run_id(self, client):
        resp = client.post(
            "/reconcile",
            files={
                "file": ("bank.csv", BANK_CSV, "text/csv"),
                "ledger_file": ("ledger.csv", LEDGER_CSV, "text/csv"),
            },
            data={"bank_name": "Generic"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data

    def test_unsupported_format(self, client):
        resp = client.post(
            "/reconcile",
            files={"file": ("data.json", b"{}", "application/json")},
            data={"bank_name": "Generic"},
        )
        assert resp.status_code == 400

    def test_full_round_trip(self, client):
        # POST reconcile
        resp = client.post(
            "/reconcile",
            files={
                "file": ("bank.csv", BANK_CSV, "text/csv"),
                "ledger_file": ("ledger.csv", LEDGER_CSV, "text/csv"),
            },
            data={"bank_name": "Generic"},
        )
        run_id = resp.json()["run_id"]

        # GET status
        resp = client.get(f"/reconcile/{run_id}/status")
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"

        # GET report
        resp = client.get(f"/reconcile/{run_id}/report")
        assert resp.status_code == 200
        report = resp.json()
        assert report["matched_count"] == 2
        assert report["unmatched_ledger_count"] == 1
        assert report["unmatched_bank_count"] == 1


class TestStatusEndpoint:
    def test_not_found(self, client):
        resp = client.get("/reconcile/nonexistent/status")
        assert resp.status_code == 404

    def test_report_not_found(self, client):
        resp = client.get("/reconcile/nonexistent/report")
        assert resp.status_code == 404
