"""Supervisor graph builder.

Phase 0: a single 'noop' graph used for end-to-end verification.
Subsequent phases register real graphs (content_pipeline, outreach, call,
funnel) keyed by `run_type`.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.orchestrator.kill import is_killed
from app.orchestrator.nodes import noop
from app.orchestrator.runs import emit_event
from app.orchestrator.state import GraphState

logger = logging.getLogger(__name__)

NodeRunner = Callable[[GraphState, dict[str, Any]], Awaitable[dict[str, Any]]]


def _wrap_with_retry(runner: NodeRunner, *, node_name: str) -> NodeRunner:
    """L2: re-invoke a node up to 2x on transient exceptions."""

    async def _wrapped(state: GraphState, config: dict[str, Any]) -> dict[str, Any]:
        meta = state.get("meta", {})
        run_id = meta.get("run_id")
        if is_killed(run_id=run_id):
            emit_event(
                agent_id=None,
                event_type="kill_switch_engaged",
                payload={"run_id": run_id, "node": node_name},
            )
            return {"status": "killed"}

        attempt = 0
        async for attempt_ctx in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.5, min=0.25, max=4),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt_ctx:
                attempt += 1
                cfg = {**config, "metadata": {**(config.get("metadata") or {}), "attempt": attempt}}
                return await runner(state, cfg)
        return {}  # unreachable; tenacity reraises

    return _wrapped


def build_noop_graph() -> StateGraph:
    g = StateGraph(GraphState)
    g.add_node("noop", _wrap_with_retry(noop.run, node_name="noop"))
    g.add_edge(START, "noop")
    g.add_edge("noop", END)
    return g


# Registry — extended per phase with real graphs.
GRAPH_REGISTRY: dict[str, Callable[[], StateGraph]] = {
    "noop": build_noop_graph,
}


async def compile_for(run_type: str, checkpointer: AsyncPostgresSaver):
    builder = GRAPH_REGISTRY.get(run_type)
    if builder is None:
        raise ValueError(f"Unknown run_type: {run_type}. Registered: {list(GRAPH_REGISTRY)}")
    graph = builder()
    return graph.compile(checkpointer=checkpointer)
