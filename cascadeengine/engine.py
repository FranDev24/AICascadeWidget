# -*- coding: utf-8 -*-
"""CascadeEngine â€” nucleo async sin bloquear el event loop (httpx)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import httpx

logger = logging.getLogger("cascadeengine")

# ------------------------------------------------------------------- breaker
class CircuitBreakerState(str, Enum):
    """Estados del disyuntor por proveedor (Hystrix-style)."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

BreakerState = CircuitBreakerState  # alias retro-compatible


class CircuitBreaker:
    """Disyuntor independiente por proveedor. Thread/asyncio-safe."""

    def __init__(self, name: str, failure_threshold: int = 3,
                 recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = max(1, int(failure_threshold))
        self.recovery_timeout = float(recovery_timeout)
        self.state = CircuitBreakerState.CLOSED
        self.failure_count: int = 0
        self.last_error: Optional[str] = None
        self.opened_at: Optional[float] = None
        self._probe_inflight = False
        self._lock = threading.Lock()

    # --- con tenencia de eventos ------------------------------
    def _now(self) -> float:
        return time.monotonic()

    def allow(self) -> bool:
        """Puede el proveedor recibir trafico AHORA? (transicion OPEN->HALF_OPEN)."""
        with self._lock:
            if self.state is CircuitBreakerState.OPEN:
                if self.opened_at is not None and \
                        (self._now() - self.opened_at) >= self.recovery_timeout:
                    # sonda de recuperacion: un solo intento a la vez
                    if not self._probe_inflight:
                        self._probe_inflight = True
                        self.state = CircuitBreakerState.HALF_OPEN
                        logger.info("[CB] %s: OPEN -> HALF_OPEN (sonda)",
                                    self.name)
                        return True
                    return False
                return False
            if self.state is CircuitBreakerState.HALF_OPEN:
                if not self._probe_inflight:
                    self._probe_inflight = True
                    return True
                return False
            return True  # CLOSED

    def record_success(self) -> None:
        with self._lock:
            self.failure_count = 0
            self.last_error = None
            self.opened_at = None
            self._probe_inflight = False
            if self.state is not CircuitBreakerState.CLOSED:
                logger.info("[CB] %s HALF_OPEN -> CLOSED (recuperado)",
                            self.name)
            self.state = CircuitBreakerState.CLOSED

    def record_failure(self, error: Optional[str] = None) -> None:
        with self._lock:
            self.failure_count += 1
            self.last_error = error[:200] if error else None
            self._probe_inflight = False  # la sonda termino (bien o mal)
            if self.state is CircuitBreakerState.HALF_OPEN:
                # la sonda fallo: re-abrir el circuito
                self.state = CircuitBreakerState.OPEN
                self.opened_at = self._now()
                logger.info("[CB] %s: HALF_OPEN -> OPEN (sonda fallo)",
                            self.name)
            elif self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.opened_at = self._now()
                logger.info("[CB] %s: CLOSED -> OPEN (%d fallos, cooldown %.0fs)",
                            self.name, self.failure_count, self.recovery_timeout)

    def reset(self) -> None:
        """Restablece el disyuntor a estado limpio (CLOSED)."""
        with self._lock:
            self.failure_count = 0
            self.state = CircuitBreakerState.CLOSED
            self.opened_at = None
            self._probe_inflight = False

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "state": self.state.value,
                "failures": self.failure_count,
                "last_error": self.last_error,
                "opened_at": self.opened_at,
            }


# ------------------------------------------------------------------- backoff
class Backoff:
    """Exponential backoff con FULL JITTER (Brooker 2015)."""

    def __init__(self, base_delay: float = 0.5, max_delay: float = 4.0):
        self.base_delay = float(base_delay)
        self.max_delay = float(max_delay)

    def delay(self, attempt: int) -> float:
        # full jitter: uniform(0, min(max, base * 2**attempt))
        ceiling = min(self.max_delay, self.base_delay * (2 ** max(0, attempt)))
        return random.uniform(0, ceiling)


