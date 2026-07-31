"""Kill-switch helpers. Polled by the supervisor before every node."""
from __future__ import annotations

from typing import Optional

from app.services.supabase_client import get_client


def is_killed(*, run_id: Optional[str] = None, agent_id: Optional[str] = None) -> bool:
    """Returns True if any matching kill switch is active.

    Order of escalation: global > workflow > agent > run.
    """
    sb = get_client()
    q = sb.table("kill_switches").select("scope,scope_id,is_active").eq("is_active", True)
    rows = q.execute().data or []
    for r in rows:
        scope = r["scope"]
        scope_id = r["scope_id"]
        if scope == "global":
            return True
        if scope == "run" and run_id and scope_id == run_id:
            return True
        if scope == "agent" and agent_id and scope_id == agent_id:
            return True
    return False


def engage(
    *,
    scope: str,
    scope_id: Optional[str] = None,
    reason: str,
    set_by: Optional[str] = None,
) -> dict:
    sb = get_client()
    payload = {
        "scope": scope,
        "scope_id": scope_id,
        "is_active": True,
        "reason": reason,
        "set_by": set_by,
        "set_at": "now()",
    }
    # Upsert by (scope, scope_id) unique constraint.
    res = (
        sb.table("kill_switches")
        .upsert(payload, on_conflict="scope,scope_id")
        .execute()
    )
    return res.data[0]


def clear(*, scope: str, scope_id: Optional[str] = None) -> None:
    sb = get_client()
    sb.table("kill_switches").update(
        {"is_active": False, "cleared_at": "now()"}
    ).eq("scope", scope).is_("scope_id", scope_id if scope_id else "null").execute()
