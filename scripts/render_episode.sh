#!/usr/bin/env bash
# =============================================================================
# CrossAIHub — CLOUD render (Linux / GitHub Actions) · RECONCILED to SSOT
# -----------------------------------------------------------------------------
# Reconciled 2026-08-08 to _pipeline_v4/config.py + hymn_visualizer (the LOCKED
# SSOT). Every locked standard below cites its config.py / SPEC source. See
# RECONCILIATION_REPORT.md for the line-by-line diff table.
#
# EPISODE structure (assemaavble.py default · PRODUCTION LAW v1.0 2026-08-05):
#   Tudum(norm) -> EpisodeBody(WM + narration+S3 bed ducked) -> Silence 1.5s
#     -> Hymn-B section (cross-glow + ribbon 5s/30s + credits 30s fade)
#   (intro_card OFF · outro tudum OFF by default · credits = the only ending)
# Final assembly is STREAM-COPY concat — every segment shares ENC_V/ENC_A.
# =============================================================================
set -euo pipefail

# ───────────────────────── 0. Config / inputs ───────────────────────────────
PAIR="${PAIR:?PAIR (e.g. 04) required}"
PSALM="${PSALM:?PSALM (e.g. 121) required}"

ASSETS_DIR="${ASSETS_DIR:-${GITHUB_WORKSPACE:-$PWD}/assets}"
OUT_DIR="${OUT_DIR:-${GITHUB_WORKSPACE:-$PWD}/out}"
WORK_DIR="${WORK_DIR:-/tmp/crossaihub_${PAIR}_${PSALM}}"
QC_DIR="${OUT_DIR}/qc"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# LOCKED ENCODING — config.py ENC_V / ENC_A  [reconciled: CRF 24->18, 192k->384k]
CRF="${CRF:-18}"                 # config.py ENC_V crf 18  (NOT 24)
PRESET="${PRESET:-medium}"       # config.py ENC_V preset medium
FPS=30; WIDTH=1920; HEIGHT=1080  # config.py FPS / WIDTH / HEIGHT
REQUIRED_FREE_GB="${REQUIRED_FREE_GB:-6}"

# config.py ENC_V (libx264 · CRF18 · GOP60 · scenecut0/open-gop0 · bt709 · faststart)
# NOTE: NO -color_range pc (dropped the scaffold's forced full-range → matches SSOT)
ENC_V=(-c:v libx264 -preset "$PRESET" -crf "$CRF" -pix_fmt yuv420p -r "$FPS"
       -g 60 -keyint_min 60 -x264-params scenecut=0:open-gop=0
       -color_primaries bt709 -color_trc bt709 -colorspace bt709 -movflags +faststart)
# config.py ENC_A (AAC 384k · 48kHz · stereo)   [NOT 192k]
ENC_A=(-c:a aac -b:a 384k -ar 48000 -ac 2)

# LOCKED WATERMARK (body) — config.py WM_HEIGHT / WM_X / WM_Y  [top-right · NOT bottom-right]
WM_HEIGHT=220; WM_X="W-w-60"; WM_Y=40                  # scale=-1:220 · 60px right · 40px top

# Brand + episode asset layout (pulled from Drive by the workflow)
BRAND_DIR="${ASSETS_DIR}/brand"
OVERLAY_DIR="${BRAND_DIR}/_locked_overlays"
EP_DIR="${ASSETS_DIR}/episodes/pair${PAIR}"

WATERMARK="${WATERMARK:-${BRAND_DIR}/watermark.png}"           # fa499139 (verified in QC)
TUDUM="${TUDUM:-${BRAND_DIR}/tudum.mp4}"                       # config.TUDUM_SRC
S3_THEME="${S3_THEME:-${BRAND_DIR}/S3_Theme.mp3}"             # config.S3_THEME (music bed)
RIBBON_HYMN="${OVERLAY_DIR}/hymn_${PAIR}.png"                 # config.ribbon_hymn_png(PAIR)
CREDITS_PNG="${OVERLAY_DIR}/credits_overlay.png"             # config.CREDITS_PNG
CROSS_GLOW="${OVERLAY_DIR}/cross_living_glow_v1.png"         # CROSS_LIVING_GLOW_SPEC cache

NARRATION="$(ls "${EP_DIR}"/narration.* 2>/dev/null | head -n1 || true)"   # approved paced master
HYMN_B="$(ls "${EP_DIR}"/take_B.* "${EP_DIR}"/psalm${PSALM}.* "${EP_DIR}"/hymn.* 2>/dev/null | head -n1 || true)"
HYMN_COVER="$(ls "${EP_DIR}"/cover.* 2>/dev/null | head -n1 || true)"
BODY_LIST="${EP_DIR}/body_segments.txt"                       # ordered nature b-roll (Pexels use-once)

