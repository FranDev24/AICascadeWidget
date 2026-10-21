// ============================================================================
// AICascade Widget — Puente Frontend <-> Backend FastAPI
// Detecta el backend en 127.0.0.1:8000 y expone window.AIBackend.
// Si el backend no responde, el HUD sigue funcionando en modo local.
// ============================================================================

window.AIBackend = {
  baseUrl: "http://127.0.0.1:8000",
  online: false,
  store: "local",

  async ping() {
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 3000);
      const r = await fetch(this.baseUrl + "/api/health", { signal: ctrl.signal });
      clearTimeout(t);
      if (!r.ok) throw new Error("HTTP " + r.status);
      const j = await r.json();
      this.online = true;
      // Compat: OpenCode renombro a supabase_connected + store sqlite/supabase.
      // Se aceptan ambas claves para no romper el badge del HUD.
      const isSb = !!(j.supabase_connected ?? j.supabase_configured);
      this.store = j.store || (isSb ? "supabase" : "local");
      return j;
    } catch (e) {
      this.online = false;
      return null;
    }
  },

  async logFailover(modelFrom, modelTo, reason, tokensRemaining) {
    if (!this.online) return null;
    try {
      const r = await fetch(this.baseUrl + "/api/cascade/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ model_from: modelFrom, model_to: modelTo,
          reason: reason || null, tokens_remaining: tokensRemaining ?? null }),
      });
      return await r.json();
    } catch (e) { return null; }
  },

  async saveVaultKey(provider, apiKey) {
    if (!this.online) return null;
    try {
      const r = await fetch(this.baseUrl + "/api/vault/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ provider, api_key: apiKey }),
      });
      return await r.json();
    } catch (e) { return null; }
  },

  async chat(message, model) {
    const r = await fetch(this.baseUrl + "/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, model: model || null }),
    });
    if (!r.ok) throw new Error("Backend chat HTTP " + r.status);
    return await r.json();
  },

  async getModels() {
    try {
      const r = await fetch(this.baseUrl + "/api/cascade/models", {
        headers: { "Content-Type": "application/json" },
      });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) { return null; }
  },

  async getProviderStatus() {
    try {
      const r = await fetch(this.baseUrl + "/api/vault/status", {
        headers: { "Content-Type": "application/json" },
      });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) { return null; }
  },

  async updateBadge() {
    const el = document.getElementById("backendStatus");
    const h = await this.ping();
    if (!el) return h;
    if (h) {
      el.innerHTML = '<span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>'
        + '<span>Backend ' + (this.store === "supabase" ? "● Supabase" : "● Local") + "</span>";
      el.className = el.className.replace(/text-\S+-600/g, "").trim()
        + " text-green-600";
    } else {
      el.innerHTML = '<span class="w-2 h-2 rounded-full bg-amber-500"></span>'
        + "<span>Backend offline — modo local</span>";
    }
    // Al (re)conectarse, sincronizar keys del Vault local → backend una sola vez
    if (h && !this._synced) {
      this._synced = true;
      try { if (window.vault) vault.syncToBackend(); } catch (e) {}
    }
    if (!h) this._synced = false;
    return h;
  },
};

document.addEventListener("DOMContentLoaded", () => {
  window.AIBackend.updateBadge();
  setInterval(() => window.AIBackend.updateBadge(), 15000);
});
