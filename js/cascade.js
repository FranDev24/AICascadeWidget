// ============================================================================
// AICascade Widget — Lógica de Cascada de IA (JavaScript)
// ============================================================================

class CascadeManager {
  constructor() {
    this.sessionId = 'sesion-' + Math.random().toString(36).substr(2, 9);
    this.models = [
      // Nivel 1 - Ultra / Flagship
      { name: 'Claude 3.5 Sonnet', tier: 1, tpmLimit: 40000, tpdLimit: 400000, contextWindow: 200000, provider: 'Anthropic', enabled: true, used: 0, errors: 0, calls: 0, latencies: [] },
      { name: 'Gemini 1.5 Pro', tier: 1, tpmLimit: 30000, tpdLimit: 300000, contextWindow: 2000000, provider: 'Google', enabled: true, used: 0, errors: 0, calls: 0, latencies: [] },
      { name: 'GPT-4o', tier: 1, tpmLimit: 20000, tpdLimit: 200000, contextWindow: 128000, provider: 'OpenAI', enabled: true, used: 0, errors: 0, calls: 0, latencies: [] },
      // Nivel 2 - Mid-Tier
      { name: 'GPT-4o-mini', tier: 2, tpmLimit: 40000, tpdLimit: 400000, contextWindow: 128000, provider: 'OpenAI', enabled: true, used: 0, errors: 0, calls: 0, latencies: [] },
      { name: 'Claude 3 Haiku', tier: 2, tpmLimit: 30000, tpdLimit: 300000, contextWindow: 200000, provider: 'Anthropic', enabled: true, used: 0, errors: 0, calls: 0, latencies: [] },
      { name: 'Llama 3.1 70B', tier: 2, tpmLimit: 25000, tpdLimit: 250000, contextWindow: 128000, provider: 'Meta', enabled: true, used: 0, errors: 0, calls: 0, latencies: [] },
      // Nivel 3 - Fast / Light
      { name: 'Gemini 1.5 Flash', tier: 3, tpmLimit: 50000, tpdLimit: 500000, contextWindow: 1000000, provider: 'Google', enabled: true, used: 0, errors: 0, calls: 0, latencies: [] },
      { name: 'Llama 3.1 8B', tier: 3, tpmLimit: 60000, tpdLimit: 600000, contextWindow: 128000, provider: 'Meta', enabled: true, used: 0, errors: 0, calls: 0, latencies: [] },
      { name: 'DeepSeek V2 Lite', tier: 3, tpmLimit: 40000, tpdLimit: 400000, contextWindow: 128000, provider: 'DeepSeek', enabled: true, used: 0, errors: 0, calls: 0, latencies: [] },
    ];
    this.activeModel = null;
    this.totalSwitches = 0;
    this.totalCalls = 0;
    this.activityLog = [];
    this.metrics = { totalInputTokens: 0, totalOutputTokens: 0, totalLatencyMs: 0, errorsByModel: {} };
    this.listeners = {};
    this.estimateTokens = (text) => Math.ceil(String(text || '').length / 4);
    this._loadState();
  }

  // ---------- Eventos (para streaming/UI) ----------
  on(evt, fn) {
    if (!this.listeners[evt]) this.listeners[evt] = [];
    this.listeners[evt].push(fn);
    return () => { this.listeners[evt] = this.listeners[evt].filter(f => f !== fn); };
  }

  emit(evt, data) {
    (this.listeners[evt] || []).forEach(fn => { try { fn(data); } catch (e) {} });
  }

  // ---------- Persistencia local ----------
  _saveState() {
    try {
      localStorage.setItem('aicascade_cascade_state_v2', JSON.stringify({
        models: this.models.map(m => ({ name: m.name, used: m.used, errors: m.errors, calls: m.calls, enabled: m.enabled })),
        activeModel: this.activeModel ? this.activeModel.name : null,
        totalSwitches: this.totalSwitches,
        totalCalls: this.totalCalls,
        metrics: this.metrics,
      }));
    } catch (e) {}
  }

