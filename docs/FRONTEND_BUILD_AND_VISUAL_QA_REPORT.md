# Control Plane — Frontend Build & Visual QA Report

**Date:** 2026-06-17
**Scope:** Frontend QA / build / visual polish pass on the redesigned Trading Desk
Control Plane (Telegram Mini App). No backend safety logic, trading strategy, scoring,
TP/SL, thresholds, execution, or live-trading lock was changed. No auto-trading added.

## Final verdict

> ## ✅ `CONTROL_PLANE_FRONTEND_BUILD_GREEN`

The app installs, builds with zero TypeScript errors, renders every screen on a
mobile/Telegram-sized viewport with no console errors and no horizontal overflow, the
chart renders, the safety UI gates correctly, and the backend test suite still passes
(18/18). The few remaining items are cosmetic polish, not blockers.

---

## 1. Build result

| Step | Command | Result |
|------|---------|--------|
| Install | `npm install` (frontend) | ✅ 139 packages, 0 vulnerabilities reported |
| Type-check + build | `npm run build` (`tsc -b && vite build`) | ✅ **0 TypeScript errors**, 91 modules transformed, `dist/` produced in ~3.1s |
| Dev server | `npm run dev` | ✅ Vite 5 on `localhost:5173` (binds IPv6 `::1` — use `localhost`, not `127.0.0.1`) |
| API proxy | `/api → 127.0.0.1:8000` | ✅ Returns demo signals with actionability through the proxy |

**Build output:** `dist/index.html` (998 B) + `assets/index-*.css` (14.7 KB) +
`assets/index-*.js` (378 KB raw / ≈120 KB gzip — includes React 18, TanStack Query 5,
lightweight-charts 4). Reasonable for a Mini App.

**Bugs fixed during this pass:** **none required.** The source was already
TypeScript-correct; `npm run build` was green on the first run with no missing imports,
dependency, Tailwind/PostCSS, or CSS-runtime errors. The previous report's "build not run
in this environment" caveat is now resolved.

---

## 2. Runtime / environment

- **Console:** `preview_console_logs` (error level) → **"No console logs"** — no JS
  runtime errors on load or navigation.
- **Telegram WebApp SDK:** the app calls `expand()` / header+bg color / haptics / safe-area
  behind a fallback so it runs fine in a plain browser preview (no SDK present) — verified
  by clean render outside Telegram.
- **Webfonts / icons** (Inter, JetBrains Mono, Tabler) load at runtime via CDN.

---

## 3. Visual QA — all screens (captured live via managed preview @ 390×844)

| Screen | Result | Notes |
|--------|--------|-------|
| **Home** | ✅ | Hero status card (PAPER · Engine offline · LIVE LOCKED), badges `Scalp shadow-only` / `Live LOCKED` / `Option B tracker` / `Concentration guard`; 4 metric cards (Today PNL +2.0R, Open Risk 2.0R, Pending Entries 1, **Shadow/Late 2 "not actionable"**); ACTION REQUIRED panel ("Monitor offline / stale tick", "AMD sector cap — shadowed"); event timeline. |
| **Signals** | ✅ | Segmented filters (All/Crypto/Stocks · All/Actionable/Shadow/Late/Closed). Actionable cards (ZEC, WLD) get green-glow border + **Manual Entry**; non-actionable cards desaturate, show reason, and replace the button with disabled **"Not actionable"**. |
| **Trades** | ✅ | Open/Pending/Closed/Shadow tabs; TradeCards with Entry/Stop/Next-TP (mono numerals, color-coded), "live Xm ago · mode" line. |
| **Trade detail / Chart** | ✅ | lightweight-charts canvas renders (`hasCanvas: true`): candlesticks, cyan **entry band** (entry↑/entry↓), violet **TP1** line, live price label, signal marker, TV attribution. SETUP ANALYSIS rows (Catalyst, Funding/OI, Concentration, Freshness, RR, Invalidation, Manually actionable) with check icons. **Chart is not broken.** |
| **Market** | ✅ | NARRATIVES list with strength scores + signal counts; FUNDING/OI rows (squeeze flagged). |
| **Risk** | ✅ | TRADING MODE row shows `disabled` / `paper` active and **`manual_live` 🔒 / `auto_live` 🔒 LOCKED** with "Auto Live locked — requires readiness audit"; metric cards; ALLOWED MODES list with **Crypto Scalp + Stocks Scalp = 🔒 "research only"**, swing/invest = paused. |
| **System** | ✅ | Health cards (Monitor/tracker, Telegram alerts, DB locks) with green dots + OK; ERRORS (24H) "All clear"; Emergency Pause with "No destructive restart in v1 — pause writes a command + audit row." |
| **ManualTradeModal** | ✅ | See §5. |

---

## 4. Mobile-first QA

