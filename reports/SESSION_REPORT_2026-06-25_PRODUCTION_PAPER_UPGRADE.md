# Session Report — Production-Paper · UI · Execution Upgrade
**Date:** 2026-06-25 · **Repos:** `crypto-ai-desk` (engines) · `trading-desk-control` (Telegram Mini App)
**Posture (unchanged):** `live_locked=true`, `auto_live_locked=true` · `signal_outcomes.final_r` never mutated · no orders · no scoring/routing/actionability change.

---

## 1. What was done this session

A 22-part production-paper upgrade, delivered as **add-only paper read-model overlays** and verified
end-to-end with **real-UI screenshots** against a clean, build-stamped deploy. Per-part verdicts and
proofs live in `reports/00…22`; the capstone is `PRODUCTION_PAPER_UI_EXECUTION_FINAL_REPORT.md`.

### 1a. Deploy / stale-frontend guard (PART 0)
- Build stamp flows vite → `dist/build_info.json` → `/api/health` (`ui_build_id`) → System tab
  (`fresh`/`STALE`). Redeploy via `scripts/launch_robust.ps1`.
- **Root cause of "real UI still broken":** the operator was viewing a **stale cached bundle**. The
  CP keeper (`app_keeper.bat`) restarts only on health-failure, so an old in-memory process keeps
  serving. Now detectable. (See memory `project_trading_desk_control_stale_deploy`.)

### 1b. Five new paper read-model overlays (the substantive engineering)
Each = engine fed **real OHLCV** → additive table → `command_nonfatal` scheduler step (every 2h) →
lifecycle reads it → Mini-App badge. Key fact: the prior structural engines existed but were called
with `candles=None` (inert); feeding real candles is what made them fire.

| Part | Capability | Table / CLI | Result | UI badge |
|---|---|---|---|---|
| 3 | Structural TP replaces ATR ladder | `signal_paper_tp` / `paper-tp-refresh` | **790/800 structural** (was 0) | `TP: STRUCTURAL` |
| 4 | Breakout/momentum entry modes | `signal_entry_mode` / `entry-mode-refresh` | **610/800 non-pullback** | `entry: …` |
| 5 | Multi-factor stock direction | `stock_direction_score` / `stock-direction-refresh` | **400/400 multi-factor**, MSTR·BTC | `dir: …` |
| 6 | Entry-latency root cause | `entry_latency_audit` / `entry-latency-audit` | **273 data-gap / 0 detection** | `entry latency: …` |
| 8 | Structural stop movement | `signal_stop_plan` / `paper-stop-refresh` | **418 structural moves** | `stop: structural` |

### 1c. Activated / fixed
- **PART 9 — Max-5x:** rebuilt the ledger under the 5x config + made the leverage label data-driven →
  `max_leverage=5` all profiles (was 2); Home `+3.72% → +6.62%`. Risk unchanged at 0.5%/trade.
- **PART 14 — Regime "Unknown":** per-signal regime falls back to the market-dashboard regime with a
  reason (`Trend ↓ · market`).
- **PART 7/10/11/12 — Trade detail:** chart-first, true partial-fill TP markers (the ENA "+3R single
  marker" bug fixed), exchange-like price ladder. Verified already-shipped, now provably live.
- **PART 13/15/16/17 — UI:** Signals no overflow @375/430; Market dashboard (VIX/Fear&Greed/regime/
  news); button audit clean (no dead controls, no console errors).

### 1d. Tests / docs
- **22/22 new-module tests pass** (deterministic, no network): `test_signal_paper_tp`,
  `test_entry_mode_classifier`, `test_stock_direction_score`, `test_entry_latency_audit`,
  `test_signal_stop_plan`.
- **Full crypto-ai-desk suite: 910 passed, 2 failed.** The 2 (`test_risk_guard_fields.py`) are
  **pre-existing + date-dependent** (hard-assert `circuit_breaker_state=="would_pause"` while live
  state computes `"watch"` after the 06-24→06-25 day roll). Source files (`circuit_breaker.py`,
  `paper_entry.py`) were **not touched this session** — unrelated to this upgrade.
- Docs: `obsidian_vault/14_Project_Commands/Daily_Commands.md` paper-command section.

---

## 2. Conclusions

**Strengths.** Safety discipline is excellent (live locked, `final_r` immutable, everything add-only).
The read-model architecture (engine→table→lifecycle→badge) is clean, testable, and extensible. The
build stamp removes the recurring "stale frontend" ambiguity. The signal pipeline is genuinely rich
(momentum + structure + catalyst + derivatives + RS + sector) with honest partial-exit accounting.

**The two real blockers before any live discussion:**
1. **Edge is fee-fragile** (prior finding, unchanged): Model-F is `+47.6%` no-cost → `+2.94%` Bybit →
   `−5.65%` conservative. The edge may not survive real fees/slippage.
2. **Label ↔ execution gap:** entry-modes and stock-direction currently *display* the better decision,
   but the tracker still **executes** the old pullback/EMA logic. The 610 breakout entries and 74
   direction flips are *potential* upside not yet realised in R. (Structural TP/stop DO already flow
   into the paper blended-R; entry-mode + direction do not.)

**Other fixes (non-blocking):** stock-intraday OHLCV coverage gap (root of the MSTR lateness);
Risk-tab `$10k/0.25%` vs ledger `$5k/0.5%` mismatch; Market "Main Risk Now" repeats the BTC headline
for stocks; chart TP-label crowding; keeper should restart on build-id drift not just health-fail.

---

## 3. Further recommendations (priority order)

1. **Build a paper-shadow execution lane** (see §4) — A/B the new logic vs production on the same
   signals for 2–4 weeks **with real Bybit fees**. This closes the label↔execution gap *and* tests
   fee-fragility without any live risk or sign-off.
2. **Backfill stock-intraday early-session 15m bars** before tracking (yfinance allows ~60d intraday)
   so entry/latency records are trustworthy; exclude `DATA_GAP_LATE` from edge stats meanwhile.
3. **Reconcile the Risk-tab vs ledger** paper-balance/risk surfaces (one source, or cross-labelled).
4. **Keeper build-id drift restart** so code edits are served without a manual kill.
5. Minor UI polish: Market main-risk dedup by asset class; chart TP-label legibility.

---

## 4. Shadow-tests status

**Existing shadow infrastructure (separate from the new logic):**
- Modules present: `src/exits/shadow_exit_manager.py`, `src/agents/discovery_expansion_agent.py`.
- Mini-App has a **Shadow** trade bucket + **Shadow** book.
- **Current state: 0 shadow/discovery rows, 0 shadow-routed signals** — the shadow lanes are wired
  but idle (nothing routed to them at present).

**Paper-shadow lane for THIS upgrade's new logic: NOT BUILT YET (recommended next step).**
- There is currently **no** lane that executes a second (shadow) branch using the new entry-modes +
  structural TP/stop + multi-factor direction to compare blended R against the production branch.
- This is the highest-value next task and is **safe + needs no live approval**: the tracker would
  write a parallel shadow outcome per signal; after ~2 weeks we compare new-logic R vs old-logic R on
  identical signals, net of real Bybit fees.
- Acceptance for that lane: new-logic blended R > old-logic blended R **after costs** on the forward
  window → only then is there a basis for the next step. Until then, everything stays paper, live
  locked.

**Net:** strategy overlays are computed and visible (paper labels), structural TP/stop already affect
paper R, but the breakout-entry + multi-factor-direction upside is **not yet measured in R** — the
shadow lane is the instrument to measure it. Status: **proposed, not yet implemented.**