FINAL="${OUT_DIR}/CrossAIHub_EP_pair${PAIR}_psalm${PSALM}.mp4"

log(){ printf '\n\033[1;36m[render]\033[0m %s\n' "$*"; }
die(){ printf '\n\033[1;31m[FATAL]\033[0m %s\n' "$*" >&2; exit 1; }
mkdir -p "$OUT_DIR" "$QC_DIR" "$WORK_DIR"
dur(){ ffprobe -v error -show_entries format=duration -of csv=p=0 "$1"; }

# ───────────────────────── 1. Disk gate + tool check ────────────────────────
free_gb="$(df -Pk "$WORK_DIR" | awk 'NR==2{printf "%d", $4/1024/1024}')"
log "Disk gate: ${free_gb} GB free (need >= ${REQUIRED_FREE_GB})"
[ "${free_gb:-0}" -ge "$REQUIRED_FREE_GB" ] || die "Disk gate failed: ${free_gb} GB."
command -v ffmpeg  >/dev/null || die "ffmpeg not on PATH."
command -v ffprobe >/dev/null || die "ffprobe not on PATH."
command -v python3 >/dev/null || die "python3 not on PATH."
for f in "$WATERMARK" "$TUDUM" "$S3_THEME" "$RIBBON_HYMN" "$CREDITS_PNG" "$CROSS_GLOW"; do
  [ -f "$f" ] || die "Required brand asset missing: $f"
done
[ -n "$NARRATION" ] || die "Approved narration missing (episodes/pair${PAIR}/narration.*)."
[ -f "$BODY_LIST" ] || die "body_segments.txt missing (upstream b-roll step)."
[ -n "$HYMN_B" ]     || die "Hymn Take B audio missing (upstream hymn/Suno step)."
[ -n "$HYMN_COVER" ] || die "Hymn cover image missing (upstream hymn step)."

# ───────────────── watermark identity gate — SHA fa499139 (LAW) ─────────────
WM_SHA="$(sha256sum "$WATERMARK" | cut -c1-8)"
[ "$WM_SHA" = "fa499139" ] || die "Watermark SHA $WM_SHA != fa499139 (locked brand law)."
log "Watermark SHA verified: fa499139"

# ───────────────────────── helpers (config.ENC_V/ENC_A) ─────────────────────
# Uniform normalize (video only) → 1920x1080 letterboxed · 30fps · yuv420p · bt709.
normalize(){ local in="$1" out="$2"
  ffmpeg -hide_banner -nostdin -y -i "$in" \
    -vf "scale=${WIDTH}:${HEIGHT}:force_original_aspect_ratio=decrease,\
pad=${WIDTH}:${HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=${FPS}" \
    "${ENC_V[@]}" -an "$out"; }

# Normalize + burn watermark TOP-RIGHT (config.WM_*) — one pass per clip so the
# watermark is present for the FULL duration of every body clip (BUG-14: zero
# gaps by construction across the concatenated body).
normalize_wm(){ local in="$1" out="$2"
  ffmpeg -hide_banner -nostdin -y -i "$in" -i "$WATERMARK" \
    -filter_complex \
"[0:v]scale=${WIDTH}:${HEIGHT}:force_original_aspect_ratio=decrease,\
pad=${WIDTH}:${HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=${FPS}[bg];\
[1:v]scale=-1:${WM_HEIGHT}[wm];\
[bg][wm]overlay=x=${WM_X}:y=${WM_Y}:format=auto[v]" \
    -map "[v]" "${ENC_V[@]}" -an "$out"; }

# ───────────────────────── 2. Tudum (normalized · NO watermark) ─────────────
log "Normalizing Tudum (watermark hidden during Tudum — config.WM_VISIBLE_PHASES)"
TUDUM_N="${WORK_DIR}/tudum_norm.mp4"
ffmpeg -hide_banner -nostdin -y -i "$TUDUM" "${ENC_V[@]}" "${ENC_A[@]}" "$TUDUM_N"

# ───────────────────────── 3. Episode body (WM + audio bed) ─────────────────
log "Preparing BODY clips (normalize + watermark top-right)…"
i=0; BODY_CLIPS=()
while IFS= read -r line; do
  line="${line%%#*}"; line="$(echo "$line" | xargs || true)"; [ -z "$line" ] && continue
  src="${EP_DIR}/${line}"; [ -f "$src" ] || src="${ASSETS_DIR}/${line}"
  [ -f "$src" ] || die "Body segment not found: $line"
  wmf="${WORK_DIR}/body_wm_$(printf '%03d' "$i").mp4"
  normalize_wm "$src" "$wmf"; BODY_CLIPS+=("$wmf"); i=$((i+1))
