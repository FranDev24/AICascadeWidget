# ============================================================================
# cascade_manager.py - Motor de cascada mejorado para AICascadeWidget  (1/2)
# Usa el paquete cascadeengine/ (Circuit Breaker + Backoff + Metrics)
# ============================================================================

import logging
import hashlib
from typing import Optional, Dict, Any
from cascadeengine.core.circuit_breaker import CircuitOpenError
from cascadeengine.core.backoff import retry_with_backoff
from cascadeengine.core.metrics import MetricsRecorder, generate_request_id, CallContext

logger = logging.getLogger("aicascade.cascade")

__engine__: Optional["CascadeManager"] = None


class CascadeManager:
    """Gestor de cascada con Circuit Breaker, backoff y métricas."""

    def __init__(self, providers=None, config=None):
        self.providers = providers or {}
        self.config = config or {}
        self.metrics = MetricsRecorder()
        self.cache = {}
        self.cache_enabled = self.config.get("cache_enabled", True)
        self.cache_ttl = self.config.get("cache_ttl", 120)
        self.circuit_breakers = {}
        from cascadeengine.core.circuit_breaker import (
            CircuitBreakerConfig, CircuitState, CircuitBreaker
        )
        for name, prov in self.providers.items():
            cb_cfg = CircuitBreakerConfig(
                failure_threshold=prov.get("circuit_failure_threshold", 5),
                recovery_timeout=prov.get("circuit_recovery_timeout", 30.0),
                success_threshold=prov.get("circuit_success_threshold", 3),
                name=f"{name} ({prov.get('endpoint', name)})",
            )
            self.circuit_breakers[name] = CircuitBreaker(cb_cfg)
            logger.info(f"[CascadeManager] CB: {name}")

    def _make_cache_key(self, request_id, model, payload):
        raw = f"{request_id}:{model}:{payload}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _cache_get(self, request_id, model, payload):
        if not self.cache_enabled:
            return None
        key = self._make_cache_key(request_id, model, payload)
        if key in self.cache:
            self.metrics.record_cache_hit(request_id, model, self.cache_ttl)
            return self.cache[key]
        self.metrics.record_cache_miss(request_id, model)
        return None

    def _cache_set(self, request_id, model, response, payload=""):
        if not self.cache_enabled:
            return
        key = self._make_cache_key(request_id, model, payload)
        self.cache[key] = response
        if len(self.cache) > 10000:
            self.cache.clear()

    def invalidate_cache(self, model=None):
        if model:
            self.cache = {k: v for k, v in self.cache.items() if not k.endswith(model)}
        else:
            self.cache.clear()
    async def call_provider_with_retry(self, provider, model, payload,
                                        max_attempts=3, base_wait=1.0, max_wait=30.0):
        cb = self.circuit_breakers.get(provider)
        if cb is None:
            raise ValueError(f"Proveedor {provider} no registrado")
        async def _inner():
            if self.cache_enabled:
                cached = self._cache_get(generate_request_id(), model, payload)
                if cached:
                    return cached
            return await self._http_call(provider, model, payload)
        result = await retry_with_backoff(
            _inner, max_attempts=max_attempts, base_wait=base_wait,
            max_wait=max_wait, backoff_factor=2.0, jitter=0.1,
            logger_instance=logger,
            on_retry=lambda a, w, e: logger.warning(
                f"[CascadeManager] {provider}: {type(e).__name__} -- retry en {w:.1f}s"
            ),
        )
        if self.cache_enabled:
            self._cache_set(generate_request_id(), model, result, payload)
        return result

    async def _http_call(self, provider, model, payload):
        raise NotImplementedError("Subclase: implemente _http_call con la llamada real.")

    async def chat(self, model, user_message, provider_override=None):
        req_id = generate_request_id("cascade")
        context = CallContext(request_id=req_id, provider=provider_override or "default", model=model)
        self.metrics.start(context)
        try:
            provider = provider_override or self._pick_provider(model)
            result = await self.call_provider_with_retry(
                provider, model, user_message,
                max_attempts=3, base_wait=1.0, max_wait=10.0
            )
            self.metrics.end(context, success=True)
            return {"request_id": req_id, "provider": provider, **result}
        except CircuitOpenError as e:
            self.metrics.record_failure(context, e, http_status=None)
            raise
        except Exception as e:
            self.metrics.record_failure(context, e)
            raise

    def _pick_provider(self, model):
        for name, prov in self.providers.items():
            if prov.get("default_for") and model in prov["default_for"]:
                return name
        return list(self.providers.keys())[0] if self.providers else "default"

    def reset_circuit_breaker(self, provider=None):
        if provider:
            if provider in self.circuit_breakers:
                cb = self.circuit_breakers[provider]
                cb.state = cb.CircuitState.CLOSED
                cb.failure_count = 0
                logger.info(f"[CB] {provider} reiniciado (CLOSED)")
        else:
            for cb in self.circuit_breakers.values():
                cb.state = cb.CircuitState.CLOSED
                cb.failure_count = 0
            logger.info("[CB] Todos los circuit breakers reiniciados")


def get_engine():
    if __engine__ is None:
        raise RuntimeError("CascadeManager no inicializado.")
    return __engine__


def inicializar(providers, config=None):
    global __engine__
    __engine__ = CascadeManager(providers=providers, config=config or {})
    return __engine__

