# Pair 04 · Cloud Render — Reconciliation Report (scaffold → `_pipeline_v4/config.py`)

**Date:** 2026-08-08 · **By:** Claude (Cowork), real Mac.
**Goal:** make the GitHub Actions cloud render FULLY law-compliant BEFORE any render is triggered.
**Render NOT triggered. GitHub NOT signed into. `PROVISION_CLOUD_RENDER.command` left as-is.**

## Files changed (in the scaffold the one-click publishes)
`_production_law/_cloud_render_inspect/crossaihub-cloud-render/`
- `scripts/render_episode.sh` — full rewrite, reconciled.
- `scripts/render_hymn_section.py` — NEW: faithful port of `hymn_visualizer` v4e (audio-driven cross glow + ribbon + credits).
- `.github/workflows/render-episode.yml` — CRF default 18; Pillow for watermark QC; pulls brand incl. overlays + S3 bed.
- `ASSET_CONTRACT.md` — NEW: exact Drive layout/filenames.

## Line-by-line: reconciled setting vs SSOT

- **CRF** — was `24` (window 23–26) → now **`18`**. Source: `config.py ENC_V` `-crf 18`. ✔
- **Video encode** — now `libx264 -preset medium -crf 18 -pix_fmt yuv420p -r 30 -g 60 -keyint_min 60 -x264-params scenecut=0:open-gop=0 -color_primaries/-trc/-colorspace bt709 -movflags +faststart`. Source: `config.py ENC_V` verbatim. ✔
- **Color range** — was forced `-color_range pc` (full/yuvj420p) → **removed** (SSOT sets no full-range). ✔
- **Audio bitrate/rate** — was `AAC 192k`, no rate → now **`AAC 384k / 48000 / stereo`**. Source: `config.py ENC_A`. ✔ (encode log confirms `aac … 48000 Hz, stereo, 384 kb/s`).
- **Music bed + sidechain** — was absent → now **narration master + `S3_Theme.mp3` looped, `volume=0.06` (BED_GAIN), `sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400:level_in=1.0`, then `loudnorm I=-16:TP=-1:LRA=9`**. Source: `tracks/episode_audio.py _mix_narration_with_bed` (bed+sidechain+loudnorm tail). ✔
  - Note: the approved `narration_masterB_paced.flac` already carries the locked Version-B voice chain, so the voice chain (+6 dB/deesser/acompressor) is **not re-applied** — only the bed/sidechain/final-loudnorm tail runs.
- **Watermark placement** — was bottom-right `overlay=W-w-48:H-h-48`, `scale=iw*0.16` → now **top-right `overlay=W-w-60:40`, `scale=-1:220` (body)**. Source: `config.py WM_X/WM_Y/WM_HEIGHT` + `tracks/pexels.py _normalize_clip`. ✔
- **Watermark full-duration + zero-gap** — burned once per body clip before concat (continuous by construction) and across the whole hymn by the visualizer. **BUG-14 continuous-scan QC** re-implemented (`_watermark_visible` gold-region method, fine step, fail on first gap; excludes Tudum + 1.5 s silence where WM is hidden by design). Verified: "watermark CONTINUOUS" on body. ✔
- **Watermark identity** — added a hard gate: `sha256(watermark.png)` must start `fa499139` or the render aborts. ✔
- **Watermark hidden during Tudum** — Tudum normalized with no watermark overlay. Source: `config.WM_VISIBLE_PHASES` (Tudum excluded). ✔
- **Ribbon** — was a full-screen mp4 segment → now the **`hymn_04.png` PNG overlay, bottom-flush, visible first 5 s + last 30 s, 1 s fade per window** (two-stream split, per the 2026-08-05 ribbon-fix2). Source: `RIBBON_SPEC` + `renderer._build_filter_complex`. ✔ (verified present at sample).
- **Credits** — was a full-screen end segment → now **`credits_overlay.png` overlay, centered, fade-in over last 30 s (2 s fade)**. Source: `CREDITS_SPEC` + renderer. ✔
- **Cross resurrection glow** — was absent → now **added**: baked `cross_living_glow_v1.png` overlaid centered with **audio-driven brightness** (RMS→per-frame `eq brightness` sendcmd envelope), alpha preserved via split/alphaextract/alphamerge. Source: `renderer._extract_cross_brightness_envelope` + `_build_filter_complex` (ported verbatim). ✔ (verified: 360-frame envelope for a 12 s take; glow present at sample).
- **Structure/order** — Tudum → Episode Body → Silence 1.5 s → Hymn-B (Take B, with credits). Source: `assemble.py` default (`intro_card` OFF, outro Tudum OFF per PRODUCTION LAW v1.0 2026-08-05; credits scroll is the only ending). ✔
- **Final assembly** — stream-copy concat (`-c copy +faststart`); all segments share ENC_V/ENC_A. Source: `assemble._final_concat_episode`. ✔
- **Uniform loudness −16 LUFS** — via the audio mix `loudnorm I=-16` + a QC loudness check. ✔
- **Nature-only b-roll / Pexels use-once** — enforced upstream at b-roll selection (`config.PEXELS_*`); the render consumes `body_segments.txt` as given. (Contract-level.)

## Verification (local smoke test of the identical scripts, sandbox)
`bash -n` + `py_compile` + YAML parse all pass. A synthetic end-to-end exercised every stage: tudum normalize; per-clip watermark burn (top-right); body concat; narration+S3-bed+sidechain+loudnorm mix (→ `aac 48000`); 1.5 s silence; **hymn-B v4e** (h264 1920×1080, aac 48 k, 360-line audio-driven glow envelope, watermark+glow+ribbon+credits all present); and the **BUG-14 zero-gap watermark scan returned "CONTINUOUS."**

## What still cannot be made compliant purely in the cloud path (honest limits)
1. **Inputs still missing (upstream gaps — render can't RUN yet):** Hymn **Take B audio + cover** (Suno) and the **b-roll `body_segments.txt` + clips** do not exist for pair_04. The reconciled script hard-fails clearly if they're absent. These are production steps, not compliance defects.
2. **SSOT internal inconsistency (needs a Founder decision):** `config.ENC_V/ENC_A` = **CRF 18 / 384k**, but `hymn_visualizer OUTPUT_SPEC` = **CRF 20 / 192k**. I reconciled the cloud to **config.py (CRF 18 / 384k uniform)** as instructed — which means the cloud hymn section differs from the *local* hymn (still CRF 20 / 192k). Recommend updating `OUTPUT_SPEC` to match `config.py` so local + cloud agree.
3. **Watermark scale-axis drift in the SSOT:** body uses `scale=-1:220` (→192×220), hymn uses `scale=220:-1` (→220×252). I matched each section to its own SSOT source. Minor; unify if desired.
4. **Cross-glow doc vs code drift:** `__init__.py CROSS_LIVING_GLOW_SPEC` text says *time-based sine*, but `renderer.py` implements *audio-driven RMS* (v4). I ported the **code** (authoritative). Doc could be cleaned up.
5. **Structure phrasing:** round-1 said "Tudum intro/outro matched," but the SSOT default is **intro Tudum only** (outro OFF). I followed the SSOT default; an `INCLUDE_OUTRO_TUDUM` path exists if you want both — confirm which you want.
6. **Not yet runtime-verified in the actual GitHub runner** (no trigger, no sign-in, per your instruction). Verified via local smoke test of the identical scripts; the cloud run remains untriggered until you provision + the two upstream inputs exist.
