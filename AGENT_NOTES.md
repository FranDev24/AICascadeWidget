# 🤖 AGENT NOTES — Estado real del proyecto (leer ANTES de editar)

_ultima actualizacion: GREEN GATE APROBADO (health+widget+chat+reset-breakers 200, latencias <25s). Regla de oro de ambos agentes (Cline y opencode): antes de dar por "listo" cualquier cambio, correr `tools/e2e_test.ps1` y confirmar :8000 + chat vivos. NUNCA entregar con el server roto._


## REGLAS DURAS (romperlas = app caida para el usuario)
1. **Un solo servidor en :8000 = `main:app`** (raiz). Prohibido levantar
   `uvicorn cascadeengine.server:app --port 8000` (asi se causo la ultima caida;
   el servidor de Cline se apropio del puerto y el HUD recibio 404s).
   El facade `cascadeengine/server.py` solo dev con **puertos >= 8100**.
2. **`server.py` debe existir SIEMPRE** en la raiz (sirve :8765 espejo).
   Hoy fue renombrado a `server_old.py` y el enlace web cayo. No renombrarlo.
3. **main.py NO levantar `requests` bloqueante** — `/api/chat` ya es async con
   CascadeEngine. No reintroducir HTTP sync (bloquea el event loop).
4. **cascadeengine/engine.py es la implementacion REAL** (testeeada). core/*
   son alias. NO dejar skeletons con NotImplementedError (ellos tiran el chat).
5. **HEDGED OFF en prod** (main.py `hedged=_HEDGED_PROD` default 0). El race
   mostro ~15x eventos repetidos con keys de prueba + sandbox lento; se
   habilita solo cuando `tools/test_engine.py` sea 17/17 estable y sin
   eventos repetidos en `logs/engine_events.jsonl` (regla del race).
6. Claves del Vault se CIFRAN (DPAPI) via `vault_crypto.py` — no exponer
   plaintext en logs/endpoints; valido para toda lectura nueva de db.py.

## NO RE-IMPLEMENTAR (y ya listo, validado con tests)
- **Paquete `cascadeengine/`** (engine.py): CircuitBreakerStates CLOSED/OPEN/HALF_OPEN, Backoff full-jitter (Brooker/AWS), cadena google→groq→openrouter→openai→deepseek→ollama→simulado, probe de ollama (`/api/version`, 0.35s) y metricas JSONL en `logs/engine_events.jsonl`.
- **`/api/chat` ya usa el engine async (httpx)** — NO reescribir con `requests` (bloquea el loop). Contrato de respuesta INTACTO + campos aditivos:
  ```json
  {"ok":true,"mode":"live|simulated","provider":"...","model":"...","response":"...",
   "attempts":[{"provider","error","latency_ms","status_code"}],
   "latency_ms": 123.4, "breaker": {"google":"CLOSED", ...}}
  ```
  Frontend usa: `res.mode, res.provider, res.response, res.model` (app.js:189-197, terminal.js:180-181). No romper esos campos.
- **Inspeccion nuevo**: `GET /api/health` incluye `"cascade": {providers:{<p>:{state,failures,last_error}},chain:[...]}` y `POST /api/cascade/reset-breakers` (reabre todos los breakers manualmente).
- Reglas del motor: sin key -> skip (no cuenta como fallo); 429/timeout -> 1 retry con backoff; error de conexion -> fallback directo; 3 fallos -> breaker OPEN 30s; con breaker OPEN la respuesta sale ~0 ms (medido E2E).

## Tests (ejecutar tras cambios)
```
venv\Scripts\python.exe tools\test_engine.py        # 15/17 PASS (2 fails solo por sandbox lento)
venv\Scripts\python.exe tools\e2e_test.ps1          # app escritorio E2E
# Green gate de 30 s recomendado tras CUALQUIER cambio:
#   curl :8000/api/health -> healthy ; POST /api/chat -> ok:true ; POST /api/cascade/reset-breakers -> ok
```

## Como atribuir causa de"app caida"
- `netstat -ano | findstr :8000` -> si el PID no es uvicorn main:app, matalo y relanza.
- El zombie tipico: `uvicorn cascadeengine.server:app --port 8000` (revisarla prohibida arriba).

## Servidores que DEBEN estar corriendo (ya corriendo)
| Puerto | Qué sirve | Uso |
|---|---|---|
| **8000** | FastAPI `main:app` — API `/api/*` **+ widget (mount "/")** | URL canonica |
| **8765** | `server.py` (estático) | espejo para pruebas |

> Desktop launcher: accesos directos → `venv\Scripts\pythonw.exe desktop_app.py` (Chrome/Edge --app 1280x860, fallback pywebview). Logo `app.ico` ya aplicado.

## Contrato del tema día/noche (CIERRE RECIENTE — no duplicar)
- HTML: `.theme-toggle-container > .toggle input#themeCheckbox onchange="toggleTheme()" + .button + .label(#themeIconLabel)` en el **header**.
- JS: `app.js` `toggleTheme()/initTheme()` ya son dual-safe. CSS del toggle: **`css/uiverse-theme-toggle.css`** carga de última.

## Orden de cascada de CSS (lo último GANA)
style.css → iphone.css → ios-dashboard.css → liquid.css → iosapp.css → ultra-glass.css → iphone18pro.css → 18pro-finish.css → uiverse-packs.css → uiverse-integrate.css → 18pro-sphere.css → uiverse-theme-toggle.css
Cada agente trabaja en SU archivo nuevo; versionar con `?v=`.

## IDs que el JS usa (no romper)
`panel-* nav-* activeModel activeTier tokenBar* status* switch/callCount metric* tier[1-3]Models activityLog chat* providersGrid vault* terminal* toast* dynamicIsland backendStatus current* theme* iosRing*`

## Paleta oficial (iPhone 18 Pro)
DÍA: base `#F2F4F8→#E6E9F0`, vidrio `rgba(255,255,255,.68) blur(36px) sat(220%)`, acento `#007AFF`.
NOCHE: base `#0A0B0E→#12141A`, vidrio `rgba(18,20,26,.78/.82) blur(36px) sat(190%)`, acentos `#0B84FF / #64D2FF / #FF9F0A`.

## QA rápido (30 s)
1. `Invoke-RestMethod http://127.0.0.1:8000/api/health` → `healthy`
2. `POST /api/chat {"message":"x"}` → `ok:true` + `provider` live o simulated
3. `POST /api/cascade/reset-breakers` → `ok:true`
4. `logs/engine_events.jsonl` crece con cada chat (eventos chat/fallback/simulated/retry)

## Proyecto hermano: AI-Cascade-Proxy (LiteLLM :4000)
Config v2 aplicada por opencode: Circuit Breaker (`allowed_fails:2, cooldown_time:30`), `retry_policy` granular (0 retries en auth), `latency-based-routing`, **callbacks custom** `cascade_observability.cascade_logger` (JSONL en logs/hcascade_YYYYMMDD.jsonl; referenciado SIN parentesis, get_instance_fn no acepta "()") y cache local (`cache_params.type: local`, TTL 600s). Estandar de compatibilidad: nombres de modelos, endpoints y fallbacks NO se tocaron. Resumen CLI: `python logs/resumen.py`; suite: `test_cascada.ps1`.
