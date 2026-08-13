#!/usr/bin/env python3
# =============================================================================
# CrossAIHub — Hymn-B section renderer (CLOUD port of hymn_visualizer v4e)
# -----------------------------------------------------------------------------
# FAITHFUL port of _pipeline_v4/hymn_visualizer/renderer.py (the SOLE locked
# hymn render path, Founder unification 2026-08-03 + v4e audio-driven cross
# 2026-08-04). Reproduces byte-for-byte the two pieces that are Python-logic
# rather than a static ffmpeg string:
#   1. _extract_cross_brightness_envelope()  — RMS → per-frame `eq brightness`
#      sendcmd script (the "living" cross that breathes with the hymn).
#   2. _build_filter_complex()  — cover(static) + watermark(top-right) +
#      audio-driven cross glow(center) + ribbon(intro 5s + last 30s) +
#      credits(last 30s fade). take_B => with_credits=True + ribbon present.
#
# Uses the PRE-BAKED PNG caches (watermark fa499139 + cross_living_glow_v1),
# so NO Pillow/numpy is needed on the runner (source-optional mode of the SSOT).
#
# Encoding is passed in from render_episode.sh so the WHOLE episode is uniform
# config.ENC_V/ENC_A (CRF 18 / AAC 384k·48k) — the Founder-directed reconciliation
# to _pipeline_v4/config.py. (NOTE: the local OUTPUT_SPEC uses CRF 20 / 192k for
# the hymn only; see RECONCILIATION_REPORT.md "OUTPUT_SPEC vs ENC_V" divergence.)
# =============================================================================
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# ── SSOT constants (verbatim from hymn_visualizer/__init__.py SPEC dicts) ─────
WM_SCALE_WIDTH = 220          # WATERMARK_SPEC.scale_width
WM_X_FROM_RIGHT = 60          # WATERMARK_SPEC.position_x_from_right
WM_Y_FROM_TOP = 40            # WATERMARK_SPEC.position_y_from_top
CREDITS_VISIBLE = 30.0        # CREDITS_SPEC.visible_seconds
CREDITS_FADE = 2.0            # CREDITS_SPEC.fade_duration
RIBBON_INTRO_VISIBLE = 5.0    # RIBBON_SPEC.intro_visible_seconds
RIBBON_OUTRO_VISIBLE = 30.0   # RIBBON_SPEC.outro_visible_seconds
RIBBON_FADE = 1.0             # RIBBON_SPEC.fade_duration
FPS = 30                      # OUTPUT_SPEC.fps


def _probe_audio_duration(audio_path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(audio_path)],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return float(json.loads(r.stdout)["format"]["duration"])


