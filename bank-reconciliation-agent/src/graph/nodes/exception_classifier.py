"""Exception classifier node — uses GPT-4o few-shot classification."""

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from src.graph.state import ExceptionItem, ReconciliationState
from src.rag.retriever import retrieve
from src.utils.config import get_env

_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "llm" / "prompts" / "exception_classification.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _classify_single(
    txn_dict: dict[str, Any],
    rag_context: list[dict],
    client: OpenAI,
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


def exception_classifier(state: ReconciliationState) -> dict[str, Any]:
    """Classify each unmatched transaction into an exception category."""
    client = OpenAI(api_key=get_env("OPENAI_API_KEY"))
    model = get_env("OPENAI_MODEL", "gpt-4o")

    exceptions: list[ExceptionItem] = list(state.get("exceptions", []))
    chroma_client = None  # use default

    for txn in state.get("unmatched_ledger", []):
        txn_dict = txn.model_dump(mode="json") if hasattr(txn, "model_dump") else dict(txn)
        rag_results = retrieve(
            "prior_reconciliations",
            query_text=txn_dict.get("description", ""),
            n_results=3,
            client=chroma_client,
        )
        result = _classify_single(txn_dict, rag_results, client, model)
        exceptions.append(ExceptionItem(
            transaction_id=txn_dict["id"],
            source="ledger",
            category=result.get("category", "unknown"),
            confidence=float(result.get("confidence", 0.0)),
            explanation=result.get("reasoning", ""),
            rag_context=rag_results,
            soft_match_candidate=None,
            soft_match_confidence=0.0,
        ))

    for txn in state.get("unmatched_bank", []):
        txn_dict = txn.model_dump(mode="json") if hasattr(txn, "model_dump") else dict(txn)
        rag_results = retrieve(
            "prior_reconciliations",
            query_text=txn_dict.get("description", ""),
            n_results=3,
            client=chroma_client,
        )
        result = _classify_single(txn_dict, rag_results, client, model)
        exceptions.append(ExceptionItem(
            transaction_id=txn_dict["id"],
            source="bank",
            category=result.get("category", "unknown"),
            confidence=float(result.get("confidence", 0.0)),
            explanation=result.get("reasoning", ""),
            rag_context=rag_results,
            soft_match_candidate=None,
            soft_match_confidence=0.0,
        ))

    return {"exceptions": exceptions}
