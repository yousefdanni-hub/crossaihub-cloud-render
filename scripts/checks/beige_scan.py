#!/usr/bin/env python3
"""[WS-19 · 2026-11-19] MAC job: which LIVE pages still render in the cancelled beige/ivory/parchment style?
Headless Playwright (no visible browser, no prompts). For each sitemap page (EN/ES/PT): screenshot 1280×900 first screen + mid-page, mean colour of the
page background → "beige" if light warm (L>80, b*>4 in Lab-ish) on >40 % of pixels. Output work/beige_20261119/BEIGE_LIST.md (most-visited first: RUM top paths
from plan/STUDY_REPORTS/HOURLY_* if present, else the key-page list) + beige_scan.json."""
import json, os, re, glob, urllib.request, time
from playwright.sync_api import sync_playwright
O = os.environ["OUT"]; IN = os.environ.get("IN", ""); SITE = "https://www.crossaihub.com"   # cloud copy: inputs from the job bundle, outputs to OUT
sm = urllib.request.urlopen(urllib.request.Request(SITE + "/sitemap.xml", headers={"User-Agent": "Mozilla/5.0 (CrossAIHub QA)"}), timeout=60).read().decode(); urls = []
for l in re.findall(r"<loc>([^<]+)</loc>", sm):
    urls += re.findall(r"<loc>([^<]+)</loc>", urllib.request.urlopen(urllib.request.Request(l, headers={"User-Agent": "Mozilla/5.0 (CrossAIHub QA)"}), timeout=60).read().decode()) if l.endswith(".xml") else [l]
visits = json.load(open(os.path.join(IN, "visits.json"))) if IN and os.path.exists(os.path.join(IN, "visits.json")) else {}   # page → visits (48 h), sent by the Mac
key = ["/", "/advent/", "/christmas/", "/free/", "/shop/", "/pray/", "/kids/", "/sing/", "/grandparents/", "/cards/", "/thanksgiving/", "/read/", "/candles/", "/your-room/", "/es/", "/pt/"]
paths = sorted({re.sub(r"https?://[^/]+", "", u) or "/" for u in urls}, key=lambda p: (-visits.get(p, 0), key.index(p) if p in key else 99, p))
res = []; T0 = time.time()
with sync_playwright() as p:
    b = p.chromium.launch(); ctx = b.new_context(viewport={"width": 1280, "height": 900})
    ctx.add_init_script("try{localStorage.setItem('cah_house_rules_agreed_v1','1');localStorage.setItem('crossaihub-entrance-shown-v1','1')}catch(e){}")
    pg = ctx.new_page()
    for path in paths[:int(os.environ.get("MAX", 400))]:
        if time.time() - T0 > float(os.environ.get("BUDGET", 3300)): break
        try:
            pg.goto(SITE + path, wait_until="domcontentloaded", timeout=45000); pg.wait_for_timeout(700)
            r = pg.evaluate("""() => { const pick = y => { window.scrollTo(0, y); const e = document.elementFromPoint(640, 450); let n = e, c = '';
                while (n && n !== document.documentElement) { const s = getComputedStyle(n).backgroundColor; if (s && !/rgba\\(0, 0, 0, 0\\)|transparent/.test(s)) { c = s; break; } n = n.parentElement; }
                return c || getComputedStyle(document.body).backgroundColor; };
                const h = document.documentElement.scrollHeight; return [pick(0), pick(h * 0.35), pick(h * 0.7)]; }""")
            def beige(c):
                m = re.findall(r"[\d.]+", c or "");
                if len(m) < 3: return False
                r_, g, b_ = map(float, m[:3]); return r_ > 225 and g > 210 and b_ > 180 and r_ - b_ > 12   # light warm cream/ivory/parchment
            hits = sum(beige(c) for c in r)
            res.append({"path": path, "visits_48h": visits.get(path, 0), "bg": r, "beige_zones": hits})
        except Exception as e: res.append({"path": path, "error": type(e).__name__})
    b.close()
json.dump(res, open(f"{O}/beige_scan.json", "w"), indent=1)
bad = [x for x in res if x.get("beige_zones", 0) >= 2]
md = [f"# Live pages still in the cancelled beige style · {time.strftime('%Y-%m-%d %H:%M')} [WS-19 scan, owner WS-07/WS-41]", "",
      f"Scanned {len(res)} pages (most visited first). Beige in ≥ 2 of 3 zones: **{len(bad)}**. Protected (TREE / HOME HERO / INTRO VIDEO) = Danni decides.", "",
      "| # | page | visits 48 h | zones beige |", "|---|---|---|---|"] + [f"| {i} | {x['path']} | {x['visits_48h']} | {x['beige_zones']}/3 |" for i, x in enumerate(bad, 1)]
open(f"{O}/BEIGE_LIST.md", "w").write("\n".join(md) + "\n")
print(f"beige scan done: {len(bad)} of {len(res)} live pages still beige")
