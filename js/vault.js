// ============================================================================
// AICascade Widget — Vault de Credenciales API
// ============================================================================

const vault = {
  providers: [
    { id: 'openai', name: 'OpenAI', models: ['GPT-4o', 'GPT-4o-mini'], color: 'text-black bg-gray-100' },
    { id: 'anthropic', name: 'Anthropic', models: ['Claude 3.5 Sonnet', 'Claude 3 Haiku'], color: 'text-orange-600 bg-orange-50' },
    { id: 'google', name: 'Google Gemini', models: ['Gemini 1.5 Pro', 'Gemini 1.5 Flash'], color: 'text-blue-600 bg-blue-50' },
    { id: 'ollama', name: 'Ollama (Local)', models: ['Llama 3.1 70B', 'Llama 3.1 8B'], color: 'text-red-600 bg-red-50' },
    { id: 'deepseek', name: 'DeepSeek', models: ['DeepSeek V2 Lite'], color: 'text-purple-600 bg-purple-50' }
  ],

  // Cargar claves desde localStorage (simulación de vault local)
  loadKeys() {
    try {
      const raw = localStorage.getItem('aicascade_vault_keys');
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  },

  saveKeys(keys) {
    try {
      localStorage.setItem('aicascade_vault_keys', JSON.stringify(keys));
    } catch (e) {
      console.error('No se pudo guardar en localStorage', e);
    }
  },

  getMaskedKey(key) {
    if (!key) return '';
    if (key.length <= 8) return '•'.repeat(key.length);
    return key.substring(0, 4) + '•'.repeat(key.length - 8) + key.substring(key.length - 4);
  },

  // Sincronizar TODAS las keys locales al backend (para que /api/chat las use)
  async syncToBackend(force = false) {
    if (!(window.AIBackend && window.AIBackend.online)) return;
    try {
      const keys = this.loadKeys();
      for (const [provider, apiKey] of Object.entries(keys)) {
        if (apiKey && provider !== 'ollama') {  // ollama es local, no necesita key
          await window.AIBackend.saveVaultKey(provider, apiKey);
        }
      }
      localStorage.setItem('aicascade_last_sync', Date.now().toString());
      if (window.app) window.app.showToast('Vault', 'Keys sincronizadas con backend', 'success');
    } catch (e) { /* modo local */ }
  },

  render() {
    const container = document.getElementById('vaultList');
    if (!container) return;
    const keys = this.loadKeys();
    container.innerHTML = '';

    this.providers.forEach(p => {
      const key = keys[p.id] || '';
      const hasKey = key.length > 0;
      const card = document.createElement('div');
      card.className = 'glass-card p-4 rounded-xl border border-white/30 flex items-center justify-between animate-slide-in';
      card.innerHTML = `
        <div class="flex items-center gap-3 flex-1">
          <div class="w-10 h-10 rounded-xl ${p.color} flex items-center justify-center font-bold text-xs">
            ${p.name.charAt(0)}
          </div>
          <div>
            <div class="font-semibold text-gray-900 text-sm">${p.name}</div>
            <div class="text-xs text-gray-500">${p.models.join(', ')}</div>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span class="px-2.5 py-1 rounded text-xs font-medium border ${hasKey ? 'bg-green-50 text-green-700 border-green-100' : 'bg-gray-50 text-gray-500 border-gray-100'}">
            ${hasKey ? 'Configurado' : 'Pendiente'}
          </span>
          <button onclick="vault.editKey('${p.id}')" class="text-xs text-gray-400 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100 transition-colors">
            ${hasKey ? 'Editar' : 'Agregar'}
          </button>
          ${hasKey ? `<button onclick="vault.toggleVisibility('${p.id}')" class="text-xs text-gray-400 hover:text-gray-700 px-2 py-1 rounded hover:bg-gray-100 transition-colors" title="Mostrar/ocultar clave">👁️</button>` : ''}
        </div>
        ${hasKey ? `<div class="mt-3 pt-3 border-t border-white/20 w-full"><div class="text-xs text-gray-500 mb-1">Clave:</div><div class="font-mono text-xs text-gray-700 break-all" id="vault-key-display-${p.id}">${this.getMaskedKey(key)}</div></div>` : ''}
      `;
      container.appendChild(card);
    });
  },

  showAddForm() {
    document.getElementById('vaultForm').classList.remove('hidden');
    document.getElementById('vaultProvider').value = 'openai';
    document.getElementById('vaultKey').value = '';
  },

  hideAddForm() {
    document.getElementById('vaultForm').classList.add('hidden');
  },

  saveKey() {
    const provider = document.getElementById('vaultProvider').value;
    const key = document.getElementById('vaultKey').value.trim();
    if (!this.validateKey(provider, key)) return;
    const keys = this.loadKeys();
    keys[provider] = key;
    this.saveKeys(keys);
    this.hideAddForm();
    this.render();
    app.showToast('Vault', `Clave guardada para ${this.providers.find(p => p.id === provider).name}`, 'success');
    // Persistir en backend/Supabase sin bloquear
    try {
      if (window.AIBackend && window.AIBackend.online) {
        window.AIBackend.saveVaultKey(provider, key).then(res => {
          if (res && res.ok) app.showToast('Backend', `Sincronizado en ${res.stored}`, 'success');
        });
      }
    } catch (e) { /* modo local */ }
  },

  // ---------- Validación por proveedor ----------
  validateKey(provider, key) {
    if (!key) { app.showToast('Error', 'Ingresa una clave API válida', 'error'); return false; }
    const patterns = {
      openai: /^sk-[A-Za-z0-9-_]{10,}$/,
      anthropic: /^sk-ant-[A-Za-z0-9-_]{10,}$/,
      google: /^[A-Za-z0-9-_]{15,}$/,
      deepseek: /^sk-[A-Za-z0-9-_]{10,}$/,
      openrouter: /^sk-or-[A-Za-z0-9-_]{10,}$/,
      ollama: /^.+$/,
    };
    const rx = patterns[provider] || /^.{4,}$/;
    if (!rx.test(key)) {
      app.showToast('Formato dudoso', `La clave de ${provider} no parece válida, se guardó igual`, 'error');
      // no bloquea: permite keys locales como "ollama-local"
    }
    return true;
  },

  deleteKey(providerId) {
    const keys = this.loadKeys();
    delete keys[providerId];
    this.saveKeys(keys);
    this.render();
    app.showToast('Vault', 'Clave eliminada (local)', 'success');
  },

  // ---------- Búsqueda ----------
  search(query) {
    const q = String(query || '').toLowerCase();
    const container = document.getElementById('vaultList');
    if (!container) return;
    Array.from(container.children).forEach(card => {
      card.style.display = !q || card.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  },

  // ---------- Export / Import ----------
  exportKeys() {
    const keys = this.loadKeys();
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), keys }, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'aicascade-vault-backup.json';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    app.showToast('Vault', `${Object.keys(keys).length} claves exportadas`, 'success');
  },

  importKeys(file) {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result);
        const keys = data.keys || data;
        const current = this.loadKeys();
        Object.assign(current, keys);
        this.saveKeys(current);
        this.render();
        app.showToast('Vault', `${Object.keys(keys).length} claves importadas`, 'success');
      } catch (e) {
        app.showToast('Error', 'Archivo JSON inválido', 'error');
      }
    };
    reader.readAsText(file);
  },

  editKey(providerId) {
    document.getElementById('vaultProvider').value = providerId;
    const keys = this.loadKeys();
    document.getElementById('vaultKey').value = keys[providerId] || '';
    this.showAddForm();
  },

  toggleVisibility(providerId) {
    const el = document.getElementById(`vault-key-display-${providerId}`);
    const keys = this.loadKeys();
    const key = keys[providerId] || '';
    const isMasked = el.textContent.includes('•');
    el.textContent = isMasked ? key : this.getMaskedKey(key);
  }
};

// Exponer global para onclick="vault.*"
window.vault = vault;
