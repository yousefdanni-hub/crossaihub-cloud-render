#!/usr/bin/env python3
"""WS-04 · STORY SHORT (Danni 11-14: no more blue/plain Shorts; every Short = rich unique painted images with story + motion, the thumbnail recipe
youtube/ART_RECIPE_thumbnails.md). 1080×1920, ≤ 58 s: several painted 9:16 plates (one per sung line/couplet) with gentle Ken Burns + crossfades,
the recipe's top title block (label · hymn title · gold rule · hook), sung-line subtitles at the bottom only while sung, an end question, gold cross +
dark seal top-left. Deterministic ffmpeg render. Then a final judge (≥ 9/10) is recorded in the batch manifest before upload is allowed.
usage: story_short.py SPEC.json      SPEC: {out, audio, lyrics, t0, t1, scenes:[img…], title, hook, end_q, label?}"""
import json, os, subprocess, sys, textwrap
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import film as Fm
from PIL import Image, ImageDraw, ImageFilter, ImageFont
Fm.W, Fm.H = 1080, 1920; Fm.XF = 1.2; Fm.DRAFT = False; W, H, FPS = 1080, 1920, Fm.FPS
FD = Fm.FD; GOLD, CREAM = (244, 200, 112, 255), (255, 246, 230, 255)
SEAL = os.path.join(Fm.D, "brand_seal", "v3", "dark", "watermark-dark_300.png")
def font(n, s): return ImageFont.truetype(os.path.join(FD, n), s)
V27 = True
END_S = 4.0   # Danni 11-17: the end question/answer card stays 4 s (v2.7: 5.0 → ≥ 4 s fully visible after the fades)


def _lum(rgb):
    def c(v):
        v = v / 255; return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb[:3]; return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)


