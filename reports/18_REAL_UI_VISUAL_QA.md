# PART 1 + 18 — Real UI Visual QA (before/after, screenshots)

**Verdict: `REAL_UI_VISUAL_QA_PASS`** (UI parts) — captured against the freshly-deployed,
build-stamped bundle `b-20260624-214244`, backend pid 21532, `live_locked=true`, via the preview
QA harness (vite dev → `/api` proxied to the live `:8000` backend with real desk data).

## Headline finding

**Most of the "real UI still broken" parts were already implemented — the operator was viewing a
STALE cached bundle.** Deployed fresh + build-stamped, they render correctly on screen. This is the
PART 0 root cause in action (keeper kept an old process alive; Telegram webview cached the old JS).
The build stamp now makes this state visible (System tab → `fresh`/`STALE`).

## Verified on screen (375 / 430 px mobile)

| Part | Claim | Real-UI result | Screenshot evidence |
|---|---|---|---|
| 0 | Build stamp / no-stale guard | System tab: `BUILD: fresh`, `UI BUILD b-20260624-214244`, `PAPER · LIVE LOCKED` | System tab |
| 9 | Max-5x active | Home: `1.68x avg · max 5x · 0 risk-capped`, `$5331 / +6.62%` (was 2x / $5186) | Home before/after |
| 13 | Signals no overflow | `scrollWidth==clientWidth`, 0 offenders at **375** and **430** px; chips + TP grid fit | Signals tab |
| 7 | Partial-exit lifecycle | ENA detail: TP1(33%)/TP2(33%)/TP3(34%) all `filled`; `+2.2R blended` vs `touch +3.0R` | Trade detail |
| 10 | True TP markers + overlay | Chart shows Entry/Initial-stop/TP1/TP2/TP3/Current-stop **price lines** + `TP1 fill`/`TP2 fill`/`Stop moved` **dot markers** — NOT one generic "+3R" exit | Trade detail chart |
| 11 | Chart-first trade detail | Candlestick chart is the top element under the header; summary + ladder below | Trade detail |
| 12 | Exchange-like price ladder | `PRICE LADDER · OUTCOMES` table: Level / Price / R / Net $ / Status | Trade detail |
| 15 | Market dashboard | `Risk Off · Bearish Trend 50%` / `Chop`, `Fear&Greed 17 Extreme fear`, `VIX 19.7 · SPY/QQQ down`, Main Risk Now, curated news (CoinDesk/The Block, symbols + importance) | Market tab |
| 16 | Opus routine feeds Market | snapshot carries regime + F&G + VIX/SPY/QQQ extras + news → rendered | Market tab |

### The ENA "+3R single misleading marker" bug — resolved
Operator's #1 visible complaint. The chart now draws the **full execution overlay**: entry, initial
+ moved stop, three TP price lines, and discrete partial-fill markers (`TP1 fill`, `TP2 fill +2.2R`,
`Stop moved +0.5R`). The header reports `+2.2R blended` (realistic, partial-weighted) alongside the
legacy `touch +3.0R` — `signal_outcomes.final_r` untouched, just no longer the only number shown.

## Remaining UI polish (minor, logged — not broken)
- **PART 14** — per-signal regime still shows `Unknown` in the trade header (Market-tab regime is
  normalized to `Bearish Trend`/`Chop`; the per-signal field isn't backfilled through the same path).
- Market "Main Risk Now" shows the same BTC headline for both Crypto and Stocks (selection/dedup).
- Trade-detail chart overlay labels crowd at narrow width (legibility, not correctness).

## Still genuinely NEW work (not UI — strategy logic)
PART 3 structural TP in **production signal generation**, PART 4 breakout/momentum entry modes,
PART 5 multi-factor stock direction, PART 6 MSTR late-entry root cause. These are code changes in
`crypto-ai-desk` signal generation, not display, and are the substantive remainder.

`live_locked=true` throughout · `final_r` untouched · paper/read-model only.
