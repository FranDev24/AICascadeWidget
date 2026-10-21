#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AICascadeWidget - Generador de logo + iconos (sigilo cascada minimalista).
Concepto: 3 chevrones descendentes (cascada/failover T1>T2>T3) + nodo/orbe
central (sigilo: circulo = unidad/proteccion, triangulo invertido = agua/
flujo/transformacion). Estilo flat como VSCode/Claude/Gemini: 1 forma,
2 tonos, legible a 16px.
Genera: icons/logo.svg, icon-16/32/180/512.png, og-cover.png, app.ico
Requiere: pip install pillow
Uso: python tools/make_logo.py
"""
import os
import math

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICONS = os.path.join(BASE, "icons")
os.makedirs(ICONS, exist_ok=True)
os.makedirs(os.path.join(BASE, "tools"), exist_ok=True)

BG_DARK = (10, 11, 14)
CYAN = (34, 211, 238)
VIOLET = (139, 92, 246)
WHITE = (255, 255, 255)

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#22d3ee"/>
      <stop offset="1" stop-color="#8b5cf6"/>
    </linearGradient>
    <radialGradient id="orb" cx="0.5" cy="0.38" r="0.72">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="0.42" stop-color="#22d3ee"/>
      <stop offset="1" stop-color="#6366f1"/>
    </radialGradient>
  </defs>
  <rect width="512" height="512" rx="116" fill="#0a0b0e"/>
  <!-- SIGILO: anillo = unidad/proteccion; orb = conciencia/nodo; -->
  <!-- 3 chevrones = cascada/failover T1&gt;T2&gt;T3 (agua/transformacion). -->
  <!-- Proporcion: orb en tercio superior (vision), cascada al centro (flujo). -->
  <circle cx="256" cy="262" r="148" fill="none" stroke="url(#g)" stroke-width="15" opacity="0.92"/>
  <circle cx="256" cy="262" r="148" fill="none" stroke="#ffffff" stroke-width="2" opacity="0.12"/>
  <path d="M176 206 L256 276 L336 206" fill="none" stroke="url(#g)" stroke-width="36" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M176 276 L256 346 L336 276" fill="none" stroke="url(#g)" stroke-width="36" stroke-linecap="round" stroke-linejoin="round" opacity="0.62"/>
  <path d="M198 336 L256 386 L314 336" fill="none" stroke="url(#g)" stroke-width="27" stroke-linecap="round" stroke-linejoin="round" opacity="0.34"/>
  <circle cx="256" cy="172" r="31" fill="url(#orb)"/>
  <circle cx="247" cy="163" r="9" fill="#ffffff" opacity="0.85"/>
</svg>
"""

def _draw_png(size, path):
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("[ERROR] pip install pillow")
        raise SystemExit(1)
    S = size
    img = Image.new("RGBA", (S, S), BG_DARK + (255,))
    d = ImageDraw.Draw(img)
    u = S / 512.0
    # fondo redondeado
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=int(116 * u), fill=BG_DARK + (255,))
    cx, cy = S / 2, S / 2
    # anillo
    d.ellipse([cx - 150 * u, cy - 150 * u, cx + 150 * u, cy + 150 * u],
              outline=CYAN + (255,), width=max(2, int(14 * u)))
    # chevrones
    def chev(y1, y2, w, col):
        d.line([(176 * u, y1 * u), (256 * u, y2 * u)], fill=col, width=int(w * u), joint="curve")
        d.line([(256 * u, y2 * u), (336 * u, y1 * u)], fill=col, width=int(w * u), joint="curve")
    chev(198, 268, 34, CYAN + (255,))
    chev(268, 338, 34, (90, 170, 245, 255))
    d.line([(196 * u, 328 * u), (256 * u, 380 * u)], fill=(120, 130, 245, 255), width=max(2, int(26 * u)), joint="curve")
    d.line([(256 * u, 380 * u), (316 * u, 328 * u)], fill=(120, 130, 245, 255), width=max(2, int(26 * u)), joint="curve")
    # orbe
    r = 30 * u
    d.ellipse([cx - r, 168 * u - r, cx + r, 168 * u + r], fill=WHITE + (255,))
    d.ellipse([cx - r * 0.6, 168 * u - r * 0.6, cx + r * 0.6, 168 * u + r * 0.6], fill=CYAN + (255,))
    img.save(path)
    print("OK", path)

def main():
    with open(os.path.join(ICONS, "logo.svg"), "w", encoding="utf-8") as f:
        f.write(SVG)
    print("OK", os.path.join(ICONS, "logo.svg"))
    for sz, name in [(16, "icon-16.png"), (32, "icon-32.png"),
                     (180, "icon-180.png"), (512, "icon-512.png")]:
        _draw_png(sz, os.path.join(ICONS, name))
    # og-cover 1200x630 con logo centrado
    try:
        from PIL import Image
        cover = Image.new("RGB", (1200, 630), BG_DARK)
        logo = Image.open(os.path.join(ICONS, "icon-512.png")).convert("RGBA").resize((380, 380))
        cover.paste(logo, (410, 125), logo)
        cover.save(os.path.join(ICONS, "og-cover.png"))
        print("OK", os.path.join(ICONS, "og-cover.png"))
        # .ico multi-resolucion (16..256) para Windows
        imgs = []
        for s in (16, 32, 48, 64, 128, 256):
            p = os.path.join(ICONS, f"_tmp{s}.png")
            _draw_png(s, p)
            imgs.append(Image.open(p).convert("RGBA"))
        imgs[0].save(os.path.join(BASE, "app.ico"), sizes=[(s, s) for s in (16, 32, 48, 64, 128, 256)])
        print("OK", os.path.join(BASE, "app.ico"))
        for s in (16, 32, 48, 64, 128, 256):
            try:
                os.remove(os.path.join(ICONS, f"_tmp{s}.png"))
            except OSError:
                pass
    except ImportError:
        print("[WARN] pillow faltante: pip install pillow")

if __name__ == "__main__":
    main()
