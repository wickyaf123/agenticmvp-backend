"""Immutable consent log writer.

Every outbound contact must have a verifiable consent record. The consent_log
table has no UPDATE/DELETE policy for non-service roles, so writes are
append-only from the application layer.
"""
from __future__ import annotations

import hashlib
from typing import Iterable, Optional

from app.services.supabase_client import get_client


def record_consent(
    *,
    contact_value: str,
    consent_type: str,
    channels: Iterable[str],
    lead_id: Optional[str] = None,
    evidence_url: Optional[str] = None,
    evidence_text: Optional[str] = None,
    script_version: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> dict:
    sb = get_client()
    evidence_hash = (
        hashlib.sha256(evidence_text.encode("utf-8")).hexdigest()
        if evidence_text
        else None
    )
    row = {
        "contact_value": contact_value,
        "consent_type": consent_type,
        "channels": list(channels),
        "lead_id": lead_id,
        "evidence_url": evidence_url,
        "evidence_hash": evidence_hash,
        "script_version": script_version,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "jurisdiction": jurisdiction,
    }
    return sb.table("consent_log").insert(row).execute().data[0]


def has_consent(*, contact_value: str, channel: str) -> bool:
    sb = get_client()
    rows = (
        sb.table("consent_log")
        .select("channels")
        .eq("contact_value", contact_value)
        .execute()
        .data
        or []
    )
    return any(channel in (r.get("channels") or []) for r in rows)
