# 📦 AICascade Widget — Listo para compartir

Este paquete contiene todo lo necesario para ejecutar el Gestor de Cascada IA como aplicación de escritorio.

## 📁 Contenido
- `index.html` — Interfaz principal (Liquid Glass, iPhone 18 Pro estilo)
- `css/style.css` — Diseño visual día/noche
- `js/cascade.js` — Motor de cascada IA (3 niveles, failover, tokens)
- `js/vault.js` — Vault de claves API
- `js/terminal.js` — Terminal Super Admin
- `js/app.js` — Orquestador principal
- `server.py` — Servidor local opcional
- `launcher.pyw` — Lanzador como app de escritorio (ventana sin navegador)
- `AICascadeWidget.bat` — Lanzador por lotes
- `README.md` — Instrucciones de uso

## 🚀 Cómo usar (sin instalar nada)
1. Descomprime esta carpeta en tu PC.
2. Haz doble clic en `index.html` → se abre en tu navegador.
3. O ejecuta `launcher.pyw` → se abre como ventana de aplicación independiente.

## 🌐 Cómo obtener un LINK para compartir por WhatsApp (gratis)

Opción A — **GitHub Pages** (recomendado, link permanente):
1. Crea una cuenta en [github.com](https://github.com).
2. Crea un repositorio público llamado `aicascade-widget`.
3. Sube todos los archivos de esta carpeta.
4. Ve a Settings → Pages → Branch: `main` → Save.
5. En 1-2 minutos tendrás un link como: `https://TU-USUARIO.github.io/aicascade-widget/`
6. Copia ese link y pégalo en WhatsApp.

Opción B — **Netlify Drop** (más rápido, sin cuenta):
1. Ve a [netlify.com](https://netlify.com).
2. Arrastra esta carpeta al área de despliegue.
3. Te dará un link inmediato tipo `https://algo-aleatorio.netlify.app`.
4. Comparte ese link por WhatsApp.

## 📱 Funcionalidades
- Cascada automática de IA: Nivel 1 → 2 → 3 al agotar tokens
- Panel de tokens en tiempo real con porcentaje
- Modo Día (iPhone Plata) / Noche (iPhone Negro)
- Vault de API keys
- Terminal Super Admin
- Atajos a VS Code, GitHub y carpeta del proyecto

## 📞 Soporte
Desarrollado como gestor de cascada inteligente para OpenCode.
