# Control Plane — Frontend Polish & Accessibility QA Report

**Date:** 2026-06-17
**Scope:** Small frontend polish / accessibility / visual-regression pass on top of the
green build. No backend safety logic, trading strategy, scoring, TP/SL, thresholds,
execution, or live-trading lock was changed. No auto-trading added. The only backend
edit is **display-only demo fixtures** (offline mock data), explicitly requested.

## Final verdict

> ## ✅ `CONTROL_PLANE_UI_POLISH_READY`

Build green (0 TS errors), all polish items implemented and verified live on
390/430px viewports, backend tests still 18/18, live/auto-live still locked.

---

## 1. FAB overlap fixed

**Problem:** the floating `+ Manual` FAB (`position: fixed`, sits at `safe-b + 84px`,
~48px tall → top ≈ `safe-b + 132px`) overlapped the last row on long-scroll screens
because the scroll container only reserved `safe-b + 92px` of bottom padding.

**Fix:** [screens.tsx](frontend/src/screens.tsx) `Screen` wrapper bottom padding
`calc(var(--safe-b) + 92px)` → **`calc(var(--safe-b) + 150px)`**. Every screen uses
`<Screen>`, so all long-scroll screens (Home, Signals, Trades, Market, Risk, System,
Trade Detail) are fixed at once. 150px clears both the bottom nav (~`safe-b + 60px`) and
the FAB top (~`safe-b + 132px`) with ~18px slack.

**Verified live (measured geometry):**
- Home @390, scrolled to bottom: last content bottom **694px** ≤ FAB top **711px** → clears ✅
- Risk @430, scrolled to bottom: disclaimer bottom **776px** ≤ FAB top **799px** → clears ✅
- Signals @390: last card (SUI) scrolls fully above the FAB (screenshot) ✅

---

## 2. Modal accessibility

[ManualTradeModal.tsx](frontend/src/ManualTradeModal.tsx) — the order-ticket bottom sheet:
- `role="dialog"`, `aria-modal="true"`, `aria-labelledby="order-ticket-title"` (title id added).
- **Escape closes** the modal.
- **Focus management:** panel is focused on open (`tabIndex={-1}`), focus restored to the
  previously focused element on close.
- **Focus trap:** Tab / Shift-Tab cycle within the dialog's focusable elements.
- Effect runs **once on mount** (via an `onClose` ref) so 15–30s query re-renders never
  steal focus from the inputs.

[App.tsx](frontend/src/App.tsx) — the emergency-pause confirm modal: added `role="dialog"`,
`aria-modal="true"`, `aria-labelledby="pause-title"`, and Escape-to-close.

**Verified live:** open → `role=dialog` + `aria-modal=true` + labelledby→"Order ticket",
`document.activeElement` is inside the dialog; **Escape → dialog removed**. ✅

---

## 3. Clickable card accessibility

[components.tsx](frontend/src/components.tsx) `TradeCard` was a bare `<div onClick>`.
Now: `role="button"`, `tabIndex={0}`, `aria-label="Open {symbol} {dir} detail"`,
`onKeyDown` handling **Enter/Space**, plus `cursor-pointer` and a
`focus-visible:ring-2 ring-accent/50` focus ring. Visual styling unchanged (same `.glass`
card). No other card uses a div-onClick (SignalCard, nav, segmented filters, quick links
are already real `<button>`s).

---

## 4. Demo fixtures for visual regression (display-only mock data)

[desk_adapter.py](backend/app/desk_adapter.py) `_demo_signals()` — added two fixtures so
every non-actionable state is now demonstrable offline (the other two already existed):

| Fixture | Mode/Tier | Resolves to | Badge | Manual Entry |
|---------|-----------|-------------|-------|--------------|
| **ARB/USDT** (new) | crypto intraday, triggered 22m ago | very_late (>15m) | `DO NOT CHASE` | none ✅ |
| **DOGE/USDT** (new) | crypto intraday, **Tier C** | blocked | `BLOCKED` | none ✅ |
| RIF/USDT (existing) | crypto **scalp** | shadow | `SHADOW ONLY` | none ✅ |
| AMD (existing) | stocks intraday, `shadow_sector_cap` | shadow | `SHADOW ONLY` | none ✅ |

