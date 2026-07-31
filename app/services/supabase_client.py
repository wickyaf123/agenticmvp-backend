import os
import logging
from datetime import datetime, timezone
from typing import Any, Optional, TypedDict

from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
else:
    logger.warning(
        "[supabase] SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY missing — persistence disabled"
    )


def get_client() -> Client:
    """Return the configured Supabase client.

    The orchestrator requires Supabase to be configured. Raises if it isn't —
    failing fast at boot is preferable to silent no-ops in agent runs.
    """
    if supabase is None:
        raise RuntimeError(
            "Supabase client not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY before starting the orchestrator."
        )
    return supabase


class LeadInsert(TypedDict, total=False):
    name: str
    email: str
    projectIdea: Optional[str]
    budget: Optional[str]
    stage: Optional[str]
    timeline: Optional[str]
    source: Optional[str]


def insert_lead(lead: LeadInsert) -> dict:
    if not supabase:
        return {"skipped": True}
    try:
        response = (
            supabase.table("leads")
            .insert(
                {
                    "name": lead["name"],
                    "email": lead["email"],
                    "project_idea": lead.get("projectIdea"),
                    "budget": lead.get("budget"),
                    "stage": lead.get("stage"),
                    "timeline": lead.get("timeline"),
                    "source": lead.get("source"),
                }
            )
            .execute()
        )
        row_id = response.data[0]["id"] if response.data else None
        return {"skipped": False, "id": row_id}
    except Exception as e:
        logger.error("[supabase] insert_lead error: %s", e)
        return {"skipped": False, "error": str(e)}


class ContentUpsert(TypedDict, total=False):
    type: str
    slug: str
    title: str
    metaDescription: Optional[str]
    data: Any


def upsert_content_item(item: ContentUpsert) -> dict:
    if not supabase:
        return {"skipped": True}
    try:
        supabase.table("content_items").upsert(
            {
                "type": item["type"],
                "slug": item["slug"],
                "title": item["title"],
                "meta_description": item.get("metaDescription"),
                "data": item["data"],
                "status": "published",
                "published_at": datetime.now(timezone.utc).isoformat(),
            },
            on_conflict="type,slug",
        ).execute()
        return {"skipped": False}
    except Exception as e:
        logger.error("[supabase] upsert_content_item error: %s", e)
        return {"skipped": False, "error": str(e)}
