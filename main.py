#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AICascade Widget - Backend FastAPI con Supabase Y SQLite.
Estrategia: Supabase primero; si falla (RLS/red/tabla faltante) -> SQLite local
(aicascade.db, base persistente creada automaticamente). La UI esta servida
por este mismo servidor: http://127.0.0.1:8000
"""

import os
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
        return "•" * len(k)
    return k[:4] + "•" * (len(k) - 8) + k[-4:]


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
    if supabase:
        try:
            r = supabase.table("vault_keys").select("provider").eq(
                "is_active", True).execute()
            if isinstance(r.data, list):
                return "supabase", [x["provider"] for x in r.data]
        except Exception:
            pass
    providers = sorted({k["provider"] for k in sq.get_keys() if k["is_active"]})
    return "sqlite", providers


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
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando AICascade Backend...")
    sq.init()
    logger.info(f"SQLite DB lista: {sq.DB_PATH}")
    yield
    logger.info("Backend detenido")


app = FastAPI(title="AICascade Widget API", version="2.1.0",
    description="Cascade failover + Vault + Chat. Supabase con fallback SQLite.",
    lifespan=lifespan, docs_url="/docs", redoc_url="/redoc")

app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------- routes
@app.get("/health")
@app.get("/api/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": _utcnow(),
        "supabase_connected": supabase is not None,
        "supabase_configured": supabase is not None,
        "sqlite_db": sq.DB_PATH,
        "stored": "supabase+sqlite-fallback" if supabase else "sqlite",
        "version": "2.1.0",
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
def _vault_key(provider: str) -> Optional[str]:
    return storage_get_key(provider)


@app.post("/api/chat")
async def chat(payload: ChatIn):
    """Failover real: OpenAI -> DeepSeek -> Ollama -> simulado."""
    import requests as _rq
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Mensaje vacio")
    attempts: List[Dict[str, Any]] = []

    def _oai(base: str, key: str, model: str) -> str:
        r = _rq.post(f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": model, "max_tokens": 512, "temperature": 0.7,
                "messages": [{"role": "user", "content": message}]}, timeout=30)
        r.raise_for_status()
        return str(r.json()["choices"][0]["message"]["content"])

    k = _vault_key("openai")
    if k:
        try:
            sq.touch_key("openai")
            return {"ok": True, "mode": "live", "provider": "openai",
                "model": "gpt-4o-mini", "response": _oai(
                    "https://api.openai.com/v1", k, "gpt-4o-mini"),
                "attempts": attempts}
        except Exception as exc:
            attempts.append({"provider": "openai", "error": str(exc)[:300]})
    k = _vault_key("deepseek")
    if k:
        try:
            sq.touch_key("deepseek")
            return {"ok": True, "mode": "live", "provider": "deepseek",
                "model": "deepseek-chat",
                "response": _oai("https://api.deepseek.com/v1", k, "deepseek-chat"),
                "attempts": attempts}
        except Exception as exc:
            attempts.append({"provider": "deepseek", "error": str(exc)[:300]})
    try:
        r = _rq.post("http://127.0.0.1:11434/api/generate",
            json={"model": "llama3.1:8b", "prompt": message, "stream": False},
            timeout=20)
        if r.status_code == 200:
            return {"ok": True, "mode": "live", "provider": "ollama",
                "model": "llama3.1:8b", "response": r.json().get("response", ""),
                "attempts": attempts}
    except Exception as exc:
        attempts.append({"provider": "ollama", "error": str(exc)[:200]})
    return {"ok": True, "mode": "simulated", "provider": "simulated",
        "model": payload.model or "Cascade-Auto",
        "response": "[SIMULADO - agrega keys en el Vault: openai/deepseek/ollama]\n\n"
            + "Recibido: " + message[:200],
        "attempts": attempts}


@app.exception_handler(HTTPException)
async def http_exc(request, exc):
    return JSONResponse(status_code=exc.status_code,
        content={"detail": exc.detail, "error": True})


@app.exception_handler(Exception)
async def gen_exc(request, exc):
    logger.exception("Unhandled")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# mount "/" al final: la API tiene prioridad, todo lo demas sirve el widget
WEB_DIR = os.path.dirname(os.path.abspath(__file__))
if os.path.isdir(WEB_DIR):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="widget")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