  _loadState() {
    try {
      const raw = localStorage.getItem('aicascade_cascade_state_v2');
      if (!raw) return;
      const s = JSON.parse(raw);
      (s.models || []).forEach(sm => {
        const m = this.models.find(x => x.name === sm.name);
        if (m) { m.used = sm.used || 0; m.errors = sm.errors || 0; m.calls = sm.calls || 0; m.enabled = sm.enabled !== false; }
      });
      if (s.activeModel) this.activeModel = this.models.find(m => m.name === s.activeModel) || null;
      this.totalSwitches = s.totalSwitches || 0;
      this.totalCalls = s.totalCalls || 0;
      if (s.metrics) this.metrics = Object.assign(this.metrics, s.metrics);
    } catch (e) {}
  }

  resetUsage() {
    this.models.forEach(m => { m.used = 0; m.errors = 0; m.calls = 0; m.latencies = []; });
    this.metrics = { totalInputTokens: 0, totalOutputTokens: 0, totalLatencyMs: 0, errorsByModel: {} };
    this._saveState();
    this.addLog('Contadores reiniciados', 'success');
    this.emit('usage-reset', {});
  }

  toggleModel(name) {
    const m = this.models.find(x => x.name === name);
    if (!m) return false;
    m.enabled = !m.enabled;
    if (!m.enabled && this.activeModel && this.activeModel.name === name) {
      const best = this.selectBestAvailable();
      if (best) this.switchModel(best, 'modelo_deshabilitado');
    }
    this._saveState();
    this.emit('models-changed', { name, enabled: m.enabled });
    return m.enabled;
  }

  // ---------- Métricas reales ----------
  avgLatency(model) {
    if (!model.latencies || !model.latencies.length) return 0;
    return Math.round(model.latencies.reduce((a, b) => a + b, 0) / model.latencies.length);
  }

  getMetrics() {
    const total = this.metrics.totalInputTokens + this.metrics.totalOutputTokens;
    return {
      totalCalls: this.totalCalls,
      totalSwitches: this.totalSwitches,
      totalInputTokens: this.metrics.totalInputTokens,
      totalOutputTokens: this.metrics.totalOutputTokens,
      totalTokens: total,
      avgLatencyMs: this.totalCalls ? Math.round(this.metrics.totalLatencyMs / this.totalCalls) : 0,
      errorRate: this.totalCalls ? ((Object.values(this.metrics.errorsByModel).reduce((a, b) => a + b, 0) / this.totalCalls) * 100).toFixed(1) + '%' : '0%',
      perModel: this.models.map(m => ({ name: m.name, tier: m.tier, calls: m.calls, errors: m.errors, used: m.used, avgLatencyMs: this.avgLatency(m) })),
    };
  }

  // Failover inteligente: puntúa por tier, errores, latencia y cuota
  scoreModel(m) {
    if (!m.enabled) return -1;
    if (m.used >= m.tpmLimit) return -1;
    let score = 100 - (m.tier - 1) * 25;
    score -= Math.min(30, m.errors * 5);
    const lat = this.avgLatency(m);
    if (lat > 3000) score -= 10;
    else if (lat > 1500) score -= 5;
    score -= (m.used / Math.max(1, m.tpmLimit)) * 20;
    return Math.max(0, score);
  }

  // Seleccionar el mejor modelo disponible (más potente con cuota)
  selectBestAvailable() {
    let best = null;
    let bestScore = -1;
    for (const m of this.models) {
      const s = this.scoreModel(m);
      if (s > bestScore) { bestScore = s; best = m; }
    }
    return best;
  }

  // Obtener siguiente modelo de nivel inferior
  nextTierModel(current) {
    const idx = this.models.findIndex(m => m.name === current.name);
    if (idx === -1) return null;
    for (let i = idx + 1; i < this.models.length; i++) {
      if (this.models[i].tier > current.tier) return this.models[i];
    }
    return null;
  }

  // Intentar failback al nivel 1 si recuperó cuota
  attemptFailback() {
    for (const m of this.models) {
      if (m.tier === 1 && m.used < m.tpmLimit) return m;
    }
    return null;
  }

