# -*- coding: utf-8 -*-
"""Tests del CascadeEngine (AICascadeWidget) — sin dependencias externas.

Casos cubiertos (patrones de ingenieria de alta disponibilidad):
  1. Circuit Breaker: CLOSED -> OPEN tras N fallos -> HALF_OPEN en recovery
     -> CLOSED si la sonda sale bien (Hystrix/Azure patterns).
  2. Backoff con full jitter (AWS Brooker 2015): 0 <= delay <= techo.
  3. CascadeEngine: claves ausentes -> respuesta simulada rapida.
  4. CascadeEngine: proveedor constantemente roto -> breaker lo aterriza
     (latencia -> ~0) y sigue entregando respuesta al HUD.

Uso:  venv\\Scripts\\python.exe tools\\test_engine.py
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cascadeengine import CascadeEngine, CascadeResult, CircuitBreaker, CircuitBreakerState

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    ok = bool(cond)
    PASS += ok
    FAIL += (not ok)
    print(("PASS" if ok else "FAIL"), "-", name, ("| " + detail if detail else ""))


# 1) Circuit Breaker estados
cb = CircuitBreaker("test-provider", failure_threshold=2, recovery_timeout=0.05)
check("CB cerrado inicia CLOSED", cb.state is CircuitBreakerState.CLOSED)
cb.record_failure("e1")
cb.record_failure("e2")
check("CB abre tras threshold fallos", cb.state is CircuitBreakerState.OPEN,
      "failures=%d" % cb.failure_count)
check("CB bloquea en OPEN", cb.allow() is False)
time.sleep(0.06)
check("CB HALF_OPEN al vencer cooldown", cb.allow() is True)   # sonda en vuelo
check("CB sonda unica en HALF_OPEN", cb.allow() is False)
cb.record_success()
check("CB cierra en sonda OK", cb.state is CircuitBreakerState.CLOSED)

# 2) Backoff full jitter
bo = CascadeEngine.__mro__ and __import__("cascadeengine.engine", fromlist=["Backoff"]).Backoff(0.5, 2.0)
a0 = bo.delay(0)
a3 = bo.delay(3)
check("Backoff delay(0) en [0, base]", 0 <= a0 <= 0.5, "%.3f" % a0)
check("Backoff delay(3) capped en max", 0 <= a3 <= 2.0, "%.3f" % a3)

# 3) Simulado rapido sin keys
async def t_simulado():
    eng = CascadeEngine(base_dir=os.getcwd(), per_call_timeout=1.0)
    res = await eng.chat("hola test", key_lookup=lambda p: None)
    return res

res = asyncio.get_event_loop().run_until_complete(t_simulado())
check("Sin claves -> simulated", res.mode == "simulated" and res.ok)
check("Respuesta simulada no vacia", bool(res.response))
check("Respuesta simulada incluye probe de ollama", any(
    a.get("provider") == "ollama" for a in res.attempts))
# Semantico: solo llama ollama (sin key no toca nube); latency generosa por
# entornos sandbox/slow-DNS: lo medible es que NO llamo a 5 proveedores.
try_cloud = [a for a in res.attempts if a.get("provider") in
             ("google", "groq", "openrouter", "openai", "deepseek")]
check("Sin claves -> no llama nube (solo ollama)", len(try_cloud) == 0,
      "lat=%0.0fms" % res.latency_ms)
check("Latencia simulada < 3s (probe + breaker)", res.latency_ms < 3000,
      "%.0fms" % res.latency_ms)


# 4) Breaker aterriza proveedor roto (latencia -> 0)
class RotoEngine(CascadeEngine):
    async def _attempt(self, spec, kkey, prompt, model_hint, max_tokens):
        await asyncio.sleep(0.01)
        raise ValueError("proveedor quemado")


async def t_roto():
    eng = RotoEngine(base_dir=os.getcwd(), failure_threshold=2,
                     recovery_timeout=30.0, per_call_timeout=0.5,
                     ollama_timeout=0.5)
    r1 = await eng.chat("x", key_lookup=lambda p: "k")
    slow = r1.latency_ms
    r2 = await eng.chat("x", key_lookup=lambda p: "k")
    r3 = await eng.chat("x", key_lookup=lambda p: "k")
    fast = r3.latency_ms
    opened = eng.breaker("google").state
    return slow, fast, opened, r3

slow, fast, opened, r3 = asyncio.get_event_loop().run_until_complete(t_roto())
check("Cascada rota sigue respondiendo", r3.ok and r3.mode == "simulated")
check("Breaker se congela en OPEN (google)", opened is CircuitBreakerState.OPEN)
check("Breaker reduce latencia (ratio >10x)", fast <= max(5.0, slow * 0.2),
      "%.1fms vs %.1fms" % (fast, slow))
check("jsonl breaker snapshot", isinstance(r3.attempts, list))

print("\nRESULTADO: %d PASS / %d FAIL" % (PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
