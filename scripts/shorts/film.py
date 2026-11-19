#!/usr/bin/env python3
"""WS-04 · Hymn Film assembler (youtube/HYMN_FILM_FORMAT_v1.md; Dispatch P0 11-13).
Structure: [hook: one sung line] → INTRO (Orion voice + KJV verse on screen, soft bed) → HYMN (full track, 12+ scenes, Ken Burns, sing-along line)
           → MEDITATION (Orion voice, "Meditation" label, My Room line + share line on screen) · chapters embedded + chapters.txt for the description.
usage:  python3 film.py SPEC.json [--draft]     (--draft = 960×540 / fast preset for a quick check)
SPEC keys (see film1_he_giveth_strength.json): out, audio, lyrics, hook{t0,t1,scene}, bed{t0,t1,gain_db}, intro{text|voice, verse, ref, scenes[]},
           hymn{scenes[{img,t0}]} (a scene lasts until the next t0), meditation{text|voice, scenes[], myroom, share}, title.
Art = the free trio (unique_art.py + Fable QA); no text inside images: every word on screen is an overlay drawn here.
Output: OUT.mp4 (1920×1080 30 fps H.264 high, yuv420p, AAC 192k, +faststart, chapters) + OUT.chapters.txt + OUT.timeline.json"""
import json, os, subprocess, sys, textwrap
from PIL import Image, ImageDraw, ImageFilter, ImageFont
D = os.path.expanduser("~/CrossAIHub-data"); FD = os.path.join(D, "shorts_engine", "fonts")
SERIF = os.path.join(FD, "cormorant-garamond-latin-600-normal.ttf"); ITAL = os.path.join(FD, "cormorant-garamond-latin-500-italic.ttf")
SANS = os.path.join(FD, "inter-latin-400-normal.ttf")
IVORY, GOLD = (246, 239, 226, 255), (232, 196, 120, 255)
DRAFT = "--draft" in sys.argv; W, H = (960, 540) if DRAFT else (1920, 1080); FPS = 30; XF = 1.6   # crossfade seconds (gentle, Danni 11-13)
EXCERPT = next((tuple(float(x) for x in a.split("=")[1].split(":")) for a in sys.argv if a.startswith("--excerpt=")), None)   # --excerpt=START:END (s)
def sh(*a): subprocess.run(a, check=True)
def dur(p): return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p], capture_output=True, text=True, check=True).stdout.strip())

def lufs(path, t0=None, t1=None):
    """integrated loudness (LUFS) of a file or a span — used to sit the music a fixed distance UNDER the voice (Danni 11-13)."""
    import re as _re
    a = ["ffmpeg", "-hide_banner", "-nostats"] + (["-ss", str(t0), "-to", str(t1)] if t0 is not None else []) + ["-i", path, "-af", "ebur128", "-f", "null", "-"]
    m = _re.findall(r"I:\s+(-?[\d.]+) LUFS", subprocess.run(a, capture_output=True, text=True).stderr)
    return float(m[-1]) if m else -23.0

def voice(seg, wd, name):
    """seg['voice'] = existing mp3, or seg['text'] → Orion TTS (live/bin/tts.py chain: 0.4 s lead, loudnorm −16, 0.8 s tail)."""
    if seg.get("voice"): return seg["voice"]
    dst = os.path.join(wd, name + ".mp3")
    if not os.path.exists(dst):
        sys.path.insert(0, os.path.join(D, "live", "bin")); sys.path.insert(0, os.path.join(D, "tools"))
        import tts as T, r2_cf, urllib.request
        tok = r2_cf.token(); acc = json.load(urllib.request.urlopen(urllib.request.Request("https://api.cloudflare.com/client/v4/accounts",
                                                                                          headers={"Authorization": "Bearer " + tok}), timeout=60))["result"][0]["id"]
        T.tts(seg["text"], dst, tok, acc)
    return dst

