"""Typed tool layer for orchestrator nodes.

Every external integration goes through `tools.base.Tool` so we get:
- Pydantic-validated input/output
- Tenacity retry with backoff (L1)
- pybreaker circuit breaker per tool
- Uniform tool_call event emission
"""