  recordUsage(model, inputTokens, outputTokens, success, latencyMs) {
    model.used += inputTokens + outputTokens;
    model.calls += 1;
    if (latencyMs != null) {
      model.latencies.push(latencyMs);
      if (model.latencies.length > 20) model.latencies.shift();
      this.metrics.totalLatencyMs += latencyMs;
    }
    this.metrics.totalInputTokens += inputTokens;
    this.metrics.totalOutputTokens += outputTokens;
    if (!success) {
      model.errors += 1;
      this.metrics.errorsByModel[model.name] = (this.metrics.errorsByModel[model.name] || 0) + 1;
    }
    this._saveState();
  }

  getTokenState(model) {
    if (!model) return 'critical';
    const pct = model.used / Math.max(1, model.tpmLimit);
    if (pct >= 0.9) return 'critical';
    if (pct >= 0.6) return 'moderate';
    return 'optimal';
  }

  addLog(message, type = 'info') {
    this.activityLog.unshift({
      time: new Date().toLocaleTimeString('es-ES', { hour12: false }),
      message,
      type
    });
    if (this.activityLog.length > 50) this.activityLog.pop();
    if (window.app && window.app.renderActivityLog) {
      window.app.renderActivityLog();
    }
  }

  diagnosticBlock(action) {
    const state = this.getTokenState(this.activeModel);
    const stateLabel = {
      optimal: 'Óptimo',
      moderate: 'Moderado',
      critical: 'Crítico / Cambiando...'
    }[state] || 'Desconocido';
    return [
      '[ESTADO DE CASCADA]',
      `• Modelo Activo: ${this.activeModel ? this.activeModel.name : 'Ninguno'} (Nivel ${this.activeModel ? this.activeModel.tier : 'N/A'})`,
      `• Estado de Tokens: ${stateLabel}`,
      `• Acción: ${action || 'Continuando'}`
    ].join('\n');
  }

  getStatus() {
    if (!this.activeModel) {
      return {
        activeModel: 'Ninguno',
        activeTier: 'Sin asignar',
        totalTokens: '0 / 0',
        remainingTokens: '0 (0%)',
        pctUsed: 0,
        pctRemaining: 100,
        statusText: 'Sin asignar',
        statusColor: 'text-gray-400',
        dotColor: 'bg-gray-400',
        switchCount: this.totalSwitches,
        callCount: this.totalCalls,
        models: this.models.map(m => ({
          name: m.name,
          tier: m.tier,
          provider: m.provider,
          used: m.used,
          limit: m.tpmLimit,
          pct: Math.round((m.used / Math.max(1, m.tpmLimit)) * 100),
          errors: m.errors,
          calls: m.calls
        }))
      };
    }
    const m = this.activeModel;
    const pct = Math.round((m.used / Math.max(1, m.tpmLimit)) * 100);
    const state = this.getTokenState(m);
    const statusMap = {
      optimal: { text: 'Óptimo', color: 'text-green-600', dot: 'bg-green-400' },
      moderate: { text: 'Moderado', color: 'text-amber-600', dot: 'bg-amber-500' },
      critical: { text: 'Crítico / Cambiando...', color: 'text-rose-500', dot: 'bg-rose-500' }
    }[state];
    return {
      activeModel: m.name,
      activeTier: `Nivel ${m.tier} — ${m.tier === 1 ? 'Ultra/Flagship' : m.tier === 2 ? 'Mid/Balanceado' : 'Fast/Light'}`,
      totalTokens: `${m.used.toLocaleString()} / ${m.tpmLimit.toLocaleString()}`,
      remainingTokens: `${Math.max(0, m.tpmLimit - m.used).toLocaleString()} (${100 - pct}%)`,
      pctUsed: pct,
      pctRemaining: 100 - pct,
      statusText: statusMap.text,
      statusColor: statusMap.color,
      dotColor: statusMap.dot,
      switchCount: this.totalSwitches,
      callCount: this.totalCalls,
      models: this.models.map(mm => ({
        name: mm.name,
        tier: mm.tier,
        provider: mm.provider,
        used: mm.used,
        limit: mm.tpmLimit,
        pct: Math.round((mm.used / Math.max(1, mm.tpmLimit)) * 100),
        errors: mm.errors,
        calls: mm.calls
      }))
    };
  }