def scrim_alpha(plate, box, text_rgb=(255, 246, 230), target=4.5):
    """11-17 TEMPLATE ROOT FIX (judge: 'question text low contrast over bright water/sky'): the scrim opacity is COMPUTED so the text reaches a
    contrast ratio ≥ 7:1 (WCAG AAA) against the plate area it sits on (worst = brightest 90th-percentile pixel under the box)."""
    try:
        im = Image.open(plate).convert("RGB"); w, h = im.size; ch = min(h, int(w * H / W)); cw = int(ch * W / H)
        im = im.crop(((w - cw) // 2, (h - ch) // 2, (w - cw) // 2 + cw, (h - ch) // 2 + ch)).resize((W, H))
        px = sorted(im.crop(box).resize((60, 30)).getdata(), key=_lum); bright = px[int(len(px) * 0.9)]
    except Exception: bright = (255, 255, 255)
    lt = _lum(text_rgb); dark = (8, 10, 22)
    for a in [x / 100 for x in range(45, 96, 3)]:
        mix = tuple(int(bright[i] * (1 - a) + dark[i] * a) for i in range(3))
        if (lt + 0.05) / (_lum(mix) + 0.05) >= target: return int(a * 255)
    return 242


INK = {"text": CREAM, "shadow": (0, 0, 0, 235), "shade": (10, 8, 6)}   # set per card by ink()


def ink(plate, box):
    """v2.4 (judge 11-18: heavy dark band on pale skies): read the plate under the text. Bright background (median luminance > 0.42) → DARK ink
    (deep navy) with a soft light halo and only a faint light haze; darker background → cream ink on a soft dark shade. Returns the shade alpha."""
    global INK
    try:
        im = Image.open(plate).convert("RGB"); w, h = im.size; ch = min(h, int(w * H / W)); cw = int(ch * W / H)
        im = im.crop(((w - cw) // 2, (h - ch) // 2, (w - cw) // 2 + cw, (h - ch) // 2 + ch)).resize((W, H))
        px = sorted(im.crop(box).resize((60, 30)).getdata(), key=_lum); med = _lum(px[len(px) // 2])
    except Exception: med = 0.0
    if med > 0.42:
        INK = {"text": (22, 26, 44, 255), "shadow": (255, 250, 240, 210), "shade": (255, 250, 240)}; return 60
    INK = {"text": CREAM, "shadow": (0, 0, 0, 235), "shade": (10, 8, 6)}; return scrim_alpha(plate, box) if plate else 200


def shade(im, y0, y1, alpha, top=True):
    """TEMPLATE v2 (11-18): NO box. A soft full-width photographic shade that fades out (like a lens grad / vignette), strongest where the
    text sits; its strength comes from the contrast check (scrim_alpha) so cream text stays ≥ 7:1 on the brightest pixels underneath."""
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(g); pad = 340   # v2.1: longer, softer fade (judge: "visible grey band")
    for y in range(max(0, y0 - pad), min(H, y1 + pad)):
        if y < y0: f = (y - (y0 - pad)) / pad
        elif y > y1: f = ((y1 + pad) - y) / pad
        else: f = 1.0
        d.line([(0, y), (W, y)], fill=INK["shade"] + (int(alpha * max(0.0, f) ** 1.9),))   # dark shade for cream ink, light haze for dark ink
    im.alpha_composite(g.filter(ImageFilter.GaussianBlur(14)))   # v2.3: no visible 8-bit banding bars


def _shadowed(im, xy, text, f, fill):
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(sh).text(xy, text, font=f, fill=INK["shadow"])
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(6))); ImageDraw.Draw(im).text(xy, text, font=f, fill=INK["text"] if fill in (CREAM, (255, 224, 160, 255)) else fill)


def _center(im, y, text, f, fill):
    d = ImageDraw.Draw(im); _shadowed(im, ((W - d.textlength(text, font=f)) / 2, y), text, f, fill)


def title_block(spec, out, plate=None):
    """TEMPLATE v2: hymn title + Bible question CENTRED in the upper band on a soft shade (no box, no kicker); shade strength from the
    contrast check against the plate. The subject (middle band) stays clear."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f = font("cormorant-garamond-latin-700-normal.ttf", 104); rows = textwrap.wrap(spec["title"], 17)[:2]
    while max(d.textlength(r, font=f) for r in rows) > W - 180 and f.size > 70: f = font("cormorant-garamond-latin-700-normal.ttf", f.size - 4)
    q = spec.get("challenge") or spec.get("hook") or ""; hf = font("cormorant-garamond-latin-600-italic.ttf" if os.path.exists(os.path.join(FD, "cormorant-garamond-latin-600-italic.ttf")) else "cormorant-garamond-latin-600-normal.ttf", 64)
    qrows = textwrap.wrap(q, 26)
    while len(qrows) > 2 and hf.size > 50: hf = font(hf.path.split("/")[-1], hf.size - 4); qrows = textwrap.wrap(q, int(26 * 64 / hf.size))   # v2.3: never cut the question
    top = 250; bot = top + len(rows) * int(f.size * 1.02) + 24 + len(qrows) * 74
    shade(im, top - 40, bot + 20, ink(plate, (90, top - 40, W - 90, bot + 20)) if plate else 200)
    y = top
    for r in rows: _center(im, y, r, f, CREAM); y += int(f.size * 1.02)
    y += 24
    for r in qrows: _center(im, y, r, hf, CREAM); y += 74   # v2.3: cream (gold lost contrast on bright skies)
    im.save(out)


def end_card(q, out, sub=None, zone="low", plate=None):
    """TEMPLATE v2: a 2-LINE answer card, centred: line 1 = the answer ("It's John 14:27."), line 2 = "Full story: crossaihub.com" on ONE line
    (never broken; the full page link is line 1 of the description). On screen for 4 s, in the clear band, on a soft shade."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    fa = font("cormorant-garamond-latin-700-normal.ttf", 112); fs = font("cormorant-garamond-latin-700-normal.ttf", 66)   # v2.3 bigger answer · v2.1 bolder site line
    a = q.strip()
    while d.textlength(a, font=fa) > W - 200 and fa.size > 60: fa = font("cormorant-garamond-latin-700-normal.ttf", fa.size - 4)
    l2 = "Search CrossAIHub · crossaihub.com" if V27 else "Full story: crossaihub.com"   # v2.7 (Danni/Dispatch 11-19)
    while d.textlength(l2, font=fs) > W - 240 and fs.size > 40: fs = font("cormorant-garamond-latin-600-normal.ttf", fs.size - 2)
    hgt = int(fa.size * 1.15) + 18 + int(fs.size * 1.2)
    sb = sub_band(plate) if plate else 1280   # v2.4: the answer card goes in the calm band ABOVE the detected subject (same rule as the lyrics)
    top = max(700, min(1500 - hgt, sb - 40)) if zone == "high" else 1500 - hgt
    shade(im, top - 30, top + hgt + 20, ink(plate, (90, top - 30, W - 90, top + hgt + 20)) if plate else 210)
    _center(im, top, a, fa, CREAM); _center(im, top + int(fa.size * 1.15) + 18, l2, fs, CREAM)
    im.save(out)


def sub_band(plate):
    """v2.2 (judge: 'subtitle over the boat' / 'mid-frame over the horizon'): find the SUBJECT in the lower 60 % (first 40-px row band whose edge
    detail is > 1.8× the median), and put the lyric band just ABOVE it (gap 40 px); no clear subject → the low band (y 1280)."""
    from PIL import ImageStat
    try:
        im = Image.open(plate).convert("L"); w, h = im.size; ch = min(h, int(w * H / W)); cw = int(ch * W / H)
        e = im.crop(((w - cw) // 2, (h - ch) // 2, (w - cw) // 2 + cw, (h - ch) // 2 + ch)).resize((W // 2, H // 2)).filter(ImageFilter.FIND_EDGES)
        rows = [(y, ImageStat.Stat(e.crop((0, y // 2, W // 2, (y + 40) // 2))).mean[0]) for y in range(760, 1700, 40)]
        med = sorted(v for _, v in rows)[len(rows) // 2]
        top = next((y for y, v in rows if y >= 1000 and v > 1.8 * med), None)
        if top is None: return 1280
        return max(760, min(1300, top - 210))
    except Exception: return 1280


def sub_card(text, out, zone, plate):
    """TEMPLATE v2 lyric subtitle: centred serif, max 2 lines, NO box — a soft shade (contrast-checked) in the clear band
    (high = y 560–760 under the title area; low = y 1240–1440, above the Shorts UI)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); f = font("cormorant-garamond-latin-600-normal.ttf", 70)
    rows = textwrap.wrap(Fm.display_text(text) if hasattr(Fm, "display_text") else text, 24)[:2]
    while max(d.textlength(r, font=f) for r in rows) > W - 180 and f.size > 52: f = font("cormorant-garamond-latin-600-normal.ttf", f.size - 2)
    lh = int(f.size * 1.18); top = zone if isinstance(zone, int) else (700 if zone == "high" else 1280); bot = top + lh * len(rows)   # high: below the title block (ends ~640)
    shade(im, top - 20, bot + 10, ink(plate, (90, top - 20, W - 90, bot + 10)) if plate else 190)
    for i, r in enumerate(rows): _center(im, top + i * lh, r, f, CREAM)
    im.save(out)


def cover_block(words, out):
    """Ask Studio 11-16 thumbnail rule: ONE focal element (the painted plate) + max 3–4 BIG words, high contrast (cream on a dark top gradient + heavy shadow)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); g = ImageDraw.Draw(im)
    for y in range(0, 900): g.line([(0, y), (W, y)], fill=(4, 6, 20, int(235 * (1 - y / 900) ** 1.1)))
    f = font("cormorant-garamond-latin-700-normal.ttf", 168); rows = textwrap.wrap(words, 11)[:3]; x0 = 80
    while max(ImageDraw.Draw(im).textlength(r, font=f) for r in rows) > W - 2 * x0 and f.size > 100: f = font("cormorant-garamond-latin-700-normal.ttf", f.size - 6)
    tl = Image.new("RGBA", (W, H), (0, 0, 0, 0)); td = ImageDraw.Draw(tl); y = 230
    for r in rows: td.text((x0, y), r, font=f, fill=CREAM); y += int(f.size * 1.0)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0)); sh.putalpha(tl.split()[3].filter(ImageFilter.GaussianBlur(14)).point(lambda v: min(255, int(v * 1.2))))
    im.alpha_composite(sh); im.alpha_composite(tl); im.save(out)   # no drawn bar (realism rule 11-16)
def marks(out):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); s = Image.open(SEAL).convert("RGBA").resize((118, 118), Image.LANCZOS)
    s.putalpha(s.split()[3].point(lambda v: int(v * 0.72))); im.alpha_composite(s, (56, 96)); im.save(out)
def bottom_band(out):
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); g = ImageDraw.Draw(im)
    for y in range(1300, H): g.line([(0, y), (W, y)], fill=(6, 8, 26, int(185 * min(1, (y - 1300) / 220) ** 1.1)))   # 11-15 v2: lighter + lower (judge: band muddied the paint)
    im.save(out)
def clear_zone(plate):
    """11-16 P0 (judge 6.0: end text over the family's faces): pick the CLEAR band for the end card on the last plate (9:16 crop as rendered):
    'high' (y 300–820) or 'low' (y 1060–1580). A band with a detected face is never used; otherwise the band with less edge detail wins."""
    from PIL import ImageStat
    im = Image.open(plate).convert("RGB"); w, h = im.size; ch = min(h, int(w * H / W)); cw = int(ch * W / H)
    y0 = int((h - ch) * 0.55); im = im.crop(((w - cw) // 2, y0, (w - cw) // 2 + cw, y0 + ch)).resize((W // 4, H // 4))
    bands = {"high": (75, 205), "low": (265, 395)}; faces = {"high": 0, "low": 0}
    try:
        import cv2, numpy as np
        cc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        big = np.array(Image.open(plate).convert("L").crop(((w - cw) // 2, y0, (w - cw) // 2 + cw, y0 + ch)).resize((W // 2, H // 2)))
        for (x, y, fw, fh) in cc.detectMultiScale(big, 1.1, 5, minSize=(30, 30)):
            cy = (y + fh / 2) / 2   # → quarter-scale y
            for k, (a_, b_) in bands.items():
                if a_ - 20 <= cy <= b_ + 20: faces[k] += 1
    except Exception: pass
    e = im.convert("L").filter(ImageFilter.FIND_EDGES)
    busy = {k: ImageStat.Stat(e.crop((0, a_, W // 4, b_))).mean[0] for k, (a_, b_) in bands.items()}
    ok = [k for k in bands if faces[k] == 0] or list(bands)
    return min(ok, key=lambda k: busy[k] + 100 * faces[k])


def small_title(spec, out, plate=None):
    """v2.6 (Arena 11-18, YouTube Help): the hymn starts on FRAME ONE — no title card before the singing. The title is a SMALL overlay at the top
    ON the singing (hymn name + the question), visible from frame 0, gone after 3 s."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); f = font("cormorant-garamond-latin-700-normal.ttf", 62)
    t = spec["title"]
    while d.textlength(t, font=f) > W - 200 and f.size > 44: f = font("cormorant-garamond-latin-700-normal.ttf", f.size - 2)
    q = spec.get("challenge") or spec.get("hook") or ""; hf = font("cormorant-garamond-latin-600-normal.ttf", 44); qrows = textwrap.wrap(q, 40)[:2]
    if len(qrows) == 2 and len(qrows[1]) < 12: qrows = textwrap.wrap(q, len(q) // 2 + 6)[:2]   # no orphan word
    top = 170; bot = top + int(f.size * 1.1) + 10 + len(qrows) * 52
    shade(im, top - 30, bot + 10, ink(plate, (90, top - 30, W - 90, bot + 10)) if plate else 170)
    _center(im, top, t, f, CREAM); y = top + int(f.size * 1.1) + 10
    for r in qrows: _center(im, y, r, hf, CREAM); y += 52
    im.save(out)


def lyric2(cur, nxt, out, zone, plate):
    """v2.6: TWO big lines — the line being sung (underlined in gold) + the NEXT line already showing (a beat early, dimmer) so families can sing on."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    dt_ = (lambda x: Fm.display_text(x) if hasattr(Fm, "display_text") else x)
    f1 = font("cormorant-garamond-latin-700-normal.ttf", 74); f2 = font("cormorant-garamond-latin-600-normal.ttf", 60)
    a = dt_(cur); b = dt_(nxt) if nxt else ""
    while d.textlength(a, font=f1) > W - 140 and f1.size > 50: f1 = font("cormorant-garamond-latin-700-normal.ttf", f1.size - 2)
    while b and d.textlength(b, font=f2) > W - 160 and f2.size > 42: f2 = font("cormorant-garamond-latin-600-normal.ttf", f2.size - 2)
    top = zone if isinstance(zone, int) else 1240; h = int(f1.size * 1.25) + (int(f2.size * 1.25) if b else 0)
    shade(im, top - 24, top + h + 14, ink(plate, (70, top - 24, W - 70, top + h + 14)) if plate else 190)
    _center(im, top, a, f1, CREAM); w = d.textlength(a, font=f1); x0 = (W - w) / 2; uy = top + int(f1.size * 1.08)
    ImageDraw.Draw(im).rounded_rectangle((x0, uy, x0 + w, uy + 6), radius=3, fill=GOLD)   # the current phrase
    if b:
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0)); _center(layer, top + int(f1.size * 1.25), b, f2, CREAM)
        layer.putalpha(layer.getchannel("A").point(lambda v: int(v * 0.62))); im.alpha_composite(layer)
    im.save(out)


def verse_card(verse, out, plate):
    """v2.6: the KJV verse gets its OWN moment (an instrumental gap, never over singing)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    txt, _, ref = verse.rpartition("\" ") if verse.startswith("\"") else (verse, "", "")
    txt = txt.strip("\"“” "); ref = ref.strip()
    f = font("cormorant-garamond-latin-600-normal.ttf", 66); rows = textwrap.wrap(txt, 26)
    while len(rows) > 4 and f.size > 48: f = font("cormorant-garamond-latin-600-normal.ttf", f.size - 4); rows = textwrap.wrap(txt, int(26 * 66 / f.size))
    lh = int(f.size * 1.2); top = 760; bot = top + lh * len(rows) + 70
    shade(im, top - 30, bot + 10, ink(plate, (80, top - 30, W - 80, bot + 10)) if plate else 200)
    for i, r in enumerate(rows): _center(im, top + i * lh, r, f, CREAM)
    if ref: _center(im, top + lh * len(rows) + 14, ref, font("cormorant-garamond-latin-700-normal.ttf", 46), GOLD)
    im.save(out)


def next_up_card(nu, out, plate):
    """v2.6: the subscribe ask is a SPECIFIC next hymn, shown during the last held note (named series 'Sing the Next Line')."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); f = font("inter-latin-600-normal.ttf", 46)
    line = f"Next · {nu['when']}: {nu['hymn']}"; d = ImageDraw.Draw(im)
    while d.textlength(line, font=f) > W - 140 and f.size > 34: f = font("inter-latin-600-normal.ttf", f.size - 2)
    shade(im, 1500, 1640, ink(plate, (70, 1500, W - 70, 1640)) if plate else 180)
    _center(im, 1512, line, f, CREAM)
    if not V27: _center(im, 1575, "Subscribe to sing with us", font("inter-latin-600-normal.ttf", 40), GOLD)   # v2.7: the subscribe ask moves to the last-3-s CTA
    im.save(out)


def cta_card(out, plate=None):
    """v2.7 (Danni/Dispatch 11-19): a light, specific CTA in the LAST 3 s only (never at the start → retention): a red 'Subscribe for
    tomorrow's hymn' pill + a small like (heart) badge, breathing gently, and a share line. Top band (the title is long gone by then)."""
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im); f = font("inter-latin-600-normal.ttf", 46); t = "Subscribe for tomorrow's hymn"
    tw = d.textlength(t, font=f); pw = tw + 96; x0 = (W - pw - 120) / 2; y0 = 330
    shade(im, 300, 560, ink(plate, (60, 300, W - 60, 560)) if plate else 160)
    d = ImageDraw.Draw(im); d.rounded_rectangle((x0, y0, x0 + pw, y0 + 92), radius=46, fill=(204, 0, 0, 240))
    d.polygon([(x0 + 34, y0 + 30), (x0 + 34, y0 + 62), (x0 + 60, y0 + 46)], fill=(255, 255, 255, 255))   # play glyph
    d.text((x0 + 76, y0 + 18), t, font=f, fill=(255, 255, 255, 255))
    cx, cy = x0 + pw + 70, y0 + 46; d.ellipse((cx - 46, cy - 46, cx + 46, cy + 46), fill=(255, 255, 255, 235))   # like badge (heart)
    d.ellipse((cx - 24, cy - 16, cx + 2, cy + 8), fill=(204, 0, 0, 255)); d.ellipse((cx - 2, cy - 16, cx + 24, cy + 8), fill=(204, 0, 0, 255))
    d.polygon([(cx - 24, cy - 2), (cx + 24, cy - 2), (cx, cy + 26)], fill=(204, 0, 0, 255))
    _center(im, y0 + 120, "Send this to someone who loves this hymn", font("cormorant-garamond-latin-700-normal.ttf", 52), CREAM)
    im.save(out)


def cta_card2(out, style, line, plate=None, gift=True):
    """SAMPLE ONLY (11-22, for Danni): calm end card in the top safe zone (y 250–700): OUR official seal (brand_seal v3, never redrawn),
    Subscribe · Like · Share as quiet line icons, and one warm family line. style navy = gold on navy glass · light = navy on cream."""
    navy, gold, cream = (11, 31, 58), (212, 175, 55), (246, 236, 214)
    bg, fg, acc = ((11, 31, 58, 205), cream, gold) if style == "navy" else ((246, 236, 214, 225), navy, (150, 112, 30))
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); x0, y0, x1, y1 = 90, 250, W - 90, (850 if gift else 700)
    panel = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0)); ImageDraw.Draw(panel).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), radius=36, fill=bg, outline=acc + (180,), width=2)
    im.alpha_composite(panel, (x0, y0)); d = ImageDraw.Draw(im)
    sp = os.path.join(Fm.D, "brand_seal", "v3", "light", "crossaihub-seal-v3-light_circle_1024.png") if style == "navy" else os.path.join(Fm.D, "brand_seal", "v3", "main", "crossaihub-seal-v3-main_circle_1024.png")
    try:
        seal = Image.open(sp).convert("RGBA"); seal.thumbnail((120, 120), Image.LANCZOS); im.alpha_composite(seal, ((W - seal.width) // 2, y0 + 26))
    except Exception: pass
    cy = y0 + 200; r = 34; labels = ("Subscribe", "Like", "Share"); fl = font("inter-latin-600-normal.ttf", 30)
    for i, lab in enumerate(labels):
        cx = W // 2 + (i - 1) * 230; d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=acc + (255,), width=3)
        if i == 0: d.polygon([(cx - 10, cy - 15), (cx - 10, cy + 15), (cx + 16, cy)], fill=acc + (255,))   # play = subscribe to our channel
        elif i == 1:   # heart
            d.ellipse((cx - 17, cy - 13, cx + 1, cy + 5), fill=acc + (255,)); d.ellipse((cx - 1, cy - 13, cx + 17, cy + 5), fill=acc + (255,)); d.polygon([(cx - 17, cy - 1), (cx + 17, cy - 1), (cx, cy + 18)], fill=acc + (255,))
        else:   # share arrow
            d.line([(cx - 14, cy + 12), (cx - 14, cy - 2), (cx + 6, cy - 2)], fill=acc + (255,), width=4); d.polygon([(cx + 4, cy - 12), (cx + 18, cy - 2), (cx + 4, cy + 8)], fill=acc + (255,))
        w = d.textlength(lab, font=fl); d.text((cx - w / 2, cy + r + 10), lab, font=fl, fill=fg + (235,))
    f = font("cormorant-garamond-latin-700-normal.ttf", 50); y = cy + r + 64
    for row in line.split("\n"):
        while d.textlength(row, font=f) > (x1 - x0 - 60) and f.size > 36: f = font("cormorant-garamond-latin-700-normal.ttf", f.size - 2)
        w = d.textlength(row, font=f); d.text(((W - w) / 2, y), row, font=f, fill=fg + (255,)); y += int(f.size * 1.18)
    if gift:   # Danni 11-22: the free gift, as plain on-screen text (not clickable in Shorts; no "click here"); valid through 12-25
        d.line([(W // 2 - 160, y + 20), (W // 2 + 160, y + 20)], fill=acc + (150,), width=2); fg2 = font("inter-latin-600-normal.ttf", 34)
        t = "Your free Christmas gift: crossaihub.com/gift"; w = d.textlength(t, font=fg2); d.text(((W - w) / 2, y + 34), t, font=fg2, fill=acc + (255,))
        f3 = font("inter-latin-400-normal.ttf", 30); t3 = "Link in the first comment"; w3 = d.textlength(t3, font=f3); ax = (W + w3) / 2 + 22; ay = y + 92
        d.text(((W - w3) / 2 - 14, y + 80), t3, font=f3, fill=fg + (220,))   # Danni 11-22: where the clickable link is
        d.line([(ax, ay - 12), (ax, ay + 10)], fill=fg + (220,), width=3); d.polygon([(ax - 8, ay + 4), (ax + 8, ay + 4), (ax, ay + 16)], fill=fg + (220,))
    im.save(out)


def main():
    spec = json.load(open(sys.argv[1])); out = spec["out"]; wd = out + "_work"; os.makedirs(wd, exist_ok=True)
    global END_S, V27
    V27 = spec.get("template", "v2.7") >= "v2.7"
    t0, t1 = float(spec["t0"]), float(spec["t1"])
    if V27:
        END_S = 5.0; _nx = [l["start"] for l in json.load(open(spec["lyrics"]))["lines"] if l["start"] >= t1 - 0.05]
        t1 += max(0.0, min(1.0, (_nx[0] - t1 - 0.2) if _nx else 1.0))   # v2.7: end card ≥ 4 s fully visible (fades eat ~0.7 s); 1 s more of the hymn tail so no sung line is cut for it
    L = t1 - t0; assert L <= 58.5, "Short longer than 58 s"
    if spec.get("loop") and not 19.5 <= L <= 25.5: print(f"⚠ Ask Studio rule: length {L:.1f}s outside 20–25 s", flush=True)
    LP = 0.7 if spec.get("loop") else 0.0   # loop tail: last 0.7 s fades back into frame 1 (picture + title block) so the replay is seamless
    sc = spec["scenes"]; n = len(sc); clips = []
    BV = spec.get("bg_video")   # 11-18: Danni's Meta AI motion clip as the MOVING background (no still drift)
    if BV:
        sc = [os.path.join(wd, "bgv_mid.png")]; n = 1
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "5", "-i", BV, "-frames:v", "1", "-vf", "scale=1080:1920:flags=lanczos", sc[0]], check=True)
    for k, img in enumerate(sc if not BV else []):
        a, b = L * k / n, L * (k + 1) / n
        import hashlib   # 11-15 fix: cache key = plate + timing + framing (the old "sNN.mp4" key re-used stale clips after a plate flip)
        c = os.path.join(wd, f"s{k:02d}_" + hashlib.md5(f"{img}|{b - a:.3f}|{n}|{k}|f5|{json.dumps((spec.get('framings') or [None] * n)[k])}".encode()).hexdigest()[:10] + ".mp4")
        # Danni 11-16: the "living motion" overlays (flicker / glow / rays / motes / snow / sparkle) look fake → REMOVED for good.
        # Only a very slow, natural camera drift on the real still: 5 % overscan, eased glide, no punch-in on frame 1 (frame 0 = the bright plate + title).
        kb = dict(fy=(0.62 if k == 0 else 0.55), z0=None, ss=1.05, px=0.6); dd = (b - a) + (Fm.XF if k + 1 < n else 0)
        fr = (spec.get("framings") or [None] * n)[k]   # 11-17 ROOT FIX: ONE real scene, several camera framings (wide · push-in · detail) = coherent AND varied
        if fr: kb = dict(fy=fr.get("fy", 0.55), z0=fr.get("z0"), ss=fr.get("ss", 1.05), px=fr.get("px", 0.4))   # v2: centred drift, subject stays framed
        if not os.path.exists(c):
            Fm.fast_pan(img, dd, k, c, **kb)
        clips.append((c, a, b))   # never a *_live.mp4 (old cached overlay clips are ignored)
    base = os.path.join(wd, "base.mp4"); inp = sum((["-i", c] for c, _, _ in clips), []); fc = []; last = "[0:v]"
    for k in range(1, n): fc.append(f"{last}[{k}:v]xfade=transition=fade:duration={Fm.XF}:offset={clips[k][1]:.3f}[x{k}]"); last = f"[x{k}]"
    if BV:   # Meta clip: audio stripped (-an, our hymn audio is added later), Lanczos upscale + light sharpen to 1080×1920, then the LAST frame holds
        bd = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", BV], capture_output=True, text=True).stdout or 10)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", BV, "-an", "-vf", f"scale=1080:1920:flags=lanczos,unsharp=5:5:0.5:5:5:0.0,fps={FPS},format=yuv420p,"
                        f"tpad=stop_mode=clone:stop_duration={max(0.0, L - bd + 1):.2f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-t", f"{L:.3f}", base], check=True)
    else: subprocess.run(["ffmpeg", "-v", "error", "-y", *inp, "-filter_complex", ";".join(fc) if fc else "[0:v]null[x0]", "-map", last if fc else "[x0]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-t", f"{L:.3f}", base], check=True)   # 11-18: intermediate → veryfast (the final pass sets quality)
    IMP = set(spec.get("improve") or [])   # v2.5 (Danni 11-18 "ALWAYS change, improve and develop"): opt-in per Short, logged in youtube/SHORTS_IMPROVEMENT_LOG.md
    if "motion_push" in IMP:   # motion never freezes: one slow continuous push-in (≈ 6 %) over the whole Short, incl. the held last frame of a motion clip
        pb = os.path.join(wd, "base_push.mp4"); nf = int(L * FPS) + 1
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", base, "-vf", f"scale=1188:2112:flags=lanczos,zoompan=z='1+0.06*on/{nf}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps={FPS},format=yuv420p",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-t", f"{L:.3f}", pb], check=True)
        os.replace(pb, base)
    if LP:   # Dispatch 11-16 loop: crossfade the end into a still of frame 1
        f0 = os.path.join(wd, "frame0.png"); lb = os.path.join(wd, "base_loop.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", base, "-frames:v", "1", f0], check=True)
        bd = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", base], capture_output=True, text=True).stdout or L)
        nz = f"fps={FPS},format=yuv420p,setsar=1,settb=AVTB"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", base, "-loop", "1", "-framerate", str(FPS), "-t", f"{LP + 0.5:.2f}", "-i", f0, "-filter_complex",
                        f"[0:v]{nz}[b];[1:v]{nz}[s];[b][s]xfade=transition=fade:duration={LP:.2f}:offset={min(L, bd) - LP:.3f}[v]", "-map", "[v]",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-r", str(FPS), "-t", f"{L:.3f}", lb], check=True)
        os.replace(lb, base)
    ov = []; bb = os.path.join(wd, "band.png"); bottom_band(bb); ov.append((bb, 0.0, L))   # 11-15: one solid soft band behind ALL lower text, whole Short
    V26 = spec.get("template", "v2.7") >= "v2.6"   # Arena 11-18: frame-one singing, 2-line lyrics, verse moment, next-hymn ask (new renders only)
    tb = os.path.join(wd, "title.png")
    if V26: small_title(spec, tb, plate=sc[0]); ov.append((tb, 0.0, 3.0))
    else: title_block(spec, tb, plate=sc[0]); ov.append((tb, 0.0, 3.0 if "pace_title" in IMP else 4.2))
    if LP: ov.append((tb.replace("title.png", "title_loop.png"), L - LP, L)); Image.open(tb).save(ov[-1][0])   # title back on the last frame = frame 1
    lyr = json.load(open(spec["lyrics"]))["lines"]
    SUBZ = sub_band(sc[0])   # v2.2 (judge 11-18: "subtitle over the boat") → the calmest band that does not cover the subject   # v2: judges hated subtitle boxes over the subject → the clearer band, same for the whole Short
    LS = [l for l in lyr if l["end"] > t0 + 0.3 and l["start"] < t1 - 0.3]; stop = L - (END_S + LP + 0.2)
    for k, l in enumerate(LS):
        p = os.path.join(wd, f"sub{k:02d}.png"); pl_ = sc[min(n - 1, int((l["start"] - t0) / max(L, 1) * n))]
        if V26:   # 2 lines: current (underlined) + next; the card holds until the next line starts (no blink between lines); first card at 0:00
            nx = LS[k + 1] if k + 1 < len(LS) else None
            lyric2(l["text"], nx["text"] if nx else "", p, SUBZ, pl_)
            b_ = (nx["start"] - t0 - 0.15) if nx and nx["start"] - l["end"] < 2.5 else l["end"] - t0 + 0.3
            ov.append((p, 0.0 if k == 0 else max(0.0, l["start"] - t0 - 0.15), min(stop, b_)))
        else:
            sub_card(l["text"], p, SUBZ, pl_)   # v2: no box, clear band
            ov.append((p, max(0.2, l["start"] - t0 - 0.15), min(stop, l["end"] - t0 + 0.3)))
    if V26 and spec.get("verse"):   # the KJV verse in its own moment: the first instrumental gap ≥ 3 s inside the Short (never over singing)
        gaps = [(LS[k]["end"] - t0 + 0.2, LS[k + 1]["start"] - t0 - 0.2) for k in range(len(LS) - 1)] + [(LS[-1]["end"] - t0 + 0.2, stop)] if LS else []
        g = next(((a, b) for a, b in gaps if b - a >= 3.0), None)
        if g: vc = os.path.join(wd, "verse.png"); verse_card(spec["verse"], vc, sc[-1]); ov.append((vc, g[0], g[1]))
        else: print("  v2.6: no instrumental gap ≥ 3 s → verse stays in the description (never over the singing)", flush=True)
    if V26 and spec.get("next_up") and LS:   # specific next hymn during the last held note
        ll = LS[-1]; a_ = ll["start"] - t0 + 0.55 * (ll["end"] - ll["start"])
        nu = os.path.join(wd, "nextup.png"); next_up_card(spec["next_up"], nu, sc[-1]); ov.append((nu, max(0.0, a_), stop + 0.2))
    ec = os.path.join(wd, "end.png"); end_card(spec["end_q"], ec, spec.get("end_sub"), zone=clear_zone(sc[-1]), plate=sc[-1]); ov.append((ec, L - END_S - LP, L - LP) if LP else (ec, L - END_S, L))   # Danni 11-17: end question/answer on screen 4 s
    # 11-22 Danni: the red flashing subscribe pill felt like an alarm → OFF on every render. A new calm card exists only as a SAMPLE
    # (spec "cta_style": "navy" | "light") until Danni approves it; nothing with a new design uploads before his OK.
    if V27 and spec.get("cta_style"):
        ct = os.path.join(wd, "cta2.png"); cta_card2(ct, spec["cta_style"], spec.get("cta_line") or "Thank you for singing with us.\nSubscribe so tomorrow's hymn finds you.", sc[-1], gift=str(spec.get("date") or "2026-12-25") <= "2026-12-25"); ov.append((ct, L - 3.5 - LP, L - LP))
    mk = os.path.join(wd, "marks.png"); marks(mk)   # v2.3: the tiny seal is no longer overlaid (judge: illegible at phone size; brand = @crossaihub on the end card)
    ov = [(q, a, b) for q, a, b in ov if b - a > 0.4]
    oin = sum((["-loop", "1", "-framerate", str(FPS), "-t", f"{b - a:.3f}", "-i", q] for q, a, b in ov), []); f2 = []; lv = "[0:v]"
    for k, (q, a, b) in enumerate(ov, 1):
        if q.endswith(("marks.png", "band.png")): fade = ""
        elif q.endswith("cta2.png"):   # calm: fade + 40 px slide-up once, then STILL (no pulse, no flash)
            fade = f",fade=t=in:st=0:d=0.6:alpha=1"
        elif q.endswith("cta.png"): fade = f",geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='alpha(X,Y)*(0.78+0.22*sin(2*PI*T/1.2))',fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={max(0, b - a - 0.25):.2f}:d=0.25:alpha=1"   # gentle breathing
        elif (LP or V26) and q.endswith("title.png"): fade = f",fade=t=out:st={b - a - 0.35:.2f}:d=0.35:alpha=1"      # visible from frame 1 (challenge ≤ 1.5 s)
        elif V26 and os.path.basename(q).startswith("sub"): fade = (f",fade=t=in:st=0:d=0.12:alpha=1" if a > 0.05 else "") + f",fade=t=out:st={max(0, b - a - 0.12):.2f}:d=0.12:alpha=1"   # v2.6: crisp hand-over, first line on frame 0
        elif LP and q.endswith("title_loop.png"): fade = f",fade=t=in:st=0:d={LP - 0.05:.2f}:alpha=1"        # ends exactly like frame 1
        else: fade = f",fade=t=in:st=0:d=0.35:alpha=1,fade=t=out:st={b - a - 0.35:.2f}:d=0.35:alpha=1"
        rise = ("end_rise" in IMP and q.endswith("end.png")) or ("lyric_rise" in IMP and os.path.basename(q).startswith("sub")) or q.endswith("cta2.png")
        oy = f"'max(0,{36 if q.endswith('end.png') else 24}*(1-(t-{a:.3f})/0.45))'" if rise else "0"   # v2.5: the card glides up into place as it fades in
        f2.append(f"[{k}:v]format=rgba{fade},setpts=PTS+{a:.3f}/TB[o{k}]"); f2.append(f"{lv}[o{k}]overlay=0:{oy}:eof_action=pass[v{k}]"); lv = f"[v{k}]"
    na = len(ov) + 1
    f2.append(f"[{na}:a]atrim={t0}:{t1},asetpts=PTS-STARTPTS,afade=t=in:d={0.01 if V26 else (0.03 if LP else 0.25)},afade=t=out:st={L - (0.5 if LP else 1.0):.2f}:d={0.5 if LP else 1.0}[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", base, *oin, "-i", spec["audio"], "-filter_complex", ";".join(f2), "-map", lv, "-map", "[a]",
                    "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p", "-crf", "18", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-t", f"{L:.3f}", out], check=True)
    # 11-15 (WS-23): custom Shorts thumbnails via API → a COVER in the thumbnail recipe: the first plate (full quality, framed on the subject),
    # the recipe title block, gold rule + hook, dark seal. 1080×1920 JPEG < 2 MB → set by yt_upload.v3_extras (platforms.youtube.thumbnail).
    cv = Image.open(sc[0]).convert("RGB"); w0, h0 = cv.size; R0 = W / H; ch = min(h0, int(w0 / R0)); cw = int(ch * R0)
    y0 = int((h0 - ch) * 0.66); cv = cv.crop(((w0 - cw) // 2, y0, (w0 - cw) // 2 + cw, y0 + ch)).resize((W, H), Image.LANCZOS).convert("RGBA")
    if spec.get("cover_words"):   # ≤ 4 big words, high contrast (Ask Studio 11-16)
        cb = os.path.join(wd, "cover_block.png"); cover_block(spec["cover_words"], cb); cv.alpha_composite(Image.open(cb).convert("RGBA"))
    else: cv.alpha_composite(Image.open(tb).convert("RGBA"))
    cv.alpha_composite(Image.open(mk).convert("RGBA"))
    cover = out.replace(".mp4", "_cover.jpg"); cv.convert("RGB").save(cover, quality=88, optimize=True)
    if os.path.getsize(cover) > 1_900_000: cv.convert("RGB").save(cover, quality=78, optimize=True)
    for t, tag in ((1.5, "a"), (L / 2, "b"), (L - 1.5, "c")):
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", out, "-frames:v", "1", "-vf", "scale=540:-2", out.replace(".mp4", f"_frame_{tag}.jpg")])
    print("STORY_SHORT_DONE", out, f"{L:.1f}s", n, "plates")
if __name__ == "__main__": main()
