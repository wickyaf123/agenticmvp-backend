"""Typed graph state shared across orchestrator nodes."""
from __future__ import annotations

from operator import add
from typing import Annotated, Any, Literal, Optional, TypedDict


class RunMeta(TypedDict, total=False):
    """Bookkeeping injected by the run starter; never mutated by nodes."""

    run_id: str
    thread_id: str
    run_type: str
    triggered_by: Optional[str]


class CostAccumulator(TypedDict, total=False):
    tokens: int
    dollar_cents: int


def _merge_cost(left: CostAccumulator, right: CostAccumulator) -> CostAccumulator:
    return {
        "tokens": int(left.get("tokens", 0)) + int(right.get("tokens", 0)),
        "dollar_cents": int(left.get("dollar_cents", 0)) + int(right.get("dollar_cents", 0)),
    }


class GraphState(TypedDict, total=False):
    """Shared LangGraph state.

    Lists use `add` reducer so concurrent branches can append safely.
    """

    meta: RunMeta
    input: dict[str, Any]
    output: dict[str, Any]

    # Lead-funnel scratchpad (populated as we walk capture -> enrich -> ... -> call)
    lead_id: Optional[str]
    lead_facts: dict[str, Any]
    score: Optional[int]

    # Drafts being shaped by nodes
    drafts: Annotated[list[dict[str, Any]], add]

    # Eval results (each entry: {kind, target_id, passed, scores, reasoning})
    evals: Annotated[list[dict[str, Any]], add]

    # Trail of node decisions for the run inspector
    trace: Annotated[list[dict[str, Any]], add]

    # Cost accounting (LLM tokens + provider $)
    cost: Annotated[CostAccumulator, _merge_cost]

    # Routing hints from the supervisor
    next_node: Optional[str]
    status: Literal["running", "needs_human", "succeeded", "failed", "killed"]
    error: Optional[str]


def initial_state(run_meta: RunMeta, payload: dict[str, Any]) -> GraphState:
    return GraphState(
        meta=run_meta,
        input=payload,
        output={},
        lead_facts={},
        drafts=[],
        evals=[],
        trace=[],
        cost=CostAccumulator(tokens=0, dollar_cents=0),
        status="running",
    )
