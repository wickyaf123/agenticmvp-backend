"""End-to-end run executor: glue between FastAPI routes and LangGraph."""
from __future__ import annotations

import logging
from typing import Any

from app.orchestrator.checkpointer import open_checkpointer
from app.orchestrator.graph import compile_for
from app.orchestrator.runs import (
    create_run,
    emit_event,
    mark_started,
    mark_terminal,
)
from app.orchestrator.state import RunMeta, initial_state

logger = logging.getLogger(__name__)


async def start_run(
    *,
    run_type: str,
    payload: dict[str, Any],
    triggered_by: str | None = None,
) -> dict[str, Any]:
    run = create_run(
        run_type=run_type, input_payload=payload, triggered_by=triggered_by
    )
    run_id = run["id"]
    thread_id = run["thread_id"]
    meta = RunMeta(
        run_id=run_id, thread_id=thread_id, run_type=run_type, triggered_by=triggered_by
    )
    state = initial_state(meta, payload)

    emit_event(
        agent_id=None,
        event_type="run_started",
        payload={"run_id": run_id, "run_type": run_type},
    )
    mark_started(run_id)

    try:
        async with open_checkpointer() as cp:
            graph = await compile_for(run_type, cp)
            final_state = await graph.ainvoke(
                state,
                config={"configurable": {"thread_id": thread_id}},
            )
        status = final_state.get("status", "succeeded")
        cost = final_state.get("cost", {}) or {}
        if status == "killed":
            mark_terminal(run_id, status="killed", output=final_state.get("output"))
            emit_event(
                agent_id=None,
                event_type="run_killed",
                payload={"run_id": run_id},
            )
        else:
            mark_terminal(
                run_id,
                status="succeeded",
                output=final_state.get("output"),
                tokens=int(cost.get("tokens", 0)),
                cost_cents=int(cost.get("dollar_cents", 0)),
            )
            emit_event(
                agent_id=None,
                event_type="run_succeeded",
                payload={"run_id": run_id, "output": final_state.get("output")},
            )
        return {"run_id": run_id, "status": status, "output": final_state.get("output")}
    except Exception as exc:  # noqa: BLE001
        logger.exception("Run %s failed", run_id)
        mark_terminal(run_id, status="failed", error=str(exc))
        emit_event(
            agent_id=None,
            event_type="run_failed",
            payload={"run_id": run_id, "error": str(exc)},
        )
        raise
