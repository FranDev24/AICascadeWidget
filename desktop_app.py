#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AICascade Desktop - ventana nativa con fallback automatico.

Estrategia:
  1. Sigue asegurando backend (uvicorn :8000) y HUD estatico (:8765).
  2. Abre ventana nativa con pywebview (WebView2).
  3. Si WebView2 no esta listo en LCD_TIMEOUT segundos (o no existe el
     runtime), cierra la ventana y relanza la UI en Chrome/Edge modo
     --app (ventana sin chrome de navegador). Nunca depende del
     navegador por defecto del sistema.
Engine override: AICASCADE_ENGINE=webview|edge|chrome|auto|browser
"""
import os, sys, time, shutil, subprocess, urllib.request, threading

BASE = os.path.dirname(os.path.abspath(__file__))
URLS = ["http://127.0.0.1:8000", "http://127.0.0.1:8765"]
ICO = os.path.join(BASE, "app.ico")
LCD_TIMEOUT = 15  # segundos maximos esperando WebView2 listo

WEBVIEW_READY = threading.Event()


def _ping(url, timeout=2):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _port_up(host="127.0.0.1", port=8000):
    import socket
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def find_browser():
    """Busca Chrome/Edge (x64/x86) y devuelve la ruta completa."""
    exe = "msedge.exe" if sys.platform == "win32" else "msedge"
    for b in (("chrome.exe", "chrome"), ("msedge.exe", "msedge")):
        exe = b[0]
        for pf in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""),
                   os.environ.get("LocalAppData", "")):
            if not pf:
                continue
            cand = os.path.join(pf, "Google", "Chrome", "Application", "chrome.exe") if b[0] == "chrome.exe" \
                else os.path.join(pf, "Microsoft", "Edge", "Application", "msedge.exe")
            if os.path.isfile(cand):
                return cand
    cand = shutil.which(exe)
    return cand


def browser_app_open(url):
    """Abre en Chrome/Edge modo app (ventana standalone). Preferencia Chrome."""
    exe = None
    for browser, exe_name in (("chrome", "chrome.exe"), ("edge", "msedge.exe")):
        folder = "Google/Chrome/Application" if browser == "chrome" else "Microsoft/Edge/Application"
        for pf in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", ""),
                   os.environ.get("LocalAppData", ""), os.environ.get("ProgramW6432", "")):
            if not pf:
                continue
            cand = os.path.join(pf, folder, exe_name)
            if os.path.isfile(cand):
                exe = cand
                break
        if exe:
            break
    if not exe:
        return None
    profile = os.path.join(os.environ.get("LOCALAPPDATA", BASE), "AICascadeWidget", "engine-profile")
    flags = [exe,
             f"--app={url}",
             "--new-window",
             "--window-size=1280,860",
             "--no-first-run",
             "--no-default-browser-check",
             "--disable-features=Translate",
             f"--user-data-dir={profile}"]
    subprocess.Popen(flags, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    return exe


def _pythonw():
    pyw = os.path.join(BASE, "venv", "Scripts", "pythonw.exe")
    return pyw if os.path.isfile(pyw) else sys.executable


def _spawn_bg(code):
    """Ejecuta codigo python en background con logging a archivo (pythonw-safe)."""
    log_dir = os.path.join(BASE, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log = os.path.join(log_dir, "aicascade-services.log")
    quoted = log.replace("\\", "\\\\")
    # El log se abre en el hijo: redirige stdout/stderr antes de importar uvicorn.
    child = ("import sys; f=open(r'%s','a',encoding='utf-8'); "
             "sys.stdout=f; sys.stderr=f; "
             "sys.dont_write_bytecode=True; ") % quoted + code
    subprocess.Popen([_pythonw(), "-c", child],
                     cwd=BASE,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _ensure_backend():
    def _healthy():
        for u in URLS:
            if _ping(u + "/api/health"):
                return True
        return False
    if _healthy():
        return "already-running"
    _spawn_bg(
        "import uvicorn; "
        "uvicorn.run('main:app', host='127.0.0.1', port=8000, log_level='warning')")
    time.sleep(0.8)
    if not _port_up(port=8765):
        _spawn_bg(
            "import runpy, os; "
            "runpy.run_path(os.path.join(r'%s', 'server.py'), run_name='__main__')" % BASE.replace("\\", "\\\\"))
    return "started"


def _wait_ready(timeout=30):
    """Espera hasta que el backend responda /api/health o /."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        for u in URLS:
            if _ping(u + "/api/health") or _ping(u.rstrip("/") + "/"):
                return u
        time.sleep(1)
    return None


def webview_mode(url):
    """Ventana nativa pywebview. Devuelve 'ok'|'timeout'|'error'. Watchdog."""
    try:
        import webview
    except ImportError:
        return "error"
    def _on_loaded():
        WEBVIEW_READY.set()
    w = webview.create_window("AICascade Widget", url, width=1280, height=860,
                              resizable=True, js_api=None)
    w.events.loaded += _on_loaded

    def _watchdog():
        time.sleep(LCD_TIMEOUT)
        if not WEBVIEW_READY.is_set():
            try:
                webview.windows[0].destroy()
            except Exception:
                pass
    webview.start(func=_watchdog, icon=ICO if os.path.exists(ICO) else None)
    return "ok" if WEBVIEW_READY.is_set() else "timeout"


def main():
    engine = os.environ.get("AICASCADE_ENGINE", "auto").lower()
    _ensure_backend()
    url = _wait_ready() or URLS[1]

    if engine == "webview":
        webview_mode(url)
        return
    if engine in ("chrome", "edge", "browser"):
        browser_app_open(url)
        return

    # auto (fiabilidad primero): Chrome/Edge --app; si no hay, pywebview; si
    # nada funciona, navegador por defecto.
    if browser_app_open(url):
        return
    try:
        webview_mode(url)
        return
    except Exception:
        pass
    import webbrowser
    webbrowser.open(url)


if __name__ == "__main__":
    main()