def _extract_cross_brightness_envelope(
    audio_path: Path, work_dir: Path,
    fps: int = FPS, smoothing_frames: int = 6,
    brightness_min: float = -0.20, brightness_max: float = 0.25,
    percentile_lo: float = 0.05, percentile_hi: float = 0.95,
) -> Path:
    """Verbatim port of renderer._extract_cross_brightness_envelope."""
    cache = work_dir / "cross_glow.crossglow_v4.cmd"
    win_samples = 48000 // fps  # 1600 @ 30fps
    with tempfile.NamedTemporaryFile("r", suffix=".txt", delete=False) as tf:
        rms_txt = tf.name
    try:
        af = (
            f"aresample=48000,aformat=channel_layouts=mono,"
            f"asetnsamples=n={win_samples}:p=0,"
            f"astats=metadata=1:reset=1,"
            f"ametadata=print:key=lavfi.astats.Overall.RMS_level:file={rms_txt}"
        )
        r = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-i", str(audio_path), "-af", af, "-f", "null", "-"],
            capture_output=True, text=True, timeout=600,
        )
        if r.returncode != 0:
            raise RuntimeError(f"astats extraction failed rc={r.returncode}: {r.stderr[:500]}")
        times: list[float] = []
        rms_db: list[float] = []
        with open(rms_txt) as f:
            lines = f.readlines()
        i = 0
        while i < len(lines) - 1:
            m1 = re.search(r"pts_time:([0-9.]+)", lines[i])
            m2 = re.search(r"RMS_level=(-?[0-9.]+|-inf)", lines[i + 1])
            if m1 and m2:
                t = float(m1.group(1))
                v = m2.group(1)
                v = -80.0 if v == "-inf" else float(v)
                times.append(t)
                rms_db.append(max(-80.0, min(0.0, v)))
                i += 2
            else:
                i += 1
    finally:
        try:
            os.remove(rms_txt)
        except OSError:
            pass
    if not times:
        raise RuntimeError("no RMS frames extracted from audio")

    alpha = 2.0 / (smoothing_frames + 1)
    smooth: list[float] = []
    prev = rms_db[0]
    for v in rms_db:
        prev = alpha * v + (1 - alpha) * prev
        smooth.append(prev)

    sv = sorted(smooth)

    def _pct(vals, p):
        k = (len(vals) - 1) * p
        lo = int(k); hi = min(lo + 1, len(vals) - 1)
        frac = k - lo
        return vals[lo] * (1 - frac) + vals[hi] * frac

    lo_db = _pct(sv, percentile_lo)
    hi_db = _pct(sv, percentile_hi)
    if hi_db - lo_db < 3.0:
        lo_db, hi_db = min(smooth), max(smooth)
    if hi_db - lo_db < 1.0:
        lo_db, hi_db = -50.0, -20.0
    span_db = hi_db - lo_db
    span_b = brightness_max - brightness_min

    with open(cache, "w") as f:
        for t, v in zip(times, smooth):
            k = (v - lo_db) / span_db
            k = max(0.0, min(1.0, k))
            b = brightness_min + k * span_b
            f.write(f"{t:.4f} eq brightness {b:.4f};\n")
    return cache


