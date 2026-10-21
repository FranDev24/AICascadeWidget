# -*- coding: utf-8 -*-
"""
CascadeEngine — motor de cascada IA (FranDev24 / AICascadeWidget).

Patrones clase mundial (compatibles con la literatura del dominio):
  - Circuit Breaker (Netflix Hystrix / MS Azure Cloud Design Patterns)
  - Exponential Backoff + Full Jitter (AWS/Brooker 2015, SRE Book cap.22)
  - LLM Cascade (FrugalGPT - Stanford 2023)

Regla del repo: engine.py es LA implementacion; los modulos de core/*
son compatibilidad de solo-alias. Este __init__ tiene FALLBACK defensivo:
si un submodulo core/* falta (edicion en curso), re-expone desde engine.py
para que la app NUNCA quede caida por un import.
"""
__version__ = '1.0.0'
__author__ = 'FranDev24'


def _imp(name, fallback=None):
    try:
        mod = __import__(name, fromlist=["*"])
        return mod
    except Exception:  # noqa: BLE001 - build en curso: degrade seguro
        return fallback


# ---- nomenclatura core (de Cline) con fallback a engine.py -------------
_m = _imp("cascadeengine.core.module")
if _m is None:
    from cascadeengine import engine as _m


def _attr(mod, name):
    return getattr(mod, name, None)


CascadeEngine = _attr(_m, "CascadeEngine")
CircuitBreaker = _attr(_m, "CircuitBreaker")
CircuitBreakerConfig = _attr(_m, "CircuitBreakerConfig")
CircuitOpenError = _attr(_m, "CircuitOpenError")
MetricsRecorder = _attr(_m, "MetricsRecorder")
generate_request_id = _attr(_m, "generate_request_id")
CallContext = _attr(_m, "CallContext")
CascadeResult = _attr(_m, "CascadeResult")
Backoff = _attr(_m, "Backoff")
BackoffJitter = _attr(_m, "BackoffJitter")

_m_backoff = _imp("cascadeengine.core.backoff", _m)
retry_with_backoff = _attr(_m_backoff, "retry_with_backoff")
exponential_backoff_with_jitter = _attr(_m_backoff, "exponential_backoff_with_jitter")

_m_cb = _imp("cascadeengine.core.circuit_breaker", _m)
CircuitState = _attr(_m_cb, "CircuitState")
AsyncCircuitBreaker = _attr(_m_cb, "AsyncCircuitBreaker")

# ---- HARD GATE: nombres esenciales obligatorios (fallo rapido y claro) ---
_from_engine = __import__("cascadeengine.engine", fromlist=["*"])
_required_map = {
    "CascadeEngine": CascadeEngine or _from_engine.CascadeEngine,
    "CascadeResult": CascadeResult or _from_engine.CascadeResult,
    "CircuitBreaker": CircuitBreaker or _from_engine.CircuitBreaker,
    "CircuitBreakerState": _from_engine.CircuitBreakerState,
    "CircuitState": CircuitState or _from_engine.CircuitBreakerState,
    "Backoff": Backoff or _from_engine.Backoff,
    "retry_with_backoff": retry_with_backoff or _from_engine.Backoff,
}
for _n, _v in _required_map.items():
    if _v is None:
        raise ImportError(f"cascadeengine: falta export esencial '{_n}'")
globals().update(_required_map)
if AsyncCircuitBreaker is None:
    from cascadeengine.core.circuit_breaker import AsyncCircuitBreaker  # reintent

__all__ = [
    '__version__', '__author__',
    'CascadeEngine', 'CascadeResult', 'CircuitBreaker', 'CircuitBreakerConfig',
    'CircuitOpenError', 'CircuitState', 'AsyncCircuitBreaker', 'MetricsRecorder',
    'generate_request_id', 'CallContext', 'Backoff', 'BackoffJitter',
    'retry_with_backoff', 'exponential_backoff_with_jitter',
    'CircuitBreakerState',
]
