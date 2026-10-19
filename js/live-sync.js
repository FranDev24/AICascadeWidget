// ============================================================================
// AICascade Widget — Live Sync con Backend (Supabase/SQLite vía FastAPI)
// Sincroniza tokens, porcentajes, niveles y cascada en tiempo real.
// Sin alucinaciones: solo consume endpoints reales definidos en main.py.
// ============================================================================

const LiveSync = {
  baseUrl: "http://127.0.0.1:8000",
  online: false,
  intervalMs: 30000,
  _timer: null,
  _lastTier: null,

  async init() {
    await this.ping();
    if (this.online) {
      await this.sync();
      this.startPolling();
    }
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden && this.online) this.sync();
    });
  },

  async ping() {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 3000);
      const r = await fetch(this.baseUrl + "/api/health", { signal: ctrl.signal });
      clearTimeout(t);
      if (!r.ok) throw new Error("HTTP " + r.status);
      await r.json();
      this.online = true;
      return true;
    } catch (e) {
      this.online = false;
      return null;
    }
  },

  startPolling() {
    if (this._timer) clearInterval(this._timer);
    this._timer = setInterval(() => this.sync(), this.intervalMs);
  },

  stopPolling() {
    if (this._timer) { clearInterval(this._timer); this._timer = null; }
  },

  async sync() {
    if (!this.online) return;
    try {
      const [telRes, logsRes] = await Promise.all([
        fetch(this.baseUrl + "/api/cascade/telemetry"),
        fetch(this.baseUrl + "/api/cascade/logs?limit=50")
      ]);
      const telemetry = await telRes.json();
      const logsData = await logsRes.json();
      // La API de telemetry devuelve métricas directas (sin campo .ok)
      if (!telemetry || typeof telemetry.total_switches !== "number") return;

      const currentModel = telemetry.current_model;
      const currentTier = telemetry.current_tier;

      // Modelo actual desde la BD -> cascada local (fuente única de verdad)
      if (currentModel && currentModel !== cascade.activeModel?.name) {
        const m = cascade.models.find(x => x.name === currentModel);
        if (m) cascade.switchModel(m, "backend_sync", true);
      }

      // Agregar llamadas/errores por modelo desde los logs persistidos
      const logs = logsData.logs || [];
      const byModel = {};
      for (const l of logs) {
        const mt = l.model_to;
        if (!mt) continue;
        if (!byModel[mt]) byModel[mt] = { used: 0, errors: 0, calls: 0, tier: l.tier_to };
        byModel[mt].calls += 1;
        if (l.reason === "error" || l.reason === "quota_exceeded") byModel[mt].errors += 1;
      }
      for (const m of cascade.models) {
        const bm = byModel[m.name];
        if (bm) {
          m.calls = bm.calls;
          m.errors = bm.errors;
          if (bm.tier) m.tier = bm.tier;
        }
      }

      this.updateDomValues();
      if (currentTier && this._lastTier != null && this._lastTier !== currentTier) {
        this.announceTierChange(this._lastTier, currentTier);
      }
      this._lastTier = currentTier;
    } catch (e) {
      console.debug("[LiveSync] sync falló:", e.message);
    }
  },

  // Delegar el render en app.render() (usa cascade.getStatus()) para evitar
  // parpadeos y mantener una única fuente de verdad visual.
  updateDomValues() {
    if (window.app && typeof window.app.render === 'function') {
      window.app.render();
    }
  },

  announceTierChange(fromTier, toTier) {
    const tierEl = document.getElementById('activeTier');
    if (tierEl) {
      tierEl.classList.add('switching');
      setTimeout(() => tierEl.classList.remove('switching'), 600);
    }
    if (window.app && typeof window.app.showToast === 'function') {
      const names = { 1: 'Ultra', 2: 'Mid', 3: 'Light' };
      window.app.showToast(
        'Cascada IA',
        'Cambio de nivel detectado en backend: Nivel ' + fromTier + ' → Nivel ' + toTier
          + ' (' + (names[toTier] || toTier) + ')',
        'info'
      );
    }
  },

  async logFailover(modelFrom, modelTo, reason, tokensRemaining, tierFrom, tierTo) {
    if (!this.online) return null;
    try {
      const r = await fetch(this.baseUrl + "/api/cascade/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model_from: modelFrom,
          model_to: modelTo,
          reason: reason || "manual",
          tokens_remaining: tokensRemaining ?? null,
          tier_from: tierFrom ?? null,
          tier_to: tierTo ?? null,
          session_id: cascade.sessionId,
          metadata: { source: "frontend-live-sync" }
        })
      });
      return await r.json();
    } catch (e) {
      console.debug("[LiveSync] logFailover falló:", e.message);
      return null;
    }
  }
};

// Exponer global
window.LiveSync = LiveSync;

// Auto-inicializar cuando el DOM esté listo (app.init también lo llama)
document.addEventListener("DOMContentLoaded", () => {
  LiveSync.init();
});
