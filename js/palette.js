// Command Palette (Ctrl+K) + atajos globales
(function () {
  const COMMANDS = [
    { id: 'go-dashboard', label: 'Ir a Dashboard', hint: 'panel' },
    { id: 'go-chat', label: 'Ir a Chat IA', hint: 'panel' },
    { id: 'go-providers', label: 'Ir a Proveedores', hint: 'panel' },
    { id: 'go-vault', label: 'Ir a Vault', hint: 'panel' },
    { id: 'go-terminal', label: 'Ir a Terminal', hint: 'panel' },
    { id: 'go-shortcuts', label: 'Ir a Atajos', hint: 'panel' },
    { id: 'cascade-failover', label: 'Forzar conmutacion', hint: 'cascade' },
    { id: 'cascade-reset', label: 'Reiniciar contadores', hint: 'cascade' },
    { id: 'cascade-metrics', label: 'Ver metricas', hint: 'cascade' },
    { id: 'vault-export', label: 'Exportar vault', hint: 'vault' },
    { id: 'theme-toggle', label: 'Alternar tema', hint: 'ui' },
    { id: 'backend-ping', label: 'Probar backend', hint: 'backend' },
  ];

  function runCmd(id) {
    if (id.indexOf('go-') === 0) { app.switchPanel(id.slice(3)); return; }
    if (id === 'cascade-failover') { cascade.runFailover(); app.render(); return; }
    if (id === 'cascade-reset') { cascade.resetUsage(); app.render(); return; }
    if (id === 'cascade-metrics') { app.switchPanel('terminal'); setTimeout(() => terminal.execute('cascade --metrics'), 150); return; }
    if (id === 'vault-export') { vault.exportKeys(); return; }
    if (id === 'theme-toggle') { app.toggleTheme(); return; }
    if (id === 'backend-ping') {
      (async () => {
        const h = window.AIBackend ? await window.AIBackend.ping() : null;
        app.showToast('Backend', h ? 'OK' : 'Offline', h ? 'success' : 'error');
      })();
      return;
    }
  }

  function openPalette() {
    let ov = document.getElementById('cmdPalette');
    if (!ov) {
      ov = document.createElement('div');
      ov.id = 'cmdPalette';
      ov.style.cssText = 'position:fixed;inset:0;z-index:100;display:flex;align-items:flex-start;justify-content:center;padding-top:12vh;background:rgba(0,0,0,.35)';
      ov.innerHTML = '<div style="width:min(560px,92vw);background:rgba(255,255,255,.9);backdrop-filter:blur(20px);border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.3);overflow:hidden">'
        + '<input id="cmdPaletteInput" placeholder="Escribe un comando... (Esc cierra)" style="width:100%;padding:14px 18px;background:transparent;font-size:14px;outline:none;border-bottom:1px solid #eee">'
        + '<div id="cmdPaletteList" style="max-height:300px;overflow-y:auto;padding:8px"></div></div>';
      document.body.appendChild(ov);
      const input = ov.querySelector('#cmdPaletteInput');
      const list = ov.querySelector('#cmdPaletteList');
      const draw = (q) => {
        const ql = String(q || '').toLowerCase();
        const cmds = COMMANDS.filter(c => !ql || (c.label + ' ' + c.hint).toLowerCase().indexOf(ql) !== -1);
        list.innerHTML = cmds.map(c => '<button data-cmd="' + c.id + '" style="width:100%;text-align:left;padding:10px 12px;border-radius:10px;font-size:13px;display:flex;justify-content:space-between"><b>' + c.label + '</b><span style="font-size:10px;opacity:.5">' + c.hint + '</span></button>').join('')
          || '<div style="padding:24px;text-align:center;font-size:13px;opacity:.5">Sin resultados</div>';
        Array.from(list.querySelectorAll('[data-cmd]')).forEach(b => { b.onclick = () => { closePalette(); runCmd(b.getAttribute('data-cmd')); }; });
      };
      input.oninput = () => draw(input.value);
      input.onkeydown = (e) => {
        if (e.key === 'Escape') closePalette();
        if (e.key === 'Enter') { const f = list.querySelector('[data-cmd]'); if (f) f.click(); }
      };
      ov.onclick = (e) => { if (e.target === ov) closePalette(); };
      ov._draw = draw;
      draw('');
    }
    ov.style.display = 'flex';
    ov._draw('');
    setTimeout(() => { const i = document.getElementById('cmdPaletteInput'); if (i) { i.value = ''; i.focus(); } }, 30);
  }

  function closePalette() {
    const ov = document.getElementById('cmdPalette');
    if (ov) ov.style.display = 'none';
  }

  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette(); return; }
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'd') { e.preventDefault(); app.toggleTheme(); return; }
    if ((e.ctrlKey || e.metaKey) && ['1', '2', '3', '4', '5', '6'].indexOf(e.key) !== -1) {
      e.preventDefault();
      app.switchPanel(['dashboard', 'chat', 'providers', 'vault', 'terminal', 'shortcuts'][parseInt(e.key, 10) - 1]);
    }
    if (e.key === 'Escape') closePalette();
  });

  if (window.app) { window.app.openPalette = openPalette; window.app.closePalette = closePalette; }
  window.addEventListener('DOMContentLoaded', () => {
    if (window.app) { window.app.openPalette = openPalette; window.app.closePalette = closePalette; }
  });
})();
