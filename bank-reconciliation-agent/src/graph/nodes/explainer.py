"""Explainer node — generates human-readable explanations per exception."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.graph.state import ReconciliationState
from src.llm.client import get_openai_client, get_model
from src.rag.retriever import retrieve

_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "llm" / "prompts" / "explanation_generation.txt"


@lru_cache(maxsize=1)
def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _explain_one(exc: dict, prompt_template: str, client, model: str) -> tuple[str, str]:
    """Generate explanation for a single exception. Returns (txn_id, explanation)."""
    txn_id = exc.get("transaction_id", "")

    rag_results = exc.get("rag_context", [])
    if not rag_results:
        rag_results = retrieve(
            "prior_reconciliations",
            query_text=exc.get("explanation", exc.get("category", "")),
            n_results=3,
        )

    context_str = "\n".join(
        f"- {c.get('document', '')}" for c in rag_results
    ) or "No similar cases found."

    filled = prompt_template.replace("{rag_context}", context_str).replace(
        "{exception}", json.dumps(dict(exc), default=str)
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": filled}],
        temperature=0.3,
        max_tokens=300,
    )
    return txn_id, response.choices[0].message.content.strip()


def explainer(state: ReconciliationState) -> dict[str, Any]:
    """Generate human-readable explanations for all exceptions."""
    client = get_openai_client()
    model = get_model()
    prompt_template = _load_prompt()

    explanations: dict[str, str] = dict(state.get("explanations", {}))

    # Collect exceptions that need explaining
    to_explain = [
        exc for exc in state.get("exceptions", [])
        if exc.get("transaction_id", "") not in explanations
    ]

    if not to_explain:
        return {"explanations": explanations}

    # Explain in parallel using threads
    max_workers = min(len(to_explain), 8)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_explain_one, exc, prompt_template, client, model): exc
            for exc in to_explain
        }
        for future in as_completed(futures):
            try:
                txn_id, explanation = future.result()
                explanations[txn_id] = explanation
            except Exception:
                exc = futures[future]
                explanations[exc.get("transaction_id", "")] = "Explanation generation failed."

    return {"explanations": explanations}
