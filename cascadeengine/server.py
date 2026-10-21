# -*- coding: utf-8 -*-
"""
cascadeengine.server — PANEL de-tests/gateway SOLO DE LIBRERIA.

REGLA HARD (coordination gate):
  El servidor CANONICO del widget en el puerto 8000 es `main:app` (raíz).
  Este app NUNCA debe levantarse con --port 8000 (lo rompe todo para la
  app de escritorio y el HUD). Usar solo ports > 8100 y para pruebas.

Corre:  uvicorn cascadeengine.server:app --port 8100   (siempre dev)
"""
import os
from fastapi import FastAPI

from cascadeengine.core.module import CascadeEngine
from cascadeengine.core.module import generate_request_id, retry_with_backoff

app = FastAPI(title="AICascade Engine Demo", version="1.0.0",
              docs_url=None, redoc_url=None, openapi_url=None)


@app.on_event("startup")
async def _warn_port():
    import os as _os
    if str(_os.getenv("AICASCADE_LIB_PORT", "8100")) != "8100":
        print("\n*** AVISO: este facade es de LIBRERIA. gebruik puertos >= 8100. ***\n")


@app.get("/engine/health")
async def engine_health():
    e = CascadeEngine(base_dir=os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    return {"status": "lib-ok", "chain": e.snapshot().get("chain", []),
            "note": "El servidor real del widget es main:app (:8000)."}


# Nota para el equipo: no importar menos; este modulo no replica /api/chat.
# Para chat real -> main.py (run: venv\Scripts\python.exe -m uvicorn main:app --port 8000)
