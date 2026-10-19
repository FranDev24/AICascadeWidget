#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Servidor opcional para AICascade Widget.
Sirve los archivos estáticos y permite conectar con el backend de Python
(cascade_manager.py) si se desea usar modelos reales en lugar de simulados.

Ejecutar: python server.py
Luego abrir: http://localhost:8765
"""

from http.server import HTTPServer, SimpleHTTPRequestHandler
import os
import sys

WEB_DIR = os.path.dirname(os.path.abspath(__file__))

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        # Silenciar logs de petición para mantener limpia la consola
        pass

def main():
    os.chdir(WEB_DIR)
    server = HTTPServer(("127.0.0.1", 8765), Handler)
    print("=" * 50)
    print("  AICascade Widget - Servidor local")
    print("=" * 50)
    print(f"  Directorio: {WEB_DIR}")
    print(f"  URL:        http://127.0.0.1:8765")
    print("  Presiona Ctrl+C para detener")
    print("=" * 50)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
        server.server_close()

if __name__ == "__main__":
    main()
