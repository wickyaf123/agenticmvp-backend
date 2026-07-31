"""Noop node. Used by Phase 0 verification.

Behavior:
- Sleeps a beat to make the run observable in Realtime.
- If `state['input'].get('force_failure')` is true, raises once to exercise the
  L1 retry path; on the retry it succeeds.
- Writes a single trace entry and returns a partial state update.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.orchestrator.runs import emit_event
from app.orchestrator.state import GraphState

logger = logging.getLogger(__name__)


async def run(state: GraphState, config: dict[str, Any]) -> dict[str, Any]:
    meta = state.get("meta", {})
    run_id = meta.get("run_id", "unknown")
    attempt = config.get("metadata", {}).get("attempt", 1)

    emit_event(
        agent_id=None,
        event_type="node_started",
        payload={"run_id": run_id, "node": "noop", "attempt": attempt},
    )

    await asyncio.sleep(0.25)

    force = bool(state.get("input", {}).get("force_failure"))
    if force and attempt == 1:
        emit_event(
            agent_id=None,
            event_type="node_retried",
            payload={"run_id": run_id, "node": "noop", "reason": "forced_failure_test"},
        )
        raise RuntimeError("forced failure (test path) — retry should recover")

    emit_event(
        agent_id=None,
        event_type="node_succeeded",
        payload={"run_id": run_id, "node": "noop"},
    )

    return {
        "trace": [{"node": "noop", "ok": True, "attempt": attempt}],
        "output": {"message": "noop ok"},
        "status": "succeeded",
    }
