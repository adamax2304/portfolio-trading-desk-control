# PART 2 — Auto Telegram daily A/B digest — REPORT
**Date:** 2026-06-26 · observability only · never trades / promotes B / changes scoring / final_r.

## What shipped
- Config `config/paper_shadow_digest.yaml` (`paper_shadow_telegram_digest`: enabled / cadence / send_time_local
  "09:00" / include_backfill false / include_top_examples true).
- Composer `src/notifiers/paper_shadow_telegram.py` enriched with **best/worst B mode**, **maker fill
  rate** (posted/missed/taker-fallback), and the gate line.
- `send_daily_if_due()` — once-per-local-day, send-time-gated, idempotent (state file
  `data/.paper_shadow_digest_last.txt`).
- CLI `paper-shadow-digest-send` (`--dry-run`/`--force`) + scheduler step `paper_shadow_digest_step`
  (command_nonfatal) wired after the shadow refresh. Does NOT spam per-trade.

## Live composed digest (verified)
```
📊 Paper-Shadow A/B — daily (FORWARD = valid evidence)
window: 0d · forward signals 40
A (old): 40t · -8.65R · $-216.18 · fee $14.95
B (new): 39t · -4.16R · $-104.1 · fee $21.79
Δ: +4.48R · $+112.08
best B mode: stocks swing +2.61R · worst: stocks invest -0.4R
maker fill 100.0% (posted 18 · missed 0 · taker-fb 0)
B: missed 0 · no-chase 1 · dir-flips 0 · DATA_GAP excl 0
B max-DD -5.712R vs A -8.647R · B fee-drag 1.933R
promotion gate: NOT_READY (4/6) — evaluation only, no auto-promote
⚠ forward B sample 39 < 60 trades · forward window 0d < 14d
backfill is look-ahead — a hypothesis, NOT proof. Decide on FORWARD only.
```

Includes every required field: forward window, A vs B net R/$, ΔR/Δ$, best/worst B mode, maker fill
rate, missed maker, DATA_GAP excluded, no-chase, dir-flips, gate status, backfill caveat.

## VERDICT: `TELEGRAM_DAILY_SHADOW_AB_DIGEST_ACTIVE` ✅