def panel(lines, out, size=58, font=SERIF, sub=None, pos="lower", width=36):
    """Transparent full-frame PNG: glass panel + ivory text (+ gold reference line)."""
    s = W / 1920; im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    f = ImageFont.truetype(font, int(size * s)); fs = ImageFont.truetype(SANS, int(30 * s))
    wrapped = [w for l in lines for w in textwrap.wrap(l, width)]; lh = int(size * s * 1.25)
    bw = int(max(d.textlength(w, font=f) for w in wrapped) + 120 * s); bh = lh * len(wrapped) + int((90 if sub else 60) * s)
    x0 = (W - bw) // 2; y0 = {"lower": H - bh - int(90 * s), "center": (H - bh) // 2, "upper": int(80 * s)}[pos]
    g = Image.new("RGBA", (W, H), (0, 0, 0, 0)); ImageDraw.Draw(g).rounded_rectangle((x0, y0, x0 + bw, y0 + bh), int(28 * s), fill=(12, 14, 22, 150))
    im = Image.alpha_composite(im, g.filter(ImageFilter.GaussianBlur(1))); d = ImageDraw.Draw(im); y = y0 + int(30 * s)
    for w in wrapped:
        d.text(((W - d.textlength(w, font=f)) // 2, y), w, font=f, fill=IVORY); y += lh
    if sub: d.text(((W - d.textlength(sub, font=fs)) // 2, y + int(6 * s)), sub, font=fs, fill=GOLD)
    im.save(out)

def display_text(t):
    """Dispatch 11-13: Suno/TTS scripts spell the brand phonetically ("Cross, A, I, Hub"); subtitles always show CrossAIHub."""
    import re as _re
    return _re.sub(r"Cross,?\s*A,?\s*I,?\s*Hub", "CrossAIHub", t, flags=_re.I)

def subtitle(text, out, size=50, frame=None, bottom=70, wrap=52):
    """Danni 11-13: subtitle style only — bottom of the frame, never over the middle of the image. Ivory text with a soft dark halo and a faint
    translucent band only as wide as the text; max 2 lines (longer sentences are split into timed chunks by subs_for()).
    frame=(w,h) for other canvases (9:16 Shorts exports: bottom≈420 keeps clear of the Shorts caption/UI zone)."""
    W, H = frame or (globals()["W"], globals()["H"]); text = display_text(text)
    s = min(W, H) / 1080; im = Image.new("RGBA", (W, H), (0, 0, 0, 0)); f = ImageFont.truetype(SERIF, int(size * s))
    lines = textwrap.wrap(text, wrap)[:2]; d = ImageDraw.Draw(im); lh = int(size * s * 1.22)
    tw = max(d.textlength(l, font=f) for l in lines); y0 = H - int(bottom * s) - lh * len(lines)
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(band).rounded_rectangle(((W - tw) / 2 - 28 * s, y0 - 14 * s, (W + tw) / 2 + 28 * s, y0 + lh * len(lines) + 10 * s), int(16 * s), fill=(8, 10, 16, 150))   # 11-15: high-contrast band for TV
    im = Image.alpha_composite(im, band.filter(ImageFilter.GaussianBlur(6 * s)))
    halo = Image.new("RGBA", (W, H), (0, 0, 0, 0)); hd = ImageDraw.Draw(halo)
    for i, l in enumerate(lines): hd.text(((W - hd.textlength(l, font=f)) / 2, y0 + i * lh), l, font=f, fill=(0, 0, 0, 210))
    im = Image.alpha_composite(im, halo.filter(ImageFilter.GaussianBlur(3 * s))); d = ImageDraw.Draw(im)
    for i, l in enumerate(lines): d.text(((W - d.textlength(l, font=f)) / 2, y0 + i * lh), l, font=f, fill=IVORY)
    im.save(out)

def subs_for(timing, t0):
    """sentence timings → subtitle chunks (≤ ~2 lines each), each chunk on screen only while it is being spoken."""
    out = []
    for s in timing:
        words = s["text"].split(); chunks = []; cur = []
        for w in words:
            cur.append(w)
            if len(" ".join(cur)) > 88 and (w.endswith((",", ";", ":")) or len(" ".join(cur)) > 100): chunks.append(" ".join(cur)); cur = []
        if cur: chunks.append(" ".join(cur))
        tot = sum(len(c) for c in chunks); a = s["start"]
        for c in chunks:
            b = a + (s["end"] - s["start"]) * len(c) / tot; out.append((c, t0 + a, t0 + b + 0.15)); a = b
    return out

def fast_pan(img, d, k, out, fy=0.5, z0=None, ss=1.12, px=1.0):
    """11-15: FAST gentle motion (zoompan on a supersampled plate took 15–20 min per scene on the Air under load). The plate is scaled once to
    ss× the frame, then a crop window glides slowly (alternating left→right / right→left / down→up) — ffmpeg crop x/y per frame, near real time.
    z0 (> 1) = frame 1 starts tighter on the subject: a larger ss for that scene, glide outward from the subject point (fy)."""
    s = max(ss, z0 or 0); n = max(2, int(round(d * FPS))); src = out + ".src.png"
    im = Image.open(img).convert("RGB"); w, h = im.size; R = W / H; ch = min(h, int(w / R)); cw = int(ch * R)
    im.crop(((w - cw) // 2, (h - ch) // 2, (w - cw) // 2 + cw, (h - ch) // 2 + ch)).resize((int(W * s) // 2 * 2, int(H * s) // 2 * 2), Image.LANCZOS).save(src)
    p = f"(t/{d:.3f})"; e = f"(0.5-0.5*cos(PI*{p}))"   # eased 0→1
    # 11-18 template v2: px = share of the overscan the drift may travel, CENTRED (px 1.0 = old edge-to-edge glide; 0.4 keeps the subject framed)
    c0 = f"(iw-ow)*{(1 - px) / 2:.3f}"; sp = f"(iw-ow)*{px:.3f}"
    x = {0: f"({c0}+{sp}*{e})", 1: f"({c0}+{sp}*(1-{e}))", 2: "(iw-ow)/2", 3: f"({c0}+{sp}*{e})"}[k % 4]
    y = f"(ih-oh)*{fy}" if k % 4 != 2 else f"(ih-oh)*({fy}+0.06*(1-{e}))"
    # decode the plate ONCE (loop filter), veryfast x264 for this intermediate (the final pass re-encodes) → seconds, not minutes, under load
    sh("ffmpeg", "-v", "error", "-y", "-i", src, "-vf", f"loop=loop={n - 1}:size=1:start=0,setpts=N/{FPS}/TB,crop={W}:{H}:x='{x}':y='min(ih-oh,max(0,{y}))',format=yuv420p",
       "-frames:v", str(n), "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", out + ".part.mp4")
    os.replace(out + ".part.mp4", out); os.remove(src)

def kenburns(img, d, k, out, fy=0.5, z0=None, ss=2.0):
    """One scene clip: 16:9 crop of the art → slow zoom in / zoom out / pan L→R / pan R→L (alternating), d seconds."""
    n = max(2, int(round(d * FPS))); src = out + ".src.png"
    im = Image.open(img).convert("RGB"); w, h = im.size; R = W / H   # crop to the OUTPUT aspect (16:9 films, 9:16 story Shorts)
    ch = min(h, int(w / R)); cw = int(ch * R)
    im.crop(((w - cw) // 2, (h - ch) // 2, (w - cw) // 2 + cw, (h - ch) // 2 + ch)).resize((int(W * ss), int(H * ss)), Image.LANCZOS).save(src)   # ss = supersampling for smooth zoompan (story Shorts use 1.4: ~2× faster)
    z = {0: f"1+0.06*on/{n}", 1: f"1.06-0.06*on/{n}", 2: "1.06", 3: "1.06"}[k % 4]   # gentler motion (Danni 11-13)
    if z0: z = f"{z0}-({z0}-1.04)*on/{n}"   # story Shorts frame 1 (11-15): start CLOSE on the subject, ease out
    x = {0: "iw/2-(iw/zoom/2)", 1: "iw/2-(iw/zoom/2)", 2: f"(iw-iw/zoom)*on/{n}", 3: f"(iw-iw/zoom)*(1-on/{n})"}[k % 4]
    sh("ffmpeg", "-v", "error", "-y", "-loop", "1", "-i", src, "-vf", f"zoompan=z='{z}':x='{x}':y='(ih-ih/zoom)*{fy}':d={n}:s={W}x{H}:fps={FPS},format=yuv420p",
       "-frames:v", str(n), "-c:v", "libx264", "-preset", "veryfast" if DRAFT else "medium", "-crf", "20", out + ".part.mp4")
    os.replace(out + ".part.mp4", out); os.remove(src)   # atomic: a killed run never leaves a half clip that a re-run would reuse

def main():
    spec = json.load(open([a for a in sys.argv[1:] if not a.startswith("--")][0])); out = spec["out"] + ("_draft" if DRAFT else "") + (f"_excerpt{int(EXCERPT[0])}-{int(EXCERPT[1])}" if EXCERPT else "")
    wd = out + "_work"; os.makedirs(wd, exist_ok=True)
    lyr = json.load(open(spec["lyrics"]))["lines"]; hymn_len = dur(spec["audio"])
    iv, mv = voice(spec["intro"], wd, "intro"), voice(spec["meditation"], wd, "meditation")
    hk = spec.get("hook"); hook_len = (hk["t1"] - hk["t0"] + 0.6) if hk else 0
    # SUNO mode (Danni 11-13, the template): intro/ending are finished Suno speech tracks WITH their own music bed → no extra bed, no lead-in;
    # the hymn crossfades in under the intro's last XIN s and the ending crossfades in under the hymn's last XOUT s.
    SI, SM = spec["intro"].get("mode") == "suno", spec["meditation"].get("mode") == "suno"
    XIN, XOUT = spec.get("xfade_in", 3.0) if SI else 0.0, spec.get("xfade_out", 2.0) if SM else 0.0
    OFF_I, OFF_M = (0.0 if SI else 1.0), (0.0 if SM else 2.0)
    md = lambda k, v: max([dur(v)] + ([dur(spec[k]["music"])] if spec[k].get("music") else []))   # separate Suno music may run longer than the voice
    intro_len = md("intro", iv) if SI else max(spec["intro"].get("min_s", 45), dur(iv) + 2.0)
    med_len = md("meditation", mv) if SM else max(spec["meditation"].get("min_s", 60), dur(mv) + 6.0)
    # Scripture gate (WS-22, Dispatch 11-13): a final render needs every verse word-check OK
    if not DRAFT and not EXCERPT:
        bad = [p for p in spec.get("verse_checks", []) if not (os.path.exists(p) and json.load(open(p)).get("ok"))]
        if bad: sys.exit(f"VERSE GATE: Scripture word-check missing or MISMATCH → {bad} (regenerate the Suno take or use a verified voice for the verse)")
        if not spec.get("verse_checks"): print("⚠ no verse_checks in the spec (only allowed when no Scripture is spoken)", flush=True)
    T_INTRO = hook_len; T_HYMN = T_INTRO + intro_len - XIN; T_MED = T_HYMN + hymn_len - XOUT; TOTAL = T_MED + med_len
    # ---- scene timeline (absolute seconds) ----
    sc = []
    if hk: sc.append((hk["scene"], 0.0, T_INTRO))
    ii = spec["intro"]["scenes"]; il = T_HYMN - T_INTRO
    for k, img in enumerate(ii): sc.append((img, T_INTRO + il * k / len(ii), T_INTRO + il * (k + 1) / len(ii)))
    hs = spec["hymn"]["scenes"]
    for k, s in enumerate(hs): sc.append((s["img"], T_HYMN + s["t0"], T_HYMN + (hs[k + 1]["t0"] if k + 1 < len(hs) else hymn_len - XOUT)))
    ms = spec["meditation"]["scenes"]
    for k, img in enumerate(ms): sc.append((img, T_MED + med_len * k / len(ms), T_MED + med_len * (k + 1) / len(ms)))
    sc[0] = (sc[0][0], 0.0, sc[0][2])
    # ---- excerpt window (review cut): only the scenes that overlap [S, E]; everything is shifted by A0 ----
    sel = [k for k, (_, a, b) in enumerate(sc) if not EXCERPT or (b > EXCERPT[0] and a < EXCERPT[1])]
    A0, OUTLEN = sc[sel[0]][1], sc[sel[-1]][2] - sc[sel[0]][1]
    # ---- video: clips (+XF tail so crossfades keep the timeline exact) → xfade chain ----
    clips = []
    for j, k in enumerate(sel):
        img, a, b = sc[k]
        c = os.path.join(wd, f"scene_{k:02d}_{int(round((b - a) * 100))}_d5.mp4"); dd = (b - a) + (XF if j + 1 < len(sel) else 0)
        # Danni 11-16: NO "living motion" overlays (they look fake). A real still with a very slow natural camera drift (5 % overscan) only.
        kb = dict(fy=0.55, z0=None, ss=1.05)
        if not os.path.exists(c): fast_pan(img, dd, k, c, **kb)
        clips.append((c, a - A0, b - A0)); print(f"scene {k:02d} {a:7.2f}–{b:7.2f}  {os.path.basename(img)}", flush=True)
    inp = sum((["-i", c] for c, _, _ in clips), []); fc = []; last = "[0:v]"
    for k in range(1, len(clips)):
        fc.append(f"{last}[{k}:v]xfade=transition=fade:duration={XF}:offset={clips[k][1]:.3f}[x{k}]"); last = f"[x{k}]"
    base = os.path.join(wd, "base.mp4")
    if not (os.path.exists(base) and abs(dur(base) - OUTLEN) < 0.5 and os.path.getmtime(base) > max(os.path.getmtime(c) for c, _, _ in clips)) and \
       not print("building base (xfade chain)", flush=True): sh("ffmpeg", "-v", "error", "-y", *inp, "-filter_complex", ";".join(fc) if fc else "[0:v]null[x0]", "-map", last if fc else "[x0]",
       "-c:v", "libx264", "-preset", "veryfast" if DRAFT else "medium", "-crf", "19", "-t", f"{OUTLEN:.3f}", base + ".part.mp4") or os.replace(base + ".part.mp4", base)
    # ---- overlays (all text is drawn here) ----
    # Danni 11-13: ALL text = bottom subtitles, only while words are spoken or sung; nothing in the middle, nothing in silence/instrumentals.
    ov = []; subs = []   # (png, t0, t1)
    if hk:
        hl = next((l["text"] for l in lyr if abs(l["start"] - hk["t0"]) < 1), "")
        if hl: subs.append((hl, 0.25, hk["t1"] - hk["t0"] + 0.3))
    if spec["intro"].get("timing"): subs += subs_for(json.load(open(spec["intro"]["timing"])), T_INTRO + OFF_I)
    subs += [(l["text"], T_HYMN + l["start"] - 0.2, T_HYMN + l["end"] + 0.3) for l in lyr]
    if spec["meditation"].get("timing"): subs += subs_for(json.load(open(spec["meditation"]["timing"])), T_MED + OFF_M)
    for k, (txt, a, b) in enumerate(subs):
        p = os.path.join(wd, f"sub_{k:03d}.png"); subtitle(txt, p, size=66, bottom=96, wrap=44); ov.append((p, a, b))   # TV: big, high-contrast, inside the 5 % safe area
    # each overlay input only lasts its own window (shifted with setpts) → ~10× faster than full-length looped PNGs
    ov = [(q, max(0, a - A0), min(OUTLEN, b - A0)) for q, a, b in ov if b - A0 > 0.5 and a - A0 < OUTLEN - 0.5]
    wm = spec.get("watermark", os.path.join(D, "brand_seal", "v3", "dark", "watermark-dark_300.png"))
    if wm and os.path.exists(wm):   # brand rule: DARK seal on video, 60–80 % opacity, top-right (clear of YouTube's bottom-right branding + our subtitles)
        s = W / 1920; mk = Image.open(wm).convert("RGBA").resize((int(110 * s), int(110 * s)), Image.LANCZOS)
        mk.putalpha(mk.split()[3].point(lambda v: int(v * 0.68))); fr = Image.new("RGBA", (W, H), (0, 0, 0, 0)); fr.alpha_composite(mk, (W - int(150 * s), int(40 * s)))
        wp = os.path.join(wd, "watermark.png"); fr.save(wp); ov.append((wp, 0.0, OUTLEN))
    oin = sum((["-loop", "1", "-framerate", str(FPS), "-t", f"{b - a:.3f}", "-i", q] for q, a, b in ov), []); f2 = []; lv = "[0:v]"
    for k, (q, a, b) in enumerate(ov, 1):
        if q.endswith("watermark.png"): f2.append(f"[{k}:v]format=rgba,setpts=PTS+{a:.3f}/TB[o{k}]")
        else: f2.append(f"[{k}:v]format=rgba,fade=t=in:st=0:d=0.4:alpha=1,fade=t=out:st={b - a - 0.4:.2f}:d=0.4:alpha=1,setpts=PTS+{a:.3f}/TB[o{k}]")
        f2.append(f"{lv}[o{k}]overlay=0:0:eof_action=pass[v{k}]"); lv = f"[v{k}]"
    # ---- audio: hook (sung line) · intro voice over soft bed · full hymn · meditation voice over soft bed ----
    na = len(ov) + 1; ai = ["-i", spec["audio"], "-i", iv, "-i", mv]; A, IV, MV = na, na + 1, na + 2; f3 = []; mix = []
    # Suno voice + music as SEPARATE tracks (Dispatch 11-13): music under the voice, gently ducked while he speaks (sidechain), then the same fades
    xtra = 0
    for key, tag, t0, ln, fo in (("intro", "im", T_INTRO, intro_len, ("out", intro_len - XIN, XIN) if XIN else None),
                                 ("meditation", "mm", T_MED, med_len, ("in", 0, XOUT) if XOUT else None)):
        mu = spec[key].get("music")
        if not mu: continue
        ai += ["-i", mu]; k = na + 3 + xtra; xtra += 1
        # Danni 11-13: soft music clearly audible but ~2 steps under the voice → music loudness = voice − UNDER LU (+ gentle ducking while he speaks)
        g = spec[key]["music_gain_db"] if "music_gain_db" in spec[key] and spec[key].get("music_gain_fixed") else \
            round((lufs(iv if key == "intro" else mv) - spec.get("music_under_db", 6)) - lufs(mu), 1)
        print(f"music under {key}: {g:+.1f} dB → {spec.get('music_under_db', 6)} LU under the voice", flush=True)
        fade = f",afade=t={fo[0]}:st={fo[1]:.2f}:d={fo[2]:.2f}" if fo else ""
        f3.append(f"[{k}:a]asetpts=PTS-STARTPTS,volume={g}dB,atrim=0:{ln:.2f}{fade}[{tag}raw]")
        f3.append(f"[{IV if key == 'intro' else MV}:a]asplit=2[{tag}vo][{tag}sc]")
        f3.append(f"[{tag}raw][{tag}sc]sidechaincompress=threshold=0.05:ratio=2.5:attack=80:release=700[{tag}duck]")
        f3.append(f"[{tag}duck]adelay={int(t0 * 1000)}:all=1[{tag}]"); mix.append(f"[{tag}]")
        if key == "intro": IV = f"{tag}vo"
        else: MV = f"{tag}vo"
    lab = lambda x: f"[{x}:a]" if isinstance(x, int) else f"[{x}]"
    if hk:
        f3.append(f"[{A}:a]atrim={hk['t0']}:{hk['t1'] + 0.6},asetpts=PTS-STARTPTS,afade=t=in:d=0.3,afade=t=out:st={hk['t1'] - hk['t0']}:d=0.6[hk]"); mix.append("[hk]")
    hy_f = (f"afade=t=in:d={XIN:.2f}," if XIN else "") + (f"afade=t=out:st={hymn_len - XOUT:.2f}:d={XOUT:.2f}," if XOUT else "")
    f3.append(f"[{A}:a]asetpts=PTS-STARTPTS,{hy_f}adelay={int(T_HYMN * 1000)}:all=1[hy]"); mix.append("[hy]")
    iv_f = f"afade=t=out:st={intro_len - XIN:.2f}:d={XIN:.2f}," if XIN else ""   # Suno intro: its music bed dips out as the hymn rises
    if spec["intro"].get("music"): iv_f = ""   # with a separate music track the voice ends on its own; the music carries the crossfade
    f3.append(f"{lab(IV)}asetpts=PTS-STARTPTS,{iv_f}adelay={int((T_INTRO + OFF_I) * 1000)}:all=1[iv]"); mix.append("[iv]")
    mv_f = f"afade=t=in:d={XOUT:.2f}," if XOUT and not spec["meditation"].get("music") else ""
    f3.append(f"{lab(MV)}asetpts=PTS-STARTPTS,{mv_f}adelay={int((T_MED + OFF_M) * 1000)}:all=1[mv]"); mix.append("[mv]")
    bd = spec.get("bed")
    if bd:   # soft instrumental bed from the hymn's own instrumental span, under spoken parts that have no bed of their own (not Suno)
        need = lambda key, suno: (not suno) or spec[key].get("add_bed")   # Suno voice delivered with music OFF (e.g. film #1 ending) → our soft bed
        span = lufs(spec["audio"], bd["t0"], bd["t1"])
        for tag, t0, ln, vf in [(*x, v) for x, k, s, v in ((("bi", T_INTRO, intro_len), "intro", SI, iv), (("bm", T_MED, med_len), "meditation", SM, mv)) if need(k, s)]:
            bg = round(lufs(vf) - spec.get("music_under_db", 6) - span, 1)   # bed sits a fixed distance under THIS voice (Danni 11-13), not a fixed −24 dB
            print(f"bed under {tag}: {bg:+.1f} dB", flush=True)
            f3.append(f"[{A}:a]atrim={bd['t0']}:{bd['t1']},asetpts=PTS-STARTPTS,aloop=loop=-1:size={int((bd['t1'] - bd['t0']) * 48000)},atrim=0:{ln:.2f},volume={bg}dB,"
                      f"afade=t=in:d=1.5,afade=t=out:st={ln - 2.5:.2f}:d=2.5,adelay={int(t0 * 1000)}:all=1[{tag}]"); mix.append(f"[{tag}]")
    f3.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=longest,atrim={A0:.3f}:{A0 + OUTLEN:.3f},asetpts=PTS-STARTPTS,alimiter=limit=0.95[aout]")
    meta = os.path.join(wd, "chapters.ffmeta")
    chs = [("Intro", 0.0, T_HYMN), ("Hymn", T_HYMN, T_MED), ("Meditation", T_MED, TOTAL)]
    if EXCERPT: chs = [(t, max(0, a - A0), min(OUTLEN, b - A0)) for t, a, b in chs if b - A0 > 1 and a - A0 < OUTLEN - 1]
    open(meta, "w").write(";FFMETADATA1\ntitle=" + spec["title"] + "\n" + "".join(f"[CHAPTER]\nTIMEBASE=1/1000\nSTART={int(a * 1000)}\nEND={int(b * 1000)}\ntitle={t}\n" for t, a, b in chs))
    MI = na + 3 + xtra
    sh("ffmpeg", "-v", "error", "-y", "-i", base, *oin, *ai, "-i", meta, "-filter_complex", ";".join(f2 + f3), "-map", lv, "-map", "[aout]",
       "-map_metadata", str(MI), "-map_chapters", str(MI), "-c:v", "libx264", "-profile:v", "high", "-pix_fmt", "yuv420p",
       "-preset", "veryfast" if DRAFT else "slow", "-crf", "18", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out + ".mp4")
    mm = lambda t: f"{int(t // 60)}:{int(t % 60):02d}"
    open(out + ".chapters.txt", "w").write("\n".join(f"{mm(a)} {t}" for t, a, b in chs) + "\n")
    json.dump({"total_s": round(TOTAL, 2), "chapters": chs, "scenes": [(os.path.basename(i), round(a, 2), round(b, 2)) for i, a, b in sc],
               "overlays": [(os.path.basename(q), round(a, 2), round(b, 2)) for q, a, b in ov]}, open(out + ".timeline.json", "w"), indent=1)
    print("FILM_DONE", out + ".mp4", f"{TOTAL:.1f}s", len(sc), "scenes", flush=True)
    if not EXCERPT and "--no-segments" not in sys.argv: export_segments(out, base, chs, [(t, a - A0, b - A0) for t, a, b in subs], wm)

def export_segments(out, base, chs, subs, wm):
    """Dispatch 11-13 (approved): per-segment clips next to the full film.
    16:9: <out>_seg_<Chapter>.mp4 (the finished frames + audio of each chapter).
    9:16 Shorts-ready: <out>_short_<Chapter>_<n>.mp4, ≤ 58 s parts cut at subtitle boundaries, re-framed from the TEXT-FREE picture (centre crop),
    subtitles re-drawn for vertical (above the Shorts caption zone), dark seal top-left (Shorts safe zone), audio from the film. Upload rules still apply."""
    sd = out + "_segments"; os.makedirs(sd, exist_ok=True); man = []
    VW, VH = (540, 960) if DRAFT else (1080, 1920)
    for name, a, b in chs:
        o = os.path.join(sd, f"seg_{name}.mp4")
        sh("ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", out + ".mp4", "-c:v", "libx264", "-preset", "veryfast" if DRAFT else "medium",
           "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", o)
        man.append({"file": os.path.basename(o), "kind": "16:9", "chapter": name, "start": round(a, 2), "end": round(b, 2)})
        # vertical parts: greedy at subtitle boundaries, ≤ 58 s
        inside = [s for s in subs if s[1] >= a - 0.1 and s[2] <= b + 0.1]; parts = []; p0 = a
        for t, s0, s1 in inside:
            if s1 - p0 > 58: parts.append((p0, max(p0 + 5, s0 - 0.2))); p0 = max(p0 + 5, s0 - 0.2)
        if b - p0 > 4: parts.append((p0, min(b, p0 + 58)))
        for n, (pa, pb) in enumerate(parts, 1):
            vo = os.path.join(sd, f"short_{name}_{n}.mp4"); ps = [s for s in inside if s[2] > pa and s[1] < pb]
            pngs = []
            for k, (t, s0, s1) in enumerate(ps):
                q = os.path.join(sd, f"_v_{name}_{n}_{k:02d}.png"); subtitle(t, q, size=58, frame=(VW, VH), bottom=420, wrap=26); pngs.append((q, max(0, s0 - pa), min(pb - pa, s1 - pa)))
            inp = ["-ss", f"{pa:.3f}", "-to", f"{pb:.3f}", "-i", base, "-ss", f"{pa:.3f}", "-to", f"{pb:.3f}", "-i", out + ".mp4"]
            fc = [f"[0:v]crop=ih*9/16:ih,scale={VW}:{VH}:flags=lanczos,setsar=1[v0]"]; lv = "[v0]"
            for k, (q, s0, s1) in enumerate(pngs):
                inp += ["-loop", "1", "-framerate", str(FPS), "-t", f"{s1 - s0:.3f}", "-i", q]
                fc.append(f"[{k + 2}:v]format=rgba,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st={max(0, s1 - s0 - 0.3):.2f}:d=0.3:alpha=1,setpts=PTS+{s0:.3f}/TB[s{k}]")
                fc.append(f"{lv}[s{k}]overlay=0:0:eof_action=pass[w{k}]"); lv = f"[w{k}]"
            if wm and os.path.exists(wm):
                inp += ["-i", wm]; j = len(pngs) + 2
                fc.append(f"[{j}:v]scale={int(VW * 0.11)}:-1,format=rgba,colorchannelmixer=aa=0.68[wm]"); fc.append(f"{lv}[wm]overlay={int(VW * 0.05)}:{int(VH * 0.05)}[wf]"); lv = "[wf]"
            sh("ffmpeg", "-v", "error", "-y", *inp, "-filter_complex", ";".join(fc), "-map", lv, "-map", "1:a", "-t", f"{pb - pa:.3f}", "-c:v", "libx264",
               "-preset", "veryfast" if DRAFT else "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", vo)
            for q, _, _ in pngs: os.remove(q)
            man.append({"file": os.path.basename(vo), "kind": "9:16", "chapter": name, "start": round(pa, 2), "end": round(pb, 2), "dur": round(pb - pa, 2)})
    json.dump(man, open(os.path.join(sd, "segments.json"), "w"), indent=1); print("SEGMENTS_DONE", sd, len(man), flush=True)

if __name__ == "__main__": main()
