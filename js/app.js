// ============================================================================
// AICascade Widget — Orquestador Principal (App)
// ============================================================================

const app = {
  currentPanel: 'dashboard',
  _switched: false,
  _switchedFrom: null,
  _chatBusy: false,
  _selectedModel: 'cascade-auto',
  _suggestionsOpen: false,
  _models: [],
  _voiceActive: false,

  init() {
    this.bindEvents();
    this.startClock();
    // Seleccionar modelo inicial para que el dashboard no nazca en "Ninguno"
    if (!cascade.activeModel) {
      const best = cascade.selectBestAvailable();
      if (best) cascade.switchModel(best, 'inicio', true);
    }
    cascade.addLog('Sistema iniciado — Gestor de cascada listo');
    this.render();
    // Auto-actualizacion de numeros/porcentajes cada 10s (siempre vivos)
    setInterval(() => { try { this.render(); } catch (e) {} }, 10000);
    // Telemetría del backend en vivo cada 15s (contadores persistentes)
    setInterval(() => this._pollTelemetry(), 15000);
    terminal.init();
    vault.render();
    // Sincronización en vivo con backend (Supabase/SQLite vía FastAPI)
    if (window.LiveSync) { window.LiveSync.init(); }
    // Exponer global para onclick="app.*" y para palette/settings/terminal
    window.app = this;
    // Cargar modelos para el selector tipo Gemini
    this.loadModels();
    this.showToast('AICascade Widget', 'Sistema listo — Modelo más potente seleccionado automáticamente', 'success');
  },

  bindEvents() {
    // Tema día/noche (puede no existir si el sidebar cambió)
    const themeBtn = document.getElementById('btn-theme');
    if (themeBtn) themeBtn.addEventListener('click', () => this.toggleTheme());

    // Input terminal
    const termInput = document.getElementById('terminalInput');
    if (termInput) termInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const cmd = e.target.value.trim();
        e.target.value = '';
        terminal.execute(cmd);
      }
    });

    // Input chat IA (Enter = enviar)
    const chatInput = document.getElementById('chatInput');
    if (chatInput) chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.sendChat();
    });
  },

  // ========== NUEVO: Selector de modelos tipo Gemini ==========
  async loadModels() {
    try {
      if (window.AIBackend && window.AIBackend.online) {
        const data = await window.AIBackend.getModels();
        if (data && data.ok) {
          this._models = data.models;
          this.renderModelMenu();
        }
      }
    } catch (e) { /* silencioso */ }
  },

  renderModelMenu() {
    const list = document.getElementById('modelList');
    if (!list) return;
    list.innerHTML = this._models.map(m => `
      <div class="flex items-center justify-between px-4 py-2 text-sm hover:bg-gray-50 rounded-lg cursor-pointer transition-colors" onclick="app.selectModel('${m.id}')">
        <div class="flex items-center gap-3">
          <span class="w-2 h-2 rounded-full ${m.configured ? 'bg-green-500' : 'bg-gray-400'}"></span>
          <span class="${m.configured ? 'text-gray-900' : 'text-gray-400'} font-medium">${m.name}</span>
        </div>
        <span class="text-[10px] text-gray-400 font-mono">${m.provider}</span>
      </div>
    `).join('');
  },

  toggleModelMenu() {
    const menu = document.getElementById('modelMenu');
    if (menu) menu.classList.toggle('hidden');
  },

  selectModel(modelId) {
    this._selectedModel = modelId;
    const m = this._models.find(x => x.id === modelId);
    const label = document.getElementById('modelLabel');
    if (label && m) label.textContent = m.name;
    const menu = document.getElementById('modelMenu');
    if (menu) menu.classList.add('hidden');
    this.showToast('Modelo', m ? m.name : modelId, 'info');
  },

  // ========== NUEVO: Sugerencias @ para conectores ==========
  toggleSuggestions() {
    this._suggestionsOpen = !this._suggestionsOpen;
    const panel = document.getElementById('suggestionsPanel');
    const btn = document.getElementById('atSuggestionBtn');
    if (panel) {
      panel.classList.toggle('hidden');
      if (this._suggestionsOpen) this.renderSuggestions();
    }
    if (btn) btn.className = this._suggestionsOpen
      ? 'text-indigo-500 p-2 rounded-lg bg-white/10'
      : 'text-gray-400 hover:text-indigo-500 transition-colors p-2 rounded-lg hover:bg-white/5';
  },

  renderSuggestions() {
    const list = document.getElementById('suggestionsList');
    if (!list) return;
    const suggs = [
      { id: 'google', name: 'Google Gemini', icon: '🧠' },
      { id: 'groq', name: 'Groq', icon: '⚡' },
      { id: 'openrouter', name: 'OpenRouter', icon: '🔀' },
      { id: 'openai', name: 'OpenAI', icon: '🤖' },
      { id: 'deepseek', name: 'DeepSeek', icon: '🔍' },
      { id: 'ollama', name: 'Ollama (Local)', icon: '🏠' },
      { id: 'cascade', name: 'Cascada (Failover)', icon: '🌊' },
    ];
    list.innerHTML = suggs.map(s => `
      <button onclick="app.insertSuggestion('${s.id}')" class="flex items-center justify-between px-3 py-2 rounded-lg text-left hover:bg-gray-50 transition-colors text-sm">
        <span class="text-lg mr-2">${s.icon}</span>
        <span class="text-gray-700 font-medium">${s.name}</span>
      </button>
    `).join('');
  },

  insertSuggestion(providerId) {
    const input = document.getElementById('chatInput');
    if (!input) return;
    const m = this._models.find(x => x.provider === providerId) || this._models.find(x => x.id === providerId);
    if (m) {
      this._selectedModel = m.id;
      const label = document.getElementById('modelLabel');
      if (label) label.textContent = m.name;
      input.focus();
      this.toggleSuggestions();
      this.showToast('Modelo', m.name, 'info');
    }
  },

  // ========== NUEVO: Entrada por voz (placeholder visual) ==========
  toggleVoiceInput() {
    this._voiceActive = !this._voiceActive;
    const btn = document.getElementById('voiceBtn');
    if (btn) {
      btn.className = this._voiceActive
        ? 'text-green-500 p-2 rounded-lg bg-green-500/10 animate-pulse'
        : 'text-gray-400 hover:text-green-500 transition-colors p-2 rounded-lg hover:bg-white/5';
    }
    this.showToast(this._voiceActive ? 'Voz activada' : 'Voz desactivada', 'Habla al micrófono (próximamente con Web Speech API)', 'info');
  },

  // ========== NUEVO: Indicador de escritura ==========
  _showTyping() {
    const el = document.getElementById('typingIndicator');
    if (el) el.classList.remove('hidden');
  },

  _hideTyping() {
    const el = document.getElementById('typingIndicator');
    if (el) el.classList.add('hidden');
  },

  startClock() {
    const update = () => {
      const now = new Date();
      document.getElementById('currentTime').textContent = now.toLocaleTimeString('es-ES', { hour12: false });
      document.getElementById('currentDate').textContent = now.toLocaleDateString('es-ES');
    };
    update();
    setInterval(update, 1000);
  },

  toggleTheme() {
    const html = document.documentElement;
    const isNight = html.getAttribute('data-theme') === 'night';
    const next = isNight ? 'day' : 'night';
    html.setAttribute('data-theme', next);
    localStorage.setItem('aicascade_theme', next);

    // Estructura nueva: #themeCheckbox + #themeIconLabel
    const checkbox = document.getElementById('themeCheckbox');
    const iconLabel = document.getElementById('themeIconLabel');

    // Estructura anterior (compatibilidad): #btn-theme + #themeLabel + .theme-icon
    const btn = document.getElementById('btn-theme');
    const label = document.getElementById('themeLabel');
    const icon = btn ? btn.querySelector('.theme-icon') : null;

    if (next === 'night') {
      if (checkbox) checkbox.checked = true;
      if (iconLabel) iconLabel.textContent = '🌙';
      if (label) label.textContent = 'Modo Noche';
      if (icon) icon.textContent = '🌙';
      this.showToast('Tema', 'Modo Noche activado (iPhone Negro)', 'info');
    } else {
      if (checkbox) checkbox.checked = false;
      if (iconLabel) iconLabel.textContent = '☀️';
      if (label) label.textContent = 'Modo Día';
      if (icon) icon.textContent = '☀️';
      this.showToast('Tema', 'Modo Día activado (iPhone Plata)', 'info');
    }
  },

  // Inicializar tema guardado
  initTheme() {
    const saved = localStorage.getItem('aicascade_theme');
    const checkbox = document.getElementById('themeCheckbox');
    const iconLabel = document.getElementById('themeIconLabel');
    const btn = document.getElementById('btn-theme');
    const label = document.getElementById('themeLabel');
    const icon = btn ? btn.querySelector('.theme-icon') : null;

    if (saved === 'night') {
      document.documentElement.setAttribute('data-theme', 'night');
      if (checkbox) checkbox.checked = true;
      if (iconLabel) iconLabel.textContent = '🌙';
      if (label) label.textContent = 'Modo Noche';
      if (icon) icon.textContent = '🌙';
    } else {
      document.documentElement.setAttribute('data-theme', 'day');
      if (checkbox) checkbox.checked = false;
      if (iconLabel) iconLabel.textContent = '☀️';
      if (label) label.textContent = 'Modo Día';
      if (icon) icon.textContent = '☀️';
    }
  },

  switchPanel(panel) {
    this.currentPanel = panel;
    // Ocultar todos los paneles
    document.querySelectorAll('main section').forEach(el => el.classList.add('hidden'));
    // Mostrar el activo
    const active = document.getElementById(`panel-${panel}`);
    if (active) {
      active.classList.remove('hidden');
      active.classList.add('animate-slide-in');
    }
    // Actualizar nav
    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.remove('bg-blue-50/50', 'text-blue-700', 'shadow-sm', 'border', 'border-blue-100/50');
      el.classList.add('text-gray-600');
    });
    const navBtn = document.getElementById(`nav-${panel}`);
    if (navBtn) {
      navBtn.classList.remove('text-gray-600');
      navBtn.classList.add('bg-blue-50/50', 'text-blue-700', 'shadow-sm', 'border', 'border-blue-100/50');
    }
    // Títulos
    const titles = {
      dashboard: ['Panel Principal', 'Estado en tiempo real del sistema de cascada de IA'],
      providers: ['Proveedores de IA', 'Estado de conexión y cuota de cada proveedor'],
      vault: ['Vault de Credenciales', 'Almacena y gestiona tus claves de API de forma local'],
      chat: ['Chat IA', 'Cascada con failover automático vía backend'],
      terminal: ['Terminal Super Admin', 'Consola interactiva con privilegios elevados'],
      shortcuts: ['Atajos del Sistema', 'Enlaces rápidos a VS Code, GitHub y carpetas']
    };
    const [t, s] = titles[panel] || ['Panel', ''];
    document.getElementById('panelTitle').textContent = t;
    document.getElementById('panelSubtitle').textContent = s;

    if (panel === 'dashboard') this.render();
    if (panel === 'providers') this.renderProviders();
    if (panel === 'vault') vault.render();
  },

  // ========== CHAT IA (backend con failover, fallback local) ==========
  _chatBusy: false,

  _chatBubble(who, text, meta) {
    const logEl = document.getElementById('chatLog');
    if (!logEl) return;
    const wrap = document.createElement('div');
    const mine = who === 'user';
    const now = new Date().toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit', hour12: false });

    if (mine) {
      wrap.className = 'flex justify-end items-end gap-2';
      wrap.innerHTML = `
        <div class="max-w-[75%] rounded-2xl rounded-tl-none bg-indigo-600 text-white px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap shadow-lg shadow-indigo-500/20">
          ${text.replace(/\n/g, '<br>')}
        </div>
        <span class="text-[10px] text-indigo-200 mt-1">${now}</span>
      `;
    } else {
      const providerBadge = meta && meta.provider ? `
        <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-700 text-[10px] font-medium text-gray-300 mb-1">
          <span class="w-1.5 h-1.5 rounded-full ${meta.provider === 'simulated' ? 'bg-amber-500' : 'bg-green-500'}"></span>
          ${meta.provider}
        </span>
      ` : '';
      const modelBadge = meta && meta.model ? `
        <span class="text-[10px] text-gray-500 font-mono mt-1">${meta.model}</span>
      ` : '';
      wrap.className = 'flex justify-start items-end gap-2';
      wrap.innerHTML = `
        ${providerBadge}
        <div class="max-w-[75%] rounded-2xl rounded-br-none bg-gray-800 p-4 text-sm text-gray-200 leading-relaxed whitespace-pre-wrap border border-gray-700/50 shadow-md">
          ${text.replace(/\n/g, '<br>')}
        </div>
        ${modelBadge}
        <span class="text-[10px] text-gray-600 mt-1">${now}</span>
      `;
    }
    logEl.appendChild(wrap);
    logEl.scrollTop = logEl.scrollHeight;
    return wrap;
  },},

  async sendChat() {
    const input = document.getElementById('chatInput');
    const modeEl = document.getElementById('chatBackendBadge');
    if (!input || this._chatBusy) return;
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';
    this._chatBusy = true;

    // Mostrar burbuja de usuario
    this._chatBubble('user', msg);

    // Mostrar indicador de escritura
    this._showTyping();

    const logEl = document.getElementById('chatLog');
    try {
      if (window.AIBackend && window.AIBackend.online) {
        // Intentar streaming primero
        const useStream = window.ChatStream && typeof window.ChatStream.send === 'function';
        let res;
        if (useStream) {
          res = await window.ChatStream.send(msg, this._selectedModel, (provider, content, model) => {
            // Actualizar burbuja progresiva durante el stream
            const last = logEl.lastElementChild;
            if (last && last.dataset.streaming === 'true') {
              last.querySelector('.msg-content').textContent += content;
              logEl.scrollTop = logEl.scrollHeight;
            } else {
              const bubble = this._chatBubble('ai', '', { provider, model });
              bubble.querySelector('.msg-content').textContent = content;
              bubble.dataset.streaming = 'true';
            }
          });
          this._hideTyping();
        } else {
          res = await window.AIBackend.chat(msg, this._selectedModel);
          this._hideTyping();
        }

        if (modeEl) {
          const isLive = res.mode === 'live';
          modeEl.textContent = '● ' + (res.provider || 'local');
          modeEl.className = 'text-xs font-medium px-2 py-1 rounded-full '
            + (isLive ? 'bg-green-500/10 text-green-400 border border-green-500/30' : 'bg-amber-500/10 text-amber-400 border border-amber-500/30');
        }

        // Si no hubo streaming, mostrar la respuesta final
        if (!useStream) {
          this._chatBubble('ai', res.response || '(sin respuesta)', {
            provider: res.provider,
            model: res.model
          });
        }

        if (window.app) window.app.render();
        return;
      }

      // Fallback: cascada simulada local
      const r = await cascadeChat(msg);
      this._hideTyping();
      if (modeEl) modeEl.textContent = '● Local';
      if (modeEl) modeEl.className = 'text-xs font-medium px-2 py-1 rounded-full bg-gray-500/10 text-gray-400 border border-gray-500/30';
      const tmp = document.createElement('div');
      tmp.innerHTML = r.html;
      const txt = tmp.textContent || tmp.innerText || '(sin respuesta)';
      this._chatBubble('ai', txt.trim().substring(0, 2000), { provider: 'local', model: 'Cascade-Auto' });
      if (window.app) window.app.render();
    } catch (e) {
      this._hideTyping();
      this._chatBubble('ai', '[ERROR] No se pudo contactar al backend: ' + e.message, { provider: 'error' });
    } finally {
      this._chatBusy = false;
    }
  },},

  // ========== RENDER DASHBOARD ==========
  render() {
    const s = cascade.getStatus();

    // Modelo activo
    document.getElementById('activeModel').textContent = s.activeModel;

    // Indicador de nivel de cascada con chip de color + animación al cambiar
    const tierEl = document.getElementById('activeTier');
    const tierNum = s.activeTier && typeof s.activeTier === 'number' ? s.activeTier :
      (String(s.activeTier || '').match(/\d/) || [0])[0];
    const tierChanged = this._lastRenderedTier != null && this._lastRenderedTier !== tierNum;
    if (tierEl) {
      tierEl.textContent = 'Nivel ' + tierNum;
      tierEl.className = 'text-sm font-bold mt-1 ios-num ios-tier-indicator tier-' + tierNum +
        (tierChanged ? ' switching' : '');
      if (tierChanged) {
        setTimeout(() => {
          if (tierEl) tierEl.classList.remove('switching');
        }, 600);
      }
    }
    this._lastRenderedTier = tierNum;

    // Tokens
    document.getElementById('totalTokens').textContent = s.totalTokens;
    document.getElementById('remainingTokens').textContent = s.remainingTokens;

    // Barras de progreso
    const pct = s.pctUsed;
    document.getElementById('tokenBarTotal').style.width = `${pct}%`;
    document.getElementById('tokenBarRemaining').style.width = `${s.pctRemaining}%`;

    // Colores de barra según estado
    const barTotal = document.getElementById('tokenBarTotal');
    const barRem = document.getElementById('tokenBarRemaining');
    barTotal.className = `h-full rounded-full transition-all duration-500 ${pct >= 90 ? 'bg-rose-500' : pct >= 60 ? 'bg-amber-500' : 'bg-blue-500'}`;
    barRem.className = `h-full rounded-full transition-all duration-500 ${s.pctRemaining >= 50 ? 'bg-green-500' : s.pctRemaining >= 20 ? 'bg-amber-500' : 'bg-rose-500'}`;

    // Estado
    document.getElementById('statusText').textContent = s.statusText;
    document.getElementById('statusText').className = `text-xs font-bold ${s.statusColor}`;
    document.getElementById('statusDot').className = `w-2 h-2 rounded-full ${s.dotColor}`;
    // Conmutaciones: totales persistentes (BD) si hay backend online, si no de la sesión
    const dbOnline = window.AIBackend && window.AIBackend.online && this._dbSwitches != null;
    document.getElementById('switchCount').textContent = dbOnline ? this._dbSwitches : s.switchCount;
    document.getElementById('callCount').textContent = s.callCount;

    // iOS: anillo SVG #iosRing (numero + arco + tono) + Dynamic Island
    try {
      const ring = document.getElementById('iosRing');
      if (ring) {
        // el CSS del arco lee --pct (18pro-finish.css); --ring-pct mantiene compat con capas previas
        ring.style.setProperty('--pct', pct);
        ring.style.setProperty('--ring-pct', pct);
        ring.setAttribute('data-tone', pct >= 90 ? 'crit' : pct >= 60 ? 'warn' : 'ok');
        const val = document.getElementById('iosRingVal');
        if (val) val.textContent = pct + '%';
      }
      const island = document.getElementById('iosIslandText');
      if (island) island.textContent = `${s.activeModel} · ${s.statusText}`;
      const dot = document.getElementById('iosIslandDot');
      if (dot) dot.style.background = pct >= 90 ? '#f43f5e' : pct >= 60 ? '#fbbf24' : '#34d399';
    } catch (e) {}

    // Modelos por nivel
    this.renderTiers(s.models);

    this.renderActivityLog();
    this.renderMetrics();
  },

  // Telemetría backend (persistida en BD) -> chips y estado en vivo
  async _pollTelemetry() {
    if (!(window.AIBackend && window.AIBackend.online)) return;
    try {
      const ctrl = new AbortController();
      const t = setTimeout(() => ctrl.abort(), 4000);
      const r = await fetch(window.AIBackend.baseUrl + '/api/cascade/telemetry',
        { signal: ctrl.signal });
      clearTimeout(t);
      if (!r.ok) return;
      const tel = await r.json();
      // Guardar total persistido (lo consume render() sin parpadeos)
      if (typeof tel.total_switches === 'number') this._dbSwitches = tel.total_switches;
      const hint = document.getElementById('statusHint');
      if (hint && tel.current_model) hint.textContent = 'Último cambio: ' + tel.current_model;
      const tok = document.getElementById('backendTokens');
      if (tok && typeof tel.total_tokens_used === 'number') {
        tok.textContent = tel.total_tokens_used.toLocaleString();
      }
    } catch (e) {}
  },

  // Métricas reales en el dashboard
  renderMetrics() {
    try {
      const m = cascade.getMetrics();
      const lat = document.getElementById('metricLatency');
      const err = document.getElementById('metricErrors');
      const io = document.getElementById('metricIO');
      if (lat) lat.textContent = m.avgLatencyMs + 'ms';
      if (err) err.textContent = m.errorRate;
      if (io) io.textContent = m.totalInputTokens.toLocaleString() + '/' + m.totalOutputTokens.toLocaleString();
    } catch (e) {}
  },

  renderTiers(models) {
    const tiers = { 1: document.getElementById('tier1Models'), 2: document.getElementById('tier2Models'), 3: document.getElementById('tier3Models') };
    Object.values(tiers).forEach(el => el.innerHTML = '');

    models.forEach(m => {
      const div = document.createElement('div');
      const pct = Math.round((m.used / Math.max(1, m.limit)) * 100);
      const isActive = m.name === cascade.activeModel?.name;
      const isCritical = pct >= 90;
      const dotClass = isCritical ? 'dot critical' : pct >= 60 ? 'dot warning' : 'dot';
      div.className = `model-item ${isActive ? 'active' : ''} ${isCritical ? 'border-rose-200' : ''}`;
      div.innerHTML = `
        <div class="${dotClass}"></div>
        <div class="flex-1">
          <div class="flex justify-between items-baseline">
            <span class="font-medium text-gray-800">${m.name}</span>
            <span class="text-[10px] font-bold text-gray-400">${pct}%</span>
          </div>
          <div class="text-[10px] text-gray-500">${m.provider} • ${m.used.toLocaleString()}/${m.limit.toLocaleString()} tokens</div>
        </div>
      `;
      tiers[m.tier].appendChild(div);
    });
  },

  renderActivityLog() {
    const el = document.getElementById('activityLog');
    if (!el) return;
    el.innerHTML = cascade.activityLog.map(entry => `
      <div class="flex items-start gap-3 text-sm">
        <div class="w-2 h-2 rounded-full ${entry.type === 'info' ? 'bg-blue-400' : entry.type === 'success' ? 'bg-green-400' : 'bg-amber-400'} mt-1 flex-shrink-0"></div>
        <div>
          <div class="text-gray-700 font-medium">${entry.message}</div>
          <div class="text-gray-500 text-xs">${entry.time}</div>
        </div>
      </div>
    `).join('');
  },

  // ========== RENDER PROVEEDORES ==========
  renderProviders() {
    const grid = document.getElementById('providersGrid');
    if (!grid) return;
    const s = cascade.getStatus();
    grid.innerHTML = s.models.map(m => {
      const pct = Math.round((m.used / Math.max(1, m.limit)) * 100);
      const isActive = m.name === cascade.activeModel?.name;
      const color = pct >= 90 ? 'text-rose-600 bg-rose-50 border-rose-100' : pct >= 60 ? 'text-amber-600 bg-amber-50 border-amber-100' : 'text-green-600 bg-green-50 border-green-100';
      return `
        <div class="glass-card p-5 rounded-xl border ${isActive ? 'border-blue-200 shadow-sm shadow-blue-50/50' : ''} ${color.replace('text-', '').replace('bg-', '').replace('border-', '')} flex flex-col">
          <div class="flex justify-between items-start mb-3">
            <div>
              <div class="font-bold text-gray-900">${m.name}</div>
              <div class="text-xs text-gray-500">${m.provider}</div>
            </div>
            <div class="w-2 h-2 rounded-full ${isActive ? 'bg-blue-500 animate-pulse' : (pct >= 90 ? 'bg-rose-500' : pct >= 60 ? 'bg-amber-500' : 'bg-green-500')}"></div>
          </div>
          <div class="text-2xl font-bold text-gray-800 mb-1">${pct}%</div>
          <div class="w-full bg-gray-100 rounded-full h-2 mb-2 overflow-hidden">
            <div class="h-full ${color.split(' ')[0] === 'text-green-600' ? 'bg-green-500' : color.split(' ')[0] === 'text-amber-600' ? 'bg-amber-500' : 'bg-rose-500'} rounded-full" style="width: ${pct}%"></div>
          </div>
          <div class="text-xs text-gray-500 space-y-1">
            <div>Usados: ${m.used.toLocaleString()} / ${m.limit.toLocaleString()}</div>
            <div>Errores: ${m.errors} | Llamadas: ${m.calls}</div>
          </div>
        </div>
      `;
    }).join('');
  },

  // ========== UTILIDADES ==========
  showToast(title, msg, type = 'success') {
    const toast = document.getElementById('toast');
    const titleEl = document.getElementById('toastTitle');
    const msgEl = document.getElementById('toastMsg');
    titleEl.textContent = title;
    msgEl.textContent = msg;
    toast.classList.remove('translate-y-20', 'opacity-0');
    setTimeout(() => {
      toast.classList.add('translate-y-20', 'opacity-0');
    }, 3000);
  },

  openVSCode() {
    this.showToast('VS Code', 'Abriendo editor de código...', 'info');
    // Simulado: en entorno real usaría shell.openExternal o similar
    setTimeout(() => this.showToast('VS Code', 'VS Code abierto (simulado)', 'success'), 800);
  },

  openGitHub() {
    this.showToast('GitHub', 'Redirigiendo a repositorios...', 'info');
    setTimeout(() => this.showToast('GitHub', 'GitHub abierto (simulado)', 'success'), 800);
  },

  openCascadeFolder() {
    this.showToast('Carpeta', 'Abriendo AICascadeWidget...', 'info');
    setTimeout(() => this.showToast('Carpeta', 'Carpeta abierta (simulado)', 'success'), 800);
  }
};

// Exponer global para onclick="app.*" (los botones del HTML lo necesitan)
window.app = app;

// Función global para onchange="toggleTheme()" del checkbox #themeCheckbox
window.toggleTheme = function () {
  if (window.app && typeof window.app.toggleTheme === 'function') {
    window.app.toggleTheme();
  }
};

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
  app.initTheme();
  app.init();
});
