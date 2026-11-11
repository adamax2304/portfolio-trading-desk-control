"""Paper position lifecycle read-model (PAPER ONLY, read-only).

Derives a full exchange-style lifecycle for ONE signal — entry, partial TP fills
(33/33/34), moved/structural stops, remainder exit (stop/expired/active) — LIVE from
`proposed_signals` + `signal_outcomes`, so recent/active trades render correctly even
before the batch ledger is rebuilt. Risk-based sizing mirrors the desk max-5x policy.

Blended R is the partial-exit accounting (TP1 closes 33% at TP1.R, etc.) — distinct
from the Model-F single-exit `paper_execution_r` (kept for the audit panel). No live,
no orders, never writes; `signal_outcomes.final_r` untouched.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.portfolio import _ro_conn, _has_table, _parse
from app.regime import normalize_regime

# ---- paper policy mirrors crypto-ai-desk/config/paper_portfolio.yaml --------
INIT_EQUITY = 5000.0
RISK_PCT = 0.005
MAX_LEV = 5
MAX_MARGIN_PCT = 0.25
MAX_NOTIONAL_PCT = 1.50
LIQ_BUFFER = 3.0
PARTIALS = (("tp1", 0.33), ("tp2", 0.33), ("tp3", 0.34))
# ---- asset-aware execution-cost model (display accounting; mirrors the paper ledger) --------
# crypto perps → bybit_non_vip_usdt_perp; stocks/ETFs → stock_etf_default (commission-free +
# ~1bp, NO perp funding). Stocks must NEVER be shown with the Bybit-perp fee model.
CRYPTO_MAKER, CRYPTO_TAKER = 0.0002, 0.00055
CRYPTO_SLIP_MAJOR, CRYPTO_SLIP_ALT = 0.0002, 0.0005
CRYPTO_MAJORS = {"BTC", "ETH", "SOL", "BNB", "XRP"}
STOCK_MAKER, STOCK_TAKER = 0.0, 0.0001
STOCK_SLIP_MAJOR, STOCK_SLIP_ALT = 0.0003, 0.0008
STOCK_MAJORS = {"SPY", "QQQ", "IWM", "DIA", "AAPL", "MSFT", "NVDA", "AMZN", "META",
                "GOOGL", "TSLA", "AMD", "AVGO", "NFLX"}
# approximate crypto-perp funding by typical hold (funding interval ~8h); stocks = 0
_FUNDING_RATE = 0.0001
_FUNDING_INTERVALS = {"scalp": 0, "intraday": 1, "swing": 6, "invest": 0}
# back-compat aliases (crypto defaults) for any older references
MAKER, TAKER = CRYPTO_MAKER, CRYPTO_TAKER
SLIP_MAJOR, SLIP_ALT = CRYPTO_SLIP_MAJOR, CRYPTO_SLIP_ALT
_MAJORS = CRYPTO_MAJORS
_PULLBACK_HINTS = ("swing", "failed_bounce", "retest", "pullback", "bounce")


def _sym_base(symbol: str) -> str:
    return (symbol or "").replace("/", "").replace("USDT", "").replace("PERP", "")[:5].upper()


def _cost_model(asset_class, symbol, mode) -> dict:
    """Asset-aware per-trade display cost model. Stocks/ETFs use the equity/ETF profile
    (commission-free + ~1bp, NO perp funding); crypto uses the perp profile + an approximate
    funding estimate. Mirrors crypto-ai-desk/paper_portfolio.resolve_cost_context so the
    lifecycle display and the ledger agree; a stock is NEVER priced as a Bybit perp."""
    is_stock = str(asset_class or "").lower().startswith("stock")
    base = _sym_base(symbol)
    if is_stock:
        return {"is_stock": True, "maker": STOCK_MAKER, "taker": STOCK_TAKER,
                "slip": STOCK_SLIP_MAJOR if base in STOCK_MAJORS else STOCK_SLIP_ALT,
                "fee_profile": "stock_etf_default",
                "fee_source": "US equity/ETF paper model (commission-free + ~1bp); no perp funding",
                "funding_rate": 0.0, "funding_intervals": 0}
    return {"is_stock": False, "maker": CRYPTO_MAKER, "taker": CRYPTO_TAKER,
            "slip": CRYPTO_SLIP_MAJOR if base in CRYPTO_MAJORS else CRYPTO_SLIP_ALT,
            "fee_profile": "bybit_non_vip_usdt_perp",
            "fee_source": "Bybit non-VIP USDT perpetual",
            "funding_rate": _FUNDING_RATE,
            "funding_intervals": _FUNDING_INTERVALS.get(str(mode or "").lower(), 0)}


def _size(equity, entry, stop, direction):
    """Compact mirror of position_sizing.size_position (max-5x safe)."""
    long = str(direction or "long").lower() != "short"
    risk_usdt = round(equity * RISK_PCT, 4)
    stop_dist = abs(entry - stop)
    if entry <= 0 or stop_dist <= 0:
        return {"risk_usdt": risk_usdt, "qty": 0, "notional": 0, "leverage": 1, "margin": 0,
                "stop_dist_pct": 0, "liq_price": None, "liq_dist_pct": 0, "risk_capped": True,
                "actual_risk": 0, "liq_buffer_ok": True, "leverage_reason": "invalid geometry"}
    sdp = stop_dist / entry
    max_margin = equity * MAX_MARGIN_PCT
    cap = min(max_margin * MAX_LEV, equity * MAX_NOTIONAL_PCT)
    desired = risk_usdt / sdp
    notional = min(desired, cap)
    lev = max(1, min(MAX_LEV, -(-notional // max_margin) if max_margin else MAX_LEV))  # ceil
    lev = int(lev)
    safe_lev = int(1.0 / (sdp * LIQ_BUFFER)) if sdp > 0 else MAX_LEV
    liq_reduced = False
    if safe_lev >= 1 and lev > safe_lev:
        lev = safe_lev; notional = min(notional, max_margin * lev); liq_reduced = True
    qty = notional / entry
    actual_risk = qty * stop_dist
    margin = notional / lev if lev else notional
    liq_dist = 1.0 / lev
    liq_price = entry * (1 - liq_dist) if long else entry * (1 + liq_dist)
    return {"risk_usdt": risk_usdt, "qty": qty, "notional": round(notional, 2), "leverage": lev,
            "margin": round(margin, 2), "stop_dist_pct": sdp, "liq_price": round(liq_price, 6),
            "liq_dist_pct": liq_dist, "risk_capped": notional < desired - 1e-9 or actual_risk < 0.8 * risk_usdt,
            "actual_risk": round(actual_risk, 4), "liq_buffer_ok": liq_dist >= sdp * LIQ_BUFFER,
            "leverage_reason": (f"min lev for margin cap, ≤{MAX_LEV}x"
                                + ("; reduced for liq buffer" if liq_reduced else ""))}


def _r_of(price, entry, risk, long):
    if not price or not risk:
        return None
    return round(((price - entry) if long else (entry - price)) / risk, 3)


def position_lifecycle(signal_id: str) -> dict:
    conn = _ro_conn()
    empty = {"available": False, "signal_id": signal_id}
    if conn is None:
        return empty
    try:
        sig = conn.execute(
            "SELECT symbol,direction,asset_class,mode,tier,setup_type,market_regime,suggested_entry,"
            "entry_trigger,entry_low,invalidation,stop_loss,tp1,tp2,tp3,created_at FROM proposed_signals "
            "WHERE signal_id=?", (signal_id,)).fetchone()
        if not sig:
            return empty
        sig = dict(sig)
        out = conn.execute(
            "SELECT entry_triggered,entry_triggered_at,entry_price_used,tp1_hit_at,tp2_hit_at,tp3_hit_at,"
            "stop_hit_at,final_outcome,final_r,max_favorable_excursion_r,max_adverse_excursion_r,checked_at "
            "FROM signal_outcomes WHERE signal_id=? ORDER BY checked_at DESC, id DESC LIMIT 1",
            (signal_id,)).fetchone()
        out = dict(out) if out else {}

        direction = str(sig.get("direction") or "long").lower()
        long = direction != "short"
        entry = sig.get("entry_trigger") or sig.get("suggested_entry") or sig.get("entry_low")
        entry = out.get("entry_price_used") or entry
        stop0 = sig.get("invalidation") or sig.get("stop_loss")
        if not entry or not stop0:
            return {**empty, "available": False, "reason": "missing entry/stop"}
        risk = abs(entry - stop0)
        sz = _size(INIT_EQUITY, entry, stop0, direction)
        risk_usdt = sz["actual_risk"] or sz["risk_usdt"]
        cm = _cost_model(sig.get("asset_class"), sig.get("symbol"), sig.get("mode"))
        slip = cm["slip"]
        tot_exch = 0.0   # accumulate exchange fees vs slippage SEPARATELY (asset-aware)
        tot_slip = 0.0
        pb = (sig.get("setup_type") or "").lower()
        entry_maker = any(h in pb for h in _PULLBACK_HINTS)

        tps = [("tp1", sig.get("tp1"), out.get("tp1_hit_at")),
               ("tp2", sig.get("tp2"), out.get("tp2_hit_at")),
               ("tp3", sig.get("tp3"), out.get("tp3_hit_at"))]
        pct = dict(PARTIALS)
        outcome = (out.get("final_outcome") or "").lower()
        entered = bool(out.get("entry_triggered")) or bool(out.get("entry_triggered_at"))

        events: list[dict] = []
        events.append({"event": "signal_created", "timestamp": sig.get("created_at"), "price": None,
                       "qty": None, "remaining_qty": None, "realized_pnl_usdt": None, "realized_r": None,
                       "fees_usdt": None, "order_type": None, "reason": "signal generated", "source": "registry"})
        if not entered:
            events.append({"event": "entry_missed", "timestamp": out.get("checked_at"), "price": entry,
                           "qty": 0, "remaining_qty": 0, "realized_pnl_usdt": 0, "realized_r": 0,
                           "fees_usdt": 0, "order_type": entry_maker and "maker" or "taker",
                           "reason": "entry trigger not reached within validity window", "source": "outcome"})
            status = "waiting_entry" if outcome not in ("expired", "missed_no_entry") else "missed_no_entry"
            return _assemble(signal_id, sig, out, sz, entry, stop0, risk, long, events, [], status,
                             0.0, 0.0, risk_usdt, conn, cm=cm, tot_exch=0.0, tot_slip=0.0)

        # entry filled
        qty0 = sz["qty"]
        ex_fee = qty0 * entry * (cm["maker"] if entry_maker else cm["taker"])
        sl_fee = qty0 * entry * slip
        entry_fee = ex_fee + sl_fee
        tot_exch += ex_fee; tot_slip += sl_fee
        events.append({"event": "entry_filled", "timestamp": out.get("entry_triggered_at"), "price": entry,
                       "qty": round(qty0, 8), "remaining_qty": round(qty0, 8), "realized_pnl_usdt": 0.0,
                       "realized_r": 0.0, "fees_usdt": round(entry_fee, 4),
                       "exchange_fee_usdt": round(ex_fee, 4), "slippage_usdt": round(sl_fee, 4),
                       "order_type": "maker" if entry_maker else "taker",
                       "reason": "entry trigger filled", "source": "outcome"})
        events.append({"event": "initial_stop_set", "timestamp": out.get("entry_triggered_at"), "price": stop0,
                       "qty": None, "remaining_qty": round(qty0, 8), "realized_pnl_usdt": None,
                       "realized_r": _r_of(stop0, entry, risk, long), "fees_usdt": None, "order_type": "taker",
                       "reason": "initial protective stop", "source": "signal"})

        partials: list[dict] = []
        remaining = qty0
        realized_pnl = 0.0
        realized_r = 0.0
        cur_stop = stop0
        cur_stop_r = _r_of(stop0, entry, risk, long)
        last_tp_filled = 0
        stop_plan = _read_stop_plan(conn, signal_id)  # PART 8 — structural stop-move plan
        for i, (name, price, hit_at) in enumerate(tps, start=1):
            if not hit_at or not price:
                continue
            qclose = qty0 * pct[name]
            r = _r_of(price, entry, risk, long) or 0.0
            ex_fee = qclose * price * cm["maker"]      # maker TP exits (limit)
            sl_fee = qclose * price * slip
            fee = ex_fee + sl_fee
            tot_exch += ex_fee; tot_slip += sl_fee
            pnl = pct[name] * r * risk_usdt - fee
            realized_pnl += pnl
            realized_r += pct[name] * r
            remaining = max(0.0, remaining - qclose)
            last_tp_filled = i
            partials.append({"tp": name.upper(), "price": price, "pct": pct[name], "r": r,
                             "qty_closed": round(qclose, 8), "pnl_usdt": round(pnl, 4),
                             "fee_usdt": round(fee, 4)})
            events.append({"event": f"{name}_filled", "timestamp": hit_at, "price": price,
                           "qty": round(qclose, 8), "remaining_qty": round(remaining, 8),
                           "realized_pnl_usdt": round(realized_pnl, 4), "realized_r": round(realized_r, 3),
                           "fees_usdt": round(fee, 4), "exchange_fee_usdt": round(ex_fee, 4),
                           "slippage_usdt": round(sl_fee, 4), "order_type": "maker",
                           "reason": f"{name.upper()} hit — closed {int(pct[name]*100)}%", "source": "outcome"})
            # PART 8 — structural stop move: prefer the chart-structure plan (higher-low /
            # lower-high / support / VWAP) computed from real candles; else BE/lock fallback.
            sp = stop_plan or {}
            if i == 1 and sp.get("stop_after_tp1") is not None:
                new_stop, new_stop_r, basis = sp["stop_after_tp1"], sp["stop_after_tp1_r"], sp["stop_after_tp1_basis"]
            elif i == 2 and sp.get("stop_after_tp2") is not None:
                new_stop, new_stop_r, basis = sp["stop_after_tp2"], sp["stop_after_tp2_r"], sp["stop_after_tp2_basis"]
            else:
                new_stop_r = 0.0 if i == 1 else (0.5 if i == 2 else 2.0)
                new_stop = entry + (new_stop_r * risk if long else -new_stop_r * risk)
                basis = "be" if new_stop_r == 0 else "lock"
            # never worse than current protection
            better = (new_stop > cur_stop) if long else (new_stop < cur_stop)
            if better:
                struct = basis in _STRUCT_BASES
                events.append({"event": "stop_moved_structural", "timestamp": hit_at, "price": round(new_stop, 8),
                               "qty": None, "remaining_qty": round(remaining, 8), "realized_pnl_usdt": None,
                               "realized_r": round(new_stop_r, 3), "fees_usdt": None, "order_type": "taker",
                               "stop_basis": basis,
                               "reason": f"after {name.upper()} → {basis.replace('_', ' ')} at {new_stop_r:+.2f}R "
                                         f"({'structural protection' if struct else 'BE/lock fallback'})",
                               "source": "structural_stop_plan" if struct else "model_f"})
                cur_stop, cur_stop_r = new_stop, new_stop_r

        # remainder exit
        status = "closed"
        if remaining > 1e-9:
            stop_hit = out.get("stop_hit_at")
            if outcome == "win" and last_tp_filled >= 3:
                status = "closed_win"
            elif stop_hit:
                rr = cur_stop_r
                ex_fee = remaining * cur_stop * cm["taker"]   # stop remainder = market/taker
                sl_fee = remaining * cur_stop * slip
                fee = ex_fee + sl_fee
                tot_exch += ex_fee; tot_slip += sl_fee
                pnl = (remaining / qty0) * rr * risk_usdt - fee
                realized_pnl += pnl; realized_r += (remaining / qty0) * rr
                events.append({"event": "stop_filled", "timestamp": stop_hit, "price": cur_stop,
                               "qty": round(remaining, 8), "remaining_qty": 0.0,
                               "realized_pnl_usdt": round(realized_pnl, 4), "realized_r": round(realized_r, 3),
                               "fees_usdt": round(fee, 4), "exchange_fee_usdt": round(ex_fee, 4),
                               "slippage_usdt": round(sl_fee, 4), "order_type": "taker",
                               "reason": "remainder stopped at current stop", "source": "outcome"})
                remaining = 0.0
                status = "stopped" if last_tp_filled == 0 else "closed_partial_stop"
            elif outcome == "expired":
                mfe = out.get("max_favorable_excursion_r")
                # expired remainder closes flat at implied price from final_r (or 0R)
                rr = 0.0
                exit_px = entry  # implied ~BE for expired remainder
                ex_fee = remaining * exit_px * cm["taker"]   # expiry remainder = market/taker
                sl_fee = remaining * exit_px * slip
                fee = ex_fee + sl_fee
                tot_exch += ex_fee; tot_slip += sl_fee
                pnl = (remaining / qty0) * rr * risk_usdt - fee
                realized_pnl += pnl; realized_r += (remaining / qty0) * rr
                events.append({"event": "expired_exit", "timestamp": out.get("checked_at"), "price": round(exit_px, 8),
                               "qty": round(remaining, 8), "remaining_qty": 0.0,
                               "realized_pnl_usdt": round(realized_pnl, 4), "realized_r": round(realized_r, 3),
                               "fees_usdt": round(fee, 4), "exchange_fee_usdt": round(ex_fee, 4),
                               "slippage_usdt": round(sl_fee, 4), "order_type": "taker",
                               "reason": f"validity window ended (MFE {mfe}R) — remainder closed flat",
                               "source": "outcome"})
                remaining = 0.0
                status = "expired" if last_tp_filled == 0 else "closed_partial_expired"
            else:
                # still active with remainder
                status = (f"tp{last_tp_filled}_filled_active" if last_tp_filled else "entry_filled_active")
        else:
            status = "closed_win"

        if remaining > 1e-9:
            events.append({"event": "position_active", "timestamp": out.get("checked_at"), "price": None,
                           "qty": None, "remaining_qty": round(remaining, 8),
                           "realized_pnl_usdt": round(realized_pnl, 4), "realized_r": round(realized_r, 3),
                           "fees_usdt": None, "order_type": None,
                           "reason": (f"TP{last_tp_filled} filled · waiting next target" if last_tp_filled
                                      else "entry filled · waiting TP1"), "source": "derived"})
        else:
            events.append({"event": "position_closed", "timestamp": (events[-1].get("timestamp") if events else None),
                           "price": None, "qty": None, "remaining_qty": 0.0,
                           "realized_pnl_usdt": round(realized_pnl, 4), "realized_r": round(realized_r, 3),
                           "fees_usdt": None, "order_type": None, "reason": f"position closed ({status})",
                           "source": "derived"})

        return _assemble(signal_id, sig, out, sz, entry, stop0, risk, long, events, partials, status,
                         round(realized_pnl, 4), round(realized_r, 3), risk_usdt, conn,
                         cur_stop=cur_stop, cur_stop_r=cur_stop_r, remaining_qty=round(remaining, 8),
                         cm=cm, tot_exch=tot_exch, tot_slip=tot_slip)
    finally:
        conn.close()


def missed_opportunities(limit: int = 30, min_age_min: float = 15.0) -> dict:
    """PART 9 — journal of signals whose entry NEVER triggered (genuine misses/late),
    with would-have-entered price + post-signal favorable move (MFE if recorded). The
    MSTR case (entry triggered, then expired) is NOT a miss and is excluded."""
    conn = _ro_conn()
    out = {"available": False, "items": [], "live_locked": True}
    if conn is None:
        return out
    try:
        rows = conn.execute(
            "SELECT s.signal_id, s.symbol, s.direction, s.asset_class, s.mode, s.created_at, "
            "s.entry_trigger, s.suggested_entry, "
            "o.entry_triggered, o.final_outcome, o.max_favorable_excursion_r, o.checked_at "
            "FROM proposed_signals s LEFT JOIN signal_outcomes o ON o.signal_id=s.signal_id "
            "WHERE COALESCE(o.entry_triggered,0)=0 "
            "AND (o.final_outcome IN ('expired','missed_no_entry') OR o.final_outcome IS NULL) "
            "ORDER BY s.created_at DESC LIMIT 200").fetchall()
        items = []
        now = datetime.now(timezone.utc)
        seen = set()
        for r in rows:
            r = dict(r)
            sid = r["signal_id"]
            if sid in seen:
                continue
            seen.add(sid)
            ct = _parse(r.get("created_at"))
            age = ((now - ct).total_seconds() / 60.0) if ct else None
            if age is not None and age < min_age_min:
                continue
            mfe = r.get("max_favorable_excursion_r")
            items.append({
                "signal_id": sid, "symbol": r["symbol"], "direction": r["direction"],
                "asset_class": r["asset_class"], "mode": r["mode"], "created_at": r["created_at"],
                "late_minutes": round(age, 0) if age is not None else None,
                "would_have_entered_price": r.get("entry_trigger") or r.get("suggested_entry"),
                "max_favorable_move_r": mfe,
                "reason": ("entry trigger never reached within validity window"
                           if (r.get("final_outcome") in ("expired", "missed_no_entry")) else "still pending entry"),
                "would_have_been_profitable": bool(mfe is not None and mfe >= 1.0),
            })
            if len(items) >= limit:
                break
        return {"available": True, "items": items, "count": len(items), "live_locked": True,
                "note": ("Signals whose entry never triggered (missed/late). Entry-then-expired "
                         "trades like MSTR are NOT here — they did fill and are in Closed.")}
    finally:
        conn.close()


def _regime_with_market_fallback(raw, asset_class) -> dict:
    """PART 14 — normalize the per-signal regime; if it is empty/unknown, fall back to the
    current market-dashboard regime for this asset class (labelled `· market`, with a reason)
    instead of a bare `Unknown`. Read-only display field; never consumed by actionability."""
    reg = normalize_regime(raw)
    if reg.get("regime") != "unknown":
        return reg
    try:
        from app import market_dashboard
        snap = market_dashboard.latest_snapshot() or {}
        key = "stocks_regime" if str(asset_class or "").lower().startswith("stock") else "crypto_regime"
        mkt = snap.get(key)
        if mkt:
            m = normalize_regime(mkt, source="market_snapshot")
            if m.get("regime") != "unknown":
                m["label"] = f"{m['label']} · market"
                m["reason"] = "per-signal regime empty; using current market regime"
                return m
    except Exception:
        pass
    return reg


def _read_paper_tp(conn, signal_id: str) -> dict | None:
    """PART 3 — read the persisted structural paper-TP set (signal_paper_tp) if present.
    Read-only; the table is written by the crypto-ai-desk paper path. None if absent."""
    try:
        cur = conn.execute(
            "SELECT tp_set_type, confidence, candles_used, volume_profile_supported, "
            "mechanical_tp1, mechanical_tp2, mechanical_tp3, "
            "active_paper_tp1, active_paper_tp2, active_paper_tp3, "
            "tp1_source, tp2_source, tp3_source FROM signal_paper_tp WHERE signal_id=?",
            (signal_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        # PART 9: never present volume-profile support as active unless it truly is (vp flag = 1).
        d["vp_active"] = bool(d.get("volume_profile_supported"))
        return d
    except Exception:
        return None  # table may not exist on an un-refreshed DB


def _read_entry_mode(conn, signal_id: str) -> dict | None:
    """PART 4 — read the persisted paper entry-mode classification (signal_entry_mode)."""
    try:
        cur = conn.execute(
            "SELECT entry_mode, entry_style, suggested_entry, confidence, "
            "extension_atr, momentum_atr, dist_to_level_atr, reason "
            "FROM signal_entry_mode WHERE signal_id=?", (signal_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def _read_stock_direction(conn, signal_id: str) -> dict | None:
    """PART 5 — read the multi-factor stock direction score (stock_direction_score)."""
    try:
        cur = conn.execute(
            "SELECT direction, direction_score, dir_label, production_direction, "
            "factors_used, agreement, agrees_with_production, vote_ema, vote_vwap, "
            "vote_pdhl, vote_momentum, vote_rs_spy, vote_mstr_btc, rs_spy_20d, reason "
            "FROM stock_direction_score WHERE signal_id=?", (signal_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def _read_entry_latency(conn, signal_id: str) -> dict | None:
    """PART 6 — read the entry-latency root-cause classification (entry_latency_audit)."""
    try:
        cur = conn.execute(
            "SELECT cause, recorded_latency_min, data_gap_min, in_band_before_recorded, reason "
            "FROM entry_latency_audit WHERE signal_id=?", (signal_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None


_STRUCT_BASES = {"higher_low", "lower_high", "support", "resistance", "vwap"}


def _read_stop_plan(conn, signal_id: str) -> dict | None:
    """PART 8 — read the per-signal structural stop-move plan (signal_stop_plan)."""
    try:
        cur = conn.execute(
            "SELECT stop_after_tp1, stop_after_tp1_r, stop_after_tp1_basis, "
            "stop_after_tp2, stop_after_tp2_r, stop_after_tp2_basis, prefers_structure "
            "FROM signal_stop_plan WHERE signal_id=?", (signal_id,))
        row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def _assemble(signal_id, sig, out, sz, entry, stop0, risk, long, events, partials, status,
              realized_pnl, realized_r, risk_usdt, conn, cur_stop=None, cur_stop_r=None, remaining_qty=0.0,
              cm=None, tot_exch=0.0, tot_slip=0.0):
    cm = cm or _cost_model(sig.get("asset_class"), sig.get("symbol"), sig.get("mode"))
    # asset-aware funding: crypto perps carry approx funding over the hold; stocks = 0 (known-zero)
    funding = round((sz.get("notional") or 0.0) * cm["funding_rate"] * cm["funding_intervals"], 4)
    reg = _regime_with_market_fallback(sig.get("market_regime"), sig.get("asset_class"))
    ptp = _read_paper_tp(conn, signal_id)
    emode = _read_entry_mode(conn, signal_id)
    sdir = (_read_stock_direction(conn, signal_id)
            if str(sig.get("asset_class") or "").lower().startswith("stock") else None)
    elat = _read_entry_latency(conn, signal_id)
    splan = _read_stop_plan(conn, signal_id)
    # When a structural paper-TP set exists (STRUCTURAL/HYBRID), the paper book uses those
    # levels instead of the mechanical ATR ladder; show both so the source is transparent.
    use_struct = bool(ptp) and (ptp.get("tp_set_type") in ("STRUCTURAL", "HYBRID"))
    _active = {"TP1": (ptp or {}).get("active_paper_tp1"), "TP2": (ptp or {}).get("active_paper_tp2"),
               "TP3": (ptp or {}).get("active_paper_tp3")} if use_struct else {}
    _src = {"TP1": (ptp or {}).get("tp1_source"), "TP2": (ptp or {}).get("tp2_source"),
            "TP3": (ptp or {}).get("tp3_source")}
    def tpr(p):
        return _r_of(p, entry, risk, long)
    # $ at each TP (on its partial slice) + max loss at stop (remaining at entry-time = full)
    ladder = []
    for name, mech_price in (("TP1", sig.get("tp1")), ("TP2", sig.get("tp2")), ("TP3", sig.get("tp3"))):
        price = _active.get(name) if (use_struct and _active.get(name) is not None) else mech_price
        r = tpr(price)
        pctv = dict(PARTIALS).get(name.lower(), 0.0)
        ladder.append({"label": name, "price": price, "r": r,
                       "pct_closed": pctv,
                       "mechanical_price": mech_price,
                       "tp_source": _src.get(name) if use_struct else "atr_ladder",
                       "pnl_if_filled_usdt": round(pctv * (r or 0) * risk_usdt, 2) if r else None})
    max_loss = round(-1.0 * risk_usdt, 2)
    return {
        "available": True, "signal_id": signal_id, "symbol": sig.get("symbol"),
        "direction": sig.get("direction"), "asset_class": sig.get("asset_class"),
        "mode": sig.get("mode"), "tier": sig.get("tier"), "playbook": sig.get("setup_type"),
        "status": status, "regime": reg,
        "position": {
            "equity_at_entry_usdt": INIT_EQUITY, "risk_usdt": round(risk_usdt, 2),
            "risk_pct": RISK_PCT, "notional_usdt": sz["notional"], "qty": round(sz["qty"], 8),
            "margin_usdt": sz["margin"], "leverage": sz["leverage"], "leverage_reason": sz["leverage_reason"],
            "liquidation_price": sz["liq_price"], "liq_distance_pct": round(sz["liq_dist_pct"], 4),
            "stop_distance_pct": round(sz["stop_dist_pct"], 4), "liquidation_buffer_ok": sz["liq_buffer_ok"],
            "risk_capped": sz["risk_capped"], "fee_profile": cm["fee_profile"], "fee_source": cm["fee_source"],
        },
        # asset-aware execution costs, split (stocks are NEVER priced as a Bybit perp; no perp funding)
        "cost_model": {
            "asset_class": sig.get("asset_class"), "fee_profile": cm["fee_profile"],
            "fee_source": cm["fee_source"], "exchange_fees_usdt": round(tot_exch, 4),
            "slippage_usdt": round(tot_slip, 4), "funding_usdt": funding,
            "funding_known": (not cm["is_stock"]),
            "total_cost_usdt": round(tot_exch + tot_slip + funding, 4),
            "note": ("stocks/ETFs priced with the equity/ETF model (commission-free + ~1bp, no perp "
                     "funding); crypto with the perp profile + approximate funding"),
        },
        "price_ladder": {
            "entry": entry, "initial_stop": stop0, "current_stop": cur_stop if cur_stop is not None else stop0,
            "current_stop_r": cur_stop_r, "tps": ladder, "max_loss_at_stop_usdt": max_loss,
        },
        # PART 3 — which TP set the paper book used (structural-from-chart vs mechanical ATR).
        "paper_tp": ({
            "tp_set_type": ptp.get("tp_set_type"), "confidence": ptp.get("confidence"),
            "candles_used": ptp.get("candles_used"), "applied": use_struct,
            "mechanical": [ptp.get("mechanical_tp1"), ptp.get("mechanical_tp2"), ptp.get("mechanical_tp3")],
            "active": [ptp.get("active_paper_tp1"), ptp.get("active_paper_tp2"), ptp.get("active_paper_tp3")],
            "sources": [ptp.get("tp1_source"), ptp.get("tp2_source"), ptp.get("tp3_source")],
        } if ptp else {"tp_set_type": "ATR_LADDER", "applied": False,
                       "note": "no structural paper-TP record; mechanical ATR ladder shown"}),
        # PART 4 — which entry mode the paper book uses (breakout/momentum/retest vs pullback).
        "entry_mode": (emode or {"entry_mode": "PULLBACK_LIMIT", "entry_style": "limit",
                                 "note": "no entry-mode record; production pullback default"}),
        # PART 5 — multi-factor stock direction (EMA + VWAP + PDH/PDL + momentum + RS + MSTR·BTC).
        "stock_direction": sdir,
        # PART 6 — entry-latency root cause (DATA_GAP_LATE coverage vs DETECTION_LATENCY bug).
        "entry_latency": elat,
        # PART 8 — structural stop-move plan (prefers chart structure over BE/lock).
        "stop_protection": ({
            "prefers_structure": bool(splan.get("prefers_structure")),
            "after_tp1": {"price": splan.get("stop_after_tp1"), "r": splan.get("stop_after_tp1_r"),
                          "basis": splan.get("stop_after_tp1_basis")},
            "after_tp2": {"price": splan.get("stop_after_tp2"), "r": splan.get("stop_after_tp2_r"),
                          "basis": splan.get("stop_after_tp2_basis")},
        } if splan else {"prefers_structure": False, "note": "no stop plan; BE/lock fallback"}),
        "partials": partials, "events": events,
        "remaining_qty": remaining_qty,
        "realized_pnl_usdt": realized_pnl, "realized_r": realized_r,
        "blended_r": realized_r,
        "audit": {
            "touch_final_r": out.get("final_r"),
            "mfe_r": out.get("max_favorable_excursion_r"), "mae_r": out.get("max_adverse_excursion_r"),
            "outcome": out.get("final_outcome"), "entry_triggered_at": out.get("entry_triggered_at"),
            "note": ("blended_r = partial-exit accounting (TP1 33%/TP2 33%/TP3 34%); "
                     "touch_final_r is the optimistic highest-TP-touched signal-quality metric"),
        },
        "live_locked": True, "auto_live_locked": True,
    }
