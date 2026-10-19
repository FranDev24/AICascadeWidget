#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera los PNG del PWA desde icons/icon.svg (usa cairosvg o Pillow si están).
Uso: venv\Scripts\python.exe tools\make_icons.py
Si no hay librerías, imprime instrucciones para generarlo online en 1 minuto.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ICONS = os.path.join(ROOT, "icons")
SVG = os.path.join(ICONS, "icon.svg")
SIZES = [16, 32, 180, 192, 512]

def with_cairosvg():
    import cairosvg
    for s in SIZES:
        out = os.path.join(ICONS, f"icon-{s}.png")
        cairosvg.svg2png(url=SVG, write_to=out, output_width=s, output_height=s)
        print("OK", out)

def with_pillow_fallback():
    # Dibuja un icono simple (rayo sobre fondo oscuro) si no hay cairosvg
    from PIL import Image, ImageDraw
    for s in SIZES:
        img = Image.new("RGBA", (s, s), (10, 10, 15, 255))
        d = ImageDraw.Draw(img)
        m = s // 8
        d.rounded_rectangle([m, m, s - m, s - m], radius=s // 6, outline=(255, 255, 255, 60))
        # rayo simplificado
        w = s / 512
        bolt = [(285*w, 90*w), (160*w, 290*w), (250*w, 290*w), (230*w, 422*w), (365*w, 222*w), (270*w, 222*w)]
        d.polygon(bolt, fill=(96, 165, 250, 255))
        out = os.path.join(ICONS, f"icon-{s}.png")
        img.save(out)
        print("OK", out)

def og_cover():
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (1200, 630), (10, 10, 15))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([60, 60, 1140, 570], radius=60, outline=(96, 165, 250), width=6)
        d.text((100, 220), "AICascade Widget", fill=(255, 255, 255))
        d.text((100, 300), "Gestor de Cascada IA — Liquid Glass", fill=(150, 160, 180))
        out = os.path.join(ICONS, "og-cover.png")
        img.save(out)
        print("OK", out)
    except Exception as e:
        print("OG skip:", e)

if __name__ == "__main__":
    os.makedirs(ICONS, exist_ok=True)
    try:
        with_cairosvg()
    except Exception as e:
        print("cairosvg no disponible, usando Pillow:", e)
        try:
            with_pillow_fallback()
        except Exception as e2:
            print("ERROR: instala Pillow: pip install pillow")
            print("O genera los PNG online: https://cloudconvert.com/svg-to-png (512,192,180,32,16)")
            sys.exit(1)
    og_cover()
