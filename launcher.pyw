#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Launcher de AICascade Widget como aplicación de escritorio.
Intenta abrir el widget en modo ventana (sin barra de navegador) usando
Chrome o Edge en modo --app. Si no los encuentra, abre el navegador predeterminado.
"""

import os
import subprocess
import sys
import webbrowser
import time

WEB_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(WEB_DIR, "index.html")
BACKEND_URL = "http://127.0.0.1:8000"
HUD_URL = "http://127.0.0.1:8765"
# Compat: OpenCode usaba SERVER_URL=:8765; se mantiene como fallback
SERVER_URL = HUD_URL

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
EDGE_PATHS = [
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]


def find_browser():
    for path in CHROME_PATHS + EDGE_PATHS:
        if os.path.isfile(path):
            return path
    return None


def start_server():
    """Inicia backend :8000 + HUD :8765 en segundo plano (mejora aditiva)."""
    import urllib.request
    def _up(url):
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=2) as r:
                return r.status == 200
        except Exception:
            return False
    if _up("http://127.0.0.1:8000"):
        return
    venv_py = os.path.join(WEB_DIR, "venv", "Scripts", "python.exe")
    py = venv_py if os.path.isfile(venv_py) else sys.executable
    try:
        subprocess.Popen(
            [py, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=WEB_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
    except Exception:
        pass
    server_path = os.path.join(WEB_DIR, "server.py")
    if os.path.isfile(server_path):
        try:
            subprocess.Popen(
                [py, server_path],
                cwd=WEB_DIR,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
        except Exception:
            pass
    # Esperar backend hasta 20s (evita ECONNREFUSED al abrir)
    for _ in range(20):
        if _up("http://127.0.0.1:8000"):
            break
        time.sleep(1)


def main():
    start_server()

    # Preferir backend :8000 (API+widget). Fallback HUD :8765.
    import urllib.request
    def _up(url):
        try:
            with urllib.request.urlopen(url + "/api/health", timeout=2) as r:
                return r.status == 200
        except Exception:
            return False
    target = BACKEND_URL if _up(BACKEND_URL) else (HUD_URL if _up(HUD_URL) else BACKEND_URL)

    browser = find_browser()
    if browser:
        try:
            subprocess.Popen(
                [browser, f"--app={target}", "--new-window"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"AICascade Widget abierto en ventana de escritorio ({target}).")
            return
        except Exception:
            pass

    # Fallback: backend directo (mejor que file:// porque file:// rompe fetch/CORS)
    try:
        webbrowser.open(target)
        print(f"AICascade Widget abierto en navegador ({target}).")
        return
    except Exception:
        pass
    webbrowser.open(f"file:///{INDEX_FILE}")
    print("AICascade Widget abierto en el navegador predeterminado.")


if __name__ == "__main__":
    main()
