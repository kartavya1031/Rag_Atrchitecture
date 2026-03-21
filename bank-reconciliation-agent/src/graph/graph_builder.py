"""Build and compile the reconciliation LangGraph StateGraph."""

from typing import Any

from langgraph.graph import END, StateGraph

from src.graph.nodes.exception_classifier import exception_classifier
from src.graph.nodes.explainer import explainer
from src.graph.nodes.edge_case_reasoner import edge_case_reasoner
from src.graph.nodes.soft_matcher import soft_matcher
from src.graph.nodes.validator_node import validator_node
from src.graph.routes import after_deterministic
from src.graph.state import ReconciliationState
from src.ingestion.schema import Transaction
from src.matching_engine.ledger_bank_aligner import align


# ---------------------------------------------------------------------------
# Wrapper nodes that operate on ReconciliationState
# ---------------------------------------------------------------------------

def deterministic_match_node(state: ReconciliationState) -> dict[str, Any]:
    """Run exact → rule → tolerance matchers."""
    ledger = state.get("ledger_transactions", [])
    bank = state.get("bank_transactions", [])
    bank_name = state.get("bank_name", "Generic")
    result = align(ledger, bank, bank_name=bank_name)
    return {
        "matches": result["matched_pairs"],
        "unmatched_ledger": result["unmatched_ledger"],
        "unmatched_bank": result["unmatched_bank"],
    }


def soft_match_and_reason_node(state: ReconciliationState) -> dict[str, Any]:
    """Run soft matcher + edge-case reasoner sequentially."""
    updates: dict[str, Any] = {}
    sm_result = soft_matcher(state)
    updates.update(sm_result)
    # Merge soft matches into state for edge-case reasoner
    merged_state = {**state, **updates}
    ec_result = edge_case_reasoner(merged_state)
    updates.update(ec_result)
    return updates


def explain_node(state: ReconciliationState) -> dict[str, Any]:
    """Generate explanations for all exceptions."""
    return explainer(state)


def output_node(state: ReconciliationState) -> dict[str, Any]:
    """Assemble the final report."""
    matches = state.get("matches", [])
    soft = state.get("soft_match_candidates", [])
    all_matches = list(matches) + list(soft)

    return {
        "final_report": {
            "matched_count": len(all_matches),
            "unmatched_ledger_count": len(state.get("unmatched_ledger", [])),
            "unmatched_bank_count": len(state.get("unmatched_bank", [])),
            "exception_count": len(state.get("exceptions", [])),
            "human_review_count": len(state.get("human_review_queue", [])),
        }
    }


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Assemble the reconciliation StateGraph."""
    graph = StateGraph(ReconciliationState)

    # Add nodes
    graph.add_node("deterministic_match", deterministic_match_node)
    graph.add_node("exception_classifier", exception_classifier)
    graph.add_node("soft_match_and_reason", soft_match_and_reason_node)
    graph.add_node("explainer", explain_node)
    graph.add_node("validator", validator_node)
    graph.add_node("output", output_node)

    # Entry
    graph.set_entry_point("deterministic_match")

    # Edges
    graph.add_conditional_edges(
        "deterministic_match",
        after_deterministic,
        {
            "exception_classifier": "exception_classifier",
            "output": "output",
        },
    )
    graph.add_edge("exception_classifier", "soft_match_and_reason")
    graph.add_edge("soft_match_and_reason", "explainer")
    graph.add_edge("explainer", "validator")
    graph.add_edge("validator", "output")
    graph.add_edge("output", END)

    return graph


def compile_graph():
    """Build and compile the graph, returning a runnable."""
    return build_graph().compile()
