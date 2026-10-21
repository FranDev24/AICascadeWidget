#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AICascadeWidget - Suite de pruebas profesional (Fase 1: Testing)."""
import os, sys, py_compile
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASS, FAIL = [], []
def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  [OK] " if cond else "  [FAIL] ") + name + (f" - {detail}" if detail and not cond else ""))
print("=" * 60)
print(" AICascadeWidget - Test Suite v2.1 (parte 1: sintaxis+backend)")
print("=" * 60)
for f in ["main.py", "db.py", "bridge.py", "server.py", "tools/make_logo.py"]:
    p = os.path.join(BASE, f)
    try:
        py_compile.compile(p, doraise=True)
        check(f"compile:{f}", True)
    except Exception as e:
        check(f"compile:{f}", False, str(e)[:150])
try:
    sys.path.insert(0, BASE)
    os.chdir(BASE)
    from fastapi.testclient import TestClient
    import main as backend
    c = TestClient(backend.app)
    r = c.get("/api/health")
    j = r.json() if r.status_code == 200 else {}
    check("GET /api/health 200", r.status_code == 200)
    check("health.supabase_connected bool", isinstance(j.get("supabase_connected"), bool), str(j)[:120])
    check("health.store presente", "store" in j, str(j)[:120])
    check("health.compat supabase_configured", "supabase_configured" in j)
    r2 = c.post("/api/cascade/log", json={"model_from": "GPT-4o", "model_to": "GPT-4o-mini", "reason": "test"})
    check("POST /api/cascade/log 201", r2.status_code == 201, f"got {r2.status_code}")
    r3 = c.get("/api/cascade/logs?limit=5")
    logs = r3.json().get("logs", []) if r3.status_code == 200 else []
    check("GET /api/cascade/logs 200 + lista", r3.status_code == 200 and isinstance(logs, list))
    check("log roundtrip persistido", any(l.get("reason") == "test" for l in logs))
    r4 = c.get("/api/cascade/telemetry")
    check("GET /api/cascade/telemetry 200", r4.status_code == 200)
    rv = c.post("/api/vault/save", json={"provider": "openai", "api_key": "sk-test-1234567890"})
    check("POST /api/vault/save 201", rv.status_code == 201, f"got {rv.status_code}")
    rs = c.get("/api/vault/status")
    provs = rs.json().get("providers", []) if rs.status_code == 200 else []
    check("vault/status incluye openai", "openai" in provs, str(provs)[:120])
    all9 = ["openai", "anthropic", "google", "ollama", "deepseek", "openrouter", "groq", "meta", "xai"]
    ok9 = True
    for p in all9:
        rr = c.post("/api/vault/save", json={"provider": p, "api_key": "sk-test-1234567890"})
        if rr.status_code != 201:
            ok9 = False
    check("vault acepta 9 proveedores", ok9)
    rc = c.post("/api/chat", json={"message": "hola test"})
    jc = rc.json() if rc.status_code == 200 else {}
    check("POST /api/chat 200 ok:true", rc.status_code == 200 and jc.get("ok") is True, f"got {rc.status_code}")
    rw = c.get("/")
    check("GET / sirve widget 200", rw.status_code == 200, f"got {rw.status_code}")
    rb = c.get("/.env")
    check("GET /.env bloqueado 404", rb.status_code == 404, f"got {rb.status_code}")
except Exception as e:
    check("backend TestClient", False, str(e)[:300])
print(f"PARTE1 PASADOS:{len(PASS)} FALLIDOS:{len(FAIL)} -> {FAIL}")
