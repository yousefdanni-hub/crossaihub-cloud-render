# CrossAIHub Cloud Render — Asset Contract (reconciled to _pipeline_v4/config.py)

The workflow pulls exactly two Drive trees: `crossaihub_assets/brand` (shared) and
`crossaihub_assets/episodes/pair{NN}` (per episode). Filenames below are what the
reconciled `render_episode.sh` + `render_hymn_section.py` consume.

## `brand/` — shared, staged once
- `watermark.png` — **must hash to SHA256 `fa499139…`** (config.py `WATERMARK`); the script hard-fails otherwise.
- `tudum.mp4` — config.py `TUDUM_SRC` (`visual/tudum/tudum_1080.mp4`).
- `S3_Theme.mp3` — config.py `S3_THEME`; the episode-body music bed.
- `_locked_overlays/hymn_{NN}.png` — per-pair hymn ribbon (config.py `ribbon_hymn_png`); e.g. `hymn_04.png`.
- `_locked_overlays/credits_overlay.png` — config.py `CREDITS_PNG`.
- `_locked_overlays/cross_living_glow_v1.png` — pre-baked cross resurrection glow (`CROSS_LIVING_GLOW_SPEC` cache). Provided baked so the runner needs no Pillow/numpy to bake it.

## `episodes/pair{NN}/` — per episode
- `narration.<ext>` — the CP-approved paced narration master (e.g. `narration.flac`). Already carries the locked Version-B voice chain; the render adds only the S3 bed + sidechain + final loudnorm.
- `take_B.mp3` — Hymn Take B (Suno). **Upstream gap for pair_04** (not made yet).
- `cover.<ext>` — hymn cover image (`cover.jpeg`). **Upstream gap for pair_04**.
- `body_segments.txt` — ordered nature b-roll filenames, one per line (`#` comments ok). **Upstream gap for pair_04** (Pexels use-once, ~22 clips).
- the b-roll clip files referenced by `body_segments.txt` (raw or normalized). **Upstream gap**.

## Output (pushed to `crossaihub_renders/pair{NN}_psalm{PP}/`)
- `CrossAIHub_EP_pair{NN}_psalm{PP}.mp4` + `qc/*.png` review frames.

## Structure produced (assemble.py default · PRODUCTION LAW v1.0)
`Tudum → EpisodeBody(watermark + narration+bed) → Silence 1.5s → Hymn-B(cross-glow + ribbon 5s/30s + credits 30s fade)`.
Intro card OFF, outro tudum OFF by default (credits scroll is the only ending).
