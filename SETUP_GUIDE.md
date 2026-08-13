# CrossAIHub — Free Cloud Render on GitHub Actions — v1.0

**Purpose:** Move heavy video renders OFF the Founder's slow 2-core fanless MacBook Air
and into a free cloud runner, running the *same* locked CrossAIHub pipeline, triggered
on demand from mobile.

**Status:** Design + working scaffold. No repo was pushed, no account created, no
production render run. Everything is prepared and ready to drop in.

---

## الخلاصة بالعربي (اقرأي هذا أولاً)

- **فيها؟ نعم — مجاني بالكامل.** GitHub Actions بيشغّل الرندر على سيرفر Linux ببلاش.
  إذا الريبو **عام (public)** بتصير الدقائق **غير محدودة** والسيرفر **4 أنوية / 16 غيغا** —
  يعني أقوى من ماك الفاوندر وبدون أي تكلفة. إذا الريبو **خاص (private)** عندك **2000 دقيقة
  بالشهر مجاناً** على سيرفر 2 نواة.
- **الوقت المتوقع لرندر حلقة ~22 دقيقة:** حوالي **20 لـ 40 دقيقة** على السيرفر العام،
  وكلها **بعيدة عن الماك** — الماك بيضل فاضي.
- **أصعب مشكلة = توصيل المكتبة الكبيرة (b-roll).** الحل الموصى فيه: **نخلّي الأصول بغوغل
  درايف (زي ما هي عادتك) ونسحب وقت الرندر بس اللي نحتاجه عبر rclone** — أرخص وأسهل طريقة.
- **جاهز:** في ملف workflow شغّال + سكربت رندر Linux بيطبّق نفس المعايير المقفولة
  (libx264، توحيد 1920×1080، ووترمارك على الـ body والـ hymn، crossfades، faststart،
  فحص جودة للووترمارك). كله مكتوب وجاهز.
- **المطلوب منك (مرة وحدة بس):** إنشاء ريبو على GitHub + تثبيت تطبيق GitHub على الموبايل +
  إضافة سرّين (توكن درايف، ومفتاح TTS إذا بدك الصوت من السحابة). التفاصيل تحت.

---

## 1) Feasibility — is it free, and how fast?

**Yes — genuinely free**, with honest limits.

GitHub Actions free tier (verified Aug 2026):

- **Public repository:** unlimited Actions minutes, and the standard Linux runner was
  upgraded to **4 vCPU / 16 GB RAM / 14 GB SSD**. Best option for us.
- **Private repository:** **2,000 free Linux minutes/month** + 500 MB free artifact
  storage; standard runner **2 vCPU / ~7–8 GB RAM / 14 GB SSD**.
