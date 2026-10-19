# 🤖 AGENT NOTES — Estado real del proyecto (leer ANTES de editar)

_Última actualización: coordinación opencode ↔ Cline. Si algo difiere de esto, dicho cambio es más nuevo; actualiza esta nota._

## Servidores que DEBEN estar corriendo (ya corriendo)
| Puerto | Qué sirve | Uso |
|---|---|---|
| **8000** | FastAPI `main:app` — API `/api/*` **+ widget completo (StaticFiles mount "/")** | URL canónica: `http://127.0.0.1:8000` |
| **8765** | `server.py` (estático) | espejo para pruebas del widget Persistence de datos: `aicascade.db` (SQLite, fallback cuando Supabase falla) |

> Si ves `ERR_CONNECTION_REFUSED` en un puerto → relanza: `venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000` (y/o `venv\Scripts\python.exe server.py`).

## Contrato del tema día/noche (CIERRE RECIENTE — no duplicar)
- HTML: `.theme-toggle-container > .toggle input#themeCheckbox onchange="toggleTheme()" + .button + .label(#themeIconLabel)` en el **header**.
- JS: `app.js` `toggleTheme()/initTheme()` ya son dual-safe (checkbox nuevo + botón viejo a prueba de nulls). `window.toggleTheme` = alias global en index.html.
- CSS del toggle físico: **`css/uiverse-theme-toggle.css`** (carga DE ÚLTIMA, todo bajo `.theme-toggle-container`).
  ⚠️ No re-implementar el toggle en otros sheets (hubo duplicados en `ultra-glass.css` y `18pro-sphere.css` con el markup antiguo `.p18-*`, hoy inertes).

## Orden de cascada de CSS (lo último GANA los empates)
```
style.css → iphone.css → ios-dashboard.css → liquid.css → iosapp.css
→ ultra-glass.css (WIP de Cline) → iphone18pro.css → 18pro-finish.css
→ uiverse-packs.css → uiverse-integrate.css → 18pro-sphere.css → uiverse-theme-toggle.css
```
Regla de convivencia: **cada agente trabaja en SU archivo nuevo**; no reescribir hojas ajenas. Versiona con `?v=` al enlazar.

## IDs que el JS usa (no romper)
`panel-* · nav-* · activeModel · activeTier · tokenBar(Total|Remaining) · statusDot/Text · switch/callCount · metric* · tier[1-3]Models · activityLog · chatLog/Input/Mode · providersGrid · vault* · terminalOutput/Input · toast* · dynamicIsland · backendStatus · current(Date|Time) · themeCheckbox · themeIconLabel · iosRing(Val)`

## Paleta oficial (iPhone 18 Pro)
DÍA: base `#F2F4F8→#E6E9F0`, vidrio `rgba(255,255,255,.68) blur(36px) sat(220%)`, título `#1A1D24`, acento `#007AFF`.
NOCHE: base `#0A0B0E→#12141A`, vidrio `rgba(18,20,26,.78/.82) blur(36px) sat(190%)`, título `#F5F7FA`, acentos `#0B84FF / #64D2FF / #FF9F0A`.

## QA rápido (30 s)
1. `Invoke-RestMethod http://127.0.0.1:8000/api/health` → `healthy`
2. `Invoke-RestMethod http://127.0.0.1:8000/` → 200 (es el WIDGET, no JSON)
3. `POST /api/chat {"message":"x"}` → `ok:true` (mode=live|simulated)
4. Consola del navegador sin 404 (sw.js, manifest, icons ya existen)
