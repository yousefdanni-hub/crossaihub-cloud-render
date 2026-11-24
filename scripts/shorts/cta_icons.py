#!/usr/bin/env python3
"""Shared CTA icon set (Danni 11-23): the universally known SHAPES, drawn by us (no YouTube logo, no wordmark, no play-button logo):
  like(size, color)      → thumbs-up
  share(size, color)     → curved forward arrow
  bell(size, color)      → notification bell
  subscribe_pill(h, font)→ red rounded pill with white "SUBSCRIBE" + bell
Drawn at 4× and downsampled (smooth edges). Used by cta_long.card (end card), the CE corner badge and every CE card."""
from PIL import Image, ImageDraw
RED = (204, 0, 0); WHITE = (255, 255, 255)


def _canvas(s): S = s * 4; return Image.new("RGBA", (S, S), (0, 0, 0, 0)), S


def like(size, color):
    im, S = _canvas(size); d = ImageDraw.Draw(im); c = color + (255,) if len(color) == 3 else color
    d.rounded_rectangle([0.06 * S, 0.44 * S, 0.24 * S, 0.94 * S], radius=0.04 * S, fill=c)              # cuff
    d.rounded_rectangle([0.30 * S, 0.40 * S, 0.92 * S, 0.94 * S], radius=0.10 * S, fill=c)              # palm + fingers block
    d.polygon([(0.30 * S, 0.46 * S), (0.50 * S, 0.08 * S), (0.62 * S, 0.10 * S), (0.64 * S, 0.22 * S), (0.58 * S, 0.44 * S)], fill=c)   # thumb
    d.ellipse([0.48 * S, 0.04 * S, 0.66 * S, 0.20 * S], fill=c)
    for y in (0.56, 0.70, 0.84):                                                                         # finger lines
        d.line([(0.66 * S, y * S), (0.92 * S, y * S)], fill=(0, 0, 0, 0), width=int(0.035 * S))
    return im.resize((size, size), Image.LANCZOS)


def share(size, color):
    im, S = _canvas(size); d = ImageDraw.Draw(im); c = color + (255,) if len(color) == 3 else color; w = int(0.13 * S)
    d.arc([0.10 * S, 0.30 * S, 0.90 * S, 1.30 * S], start=190, end=270, fill=c, width=w)                 # curved shaft
    d.line([(0.50 * S, 0.36 * S), (0.62 * S, 0.36 * S)], fill=c, width=w)
    d.polygon([(0.58 * S, 0.10 * S), (0.96 * S, 0.36 * S), (0.58 * S, 0.62 * S)], fill=c)                # arrow head
    return im.resize((size, size), Image.LANCZOS)


def bell(size, color):
    im, S = _canvas(size); d = ImageDraw.Draw(im); c = color + (255,) if len(color) == 3 else color
    d.pieslice([0.18 * S, 0.10 * S, 0.82 * S, 0.80 * S], start=180, end=360, fill=c)                    # dome
    d.rectangle([0.18 * S, 0.44 * S, 0.82 * S, 0.74 * S], fill=c)                                       # body
    d.polygon([(0.06 * S, 0.80 * S), (0.18 * S, 0.66 * S), (0.82 * S, 0.66 * S), (0.94 * S, 0.80 * S)], fill=c)   # flare
    d.ellipse([0.40 * S, 0.80 * S, 0.60 * S, 0.98 * S], fill=c)                                         # clapper
    d.ellipse([0.44 * S, 0.02 * S, 0.56 * S, 0.14 * S], fill=c)                                         # top knob
    return im.resize((size, size), Image.LANCZOS)


def subscribe_pill(h, font, label="SUBSCRIBE"):
    """red rounded pill, white bell + white SUBSCRIBE (generic shape; no logo)"""
    tmp = ImageDraw.Draw(Image.new("RGBA", (10, 10))); tw = tmp.textlength(label, font=font); b = int(h * 0.55)
    w = int(h * 0.55 + b + h * 0.25 + tw + h * 0.55); im = Image.new("RGBA", (w * 4, h * 4), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], radius=h * 2, fill=RED + (255,)); im = im.resize((w, h), Image.LANCZOS)
    bi = bell(b, WHITE); im.alpha_composite(bi, (int(h * 0.5), (h - b) // 2))
    d = ImageDraw.Draw(im); asc = font.getbbox(label); d.text((int(h * 0.5) + b + int(h * 0.25), (h - (asc[3] - asc[1])) // 2 - asc[1]), label, font=font, fill=WHITE + (255,))
    return im
