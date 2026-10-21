# -*- coding: utf-8 -*-
"""
cascadeengine.core.circuit_breaker — Disyuntor (Hystrix/Azure patterns).

DELEGA a cascadeengine.core.module -> cascadeengine.engine (una sola
implementacion real, testeada). Aqui solo viven los alias/compat:
  - CircuitState  (alias de CircuitBreakerState: CLOSED/OPEN/HALF_OPEN)
  - AsyncCircuitBreaker (facade async sobre CircuitBreaker thread-safe)
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

import cascadeengine  # noqa: F401  (asegura import del motor completo)
from cascadeengine.engine import CircuitBreaker, CircuitBreakerState

# Alias canonico usado por el resto del proyecto
CircuitState = CircuitBreakerState
CircuitBreakerState = CircuitBreakerState  # alias explícito
BreakerState = CircuitBreakerState


class AsyncCircuitBreaker:
    """
    Facade async del disyuntor (sin duplicar logica interna).

    Uso:
        cb = AsyncCircuitBreaker("groq", failure_threshold=3, recovery_timeout=30)
        if await cb.allow():
            try: ... ; await cb.record_success()
            except: await cb.record_failure(exc)
    """

    def __init__(self, name: str, failure_threshold: int = 3,
                 recovery_timeout: float = 30.0,
                 open_error: bool = False):
        self._cb = CircuitBreaker(name, failure_threshold, recovery_timeout)
        self._open_error = bool(open_error)

    @property
    def state(self) -> CircuitBreakerState:
        return self._cb.state

    @property
    def failure_count(self) -> int:
        return self._cb.failure_count

    async def allow(self) -> bool:
        """Tiene trafico el proveedor? Si open_error=True lanza CircuitOpenError."""
        await asyncio.sleep(0)  # cede el loop (compat async estricta)
        can = self._cb.allow()
        if not can and self._open_error:
            from cascadeengine.core.module import CircuitOpenError
            raise CircuitOpenError(self._cb.name, self._cb.recovery_timeout)
        return can

    async def record_success(self) -> None:
        self._cb.record_success()

    async def record_failure(self, error: Optional[str] = None) -> None:
        self._cb.record_failure(error)

    def reset(self) -> None:
        self._cb.reset()

    def snapshot(self) -> dict:
        return self._cb.snapshot()
