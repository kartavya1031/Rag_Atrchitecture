"""Explainer node — generates human-readable explanations per exception."""

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from src.graph.state import ReconciliationState
from src.rag.retriever import retrieve
from src.utils.config import get_env

_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "llm" / "prompts" / "explanation_generation.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def explainer(state: ReconciliationState) -> dict[str, Any]:
    """Generate human-readable explanations for all exceptions."""
    client = OpenAI(api_key=get_env("OPENAI_API_KEY"))
    model = get_env("OPENAI_MODEL", "gpt-4o")
    prompt_template = _load_prompt()

    explanations: dict[str, str] = dict(state.get("explanations", {}))

    for exc in state.get("exceptions", []):
        txn_id = exc.get("transaction_id", "")
        if txn_id in explanations:
            continue

        # Retrieve top-3 similar cases for context
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
        explanations[txn_id] = response.choices[0].message.content.strip()

    return {"explanations": explanations}
