// ============================================================================
// chat-stream.js — Streaming SSE para el HUD (AICascadeWidget)
// Vende token-por-token via /api/chat/stream y degrada a /api/chat si falla.
// Integración no-invasiva: parchea AIBackend.chat SIN cambiar su contrato
// (app.js/terminal.js siguen recibiendo {ok,mode,provider,model,response,...}).
// Referencias: OpenAI "Streaming API responses" (SSE), failover por TTFB.
// ============================================================================

(function () {
  "use strict";
  if (!window.AIBackend || !window.AIBackend.baseUrl) return; // backend.js debe cargar antes

  var BASE = window.AIBackend.baseUrl;
  var _origChat = window.AIBackend.chat.bind(window.AIBackend);

  function _sseParse(text) {
    return text.split(/\n\n/).map(function (blk) {
      var lines = blk.split("\n").filter(Boolean);
      if (!lines.length || !/^data:/.test(lines[0])) return null;
      var raw = lines[0].slice(5).trim();
      if (raw === "[DONE]") return { event: "done-done" };
      try { return JSON.parse(raw); } catch (e) { return null; }
    }).filter(Boolean);
  }

  /** Stream real. onDelta(provider, content, model) -> por chunk; res -> final. */
  async function chatStream(message, model, onDelta) {
    var res = await fetch(BASE + "/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message, model: model || null }),
    });
    if (!res.ok || !res.body) throw new Error("HTTP " + res.status);
    var reader = res.body.getReader();
    var decoder = new TextDecoder();
    var buf = "", acum = "", meta = { provider: null, model: null }, final = null;
    while (true) {
      var chunk = await reader.read();
      if (chunk.done) break;
      buf += decoder.decode(chunk.value, { stream: true });
      var idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        var block = buf.slice(0, idx + 2); buf = buf.slice(idx + 2);
        _sseParse(block).forEach(function (ev) {
          if (ev.event === "meta") { meta.provider = ev.provider; meta.model = ev.model; }
          else if (ev.event === "delta") {
            acum += ev.content;
            if (onDelta) { try { onDelta(ev.provider, ev.content, ev.model || meta.model); } catch (e) {} }
          } else if (ev.event === "done") { final = ev; }
        });
      }
    }
    if (!final) throw new Error("stream sin done");
    if (final.ok === false) throw new Error(final.error || "stream abortado");
    // Contrato IDENTICO a /api/chat para app.js / terminal.js
    return { ok: true, mode: final.provider === "simulated" ? "simulated" : "live",
             provider: meta.provider || final.provider,
             model: meta.model || null, response: acum,
             attempts: [{ provider: meta.provider || final.provider, error: null }],
             latency_ms: final.latency_ms || null, streamed: true };
  }

  // Parche no-invasivo: stream + burbuja progresiva (deja la final de app.js)
  window.AIBackend.chat = async function (message, model) {
    var chatLog = document.getElementById("chatLog");
    var tempBubble = null;
    if (chatLog && typeof window.fetch === "function") {
      try {
        // burbuja "fantasma" progresiva; app.js pinta la final al resolver
        var ghost = document.createElement("div");
        ghost.setAttribute("data-chatstream", "ghost");
        ghost.style.cssText = "white-space:pre-wrap;opacity:.65;font-size:inherit;";
        ghost.textContent = "▌";
        chatLog.appendChild(ghost);
        tempBubble = ghost;
        var out = await chatStream(message, model, function (_p, content) {
          ghost.textContent = (ghost.textContent === "▌" ? "" : ghost.textContent) + content;
        });
        if (ghost.parentNode) ghost.parentNode.removeChild(ghost);
        return out;
      } catch (e) {
        if (tempBubble && tempBubble.parentNode) tempBubble.parentNode.removeChild(tempBubble);
        return _origChat(message, model);  // fallback estable
      }
    }
    return _origChat(message, model);
  };

  // API publica para terminal.js/otros que quieran streaming explicito
  window.ChatStream = { send: chatStream };
  console.log("[chat-stream] SSE listo (fallback a /api/chat si falla).");
})();