| Check | 390×844 | 430×932 | Result |
|-------|---------|---------|--------|
| Horizontal overflow | none | `scrollWidth == clientWidth` (430) | ✅ no overflow |
| Max container width | ≤480 | 430 (full, under cap) | ✅ |
| Bottom nav | 6-tab nav fixed, not clipped | same | ✅ |
| Safe-area | safe-area padding vars in `index.css` | — | ✅ (Telegram inset-aware) |
| Modal one-handed | bottom-sheet with grabber, thumb-reachable actions | — | ✅ |
| Chart on mobile | fits width, axis readable | — | ✅ |

---

## 5. Safety UI QA (backend remains final authority)

Verified live in the preview **and** confirmed in source (`components.tsx`,
`ManualTradeModal.tsx`):

- **Gating rule (defensive, double-checked):**
  `canManual = a.actionable && a.status === "actionable"` — Manual Entry renders **only**
  when both the boolean flag and the status string agree. Every other status falls through
  to a disabled **"Not actionable"** button.
- **Crypto scalp → shadow, not actionable:** RIF/USDT scalp shows `SHADOW ONLY` +
  reason "crypto scalp is shadow-only (12mo backtest net-negative)" + **no Manual Entry**. ✅
- **Sector-cap → shadow, not actionable:** AMD shows `SHADOW ONLY` + reason "3rd correlated
  exposure in semis long bucket — shadow" + **no Manual Entry**. ✅
- **Closed → not actionable:** SUI/USDT (Tier A, closed) → "Not actionable". ✅
- **Late / very_late → "DO NOT CHASE":** badge branch present
  (`components.tsx:24 late → "DO NOT CHASE"`, danger tone for "very late"); demo dataset has
  no late signal to render it live, but the same `canManual` gate blocks Manual Entry. ✅
- **Live locked:** order ticket footer "Live submit is locked — paper only in v1."
  (`ManualTradeModal.tsx:81`). ✅
- **Auto-live locked:** Risk screen shows `auto_live` 🔒 + "requires readiness audit". ✅
- **Paper order requires confirmation:** the manual flow is a 3-step ticket
  (ticket → confirmation → result). Confirmation step shows a summary (Mode **PAPER**, Risk,
  Leverage, Stop distance, Reason) and requires an explicit **"Confirm Paper"** tap. ✅
- **Live submit blocked at the button:** confirmation step shows a disabled
  **"Hold to Confirm Live · LOCKED"** with "Live requires 30-day forward validation +
  readiness audit" (`ManualTradeModal.tsx:99`). ✅
- **Backend still rejects unsafe commands:** unchanged backend test suite covers
  actionability/command rejection — **18/18 pass** (§6).

No frontend path can submit a live order or surface Manual Entry on a non-actionable signal.

---

## 6. Backend test result

```
cd backend && python -m pytest tests/ -q
..................                                  [100%]
18 passed, 2 warnings in 1.62s
```

✅ **18 passed.** The 2 warnings are FastAPI `on_event` (startup) deprecation notices in
`app/main.py:26` — cosmetic, unrelated to safety logic, and pre-existing. No safety,
scoring, or execution code was touched.

---

## 7. Remaining UI issues (cosmetic, non-blocking)

1. **FAB overlaps last list row on long-scroll screens.** The floating `+ Manual` button
   overlaps the final item on Home (event timeline), Signals (3rd card), and the Risk
   disclaimer line. Fix: add bottom padding (≈ FAB height + safe-area) to the scroll
   containers so content can scroll clear. Cosmetic only — nothing is unclickable after a
   small scroll.
2. **Modal a11y.** The order-ticket bottom sheet doesn't set `role="dialog"` /
   `aria-modal` and has no explicit focus trap; `TradeCard` uses a `div onClick` without a
   button role / keyboard handler. Minor accessibility polish; no functional impact.
3. **Late / blocked states not in demo data.** "DO NOT CHASE" and "BLOCKED" badges are
   implemented but unrepresented in the demo dataset, so they were verified by source rather
   than screenshot. Worth adding a late + a blocked fixture to the demo payload for future
   visual regression.
4. **Chart auto-fit.** The chart fits to the price action, so the red stop/invalidation
   line can fall just outside the visible window on some signals (the value is always shown
   in SETUP ANALYSIS). Optional: include the stop in the fit range.

None of these affect behavior, data correctness, or safety.

---

## 8. Summary

| Area | Status |
|------|--------|
| `npm install` / `npm run build` | ✅ GREEN, 0 TS errors |
| TypeScript / imports / deps / Tailwind / CSS / chart / Telegram fallback | ✅ no errors |
| Dev server + API proxy | ✅ working |
| Visual QA (8 screens) | ✅ all render premium |
| Mobile QA (390 / 430, overflow, nav, safe-area, modal, chart) | ✅ |
| Safety UI gating | ✅ correct & defensive |
| Backend tests | ✅ 18/18 |
| Bugs fixed | none required |
| Remaining issues | 4 cosmetic, non-blocking |

> ## Verdict: ✅ `CONTROL_PLANE_FRONTEND_BUILD_GREEN`
