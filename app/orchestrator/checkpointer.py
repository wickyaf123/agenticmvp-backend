"""LangGraph Postgres checkpointer wired to the Supabase database.

The checkpointer auto-creates its tables (`checkpoints`, `checkpoint_blobs`,
`checkpoint_writes`) on first `setup()`. Call `bootstrap_checkpointer()` once
at app startup.
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

logger = logging.getLogger(__name__)

_DSN_ENV = "ORCHESTRATOR_PG_DSN"  # postgresql://... pooled Supabase connection


def _dsn() -> str:
    dsn = os.getenv(_DSN_ENV)
    if not dsn:
        raise RuntimeError(
            f"{_DSN_ENV} is not set. Use the Supabase **pooled** connection string."
        )
    return dsn


@asynccontextmanager
async def open_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    """Open an async checkpointer for one graph invocation.

    Use one short-lived saver per request; the connection pool handles reuse.
    """
    async with AsyncPostgresSaver.from_conn_string(_dsn()) as saver:
        yield saver


async def bootstrap_checkpointer() -> None:
    """Run idempotent migrations for the checkpointer tables.

    Safe to call on every boot.
    """
    async with AsyncPostgresSaver.from_conn_string(_dsn()) as saver:
        await saver.setup()
    logger.info("LangGraph Postgres checkpointer migrated.")
