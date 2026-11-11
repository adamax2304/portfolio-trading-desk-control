# Re-audit tails — fixes + recomputed strategic metrics

Date: 2026-07-02 · Scope: paper / read-model / control-plane only ·
**Live, auto-live, manual-live remain HARD-LOCKED** · `signal_outcomes.final_r` untouched.

This closes the six required fixes from the second read-only audit and the three follow-on
analytics (recomputed cohorts, B-promotion decision, cohort allocator read-model).

---

## Required fixes

### #1 — Look-ahead closed in the entry-mode overlay
`crypto-ai-desk/src/execution/entry_mode_classifier.py::compute_record` now passes
`created_at=trade.get("created_at")` into `_candles_for(...)` (it already flowed through
`_entry_triggered_signals`). The classifier can no longer see candles that printed after the
signal existed. Test `test_entry_mode_compute_record_excludes_future_bars` asserts
`candles_used == 2` with a cutoff between bars and `== 4` without — it fails if future bars leak.

### #2 — B-book rebuilt on the SAME asset-aware cost model as the A-book
- Extracted the asset-aware cost selection into `paper_portfolio.resolve_cost_context(...)`
  (stocks → `stock_etf_default` + stock slippage + funding 0; crypto → futures profile +
  crypto slippage + approximate funding; `zero` → no-cost). `simulate_portfolio` now calls it.
- `scripts/structural_maker_backfill.py::simulate_b` calls the SAME helper — no relabelling;
  `cost.fee_source` is the honest model actually applied, and `funding_usdt` is passed per asset.
- **Rebuilt** `bybit_structural_maker_first` (656 rows). DB verification:
  **stocks rows with a Bybit `fee_source` = 0** (390 stocks rows now read "US equity/ETF paper
  model…", 266 crypto rows read "Bybit non-VIP USDT perpetual…"). Test
  `test_b_book_stocks_not_bybit_perp_fee_source`.

### #3 — Lifecycle read-model is asset-aware
`trading-desk-control/backend/app/lifecycle.py` gained `_cost_model(asset_class, symbol, mode)`.
Entry / TP / stop / expiry fees now use the asset's maker/taker/slippage (stocks: commission-free
+ ~1bp + stock slippage, NO perp funding; crypto: perp rates + approx funding). The response adds a
`cost_model` block splitting `exchange_fees_usdt / slippage_usdt / funding_usdt` and sets
`position.fee_profile` / `fee_source` per asset. Tests `test_stock_lifecycle_not_bybit_perp`
(stock → `stock_etf_default`, funding 0, `funding_known` False) and `test_crypto_lifecycle_is_perp`.

### #4 — Confirm gate enforced on `/api/risk/update`
Added shared `main._require_confirm(command_type, confirm_token)` (blank/whitespace token → 400).
Both `/api/command` and the typed `/api/risk/update` wrapper now use it, so a blank
`confirm_token` can no longer slip through the wrapper into `process_command`. Test
`test_risk_update_rejects_empty_confirm`.

### #5 — Python import-path hygiene for backend tests
Added `trading-desk-control/pytest.ini` (`pythonpath = backend`) + `backend/conftest.py` that
pins the backend dir to the FRONT of `sys.path` (shadow-proof against a same-named `app` package
elsewhere on the machine). `python -m pytest backend/tests -q` now runs green with **no**
`PYTHONPATH` hack (verified: 83 passed, 9 skipped).

### #6 — The "9 pre-existing" crypto failures resolved (test-only)
Root cause (via investigation): **calendar-drift stale fixtures**, product code correct.
- `test_catalyst_layer.py` + `test_entity_aliases.py` (7 tests): fixtures hardcoded
  `published_at="2026-06-01"`, which aged past the collector's rolling 720h window → 0 rows
  scanned. Fixed by anchoring the fixture timestamps to `now` (ordered `_R10 < _R11 < _R1130`).
- `test_risk_guard_fields.py` (the 2 the audit flagged): time-fragile — `_seed_losing_day`
  back-dates exits 1–3h and the circuit breaker counts stops by UTC day, so they failed only in
  the first ~3h of a UTC day. Fixed by anchoring `NOW` to **noon UTC**.
- No product code changed; no live/order path touched (the collector is read-only; the risk guard
  is `diagnostic_only` and by contract never blocks/routes/sizes).

Also fixed a real (my own) classifier ordering bug found while adding the allocator: a
`failed_bounce` is a SHORT/breakdown setup and was being swallowed by the "bounce" substring in
the pullback bucket — `cohort_allocator.setup_family` now checks breakdown before pullback.

---

## #7 — Recomputed strategic cohorts (after the B-book fix)

`scripts/strategic_cohorts.py` (read-only) writes per-book CSVs to `data/research/` with the full
split (trades / gross / exchange_fees / slippage / funding / net / avg R / win-rate / max-DD, by
asset_class × mode × tier × direction × setup_type) for three separate books. Coarse roll-up
(asset × mode × direction × setup family), net $ + allocator status:

