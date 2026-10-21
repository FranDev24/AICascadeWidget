/* ============================================================================
   gemini-chat.js — Chat IA estilo Gemini (AICascadeWidget)
   ============================================================================
   Funciones estilo Gemini:
     * Streaming token-a-token (SSE /api/chat/stream) con caret animado.
     * Historial de conversaciones persistente (localStorage).
     * Render markdown-lite (negritas, código, listas) + botón copiar código.
     * Acciones por respuesta: Copiar, Regenerar, Me gusta / No me gusta.
     * Chips de sugerencia en la pantalla de bienvenida.
     * Selector de modelo (Cascade Auto / Gemini / Groq / GPT-4o mini).
     * Adjunto: muestra chip y lo referencia en el mensaje.
   ============================================================================ */
(function () {
  "use strict";

  var STORE = "aicascade_gem_chats_v1";
  var MODELS = [
    { id: "auto",           label: "Cascade Auto", hint: "La cascada elige el mejor" },
    { id: "cascade-smart",  label: "Gemini Flash",  hint: "Calidad gratis" },
    { id: "groq-fast",      label: "Groq GPT-OSS",  hint: "Máxima velocidad" },
    { id: "gpt-4o-mini",    label: "GPT-4o mini",   hint: "OpenAI" }
  ];
  var SUGGEST = [
    "¿Cómo está mi cascada de IA?",
    "Resume el estado de los proveedores",
    "Explícame qué es el failover",
    "Dame 3 ideas para mejorar el HUD"
  ];

  var state = { convs: {}, order: [], current: null, busy: false, model: "auto", attach: null };

  /* ---------------- persistencia ---------------- */
  function load() {
    try {
      var raw = localStorage.getItem(STORE);
      if (raw) { var d = JSON.parse(raw); state.convs = d.convs || {}; state.order = d.order || []; }
    } catch (e) {}
  }
  function save() {
    try {
      localStorage.setItem(STORE, JSON.stringify({ convs: state.convs, order: state.order }));
    } catch (e) {}
  }
  function newConv() {
    var id = "c" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
    state.convs[id] = { id: id, title: "Nueva conversación", messages: [], ts: Date.now() };
    state.order.unshift(id);
    state.current = id;
    save();
    return state.convs[id];
  }
  function conv() {
    if (!state.current || !state.convs[state.current]) return newConv();
    return state.convs[state.current];
  }

  /* ---------------- markdown-lite ---------------- */
  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }
  function md(src) {
    if (!src) return "";
    var out = "", inCode = false, lines = String(src).split("\n"), i = 0;
    while (i < lines.length) {
      var ln = lines[i];
      if (/^```/.test(ln)) {
        if (inCode) { out += "</code></pre>"; inCode = false; }
        else { out += "<pre><code>"; inCode = true; }
        i++; continue;
      }
      if (inCode) { out += esc(ln) + "\n"; i++; continue; }
      if (/^\s*[-*]\s+/.test(ln)) { out += "<li>" + inline(ln.replace(/^\s*[-*]\s+/, "")) + "</li>"; i++; continue; }
      if (/^\s*\d+\.\s+/.test(ln)) { out += "<li>" + inline(ln.replace(/^\s*\d+\.\s+/, "")) + "</li>"; i++; continue; }
      if (/^#{1,3}\s/.test(ln)) { out += "<strong>" + inline(ln.replace(/^#{1,3}\s/, "")) + "</strong><br>"; i++; continue; }
      out += inline(ln) + "\n"; i++;
    }
    if (inCode) out += "</code></pre>";
    return out.replace(/\n{2,}/g, "<br><br>").replace(/\n/g, "<br>")
      .replace(/<li><br><\/li>/g, "</ul><ul>");
  }
  function inline(s) {
    return esc(s)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  }

  /* ---------------- DOM ---------------- */
  var panel = document.getElementById("panel-chat");
  if (!panel) return;

  panel.innerHTML =
    '<div class="gem-wrap">' +
      '<aside class="gem-side" id="gemSide">' +
        '<div class="gem-side-head"><span>Recientes</span></div>' +
        '<div class="gem-side-list" id="gemSideList"></div>' +
        '<div class="gem-side-foot"><button class="gem-new-btn" id="gemNew">+ Nueva conversación</button></div>' +
      '</aside>' +
      '<div class="gem-main">' +
        '<div class="gem-topbar">' +
          '<div class="gem-sparkle">✦</div>' +
          '<div><div class="gem-title">AICascade</div><div class="gem-sub" id="gemSub">Cascada con failover automático</div></div>' +
          '<div class="spacer"></div>' +
          '<div class="gem-model" id="gemModel" title="Cambiar modelo"><span id="gemModelLabel">Cascade Auto</span>▾</div>' +
          '<span class="gem-badge online" id="gemBadge"><span class="d"></span>Backend ● Local</span>' +
        '</div>' +
        '<div class="gem-log" id="gemLog"></div>' +
        '<div class="gem-inputbar">' +
          '<div class="gem-inputrow">' +
            '<button class="gem-iconbtn" id="gemAttachBtn" title="Adjuntar archivo">📎</button>' +
            '<input class="gem-attach" id="gemAttach" type="file" accept="image/*,.txt,.md,.json,.csv">' +
            '<input id="gemInput" type="text" placeholder="Escribe tu mensaje…" autocomplete="off">' +
            '<button class="gem-send" id="gemSend" title="Enviar">➤</button>' +
          '</div>' +
          '<div class="gem-hint" id="gemHint">Enter para enviar · Shift+Enter para salto de línea · la cascada usa tus claves del Vault</div>' +
        '</div>' +
      '</div>' +
    '</div>';

  var $log = document.getElementById("gemLog");
  var $input = document.getElementById("gemInput");
  var $send = document.getElementById("gemSend");

  /* ---------------- render ---------------- */
  function renderSide() {
    var el = document.getElementById("gemSideList");
    el.innerHTML = state.order.filter(function (id) { return state.convs[id]; }).map(function (id) {
      var c = state.convs[id];
      return '<div class="gem-conv' + (id === state.current ? " active" : "") + '" data-id="' + id + '">' +
        '<span class="dot"></span><span>' + esc(c.title).slice(0, 24) + '</span></div>';
    }).join("");
  }
  function renderMessages() {
    var c = conv();
    if (!c || !c.messages.length) { renderWelcome(); return; }
    $log.innerHTML = c.messages.map(function (m) { return bubble(m, true); }).join("");
    scrollDown();
  }
  function renderWelcome() {
    $log.innerHTML =
      '<div class="gem-welcome">' +
        '<div class="gem-sparkle" style="width:54px;height:54px;font-size:1.6rem;margin:0 auto;">✦</div>' +
        '<h1>¡Hola! Soy AICascade</h1>' +
        '<p>Tu asistente con cascada de IA y failover automático. Pregúntame lo que quieras.</p>' +
        '<div class="gem-chips">' +
          SUGGEST.map(function (s) { return '<button class="gem-chip" data-q="' + esc(s) + '">' + esc(s) + '</button>'; }).join("") +
        '</div>' +
      '</div>';
  }
  function scrollDown() { $log.scrollTop = $log.scrollHeight; }

  function bubble(m, withActions) {
    var mine = m.role === "user";
    var cls = mine ? "user" : "ai";
    var av = mine ? '<div class="gem-avatar me">Tú</div>'
                  : '<div class="gem-avatar ai">✦</div>';
    var html = mine ? esc(m.content) : md(m.content);
    var caret = m.streaming ? '<span class="gem-caret"></span>' : "";
    var actions = (!mine && withActions) ?
      '<div class="gem-actions">' +
        '<button class="gem-act" data-act="copy" title="Copiar">⧉</button>' +
        '<button class="gem-act" data-act="regen" title="Regenerar">↻</button>' +
        '<button class="gem-act" data-act="like" title="Me gusta">👍</button>' +
        '<button class="gem-act" data-act="dislike" title="No me gusta">👎</button>' +
      '</div>' +
      '<div class="gem-meta">' + esc(m.meta || "") + '</div>'
      : "";
    return '<div class="gem-msg ' + cls + '" data-id="' + (m.id || "") + '">' +
      av + '<div class="gem-body">' +
        '<div class="gem-bubble">' + html + caret + '</div>' +
        actions +
      '</div></div>';
  }

  /* ---------------- envío con streaming ---------------- */
  async function send(text) {
    text = (text || "").trim();
    if (!text || state.busy) return;
    if (state.attach) { text = "[Archivo adjunto: " + state.attach.name + "] " + text; clearAttach(); }
    state.busy = true; $send.disabled = true;

    var c = conv();
    if (!c.messages.length) c.title = text.slice(0, 28) || c.title;
    c.messages.push({ id: "u" + Date.now(), role: "user", content: text, meta: "" });
    var aiId = "a" + Date.now();
    c.messages.push({ id: aiId, role: "ai", content: "", streaming: true, meta: "" });
    save(); renderSide(); renderMessages();
    var aiMsg = c.messages.find(function (m) { return m.id === aiId; });
    var bubbleEl = $log.querySelector('[data-id="' + aiId + '"] .gem-bubble');

    var model = state.model === "auto" ? null : state.model;
    var provider = "", modelName = "", started = 0, full = "";

    try {
      if (window.ChatStream && window.ChatStream.send) {
        // SSE real: token por token
        var res = await window.ChatStream.send(text, model, function (prov, chunk) {
          full += chunk;
          aiMsg.content = full;
          if (!started) { started = 1; provider = prov; }
          if (bubbleEl) bubbleEl.innerHTML = md(full) + '<span class="gem-caret"></span>';
          scrollDown();
        });
        aiMsg.content = res.response || full;
        aiMsg.streaming = false;
        aiMsg.meta = (res.provider || provider || "") + (res.mode === "simulated" ? " · simulado" : "");
      } else if (window.AIBackend) {
        var r = await window.AIBackend.chat(text, model);
        aiMsg.content = r.response || "";
        aiMsg.streaming = false;
        aiMsg.meta = (r.provider || "") + (r.model ? " · " + r.model : "");
      } else {
        throw new Error("sin backend disponible");
      }
    } catch (e) {
      aiMsg.content = "[ERROR] " + (e.message || e);
      aiMsg.streaming = false;
      aiMsg.meta = "";
    }
    save(); renderMessages();
    state.busy = false; $send.disabled = false; $input.focus();
  }

  function regenerate() {
    var c = conv();
    if (!c || state.busy) return;
    // borrar última respuesta y reenviar el último prompt del usuario
    var lastUser = null;
    for (var i = c.messages.length - 1; i >= 0; i--) {
      if (c.messages[i].role === "user") { lastUser = c.messages[i]; break; }
    }
    while (c.messages.length && c.messages[c.messages.length - 1].role === "ai") c.messages.pop();
    if (lastUser) send(lastUser.content);
  }

  /* ---------------- adjunto ---------------- */
  function clearAttach() {
    state.attach = null;
    var b = document.getElementById("gemAttachBtn");
    if (b) b.style.background = "rgba(11,132,255,.1)";
  }
  function handleFile(f) {
    if (!f) return;
    state.attach = { name: f.name };
    var b = document.getElementById("gemAttachBtn");
    if (b) b.style.background = "rgba(52,199,89,.25)";
  }

  /* ---------------- wiring ---------------- */
  $input.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send($input.value); }
    else if (e.key === "Enter" && e.shiftKey) { /* salto de línea nativo */ }
  });
  $send.addEventListener("click", function () { send($input.value); });
  document.getElementById("gemAttachBtn").addEventListener("click", function () {
    document.getElementById("gemAttach").click();
  });
  document.getElementById("gemAttach").addEventListener("change", function (e) {
    handleFile(e.target.files[0]); e.target.value = "";
  });
  document.getElementById("gemNew").addEventListener("click", function () {
    newConv(); renderSide(); renderMessages(); $input.focus();
  });
  document.getElementById("gemModel").addEventListener("click", function () {
    var idx = MODELS.findIndex(function (m) { return m.id === state.model; });
    idx = (idx + 1) % MODELS.length;
    state.model = MODELS[idx].id;
    document.getElementById("gemModelLabel").textContent = MODELS[idx].label;
    document.getElementById("gemSub").textContent = MODELS[idx].hint;
  });

  // acciones y chips (delegación)
  $log.addEventListener("click", function (e) {
    var chip = e.target.closest(".gem-chip");
    if (chip) { send(chip.getAttribute("data-q")); return; }
    var act = e.target.closest(".gem-act");
    if (act) {
      var msgEl = act.closest(".gem-msg");
      var id = msgEl ? msgEl.getAttribute("data-id") : null;
      var c = conv();
      var m = c.messages.find(function (x) { return x.id === id; });
      var action = act.getAttribute("data-act");
      if (action === "copy" && m) { copyText(m.content, act); }
      else if (action === "regen") { regenerate(); }
      else if (action === "like" && m) { m.meta = "👍 " + (m.meta || ""); renderMessages(); }
      else if (action === "dislike" && m) { m.meta = "👎 " + (m.meta || ""); renderMessages(); }
      return;
    }
  });
  document.getElementById("gemSideList").addEventListener("click", function (e) {
    var el = e.target.closest(".gem-conv");
    if (!el) return;
    state.current = el.getAttribute("data-id");
    renderSide(); renderMessages();
  });

  function copyText(txt, btn) {
    var done = function () { btn.textContent = "✓"; setTimeout(function () { btn.textContent = "⧉"; }, 1200); };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(done).catch(function () {});
    } else {
      var ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta);
      ta.select(); try { document.execCommand("copy"); } catch (e) {} document.body.removeChild(ta); done();
    }
  }

  // parche: app.js legacy llama a sendChat() -> redirigir al chat Gemini
  window.app && (window.app.sendChat = function () { send(document.getElementById("gemInput").value); });

  /* ---------------- init ---------------- */
  load();
  if (!state.order.length) newConv();
  renderSide();
  renderMessages();
  $input.focus();
  console.log("[gemini-chat] listo · conversaciones:", state.order.length);
})();
