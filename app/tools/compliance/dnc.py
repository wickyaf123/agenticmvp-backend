"""Do-Not-Call list check.

Phase 0: stub that consults `dnc_cache` only. Real National DNC + state DNC
fetchers ship in Phase 3 alongside outbound calling.
"""
from __future__ import annotations

from typing import Optional

from app.services.supabase_client import get_client


def is_blocked(phone_e164: str) -> tuple[bool, Optional[str]]:
    """Return (blocked, source). Internal suppression list also honored here."""
    sb = get_client()
    rows = (
        sb.table("dnc_cache")
        .select("source,expires_at")
        .eq("phone_e164", phone_e164)
        .execute()
        .data
        or []
    )
    if not rows:
        return False, None
    # Any non-expired row blocks.
    return True, rows[0]["source"]


def add_to_internal_suppression(phone_e164: str, *, reason: str) -> None:
    sb = get_client()
    sb.table("dnc_cache").upsert(
        {
            "phone_e164": phone_e164,
            "source": "internal_suppression",
            "reason": reason,
        },
        on_conflict="phone_e164,source",
    ).execute()
