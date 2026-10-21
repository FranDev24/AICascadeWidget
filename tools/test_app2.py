#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AICascadeWidget - Test parte 2: contrato frontend + schema + bats."""
import os, sys
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []
def check(name, cond, detail=""):
    print(("  [OK] " if cond else "  [FAIL] ") + name)
    if not cond:
        fails.append(name + (f" :: {detail[:150]}" if detail else ""))
src = open(os.path.join(BASE, "main.py"), encoding="utf-8").read()
for ep in ["/api/health", "/api/cascade/log", "/api/cascade/logs",
           "/api/cascade/telemetry", "/api/vault/save", "/api/vault/status", "/api/chat"]:
    check(f"contrato {ep}", ep in src)
for js in ["js/backend.js", "js/live-sync.js", "js/vault.js", "js/app.js", "js/cascade.js"]:
    check(f"existe {js}", os.path.exists(os.path.join(BASE, js)))
sql = open(os.path.join(BASE, "schema.sql"), encoding="utf-8").read().lower()
for t in ["cascade_logs", "vault_keys", "sessions"]:
    check(f"schema tabla {t}", f"create table if not exists {t}" in sql)
check("schema RLS sessions", "alter table sessions enable row level security" in sql)
bat = open(os.path.join(BASE, "start-all.bat"), encoding="utf-8", errors="ignore").read()
check("bat sin cmd /c anidado", 'cmd /c "cd /d' not in bat)
check("bat health check", "api/health" in bat)
man = open(os.path.join(BASE, "manifest.webmanifest"), encoding="utf-8").read()
check("manifest standalone", "standalone" in man)
print(f"PARTE2 FALLIDOS:{len(fails)} -> {fails}")
sys.exit(1 if fails else 0)