done < "$BODY_LIST"
[ "${#BODY_CLIPS[@]}" -ge 1 ] || die "No body clips prepared."
log "Concatenating ${#BODY_CLIPS[@]} watermarked body clips (stream copy)…"
: > "${WORK_DIR}/body_list.txt"
for c in "${BODY_CLIPS[@]}"; do echo "file '${c}'" >> "${WORK_DIR}/body_list.txt"; done
ffmpeg -hide_banner -nostdin -y -f concat -safe 0 -i "${WORK_DIR}/body_list.txt" \
  -c:v copy -an "${WORK_DIR}/body_video.mp4"

# Episode audio = approved narration master  +  S3 theme bed (ducked)  → loudnorm -16.
# The master (narration_masterB_paced.flac) ALREADY carries the locked Version-B
# voice chain (Onyx 0.88 + Chain B · +6dB/deesser/acompressor · per pair progress
# json), so the voice chain is NOT re-applied here — only the bed + sidechain +
# final loudnorm tail of config._mix_narration_with_bed is applied.
NAR_DUR="$(dur "$NARRATION")"
log "Mixing narration master + S3 bed (sidechain duck) → loudnorm -16 LUFS…"
ffmpeg -hide_banner -nostdin -y \
  -i "${WORK_DIR}/body_video.mp4" \
  -i "$NARRATION" \
  -stream_loop -1 -i "$S3_THEME" \
  -filter_complex \
"[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asplit=2[v1][v2];\
[2:a]volume=0.06,atrim=0:${NAR_DUR},asetpts=PTS-STARTPTS,aresample=48000,\
aformat=sample_fmts=fltp:channel_layouts=stereo[bed];\
[v1]aformat=sample_fmts=fltp:channel_layouts=stereo[v1f];\
[bed][v1f]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400:level_in=1.0[bedducked];\
[v2][bedducked]amix=inputs=2:duration=shortest:normalize=0,loudnorm=I=-16:TP=-1:LRA=9[mix]" \
  -map 0:v:0 -map "[mix]" -c:v copy "${ENC_A[@]}" -shortest "${WORK_DIR}/body.mp4"

# ───────────────────────── 4. Silence 1.5s (config assemble._make_silence) ──
log "Building 1.5s silence bridge…"
ffmpeg -hide_banner -nostdin -y \
  -f lavfi -i "color=c=black:s=${WIDTH}x${HEIGHT}:r=${FPS}:d=1.5" \
  -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=48000:d=1.5" \
  "${ENC_V[@]}" "${ENC_A[@]}" -shortest -t 1.5 "${WORK_DIR}/silence.mp4"

# ───────────────────────── 5. Hymn-B section (cross glow+ribbon+credits) ────
log "Rendering Hymn-B section via faithful hymn_visualizer v4e port…"
python3 "${SCRIPT_DIR}/render_hymn_section.py" \
  --cover "$HYMN_COVER" --audio "$HYMN_B" \
  --watermark "$WATERMARK" --glow "$CROSS_GLOW" \
  --ribbon "$RIBBON_HYMN" --credits "$CREDITS_PNG" \
  --out "${WORK_DIR}/hymn_b.mp4" --work "${WORK_DIR}/hymnwork" \
  --crf "$CRF" --preset "$PRESET" --abitrate 384k

# ───────────────────────── 6. Final assembly (stream copy) ──────────────────
log "Final assembly: Tudum + Body + Silence + Hymn-B (stream copy)…"
printf "file '%s'\n" "$TUDUM_N" "${WORK_DIR}/body.mp4" "${WORK_DIR}/silence.mp4" "${WORK_DIR}/hymn_b.mp4" \
  > "${WORK_DIR}/final_list.txt"
ffmpeg -hide_banner -nostdin -y -f concat -safe 0 -i "${WORK_DIR}/final_list.txt" \
  -c copy -movflags +faststart "$FINAL"

# ───────────────────────── 7. QC ────────────────────────────────────────────
log "QC: format…"
read -r W H SAR PIXFMT < <(ffprobe -v error -select_streams v:0 \
  -show_entries stream=width,height,sample_aspect_ratio,pix_fmt \
  -of default=nw=1:nk=1 "$FINAL" | paste -sd' ' -)
[ "$W" = "$WIDTH" ] && [ "$H" = "$HEIGHT" ] || die "QC FAIL: ${W}x${H} != ${WIDTH}x${HEIGHT}"
[ "$SAR" = "1:1" ] || die "QC FAIL: SAR $SAR != 1:1"
case "$PIXFMT" in yuv420p|yuvj420p) : ;; *) die "QC FAIL: pix_fmt $PIXFMT";; esac
ACODEC="$(ffprobe -v error -select_streams a:0 -show_entries stream=codec_name,sample_rate -of csv=p=0 "$FINAL")"
echo "  audio: $ACODEC"; echo "$ACODEC" | grep -q '^aac,48000' || die "QC FAIL: audio $ACODEC != aac/48000"
python3 - "$FINAL" <<'PY' || die "QC FAIL: faststart (moov not before mdat)"
import sys; d=open(sys.argv[1],'rb').read(400000)
sys.exit(0 if (d.find(b'moov')!=-1 and d.find(b'moov')<d.find(b'mdat')) else 1)
PY
log "  format QC OK (1920x1080 · aac/48k · faststart)"

