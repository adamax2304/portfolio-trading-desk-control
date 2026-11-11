"""Paper portfolio read-model for the Control Plane (READ-ONLY).

Reads the desk-side `paper_portfolio_ledger` (written by the crypto-ai-desk paper
backfill: $5000 start, 0.5% risk, sizing, dynamic leverage, fees) and exposes
equity cards, a portfolio trade list with USD fields, and per-trade chart events
(entry/stop/TP/exit markers). Never writes; never enables live/exec.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from app.config import get_settings


def _ro_conn():
    s = get_settings()
    if s.demo_mode or not s.has_desk_db:
        return None
    try:
        conn = sqlite3.connect(f"file:{s.desk_db_path}?mode=ro", uri=True, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception:
        return None


def _has_table(conn, name) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def _parse(ts):
    if not ts:
        return None
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


ACTIVE_FEE_PROFILE = "bybit_non_vip_usdt_perp"   # the headline profile; ledger holds several
STRUCTURAL_MAKER_PROFILE = "bybit_structural_maker_first"  # PART 6: active structural+maker-first paper book


def _profiles_available(conn) -> list[str]:
    try:
        return [r[0] for r in conn.execute(
            "SELECT DISTINCT fee_profile FROM paper_portfolio_ledger ORDER BY fee_profile")]
    except Exception:
        return []


def portfolio_summary(fee_profile: str | None = None) -> dict:
    fee_profile = fee_profile or ACTIVE_FEE_PROFILE
    conn = _ro_conn()
    base = {"available": False, "reason": "demo or no desk DB",
            "initial_equity_usdt": 5000, "risk_per_trade_pct": 0.005,
            "fee_profile": fee_profile, "live_locked": True, "auto_live_locked": True}
    if conn is None:
        return base
    try:
        if not _has_table(conn, "paper_portfolio_ledger"):
            base["reason"] = "paper_portfolio_ledger not built yet (run paper_portfolio_backfill)"
            return base
        avail = _profiles_available(conn)
        if fee_profile not in avail and avail:
            fee_profile = ACTIVE_FEE_PROFILE if ACTIVE_FEE_PROFILE in avail else avail[0]
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM paper_portfolio_ledger WHERE event_type='exit' AND fee_profile=? "
            "ORDER BY timestamp ASC, id ASC", (fee_profile,))]
        if not rows:
            base["reason"] = "ledger empty"
            return base
        init = 5000.0
        equity = rows[-1]["equity_after"] or init
        peak = init; max_dd = 0.0
        for r in rows:
            eq = r["equity_after"] or init
            peak = max(peak, eq)
            max_dd = max(max_dd, (peak - eq) / peak if peak else 0.0)
        now = datetime.now(timezone.utc)
        d1 = now - timedelta(hours=24); d7 = now - timedelta(days=7)

        def net_since(since):
            return round(sum((r["net_pnl_usdt"] or 0) for r in rows if (_parse(r["timestamp"]) or now) >= since), 2)

        def r_since(since):
            return round(sum((r["paper_execution_r"] or 0) for r in rows if (_parse(r["timestamp"]) or now) >= since), 2)

        wins = sum(1 for r in rows if (r["net_pnl_usdt"] or 0) > 0)
        losses = sum(1 for r in rows if (r["net_pnl_usdt"] or 0) < 0)
        be = sum(1 for r in rows if (r["net_pnl_usdt"] or 0) == 0)
        # PART 1: keep exchange fees and slippage SEPARATE (they are distinct execution costs).
        exchange_fees = round(sum((r["fees_usdt"] or 0) for r in rows), 2)
        slippage = round(sum((r["slippage_usdt"] or 0) for r in rows), 2)
        funding = round(sum((r["funding_usdt"] or 0) for r in rows), 2)
        funding_known = any((r["funding_usdt"] or 0) != 0 for r in rows)
        total_exec_cost = round(exchange_fees + slippage + funding, 2)
        # leverage / margin visibility (PART 5)
        levs = [r.get("leverage_used") for r in rows if r.get("leverage_used")]
        # risk-capped = actual risk fell below the 0.5% target (tight stop hit the notional cap)
        risk_capped = sum(1 for r in rows if (r.get("risk_pct") or 0) > 0 and (r.get("risk_pct") or 1) < 0.00499)
        return {
            "available": True, "fee_profile": fee_profile,
            "fee_profiles_available": avail,
            "fee_estimated_any": any(int(r.get("fee_estimated") or 0) for r in rows),
            "avg_leverage": round(sum(levs) / len(levs), 2) if levs else 0,
            "max_leverage": max(levs) if levs else 0,
            "risk_capped_trades": risk_capped,
            "initial_equity_usdt": init, "equity_usdt": round(equity, 2),
            "risk_per_trade_pct": 0.005,
            "net_pnl_usdt_total": round(equity - init, 2),
            "return_pct": round((equity / init - 1) * 100, 2),
            "today_net_pnl_usdt": net_since(d1), "today_net_r": r_since(d1),
            "d7_net_pnl_usdt": net_since(d7), "d7_net_r": r_since(d7),
            "max_drawdown_pct": round(max_dd * 100, 2),
            # PART 1: split execution costs — exchange fees vs slippage vs funding, + total.
            "exchange_fees_usdt": exchange_fees,
            "slippage_usdt": slippage,
            "funding_usdt": funding, "funding_known": funding_known,
            "total_execution_cost_usdt": total_exec_cost,
            "fees_paid_usdt": total_exec_cost,  # DEPRECATED alias = total execution cost (was fees+slippage)
            "trades": len(rows),
            "wins": wins, "losses": losses, "breakeven": be,
            # historical/derived ledger → no live open positions/margin
            "open_positions": 0, "open_risk_usdt": 0.0, "margin_used_usdt": 0.0,
            "note": ("Derived historical paper portfolio ($5000 start, 0.5% risk, dynamic leverage). "
                     "Net USD is gross − exchange fees − slippage − funding. No live."),
            "live_locked": True, "auto_live_locked": True,
        }
    finally:
        conn.close()


def _parse_b_execution(led_b: dict) -> dict | None:
    """Parse the structural+maker-first ledger row's close_reason
    ('...|<entry>E/<exit>X|<TP_SET_LABEL>') into a per-trade execution summary."""
    if not led_b:
        return None
    reason = str(led_b.get("close_reason") or "")
    entry_ot = exit_ot = None
    tp_label = None
    for tok in reason.split("|"):
        if "E/" in tok and "X" in tok:   # '<entry>E/<exit>X'
            try:
                e, x = tok.split("/")
                entry_ot = e.replace("E", "").strip()
                exit_ot = x.replace("X", "").strip()
            except Exception:
                pass
        elif tok in ("STRUCTURAL", "HYBRID", "STRUCTURAL_FALLBACK_ATR", "NO_VALID_TP"):
            tp_label = tok
    return {
        "fee_profile": led_b.get("fee_profile"), "entry_order_type": entry_ot,
        "exit_order_type": exit_ot, "tp_set_label": tp_label,
        "net_pnl_usdt": led_b.get("net_pnl_usdt"), "fees_usdt": led_b.get("fees_usdt"),
        "slippage_usdt": led_b.get("slippage_usdt"), "leverage_used": led_b.get("leverage_used"),
        "position_notional_usdt": led_b.get("position_notional_usdt"),
        "margin_used_usdt": led_b.get("margin_used_usdt"), "risk_usdt": led_b.get("risk_usdt"),
        "paper_execution_r": led_b.get("paper_execution_r"),
        "stop_order_type": "taker",  # stops always taker for safety
    }


def _profile_meta(conn, profile: str) -> dict:
    """PART 11: latest timestamp + trade count + signal-set for a fee_profile, to verify an A/B
    comparison covers the same trades over the same period (not a stale vs fresh mismatch)."""
    rows = conn.execute(
        "SELECT timestamp, signal_id FROM paper_portfolio_ledger WHERE event_type='exit' AND fee_profile=?",
        (profile,)).fetchall()
    sigs = frozenset(r["signal_id"] for r in rows if r["signal_id"])
    ts = [str(r["timestamp"]) for r in rows if r["timestamp"]]
    return {"profile": profile, "trades": len(rows), "latest_ts": max(ts) if ts else None,
            "signal_ids": sigs}


def portfolio_compare() -> dict:
    """PART 6 — A (mechanical taker) vs B (structural + maker-first + fee-aware + 2x).
    Both books are derived paper ledgers; read-only. B's per-trade execution model is
    encoded in close_reason as '...|<entry>E/<exit>X|<TP_SET_LABEL>'."""
    conn = _ro_conn()
    out = {"available": False, "live_locked": True, "auto_live_locked": True,
           "production_tp_unchanged": True, "paper_tp": "structural_maker_first"}
    if conn is None or not _has_table(conn, "paper_portfolio_ledger"):
        return out
    try:
        avail = _profiles_available(conn)
        if STRUCTURAL_MAKER_PROFILE not in avail:
            out["reason"] = "structural/maker-first ledger not built (run structural_maker_backfill)"
            return out
        a = portfolio_summary(ACTIVE_FEE_PROFILE)
        b = portfolio_summary(STRUCTURAL_MAKER_PROFILE)
        brows = [dict(r) for r in conn.execute(
            "SELECT close_reason FROM paper_portfolio_ledger WHERE event_type='exit' AND fee_profile=?",
            (STRUCTURAL_MAKER_PROFILE,))]
        maker_entry = sum(1 for r in brows if "makerE" in (r["close_reason"] or ""))
        taker_entry = sum(1 for r in brows if "takerE" in (r["close_reason"] or ""))
        maker_exit = sum(1 for r in brows if "makerX" in (r["close_reason"] or ""))
        structural = sum(1 for r in brows if any(
            lbl in (r["close_reason"] or "") for lbl in ("|STRUCTURAL", "|HYBRID")))
        atr_fallback = sum(1 for r in brows if "STRUCTURAL_FALLBACK_ATR" in (r["close_reason"] or ""))
        fees_saved = round((a.get("fees_paid_usdt") or 0) - (b.get("fees_paid_usdt") or 0), 2)
        # leverage_policy reflects the ACTUAL max leverage in the ledger (no hardcode) so
        # the label can never go stale vs the rebuilt data (max_5x_safe after a 5x rebuild).
        _maxlev = max(int(a.get("max_leverage") or 0), int(b.get("max_leverage") or 0))
        # PART 11: comparability — A and B must cover the SAME trades over the SAME period.
        mA, mB = _profile_meta(conn, ACTIVE_FEE_PROFILE), _profile_meta(conn, STRUCTURAL_MAKER_PROFILE)
        same_signals = mA["signal_ids"] == mB["signal_ids"]
        only_a = len(mA["signal_ids"] - mB["signal_ids"])
        only_b = len(mB["signal_ids"] - mA["signal_ids"])
        cmp_warnings = []
        if not same_signals:
            cmp_warnings.append(f"trade sets differ (A-only {only_a}, B-only {only_b}) — not a like-for-like A/B")
        if mA["latest_ts"] and mB["latest_ts"]:
            try:
                gap_h = abs((_parse(mA["latest_ts"]) - _parse(mB["latest_ts"])).total_seconds()) / 3600
                if gap_h > 6:
                    cmp_warnings.append(f"profiles last updated {round(gap_h,1)}h apart — one ledger is stale; rebuild both")
            except Exception:
                pass
        comparison_integrity = {
            "comparable": same_signals and not cmp_warnings,
            "A": {"trades": mA["trades"], "latest_ts": mA["latest_ts"]},
            "B": {"trades": mB["trades"], "latest_ts": mB["latest_ts"]},
            "common_trades": len(mA["signal_ids"] & mB["signal_ids"]),
            "warnings": cmp_warnings}
        return {
            "available": True, "live_locked": True, "auto_live_locked": True,
            "comparison_integrity": comparison_integrity,
            "production_tp_unchanged": True, "paper_tp": "structural_maker_first",
            "leverage_policy": f"max_{_maxlev or 5}x_safe",
            "mechanical_taker": {
                "fee_profile": ACTIVE_FEE_PROFILE, "equity_usdt": a.get("equity_usdt"),
                "return_pct": a.get("return_pct"), "fees_paid_usdt": a.get("fees_paid_usdt"),
                "max_drawdown_pct": a.get("max_drawdown_pct"), "avg_leverage": a.get("avg_leverage"),
                "max_leverage": a.get("max_leverage")},
            "structural_maker_first": {
                "fee_profile": STRUCTURAL_MAKER_PROFILE, "equity_usdt": b.get("equity_usdt"),
                "return_pct": b.get("return_pct"), "fees_paid_usdt": b.get("fees_paid_usdt"),
                "max_drawdown_pct": b.get("max_drawdown_pct"), "avg_leverage": b.get("avg_leverage"),
                "max_leverage": b.get("max_leverage")},
            "delta_return_pct": round((b.get("return_pct") or 0) - (a.get("return_pct") or 0), 2),
            "fees_saved_usdt": fees_saved,
            "maker_entries": maker_entry, "taker_entries": taker_entry, "maker_exits": maker_exit,
            "structural_tp_trades": structural, "atr_fallback_tp_trades": atr_fallback,
            "note": ("B re-prices the same Model-F R with maker-first fees + fee-aware skips + "
                     "max-2x sizing. Full swing/VP structural TP applies to FORWARD trades "
                     "(live candles); this historical book uses ATR-fallback TP labels."),
        }
    finally:
        conn.close()


def portfolio_by_asset(fee_profile: str | None = None) -> dict:
    """PART 3: crypto-only vs stocks-only P&L contribution. The ledger has no asset_class, so we
    join proposed_signals. Surfaces that STOCKS are currently priced under the crypto-perp fee
    profile (a known cost-model bug) — the per-asset split makes that visible until the engine adds a
    stock/ETF cost model. Read-only; no live."""
    fee_profile = fee_profile or ACTIVE_FEE_PROFILE
    conn = _ro_conn()
    out = {"available": False, "fee_profile": fee_profile, "live_locked": True, "auto_live_locked": True}
    if conn is None or not _has_table(conn, "paper_portfolio_ledger"):
        return out
    try:
        rows = [dict(r) for r in conn.execute(
            "SELECT l.*, COALESCE(p.asset_class,'unknown') AS asset_class "
            "FROM paper_portfolio_ledger l LEFT JOIN proposed_signals p ON l.signal_id = p.signal_id "
            "WHERE l.event_type='exit' AND l.fee_profile=?", (fee_profile,))]
        if not rows:
            out["reason"] = "ledger empty"
            return out

        def book(subset: list[dict], asset: str) -> dict:
            n = len(subset)
            net = round(sum((r["net_pnl_usdt"] or 0) for r in subset), 2)
            gross = round(sum((r["gross_pnl_usdt"] or 0) for r in subset), 2)
            ef = round(sum((r["fees_usdt"] or 0) for r in subset), 2)
            sl = round(sum((r["slippage_usdt"] or 0) for r in subset), 2)
            fu = round(sum((r["funding_usdt"] or 0) for r in subset), 2)
            wins = sum(1 for r in subset if (r["net_pnl_usdt"] or 0) > 0)
            # cost-model appropriateness is judged from the ACTUAL cost model used (fee_source),
            # not the book id: stocks priced under the equity/ETF model are correct even though the
            # ledger row's fee_profile carries the book identity.
            # `fee_profile_used` must reflect the ACTUAL cost model applied (from the ledger row's
            # fee_source), NOT the shared book id — stocks are priced with the equity/ETF model and
            # must never be labelled as a Bybit perp.
            srcs = " ".join(str(r.get("fee_source") or "").lower() for r in subset)
            is_equity_model = ("equity" in srcs or "etf" in srcs)
            if asset == "stocks":
                cost_model_ok = is_equity_model
                profile_used = "stock_etf_default" if is_equity_model else fee_profile
                model_label = ("US equity/ETF paper model (commission-free + ~1bp; no perp funding)"
                               if is_equity_model else "crypto-perp (MISPRICED — pending stock model)")
            else:
                cost_model_ok = True
                profile_used = fee_profile
                model_label = "crypto perp profile"
            return {"asset_class": asset, "trades": n, "net_pnl_usdt": net, "gross_pnl_usdt": gross,
                    "exchange_fees_usdt": ef, "slippage_usdt": sl, "funding_usdt": fu,
                    "total_execution_cost_usdt": round(ef + sl + fu, 2),
                    "win_rate": round(100 * wins / n, 1) if n else 0.0,
                    "fee_profile_used": profile_used, "fee_model_label": model_label,
                    "cost_model_appropriate": cost_model_ok,
                    "cost_model_note": (None if cost_model_ok else
                        "STOCKS priced under crypto-perp fees — MISPRICED; expected equity/ETF model")}

        crypto = book([r for r in rows if r["asset_class"] == "crypto"], "crypto")
        stocks = book([r for r in rows if r["asset_class"] == "stocks"], "stocks")
        out.update({"available": True, "crypto": crypto, "stocks": stocks,
                    "unknown_asset_trades": sum(1 for r in rows if r["asset_class"] not in ("crypto", "stocks")),
                    "note": "Per-asset P&L contribution (shared $5000 book). Crypto priced with the "
                            "perp profile; stocks with the US equity/ETF paper model (commission-free "
                            "+ ~1bp, no perp funding). Net USD is the authoritative profitability."})
        return out
    finally:
        conn.close()


def portfolio_trades(limit: int = 100, fee_profile: str | None = None) -> list[dict]:
    fee_profile = fee_profile or ACTIVE_FEE_PROFILE
    conn = _ro_conn()
    if conn is None or not _has_table(conn, "paper_portfolio_ledger"):
        return []
    try:
        rows = conn.execute(
            "SELECT * FROM paper_portfolio_ledger WHERE event_type='exit' AND fee_profile=? "
            "ORDER BY timestamp DESC, id DESC LIMIT ?", (fee_profile, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def chart_events(signal_id: str) -> dict:
    """Entry / stop / TP1-3 / moved-stop / exit markers for one trade — for chart
    overlay. Joins proposed_signals + signal_outcomes + paper_execution_outcomes."""
    conn = _ro_conn()
    empty = {"available": False, "signal_id": signal_id, "levels": [], "events": []}
    if conn is None:
        return empty
    try:
        sig = conn.execute(
            "SELECT symbol,direction,suggested_entry,entry_trigger,entry_low,invalidation,stop_loss,"
            "tp1,tp2,tp3 FROM proposed_signals WHERE signal_id=?", (signal_id,)).fetchone()
        if not sig:
            return empty
        sig = dict(sig)
        out = conn.execute(
            "SELECT entry_triggered_at,entry_price_used,stop_hit_at,tp1_hit_at,tp2_hit_at,tp3_hit_at,"
            "max_favorable_excursion_r,max_adverse_excursion_r,final_outcome FROM signal_outcomes "
            "WHERE signal_id=? ORDER BY checked_at DESC, id DESC LIMIT 1", (signal_id,)).fetchone()
        out = dict(out) if out else {}
        pe = {}
        if _has_table(conn, "paper_execution_outcomes"):
            r = conn.execute("SELECT * FROM paper_execution_outcomes WHERE signal_id=?", (signal_id,)).fetchone()
            pe = dict(r) if r else {}
        entry = sig.get("entry_trigger") or sig.get("suggested_entry") or sig.get("entry_low")
        stop = sig.get("invalidation") or sig.get("stop_loss")
        long = str(sig.get("direction") or "long").lower() != "short"
        risk = abs((entry or 0) - (stop or 0))

        def r_of(price):
            if not price or not entry or not risk:
                return None
            return round(((price - entry) if long else (entry - price)) / risk, 3)

        # level lines with EXACT R-multiples (not "+1R" by name)
        levels = [
            {"label": "Entry", "price": entry, "kind": "entry", "r_multiple": 0.0},
            {"label": "Initial stop", "price": stop, "kind": "stop", "r_multiple": -1.0},
            {"label": "TP1", "price": sig.get("tp1"), "kind": "tp", "r_multiple": r_of(sig.get("tp1"))},
            {"label": "TP2", "price": sig.get("tp2"), "kind": "tp", "r_multiple": r_of(sig.get("tp2"))},
            {"label": "TP3", "price": sig.get("tp3"), "kind": "tp", "r_multiple": r_of(sig.get("tp3"))},
        ]
        if pe.get("protection_armed") and entry and risk:
            levels.append({"label": "Stop→BE", "price": round(entry, 10), "kind": "moved_stop", "r_multiple": 0.0})
        if pe.get("lock_armed") and entry and risk:
            lock_price = entry + (0.5 * risk if long else -0.5 * risk)
            levels.append({"label": "Lock +0.5R", "price": round(lock_price, 10), "kind": "moved_stop", "r_multiple": 0.5})

        # markers (richer): entry / tp hits / stop / EXIT (incl. expired) with R + $.
        led = {}
        if _has_table(conn, "paper_portfolio_ledger"):
            lr = conn.execute(
                "SELECT * FROM paper_portfolio_ledger WHERE signal_id=? AND fee_profile=? LIMIT 1",
                (signal_id, ACTIVE_FEE_PROFILE)).fetchone()
            led = dict(lr) if lr else {}
            bl = conn.execute(
                "SELECT * FROM paper_portfolio_ledger WHERE signal_id=? AND fee_profile=? LIMIT 1",
                (signal_id, STRUCTURAL_MAKER_PROFILE)).fetchone()
            led_b = dict(bl) if bl else {}
        markers = []
        if out.get("entry_triggered_at"):
            markers.append({"marker_type": "entry", "timestamp": out["entry_triggered_at"],
                            "price": out.get("entry_price_used") or entry, "label": "Entry",
                            "status": "entry", "reason": "entry_filled", "r_at_marker": 0.0,
                            "pnl_usdt_at_marker": 0.0})
        for k, ts, pr in [("tp1", out.get("tp1_hit_at"), sig.get("tp1")),
                          ("tp2", out.get("tp2_hit_at"), sig.get("tp2")),
                          ("tp3", out.get("tp3_hit_at"), sig.get("tp3"))]:
            if ts:
                markers.append({"marker_type": "tp", "timestamp": ts, "price": pr, "label": k.upper(),
                                "status": "tp", "reason": f"{k}_touched", "r_at_marker": r_of(pr),
                                "pnl_usdt_at_marker": None})
        if out.get("stop_hit_at"):
            markers.append({"marker_type": "stop", "timestamp": out["stop_hit_at"], "price": stop,
                            "label": "Stop", "status": "stop", "reason": "stop_hit", "r_at_marker": -1.0,
                            "pnl_usdt_at_marker": None})
        # EXIT / EXPIRED marker from the paper ledger
        if led:
            reason = led.get("close_reason") or pe.get("close_reason") or ""
            is_expired = bool(led.get("expiry_close_price") is not None) or ("expired" in str(reason))
            exit_px = led.get("exit_price")
            markers.append({
                "marker_type": "expired_exit" if is_expired else "exit",
                "timestamp": led.get("timestamp") or out.get("checked_at"),
                "price": exit_px, "label": "Expired close" if is_expired else "Exit",
                "status": "expired" if is_expired else "exit", "reason": reason,
                "r_at_marker": led.get("paper_execution_r"),
                "pnl_usdt_at_marker": led.get("net_pnl_usdt"),
            })
        # MFE/MAE
        for k, val, kind in [("MFE", out.get("max_favorable_excursion_r"), "mfe"),
                             ("MAE", out.get("max_adverse_excursion_r"), "mae")]:
            if val is not None:
                markers.append({"marker_type": kind, "timestamp": None, "price": None, "label": k,
                                "status": kind, "reason": f"{kind}_r", "r_at_marker": round(val, 3),
                                "pnl_usdt_at_marker": None})

        # PART 5 — true execution markers from the live position lifecycle (partial TP
        # fills, moved/structural stops, expired/missed). Replaces the single misleading
        # exit marker (ETH fix). Local import avoids a circular import.
        lc = None
        try:
            from app.lifecycle import position_lifecycle
            lc = position_lifecycle(signal_id)
        except Exception:
            lc = None
        # shape key (frontend marker glyph) + display label per lifecycle event
        _evt_marker = {"entry_filled": ("entry", "Entry"), "entry_missed": ("missed", "Entry missed"),
                       "tp1_filled": ("tp_fill", "TP1 fill"), "tp2_filled": ("tp_fill", "TP2 fill"),
                       "tp3_filled": ("tp_fill", "TP3 fill"), "stop_moved_structural": ("moved_stop", "Stop moved"),
                       "stop_filled": ("stop", "Stop"), "expired_exit": ("expired_exit", "Expired close"),
                       "late_rejected": ("missed", "Late — rejected")}
        side = "sell" if not long else "buy"   # exit side is opposite of entry; chart-only hint
        if lc and lc.get("available"):
            lc_markers = []
            mid = 0
            for e in lc.get("events", []):
                mt = _evt_marker.get(e["event"])
                if not mt or e.get("price") is None:
                    continue
                mid += 1
                is_exit = e["event"] in ("tp1_filled", "tp2_filled", "tp3_filled", "stop_filled", "expired_exit")
                rem = e.get("remaining_qty")
                lc_markers.append({
                    "marker_id": f"{signal_id}:{mid}:{e['event']}",
                    "marker_type": mt[0], "event_type": e["event"],
                    "timestamp": e.get("timestamp"), "price": e.get("price"),
                    "label": mt[1], "status": mt[0], "side": side if is_exit else ("buy" if long else "sell"),
                    "reason": e.get("reason"),
                    "r_at_marker": e.get("realized_r"), "pnl_usdt_at_marker": e.get("realized_pnl_usdt"),
                    "cumulative_realized_r": e.get("realized_r"),
                    "cumulative_realized_pnl_usdt": e.get("realized_pnl_usdt"),
                    "qty_closed": e.get("qty"), "remaining_qty": rem, "fee_usdt": e.get("fees_usdt"),
                    "order_type": e.get("order_type"), "source_book": "paper_B_structural_maker",
                    "is_partial_exit": bool(is_exit and rem is not None and rem > 1e-12),
                    "is_final_exit": bool(is_exit and (rem is None or rem <= 1e-12))})
            for k, val, kind in [("MFE", out.get("max_favorable_excursion_r"), "mfe"),
                                 ("MAE", out.get("max_adverse_excursion_r"), "mae")]:
                if val is not None:
                    lc_markers.append({"marker_type": kind, "timestamp": None, "price": None, "label": k,
                                       "status": kind, "reason": f"{kind}_r", "r_at_marker": round(val, 3),
                                       "pnl_usdt_at_marker": None})
            pl = lc.get("price_ladder", {})
            lc_levels = [
                {"label": "Entry", "price": pl.get("entry"), "kind": "entry", "r_multiple": 0.0},
                {"label": "Initial stop", "price": pl.get("initial_stop"), "kind": "stop", "r_multiple": -1.0},
            ]
            if pl.get("current_stop") is not None and pl.get("current_stop") != pl.get("initial_stop"):
                lc_levels.append({"label": "Current stop", "price": pl.get("current_stop"),
                                  "kind": "moved_stop", "r_multiple": pl.get("current_stop_r")})
            for t in pl.get("tps", []):
                lc_levels.append({"label": t["label"], "price": t["price"], "kind": "tp",
                                  "r_multiple": t.get("r")})
            markers = lc_markers
            levels = lc_levels

        return {
            "available": True, "signal_id": signal_id, "symbol": sig.get("symbol"),
            "direction": sig.get("direction"),
            "levels": [l for l in levels if l["price"] is not None],
            "lines": [l for l in levels if l["price"] is not None],  # alias for chart overlay
            "markers": markers,
            "source_book": "paper_B_structural_maker",
            "lifecycle": lc if (lc and lc.get("available")) else None,
            "tp_r_exact": {"tp1": r_of(sig.get("tp1")), "tp2": r_of(sig.get("tp2")), "tp3": r_of(sig.get("tp3"))},
            "mfe_r": out.get("max_favorable_excursion_r"), "mae_r": out.get("max_adverse_excursion_r"),
            "paper_execution_r": pe.get("paper_execution_r"),
            # legacy touch = old final_r / highest-TP-touched (optimistic, NOT PnL). It lives in
            # paper_execution_outcomes.touch_r — the ledger has NO touch_r column (was always null).
            "legacy_touch_r": pe.get("touch_r"),
            "stop_current_r": pe.get("stop_current_r"), "close_reason": led.get("close_reason") if led else pe.get("close_reason"),
            "exit_price": led.get("exit_price") if led else None,
            "expiry_close_price": led.get("expiry_close_price") if led else None,
            "expiry_close_price_source": led.get("expiry_close_price_source") if led else None,
            "net_pnl_usdt": led.get("net_pnl_usdt") if led else None,
            "leverage_used": led.get("leverage_used") if led else None,
            "position_notional_usdt": led.get("position_notional_usdt") if led else None,
            "margin_used_usdt": led.get("margin_used_usdt") if led else None,
            "risk_usdt": led.get("risk_usdt") if led else None,
            "tp_quality": {
                "label": "MECHANICAL_ATR_LADDER",
                "volume_profile_supported": "unknown",
                "note": ("Production TPs are a mechanical ATR ladder (close ± 1/2/3·ATR), "
                         "not structural chart levels. Stops are semi-structural. R-multiples above are exact."),
            },
            "paper_execution_b": _parse_b_execution(led_b),
        }
    finally:
        conn.close()
