#!/usr/bin/env python3
"""Cloud copy of the WS-41 live-site screenshot job: public pages only, full-page PNGs (day / lamp / grandparent mode) at 1440 and 390 px.
Pages come from IN/pages.json if the job bundle has one, else the default list. Output → OUT."""
import json, os, sys
from playwright.sync_api import sync_playwright
out = os.environ["OUT"]; IN = os.environ.get("IN", ""); base = "https://www.crossaihub.com"
pages = json.load(open(os.path.join(IN, "pages.json"))) if IN and os.path.exists(os.path.join(IN, "pages.json")) else ["/", "/free/", "/advent/", "/pray/", "/free/verse-cards/", "/christmas-gift/"]
modes = [("day", "off", "off"), ("lamp", "on", "off"), ("gm", "off", "on")]; err = 0
with sync_playwright() as p:
    b = p.chromium.launch()
    for w in (1440, 390):
        for path in pages:
            for name, lamp, gm in modes:
                if w == 1440 and name == "gm": continue
                pg = b.new_page(viewport={"width": w, "height": 900}, reduced_motion="reduce")
                pg.add_init_script(f"try{{localStorage.setItem('cah_lamp','{lamp}');localStorage.setItem('cah_gm','{gm}')}}catch(e){{}}")
                try:
                    pg.goto(base + path, wait_until="networkidle", timeout=45000); pg.wait_for_timeout(800)
                    slug = path.strip("/").replace("/", "_") or "home"; pg.screenshot(path=f"{out}/{slug}_{w}_{name}.png", full_page=True)
                except Exception as e: print("ERR", path, w, name, type(e).__name__); err += 1
                pg.close()
    b.close()
print(f"site shots: {len(os.listdir(out))} files, {err} errors")
