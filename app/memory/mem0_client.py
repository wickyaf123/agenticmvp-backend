"""mem0 client wired to the Supabase pgvector backend.

Application-level facts are also mirrored into the `memories` table so the
dashboard's Memory Inspector can display + correct them.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Iterable, Optional

from app.services.supabase_client import get_client

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _mem0():
    """Lazy import + lazy init so missing env doesn't crash app import."""
    from mem0 import Memory  # type: ignore

    config = {
        "vector_store": {
            "provider": "supabase",
            "config": {
                "connection_string": os.getenv("ORCHESTRATOR_PG_DSN"),
                "collection_name": "mem0_collection",
                "embedding_model_dims": int(os.getenv("MEM0_EMBED_DIMS", "1536")),
            },
        },
        "llm": {
            "provider": "google",
            "config": {
                "model": os.getenv("MEM0_LLM_MODEL", "gemini-2.5-flash"),
                "api_key": os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
            },
        },
        "embedder": {
            "provider": "google",
            "config": {
                "model": os.getenv("MEM0_EMBED_MODEL", "text-embedding-004"),
                "api_key": os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"),
            },
        },
    }
    return Memory.from_config(config)


def remember(
    *,
    namespace: str,
    entity_id: str,
    facts: Iterable[str],
    source_run_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> list[dict]:
    """Store one or more facts. Returns the inserted memory rows."""
    user_id = f"{namespace}:{entity_id}"
    inserted: list[dict] = []
    sb = get_client()
    for fact in facts:
        try:
            _mem0().add(fact, user_id=user_id, metadata=metadata or {})
        except Exception as exc:  # noqa: BLE001
            logger.warning("mem0 add failed (%s): %s", fact[:60], exc)
        row = {
            "namespace": namespace,
            "entity_id": entity_id,
            "fact": fact,
            "source_run_id": source_run_id,
            "metadata": metadata or {},
        }
        inserted.append(sb.table("memories").insert(row).execute().data[0])
    return inserted


def recall(
    *,
    namespace: str,
    entity_id: str,
    query: str,
    limit: int = 8,
) -> list[dict]:
    """Semantic recall scoped to namespace+entity."""
    user_id = f"{namespace}:{entity_id}"
    try:
        results = _mem0().search(query, user_id=user_id, limit=limit)
        return list(results.get("results", []))
    except Exception as exc:  # noqa: BLE001
        logger.warning("mem0 recall failed: %s", exc)
        return []
