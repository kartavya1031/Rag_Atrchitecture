"""Exception classifier node — uses GPT-4o few-shot classification."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.graph.state import ExceptionItem, ReconciliationState
from src.llm.client import get_openai_client, get_model
from src.rag.retriever import retrieve

_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "llm" / "prompts" / "exception_classification.txt"


@lru_cache(maxsize=1)
def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _classify_single(
    txn_dict: dict[str, Any],
    rag_context: list[dict],
    client,
    model: str,
) -> dict[str, Any]:
    """Classify a single unmatched transaction."""
    prompt = _load_prompt()
    context_str = "\n".join(
        f"- [{c.get('metadata', {}).get('exception_type', 'N/A')}] {c.get('document', '')}"
        for c in rag_context
    ) or "No similar historical cases found."

    filled = prompt.replace("{rag_context}", context_str).replace(
        "{transaction}", json.dumps(txn_dict, default=str)
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": filled}],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def _classify_one_txn(txn, source: str, client, model: str) -> ExceptionItem:
    """Retrieve RAG context and classify a single transaction (used by thread pool)."""
    txn_dict = txn.model_dump(mode="json") if hasattr(txn, "model_dump") else dict(txn)
    rag_results = retrieve(
        "prior_reconciliations",
        query_text=txn_dict.get("description", ""),
        n_results=3,
    )
    result = _classify_single(txn_dict, rag_results, client, model)
    return ExceptionItem(
        transaction_id=txn_dict["id"],
        source=source,
        category=result.get("category", "unknown"),
        confidence=float(result.get("confidence", 0.0)),
        explanation=result.get("reasoning", ""),
        rag_context=rag_results,
        soft_match_candidate=None,
        soft_match_confidence=0.0,
    )


def exception_classifier(state: ReconciliationState) -> dict[str, Any]:
    """Classify each unmatched transaction into an exception category."""
    client = get_openai_client()
    model = get_model()

    exceptions: list[ExceptionItem] = list(state.get("exceptions", []))

    # Collect all unmatched transactions for parallel classification
    tasks: list[tuple] = []
    for txn in state.get("unmatched_ledger", []):
        tasks.append((txn, "ledger"))
    for txn in state.get("unmatched_bank", []):
        tasks.append((txn, "bank"))

    if not tasks:
        return {"exceptions": exceptions}

    # Classify in parallel using threads (OpenAI calls are I/O-bound)
    max_workers = min(len(tasks), 8)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_classify_one_txn, txn, source, client, model): (txn, source)
            for txn, source in tasks
        }
        for future in as_completed(futures):
            try:
                exceptions.append(future.result())
            except Exception:
                txn, source = futures[future]
                txn_dict = txn.model_dump(mode="json") if hasattr(txn, "model_dump") else dict(txn)
                exceptions.append(ExceptionItem(
                    transaction_id=txn_dict["id"],
                    source=source,
                    category="unknown",
                    confidence=0.0,
                    explanation="Classification failed",
                    rag_context=[],
                    soft_match_candidate=None,
                    soft_match_confidence=0.0,
                ))

    return {"exceptions": exceptions}
