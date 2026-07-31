"""Base classes for orchestrator tools.

Usage:

    class MyToolInput(BaseModel):
        x: int

    class MyToolOutput(BaseModel):
        y: int

    class MyTool(Tool[MyToolInput, MyToolOutput]):
        name = "my.tool"
        InputModel = MyToolInput
        OutputModel = MyToolOutput

        async def _call(self, payload: MyToolInput) -> MyToolOutput:
            return MyToolOutput(y=payload.x * 2)

    result = await MyTool().invoke({"x": 21})  # auto-validates, retries, breaks
"""
from __future__ import annotations

import logging
import time
from typing import Any, ClassVar, Generic, TypeVar

import pybreaker
from pydantic import BaseModel, ValidationError
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.orchestrator.runs import emit_event

logger = logging.getLogger(__name__)

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)

# One breaker per tool name; lazy-created on first invocation.
_BREAKERS: dict[str, pybreaker.CircuitBreaker] = {}


def _breaker_for(name: str) -> pybreaker.CircuitBreaker:
    if name not in _BREAKERS:
        _BREAKERS[name] = pybreaker.CircuitBreaker(
            fail_max=5, reset_timeout=60, name=name
        )
    return _BREAKERS[name]


class ToolError(Exception):
    """Raised when a tool fails after retries or while the breaker is open."""


class Tool(Generic[I, O]):
    name: ClassVar[str] = "tool.unspecified"
    InputModel: ClassVar[type[BaseModel]]
    OutputModel: ClassVar[type[BaseModel]]

    # Tunable per-tool. Override in subclasses.
    max_attempts: ClassVar[int] = 3
    retry_min_seconds: ClassVar[float] = 0.5
    retry_max_seconds: ClassVar[float] = 8.0
    retry_on: ClassVar[tuple[type[BaseException], ...]] = (Exception,)

    async def _call(self, payload: I) -> O:  # pragma: no cover - abstract
        raise NotImplementedError

    async def invoke(self, raw_input: dict[str, Any], *, run_id: str | None = None) -> O:
        try:
            payload: I = self.InputModel.model_validate(raw_input)  # type: ignore[assignment]
        except ValidationError as ve:
            emit_event(
                agent_id=None,
                event_type="tool_call",
                payload={
                    "tool": self.name,
                    "run_id": run_id,
                    "ok": False,
                    "error": "input_validation",
                    "detail": ve.errors(),
                },
            )
            raise

        breaker = _breaker_for(self.name)
        if breaker.current_state == pybreaker.STATE_OPEN:
            emit_event(
                agent_id=None,
                event_type="tool_circuit_open",
                payload={"tool": self.name, "run_id": run_id},
            )
            raise ToolError(f"Circuit open for tool {self.name}")

        started = time.monotonic()
        attempts = 0

        async def _attempt() -> O:
            nonlocal attempts
            attempts += 1
            result = await self._call(payload)
            try:
                # Validate the output too — catches drifting upstream contracts.
                return self.OutputModel.model_validate(result.model_dump())  # type: ignore[return-value]
            except ValidationError as ve:
                raise ToolError(f"Output validation failed for {self.name}: {ve}") from ve

        try:
            async for ctx in AsyncRetrying(
                stop=stop_after_attempt(self.max_attempts),
                wait=wait_exponential(
                    multiplier=self.retry_min_seconds, max=self.retry_max_seconds
                ),
                retry=retry_if_exception_type(self.retry_on),
                reraise=True,
            ):
                with ctx:
                    out = await breaker.call_async(_attempt)
                    emit_event(
                        agent_id=None,
                        event_type="tool_call",
                        payload={
                            "tool": self.name,
                            "run_id": run_id,
                            "ok": True,
                            "attempts": attempts,
                            "elapsed_ms": int((time.monotonic() - started) * 1000),
                        },
                    )
                    return out  # type: ignore[return-value]
        except RetryError as re:
            emit_event(
                agent_id=None,
                event_type="tool_call",
                payload={
                    "tool": self.name,
                    "run_id": run_id,
                    "ok": False,
                    "attempts": attempts,
                    "error": str(re),
                },
            )
            raise ToolError(f"{self.name} exhausted retries: {re}") from re
        except pybreaker.CircuitBreakerError as cb:
            emit_event(
                agent_id=None,
                event_type="tool_circuit_open",
                payload={"tool": self.name, "run_id": run_id, "error": str(cb)},
            )
            raise ToolError(f"Circuit breaker tripped for {self.name}") from cb

        raise ToolError(f"{self.name}: unreachable retry path")
