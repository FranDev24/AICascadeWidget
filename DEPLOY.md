# 🌐 Publicar AICascadeWidget 24/7 (sin PC encendido) — iPhone 16 Pro

> Yo no puedo crear el link por ti (no tengo acceso a desplegar), pero con estos
> archivos ya listos lo tienes en ~10 minutos. Elige UNA opción.

## ✅ Lo que ya dejé listo en el proyecto

- `index.html` con meta PWA iOS, Open Graph para WhatsApp, `viewport-fit=cover`
- `manifest.webmanifest` + `sw.js` (offline en iPhone) + `css/iphone.css`
  (safe-area Dynamic Island, bottom-bar, botones 44px, 120Hz, sin auto-zoom)
- `icons/icon.svg` + `tools/make_icons.py` (genera los PNG)
- `vercel.json` + `netlify.toml` (config de hosting)
- `.nojekyll` + `404.html` (GitHub Pages)

## 1️⃣ Genera los iconos (1 min, en tu PC)

```bat
cd /d C:\Users\MT-110326\Documents\Programas\AICascadeWidget
venv\Scripts\python.exe -m pip install pillow -q
venv\Scripts\python.exe tools\make_icons.py
```

Debe crear: `icons/icon-16.png, icon-32.png, icon-180.png, icon-192.png, icon-512.png, og-cover.png`

## 2️⃣ Opción A — Cloudflare Pages (recomendada: gratis, 24/7, link inmediato)

1. Crea cuenta en https://dash.cloudflare.com/sign-up
2. Pages → Create → **Upload assets** → arrastra TODA la carpeta
   `AICascadeWidget` (sin el `venv`) → Deploy.
3. Te da un link `https://aicascade-xxx.pages.dev` ✅ activo 24/7.
4. Ese link lo compartes por WhatsApp y abre perfecto en iPhone.

## 2️⃣ Opción B — Netlify Drop (la más fácil, sin cuenta al inicio)

1. Entra a https://app.netlify.com/drop desde tu PC.
2. Arrastra la carpeta `AICascadeWidget` (sin `venv`) al navegador.
3. Te da link `https://xxx.netlify.app` ✅ 24/7. (Usa `netlify.toml` incluido.)

## 2️⃣ Opción C — Vercel (gratis)

1. https://vercel.com/new → importa la carpeta (usa `vercel.json` incluido).
2. Deploy → link `https://aicascade-xxx.vercel.app` ✅ 24/7.

## 2️⃣ Opción D — GitHub Pages (gratis, con tu GitHub)

```bat
cd /d C:\Users\MT-110326\Documents\Programas\AICascadeWidget
git init && git add -A && git commit -m "AICascade PWA"
gh repo create aicascade-widget --public --source=. --push
```

Luego: repo → Settings → Pages → Deploy from branch → `main` → `/ (root)`.
Link: `https://TU-USUARIO.github.io/aicascade-widget/` ✅ (usa `.nojekyll` + `404.html` incluidos).

## 3️⃣ En tu iPhone 16 Pro (iOS 18)

1. Abre el link en Safari.
2. Compartir → **Añadir a pantalla de inicio** → se instala como app
   (icono, splash, standalone sin barra, funciona offline).
3. El link se comparte por WhatsApp con vista previa (título + descripción +
   imagen `og-cover.png`).

## ⚠️ Nota importante (backend)

El link público sirve el **HUD completo en modo local** (cascada simulada,
vault en el iPhone, terminal, chat simulado). El backend FastAPI `:8000` y
Supabase son opcionales: si quieres respuestas IA reales 24/7, despliega
`main.py` aparte en Render/Railway (gratis) y pega su URL en `js/backend.js`
(`baseUrl`). Sin eso, todo lo demás funciona igual.

## 📱 Optimizaciones iPhone aplicadas

- `viewport-fit=cover` + `safe-area-inset-*` (Dynamic Island / notch)
- Sidebar → bottom-bar táctil en ≤768px, botones ≥44px, inputs 16px (sin zoom)
- Animaciones recortadas a 120Hz ProMotion, blur reducido en móvil
- PWA standalone + service worker con caché offline
