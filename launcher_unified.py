#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AICascade Widget - Unified Launcher
Starts both the FastAPI backend (port 8000) and the static file server (port 8765).
"""

import os
import sys
import subprocess
import time
import signal
import threading
from pathlib import Path

WEB_DIR = Path(__file__).parent.absolute()
BACKEND_DIR = WEB_DIR

processes = []

def start_backend():
    """Start FastAPI backend on port 8000."""
    print("[BACKEND] Starting FastAPI backend on http://127.0.0.1:8000")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0
    )
    processes.append(("Backend", proc))
    return proc

def start_frontend():
    """Start static file server on port 8765."""
    print("[FRONTEND] Starting frontend server on http://127.0.0.1:8765")
    proc = subprocess.Popen(
        [sys.executable, "server.py"],
        cwd=WEB_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, "CREATE_NEW_PROCESS_GROUP") else 0
    )
    processes.append(("Frontend", proc))
    return proc

def monitor_process(name, proc):
    """Monitor process output."""
    try:
        for line in iter(proc.stdout.readline, ''):
            if line:
                print(f"[{name}] {line.rstrip()}")
    except Exception:
        pass

def signal_handler(sig, frame):
    """Handle shutdown signals."""
    print("\n[STOP] Shutting down all services...")
    for name, proc in processes:
        try:
            if hasattr(proc, 'send_signal'):
                proc.send_signal(signal.CTRL_BREAK_EVENT if sys.platform == 'win32' else signal.SIGTERM)
            else:
                proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    sys.exit(0)

def main():
    print("=" * 60)
    print("  AICascade Widget - Unified Launcher")
    print("=" * 60)
    print(f"[DIR] Working directory: {WEB_DIR}")
    print()

    # Check for .env
    env_path = WEB_DIR / ".env"
    if not env_path.exists():
        print("[WARN] No .env file found. Creating template...")
        # The .env was already created by the setup

    # Start backend
    backend_proc = start_backend()
    backend_thread = threading.Thread(target=monitor_process, args=("BACKEND", backend_proc), daemon=True)
    backend_thread.start()

    # Wait for backend to start
    time.sleep(2)

    # Start frontend
    frontend_proc = start_frontend()
    frontend_thread = threading.Thread(target=monitor_process, args=("FRONTEND", frontend_proc), daemon=True)
    frontend_thread.start()

    # Wait a bit for frontend
    time.sleep(1.5)

    print()
    print("=" * 60)
    print("  AICascade Widget is running!")
    print("=" * 60)
    print("  Frontend (Widget):  http://127.0.0.1:8765")
    print("  Backend (API):      http://127.0.0.1:8000")
    print("  API Docs (Swagger): http://127.0.0.1:8000/docs")
    print("  API Docs (ReDoc):   http://127.0.0.1:8000/redoc")
    print()
    print("  Press Ctrl+C to stop all services")
    print("=" * 60)

    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, signal_handler)

    # Keep running
    try:
        while True:
            time.sleep(1)
            # Check if processes are still alive
            for name, proc in processes:
                if proc.poll() is not None:
                    print(f"[WARN] {name} process exited unexpectedly")
    except KeyboardInterrupt:
        signal_handler(signal.SIGINT, None)

if __name__ == "__main__":
    main()