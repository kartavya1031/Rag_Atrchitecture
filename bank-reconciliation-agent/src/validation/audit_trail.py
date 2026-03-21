"""Append-only audit trail for all reconciliation decisions."""

import datetime
import json
from pathlib import Path
from typing import Any


class AuditTrail:
    """Immutable, append-only audit log backed by a JSONL file."""

    def __init__(self, log_path: str | Path = "data/audit_trail.jsonl"):
        self._path = Path(log_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def record(
        self,
        *,
        run_id: str,
        transaction_id: str,
        match_method: str,
        confidence: float,
        decision: str,
        explanation_ref: str = "",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a single audit entry. Returns the entry dict."""
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "run_id": run_id,
            "transaction_id": transaction_id,
            "match_method": match_method,
            "confidence": confidence,
            "decision": decision,
            "explanation_ref": explanation_ref,
        }
        if extra:
            entry["extra"] = extra

        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

        return entry

    def read_all(self) -> list[dict[str, Any]]:
        """Read all audit entries."""
        if not self._path.exists():
            return []
        entries = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        return entries
