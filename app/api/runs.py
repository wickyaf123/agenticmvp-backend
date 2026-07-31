"""HTTP routes for orchestrator runs (start, inspect, kill)."""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.orchestrator import kill as kill_mod
from app.orchestrator.executor import start_run
from app.queue.worker import enqueue_run
from app.services.supabase_client import get_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/runs", tags=["runs"])


class StartRunRequest(BaseModel):
    run_type: str = Field(..., description="Registered graph key, e.g. 'noop'")
    payload: dict[str, Any] = Field(default_factory=dict)
    triggered_by: Optional[str] = None
    sync: bool = Field(False, description="If true, execute inline; else enqueue to RQ")


class StartRunResponse(BaseModel):
    run_id: Optional[str] = None
    job_id: Optional[str] = None
    mode: str


@router.post("", response_model=StartRunResponse)
async def start(req: StartRunRequest, background: BackgroundTasks):
    if req.sync:
        result = await start_run(
            run_type=req.run_type, payload=req.payload, triggered_by=req.triggered_by
        )
        return StartRunResponse(run_id=result["run_id"], mode="sync")

    try:
        job_id = enqueue_run(req.run_type, req.payload, triggered_by=req.triggered_by)
        return StartRunResponse(job_id=job_id, mode="enqueued")
    except Exception as exc:  # noqa: BLE001
        # Fallback: in dev (no Redis) accept inline execution.
        logger.warning("RQ enqueue failed (%s); falling back to background task", exc)
        background.add_task(_run_in_background, req.run_type, req.payload, req.triggered_by)
        return StartRunResponse(mode="background-task")


async def _run_in_background(run_type: str, payload: dict, triggered_by: Optional[str]) -> None:
    try:
        await start_run(run_type=run_type, payload=payload, triggered_by=triggered_by)
    except Exception:  # noqa: BLE001
        logger.exception("Background run failed")


@router.get("/{run_id}")
def get_run(run_id: str):
    sb = get_client()
    res = sb.table("agent_runs").select("*").eq("id", run_id).limit(1).execute()
    if not res.data:
        raise HTTPException(404, "run not found")
    return res.data[0]


@router.get("/{run_id}/events")
def get_events(run_id: str, limit: int = 200):
    sb = get_client()
    res = (
        sb.table("agent_events")
        .select("*")
        .contains("payload", {"run_id": run_id})
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


class KillRequest(BaseModel):
    scope: str = Field("run", description="'global'|'agent'|'workflow'|'run'")
    scope_id: Optional[str] = None
    reason: str = "manual"


@router.post("/{run_id}/kill")
def kill(run_id: str, req: KillRequest):
    return kill_mod.engage(scope=req.scope, scope_id=req.scope_id or run_id, reason=req.reason)


class GlobalKillRequest(BaseModel):
    enabled: bool
    reason: str = "manual"


@router.post("/kill/global", tags=["kill-switch"])
def kill_global(req: GlobalKillRequest):
    if req.enabled:
        return kill_mod.engage(scope="global", scope_id=None, reason=req.reason)
    kill_mod.clear(scope="global", scope_id=None)
    return {"scope": "global", "is_active": False}
