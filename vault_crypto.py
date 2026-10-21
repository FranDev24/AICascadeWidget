# -*- coding: utf-8 -*-
"""
vault_crypto — Cifrado at-rest de API keys (AICascadeWidget).

Las claves del Vault ya NO se guardan en texto plano en aicascade.db:
se cifran con Windows DPAPI (CryptProtectData, per-usuario y por-maquina,
via ctypes: sin contrasenas externas ni dependencias nuevas).

  Formato en disco:  "dpapi:<base64>"
  Legado (texto plano antiguo): se lee tal cual; se re-cifra al proximo save.
  No-Windows: compatible (se guarda sin cifrar, avisando en el log).

Uso:
    cifrado  = protect("sk-tu-key")        # -> "dpapi:AbCd..."
    original = unprotect(cifrado)          # -> "sk-tu-key"
    original = unprotect("sk-tu-key")      # passthrough legacy
"""
import base64
import ctypes
from ctypes import wintypes
import logging
import os
from typing import Optional

logger = logging.getLogger("vault-crypto")

PREFIX = "dpapi:"
_ENTROPY = "AICascadeWidget::vault::v1::frandev24".encode("utf-8")
_CRYPTPROTECT_UI_FORBIDDEN = 0x1

_WIN = (os.name == "nt")


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _pack(data: bytes) -> _DATA_BLOB:
    buf = ctypes.create_string_buffer(data, len(data))
    return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))


def _unpack(blob: _DATA_BLOB) -> bytes:
    ptr = ctypes.cast(blob.pbData, ctypes.POINTER(ctypes.c_byte))
    out = ctypes.string_at(ptr, blob.cbData)
    ctypes.windll.kernel32.LocalFree(blob.pbData)
    return out


def protect(api_key: str) -> str:
    """Devuelve el formato cifrado dpapi:* para guardar en DB."""
    if not api_key:
        return api_key
    if not _WIN or str(api_key).startswith(PREFIX):
        return api_key
    try:
        inb = _pack(api_key.encode("utf-8"))
        ent = _pack(_ENTROPY)
        out = _DATA_BLOB()
        ok = ctypes.windll.crypt32.CryptProtectDataW(
            ctypes.byref(inb), "AICascade vault key",
            ent, len(_ENTROPY), None, _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out))
        if not ok:
            raise OSError("CryptProtectData fallo (err=%d)"
                          % ctypes.windll.kernel32.GetLastError())
        raw = _unpack(out)
        return PREFIX + base64.b64encode(raw).decode("ascii")
    except Exception as e:  # si el entorno falla, no bloquear la app
        logger.warning("DPAPI no disponible (%s); la clave se guarda sin cifrar", e)
        return api_key


def unprotect(value: Optional[str]) -> Optional[str]:
    """Devuelve la clave original: prefijo dpapi: descifra; plaintext passthrough."""
    if value is None:
        return None
    if not str(value).startswith(PREFIX):
        return value  # legado (plaintext)
    if not _WIN:
        raise OSError("blob dpapi en un sistema no-Windows")
    try:
        raw = base64.b64decode(value[len(PREFIX):])
        inb = _pack(raw)
        ent = _pack(_ENTROPY)
        out = _DATA_BLOB()
        ok = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(inb), None,
            ent, len(_ENTROPY), None, _CRYPTPROTECT_UI_FORBIDDEN,
            ctypes.byref(out))
        if not ok:
            raise OSError("CryptUnprotectData fallo (err=%d)"
                          % ctypes.windll.kernel32.GetLastError())
        return _unpack(out).decode("utf-8")
    except Exception as e:
        # Blob de otra maquina/usuario: informar con detalle y salir limpio.
        logger.error("No se pudo descifrar vault key (LAST user/machine?): %s", e)
        raise ValueError("Vault key ilegible (blob de otra usuario/maquina?): %s" % e) from e
