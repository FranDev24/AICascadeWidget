// Settings modal (preferencias persistentes)
(function () {
  function openSettings() {
    let ov = document.getElementById('settingsModal');
    if (!ov) {
      ov = document.createElement('div');
      ov.id = 'settingsModal';
      ov.style.cssText = 'position:fixed;inset:0;z-index:100;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,.35);padding:16px';
      ov.innerHTML = '<div id="setCard" style="width:min(440px,94vw);background:rgba(255,255,255,.92);backdrop-filter:blur(20px);border-radius:16px;box-shadow:0 20px 60px rgba(0,0,0,.3)"></div>';
      document.body.appendChild(ov);
      ov.onclick = (e) => { if (e.target === ov) closeSettings(); };
    }
    let s = {};
    try { s = JSON.parse(localStorage.getItem('aicascade_settings') || '{}'); } catch (e) {}
    ov.querySelector('#setCard').innerHTML = '<div style="padding:24px">'
      + '<div style="display:flex;justify-content:space-between;margin-bottom:8px"><b>Ajustes</b><button id="setClose">✕</button></div>'
      + '<label style="display:flex;justify-content:space-between;padding:10px 0;font-size:13px">Auto-failback a Nivel 1<input type="checkbox" id="setAutoFailback" ' + (s.autoFailback !== false ? 'checked' : '') + '></label>'
      + '<label style="display:flex;justify-content:space-between;padding:10px 0;font-size:13px">Persistir estado local<input type="checkbox" id="setPersist" ' + (s.persist !== false ? 'checked' : '') + '></label>'
      + '<div style="display:flex;justify-content:flex-end;gap:8px;margin-top:12px"><button id="setCancel">Cerrar</button><button id="setSave" style="padding:8px 16px;background:#2563eb;color:#fff;border-radius:10px">Guardar</button></div></div>';
    ov.querySelector('#setClose').onclick = closeSettings;
    ov.querySelector('#setCancel').onclick = closeSettings;
    ov.querySelector('#setSave').onclick = () => {
      const ns = { autoFailback: ov.querySelector('#setAutoFailback').checked, persist: ov.querySelector('#setPersist').checked };
      try { localStorage.setItem('aicascade_settings', JSON.stringify(ns)); } catch (e) {}
      closeSettings();
      app.showToast('Ajustes', 'Preferencias guardadas', 'success');
    };
    ov.style.display = 'flex';
  }
  function closeSettings() {
    const ov = document.getElementById('settingsModal');
    if (ov) ov.style.display = 'none';
  }
  if (window.app) { window.app.openSettings = openSettings; window.app.closeSettings = closeSettings; }
  window.addEventListener('DOMContentLoaded', () => {
    if (window.app) { window.app.openSettings = openSettings; window.app.closeSettings = closeSettings; }
  });
})();
