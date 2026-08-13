# CrossAIHub — Cloud Render (GitHub Actions)

Runs the **locked** CrossAIHub render pipeline (episode + hymn) in the cloud on a
free GitHub Actions runner, so heavy video renders stay **off the Mac**. Triggered
on demand from the **GitHub mobile app**.

## What it does
1. Spins up a free Linux runner (public repo → 4 vCPU / 16 GB RAM, unlimited minutes).
2. Installs `ffmpeg` + `rclone`.
3. Pulls **only** the assets it needs (shared brand + this episode) from Google Drive.
4. (Optional) Generates narration with OpenAI TTS.
5. Runs `scripts/render_episode.sh` — the same locked logic: libx264 crf 24, uniform
   normalize 1920×1080 / SAR 1:1 / 30 fps / yuv420p / full-range bt709, watermark on
   **body + hymn**, crossfades at every seam, no infinite-loop watermark input, disk
   gate, /tmp intermediates, `+faststart` output, plus a **continuous-watermark QC**.
6. Uploads the final mp4 + QC sample frames as a downloadable **artifact** and
   (optionally) pushes them back to Google Drive.

## Trigger a render (from mobile)
GitHub app → your repo → **Actions** → **"CrossAIHub — Cloud Render"** →
**Run workflow** → enter `pair` and `psalm` → **Run**.
Download the result from the run's **Artifacts** (or from Drive if `push_to_drive` is on).

## Required repo secrets
- `RCLONE_CONF` — the full contents of an `rclone.conf` for your Google Drive.
- `OPENAI_API_KEY` — only if you use cloud TTS (`generate_tts = true`).

## Optional repo variables (Settings → Variables)
- `DRIVE_REMOTE` (default `gdrive`), `DRIVE_ROOT` (default `crossaihub_assets`),
  `DRIVE_OUT_DIR` (default `crossaihub_renders`).

## Google Drive layout expected
```
crossaihub_assets/
  brand/            watermark.png, tudum.mp4, v4e_ribbon.mp4, credits.mp4
  episodes/
    pair07/         narration.mp3 (or narration_script.txt), psalm23.mp3,
                    body_segments.txt, hymn_segments.txt, + the chosen b-roll clips
```
`body_segments.txt` / `hymn_segments.txt` = one clip filename per line, in play order.

## Files
- `.github/workflows/render-episode.yml` — the workflow (workflow_dispatch).
- `scripts/render_episode.sh` — Linux port of the locked ffmpeg pipeline + QC.
- `scripts/generate_tts.py` — optional OpenAI TTS.
- `examples/pair07/*` — example segment lists / script (safe to delete).
- `rclone.conf.example` — how to build the `RCLONE_CONF` secret.

> This repo intentionally contains **no assets and no secrets**. Big/private media
> lives in Google Drive and is pulled at runtime. Keep the repo **public** for free
> unlimited 4-vCPU minutes — nothing sensitive is committed.