  // Ejecutar a través de la cascada
  async execute(prompt, modelCall, context = null) {
    const start = performance.now();
    this.totalCalls++;
    const attempts = [];
    const ctx = context || { sessionId: this.sessionId, taskDescription: 'Tarea', ultimoPaso: 'Inicio', pasosPendientes: [] };

    // Failback si estamos en nivel inferior y el Nivel 1 se restauró
    if (this.activeModel && this.activeModel.tier > 1) {
      const mejor = this.attemptFailback();
      if (mejor && mejor.name !== this.activeModel.name) {
        this.switchModel(mejor, 'failback');
      }
    }

    if (!this.activeModel) {
      const best = this.selectBestAvailable();
      if (!best) {
        return this._result(false, 'Ninguno', 0, null, null, 'No hay modelos con cuota disponible', attempts, start);
      }
      this.switchModel(best, 'inicio', true);
    }

    let current = this.activeModel;

    while (true) {
      const u = current;
      if (u.used >= u.tpmLimit) {
        attempts.push({ model: u.name, tier: u.tier, skipped: true, reason: 'cuota_agotada' });
        const nxt = this.nextTierModel(current);
        if (nxt) {
          this.switchModel(nxt, 'cuota_agotada');
          current = this.activeModel;
          continue;
        }
        break;
      }

      const estIn = this.estimateTokens(prompt);
      try {
        const callStart = performance.now();
        const response = await modelCall(prompt, current);
        const callMs = Math.round(performance.now() - callStart);
        const estOut = this.estimateTokens(String(response));
        this.recordUsage(current, estIn, estOut, true, callMs);
        this.emit('token', { model: current.name, text: String(response).substring(0, 4000), latencyMs: callMs });

        const latencyMs = performance.now() - start;
        const switched = window.app ? window.app._switched : false;
        const swFrom = window.app ? window.app._switchedFrom : null;
        if (window.app) { window.app._switched = false; window.app._switchedFrom = null; }

        return this._result(true, current.name, current.tier, response, u, null, attempts, start, switched, swFrom);
      } catch (exc) {
        u.errors += 1;
        attempts.push({ model: u.name, tier: u.tier, error: String(exc), reason: exc.constructor.name });
        const nxt = this.nextTierModel(current);
        if (nxt) {
          this.switchModel(nxt, String(exc));
          current = this.activeModel;
          // Reinyectar contexto al nuevo modelo
          continue;
        }
        break;
      }
    }

    return this._result(false, current ? current.name : 'Ninguno', current ? current.tier : 0, null, current, 'Todos los modelos de la cascada agotados o fallidos', attempts, start);
  }

  switchModel(newModel, reason, initial = false) {
    const old = this.activeModel;
    const oldName = old ? old.name : 'inicio';
    const newName = typeof newModel === 'string' ? newModel : newModel.name;
    this.activeModel = typeof newModel === 'string'
      ? (this.models.find(m => m.name === newModel) || old)
      : newModel;
    this.totalSwitches++;
    if (!initial) {
      this._switched = true;
      this._switchedFrom = old ? old.name : null;
    }
    this.addLog(`Conmutado ${oldName} → ${newName} (${reason})`);
    // Persistir en backend/Supabase sin bloquear la UI
    try {
      if (window.AIBackend && window.AIBackend.online) {
        const remaining = this.activeModel
          ? Math.max(0, this.activeModel.tpmLimit - this.activeModel.used) : null;
        window.AIBackend.logFailover(oldName, newName, String(reason || ''), remaining);
      }
    } catch (e) { /* modo local */ }
  }

  _result(success, modelUsed, tierUsed, response, tokenUsage, error, attempts, start, switched = false, fromModel = null) {
    return {
      success,
      modelUsed,
      tierUsed,
      response,
      tokenUsage,
      error,
      switched,
      fromModel,
      toModel: modelUsed,
      attempts,
      latencyMs: performance.now() - start
    };
  }

