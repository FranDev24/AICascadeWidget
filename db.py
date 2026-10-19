#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AICascade Widget - Storage Layer:
  1) Supabase (Postgres remoto) si las credenciales funcionan
  2) SQLite local (aicascade.db) como base de datos persistente automatica
Ambas comparten el mismo esquema logico. Todas las operaciones hacen
fallback a SQLite si Supabase falla (RLS, tabla inexistente, red, etc.).
"""

import os
import sqlite3
import threading
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger("aicascade-storage")

DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    os.getenv("SQLITE_DB", "aicascade.db")
)

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS cascade_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    model_from TEXT NOT NULL,
    model_to TEXT NOT NULL,
    reason TEXT,
    tokens_remaining INTEGER DEFAULT 0,
    tier_from INTEGER DEFAULT 1,
    tier_to INTEGER DEFAULT 2,
    session_id TEXT,
    metadata TEXT DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_cl_created ON cascade_logs (created_at DESC);

CREATE TABLE IF NOT EXISTS vault_keys (
    provider TEXT PRIMARY KEY,
    api_key TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    usage_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    active_model TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    total_calls INTEGER DEFAULT 0,
    total_switches INTEGER DEFAULT 0
);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init() -> None:
    with _lock:
        conn = _conn()
        try:
            conn.executescript(SCHEMA)
            conn.commit()
        finally:
            conn.close()
    logger.info(f"SQLite ready: {DB_PATH}")


# ---------------------------------------------------------------- cascade_logs
def insert_log(data: Dict[str, Any]) -> Dict[str, Any]:
    with _lock:
        conn = _conn()
        try:
            cur = conn.execute(
                "INSERT INTO cascade_logs (created_at, model_from, model_to, reason,"
                " tokens_remaining, tier_from, tier_to, session_id, metadata)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    data.get("created_at") or datetime.utcnow().isoformat() + "Z",
                    data.get("model_from", ""),
                    data.get("model_to", ""),
                    data.get("reason") or "manual",
                    data.get("tokens_remaining") or 0,
                    data.get("tier_from") or 1,
                    data.get("tier_to") or 2,
                    data.get("session_id"),
                    data.get("metadata") or "{}",
                ),
            )
            conn.commit()
            row_id = cur.lastrowid
            row = conn.execute(
                "SELECT * FROM cascade_logs WHERE id = ?", (row_id,)).fetchone()
            return dict(row)
        finally:
            conn.close()


def get_logs(limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    with _lock:
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT * FROM cascade_logs ORDER BY id DESC LIMIT ? OFFSET ?",
                (limit, offset)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# ------------------------------------------------------------------ vault_keys
def upsert_key(provider: str, api_key: str, is_active: bool = True) -> None:
    with _lock:
        conn = _conn()
        try:
            conn.execute(
                "INSERT INTO vault_keys (provider, api_key, is_active, created_at)"
                " VALUES (?,?,?,CURRENT_TIMESTAMP)"
                " ON CONFLICT(provider) DO UPDATE SET api_key=excluded.api_key,"
                " is_active=excluded.is_active",
                (provider, api_key, int(is_active)),
            )
            conn.commit()
        finally:
            conn.close()


def get_key(provider: str) -> Optional[str]:
    with _lock:
        conn = _conn()
        try:
            row = conn.execute(
                "SELECT api_key FROM vault_keys WHERE provider=? AND is_active=1",
                (provider,)).fetchone()
            return row["api_key"] if row else None
        finally:
            conn.close()


def get_keys() -> List[Dict[str, Any]]:
    with _lock:
        conn = _conn()
        try:
            rows = conn.execute(
                "SELECT provider, api_key, is_active, created_at, usage_count"
                " FROM vault_keys ORDER BY provider").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def deactivate_key(provider: str) -> bool:
    with _lock:
        conn = _conn()
        try:
            cur = conn.execute(
                "UPDATE vault_keys SET is_active=0 WHERE provider=?", (provider,))
            conn.commit()
            return cur.rowcount > 0
        finally:
            conn.close()


def touch_key(provider: str) -> None:
    with _lock:
        conn = _conn()
        try:
            conn.execute(
                "UPDATE vault_keys SET usage_count = usage_count + 1 WHERE provider=?",
                (provider,))
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()