- Linux minutes count 1×. (Windows 2×, macOS 10× — we use Linux only, so those don't apply.)
- Jan 1 2026 price cut lowered *paid* overage rates; **free quotas unchanged**.
- A brief Dec 2025 proposal to charge for self-hosted runners on private repos was
  **withdrawn** — not in effect.

> Note: the original assumption of "2-core / 7 GB" is now the **private-repo** spec.
> On a **public** repo you get **double** that (4 vCPU / 16 GB) for free — so this is
> even better than expected.

**Realistic render time for a ~22-min 1080p libx264 episode:**

| Stage | Public runner (4 vCPU) | Private runner (2 vCPU) |
|---|---|---|
| ffmpeg/rclone install | ~0.5–1 min | ~0.5–1 min |
| Pull assets from Drive (few hundred MB) | ~1–5 min | ~1–5 min |
| Normalize clips + watermark | ~2–5 min | ~4–9 min |
| Crossfade compositing + final encode (crf 24, preset medium) | ~10–20 min | ~20–40 min |
| QC + artifact upload | ~1–3 min | ~1–3 min |
| **End-to-end** | **~20–40 min** | **~35–70 min** |

(Prose, since tables aren't your preference — the numbers above are the honest estimate.)

The Founder's fanless 2-core Mac throttles under sustained encode and is often near or
below real-time for a multi-pass job like this; the cloud runner has no thermal throttle
and finishes far faster **while the Mac stays completely free**. On a private repo at
~35–70 min/render, the 2,000 free minutes still cover roughly **30–50 renders/month**.

**Honest limits**

- **14 GB workspace disk.** The full multi-GB b-roll library will NOT fit if pulled
  wholesale. We pull **only the episode + brand assets** (a few hundred MB) and clean
  `/tmp`. If a single episode's inputs ever get large, point `WORK_DIR` to the runner's
  larger ephemeral mount (`/mnt`, ~65 GB).
- **Artifact storage** on private repos is 500 MB free; we set 14-day retention and can
  push finished files to Drive instead.
- **Public repo = code is visible.** That's fine here: **no assets and no secrets are in
  the repo** (media stays in Drive; keys are encrypted GitHub Secrets, which are not
  exposed to fork pull requests, and only you can dispatch the workflow).
- **rclone token** needs a one-time creation (the single most technical step — details in §5).
- **Fidelity caveat:** this scaffold ports the locked standard faithfully (flags below),
  but the literal `BUILD_EPISODE_HARDENED.command` was not readable in this setup session.
  **Before the first production render, diff `scripts/render_episode.sh` against
  `CROSSAIHUB_VIDEO_PRODUCTION_PIPELINE_LAW.md`** to confirm the ffmpeg flags match 1:1.

---

## 2) The hard problem — asset delivery (recommended: rclone from Google Drive)

The b-roll library is multi-GB and cannot live in a normal git repo. Options considered:

- **(a) git-LFS — rejected.** Free tier is only **1 GB storage + 1 GB bandwidth/month**.
  A multi-GB library plus a fresh pull on every run blows past this immediately and starts
  costing money. Wrong tool for large media that changes.
- **(b) GitHub Release / artifact bundle — good fallback, medium friction.** Store a
  compressed asset bundle as a Release asset (no LFS cost, ~2 GB/file). Downside: you must
  build and **re-upload the whole bundle every time the library changes**, and each run
  downloads the full bundle. Awkward to maintain from mobile.
- **(c) rclone pull from Google Drive at runtime — ✅ RECOMMENDED.** The brand already
  uses Drive as primary storage. Store an `rclone.conf` (with the Drive token) as a GitHub
  secret; the workflow pulls **only** the shared brand folder + the specific episode folder
  at runtime. **Lowest friction:** the Founder just drops files into Drive from the phone;
  nothing to bundle, nothing big in git, fully free. One-time cost: create the rclone token.
- **(d) Push only small per-episode inputs — rejected as primary.** Lowest tech, but it
  forces the Mac to pre-select and normalize clips and git-push each episode — that defeats
  "off the Mac" and is painful from mobile. Keep only as an emergency fallback.

**Recommendation: (c) rclone from Drive, with the repo kept PUBLIC** for free unlimited
4-vCPU minutes. Fallback if the token setup ever breaks: (b) Release bundle.

Expected Drive layout:

```
crossaihub_assets/
  brand/            watermark.png  tudum.mp4  v4e_ribbon.mp4  credits.mp4
  episodes/
    pair07/         narration.mp3 (or narration_script.txt)  psalm23.mp3
                    body_segments.txt  hymn_segments.txt  + chosen b-roll clips
```

---

## 3) The scaffold (what's already written)

Repo folder `crossaihub-cloud-render/`:

- `.github/workflows/render-episode.yml` — the workflow. `workflow_dispatch` inputs:
  `pair`, `psalm`, `generate_tts`, `crf`, `push_to_drive`. Installs ffmpeg + rclone,
  writes rclone.conf from the `RCLONE_CONF` secret, pulls only the needed assets,
  optionally runs TTS, runs the render, uploads the mp4 + QC frames as an artifact, and
  optionally pushes results back to Drive.
- `scripts/render_episode.sh` — **Linux port of the locked pipeline**. Enforces:
  - libx264, `crf 24` (locked window 23–26), preset medium;
  - uniform normalize **1920×1080 / SAR 1:1 / 30 fps / yuv420p / full-range bt709**;
  - **watermark burned on BODY and HYMN** (bottom-right), using a **static image overlay
    on a finite base — no `-loop`, no infinite watermark input**;
  - **crossfades (xfade + acrossfade) at every seam**: tudum → v4e ribbon → body → hymn → credits;
  - **disk gate** before any encode; **/tmp intermediates**, cleaned at the end;
  - final output `+faststart`, bt709 tags, yuv420p;
  - **QC:** format asserts (resolution/SAR/pix_fmt/faststart) **+ continuous-watermark
    check** (samples frames across body & hymn, crops the watermark region, and fails the
    run if the logo is missing on any sample) + exports QC sample PNGs.
- `scripts/generate_tts.py` — optional OpenAI TTS (reads `narration_script.txt` → `narration.mp3`).
- `examples/pair07/{body_segments.txt,hymn_segments.txt,narration_script.txt}` —
  example inputs (safe to delete/replace; real ones live in Drive).
- `rclone.conf.example`, `.gitignore`, `README.md`.

The render is triggered on demand; the scaffold does **not** run a production render.

---

## 4) Secrets + trigger plan

**GitHub repository secrets** (Settings → Secrets and variables → Actions):

- `RCLONE_CONF` **(required)** — the full text of your Google Drive `rclone.conf`.
- `OPENAI_API_KEY` **(required only for cloud TTS)** — used when `generate_tts = true`.

**Optional repository variables:** `DRIVE_REMOTE` (default `gdrive`),
`DRIVE_ROOT` (default `crossaihub_assets`), `DRIVE_OUT_DIR` (default `crossaihub_renders`).

**How the Founder triggers a render from mobile:**
Open the GitHub app → the repo → **Actions** → **"CrossAIHub — Cloud Render"** →
**Run workflow** → type `pair` (e.g. `07`) and `psalm` (e.g. `23`), leave the rest default →
**Run**. When it finishes, download the mp4 from the run's **Artifacts** (or from the Drive
`crossaihub_renders/` folder if `push_to_drive` stayed on).

**TTS — where should it run?**

- **Recommended default: TTS in the cloud** (`generate_tts = true`). It's a lightweight API
  call, not heavy compute, and it keeps the whole job one-tap from mobile with **zero Mac
  involvement**. Put the narration *text* in Drive; the runner makes `narration.mp3`.
- **Alternative: TTS on the Mac** (cheap) when you want to *listen to and approve* the
  narration before the video is built — then drop the finished `narration.mp3` into Drive and
  leave `generate_tts = false`. The heavy video render still offloads to the cloud.

Use cloud TTS for speed and zero-Mac; switch to Mac-TTS only for episodes where you want to
vet the voice first.

---

## 5) What's needed from the Founder (minimal, one-time)

Almost all of this is mobile. The only genuinely technical one-time step is creating the
Drive token (§ step 4).

1. **GitHub account + app** — create a free GitHub account if you don't have one, install the
   **GitHub mobile app**, and log in. (mobile)
2. **Create a repo** — new **public** repository named e.g. `crossaihub-cloud-render`. (mobile or web)
3. **Add the scaffold files to the repo** — two ways:
   - *Fully mobile:* on github.com use **Add file → Upload files** and upload the scaffold
     contents (keep the `.github/workflows/` path). A few uploads, but no Mac needed.
   - *Fastest:* a single short desktop moment — unzip the delivered folder and `git push` it
     once. (This is optional and can be the one Mac approval.)
4. **Create the Drive token (`RCLONE_CONF`)** — the one technical step. On any machine run
   `rclone config` → new remote named `gdrive` → type `drive` → complete the Google sign-in →
   copy the **entire** resulting `rclone.conf` text. (I can also do this *for* you in a later
   session via the browser tools — no Mac required — just ask.)
5. **Add secrets** — repo **Settings → Secrets and variables → Actions → New repository
   secret**: paste `RCLONE_CONF`; add `OPENAI_API_KEY` only if you want cloud TTS. (mobile browser)
6. **Put assets in Drive** — arrange them under the layout in §2. Going forward you only ever
   drop files into Drive from your phone. (mobile)
7. **Run it** — Actions → Run workflow → enter pair + psalm → Run. (mobile)

That's it. After the one-time setup, every future render is: drop files in Drive → tap Run.

---

## 6) File paths

Delivered in this session (Claude's working/output folder, and copied where you can open them):

- `crossaihub-cloud-render/` — the full ready-to-use repo scaffold
  - `.github/workflows/render-episode.yml`
  - `scripts/render_episode.sh`
  - `scripts/generate_tts.py`
  - `examples/pair07/…` (examples)
  - `README.md`, `rclone.conf.example`, `.gitignore`
- `CROSSAIHUB_GITHUB_ACTIONS_CLOUD_RENDER_v1.0.md` — this document.

Intended permanent homes (drop the same files here):

- `~/Documents/CrossAIHub/_production_law/CROSSAIHUB_GITHUB_ACTIONS_CLOUD_RENDER_v1.0.md`
- `~/Documents/CrossAIHub/_production_law/crossaihub-cloud-render/` (the scaffold)
- A copy of this doc on the **Desktop** for easy attachment.

---

*v1.0 — design + scaffold only. No push, no account, no production render performed.*
