# AI Trading Desk — Control Plane (Telegram Mini App)

Professional, safety-first control plane for the existing `crypto-ai-desk` trading system.
**Read-only monitoring + safe paper control. Live trading is hard-locked in v1.**

> **PnL accounting (2026-06-24):** the dashboard headline is **Paper Execution R** (Model F — early MFE-armed protection: stop→BE @ +0.6R, lock +0.5R @ +1R, runner TP3), the authoritative paper PnL. The old **Touch R** (highest TP touched) is shown only as a secondary, optimistic **signal-quality** metric — it is NOT real PnL. Accounting/display only; no live execution; historical `final_r` is never rewritten.

> **Paper portfolio (2026-06-24):** the dashboard shows a paper-trading portfolio — **$5000 deposit, 0.5%/equity risk, stop-based position sizing, dynamic leverage** (margin + liquidation aware; **avg ~1.95x, max 5x**, shown in-app — leverage ≠ risk), **net of configurable fees/slippage** (Bybit/MEXC/conservative profiles, each with source/last_verified). Cards: Paper Equity, Today Net $/R, Max Drawdown, Fees, **Leverage, Open/Margin**. Endpoints: `GET /api/portfolio`, `GET /api/portfolio/trades`, `GET /api/trades/{id}/chart-events` (entry / **exit** / **expired** / stop / moved-stop / TP markers with **exact R** + $). Paper PnL is **net USD after fees** (close fee on the exit notional; from `paper_execution_r`, never touch_r). Expired trades close at the implied price (not 0). TP levels are shown with **exact R (e.g. 1.2/2.2/3.2R, not "+1R")** and labelled **MECHANICAL_ATR_LADDER** (production TPs are an ATR ladder; volume-profile unknown). Model-F edge is fee-fragile (replay: +47.5% no-cost → +2.82% Bybit). Full candlestick line-overlay = TODO (marker timeline live). No live execution; `final_r` never rewritten. Config: `crypto-ai-desk/config/paper_portfolio.yaml` + `config/fee_profiles.yaml`.

> **Paper Features panel (2026-06-24):** the dashboard shows a **Paper Features** panel (`GET /api/paper-features`) listing which paper features are active (accounting/display/advisory), which are kept shadow/measuring, archived, or dangerous-locked — each with evidence + decision date. Every active feature is non-trade-affecting; live/auto-live remain hard-locked. Source of truth: `crypto-ai-desk/config/paper_features.yaml`. Plain-English status of what's implemented / testing / waiting / locked: `crypto-ai-desk/docs/CURRENT_TESTING_AND_WAITING_STATE.md`.

> **Trade-detail chart-first + true partial-exit markers + Market VIX (2026-06-24, PAPER):** clicking any trade (Signals / open / closed) opens a **chart-first** page: a candlestick (`lightweight-charts`) with **per-partial-fill markers** (TP1/TP2/TP3 fills at their real prices) + entry/stop/moved-stop/TP price lines — the ENA "single exit near TP1/TP2" was a `Chart.tsx` bug (it drew one `exit` marker and ignored the already-correct chart-events; now fixed). Below the chart: a **price-ladder outcome table** (Stop/Entry/TP1-3 · price·R·net$·status), the lifecycle timeline, and setup. `/api/trades/{id}/chart-events` markers now carry the full execution schema (cumulative R/$, side, source_book, is_partial/final) + `lines`. Active trades keep partial badges after TP1. **Market tab VIX** now loads via deterministic `fetch_market_extras` (yfinance ^VIX + SPY/QQQ trend + ETH/BTC), backfilled in the Opus parser/fallback so it's never blank (shows "VIX unavailable" explicitly otherwise). Signals cards no longer overflow on narrow widths. No live execution; `final_r` never rewritten.

> **Execution UI + position lifecycle + market dashboard + max-5x (2026-06-24, PAPER):** leverage policy raised **2x → max 5x safe** (margin ≤25%, notional ≤150%, liquidation kept ≥3× the stop distance — leverage ≠ risk; wide stops auto-reduce leverage). Trades now have a full **position lifecycle** (`GET /api/trades/{id}/lifecycle`): partial TP fills **33%/33%/34%**, moved/structural stops, **blended R + $ per fill**, active-after-TP1. The trade-detail drawer is **exchange-like** (position summary, price ladder with $ per TP, execution timeline, price-scaled chart overlay) and `/api/trades/{id}/chart-events` now shows the **true execution markers** (e.g. ETH +3R → three TP fill markers at their real prices, not one misleading exit). Active rows show partial badges ("TP1 filled · waiting TP2/TP3"). **Regime** shows a readable label (free-text→enum; "unknown" only when truly empty). The **MSTR** "very late — DO NOT CHASE" label no longer appears on closed/expired trades (chase-guard is for open trades only); a **missed-opportunity journal** (`/api/missed-opportunities`) lists genuine no-entry misses. New **Market tab** (`/api/market-dashboard`): crypto fear&greed, crypto/stock market mode + main risk now, regime, today + long-term news, extras — written by the **Opus enriched-review routine's final JSON block** (does not change the review body; fail-open + stale-warning). No live execution; `final_r` never rewritten.