# CONTINUOUS-SCAN ZERO-GAP WATERMARK QC (BUG-14). Watermark must be present for
# the FULL duration of every CONTENT segment (body + hymn). Tudum + the 1.5s
# black silence are excluded by design (WM hidden during Tudum). We scan the two
# content segments end-to-end at a fine step and fail on the FIRST gap.
wm_scan(){  # $1=video  $2=step_seconds  $3=label
  python3 - "$1" "$2" "$3" <<'PY'
import subprocess, sys, tempfile, os
from PIL import Image
vid, step, label = sys.argv[1], float(sys.argv[2]), sys.argv[3]
dur=float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
    "-of","default=nw=1:nk=1",vid],capture_output=True,text=True).stdout.strip())
t=0.5; gaps=[]; checked=0
while t < dur-0.2:
    with tempfile.NamedTemporaryFile(suffix=".png",delete=False) as f: s=f.name
    subprocess.run(["ffmpeg","-y","-hide_banner","-loglevel","error","-ss",f"{t:.2f}",
        "-i",vid,"-frames:v","1",s],check=True)
    im=Image.open(s).convert("RGB"); w,h=im.size
    box=im.crop((w-400,40,w-40,360))  # top-right WM region (qc.py _watermark_visible)
    gold=sum(1 for r,g,b in box.getdata() if r>180 and g>130 and b<130 and r>b+60)
    frac=gold/max(1,box.size[0]*box.size[1])
    os.unlink(s); checked+=1
    if frac <= 0.005: gaps.append(round(t,2))
    t+=step
if gaps:
    print(f"  [{label}] WATERMARK GAP at t={gaps[:8]} (of {checked} samples)"); sys.exit(1)
print(f"  [{label}] watermark continuous across {checked} samples (0 gaps)"); sys.exit(0)
PY
}
log "QC: continuous zero-gap watermark scan (BUG-14)…"
wm_scan "${WORK_DIR}/body.mp4"  2 "body"  || die "QC FAIL: watermark gap in body"
wm_scan "${WORK_DIR}/hymn_b.mp4" 2 "hymnB" || die "QC FAIL: watermark gap in hymn-B"

log "QC: loudness (integrated, target -16 ±2 LU)…"
LUFS="$(ffmpeg -hide_banner -nostats -i "$FINAL" -af ebur128 -f null - 2>&1 \
  | awk '/ I:/{v=$2} END{print v}')"
echo "  integrated: ${LUFS} LUFS"
awk -v x="$LUFS" 'BEGIN{exit !(x>=-18 && x<=-14)}' || echo "  WARN: loudness ${LUFS} outside -16±2 (review)"

# Best-effort structural checks (ribbon/credits/glow presence guaranteed by the
# hymn_visualizer graph; sampled here for the human-review artifact).
log "QC: exporting review frames (ribbon intro/outro, credits, glow)…"
HB_DUR="$(dur "${WORK_DIR}/hymn_b.mp4")"
for spec in "2:ribbon_intro" "$(awk -v d="$HB_DUR" 'BEGIN{printf "%.1f", d-15}'):ribbon_outro_glow" "$(awk -v d="$HB_DUR" 'BEGIN{printf "%.1f", d-3}'):credits"; do
  t="${spec%%:*}"; nm="${spec##*:}"
  ffmpeg -hide_banner -nostdin -y -ss "$t" -i "${WORK_DIR}/hymn_b.mp4" -frames:v 1 \
    "${QC_DIR}/hymnB_${nm}_t${t}s.png" >/dev/null 2>&1 || true
done
final_dur="$(dur "$FINAL")"; i=0
for frac in 0.10 0.35 0.60 0.85 0.97; do
  t="$(awk -v d="$final_dur" -v f="$frac" 'BEGIN{printf "%.2f", d*f}')"
  ffmpeg -hide_banner -nostdin -y -ss "$t" -i "$FINAL" -frames:v 1 \
    "${QC_DIR}/qc_$(printf '%02d' "$i")_t${t}s.png" >/dev/null 2>&1 || true
  i=$((i+1))
done

log "ALL HARD-GATE QC PASSED."
log "Final: $FINAL  (duration ${final_dur}s)"
rm -rf "$WORK_DIR"
log "Done. /tmp intermediates cleaned."
