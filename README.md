# AICascade Widget — Gestor de Cascada IA (Full-Stack)

HUD Liquid Glass + Backend FastAPI + Supabase + CLI Bridge.

## 🚀 Inicio rápido (todo junto)
Doble clic en **`start-all.bat`** — levanta Backend :8000 + HUD :8765.  
Solo backend: **`start-backend.bat`**.  
Manual: `pip install -r requirements.txt` → `uvicorn main:app --port 8000` → `python server.py`.

## 🗄️ Supabase (1 vez)
SQL Editor → pegar **`schema.sql`** → Run. Copiar URL + key a **`.env`**.  
Sin Supabase funciona en `memory-fallback`.

## ✨ Módulos
- **Dashboard** con persistencia  
- **Chat IA** (`POST /api/chat`, failover OpenAI → DeepSeek → Ollama → simulado)  
- **Proveedores** (9 modelos)  
- **Vault** (localStorage + Supabase)  
- **Terminal**  
- **CLI** (`python bridge.py status|chat "hola"`)

## 🔌 API
`GET /` · `GET /api/health` · `POST /api/cascade/log` · `GET /api/cascade/logs` ·  
`POST /api/vault/save` · `GET /api/vault/status` · `POST /api/chat`  
Documentación interactiva en `/docs`.

## 🧪 Estado
Frontend OpenCode conservado + bug `switchModel` corregido. `main.py` compila OK, JS validado, CORS local + `file://`.

---

## 🌐 Demo en vivo (GitHub Pages)

[https://FranDev24.github.io/AICascadeWidget/](https://FranDev24.github.io/AICascadeWidget/)

Desde tu **iPhone 16 Pro** se abre sin necesidad de tener tu PC encendido.

---

Desarrollado por **FranDev24**
