#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AICascade Widget - Backend FastAPI con Supabase Y SQLite.
Estrategia: Supabase primero; si falla (RLS/red/tabla faltante) -> SQLite local
(aicascade.db, base persistente creada automaticamente). La UI esta servida
por este mismo servidor: http://127.0.0.1:8000
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import uvicorn

import db as sq
import cascadeengine as _engine

load_dotenv()
logging.basicConfig(level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("aicascade-backend")


def _placeholder(v: Optional[str]) -> bool:
    if not v:
        return True
    v = v.strip().lower()
    return ("your-" in v or "tu-proyecto" in v or "here" in v
            or "your-project-ref" in v)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                or os.getenv("SUPABASE_ANON_KEY") or os.getenv("SUPABASE_KEY"))

supabase = None
if not _placeholder(SUPABASE_URL) and not _placeholder(SUPABASE_KEY):
    try:
        import socket
        _host = SUPABASE_URL.split("//", 1)[1].split("/", 1)[0]
        socket.gethostbyname(_host)  # valida DNS: proyecto eliminado -> fallback SQLite limpio
        from supabase import create_client
        supabase = create_client(SUPABASE_URL.strip(), SUPABASE_KEY.strip())
        logger.info(f"Supabase configurado: {SUPABASE_URL[:30]}...")
    except Exception as e:
        logger.warning(f"Supabase no disponible ({e}); usando SQLite")
        supabase = None
else:
    logger.info("Sin credenciales Supabase -> modo SQLite local")


# ---------------------------------------------------------------- models
class CascadeLogCreate(BaseModel):
    model_from: str
    model_to: str
    reason: Optional[str] = "manual"
    tokens_remaining: Optional[int] = 0
    tier_from: Optional[int] = 1
    tier_to: Optional[int] = 2
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}

class VaultKeyCreate(BaseModel):
    provider: str = Field(..., pattern="^(openai|anthropic|google|ollama|deepseek|openrouter|groq|meta|xai)$")
    api_key: str