**A — mechanical/taker (backfill), 650 trades, net +$533.94**

| asset | mode | dir | family | trades | net$ | alloc |
|---|---|---|---|---:|---:|---|
| crypto | swing | long | pullback | 102 | **+485.04** | candidate 1.0 |
| crypto | swing | short | breakdown | 16 | **+415.99** | candidate 1.0 |
| crypto | intraday | short | breakdown | 27 | +303.24 | candidate 0.5 |
| crypto | intraday | long | continuation | 8 | +132.39 | shadow_only |
| stocks | intraday | short | continuation | 39 | +190.67 | research_shadow |
| crypto | swing | long | continuation | 6 | −55.21 | candidate 1.0 |
| crypto | intraday | long | pullback | 101 | **−411.99** | disabled |
| stocks | intraday | long | continuation | 351 | **−526.19** | disabled |

**B — structural/maker (backfill), 656 trades, net +$830.62** (same shape, better net: maker-first
+ asset-aware costs lift stocks and swing).

**S — paper-shadow FORWARD, clean cohort (DATA_GAP_LATE excluded), 81 trades, net −$358.33**

| asset | mode | dir | family | trades | net$ | alloc |
|---|---|---|---|---:|---:|---|
| crypto | swing | long | pullback | 18 | −12.77 | candidate 1.0 |
| crypto | swing | short | breakdown | 5 | −28.80 | candidate 1.0 |
| crypto | intraday | short | breakdown | 3 | −39.72 | candidate 0.5 |
| crypto | scalp | (all) | — | 13 | −138.63 | shadow_only |
| stocks | intraday | short | continuation | 11 | +3.08 | research_shadow |
| stocks | intraday | long | continuation | 21 | −76.02 | disabled |

The allocator's `disabled` cohorts (crypto intraday long pullback, stocks intraday long
continuation) are exactly the two biggest **backfill losers** — an independent sanity check that
the weights point at the right cohorts.

---

## #8 — Decision: do NOT promote "all of B"

**Backfill is look-ahead and is NOT proof.** A and B are whole-history repricings; the only valid
evidence is the forward-since-activation shadow, and **clean forward B is net-negative (−$358 over
81 trades)**. No cohort has a forward-proven positive edge yet — even the strongest candidates
(crypto swing pullback/breakdown) are marginally negative in clean forward.

Therefore:
- **A stays the shadow baseline / control.** B is a better *idea* (backfill net and per-cohort),
  but not promotable as a whole.
- Continue **paper** validation only on the specific B candidates (weights below), forward-only.
- **Stocks B is not "ready"** — stocks intraday long continuation is a disabled loser; only stocks
  short continuation survives as a separate research/shadow candidate needing its own forward proof.
- Live / auto-live / manual-live stay hard-locked; nothing here promotes to execution.

## #9 — Cohort allocator / risk-weights read-model (paper-only)

`crypto-ai-desk/src/execution/cohort_allocator.py` — a labelling/reporting layer (NOT execution):

| cohort | weight | status |
|---|---:|---|
| crypto swing (pullback / breakdown) | 1.0 | candidate |
| crypto intraday short breakdown | 0.5 | candidate_reduced |
| crypto intraday long pullback | 0.0 | disabled |
| stocks intraday long continuation | 0.0 | disabled |
| crypto scalp | 0.0 | shadow_only |
| stocks short continuation | 0.0 | research_shadow (own forward proof required) |
| everything else | 0.0 | shadow_only |

Test `test_cohort_allocator_weights`. Nothing here sizes, routes, or gates any order.

---

## Strict profitability verdict

- On **backfill**, B (+$830.62) beats A (+$533.94) and the winning cohorts are crypto swing
  pullback/breakdown + crypto intraday short breakdown; the losers are crypto intraday long
  pullback and stocks intraday long continuation.
- On **valid forward evidence**, the whole book is still **net-negative** (clean forward B
  −$358.33). **No cohort is live-ready.** The realistic status is: a small set of crypto
  swing/short-breakdown candidates worth continued PAPER validation, everything else shadow-only,
  live locked.

## Verification (acceptance criteria)

- Audit tests green: `crypto tests/test_audit_fixes_engine.py` **11/11**;
  `backend/tests/test_audit_fixes.py` **10/10 (+1 skip)**.
- Backend suite via plain `python -m pytest backend/tests -q` (no PYTHONPATH hack): **83 passed,
  9 skipped, 0 failed**.
- Full `crypto-ai-desk` suite: **948 passed, 0 failed** (was 936/9 — the 7 previously-failing
  catalyst/alias/risk-guard tests now pass, plus the new re-audit tests).
- Frontend `npm run build`: clean (tsc + vite).
- B-book stocks rows with Bybit-perp `fee_source`: **0**.
- Entry-mode overlay: look-ahead-safe (test-guarded).
- `/api/risk/update`: blank confirm token → 400 (shared gate; test-guarded); backend redeployed.
- Live / auto-live / manual-live: **LOCKED** (unchanged).
