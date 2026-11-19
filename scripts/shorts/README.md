# Cloud Shorts render
`story_short.py` + `film.py` = the CrossAIHub Shorts engine (template v2.6), copied verbatim from the Mac.
Workflow: `.github/workflows/render-short.yml` (manual/API dispatch). The job bundle (spec + its own media) comes from our R2 tmp bucket;
the finished mp4 is a 3-day artifact the Mac downloads before uploading to YouTube. No secrets in this repo.
Media rules: only our own or public-domain media; no private/family data; no JESUS 33 assets.
