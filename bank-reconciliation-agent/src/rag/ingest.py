"""Seed data/reference/ documents into ChromaDB collections."""

import json
from pathlib import Path

from src.rag.collection_manager import get_chroma_client, initialize_all_collections

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "reference"


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ingest_sops(collections: dict) -> int:
    """Ingest SOP markdown files into policies_sops collection."""
    col = collections["policies_sops"]
    sop_files = sorted(_DATA_DIR.glob("sop_*.md"))
    ids, docs, metas = [], [], []
    for f in sop_files:
        doc_id = f.stem
        ids.append(doc_id)
        docs.append(_load_text(f))
        metas.append({"bank": "all", "type": "sop", "effective_date": "2024-01-01", "version": "1"})

    if ids:
        col.upsert(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def ingest_historical_cases(collections: dict) -> int:
    """Ingest historical reconciliation cases into prior_reconciliations."""
    col = collections["prior_reconciliations"]
    path = _DATA_DIR / "historical_cases.json"
    if not path.exists():
        return 0

    cases = json.loads(path.read_text(encoding="utf-8"))
    ids, docs, metas = [], [], []
    for case in cases:
        ids.append(case["case_id"])
        docs.append(case["description"] + " Resolution: " + case["resolution"])
        metas.append({
            "outcome": case["outcome"],
            "exception_type": case["exception_type"],
            "bank": case["bank"],
            "date_range": case["date_range"],
        })

    if ids:
        col.upsert(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def ingest_exception_catalog(collections: dict) -> int:
    """Ingest exception type catalog into exception_catalog collection."""
    col = collections["exception_catalog"]
    path = _DATA_DIR / "exception_catalog.json"
    if not path.exists():
        return 0

    exceptions = json.loads(path.read_text(encoding="utf-8"))
    ids, docs, metas = [], [], []
    for exc in exceptions:
        ids.append(exc["exception_id"])
        docs.append(exc["description"] + " Resolution: " + exc["resolution"])
        metas.append({
            "exception_id": exc["exception_id"],
            "category": exc["category"],
            "frequency": exc["frequency"],
            "resolution": exc["resolution"],
        })

    if ids:
        col.upsert(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def ingest_bank_rules(collections: dict) -> int:
    """Ingest bank rules from config into bank_rules collection."""
    from src.utils.config import get_bank_rules

    col = collections["bank_rules"]
    rules = get_bank_rules()
    ids, docs, metas = [], [], []
    for i, bank in enumerate(rules.get("banks", [])):
        doc_id = f"bank_rule_{bank['name'].lower()}"
        ids.append(doc_id)
        text = (
            f"Bank: {bank['name']}. "
            f"Timing offset: {bank.get('timing_offset_days', 0)} days. "
            f"Sign convention: {bank.get('amount_sign_convention', 'standard')}. "
            f"Prefix strips: {bank.get('description_prefix_strip', [])}."
        )
        docs.append(text)
        metas.append({
            "bank_name": bank["name"],
            "rule_type": "timing_and_format",
            "priority": str(i + 1),
        })

    if ids:
        col.upsert(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


def ingest_all() -> dict[str, int]:
    """Run all ingestion steps. Returns counts per collection."""
    client = get_chroma_client()
    collections = initialize_all_collections(client)

    return {
        "policies_sops": ingest_sops(collections),
        "prior_reconciliations": ingest_historical_cases(collections),
        "exception_catalog": ingest_exception_catalog(collections),
        "bank_rules": ingest_bank_rules(collections),
    }


if __name__ == "__main__":
    counts = ingest_all()
    for name, count in counts.items():
        print(f"  {name}: {count} documents")
    print("Ingestion complete.")
