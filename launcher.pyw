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
SERVER_URL = "http://127.0.0.1:8765"

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
    """Inicia server.py en segundo plano si python está disponible."""
    server_path = os.path.join(WEB_DIR, "server.py")
    if not os.path.isfile(server_path):
        return
    try:
        subprocess.Popen(
            [sys.executable, server_path],
            cwd=WEB_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        time.sleep(1.5)
    except Exception:
        pass


def main():
    start_server()

    browser = find_browser()
    if browser:
        try:
            subprocess.Popen(
                [browser, f"--app={SERVER_URL}", "--new-window"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("AICascade Widget abierto en ventana de escritorio (modo app).")
            return
        except Exception:
            pass

    # Fallback: abrir archivo HTML directamente
    webbrowser.open(f"file:///{INDEX_FILE}")
    print("AICascade Widget abierto en el navegador predeterminado.")


if __name__ == "__main__":
    main()
