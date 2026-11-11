"""PART 4 — real Playwright screenshots of the Mini App (preview tool was flaky).
Points headless chromium (cached ms-playwright build) at the production backend on :8010,
which serves the built dist with AUTH_DISABLED + real data. Read-only; no live, no orders.
"""
from __future__ import annotations

import os
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = (Path(os.environ["LOCALAPPDATA"]) / "ms-playwright" / "chromium-1208"
          / "chrome-win64" / "chrome.exe")
URL = "http://127.0.0.1:8010"
OUT = Path(__file__).resolve().parents[1] / "reports" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

done: list[str] = []


def shot(page, name: str) -> None:
    page.screenshot(path=str(OUT / name), full_page=True)
    done.append(name)


def el_shot(page, testid: str, name: str) -> bool:
    loc = page.locator(f'[data-testid="{testid}"]')
    if loc.count() == 0:
        return False
    loc.first.scroll_into_view_if_needed()
    loc.first.screenshot(path=str(OUT / name))
    done.append(name)
    return True


def tab(page, label: str) -> None:
    page.click(f'button[aria-label="{label}"]')
    page.wait_for_timeout(1200)


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=str(CHROME), headless=True, args=["--no-sandbox"])
    pg = b.new_page(viewport={"width": 420, "height": 880})
    pg.goto(URL, wait_until="networkidle", timeout=30000)
    pg.wait_for_timeout(1500)

    # System tab — Paper Shadow A/B panel + gate + maker + fees + per-trade
    tab(pg, "System")
    pg.wait_for_selector('[data-testid="shadow-ab"]', timeout=15000)
    pg.wait_for_timeout(1500)
    el_shot(pg, "shadow-ab", "final_shadow_ab_panel.png")
    el_shot(pg, "shadow-maker", "final_maker_realism.png")
    el_shot(pg, "shadow-fees", "final_fee_card.png")

    # open the first per-trade row -> A/B detail
    rows = pg.locator('[data-testid="shadow-trades"] .glass-soft button')
    if rows.count() > 0:
        rows.first.click()
        pg.wait_for_timeout(900)
        el_shot(pg, "shadow-trades", "final_trade_ab_detail.png")

    # System build-id (full page top)
    pg.evaluate("window.scrollTo(0,0)")
    pg.wait_for_timeout(400)
    shot(pg, "final_system_build_id.png")

    # Risk tab
    tab(pg, "Risk")
    shot(pg, "final_risk_tab.png")

    # Market tab (crypto/stocks risk dedup)
    tab(pg, "Market")
    shot(pg, "final_market_dedup.png")

    b.close()

print("SAVED:", ", ".join(done) if done else "NONE")
