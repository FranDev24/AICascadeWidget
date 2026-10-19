// ============================================================================
// AICascade Widget — Terminal Super Admin (simulado)
// ============================================================================

const terminal = {
  outputEl: null,
  inputEl: null,
  history: [],
  historyIndex: -1,

  COMMANDS: [
    'help', 'clear', 'exit',
    'cascade --status', 'cascade --failover', 'cascade --reset', 'cascade --metrics',
    'cascade --enable', 'cascade --disable', 'cascade --use',
    'vault --sync', 'vault --status', 'vault --export',
    'backend --ping', 'chat',
    'vscode --open', 'github --open',
    'theme --day', 'theme --night',
  ],

  init() {
    this.outputEl = document.getElementById('terminalOutput');
    this.inputEl = document.getElementById('terminalInput');
    if (!this.outputEl || !this.inputEl) return;

    try {
      const raw = localStorage.getItem('aicascade_term_history');
      if (raw) { this.history = JSON.parse(raw) || []; this.historyIndex = this.history.length; }
    } catch (e) {}

    this.inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        const cmd = this.inputEl.value.trim();
        this.inputEl.value = '';
        this.execute(cmd);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (this.history.length > 0) {
          this.historyIndex = Math.max(0, this.historyIndex - 1);
          this.inputEl.value = this.history[this.historyIndex];
        }
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (this.historyIndex < this.history.length - 1) {
          this.historyIndex++;
          this.inputEl.value = this.history[this.historyIndex];
        } else {
          this.historyIndex = this.history.length;
          this.inputEl.value = '';
        }
      } else if (e.key === 'Tab') {
        // Autocompletado
        e.preventDefault();
        const cur = this.inputEl.value;
        const match = this.COMMANDS.filter(c => c.startsWith(cur));
        if (match.length === 1) {
          this.inputEl.value = match[0];
        } else if (match.length > 1) {
          this.log('Sugerencias: ' + match.join('  |  '), 'cyan');
        }
      }
    });

    this.log('> AICascade Terminal v2.0 — Modo Super Admin (Tab=autocompletar)', 'blue');
    this.log('> Tipo \'help\' para ver comandos disponibles', 'gray');
    this.prompt();
  },

  _persistHistory() {
    try {
      localStorage.setItem('aicascade_term_history', JSON.stringify(this.history.slice(-100)));
    } catch (e) {}
  },

  log(msg, color = 'white') {
    const div = document.createElement('div');
    div.className = 'mb-1 text-xs leading-relaxed break-all';
    div.innerHTML = `<span class="text-${color}-400 font-bold mr-2">»</span> <span class="text-gray-300">${this.escapeHtml(msg)}</span>`;
    this.outputEl.appendChild(div);
    this.outputEl.scrollTop = this.outputEl.scrollHeight;
  },

  prompt() {
    const div = document.createElement('div');
    div.className = 'mt-2 flex items-baseline';
    div.innerHTML = `<span class="text-blue-400 font-mono text-xs mr-2">$</span> <span class="text-xs text-gray-300 cursor-text" style="user-select:all;"></span>`;
    this.outputEl.appendChild(div);
    this.outputEl.scrollTop = this.outputEl.scrollHeight;
    setTimeout(() => this.inputEl.focus(), 50);
  },

  execute(cmd) {
    if (!cmd) { this.prompt(); return; }
    this.history.push(cmd);
    this.historyIndex = this.history.length;
    this._persistHistory();

    const lower = cmd.toLowerCase();
    const parts = cmd.split(/\s+/);
    const base = parts[0].toLowerCase();
    const args = parts.slice(1).join(' ');

    // Eco del comando
    const echo = document.createElement('div');
    echo.className = 'mb-1 text-xs text-blue-400 font-mono break-all';
    echo.textContent = `> ${cmd}`;
    this.outputEl.insertBefore(echo, this.outputEl.lastElementChild);
    this.outputEl.scrollTop = this.outputEl.scrollHeight;

    if (lower === 'help') {
      this.log('Comandos (Tab autocompleta): cascade --status|--failover|--reset|--metrics|--enable|--disable|--use | vault --sync|--status|--export | backend --ping | chat <msg> | theme --day|--night | vscode/github --open | clear | exit', 'green');
    } else if (lower === 'clear') {
      this.outputEl.innerHTML = '';
    } else if (lower === 'cascade --status') {
      const s = cascade.getStatus();
      this.log(`Modelo activo: ${s.activeModel} (${s.activeTier})`, 'cyan');
      this.log(`Tokens: ${s.totalTokens}`, 'white');
      this.log(`Restantes: ${s.remainingTokens}`, 'white');
      this.log(`Estado: ${s.statusText}`, s.statusText.includes('Óptimo') ? 'green' : 'yellow');
      this.log(`Conmutaciones: ${s.switchCount} | Llamadas: ${s.callCount}`, 'white');
    } else if (lower === 'cascade --failover') {
      const nxt = cascade.runFailover();
      if (nxt) {
        this.log(`Conmutación forzada a: ${nxt.name} (Nivel ${nxt.tier})`, 'green');
        if (window.app) window.app.render();
      } else {
        this.log('No hay modelo inferior disponible para conmutar', 'red');
      }
    } else if (lower === 'cascade --reset') {
      cascade.resetUsage();
      this.log('Contadores reiniciados', 'green');
      if (window.app) window.app.render();
    } else if (lower === 'cascade --metrics') {
      const m = cascade.getMetrics();
      this.log(`Llamadas:${m.totalCalls} Switches:${m.totalSwitches} Tokens:${m.totalTokens} Lat:${m.avgLatencyMs}ms Err:${m.errorRate}`, 'cyan');
      m.perModel.forEach(p => this.log(`  ${p.name}: ${p.calls}ll ${p.errors}err ${p.avgLatencyMs}ms`, 'white'));
    } else if (lower === 'vault --sync') {
      vault.render();
      this.log('Vault sincronizado desde localStorage', 'green');
    } else if (lower === 'vault --export') {
      vault.exportKeys();
      this.log('Backup del vault descargado', 'green');
    } else if (lower.startsWith('cascade --use ')) {
      const name = cmd.substring(15).trim();
      const mm = cascade.models.find(x => x.name.toLowerCase() === name.toLowerCase());
      if (mm) { cascade.switchModel(mm, 'manual_terminal'); this.log(`Activo: ${mm.name}`, 'green'); }
      else this.log(`No encontrado: ${name}`, 'red');
      if (window.app) window.app.render();
    } else if (lower.startsWith('cascade --disable ') || lower.startsWith('cascade --enable ')) {
      const dis = lower.startsWith('cascade --disable ');
      const name = cmd.substring(dis ? 19 : 18).trim();
      const mm = cascade.models.find(x => x.name.toLowerCase() === name.toLowerCase());
      if (mm && mm.enabled === dis) { cascade.toggleModel(mm.name); this.log(`${mm.name} ${dis ? 'deshabilitado' : 'habilitado'}`, dis ? 'yellow' : 'green'); }
      else this.log(mm ? 'Sin cambios' : `No encontrado: ${name}`, 'yellow');
      if (window.app) window.app.render();
    } else if (lower === 'vault --status' || lower === 'backend --ping') {
      this.log('Consultando backend…', 'cyan');
      const onlyPing = lower === 'backend --ping';
      (async () => {
        const h = window.AIBackend ? await window.AIBackend.ping() : null;
        if (!h) { this.log('Backend offline', 'red'); this.prompt(); return; }
        this.log(`Backend OK (${window.AIBackend.store})`, 'green');
        if (!onlyPing) {
          try {
            const r = await fetch(window.AIBackend.baseUrl + '/api/vault/status');
            const j = await r.json();
            this.log(`Providers: ${(j.providers || []).join(', ') || 'ninguno'}`, 'white');
          } catch (e) { this.log('Error vault: ' + e.message, 'red'); }
        }
        this.prompt();
      })();
      return;
    } else if (base === 'chat') {
      if (!args) { this.log('Uso: chat <mensaje>', 'yellow'); }
      else {
        this.log('Enviando…', 'cyan');
        ((msg) => (async () => {
          try {
            if (window.AIBackend && window.AIBackend.online) {
              const res = await window.AIBackend.chat(msg);
              this.log(`[${res.provider}/${res.mode}] ${String(res.response).substring(0, 500)}`, 'green');
            } else {
              const r = await cascadeChat(msg);
              const tmp = document.createElement('div'); tmp.innerHTML = r.html;
              this.log((tmp.textContent || '').substring(0, 500), 'green');
            }
          } catch (e) { this.log('Error: ' + e.message, 'red'); }
          this.prompt();
        })())(args);
        return;
      }
    } else if (lower === 'theme --day' || lower === 'theme --night') {
      const want = lower.endsWith('--night') ? 'night' : 'day';
      if (document.documentElement.getAttribute('data-theme') !== want && window.app) window.app.toggleTheme();
      this.log(`Tema: ${want}`, 'green');
    } else if (lower === 'vscode --open') {
      this.log('Abriendo Visual Studio Code...', 'cyan');
      setTimeout(() => this.log('VS Code abierto en workspace: C:\\Users\\MT-110326\\Documents\\Default Project', 'green'), 500);
    } else if (lower === 'github --open') {
      this.log('Abriendo GitHub...', 'cyan');
      setTimeout(() => this.log('Redirigiendo a https://github.com (simulado)', 'green'), 500);
    } else if (lower === 'exit') {
      this.log('Saliendo del modo super admin...', 'yellow');
      this.inputEl.disabled = true;
      this.inputEl.placeholder = 'Terminal desactivado';
    } else {
      this.log(`Comando no reconocido: ${cmd}`, 'red');
    }

    this.prompt();
  },

  escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }
};

// Exponer global para onclick="terminal.*" y uso desde app/palette
window.terminal = terminal;
