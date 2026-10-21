# -*- coding: utf-8 -*-
"""
cascadeengine.core.backoff — Reintentos con Exponential Backoff + Full Jitter.

Referencias: AWS Architecture Blog (M. Brooker, 2015) / Google SRE Book cap.22.
DELEGA a core/module.py (implementacion real compartida con engine.py).
"""
from cascadeengine.core.module import (
    Backoff,
    BackoffJitter,
    exponential_backoff_with_jitter,
    retry_with_backoff,
)

__all__ = ["Backoff", "BackoffJitter", "exponential_backoff_with_jitter", "retry_with_backoff"]
