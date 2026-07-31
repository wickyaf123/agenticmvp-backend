"""Run lifecycle: create row, stream events to Supabase, mark terminal.

Every orchestrator action that the dashboard needs to observe is recorded as
either a row in `agent_runs` or an event in `agent_events`. The dashboard
subscribes to both via Supabase Realtime.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from app.services.supabase_client import get_client

logger = logging.getLogger(__name__)

EventType = Literal[
    "run_started",
    "run_succeeded",
    "run_failed",
    "run_killed",
    "node_started",
    "node_succeeded",
    "node_failed",
    "node_retried",
    "tool_call",
    "tool_retry",
    "tool_circuit_open",
    "tool_circuit_close",
    "eval_passed",
    "eval_failed",
    "human_required",
    "budget_warning",
    "budget_exceeded",
    "kill_switch_engaged",
]


def create_run(
    *,
    run_type: str,
    input_payload: dict[str, Any],
    agent_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    triggered_by: Optional[str] = None,
) -> dict[str, Any]:
    """Insert a new agent_runs row and return it. Generates a thread_id."""
    sb = get_client()
    thread_id = f"thr_{uuid.uuid4().hex[:24]}"
    row = {
        "run_type": run_type,
        "status": "pending",
        "thread_id": thread_id,
        "input": input_payload,
        "agent_id": agent_id,
        "workflow_id": workflow_id,
        "triggered_by": triggered_by,
    }
    inserted = sb.table("agent_runs").insert(row).execute()
    return inserted.data[0]


def mark_started(run_id: str) -> None:
    _patch_run(run_id, {"status": "running", "started_at": _now()})


def mark_terminal(
    run_id: str,
    *,
    status: Literal["succeeded", "failed", "killed", "needs_human"],
    output: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
    tokens: int = 0,
    cost_cents: int = 0,
) -> None:
    patch: dict[str, Any] = {
        "status": status,
        "completed_at": _now(),
        "total_tokens": tokens,
        "total_cost_cents": cost_cents,
    }
    if output is not None:
        patch["output"] = output
    if error is not None:
        patch["error"] = error
    _patch_run(run_id, patch)


def emit_event(
    *,
    agent_id: Optional[str],
    event_type: EventType,
    payload: dict[str, Any],
) -> None:
    """Append to agent_events (which is Realtime-published).

    `agent_id` may be None for run-level / system events; the table currently
    requires an agent_id, so runs without an owning agent are written into a
    system 'orchestrator' agent (created lazily on first call).
    """
    sb = get_client()
    if agent_id is None:
        agent_id = _orchestrator_system_agent_id()
    sb.table("agent_events").insert(
        {"agent_id": agent_id, "event_type": event_type, "payload": payload}
    ).execute()


_SYSTEM_AGENT_CACHE: Optional[str] = None


def _orchestrator_system_agent_id() -> str:
    global _SYSTEM_AGENT_CACHE
    if _SYSTEM_AGENT_CACHE:
        return _SYSTEM_AGENT_CACHE
    sb = get_client()
    existing = (
        sb.table("agents").select("id").eq("slug", "orchestrator-system").limit(1).execute()
    )
    if existing.data:
        _SYSTEM_AGENT_CACHE = existing.data[0]["id"]
        return _SYSTEM_AGENT_CACHE
    inserted = (
        sb.table("agents")
        .insert(
            {
                "name": "Orchestrator",
                "slug": "orchestrator-system",
                "agent_type": "system",
                "status": "online",
                "capabilities": ["supervisor", "router"],
                "color": "#ff4d00",
            }
        )
        .execute()
    )
    _SYSTEM_AGENT_CACHE = inserted.data[0]["id"]
    return _SYSTEM_AGENT_CACHE


def _patch_run(run_id: str, patch: dict[str, Any]) -> None:
    get_client().table("agent_runs").update(patch).eq("id", run_id).execute()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
