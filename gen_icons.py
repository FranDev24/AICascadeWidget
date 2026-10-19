#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera iconos PWA/OG para AICascadeWidget (PNG puro, sin PIL)."""
import zlib, struct, os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
os.makedirs(OUT, exist_ok=True)

def png(path, w, h, pixel_fn):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            r, g, b, a = pixel_fn(x, y)
            raw += bytes((max(0,min(255,r)), max(0,min(255,g)), max(0,min(255,b)), max(0,min(255,a))))
    def chunk(tag, data):
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)
    print("OK", path, os.path.getsize(path), "bytes")

def lerp(a, b, t): return int(a + (b - a) * t)

def brand_pixel(size, rounding=0.225):
    rad = size * rounding
    def fn(x, y):
        # esquinas redondeadas
        cx = min(x, size - 1 - x); cy = min(y, size - 1 - y)
        if cx < rad and cy < rad:
            dx, dy = rad - cx, rad - cy
            if dx*dx + dy*dy > rad*rad:
                return (0, 0, 0, 0)
        # gradiente diagonal azul->violeta + brillo
        t = (x + y) / (2 * size)
        r = lerp(59, 139, t); g = lerp(130, 92, t); b = lerp(246, 246, t)
        # destello especular esquina sup-izq
        d = ((x - size*0.28)**2 + (y - size*0.22)**2) ** 0.5
        if d < size*0.30:
            k = 1 - d/(size*0.30)
            r = lerp(r, 255, k*0.35); g = lerp(g, 255, k*0.35); b = lerp(b, 255, k*0.35)
        return (r, g, b, 255)
    return fn

png(os.path.join(OUT, "icon-180.png"), 180, 180, brand_pixel(180))
png(os.path.join(OUT, "icon-32.png"), 32, 32, brand_pixel(32, 0.28))
png(os.path.join(OUT, "icon-16.png"), 16, 16, brand_pixel(16, 0.30))

# ---- OG cover 1200x630: fondo titanio + 'AC' pixel-art centrado ----
GLYPH = {
 'A': ["01110","10001","10001","11111","10001","10001","10001"],
 'C': ["01111","10000","10000","10000","10000","10000","01111"],
}
def og_pixel(w, h):
    W, H = 1200, 630
    def fn(x, y):
        t = (x/W + y/H)/2
        r = lerp(10, 18, t); g = lerp(11, 20, t); b = lerp(14, 26, t)  # obsidiana
        # neblina cobalto
        d = ((x - W*0.82)**2 + (y + H*0.1 - H*0.55)**2) ** 0.5
        if d < 480:
            k = 1 - d/480; r = lerp(r, 20, k*0.5); g = lerp(g, 70, k*0.5); b = lerp(b, 160, k*0.5)
        # letras AC centradas (pixel 5x7, celda 56px)
        cell, gap = 56, 22
        word = "AC"
        gw = (5*cell)*2 + gap
        x0 = (W - gw)//2; y0 = (H - 7*cell)//2
        col = 0
        for ch in word:
            rows = GLYPH[ch]
            for ry, rowbits in enumerate(rows):
                for rx, bit in enumerate(rowbits):
                    if bit == '1':
                        px = x0 + col*(5*cell+gap) + rx*cell
                        py = y0 + ry*cell
                        if px <= x < px+cell-6 and py <= y < py+cell-6:
                            # metal plateado con destello
                            tt = ((x-px)/cell + (y-py)/cell)/2
                            rr = lerp(245, 200, tt); gg = lerp(247, 210, tt); bb = lerp(250, 222, tt)
                            # glow cobalto en borde
                            return (max(r,rr), max(g,gg), max(b,bb), 255)
            col += 1
        return (r, g, b, 255)
    return fn

png(os.path.join(OUT, "og-cover.png"), 1200, 630, og_pixel(1200, 630))
print("Todos los iconos generados.")