"""Agent nodes. Each module exports an `async def run(state, config) -> dict` callable.

Phase 0 ships only `noop`. Subsequent slices add real nodes.
"""
from app.orchestrator.nodes import noop  # noqa: F401

__all__ = ["noop"]
