"""RQ worker bootstrap.

Run with:  rq worker --url $REDIS_URL orchestrator
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from redis import Redis
from rq import Queue

logger = logging.getLogger(__name__)

QUEUE_NAME = "orchestrator"


def _redis() -> Redis:
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    return Redis.from_url(url)


def queue() -> Queue:
    return Queue(QUEUE_NAME, connection=_redis())


def enqueue_run(run_type: str, payload: dict[str, Any], *, triggered_by: str | None = None) -> str:
    """Enqueue an orchestrator run; returns the RQ job id."""
    job = queue().enqueue(
        "app.queue.worker.execute_run",
        run_type,
        payload,
        triggered_by,
        result_ttl=3600,
        failure_ttl=86400,
        job_timeout=1800,
    )
    return job.id


def execute_run(run_type: str, payload: dict[str, Any], triggered_by: str | None) -> dict:
    """RQ job entrypoint. Bridges sync RQ -> async LangGraph executor."""
    from app.orchestrator.executor import start_run

    return asyncio.run(start_run(run_type=run_type, payload=payload, triggered_by=triggered_by))
