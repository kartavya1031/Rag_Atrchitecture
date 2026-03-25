"""FastAPI workflow engine — reconciliation + knowledge-base endpoints."""

import csv
import io
import uuid
from enum import Enum
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from src.ingestion.parsers.csv_parser import parse_csv
from src.ingestion.parsers.excel_parser import parse_excel
from src.ingestion.schema import Transaction
from src.ingestion.enricher import enrich_transactions
from src.matching_engine.ledger_bank_aligner import align
from src.llm.client import get_openai_client, get_model

from src.rag.knowledge_base import (
    delete_document,
    ingest_document,
    list_documents,
    query_knowledge_base,
)

app = FastAPI(title="SmartBots Bank Reconciliation", version="0.1.0")

# ---------------------------------------------------------------------------
# In-memory stores (single-process local dev)
# ---------------------------------------------------------------------------

_runs: dict[str, dict[str, Any]] = {}
_exceptions: dict[str, dict[str, Any]] = {}  # exception_id → exception data


class RunStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class RunResponse(BaseModel):
    run_id: str


class StatusResponse(BaseModel):
    run_id: str
    status: RunStatus


class ExceptionAction(BaseModel):
    reason: str = ""


class ManualMatchBody(BaseModel):
    ledger_id: str
    bank_id: str


# ---------------------------------------------------------------------------
# File format detection
# ---------------------------------------------------------------------------

_SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _detect_format(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return "csv"
    if lower.endswith((".xlsx", ".xls")):
        return "excel"
    if lower.endswith(".bai2") or lower.endswith(".bai"):
        return "bai2"
    raise ValueError(f"Unsupported file format: {filename}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/reconcile", response_model=RunResponse)
async def reconcile(
    file: UploadFile = File(...),
    bank_name: str = Form("Generic"),
    ledger_file: UploadFile | None = File(None),
):
    """Accept file upload, detect format, and run reconciliation.

    - `file`: Bank statement (CSV/Excel)
    - `bank_name`: Bank name for rule matching
    - `ledger_file`: Optional separate ledger file. If not provided, the
      uploaded file is treated as containing both ledger and bank data
      (first sheet = ledger, second sheet = bank for Excel; for CSV we
      expect two files).
    """
    run_id = str(uuid.uuid4())

    # Validate file size
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")

    filename = file.filename or "upload.csv"
    try:
        fmt = _detect_format(filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    _runs[run_id] = {"status": RunStatus.running, "report": None, "exceptions": {}}

    try:
        bank_transactions: list[Transaction] = []
        ledger_transactions: list[Transaction] = []

        if fmt == "csv":
            bank_transactions = parse_csv(io.BytesIO(content))
            if ledger_file:
                ledger_content = await ledger_file.read()
                ledger_transactions = parse_csv(io.BytesIO(ledger_content))
        elif fmt == "excel":
            bank_transactions = parse_excel(io.BytesIO(content), sheet_name="bank")
            if ledger_file:
                ledger_content = await ledger_file.read()
                ledger_transactions = parse_excel(io.BytesIO(ledger_content), sheet_name="ledger")
            else:
                # Try second sheet
                try:
                    ledger_transactions = parse_excel(io.BytesIO(content), sheet_name="ledger")
                except Exception:
                    ledger_transactions = []

        result = align(
            enrich_transactions(ledger_transactions, bank_name),
            enrich_transactions(bank_transactions, bank_name),
            bank_name=bank_name,
        )

        # Build exception queue
        exceptions_dict: dict[str, dict[str, Any]] = {}
        for txn in result["unmatched_ledger"]:
            exc_id = str(uuid.uuid4())
            exc = {
                "id": exc_id,
                "run_id": run_id,
                "transaction_id": txn.id,
                "source": "ledger",
                "status": "pending",
                "amount": str(txn.amount),
                "date": str(txn.date),
                "description": txn.description,
            }
            exceptions_dict[exc_id] = exc
            _exceptions[exc_id] = exc

        for txn in result["unmatched_bank"]:
            exc_id = str(uuid.uuid4())
            exc = {
                "id": exc_id,
                "run_id": run_id,
                "transaction_id": txn.id,
                "source": "bank",
                "status": "pending",
                "amount": str(txn.amount),
                "date": str(txn.date),
                "description": txn.description,
            }
            exceptions_dict[exc_id] = exc
            _exceptions[exc_id] = exc

        report = {
            "run_id": run_id,
            "bank": bank_name,
            "matched_count": len(result["matched_pairs"]),
            "unmatched_ledger_count": len(result["unmatched_ledger"]),
            "unmatched_bank_count": len(result["unmatched_bank"]),
            "matches": [m.model_dump(mode="json") for m in result["matched_pairs"]],
            "exception_ids": list(exceptions_dict.keys()),
        }

        _runs[run_id]["status"] = RunStatus.completed
        _runs[run_id]["report"] = report
        _runs[run_id]["exceptions"] = exceptions_dict

    except Exception as e:
        _runs[run_id]["status"] = RunStatus.failed
        _runs[run_id]["report"] = {"error": str(e)}

    return RunResponse(run_id=run_id)


@app.get("/reconcile/{run_id}/status", response_model=StatusResponse)
async def get_status(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    return StatusResponse(run_id=run_id, status=_runs[run_id]["status"])


@app.get("/reconcile/{run_id}/report")
async def get_report(run_id: str):
    if run_id not in _runs:
        raise HTTPException(status_code=404, detail="Run not found")
    run = _runs[run_id]
    if run["status"] != RunStatus.completed:
        raise HTTPException(status_code=409, detail=f"Run status: {run['status']}")
    return run["report"]


@app.get("/exceptions/queue")
async def exception_queue():
    """List all pending human review items."""
    return [exc for exc in _exceptions.values() if exc["status"] == "pending"]


@app.post("/exceptions/{exception_id}/approve")
async def approve_exception(exception_id: str, body: ExceptionAction | None = None):
    if exception_id not in _exceptions:
        raise HTTPException(status_code=404, detail="Exception not found")
    _exceptions[exception_id]["status"] = "approved"
    _exceptions[exception_id]["reason"] = body.reason if body else ""
    return _exceptions[exception_id]


@app.post("/exceptions/{exception_id}/reject")
async def reject_exception(exception_id: str, body: ExceptionAction | None = None):
    if exception_id not in _exceptions:
        raise HTTPException(status_code=404, detail="Exception not found")
    _exceptions[exception_id]["status"] = "rejected"
    _exceptions[exception_id]["reason"] = body.reason if body else ""
    return _exceptions[exception_id]


@app.post("/exceptions/{exception_id}/manual-match")
async def manual_match(exception_id: str, body: ManualMatchBody):
    if exception_id not in _exceptions:
        raise HTTPException(status_code=404, detail="Exception not found")
    _exceptions[exception_id]["status"] = "manually_matched"
    _exceptions[exception_id]["manual_match"] = {
        "ledger_id": body.ledger_id,
        "bank_id": body.bank_id,
    }
    return _exceptions[exception_id]


# ---------------------------------------------------------------------------
# Knowledge Base Endpoints
# ---------------------------------------------------------------------------

_KB_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".xls", ".txt", ".md", ".csv", ".json"}


@app.post("/knowledge-base/upload")
async def kb_upload(file: UploadFile = File(...)):
    """Upload a document (PDF, Word, Excel, text) into the knowledge base."""
    filename = file.filename or "upload.bin"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in _KB_ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(_KB_ALLOWED_EXTENSIONS)}",
        )

    content_bytes = await file.read()
    if len(content_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 50 MB)")
    if len(content_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    result = ingest_document(filename, io.BytesIO(content_bytes), content_bytes=content_bytes)
    return result


@app.get("/knowledge-base/documents")
async def kb_list():
    """List all documents in the knowledge base."""
    return list_documents()


@app.delete("/knowledge-base/documents/{filename:path}")
async def kb_delete(filename: str, content_hash: str | None = Query(None)):
    """Delete a document (all its chunks) from the knowledge base."""
    deleted = delete_document(filename, content_hash=content_hash)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"filename": filename, "deleted_chunks": deleted}


