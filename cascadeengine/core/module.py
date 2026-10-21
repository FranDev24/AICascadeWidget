# -*- coding: utf-8 -*-
"""
cascadeengine.core.module — API "core" del motor (compatibilidad Cline).

DELEGA a cascadeengine.engine (implementacion real testeada: 17 checks).
Mantiene la nomenclatura core (CircuitState, MetricsRecorder, ...) usable
por cualquier parte del proyecto sin duplicar logica. Una sola fuente
de verdad: engine.py.
"""
from __future__ import annotations

import asyncio
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from cascadeengine.engine import (  # implementacion real
    Backoff,
    CascadeEngine as _EngineImpl,
    CascadeResult,
    CircuitBreaker as _CBImpl,
    CircuitBreakerState,
)

# ------------------------------------------------------------------ alias
CircuitState = CircuitBreakerState
BreakerState = CircuitBreakerState
BackoffJitter = Backoff


class CircuitOpenError(RuntimeError):
    """El circuito esta OPEN: el proveedor NO puede recibir trafico ahora."""
    def __init__(self, provider: str, cooldown: float = 0.0):
        self.provider = provider
        self.cooldown = cooldown
        super().__init__(
            f"Circuit OPEN para '{provider}' (cooldown {cooldown:.0f}s). "
            "Usa otra via de la cascada o espera a HALF_OPEN.")


# ------------------------------------------------------------- utilidades
def generate_request_id() -> str:
    return uuid.uuid4().hex[:8]


def exponential_backoff_with_jitter(attempt: int, base_delay: float = 0.5,
                                    max_delay: float = 4.0) -> float:
    """Full jitter (Brooker/AWS 2015): delay uniforme en [0, base*2^attempt]."""
    ceiling = min(max_delay, base_delay * (2 ** max(0, attempt)))
    import random
    return random.uniform(0, ceiling)


async def retry_with_backoff(coro_factory: Callable[[], Any], attempts: int = 2,
                             base_delay: float = 0.5, max_delay: float = 4.0,
                             transient_check: Optional[Callable[[Exception], bool]] = None):
    """Reejecuta coro_factory con backoff+jitter si el error es transitorio.

    No re-propaga CancelledError (BaseException); pasa otros errores."""
    func_delay = exponential_backoff_with_jitter
    exc: Optional[BaseException] = None
    for att in range(max(1, attempts)):
        try:
            return await coro_factory()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            exc = e
            if att == attempts - 1:
                raise
            if transient_check is not None and not transient_check(e):
                raise
            await asyncio.sleep(func_delay(att))
    raise exc  # pragma: no cover


# ------------------------------------------------------------ dataclasses
@dataclass
class CircuitBreakerConfig:
    """Config declarativa de un disyuntor (nombre + umbrales)."""
    name: str
    failure_threshold: int = 3
    recovery_timeout: float = 30.0

    def build(self) -> _CBImpl:
        return _CBImpl(self.name, self.failure_threshold, self.recovery_timeout)


@dataclass
class CallContext:
    """Contexto de una invocacion chat (telemetria/orquestacion)."""
    request_id: str = field(default_factory=generate_request_id)
    message: str = ""
    model_hint: Optional[str] = None
    max_tokens: int = 512
    total_budget: float = 20.0


@dataclass
class CallMetrics:
    """KPI de una respuesta (por evento chat/fallback)."""
    provider: str
    latency_ms: float = 0.0
    status_code: Optional[int] = None
    error: Optional[str] = None
    hedged: bool = False


class MetricsRecorder:
    """Grabador de eventos JSONL fuera del request (auditoria/CLI).

    Escribe en <base_dir>/logs/engine_events.jsonl con la misma esquema
    del engine. Operacion a prueba de fallos: nunca explota."""
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.getcwd()
        os.makedirs(os.path.join(self.base_dir, "logs"), exist_ok=True)
        self._lock = threading.Lock()

    def _path(self) -> str:
        import datetime as dt
        return os.path.join(self.base_dir, "logs",
                            "engine_%s.jsonl" % (dt.datetime.now().strftime("%Y%m%d")))

    def event(self, kind: str, **payload: Any):
        import datetime as dt
        import json
        rec = {"event": kind, **payload,
               "ts": dt.datetime.now().isoformat(timespec="milliseconds")}
        try:
            with self._lock:
                with open(self._path(), "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass


# core.CascadeEngine / core.CircuitBreaker / core.CascadeResult: alias directos
CascadeEngine = _EngineImpl
CircuitBreaker = _CBImpl
CascadeResult = CascadeResult  # noqa: transparencia explícita
