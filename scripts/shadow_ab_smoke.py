"""PART 6 — Playwright smoke: A/B panel visible, trade detail opens, fee card + maker visible,
no console errors, no horizontal overflow. Read-only; no live."""
from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = (Path(os.environ["LOCALAPPDATA"]) / "ms-playwright" / "chromium-1208"
          / "chrome-win64" / "chrome.exe")
URL = "http://127.0.0.1:8010"

errors: list[str] = []
res: dict[str, object] = {}

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=str(CHROME), headless=True, args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 420, "height": 880})
    pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL, wait_until="networkidle", timeout=30000)
    pg.click('button[aria-label="System"]'); pg.wait_for_timeout(1500)

    res["panel_visible"] = pg.locator('[data-testid="shadow-ab"]').count() > 0
    res["fee_card_visible"] = pg.locator('[data-testid="shadow-fees"]').count() > 0
    res["maker_visible"] = pg.locator('[data-testid="shadow-maker"]').count() > 0
    res["trades_visible"] = pg.locator('[data-testid="shadow-trades"]').count() > 0

    rows = pg.locator('[data-testid="shadow-trades"] .glass-soft button')
    if rows.count() > 0:
        before = pg.locator('[data-testid="shadow-trades"] .grid').count()
        rows.first.click(); pg.wait_for_timeout(700)
        after = pg.locator('[data-testid="shadow-trades"] .grid').count()
        res["trade_detail_opens"] = after > before
    else:
        res["trade_detail_opens"] = False

    # horizontal overflow across tabs
    overflow = {}
    for tab in ("Home", "Signals", "Trades", "Market", "Risk", "System"):
        pg.click(f'button[aria-label="{tab}"]'); pg.wait_for_timeout(900)
        ow = pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
        overflow[tab] = ow
    res["max_horizontal_overflow_px"] = max(overflow.values())
    res["overflow_by_tab"] = overflow
    b.close()

res["console_errors"] = errors
print("SMOKE:", res)
ok = (res["panel_visible"] and res["fee_card_visible"] and res["maker_visible"]
      and res["trade_detail_opens"] and not errors and res["max_horizontal_overflow_px"] <= 2)
print("RESULT:", "PASS" if ok else "FAIL")