  runFailover() {
    if (!this.activeModel) return;
    const nxt = this.nextTierModel(this.activeModel);
    if (nxt) {
      this.switchModel(nxt, 'failover_manual');
      return nxt;
    }
    return null;
  }
}

const cascade = new CascadeManager();

// Exponer global para onclick="cascade.*" y uso desde app/terminal/palette
window.cascade = cascade;

// Modelo simulado para demostración (sin API keys)
// Cuotas con ventana por minuto (como proveedores reales): los modelos
// se agotan, entran en cooldown y se RECUPERAN solos → la cascada nunca muere.
function createSimulatedDispatcher() {
  const WINDOW_MS = 60000; // ventana de 1 minuto
  const simulados = {
    'Claude 3.5 Sonnet': { limit: 2, calls: 0, windowStart: 0 },
    'Gemini 1.5 Pro': { limit: 2, calls: 0, windowStart: 0 },
    'GPT-4o': { limit: 2, calls: 0, windowStart: 0 },
    'GPT-4o-mini': { limit: 4, calls: 0, windowStart: 0 },
    'Claude 3 Haiku': { limit: 4, calls: 0, windowStart: 0 },
    'Llama 3.1 70B': { limit: 4, calls: 0, windowStart: 0 },
    'Gemini 1.5 Flash': { limit: 10, calls: 0, windowStart: 0 },
    'Llama 3.1 8B': { limit: 10, calls: 0, windowStart: 0 },
    'DeepSeek V2 Lite': { limit: 10, calls: 0, windowStart: 0 },
  };

  return async (prompt, modelo) => {
    const sim = simulados[modelo.name];
    if (!sim) return `[SIMULADO] Respuesta de ${modelo.name}`;
    const now = Date.now();
    // Ventana rotatoria: si pasó 1 minuto, la cuota se reinicia (auto-sanación)
    if (sim.windowStart && now - sim.windowStart >= WINDOW_MS) {
      sim.calls = 0;
      sim.windowStart = 0;
    }
    if (!sim.windowStart) sim.windowStart = now;
    sim.calls++;
    const waitMs = Math.max(0, WINDOW_MS - (Date.now() - sim.windowStart));
    if (sim.calls > sim.limit) {
      throw new Error(`${modelo.name}: 429 Too Many Requests (cuota por minuto agotada, se recupera en ${Math.ceil(waitMs / 1000)}s)`);
    }
    // Simular latencia de red
    await new Promise(r => setTimeout(r, 400 + Math.random() * 600));
    return `[SIMULADO] Respuesta de ${modelo.name} (llamada ${sim.calls}/${sim.limit} esta ventana)\n\nProcesado: "${prompt.substring(0, 60)}..."`;
  };
}

const dispatcher = createSimulatedDispatcher();

// Ejecutar chat a través de la cascada
async function cascadeChat(mensaje) {
  const ctx = {
    sessionId: cascade.sessionId,
    taskDescription: 'Asistencia general',
    ultimoPaso: `Usuario: ${mensaje.substring(0, 80)}...`,
    pasosPendientes: []
  };

  const resultado = await cascade.execute(mensaje, dispatcher, ctx);

  if (!resultado.success) {
    const intentos = resultado.attempts.map(a => a.model).join(', ') || 'ninguno';
    return {
      success: false,
      html: `
        <div class="p-4 bg-rose-50 border border-rose-100 rounded-xl">
          <div class="text-rose-800 font-medium">[ERROR] ${resultado.error}</div>
          <div class="text-rose-600 text-sm mt-1">Modelos intentados: ${intentos}</div>
        </div>
        <div class="mt-3 text-xs text-gray-500 font-mono">${cascade.diagnosticBlock('Sesión detenida')}</div>
      `
    };
  }

  const status = cascade.getStatus();
  return {
    success: true,
    modelUsed: resultado.modelUsed,
    tier: resultado.tierUsed,
    response: resultado.response,
    html: `
      <div class="text-sm text-gray-700">${resultado.response}</div>
      <div class="mt-3 text-xs text-gray-500 font-mono">${cascade.diagnosticBlock('Continuando')}</div>
    `,
    status
  };
}