def _build_filter_complex(duration: float, sendcmd_path: Path) -> str:
    """Verbatim port of renderer._build_filter_complex for the take_B case
    (ribbon present + with_credits=True)."""
    credits_start = max(0.0, duration - CREDITS_VISIBLE)
    fade_dur = CREDITS_FADE
    base = (
        "[0:v]scale=1920:1080:force_original_aspect_ratio=increase,"
        "crop=1920:1080,setsar=1,format=yuv420p[bg];"
        f"[2:v]scale={WM_SCALE_WIDTH}:-1[wm];"
        f"[bg][wm]overlay=W-w-{WM_X_FROM_RIGHT}:{WM_Y_FROM_TOP}:format=auto[with_wm];"
        f"[3:v]format=rgba,split[cross_rgba_a][cross_rgba_b];"
        f"[cross_rgba_a]alphaextract[cross_a];"
        f"[cross_rgba_b]sendcmd=f={sendcmd_path},eq=brightness=0[cross_rgb];"
        f"[cross_rgb][cross_a]alphamerge[cross_breathing];"
        f"[with_wm][cross_breathing]overlay="
        f"x=(main_w-overlay_w)/2:y=(main_h-overlay_h)/2:format=auto"
    )
    intro_visible = RIBBON_INTRO_VISIBLE
    outro_visible = RIBBON_OUTRO_VISIBLE
    ribbon_fade = RIBBON_FADE
    intro_fade_out_start = max(0.0, intro_visible - ribbon_fade)
    outro_start = max(0.0, duration - outro_visible)
    outro_fade_out_start = max(0.0, duration - ribbon_fade)
    ribbon_input_idx = 4
    credits_input_idx = 5
    ribbon_frags = (
        f"[{ribbon_input_idx}:v]format=rgba,split[r_intro][r_outro];"
        f"[r_intro]"
        f"fade=t=in:st=0:d={ribbon_fade}:alpha=1,"
        f"fade=t=out:st={intro_fade_out_start}:d={ribbon_fade}:alpha=1"
        f"[ribbon_intro];"
        f"[r_outro]"
        f"fade=t=in:st={outro_start}:d={ribbon_fade}:alpha=1,"
        f"fade=t=out:st={outro_fade_out_start}:d={ribbon_fade}:alpha=1"
        f"[ribbon_outro];"
    )
    ribbon_overlay_intro = (
        f"overlay=x=0:y=main_h-overlay_h:"
        f"enable='between(t,0,{intro_visible})':format=auto"
    )
    ribbon_overlay_outro = (
        f"overlay=x=0:y=main_h-overlay_h:"
        f"enable='between(t,{outro_start},{duration})':format=auto"
    )
    return (
        base + "[with_cross];"
        + ribbon_frags
        + f"[with_cross][ribbon_intro]{ribbon_overlay_intro}[with_r1];"
        + f"[with_r1][ribbon_outro]{ribbon_overlay_outro}[with_ribbon];"
        + f"[{credits_input_idx}:v]format=rgba,"
        + f"fade=t=in:st={credits_start}:d={fade_dur}:alpha=1[credits_fx];"
        + f"[with_ribbon][credits_fx]overlay=x=(W-w)/2:y=(H-h)/2:"
        + f"enable='between(t,{credits_start},{duration})':format=auto[v]"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cover", required=True)
    ap.add_argument("--audio", required=True)         # hymn take_B
    ap.add_argument("--watermark", required=True)     # baked fa499139 cache
    ap.add_argument("--glow", required=True)          # baked cross_living_glow_v1
    ap.add_argument("--ribbon", required=True)        # hymn_NN.png
    ap.add_argument("--credits", required=True)       # credits_overlay.png
    ap.add_argument("--out", required=True)
    ap.add_argument("--work", required=True)
    # Encoding params — passed by render_episode.sh from config.ENC_V/ENC_A
    ap.add_argument("--crf", default="18")
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--abitrate", default="384k")
    args = ap.parse_args()

    cover = Path(args.cover); audio = Path(args.audio)
    watermark = Path(args.watermark); glow = Path(args.glow)
    ribbon = Path(args.ribbon); credits = Path(args.credits)
    out = Path(args.out); work = Path(args.work)
    for p, name in [(cover, "cover"), (audio, "audio"), (watermark, "watermark"),
                    (glow, "glow"), (ribbon, "ribbon"), (credits, "credits")]:
        if not p.exists():
            print(f"[FATAL] {name} not found: {p}", file=sys.stderr); return 2
    work.mkdir(parents=True, exist_ok=True)

    duration = _probe_audio_duration(audio)
    sendcmd_path = _extract_cross_brightness_envelope(audio, work)
    fcomplex = _build_filter_complex(duration, sendcmd_path)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-stats",
        "-loop", "1", "-framerate", str(FPS), "-t", f"{duration:.3f}", "-i", str(cover),
        "-i", str(audio),
        "-loop", "1", "-framerate", str(FPS), "-t", f"{duration:.3f}", "-i", str(watermark),
        "-loop", "1", "-framerate", str(FPS), "-t", f"{duration:.3f}", "-i", str(glow),
        "-loop", "1", "-framerate", str(FPS), "-t", f"{duration:.3f}", "-i", str(ribbon),
        "-loop", "1", "-framerate", str(FPS), "-t", f"{duration:.3f}", "-i", str(credits),
        "-filter_complex", fcomplex,
        "-map", "[v]", "-map", "1:a",
        # ── config.ENC_V (CRF 18 · GOP60 · scenecut0 · bt709) ──
        "-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-g", "60", "-keyint_min", "60", "-x264-params", "scenecut=0:open-gop=0",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        # ── config.ENC_A (AAC 384k · 48k · stereo) ──
        "-c:a", "aac", "-b:a", str(args.abitrate), "-ar", "48000", "-ac", "2",
        "-movflags", "+faststart",
        "-t", f"{duration:.3f}",
        str(out),
    ]
    print(f"[hymn-B] duration={duration:.2f}s cover={cover.name} audio={audio.name}")
    r = subprocess.run(cmd)
    if r.returncode != 0:
        print(f"[FATAL] ffmpeg exited {r.returncode}", file=sys.stderr); return 3
    print(f"[OK] hymn-B section written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
