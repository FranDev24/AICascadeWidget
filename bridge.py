#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AICascade CLI Bridge - habla con el backend FastAPI local."""
import argparse, json, sys
import urllib.request

BASE = "http://127.0.0.1:8000"

def _req(method, path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    r = urllib.request.Request(BASE + path, data=body, method=method,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=10) as res:
            return json.loads(res.read().decode())
    except Exception as exc:
        print(f"[ERROR] {exc} (backend en {BASE}?)", file=sys.stderr)
        sys.exit(1)

def main():
    p = argparse.ArgumentParser(prog="bridge", description="AICascade CLI Bridge")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="Estado del backend")
    s = sub.add_parser("log", help="Registrar failover")
    s.add_argument("--from", dest="mfrom", required=True)
    s.add_argument("--to", required=True)
    s.add_argument("--reason", default="")
    s.add_argument("--tokens", type=int, default=None)
    s = sub.add_parser("vault-save", help="Guardar key")
    s.add_argument("--provider", required=True)
    s.add_argument("--key", required=True)
    sub.add_parser("vault-status", help="Providers configurados")
    s = sub.add_parser("chat", help="Chatear con failover")
    s.add_argument("message", nargs="+")
    a = p.parse_args()
    if a.cmd == "status":
        print(json.dumps(_req("GET", "/api/health"), indent=2, ensure_ascii=False))
    elif a.cmd == "log":
        print(json.dumps(_req("POST", "/api/cascade/log",
            {"model_from": a.mfrom, "model_to": a.to,
             "reason": a.reason or None, "tokens_remaining": a.tokens}), indent=2))
    elif a.cmd == "vault-save":
        print(json.dumps(_req("POST", "/api/vault/save",
            {"provider": a.provider, "api_key": a.key}), indent=2))
    elif a.cmd == "vault-status":
        print(json.dumps(_req("GET", "/api/vault/status"), indent=2))
    elif a.cmd == "chat":
        print(json.dumps(_req("POST", "/api/chat",
            {"message": " ".join(a.message)}), indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