@app.get("/knowledge-base/search")
async def kb_search(
    q: str = Query(..., min_length=1),
    n: int = Query(5, ge=1, le=50),
    filename: str | None = Query(None),
    summarize: bool = Query(False),
):
    """Search the knowledge base for relevant chunks, optionally with an LLM summary."""
    chunks = query_knowledge_base(q, n_results=n, filename_filter=filename)

    if not summarize or not chunks:
        return {"chunks": chunks, "summary": None}

    # Build context from retrieved chunks for the LLM
    context_parts = []
    for i, c in enumerate(chunks, 1):
        meta = c.get("metadata", {})
        source = meta.get("filename", "unknown")
        context_parts.append(
            f"[Source: {source}, chunk {meta.get('chunk_index', '?')}/{meta.get('total_chunks', '?')}, "
            f"similarity: {c.get('similarity', 0):.4f}]\n{c.get('document', '')}"
        )
    context_block = "\n\n---\n\n".join(context_parts)

    try:
        client = get_openai_client()
        model = get_model()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant for a bank reconciliation system. "
                        "Given the user's query and retrieved document chunks, provide a "
                        "clear, concise summary that directly answers the query. "
                        "Cite the source filenames when referencing specific information. "
                        "If the chunks don't contain relevant information, say so."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Query: {q}\n\n"
                        f"Retrieved documents:\n\n{context_block}"
                    ),
                },
            ],
            temperature=0.3,
            max_tokens=1024,
        )
        summary = response.choices[0].message.content
    except Exception as e:
        summary = f"Summary generation failed: {e}"

    return {"chunks": chunks, "summary": summary}