# ------------------------------------------------------------------- result
@dataclass
class CascadeResult:
    ok: bool = True
    mode: str = "simulated"           # live | simulated
    provider: str = "simulated"
    model: str = "Cascade-Auto"
    response: str = ""
    attempts: List[Dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    breaker: Dict[str, Any] = field(default_factory=dict)
    hedge_cancelled: Optional[bool] = None  # True: el secundario fue cancelado en carrera


# ------------------------------------------------------------------- engine
_TRANSIENT_STATUS = {408, 425, 429, 500, 502, 503, 504}


class CascadeEngine:
    """Cascada de proveedores: google->groq->openrouter->openai->deepseek->ollama.

    async-no-bloqueante; circuit breaker por proveedor; 1 reintento con
    backoff+jitter ante 429/timeout; telemetria JSONL estructurada.
    """

    NAME = "cascadeengine"
    VERSION = "2.2.0"

    def __init__(self, base_dir: Optional[str] = None,
                 failure_threshold: int = 3, recovery_timeout: float = 30.0,
                 per_call_timeout: float = 8.0, ollama_timeout: float = 6.0,
                 timeout_provider: float = 8.0,
                 hedged: bool = True, hedge_delay: float = 0.8):
        self.base_dir = base_dir or os.getenv("AICASCADE_BASE_DIR") or os.getcwd()
        self.breakers: Dict[str, CircuitBreaker] = {}
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self.per_call_timeout = per_call_timeout
        self.ollama_timeout = ollama_timeout
        self.timeout_provider = timeout_provider
        # Hedged requests ("The Tail at Scale", Dean&Barroso 2013): lanzar el
        # secundario tras hedge_delay s. si el primario no aterriza; gana el
        # primero y se cancela el perdedor. AICASCADE_HEDGED=0 desactiva.
        self.hedging = hedged and os.getenv("AICASCADE_HEDGED", "1") != "0"
        self.hedge_delay = float(hedge_delay)
        self.backoff = Backoff(base_delay=0.5, max_delay=4.0)
        self._metrics_lock = threading.Lock()
        self._client: Optional[httpx.AsyncClient] = None
        # Proxy-first (LiteLLM gateway :4000): si esta vivo concentra la
        # cascada+cache+telemetria del proyecto hermano; si no, cadena directa.
        key_proxy = os.getenv("AICASCADE_PROXY_KEY", "sk-cascade-frandev-2026")
        self._chain: List[Dict[str, Any]] = [
            {"provider": "cascade-proxy", "kind": "openai-like",
             "base": "http://127.0.0.1:4000/v1", "model": "cascade-smart",
             "is_proxy": True, "key": key_proxy},
            {"provider": "google", "kind": "google",
             "model": "gemini-1.5-flash"},
            {"provider": "groq", "kind": "openai-like", "base": "https://api.groq.com/openai/v1",
             "model": "openai/gpt-oss-120b"},
            {"provider": "openrouter", "kind": "openai-like", "base": "https://openrouter.ai/api/v1",
             "model": "nvidia/nemotron-3-ultra-550b-a55b:free"},
            {"provider": "openai", "kind": "openai-like", "base": "https://api.openai.com/v1",
             "model": "gpt-4o-mini"},
            {"provider": "deepseek", "kind": "openai-like", "base": "https://api.deepseek.com/v1",
             "model": "deepseek-chat"},
            {"provider": "ollama", "kind": "ollama", "base": "http://127.0.0.1:11434",
             "model": "llama3.1:8b"},
        ]

    # ---------------- infraestructura interna --------------------------
    def breaker(self, provider: str) -> CircuitBreaker:
        cb = self.breakers.get(provider)
        if cb is None:
            cb = CircuitBreaker(provider, self._failure_threshold,
                                self._recovery_timeout)
            self.breakers[provider] = cb
        return cb

    def reset_breakers(self) -> None:
        """[CB] Todos los circuit breakers reiniciados a CLOSEND (por SI TODO FALLA o reset API)."""
        for cb in self.breakers.values():
            cb.reset()
        logger.info("[CB] Todos los circuit breakers reiniciados (CLOSED).")

    @property
    def client(self):
        """httpx AsyncClient perezoso reutilizable (no bloquea el loop)."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout_provider)
        return self._client

    async def aclose(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    # ---------------- metricas JSONL -----------------------------------
    def _log_event(self, record: Dict[str, Any]) -> None:
        try:
            logs_dir = os.path.join(self.base_dir, "logs")
            os.makedirs(logs_dir, exist_ok=True)
            record["ts"] = datetime.now(timezone.utc).isoformat()
            record["engine"] = self.NAME
            line = json.dumps(record, ensure_ascii=False, default=str)
            with self._metrics_lock:
                with open(os.path.join(logs_dir, "engine_events.jsonl"),
                          "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except Exception as exc:      # telemetria jamas rompe el request
            logger.debug("metric jsonl fallo: %s", exc)

    # ---------------- llamadas por proveedor ---------------------------
    async def _call_google(self, kkey: str, model: str, prompt: str,
                           max_tokens: int) -> str:
        base = "https://generativelanguage.googleapis.com/v1beta/models"
        url = f"{base}/{model}:generateContent"
        r = await self.client.post(
            url,
            params={"key": kkey},
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": max_tokens}})
        r.raise_for_status()
        j = r.json()
        return str(j["candidates"][0]["content"]["parts"][0]["text"])

    async def _call_oai(self, base: str, kkey: str, model: str,
                        prompt: str, max_tokens: int) -> str:
        r = await self.client.post(f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {kkey}"},
            json={"model": model, "max_tokens": max_tokens, "temperature": 0.7,
                  "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        j = r.json()
        return str(j["choices"][0]["message"]["content"])

    async def _call_ollama(self, model: str, prompt: str) -> str:
        r = await self.client.post("http://127.0.0.1:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False})
        r.raise_for_status()
        j = r.json()
        return str(j.get("response", ""))

    async def _ollama_alive(self, probe_timeout: float = 0.35) -> bool:
        """Healthcheck barato de ollama (SRE: health-check antes de invocar)."""
        try:
            r = await asyncio.wait_for(
                self.client.get("http://127.0.0.1:11434/api/version"),
                timeout=probe_timeout)
            return r.status_code == 200
        except Exception:
            return False

    async def _attempt(self, spec: Dict[str, Any], kkey: Optional[str],
                       prompt: str, model_hint: Optional[str],
                       max_tokens: int) -> str:
        kind = spec["kind"]
        model = spec["model"]
        if kind == "google":
            return await self._call_google(kkey or "", model, prompt, max_tokens)
        if kind == "openai-like":
            return await self._call_oai(spec["base"], kkey or "", model, prompt, max_tokens)
        return await self._call_ollama(model, prompt)

    # ---------------- orquestacion ------------------------------------
    async def _proxy_alive(self, probe_timeout: float = 0.40) -> bool:
        """El gateway LiteLLM (:4000) responde? (health-check proactiva)."""
        try:
            r = await asyncio.wait_for(
                self.client.get("http://127.0.0.1:4000/health/liveliness"),
                timeout=probe_timeout)
            return r.status_code == 200
        except Exception:
            return False

    async def _available(self, spec: Dict[str, Any],
                         key: Optional[str]) -> (bool, Optional[str]):  # type: ignore[name-defined]
        """Pre-chequeos sin costo de breaker: clave, probe de ollama y del proxy."""
        provider = spec["provider"]
        if spec.get("is_proxy"):
            if not await self._proxy_alive():
                return False, "proxy_offline"
            return True, None
        if provider != "ollama" and not key:
            return False, None  # sin key NO es fallo del proveedor
        if provider == "ollama" and not await self._ollama_alive():
            return False, "ollama_offline"
        return True, None

    async def _call_once(self, spec: Dict[str, Any], key: Optional[str],
                         prompt: str, model_hint: Optional[str],
                         max_tokens: int) -> (str, Optional[str], Optional[int]):  # type: ignore[name-defined]
        """1 intento unico (sin retry) para uso en hedging/streams."""
        timeout = self.ollama_timeout if spec["provider"] == "ollama" else \
            self.per_call_timeout
        try:
            reply = await asyncio.wait_for(
                self._attempt(spec, key, prompt, model_hint, max_tokens),
                timeout=timeout)
            return reply, None, None
        except Exception as exc:  # noqa: BLE001
            err = str(exc)[:280]
            status = getattr(exc, "response", None) and \
                getattr(exc.response, "status_code", None)
            return "", err, status

    async def _attempt_with_retry(self, spec: Dict[str, Any], key: Optional[str],
                                  prompt: str, model_hint: Optional[str],
                                  max_tokens: int, call_id: str,
                                  t0: float) -> (Optional[str], Optional[str], Optional[int]):  # type: ignore[name-defined]
        """Intento con 1 reintento transitorio backoff (secuencia clasica)."""
        ok_reply: Optional[str] = None
        err: Optional[str] = None
        status: Optional[int] = None
        attempt_no = 0
        for attempt_no in (0, 1):
            reply, e, s = await self._call_once(spec, key, prompt,
                                                model_hint, max_tokens)
            ok_reply, err, status = (reply or None), e, s
            if ok_reply is not None or err is None:
                break
            exc_type = ""
            # SRE Book (cap.22): reintentar SOLO fallas transitorias;
            # conexion rota -> fallback directo para no paginar latencia.
            transient = (status in _TRANSIENT_STATUS if status is not None
                         else ("timeout" in str(e).lower()))
            if attempt_no == 0 and transient:
                delay = self.backoff.delay(attempt_no)
                self._log_event({"event": "retry", "call_id": call_id,
                                 "provider": spec["provider"], "error": err,
                                 "delay_s": round(delay, 2),
                                 "status_code": status})
                await asyncio.sleep(delay)
                continue
            break
        return ok_reply, err, status

    async def _hedged_race(self, primary: Dict[str, Any], secondary: Dict[str, Any],
                           key_p: Optional[str], key_s: Optional[str],
                           prompt: str, model_hint: Optional[str],
                           max_tokens: int) -> Dict[str, Any]:
        """Carrera hedged (Dean&Barroso, The Tail at Scale 2013):
        primario corre ya; si no aterriza en hedge_delay s. se lanza el
        secundario; el primero en SER bien gana y el otro se cancela.
        Solo re-intentamos/transient no aplica: cada participante corre 1 vez.

        Devuelve: {'winner': spec|None, 'reply', 'latency_ms',
                   'outcome': [{provider,error,status_code,latency_ms}]}
        El breaker NO se toca aqui; el orquestador lo hace con outcome."""
        t_start = time.monotonic()
        call_id = uuid.uuid4().hex[:8]
        outcome: List[Dict[str, Any]] = []

        async def run(spec, key):
            try:
                reply, err, status = await self._call_once(
                    spec, key, prompt, model_hint, max_tokens)
                return spec, reply, err, status
            except asyncio.CancelledError:
                # perdedor de la carrera: no es deproveedor con falla
                return spec, None, "hedged_cancelled", None
            except Exception as exc:  # por si _call_once explota fuera
                return spec, None, str(exc)[:200], None

        prim_task = asyncio.create_task(run(primary, key_p))
        sec_task: Optional[asyncio.Task] = None

        async def arm():
            await asyncio.sleep(self.hedge_delay)
            return await run(secondary, key_s)

        arm_task = asyncio.create_task(arm())
        winner = None
        reply = err = status = None
        while True:
            done, _ = await asyncio.wait((prim_task, arm_task),
                                         return_when=asyncio.FIRST_COMPLETED)
            for done_task in done:
                if done_task.done():
                    try:
                        spec, rreply, eerr, sst = done_task.result()
                    except (asyncio.CancelledError, Exception):  # noqa: PERF203
                        continue
                    if (eerr is None and rreply) and winner is None:
                        winner, reply, status = spec, rreply, sst
                    else:
                        outcome.append({"provider": spec["provider"],
                                        "error": eerr or "hedged_cancelled",
                                        "status_code": sst,
                                        "latency_ms": 0.0,
                                        "cancelled": eerr == "hedged_cancelled"})
            if winner is not None:
                # perdedor de la carrera: cancelar lo que siga corriendo
                for t in (prim_task, arm_task):
                    if not t.done():
                        t.cancel()
                break
            if all(t.done() for t in (prim_task, arm_task)):
                break
        lat = round((time.monotonic() - t_start) * 1000, 1)
        return {"winner": winner, "reply": reply, "err": err,
                "status": status, "latency_ms": lat, "outcome": outcome,
                "call_id": call_id}

    async def chat(self, message: str,
                   key_lookup: Callable[[str], Optional[str]] = lambda p: None,
                   model_hint: Optional[str] = None,
                   max_tokens: int = 512,
                   total_budget: float = 20.0) -> CascadeResult:
        """Ejecuta la cadena de failovers hasta lograr respuesta live o simulada."""
        t_start = time.monotonic()
        deadline = t_start + float(total_budget)
        call_id = uuid.uuid4().hex[:8]
        attempts: List[Dict[str, Any]] = []

        cands: List[tuple[Dict[str, Any], Optional[str]]] = []
        for spec in self._chain:
            key = key_lookup(spec["provider"]) if not spec.get("is_proxy") \
                else spec.get("key")
            ok, skip_err = await self._available(spec, key)
            if not ok:
                if skip_err:
                    attempts.append({"provider": spec["provider"],
                                     "error": skip_err, "latency_ms": 0})
                continue
            cands.append((spec, key))

        async def race_to_result(spec, key):
            """Corre attempt-with-retry y actualiza breaker/attempts/logs."""
            cb = self.breaker(spec["provider"])
            t0 = time.monotonic()
            reply, err, status = await self._attempt_with_retry(
                spec, key, message, model_hint, max_tokens, call_id, t0)
            lat = round((time.monotonic() - t0) * 1000, 1)
            if reply is not None:
                cb.record_success()
                self._log_event({"event": "chat", "call_id": call_id,
                                 "provider": spec["provider"],
                                 "model": spec["model"], "latency_ms": lat,
                                 "status_code": status, "hedged": self.hedging})
                return CascadeResult(
                    ok=True, mode="live", provider=spec["provider"],
                    model=spec["model"], response=reply, attempts=attempts,
                    latency_ms=lat,
                    breaker={p: c.snapshot()["state"]
                             for p, c in self.breakers.items()})
            cb.record_failure(err)
            attempts.append({"provider": spec["provider"], "error": err,
                             "latency_ms": lat, "status_code": status})
            self._log_event({"event": "fallback", "call_id": call_id,
                             "provider": spec["provider"], "error": err,
                             "latency_ms": lat, "status_code": status,
                             "hedged": self.hedging})
            return None

        idx = 0
        while idx < len(cands):
            spec, key = cands[idx]
            remain = deadline - time.monotonic()
            if remain <= 0.3:
                self._log_event({"event": "budget_exhausted",
                                 "call_id": call_id,
                                 "provider": spec["provider"]})
                break
            if not self.breaker(spec["provider"]).allow():
                attempts.append({"provider": spec["provider"],
                                 "error": "circuit_breaker_open",
                                 "latency_ms": 0})
                idx += 1
                continue
            # ---- HEDGING: primario + secundario compiten (2 slots) ----
            if self.hedging and idx + 1 < len(cands):
                sec, key_s = cands[idx + 1]
                race = await self._hedged_race(spec, sec, key, key_s,
                                               message, model_hint, max_tokens)
                # book-keeping exacto: 1 registro por participante, en orden
                for part in race["outcome"]:
                    pe = part.get("error")
                    if part.get("cancelled"):
                        # no enoja al breaker: no fue culpa del proveedor
                        attempts.append({"provider": part["provider"],
                                         "error": "hedged_cancelled",
                                         "latency_ms": 0})
                        self._log_event({"event": "hedged_cancelled",
                                         "call_id": call_id,
                                         "provider": part["provider"]})
                        continue
                    ask = part.get("latency_ms") or race.get("latency_ms", 0)
                    attempts.append({"provider": part["provider"],
                                     "error": pe, "latency_ms": ask,
                                     "status_code": part.get("status_code")})
                if race["winner"] is not None:
                    cbw = self.breaker(race["winner"]["provider"])
                    cbw.record_success()
                    lat = race.get("latency_ms", 0.0)
                    self._log_event({"event": "chat", "call_id": call_id,
                                     "provider": race["winner"]["provider"],
                                     "model": race["winner"].get("model"),
                                     "latency_ms": lat, "hedged": True})
                    return CascadeResult(
                        ok=True, mode="live",
                        provider=race["winner"]["provider"],
                        model=race["winner"].get("model"), response=race["reply"],
                        attempts=attempts, latency_ms=lat,
                        breaker={p: c.snapshot()["state"]
                                 for p, c in self.breakers.items()},
                        hedge_cancelled=any(part.get("error") == "CancelledError"
                                            for part in race["outcome"]))
                for part in race["outcome"]:
                    if part.get("cancelled"):
                        continue
                    if part.get("error"):
                        cbp = self.breaker(part["provider"])
                        cbp.record_failure(part["error"])
                        self._log_event({"event": "fallback", "call_id": call_id,
                                         "provider": part["provider"],
                                         "error": part["error"],
                                         "status_code": part.get("status_code"),
                                         "hedged": True})
                idx += 2  # se consumieron dos slots de la cadena
                continue
            r = await race_to_result(spec, key)
            if r:
                return r
            idx += 1

        # ------- Fallback simulado determinista (nunca rompe al HUD) -------
        lat = round((time.monotonic() - t_start) * 1000, 1)
        tally = {p: c.snapshot()["state"] for p, c in self.breakers.items()}
        reply = ("[SIMULADO - agrega keys en el Vault: google/groq/openai/"
                 "deepseek/openrouter]\n\n" + "Recibido: " + message[:200])
        self._log_event({"event": "simulated", "call_id": call_id,
                         "providers_tried": attempts, "latency_ms": lat})
        return CascadeResult(ok=True, mode="simulated", provider="simulated",
                             model=model_hint or "Cascade-Auto", response=reply,
                             attempts=attempts, latency_ms=lat, breaker=tally)

    # ---------------- streaming SSE ------------------------------------
    async def _stream_openai_sse(self, base: str, kkey: str, model: str,
                                 prompt: str, max_tokens: int):
        headers = {"Authorization": f"Bearer {kkey}"}
        body = {"model": model, "max_tokens": max_tokens, "temperature": 0.7,
                "stream": True,
                "messages": [{"role": "user", "content": prompt}]}
        async with self.client.stream("POST", f"{base}/chat/completions",
                                      headers=headers, json=body) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    return
                try:
                    chunk = json.loads(raw)
                    delta = (chunk.get("choices") or [{}])[0].get("delta", {}) \
                        .get("content")
                    if delta:
                        yield str(delta)
                except Exception:
                    continue

    async def _stream_google_sse(self, kkey: str, model: str, prompt: str,
                                 max_tokens: int):
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model}:streamGenerateContent?alt=sse")
        async with self.client.stream(
                "POST", url, params={"key": kkey},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"maxOutputTokens": max_tokens}}) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line or not line.startswith("data:"):
                    continue
                try:
                    chunk = json.loads(line[5:].strip())
                    parts = (chunk.get("candidates") or [{}])[0].get("content", {}) \
                        .get("parts", [])
                    text = "".join(p.get("text", "") for p in parts
                                   if isinstance(p, dict))
                    if text:
                        yield text
                except Exception:
                    continue

    async def _stream_ollama(self, model: str, prompt: str):
        async with self.client.stream(
                "POST", "http://127.0.0.1:11434/api/generate",
                json={"model": model, "prompt": prompt, "stream": True}) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                    piece = chunk.get("response") or ""
                    if piece:
                        yield piece
                    if chunk.get("done"):
                        return
                except Exception:
                    continue

    async def _stream_attempt(self, spec: Dict[str, Any], kkey: Optional[str],
                              prompt: str, model_hint: Optional[str],
                              max_tokens: int):
        kind = spec["kind"]
        if kind == "google":
            agen = self._stream_google_sse(kkey or "", spec["model"], prompt,
                                           max_tokens)
        elif kind == "openai-like":
            agen = self._stream_openai_sse(spec["base"], kkey or "",
                                           spec["model"], prompt, max_tokens)
        else:
            agen = self._stream_ollama(spec["model"], prompt)
        async for delta in agen:
            yield delta

    async def stream_chat(self, message: str,
                          key_lookup: Callable[[str], Optional[str]] = lambda p: None,
                          model_hint: Optional[str] = None,
                          max_tokens: int = 512,
                          ttfb_timeout: float = 4.0):
        """Yields eventos: {'event':'start'|'delta'|'done'} con failover:
        si un proveedor tarda > ttfb_timeout en su primer delta o falla,
        pasa al siguiente; el ultimo recurso es 'simulated'."""
        t_start = time.monotonic()
        call_id = uuid.uuid4().hex[:8]
        yield {"event": "start", "call_id": call_id,
               "chain": [s["provider"] for s in self._chain if s["provider"] != "cascade-proxy"]}

        for spec in self._chain:
            provider = spec["provider"]
            key = spec.get("key") if spec.get("is_proxy") else key_lookup(provider)
            ok, skip_err = await self._available(spec, key)
            if not ok:
                continue
            if not self.breaker(provider).allow():
                self._log_event({"event": "fallback", "call_id": call_id,
                                 "provider": provider,
                                 "error": "circuit_breaker_open", "stream": True})
                continue

            t0 = time.monotonic()
            # Un solo HTTP: abrir generador una vez; primer delta con TTFB cap
            agen = self._stream_attempt(spec, key, message, model_hint,
                                        max_tokens)
            iter_ = agen.__aiter__()
            first = None
            try:
                first = await asyncio.wait_for(iter_.__anext__(),
                                               timeout=ttfb_timeout)
            except asyncio.CancelledError:
                await agen.aclose() if hasattr(agen, "aclose") else None
                raise
            except Exception:
                first = None
            if not first:
                try:
                    await agen.aclose()
                except Exception:
                    pass
                self.breaker(provider).record_failure("ttfb_timeout")
                self._log_event({"event": "fallback", "call_id": call_id,
                                 "provider": provider, "error": "ttfb_timeout",
                                 "latency_ms": round((time.monotonic() - t0) * 1000, 1),
                                 "stream": True})
                continue

            # primer delta exitoso: breaker OK y stream en camino
            self.breaker(provider).record_success()
            lat = round((time.monotonic() - t0) * 1000, 1)
            self._log_event({"event": "chat_stream", "call_id": call_id,
                             "provider": provider, "model": spec["model"],
                             "ttfb_ms": lat})
            yield {"event": "meta", "provider": provider, "model": spec["model"]}
            yield {"event": "delta", "provider": provider, "content": first}
            chars = len(first)
            try:
                async for delta in iter_:  # MISMO stream, sin re-conexion
                    if not delta:
                        continue
                    chars += len(delta)
                    yield {"event": "delta", "provider": provider,
                           "content": delta}
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # stream murio a mitad: entregar parcial
                self._log_event({"event": "stream_abort", "call_id": call_id,
                                 "provider": provider,
                                 "error": str(exc)[:200], "stream": True})
                yield {"event": "done", "provider": provider, "ok": False,
                       "partial": True, "chars": chars}
                return
            yield {"event": "done", "provider": provider, "ok": True,
                   "latency_ms": round((time.monotonic() - t_start) * 1000, 1),
                   "chars": chars}
            self._log_event({"event": "done", "call_id": call_id,
                             "provider": provider, "stream": True,
                             "latency_ms": round((time.monotonic() - t_start) * 1000, 1),
                             "chars": chars})
            return

        # fallback simulado
        reply = ("[SIMULADO - agrega keys en el Vault]\n\nRecibido: "
                 + message[:200])
        yield {"event": "meta", "provider": "simulated",
               "model": model_hint or "Cascade-Auto"}
        yield {"event": "delta", "provider": "simulated", "content": reply}
        self.breaker("simulated")  # crea snapshot si el HUD lo pide
        self._log_event({"event": "simulated", "call_id": call_id,
                         "stream": True,
                         "latency_ms": round((time.monotonic() - t_start) * 1000, 1)})
        yield {"event": "done", "provider": "simulated", "ok": True,
               "latency_ms": round((time.monotonic() - t_start) * 1000, 1),
               "chars": len(reply)}

    # ---------------- snapshot para /api/health ------------------------
    def snapshot(self) -> Dict[str, Any]:
        return {
            "engine": self.NAME,
            "version": self.VERSION,
            "providers": {name: cb.snapshot()
                          for name, cb in self.breakers.items()},
            "chain": [s["provider"] for s in self._chain],
        }