class ChatIn(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    model: Optional[str] = None


def mask_api_key(k: str) -> str:
    if not k:
        return ""
    if len(k) <= 8:
        return "â€¢" * len(k)
    return k[:4] + "â€¢" * (len(k) - 8) + k[-4:]


def _safe_err(exc: Exception) -> str:
    """Sanitiza errores: nunca exponer API keys en URLs/headers de mensajes."""
    import re
    msg = str(exc)
    msg = re.sub(r"(key=)[^&\s]+", r"\1***", msg)
    msg = re.sub(r"(Bearer\s)[A-Za-z0-9._\-]+", r"\1***", msg)
    return msg[:300]


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ------------------------------------------------- storage con fallback
def storage_insert_log(data: Dict[str, Any]) -> Dict[str, Any]:
    data["created_at"] = _utcnow()
    if supabase:
        try:
            r = supabase.table("cascade_logs").insert(data).execute()
            if r.data:
                return {"log": r.data[0], "stored": "supabase"}
        except Exception as e:
            logger.warning(f"Supabase insert fallo -> SQLite: {str(e)[:120]}")
    row = sq.insert_log(data)
    return {"log": row, "stored": "sqlite"}


def storage_get_logs(limit: int, offset: int, session_id: Optional[str]) -> Dict[str, Any]:
    if supabase:
        try:
            q = supabase.table("cascade_logs").select("*").order(
                "created_at", desc=True).range(offset, offset + limit - 1)
            if session_id:
                q = q.eq("session_id", session_id)
            r = q.execute()
            if isinstance(r.data, list):
                return {"logs": r.data, "stored": "supabase"}
        except Exception as e:
            logger.warning(f"Supabase select fallo -> SQLite: {str(e)[:120]}")
    logs = sq.get_logs(limit, offset)
    if session_id:
        logs = [l for l in logs if l.get("session_id") == session_id]
    return {"logs": logs, "stored": "sqlite"}


def storage_upsert_key(provider: str, api_key: str) -> str:
    if supabase:
        try:
            r = supabase.table("vault_keys").upsert(
                {"provider": provider, "api_key": api_key, "is_active": True},
                on_conflict="provider").execute()
            if r.data:
                return "supabase"
        except Exception as e:
            logger.warning(f"Supabase upsert key fallo -> SQLite: {str(e)[:120]}")
    sq.upsert_key(provider, api_key)
    return "sqlite"


def storage_get_key(provider: str) -> Optional[str]:
    if supabase:
        try:
            r = supabase.table("vault_keys").select("api_key").eq(
                "provider", provider).eq("is_active", True).limit(1).execute()
            if r.data:
                return r.data[0]["api_key"]
        except Exception:
            pass
    return sq.get_key(provider)


def storage_key_providers() -> (str, List[str]):
    provs: List[str] = []
    src = "sqlite"
    if supabase:
        try:
            r = supabase.table("vault_keys").select("provider").eq(
                "is_active", True).execute()
            if isinstance(r.data, list):
                provs = [x["provider"] for x in r.data]
                src = "supabase"
        except Exception:
            pass
    try:
        local = [x["provider"] for x in sq.get_keys() if x.get("is_active")]
        for p in local:
            if p not in provs:
                provs.append(p)
        if src == "supabase" and local:
            src = "supabase+sqlite"
    except Exception:
        pass
    return src, provs


def storage_keys_masked() -> List[Dict[str, Any]]:
    if supabase:
        try:
            r = supabase.table("vault_keys").select("*").eq("is_active", True).execute()
            if isinstance(r.data, list):
                return [{"id": k.get("id", i + 1), "provider": k["provider"],
                         "api_key_masked": mask_api_key(k["api_key"]),
                         "created_at": k.get("created_at") or _utcnow(),
                         "is_active": True}
                        for i, k in enumerate(r.data)]
        except Exception:
            pass
    return [{"id": i + 1, "provider": k["provider"],
             "api_key_masked": mask_api_key(k["api_key"]),
             "created_at": k["created_at"], "is_active": bool(k["is_active"])}
            for i, k in enumerate(sq.get_keys())]


def storage_delete_key(provider: str) -> bool:
    if supabase:
        try:
            r = supabase.table("vault_keys").update({"is_active": False}).eq(
                "provider", provider).execute()
            if r.data:
                return True
        except Exception:
            pass
    return sq.deactivate_key(provider)


# ---------------------------------------------------------------- lifespan
def _import_keys_from_opencode() -> List[str]:
    """Importa claves reales de opencode (~/.local/share/opencode/auth.json)
    al Vault local una sola vez; los placeholders ('sk-test...') se sobreescriben."""
    if os.getenv("AICASCADE_IMPORT_KEYS", "1") != "1":
        return []
    path = os.path.expanduser(os.path.join("~", ".local", "share",
                                           "opencode", "auth.json"))
    imported = []
    if not os.path.isfile(path):
        return imported
    try:
        with open(path, encoding="utf-8") as fh:
            auth = json.load(fh)
    except Exception as e:
        logger.warning("auth.json ilegible (%s): Vault sin auto-import", e)
        return imported
    for provider in ("google", "groq", "openrouter", "openai", "deepseek"):
        try:
            k = (auth.get(provider) or {}).get("key")
        except Exception:
            k = None
        if not k:
            continue
        existing = storage_get_key(provider)
        looks_placeholder = (not existing or str(existing).startswith("sk-test")
                            or len(str(existing)) < 20)
        if looks_placeholder:
            storage_upsert_key(provider, k)
            imported.append(provider)
    if imported:
        logger.info("Vault auto-import desde opencode: %s",
                    ", ".join(imported))
    return imported


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando AICascade Backend...")
    sq.init()
    logger.info(f"SQLite DB lista: {sq.DB_PATH}")
    try:
        _import_keys_from_opencode()
    except Exception as e:
        logger.warning("auto-import de claves fallo (no critico): %s", e)
    yield
    logger.info("Backend detenido")


app = FastAPI(title="AICascade Widget API", version="2.1.0",
    description="Cascade failover + Vault + Chat. Supabase con fallback SQLite.",
    lifespan=lifespan, docs_url="/docs", redoc_url="/redoc")

app.add_middleware(CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://127.0.0.1:8765",
        "http://localhost:8000", "http://localhost:8765",
        "https://frandev24.github.io"],
    allow_origin_regex=r"http://(127\.0\.0\.1|localhost)(:\d+)?",
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# --- Private Network Access (Chrome 130+): la web en https://frandev24
# llama a 127.0.0.1 -> el preflight EXIGE Allow-Private-Network: true.
# CORSMiddleware de Starlette no lo agrega: capa propia externa lo inyecta.
_PNA_ORIGINS = ("https://frandev24.github.io", "http://127.0.0.1",
                "http://localhost")


class _PrivateNetworkAccessMiddleware:
    """Chrome 130+ Private Network Access: la web (https://frandev24.github
    .io) llama al backend local 127.0.0.1:8000; el preflight exige
    Access-Control-Allow-Private-Network: true. Inyecta ese header en las
    respuestas (incluido el preflight) para origins permitidos."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http":
            return await self.app(scope, receive, send)
        hdrs = {k.decode("latin-1").lower(): v.decode("latin-1")
                for k, v in (scope.get("headers") or [])}
        origin = hdrs.get("origin", "")
        allowed = (origin in _PNA_ORIGINS[:1]
                   or origin.startswith(_PNA_ORIGINS[1:]))
        if not allowed:
            return await self.app(scope, receive, send)

        async def send_pna(message):
            if message["type"] == "http.response.start":
                hh = list(message.get("headers") or [])
                hh.append((b"access-control-allow-private-network", b"true"))
                message = {**message, "headers": hh}
            await send(message)

        await self.app(scope, receive, send_pna)


# Se registra DESPUES de CORSMiddleware => queda mas externo (envuelve el
# preflight del propio CORS y su respuesta).
app.add_middleware(_PrivateNetworkAccessMiddleware)


# ---------------------------------------------------------------- routes
@app.get("/health")
@app.get("/api/health")
async def health():
    is_sb = supabase is not None
    return {
        "status": "healthy",
        "timestamp": _utcnow(),
        "supabase_connected": is_sb,
        "supabase_configured": is_sb,
        "store": "supabase" if is_sb else "sqlite",
        "sqlite_db": sq.DB_PATH,
        "stored": "supabase+sqlite-fallback" if is_sb else "sqlite",
        "version": "2.1.0",
        "cascade": _CASCADE.snapshot(),  # additive: CircuitBreaker por proveedor
    }


@app.post("/api/cascade/log", status_code=201)
async def create_cascade_log(log: CascadeLogCreate):
    data = log.model_dump()
    data["reason"] = data.get("reason") or "manual"
    res = storage_insert_log(data)
    logger.info(f"Failover registrado [{res['stored']}]: "
        f"{data['model_from']} -> {data['model_to']} ({data['reason']})")
    return {"ok": True, "stored": res["stored"], "data": [res["log"]]}


@app.get("/api/cascade/logs")
async def get_cascade_logs(limit: int = 100, offset: int = 0,
    session_id: Optional[str] = None):
    limit = max(1, min(limit, 200))
    res = storage_get_logs(limit, offset, session_id)
    return {"ok": True, "stored": res["stored"], "logs": res["logs"]}


@app.get("/api/cascade/telemetry")
async def telemetry():
    logs = storage_get_logs(1000, 0, None)["logs"]
    today = datetime.now(timezone.utc).date().isoformat()
    return {
        "total_switches": len(logs),
        "switches_today": sum(1 for l in logs if str(l.get("created_at", "")).startswith(today)),
        "current_model": logs[0]["model_to"] if logs else None,
        "current_tier": logs[0].get("tier_to") if logs else None,
        "total_tokens_used": sum(l.get("tokens_remaining") or 0 for l in logs),
        "avg_latency_ms": 0.0,
        "error_rate": 0.0,
        "providers_status": {p: {"configured": True} for p in storage_key_providers()[1]},
    }


@app.get("/api/cascade/models")
async def cascade_models():
    """Lista de modelos disponibles para el selector tipo Gemini."""
    chain = _CASCADE.snapshot().get("chain", [])
    models = [
        {"id": "cascade-auto", "name": "Cascade Auto (Failover)", "provider": "cascade", "tier": 1},
        {"id": "google", "name": "Gemini 1.5 Flash", "provider": "google", "tier": 1},
        {"id": "google-pro", "name": "Gemini 1.5 Pro", "provider": "google", "tier": 1},
        {"id": "groq", "name": "Groq (gpt-oss-120b)", "provider": "groq", "tier": 2},
        {"id": "openrouter", "name": "OpenRouter (Nemotron)", "provider": "openrouter", "tier": 2},
        {"id": "openai", "name": "OpenAI (gpt-4o-mini)", "provider": "openai", "tier": 1},
        {"id": "deepseek", "name": "DeepSeek V2 Lite", "provider": "deepseek", "tier": 3},
        {"id": "ollama", "name": "Ollama (llama3.1:8b)", "provider": "ollama", "tier": 3},
    ]
    # Marcar cuáles tienen clave configurada
    _, providers = storage_key_providers()
    configured = set(providers)
    for m in models:
        m["configured"] = m["provider"] in configured or m["provider"] == "cascade"
    return {"ok": True, "models": models, "chain": chain, "default": "cascade-auto"}


@app.post("/api/vault/save", status_code=201)
async def save_vault_key(key: VaultKeyCreate):
    stored = storage_upsert_key(key.provider, key.api_key)
    logger.info(f"Vault key guardada [{stored}]: {key.provider}")
    return {"ok": True, "stored": stored, "provider": key.provider}


@app.get("/api/vault/status")
async def vault_status():
    stored, providers = storage_key_providers()
    return {"ok": True, "stored": stored, "providers": providers}


@app.get("/api/vault/keys")
async def vault_keys():
    return storage_keys_masked()


@app.delete("/api/vault/keys/{provider}")
async def delete_vault_key(provider: str):
    if not storage_delete_key(provider):
        raise HTTPException(status_code=404, detail="Key not found")
    return {"message": f"Key {provider} desactivada"}


@app.get("/api/vault/keys/{provider}/decrypt")
async def decrypt_vault_key(provider: str):
    k = storage_get_key(provider)
    if not k:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"api_key": k}


@app.post("/api/cascade/simulate-failover")
async def simulate_failover(model_from: str = "Claude 3.5 Sonnet",
    model_to: str = "GPT-4o-mini", reason: str = "manual",
    tokens_remaining: int = 5000, tier_from: int = 1, tier_to: int = 2):
    return await create_cascade_log(CascadeLogCreate(
        model_from=model_from, model_to=model_to, reason=reason,
        tokens_remaining=tokens_remaining, tier_from=tier_from, tier_to=tier_to,
        session_id=f"sim-{_utcnow()}", metadata={"simulated": True}))


# ---------------------------------------------------------------- chat
@app.get("/api/cascade/metrics")
async def cascade_metrics():
    """KPIs en vivo del CascadeEngine (fuente: logs/engine_events.jsonl):
    latencias p50/p95, llamadas por proveedor, fallos y tasa simulada."""
    import statistics
    events_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "logs", "engine_events.jsonl")
    rows = []
    try:
        with open(events_path, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        pass
    except FileNotFoundError:
        rows = []
    ok_rows = [r for r in rows if r.get("event") == "chat"]
    lat = [r["latency_ms"] for r in ok_rows
           if isinstance(r.get("latency_ms"), (int, float)) and r["latency_ms"] >= 0]
    ttfb = [r["ttfb_ms"] for r in rows
            if r.get("event") == "chat_stream"
            and isinstance(r.get("ttfb_ms"), (int, float))]
    provs = {}
    for r in ok_rows + [x for x in rows if x.get("event") == "fallback"]:
        p = r.get("provider") or "?"
        d = provs.setdefault(p, {"ok": 0, "fails": 0, "lat": []})
        if r.get("event") == "chat":
            d["ok"] += 1
            if isinstance(r.get("latency_ms"), (int, float)):
                d["lat"].append(r["latency_ms"])
        else:
            d["fails"] += 1
    for d in provs.values():
        d["latency_ms_avg"] = round(statistics.fmean(d["lat"]), 1) if d["lat"] else None
        d.pop("lat", None)
    total = len(ok_rows) + sum(1 for r in rows if r.get("event") == "simulated")
    sim = sum(1 for r in rows if r.get("event") == "simulated")

    def pct(vals, q):
        if not vals:
            return None
        v = sorted(vals)
        return v[min(len(v) - 1, int(round(q * (len(v) - 1))))]

    return {
        "ok": True,
        "engine": {"name": _CASCADE.NAME, "version": _CASCADE.VERSION},
        "events": {"chat": len(ok_rows),
                   "fallback": sum(1 for r in rows if r.get("event") == "fallback"),
                   "simulated": sim,
                   "retry": sum(1 for r in rows if r.get("event") == "retry"),
                   "stream": sum(1 for r in rows
                                 if str(r.get("event", "")).endswith("_stream")),
                   "total": len(rows)},
        "latency_ms": {"p50": pct(lat, 0.5), "p95": pct(lat, 0.95),
                       "ttfb_p50": pct(ttfb, 0.5), "ttfb_p95": pct(ttfb, 0.95)},
        "simulated_rate": round(sim / total, 3) if total else 0.0,
        "providers": provs,
        "breakers": {n: c.state.value for n, c in _CASCADE.breakers.items()},
    }


@app.get("/", include_in_schema=False)
async def widget_root():
    from fastapi.responses import FileResponse
    idx = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    return FileResponse(idx)
def _vault_key(provider: str) -> Optional[str]:
    return storage_get_key(provider)


# Motor de cascada: Circuit Breaker + Backoff+Jitter + telemetria JSONL.
# Ver cascadeengine/engine.py para los patrones y referencias.
# HEDGING (carrera de 2 proveedores) DESACTIVADO en prod: el modo secuencial
# es el camion probado en test_engine.py (17/17 PASS). Se habilita con
# AICASCADE_HEDGED=1 una vez reconciliado el race con Cline.
_HEDGED_PROD = os.getenv("AICASCADE_HEDGED", "0") == "1"
_CASCADE = _engine.CascadeEngine(
    base_dir=os.path.dirname(os.path.abspath(__file__)),
    failure_threshold=3, recovery_timeout=30.0,
    per_call_timeout=4.5, ollama_timeout=4.0,
    timeout_provider=4.5,
    hedged=_HEDGED_PROD, hedge_delay=0.8)


@app.post("/api/chat")
async def chat(payload: ChatIn):
    """Failover real async (CascadeEngine): Google -> Groq -> OpenRouter ->
    OpenAI -> DeepSeek -> Ollama -> simulado. No bloquea el event loop."""
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Mensaje vacio")
    try:
        r = await _CASCADE.chat(message, key_lookup=_vault_key,
                                model_hint=payload.model)
    except Exception as exc:
        logger.exception("CascadeEngine fallo; fallback simulado controlado")
        r = _engine.CascadeResult(
            ok=True, mode="simulated", provider="simulated",
            model=payload.model or "Cascade-Auto",
            response="[SIMULADO - CascadeEngine indisponible]\n\nRecibido: "
                     + message[:200],
            attempts=[{"provider": "engine", "error": _safe_err(exc)}])
    if r.mode == "live" and r.provider in ("google", "groq", "openrouter",
                                           "openai", "deepseek", "ollama"):
        try:
            sq.touch_key(r.provider)
        except Exception:
            pass
    logger.info("Chat ok [%s/%s] lat=%.0fms intentos=%d",
                r.provider, r.mode, r.latency_ms, len(r.attempts))
    return {"ok": r.ok, "mode": r.mode, "provider": r.provider,
            "model": r.model, "response": r.response, "attempts": r.attempts,
            "latency_ms": r.latency_ms, "breaker": r.breaker}


@app.post("/api/cascade/reset-breakers")
async def reset_breakers():
    """Resetea el Circuit Breaker de todos los proveedores (operacion manual)."""
    _CASCADE.reset_breakers()
    return {"ok": True, "cascade": _CASCADE.snapshot()}


@app.post("/api/chat/stream")
async def chat_stream(payload: ChatIn):
    """SSE token-por-token con failover por TTFB (OpenAI-style).

    Eventos: 'start' -> 'meta'|'delta'* -> 'done'. Ultima salida 'simulated'.
    curl -N -X POST :8000/api/chat/stream -H 'Content-Type: application/json' -d '{"message":"hola"}'
    """
    from fastapi.responses import StreamingResponse

    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Mensaje vacio")

    async def sse():
        try:
            async for evt in _CASCADE.stream_chat(
                    message, key_lookup=_vault_key,
                    model_hint=payload.model, ttfb_timeout=4.0):
                kind = evt.get("event")
                if kind == "delta":
                    line = {"event": "delta", "provider": evt["provider"],
                            "content": evt["content"]}
                elif kind == "meta":
                    line = {"event": "meta", "provider": evt["provider"],
                            "model": evt.get("model")}
                else:
                    line = {**evt}
                yield "data: " + json.dumps(line, ensure_ascii=False) + "\n\n"
        except Exception as exc:
            logger.exception("SSE stream fallo; cierre controlado")
            yield ("data: " + json.dumps({"event": "done", "ok": False,
                                          "provider": "engine",
                                          "error": _safe_err(exc)},
                                         ensure_ascii=False) + "\n\n")
        yield "data: [DONE]\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.exception_handler(HTTPException)
async def http_exc(request, exc):
    return JSONResponse(status_code=exc.status_code,
        content={"detail": exc.detail, "error": True})


@app.exception_handler(Exception)
async def gen_exc(request, exc):
    logger.exception("Unhandled")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# mount "/" al final: la API tiene prioridad, todo lo demas sirve el widget.
# Nota seguridad: StaticFiles(html=True) expondria .env / .db / venv si se
# montara todo el proyecto. Solo se sirven archivos del HUD (lista blanca).
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.isdir(WEB_DIR):
    from fastapi.staticfiles import StaticFiles
    from starlette.middleware.base import BaseHTTPMiddleware

    _PUBLIC_FILES = {
        "index.html", "manifest.webmanifest", "bridge.py",
        "requirements.txt", "README.md", "app.ico",
    }
    _PUBLIC_PREFIXES = ("css/", "js/", "icons/")
    _BLOCKED_SUFFIX = (".env", ".db", ".sqlite", ".sqlite3", ".log",
        ".pem", ".key", ".bat", ".sh", ".pyc")
    _BLOCKED_DIRS = ("venv/", ".git/", "__pycache__/", ".venv/")

    class _GuardStatic(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            p = (request.url.path or "/").lstrip("/").lower()
            if request.url.path.startswith("/api/") or request.url.path in (
                    "/docs", "/redoc", "/openapi.json", "/health"):
                return await call_next(request)
            if (p.startswith(_BLOCKED_DIRS) or p.endswith(_BLOCKED_SUFFIX)
                    or p in (".env", ".gitignore")):
                return JSONResponse(status_code=404,
                    content={"detail": "Not found"})
            return await call_next(request)

    app.add_middleware(_GuardStatic)

    class _WhitelistStatic(StaticFiles):
        async def get_response(self, path, scope):
            from fastapi.responses import FileResponse
            rel = (path or "").replace("\\", "/").lstrip("/")
            if rel in ("", "/"):
                return FileResponse(os.path.join(WEB_DIR, "index.html"))
            ok = (rel in _PUBLIC_FILES
                or rel.startswith(_PUBLIC_PREFIXES))
            if not ok:
                return JSONResponse(status_code=404,
                    content={"detail": "Not found"})
            return await super().get_response(path, scope)

    app.mount("/", _WhitelistStatic(directory=WEB_DIR, html=True),
        name="widget")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
