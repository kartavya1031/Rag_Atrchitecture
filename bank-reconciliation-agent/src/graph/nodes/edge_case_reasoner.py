"""Edge-case reasoner node — chain-of-thought for reversals, partial payments, etc."""

import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from src.graph.state import ReconciliationState
from src.matching_engine.models import MatchResult
from src.rag.retriever import retrieve
from src.utils.config import get_env

_PROMPT_PATH = Path(__file__).resolve().parent.parent.parent / "llm" / "prompts" / "edge_case_reasoning.txt"


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def edge_case_reasoner(state: ReconciliationState) -> dict[str, Any]:
    """Use chain-of-thought LLM reasoning for complex edge cases."""
    unmatched_ledger = state.get("unmatched_ledger", [])
    unmatched_bank = state.get("unmatched_bank", [])

    if not unmatched_ledger and not unmatched_bank:
        return {}

    client = OpenAI(api_key=get_env("OPENAI_API_KEY"))
    model = get_env("OPENAI_MODEL", "gpt-4o")

    # Retrieve relevant policy / SOP context
    rag_results = retrieve(
        "policies_sops",
        query_text="reversal partial payment edge case reconciliation",
        n_results=3,
    )
    context_str = "\n".join(
        f"- {c.get('document', '')}" for c in rag_results
    ) or "No policy context available."

    ledger_dicts = [
        t.model_dump(mode="json") if hasattr(t, "model_dump") else dict(t)
        for t in unmatched_ledger
    ]
    bank_dicts = [
        t.model_dump(mode="json") if hasattr(t, "model_dump") else dict(t)
        for t in unmatched_bank
    ]

    prompt_template = _load_prompt()
    filled = (
        prompt_template
        .replace("{rag_context}", context_str)
        .replace("{unmatched_ledger}", json.dumps(ledger_dicts, default=str))
        .replace("{unmatched_bank}", json.dumps(bank_dicts, default=str))
    )

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": filled}],
        temperature=0.2,
        response_format={"type": "json_object"},
    )

    try:
        result = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, IndexError):
        return {}

    new_matches: list[MatchResult] = list(state.get("soft_match_candidates", []))
    for m in result.get("proposed_matches", []):
        new_matches.append(MatchResult(
            ledger_id=m["ledger_id"],
            bank_id=m["bank_id"],
            confidence=float(m.get("confidence", 0.5)),
            method="llm",
            details=m.get("reasoning", "LLM edge-case reasoning"),
        ))

    return {"soft_match_candidates": new_matches}