These are mock data only — `actionability.classify` (the safety gate) and all trading
logic are untouched. The fixtures simply make the gate's existing branches visible.

**Verified live (Signals @390):** 7 cards, button map = `[Chart, Manual Entry]×2`
(ZEC, WLD — the only actionable signals) then `[Chart, Not actionable]×5`
(RIF, AMD, ARB, DOGE, SUI). ARB shows "very late 22m — DO NOT CHASE"; DOGE shows
"tier C — not actionable". ✅

---

## 5. Chart auto-fit

[Chart.tsx](frontend/src/Chart.tsx) — added an `autoscaleInfoProvider` to the candlestick
series that extends the autoscale price range to include all overlay levels
(entry_high/low/trigger, stop_loss, tp1/2/3) with 4% padding. No price data is faked —
only the visible price range is widened so the lines aren't drawn off-screen.

**Verified live (ZEC detail @390):** before, the stop (46.90) sat below the visible range;
now the full set renders in view — stop **46.90** (red, bottom), entry band **48.20/48.70**,
TP1 **50.10**, TP2 **51.80**, TP3 **53.40** (violet, top). ✅

---

## 6. Re-build

```
cd frontend && npm run build
tsc -b && vite build → 91 modules, ✓ built in 2.49s, 0 TypeScript errors
dist: index.html 1.00 kB · index.css 15.30 kB (gz 4.17) · index.js 379.85 kB (gz 120.12)
```
✅ Green. (CSS grew ~0.6 kB from the new focus-ring / cursor utilities.)

---

## 7. Re-check (live preview, demo backend)

| Check | Result |
|-------|--------|
| Console errors | none |
| 390px | no horizontal overflow; Home/Signals FAB clearance ✅ |
| 430px | `scrollWidth == clientWidth` (430), no overflow; Risk FAB clearance ✅ |
| Home | new "ARB/USDT late entry — do not chase" alert + Shadow/late count = 3 ✅ |
| Signals | DO NOT CHASE + BLOCKED + SHADOW ONLY + CLOSED all render, no Manual Entry ✅ |
| Trade Detail / Chart | all overlay levels in view, no console errors ✅ |
| Risk | manual_live/auto_live 🔒 LOCKED, scalp = research only; disclaimer clears FAB ✅ |
| ManualTradeModal | dialog roles + labelled title + focus-in + Escape-close ✅ |

---

## 8. Backend tests

```
cd backend && python -m pytest tests/ -q
18 passed, 2 warnings in 1.41s
```
✅ **18/18.** Warnings are pre-existing FastAPI `on_event` deprecation notices. The new
demo fixtures don't break `test_shadow_signal_not_actionable` (ARB/DOGE aren't scalp) or
any other test.

---

## 9. Safety unchanged (re-confirmed)

- `actionability.classify` untouched; gate `canManual = actionable && status==="actionable"` intact.
- Crypto/stocks scalp still shadow-only; C-tier still blocked; live + auto-live still LOCKED.
- The only backend change is offline demo display data. No strategy, scoring, TP/SL,
  threshold, or execution change. No auto-trading.

## Files changed
- `frontend/src/screens.tsx` — FAB clearance padding
- `frontend/src/ManualTradeModal.tsx` — dialog a11y + Escape + focus trap
- `frontend/src/App.tsx` — pause-modal a11y + Escape
- `frontend/src/components.tsx` — TradeCard button semantics + keyboard + focus ring
- `frontend/src/Chart.tsx` — autoscale includes overlay levels
- `backend/app/desk_adapter.py` — two display-only demo fixtures (late, blocked)

> ## Verdict: ✅ `CONTROL_PLANE_UI_POLISH_READY`