> **Structural TP + maker-first + safe max-2x (2026-06-24, PAPER):** paper trades now use a **structural TP set** (swing/range/round/volume-profile levels; production TP generation = mechanical ATR ladder, **unchanged**), a **maker-first execution model** (maker entry for pullbacks, maker TP exits, **stops always taker**, conservative fills) and a **safe max-2x leverage policy** (margin ≤40%, notional ≤80%, liq-buffer 3× — *leverage ≠ risk*; tight stops cap notional, never lever up). `GET /api/portfolio/compare` returns **A (mechanical+taker) vs B (structural+maker-first)**: Bybit $5000/587 → **A +3.72%/$1763 fees, B +8.19%/$1585 fees (Δ +4.47pp, 177 maker entries)**. The dashboard shows an A/B card; the trade detail shows the per-trade `paper_execution_b` (TP-set label, entry/exit/stop order types, leverage, B net vs A net). The B book is the `bybit_structural_maker_first` fee profile. Structural swing/VP TP is **forward-only** (live candles); the historical backfill labels ATR-fallback. No live execution; `final_r` never rewritten.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design and
[docs/IMPLEMENTATION_REPORT.md](docs/IMPLEMENTATION_REPORT.md) for what's built vs locked.

**v1 status:** `CONTROL_PLANE_V1_READ_ONLY_PLUS_PAPER_READY` — see
[docs/CONTROL_PLANE_V1_FINAL_REPORT.md](docs/CONTROL_PLANE_V1_FINAL_REPORT.md).

## Layout
```
backend/   FastAPI control API (auth, read adapter, command queue, audit) + control.sqlite
frontend/  Vite + React + TS + Tailwind Mini App (6 tabs + chart + manual + risk modal)
bot/       aiogram launcher (/start, /help) + emergency pause
scripts/   PowerShell launchers (start_backend/frontend/bot/control_plane, build, tests)
docs/      architecture, per-part implementation reports, runbook, checklist, final report
```

## Run (local dev) — PowerShell scripts
```powershell
# configure: copy .env.example → .env  (demo: APP_ENV=dev, DEMO_MODE=1, AUTH_DISABLED=1)
./scripts/start_backend.ps1        # http://127.0.0.1:8000  (loads .env)
./scripts/start_frontend.ps1       # http://localhost:5173  (proxies /api → :8000)
./scripts/start_bot.ps1            # optional; needs TELEGRAM_BOT_TOKEN + MINI_APP_URL
# or both at once:
./scripts/start_control_plane.ps1
```
Real data: set `DESK_DB_PATH` to `../crypto-ai-desk/db/crypto_ai_desk.sqlite` (read-only),
leave `DEMO_MODE`/`AUTH_DISABLED` empty, set `TELEGRAM_BOT_TOKEN` + `ALLOWED_TELEGRAM_USER_IDS`.
Full steps: [docs/LOCAL_LAUNCH_RUNBOOK.md](docs/LOCAL_LAUNCH_RUNBOOK.md). Telegram setup:
[docs/TELEGRAM_MINI_APP_LAUNCH_SETUP.md](docs/TELEGRAM_MINI_APP_LAUNCH_SETUP.md).

## Tests
```powershell
./scripts/run_tests.ps1            # backend pytest (33) + frontend build
# or: cd backend; python -m pytest tests/ -q   ·   cd frontend; npm run build
```

## What v1 can do
Read-only monitor (signals/trades/charts/market/health) · audited **paper** risk & mode
controls · **paper** orders (from signal or custom) + close/cancel/notes · sanity checks ·
emergency pause — all via the command queue + audit log.

## Environment
See [.env.example](.env.example). Secrets live only in the backend; the frontend never
receives keys. `AUTH_DISABLED=1` is **local dev only**.

## Safety at a glance
- Telegram initData verified server-side + user-id whitelist.
- Every state change → command queue + audit row; UI cannot touch trading YAML/DB.
- Hard-locked in v1: live & auto-live modes, `MANUAL_LIVE_ORDER`, enabling crypto/stocks
  **scalp**, C-tier promotion. Crypto scalp stays shadow-only; stocks scalp research-only.
- Shadow/late/C-tier/paused signals **cannot** show “Manual Entry”; late entries show
  “DO NOT CHASE”.

## Paper-shadow A/B observability (System tab)

The **Paper Shadow A/B** panel (System tab) measures old-paper (A) vs new-logic shadow (B) over the
same signals/OHLCV/fees. **Forward A/B monitoring continues** (promotion gate NOT_READY; decide on the
forward window in ~2–4 weeks; **B is not promoted; live stays locked; `final_r` untouched**).

- **Per-mode breakdown active** — `/api/paper-shadow/breakdown` + the *By mode* section (forward is the
  default; backfill is behind a toggle and labelled look-ahead/hypothesis).
- **Per-trade A/B detail** — `/api/paper-shadow/trades` (A vs B blocks + ΔR/why + valid-forward vs backfill).
- **Fee assumptions card** + **maker realism** line (posted/filled/missed/taker-fallback).
- **Daily Telegram A/B digest** — once-daily, observability only (config `paper_shadow_digest.yaml`).
- **DB retention** — `signal-outcomes-retention` archives old per-bar tracking rows (latest-row-per-signal
  + final outcomes always kept; dry-run default).
- **Diagnostics (no production effect):** catalyst-linkage shadow audit, A-tier strictness, stocks-mode
  readiness — none change scoring, thresholds, or actionability. **Stocks scalp/swing/invest remain
  non-actionable unless separately approved.**
