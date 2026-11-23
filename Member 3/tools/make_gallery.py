"""Generate the 10 built-in gallery pictures (abstract, textured, royalty-free).

Run once:  python tools/make_gallery.py
Textured images are deliberate: the image algorithm hides data in busy areas,
so these hold far more than flat colours would. Replace with your own photos if you like.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = Path(__file__).resolve().parents[1] / "static" / "gallery"
W, H = 960, 720

PALETTES = {
    "Ocean": ["#0b3c8d", "#2563eb", "#60a5fa", "#e0f2fe"],
    "Sunset": ["#7c2d12", "#ea580c", "#fbbf24", "#fde68a"],
    "Forest": ["#052e16", "#15803d", "#4ade80", "#d9f99d"],
    "Lavender": ["#3b0764", "#7e22ce", "#c084fc", "#f3e8ff"],
    "Ember": ["#450a0a", "#b91c1c", "#f87171", "#fee2e2"],
    "Glacier": ["#0f172a", "#0e7490", "#67e8f9", "#ecfeff"],
    "Dune": ["#422006", "#a16207", "#facc15", "#fef9c3"],
    "Rose": ["#500724", "#be185d", "#f472b6", "#fce7f3"],
    "Slate": ["#020617", "#334155", "#94a3b8", "#f1f5f9"],
    "Mint": ["#042f2e", "#0f766e", "#5eead4", "#f0fdfa"],
}


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def gradient(colors, angle):
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    t = (xx * math.cos(angle) + yy * math.sin(angle))
    t = (t - t.min()) / (t.max() - t.min())
    stops = np.array([hex_rgb(c) for c in colors], np.float32)
    pos = np.linspace(0, 1, len(stops))
    out = np.zeros((H, W, 3), np.float32)
    for ch in range(3):
        out[..., ch] = np.interp(t, pos, stops[:, ch])
    return out


def make(name, colors, seed):
    rng = random.Random(seed)
    base = gradient(colors, rng.uniform(0, math.pi))
    im = Image.fromarray(base.clip(0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(im, "RGBA")
    style = seed % 5
    for _ in range(rng.randint(14, 30)):
        c = hex_rgb(rng.choice(colors)) + (rng.randint(40, 120),)
        x, y = rng.randint(-100, W), rng.randint(-100, H)
        r = rng.randint(40, 320)
        if style == 0:
            draw.ellipse([x, y, x + r, y + r], fill=c)
        elif style == 1:
            draw.rectangle([x, y, x + r, y + r * rng.uniform(0.3, 1.2)], fill=c)
        elif style == 2:
            draw.polygon([(x, y), (x + r, y + rng.randint(-r, r)), (x + rng.randint(-r, r), y + r)], fill=c)
        elif style == 3:
            draw.line([x, y, x + r * 2, y + rng.randint(-r, r)], fill=c, width=rng.randint(6, 40))
        else:
            draw.arc([x, y, x + r, y + r], rng.randint(0, 360), rng.randint(0, 360), fill=c, width=rng.randint(8, 30))
    im = im.filter(ImageFilter.GaussianBlur(rng.uniform(0.5, 2.5)))
    arr = np.asarray(im).astype(np.int16)
    noise = np.random.default_rng(seed).normal(0, 9, arr.shape)  # film grain -> texture for hiding
    arr = (arr + noise).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    index = []
    for i, (name, colors) in enumerate(PALETTES.items(), 1):
        im = make(name, colors, i * 7919)
        file = f"{i:02d}-{name.lower()}.png"
        im.save(OUT / file, optimize=True)
        im.resize((320, 240), Image.LANCZOS).save(OUT / f"thumb-{file}", optimize=True)
        index.append({"id": i, "name": name, "file": file, "thumb": f"thumb-{file}", "width": W, "height": H})
        print("wrote", file)
    (OUT / "index.json").write_text(json.dumps(index, indent=2))


if __name__ == "__main__":
    main()
