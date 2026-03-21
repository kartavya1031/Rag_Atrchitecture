"""Report generator — CSV, JSON, and plain-text audit exports."""

import csv
import datetime
import io
import json
from pathlib import Path
from typing import Any

from src.matching_engine.models import MatchResult


def build_report(
    *,
    run_id: str,
    bank_name: str,
    matches: list[MatchResult],
    unmatched_ledger: list[dict[str, Any]],
    unmatched_bank: list[dict[str, Any]],
    exceptions: list[dict[str, Any]] | None = None,
    audit_entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build the canonical reconciliation report dict."""
    matched_amount = sum(
        abs(float(m.confidence)) for m in matches
    )  # placeholder — real: sum actual matched amounts

    total_ledger_amount = sum(abs(float(u.get("amount", 0))) for u in unmatched_ledger)
    total_bank_amount = sum(abs(float(u.get("amount", 0))) for u in unmatched_bank)

    return {
        "run_id": run_id,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "bank": bank_name,
        "matched_count": len(matches),
        "unmatched_count": len(unmatched_ledger) + len(unmatched_bank),
        "match_rate_pct": round(
            len(matches) / max(len(matches) + len(unmatched_ledger) + len(unmatched_bank), 1) * 100,
            2,
        ),
        "total_matched_amount": matched_amount,
        "unreconciled_amount": total_ledger_amount + total_bank_amount,
        "exception_summary": exceptions or [],
        "audit_trail": audit_entries or [],
        "matches": [m.model_dump(mode="json") for m in matches],
        "unmatched_ledger": unmatched_ledger,
        "unmatched_bank": unmatched_bank,
    }


def export_json(report: dict[str, Any]) -> str:
    """Export full report as JSON string."""
    return json.dumps(report, indent=2, default=str)


def export_csv_unmatched(
    unmatched: list[dict[str, Any]],
    source_label: str = "ledger",
) -> str:
    """Export unmatched items as CSV (ERP-ready format)."""
    if not unmatched:
        return ""

    fieldnames = ["source", "id", "date", "amount", "description", "reference"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for item in unmatched:
        row = {**item, "source": source_label}
        writer.writerow(row)
    return buf.getvalue()


def export_audit_text(report: dict[str, Any]) -> str:
    """Export plain-text immutable audit document."""
    lines = [
        "=" * 60,
        "BANK RECONCILIATION AUDIT DOCUMENT",
        "=" * 60,
        f"Run ID:       {report['run_id']}",
        f"Generated:    {report['generated_at']}",
        f"Bank:         {report['bank']}",
        f"Match Rate:   {report['match_rate_pct']}%",
        f"Matched:      {report['matched_count']}",
        f"Unmatched:    {report['unmatched_count']}",
        "",
        "-" * 60,
        "MATCHED PAIRS",
        "-" * 60,
    ]

    for m in report.get("matches", []):
        lines.append(
            f"  {m['ledger_id']} <-> {m['bank_id']}  "
            f"confidence={m['confidence']}  method={m['method']}"
        )

    lines.append("")
    lines.append("-" * 60)
    lines.append("EXCEPTIONS")
    lines.append("-" * 60)

    for exc in report.get("exception_summary", []):
        lines.append(f"  [{exc.get('category', 'N/A')}] {exc.get('transaction_id', 'N/A')}: {exc.get('explanation', '')}")

    lines.append("")
    lines.append("-" * 60)
    lines.append("AUDIT TRAIL")
    lines.append("-" * 60)

    for entry in report.get("audit_trail", []):
        lines.append(
            f"  {entry.get('timestamp', '')} | {entry.get('transaction_id', '')} | "
            f"{entry.get('match_method', '')} | conf={entry.get('confidence', '')} | "
            f"{entry.get('decision', '')}"
        )

    lines.append("")
    lines.append("=" * 60)
    lines.append("END OF AUDIT DOCUMENT")
    lines.append("=" * 60)

    return "\n".join(lines)
