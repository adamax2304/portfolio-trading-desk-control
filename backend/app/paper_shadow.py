"""PART 8 — Paper-shadow A/B read-model for the Mini App (read-only).

Reads `paper_shadow_execution_outcomes` (written by the crypto-ai-desk shadow engine) and
aggregates branch A (old_paper) vs branch B (new_logic_shadow), split into the look-ahead
`historical_backfill` window vs the trustworthy `forward_since_activation` window. Never writes.
"""
from __future__ import annotations

from . import desk_adapter


def _agg(rows: list[dict]) -> dict:
    a = [r for r in rows if r["branch"] == "old_paper" and r.get("entry_fill_status") == "filled"]
    b = [r for r in rows if r["branch"] == "new_logic_shadow" and r.get("entry_fill_status") == "filled"]
    ball = [r for r in rows if r["branch"] == "new_logic_shadow"]

    def book(trades):
        net_r = round(sum((t.get("net_r") or 0) for t in trades), 2)
        net_usd = round(sum((t.get("net_pnl_usdt") or 0) for t in trades), 2)
        fees = round(sum((t.get("fees_usdt") or 0) for t in trades), 2)
        wins = sum(1 for t in trades if (t.get("net_r") or 0) > 0.05)
        losses = sum(1 for t in trades if (t.get("net_r") or 0) < -0.05)
        be = len(trades) - wins - losses
        wr = round(100.0 * wins / len(trades), 1) if trades else None
        return {"trades": len(trades), "net_r": net_r, "net_usd": net_usd, "fees_usd": fees,
                "wins": wins, "losses": losses, "be": be, "win_rate_pct": wr}

    A, B = book(a), book(b)
    return {
        "A": A, "B": B,
        "delta": {"net_r": round(B["net_r"] - A["net_r"], 2),
                  "net_usd": round(B["net_usd"] - A["net_usd"], 2),
                  "fees_usd": round(B["fees_usd"] - A["fees_usd"], 2),
                  "win_rate_pct": (round((B["win_rate_pct"] or 0) - (A["win_rate_pct"] or 0), 1)
                                   if (A["win_rate_pct"] is not None and B["win_rate_pct"] is not None) else None)},
        "B_detail": {
            "missed": sum(1 for r in ball if r.get("entry_fill_status") == "missed"),
            "skipped_no_chase": sum(1 for r in ball if r.get("entry_fill_status") == "skipped"),
            "direction_flips": sum(1 for r in ball if r.get("direction_changed")),
            "structural_tp": sum(1 for r in b if r.get("structural_tp_set") in ("STRUCTURAL", "HYBRID")),
            "maker_entries": sum(1 for r in b if r.get("entry_order_type") == "maker"),
        },
    }


def summary() -> dict:
    conn = desk_adapter._ro_conn()
    if conn is None:
        return {"available": False, "reason": "desk db unavailable"}
    try:
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT branch, window, entry_fill_status, net_r, net_pnl_usdt, fees_usdt, "
                "direction_changed, structural_tp_set, entry_order_type "
                "FROM paper_shadow_execution_outcomes").fetchall()]
        except Exception:
            return {"available": False, "reason": "shadow lane not yet populated"}
        act = conn.execute("SELECT v FROM paper_shadow_meta WHERE k='activated_at'").fetchone()
        activated = act[0] if act else None
    finally:
        conn.close()
    if not rows:
        return {"available": False, "reason": "no shadow rows yet"}
    fwd = [r for r in rows if r.get("window") == "forward_since_activation"]
    bf = [r for r in rows if r.get("window") != "forward_since_activation"]
    return {
        "available": True, "activated_at": activated, "live_locked": True,
        "note": ("FORWARD is the only valid evidence; HISTORICAL_BACKFILL uses overlays computed on "
                 "non-time-aligned candles (look-ahead) and is a hypothesis, not proof."),
        "forward_since_activation": _agg(fwd),
        "historical_backfill": _agg(bf),
        "counts": {"forward_rows": len(fwd), "backfill_rows": len(bf)},
    }


_GATE = {"min_forward_days": 14, "min_forward_trades": 60, "max_drawdown_worse_r": 5.0,
         "max_data_gap_share": 0.30}


def forward_monitor() -> dict:
    """PART 7 + 10 — forward quality + promotion-gate evaluation (read-only, never executes)."""
    conn = desk_adapter._ro_conn()
    if conn is None:
        return {"available": False}
    try:
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT signal_id, branch, entry_fill_status, entry_fill_time, net_r, net_pnl_usdt, "
                "fees_usdt, gross_r, direction_changed, entry_order_type, outcome_status, "
                "maker_entry_posted, maker_entry_filled, maker_entry_missed, taker_fallback_used "
                "FROM paper_shadow_execution_outcomes WHERE window='forward_since_activation'").fetchall()]
            act = conn.execute("SELECT v FROM paper_shadow_meta WHERE k='activated_at'").fetchone()
            # PART 8: DATA_GAP_LATE cohort (entry_latency_audit) is dirty — exclude from edge metrics.
            try:
                dgl = {r[0] for r in conn.execute(
                    "SELECT signal_id FROM entry_latency_audit WHERE cause='DATA_GAP_LATE'")}
            except Exception:
                dgl = set()
        except Exception:
            return {"available": False}
        activated = act[0] if act else None
    finally:
        conn.close()
    dgl_excluded = len({r["signal_id"] for r in rows if r.get("signal_id") in dgl})
    rows = [r for r in rows if r.get("signal_id") not in dgl]   # primary edge = clean cohort
    A = [r for r in rows if r["branch"] == "old_paper" and r.get("entry_fill_status") == "filled"]
    Ball = [r for r in rows if r["branch"] == "new_logic_shadow"]
    B = [r for r in Ball if r.get("entry_fill_status") == "filled"]

    def dd(rs):
        peak = d = run = 0.0
        for r in sorted(rs, key=lambda x: x.get("entry_fill_time") or ""):
            run += (r["net_r"] or 0); peak = max(peak, run); d = min(d, run - peak)
        return round(d, 2)
    a_r = round(sum((r["net_r"] or 0) for r in A), 2)
    b_r = round(sum((r["net_r"] or 0) for r in B), 2)
    a_usd = round(sum((r["net_pnl_usdt"] or 0) for r in A), 2)
    b_usd = round(sum((r["net_pnl_usdt"] or 0) for r in B), 2)
    a_dd, b_dd = dd(A), dd(B)
    days = None
    if activated:
        import datetime as _dt
        try:
            days = (_dt.datetime.now(_dt.timezone.utc) - _dt.datetime.fromisoformat(activated)).days
        except Exception:
            pass
    # PART 4 — maker fill realism
    mk_posted = sum((r.get("maker_entry_posted") or 0) for r in Ball)
    mk_filled = sum((r.get("maker_entry_filled") or 0) for r in Ball)
    mk_missed = sum((r.get("maker_entry_missed") or 0) for r in Ball)
    taker_fb = sum((r.get("taker_fallback_used") or 0) for r in Ball)
    mk_rate = round(100.0 * mk_filled / mk_posted, 1) if mk_posted else None
    maker = {"posted": mk_posted, "filled": mk_filled, "missed": mk_missed,
             "taker_fallback": taker_fb, "fill_rate_pct": mk_rate}
    warnings = []
    if len(B) < _GATE["min_forward_trades"]:
        warnings.append(f"forward B sample {len(B)} < {_GATE['min_forward_trades']}")
    if (days or 0) < _GATE["min_forward_days"]:
        warnings.append(f"forward window {days or 0}d < {_GATE['min_forward_days']}d")
    if mk_rate is not None and mk_rate < 50.0:
        warnings.append(f"maker entry fill rate {mk_rate}% < 50% — many limits missed")
    if dgl_excluded:
        warnings.append(f"DATA_GAP_LATE {dgl_excluded} signals excluded from edge (dirty stock-intraday coverage)")
    crit = [
        {"name": "forward_days≥14", "ok": (days or 0) >= _GATE["min_forward_days"], "value": days},
        {"name": "trades≥60", "ok": len(B) >= _GATE["min_forward_trades"], "value": len(B)},
        {"name": "B netR>A netR", "ok": b_r > a_r, "value": f"{b_r} vs {a_r}"},
        {"name": "B net$>A net$", "ok": b_usd > a_usd, "value": f"{b_usd} vs {a_usd}"},
        {"name": "B dd not worse", "ok": b_dd >= a_dd - _GATE["max_drawdown_worse_r"], "value": f"{b_dd} vs {a_dd}"},
    ]
    ready = all(c["ok"] for c in crit)
    return {"available": True, "activated_at": activated, "forward_days": days,
            "forward_signals": len({r.get("entry_fill_time") for r in rows}),
            "A": {"trades": len(A), "net_r": a_r, "net_usd": a_usd, "max_dd_r": a_dd},
            "B": {"trades": len(B), "net_r": b_r, "net_usd": b_usd, "max_dd_r": b_dd},
            "delta_net_r": round(b_r - a_r, 2), "maker": maker,
            "data_gap_late_excluded": dgl_excluded, "primary_cohort": "clean (DATA_GAP_LATE excluded)",
            "gate": {"verdict": "READY" if ready else "NOT_READY", "executed": False,
                     "criteria": crit, "thresholds": _GATE,
                     "note": "evaluation only; promotion needs explicit sign-off; backfill never counts"},
            "warnings": warnings}


_CRYPTO_FEE_PROFILE = "bybit_non_vip_usdt_perp"
_STOCK_FEE_PROFILE = "stock_etf_default"


def _is_stock(ac) -> bool:
    a = str(ac or "").strip().lower()
    return a.startswith("stock") or a.startswith("equit") or a in ("etf", "etfs")


def readiness_by_mode() -> dict:
    """READ-ONLY per (asset_class, mode) promotion-readiness for the Mini App. Mirrors the desk's
    3-verdict scale (NOT_READY / WATCH / READY_FOR_OPERATOR_REVIEW). Evaluates only — never promotes.
    Includes fee-profile integrity + DATA_GAP_LATE share per mode. Live/auto-live remain locked."""
    _READINESS_NOTE = ("READY_FOR_OPERATOR_REVIEW is NOT auto-promotion; operator sign-off required. "
                       "Live / auto-live / manual-live remain locked.")
    _unavail = {"available": False, "live_locked": True, "executed": False,
                "fee_profile_integrity_ok": True, "modes": [], "warnings": [], "note": _READINESS_NOTE}
    conn = desk_adapter._ro_conn()
    if conn is None:
        return dict(_unavail)
    try:
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT e.signal_id, e.branch, e.net_r, e.net_pnl_usdt, e.entry_fill_status, "
                "e.entry_fill_time, e.fee_profile, e.cost_model_status, e.asset_class AS e_asset, "
                "p.asset_class AS p_asset, p.mode AS mode "
                "FROM paper_shadow_execution_outcomes e "
                "LEFT JOIN proposed_signals p ON e.signal_id = p.signal_id "
                "WHERE e.window='forward_since_activation'").fetchall()]
        except Exception:
            return dict(_unavail)
        act = conn.execute("SELECT v FROM paper_shadow_meta WHERE k='activated_at'").fetchone()
        activated = act[0] if act else None
        try:
            dgl = {r[0] for r in conn.execute(
                "SELECT signal_id FROM entry_latency_audit WHERE cause='DATA_GAP_LATE'")}
        except Exception:
            dgl = set()
    finally:
        conn.close()
    days = None
    if activated:
        import datetime as _dt
        try:
            days = (_dt.datetime.now(_dt.timezone.utc) - _dt.datetime.fromisoformat(activated)).days
        except Exception:
            days = None

    def _dd(rs):
        peak = d = run = 0.0
        for r in sorted(rs, key=lambda x: x.get("entry_fill_time") or ""):
            run += (r.get("net_r") or 0); peak = max(peak, run); d = min(d, run - peak)
        return round(d, 3)

    groups: dict[str, dict] = {}
    for r in rows:
        ac = str(r.get("e_asset") or r.get("p_asset") or "?")
        mode = str(r.get("mode") or "?")
        g = groups.setdefault(f"{ac}|{mode}", {"asset_class": ac, "mode": mode, "A": [], "B": [],
                                               "sig": set(), "dgl": set(), "profiles": set(), "stale": 0})
        g["sig"].add(r["signal_id"])
        if r["signal_id"] in dgl:
            g["dgl"].add(r["signal_id"])
        if r.get("cost_model_status") == "stale_cost_model":
            g["stale"] += 1
        if r.get("fee_profile"):
            g["profiles"].add(r["fee_profile"])
        if r["signal_id"] in dgl or r.get("entry_fill_status") != "filled":
            continue
        (g["A"] if r["branch"] == "old_paper" else g["B"]).append(r)
    _GATE_MODE = {"min_forward_days": 14, "min_forward_trades": 60, "max_data_gap_share": 0.30}
    out, stock_intraday_gap = [], 0.0
    for g in groups.values():
        A, B = g["A"], g["B"]
        a_r = round(sum((x.get("net_r") or 0) for x in A), 3)
        b_r = round(sum((x.get("net_r") or 0) for x in B), 3)
        a_usd = round(sum((x.get("net_pnl_usdt") or 0) for x in A), 2)
        b_usd = round(sum((x.get("net_pnl_usdt") or 0) for x in B), 2)
        n = len(g["sig"]) or 1
        dgl_share = round(len(g["dgl"]) / n, 3)
        expected = _STOCK_FEE_PROFILE if _is_stock(g["asset_class"]) else _CRYPTO_FEE_PROFILE
        integrity = (g["stale"] == 0) and (not g["profiles"] or g["profiles"] <= {expected})
        crit = {"forward_days>=14": (days or 0) >= _GATE_MODE["min_forward_days"],
                "forward_trades>=60": len(B) >= _GATE_MODE["min_forward_trades"],
                "B_net_usd>A_net_usd": b_usd > a_usd, "B_net_r>A_net_r": b_r > a_r,
                "data_gap_late<=30%": dgl_share <= _GATE_MODE["max_data_gap_share"],
                "fee_profile_integrity_ok": bool(integrity)}
        b_beats_a = crit["B_net_usd>A_net_usd"] and crit["B_net_r>A_net_r"]
        if all(crit.values()):
            verdict = "READY_FOR_OPERATOR_REVIEW"
        elif b_beats_a and integrity and crit["data_gap_late<=30%"]:
            verdict = "WATCH"
        else:
            verdict = "NOT_READY"
        if _is_stock(g["asset_class"]) and g["mode"] == "intraday":
            stock_intraday_gap = dgl_share
        out.append({"asset_class": g["asset_class"], "mode": g["mode"], "forward_days": days,
                    "forward_trades": len(B), "A_net_usd": a_usd, "B_net_usd": b_usd,
                    "A_net_r": a_r, "B_net_r": b_r, "delta_net_usd": round(b_usd - a_usd, 2),
                    "delta_net_r": round(b_r - a_r, 3), "B_max_drawdown_r": _dd(B),
                    "data_gap_late_share": dgl_share, "fee_profile_integrity_ok": bool(integrity),
                    "fee_profile_expected": expected, "fee_profiles_seen": sorted(g["profiles"]),
                    "verdict": verdict})
    out.sort(key=lambda g: (g["asset_class"], g["mode"]))
    all_integrity = all(m["fee_profile_integrity_ok"] for m in out) if out else True
    warnings = []
    if stock_intraday_gap > 0.30:
        warnings.append(f"stocks intraday DATA_GAP_LATE {round(stock_intraday_gap*100)}% > 30% — "
                        "entry timestamps are coverage artifacts; B cannot be promoted for that mode.")
    return {"available": True, "live_locked": True, "executed": False, "forward_days": days,
            "fee_profile_integrity_ok": all_integrity, "modes": out, "warnings": warnings,
            "note": _READINESS_NOTE}


def trades(limit: int = 60) -> dict:
    """Per-signal A vs B side-by-side (most recent)."""
    conn = desk_adapter._ro_conn()
    if conn is None:
        return {"available": False, "trades": []}
    try:
        try:
            # forward rows are the ONLY valid evidence → fetch them first, then fill with recent backfill
            fwd = [dict(r) for r in conn.execute(
                "SELECT * FROM paper_shadow_execution_outcomes WHERE window='forward_since_activation' "
                "ORDER BY updated_at DESC LIMIT ?", (limit * 2,)).fetchall()]
            back = [dict(r) for r in conn.execute(
                "SELECT * FROM paper_shadow_execution_outcomes "
                "WHERE window IS NULL OR window!='forward_since_activation' "
                "ORDER BY updated_at DESC LIMIT ?", (limit * 2,)).fetchall()]
            rows = fwd + back
        except Exception:
            return {"available": False, "trades": []}
    finally:
        conn.close()
    by_sig: dict[str, dict] = {}
    for r in rows:
        sid = r["signal_id"]
        valid = r.get("window") == "forward_since_activation"
        slot = by_sig.setdefault(sid, {"signal_id": sid, "symbol": r["symbol"],
                                       "asset_class": r["asset_class"], "window": r.get("window"),
                                       "valid_forward": valid,
                                       "data_gap": (r.get("outcome_status") == "no_data" or r.get("close_reason") == "data_gap")})
        key = "A" if r["branch"] == "old_paper" else "B"
        slot[key] = {
            "side": r.get("side"), "entry_mode": r.get("entry_mode"),
            "entry_price": r.get("entry_price"), "fill_status": r.get("entry_fill_status"),
            "entry_order_type": r.get("entry_order_type"), "exit_order_type": r.get("exit_order_type"),
            "tp_set": r.get("structural_tp_set"), "tp1": r.get("tp1"), "tp2": r.get("tp2"), "tp3": r.get("tp3"),
            "stop_initial": r.get("stop_initial"), "stop_current": r.get("stop_current"),
            "structural_stop_used": r.get("structural_stop_used"),
            "gross_r": r.get("gross_r"), "net_r": r.get("net_r"),
            "net_usd": r.get("net_pnl_usdt"), "fees_usd": r.get("fees_usdt"),
            "mfe_r": r.get("mfe_r"), "mae_r": r.get("mae_r"),
            "close_reason": r.get("close_reason"), "direction_changed": r.get("direction_changed"),
            "old_side": r.get("old_side"), "skipped_reason": r.get("skipped_shadow_reason"),
            "missed_reason": r.get("missed_entry_reason"),
            "maker_posted": r.get("maker_entry_posted"), "maker_filled": r.get("maker_entry_filled"),
            "maker_missed": r.get("maker_entry_missed"), "taker_fallback": r.get("taker_fallback_used"),
            "maker_tp_fills": r.get("maker_tp_fills"),
        }
    # surface the VALID forward trades first (the only evidence), then recent backfill
    out = sorted(by_sig.values(), key=lambda t: 0 if t.get("valid_forward") else 1)[:limit]
    # annotate the interesting cases + per-trade delta
    for t in out:
        a, b = t.get("A", {}), t.get("B", {})
        dR = round((b.get("net_r") or 0) - (a.get("net_r") or 0), 3)
        t["delta"] = {"net_r": dR, "net_usd": round((b.get("net_usd") or 0) - (a.get("net_usd") or 0), 2),
                      "fees_usd": round((b.get("fees_usd") or 0) - (a.get("fees_usd") or 0), 2)}
        t["highlight"] = (
            "B_traded_A_missed" if (b.get("fill_status") == "filled" and a.get("fill_status") in ("missed", "invalid")) else
            "A_traded_B_skipped" if (a.get("fill_status") == "filled" and b.get("fill_status") in ("skipped", "missed")) else
            "direction_flip" if b.get("direction_changed") else
            "B_outperforms" if dR > 0.5 else
            "A_outperforms" if dR < -0.5 else None)
        t["why"] = (
            "B entered on a setup A's pullback missed" if t["highlight"] == "B_traded_A_missed" else
            "B's no-chase/skip avoided a trade A took" if t["highlight"] == "A_traded_B_skipped" else
            f"B flipped {b.get('old_side')}→{b.get('side')} (multi-factor)" if t["highlight"] == "direction_flip" else
            f"B {'+' if dR>=0 else ''}{dR}R vs A (structural TP/stop)" if t["highlight"] == "B_outperforms" else
            f"A {'+' if -dR>=0 else ''}{round(-dR,3)}R vs B" if t["highlight"] == "A_outperforms" else "≈ equal")
    return {"available": True, "trades": out}


def fee_assumptions() -> dict:
    """PART 2 — active fee profile + assumptions for the UI fee card (read-only)."""
    prof = "bybit_non_vip_usdt_perp"
    rates = {"bybit_non_vip_usdt_perp": {"maker": 0.0002, "taker": 0.00055},
             "conservative_taker": {"maker": 0.00055, "taker": 0.00075},
             "mexc_default_futures": {"maker": 0.0002, "taker": 0.0006}}
    fwd = forward_monitor()
    fee_fragile = any("fee-fragile" in w for w in (fwd.get("warnings") or [])) if fwd.get("available") else False
    fdrag = None
    if fwd.get("available"):
        # B fee-drag in R = gross-net would need gross; approximate via fees not available here → show $ fees
        fdrag = fwd.get("B", {}).get("net_usd")
    return {"active_profile": prof, "maker_fee": rates[prof]["maker"], "taker_fee": rates[prof]["taker"],
            "slippage_estimate": 0.0002, "custom_account_override": False,
            "all_numbers_after_fees": True, "fee_fragile_warning": fee_fragile,
            "note": "default bybit_non_vip_usdt_perp; all A/B headline numbers are net of fees + slippage"}


def _is_data_gap(r: dict) -> bool:
    return (r.get("outcome_status") == "no_data") or (r.get("close_reason") == "data_gap")


def _branch_book(rows: list[dict]) -> dict:
    """Aggregate one branch's rows for a group (DATA_GAP rows already excluded).
    Trades/R/win-rate use FILLED rows only; missed/no-chase/flips count over all rows."""
    filled = [r for r in rows if r.get("entry_fill_status") == "filled"]
    n = len(filled)
    net_r = round(sum((r.get("net_r") or 0) for r in filled), 2)
    wins = sum(1 for r in filled if (r.get("net_r") or 0) > 0)
    posted = sum(int(r.get("maker_entry_posted") or 0) for r in rows)
    mfilled = sum(int(r.get("maker_entry_filled") or 0) for r in rows)
    return {
        "trades": n, "net_r": net_r,
        "net_usd": round(sum((r.get("net_pnl_usdt") or 0) for r in filled), 2),
        "fees_usd": round(sum((r.get("fees_usdt") or 0) for r in filled), 2),
        "win_rate": round(100 * wins / n, 1) if n else 0.0,
        "worst_r": round(min((r.get("net_r") or 0) for r in filled), 2) if filled else 0.0,
        "maker_posted": posted, "maker_filled": mfilled,
        "maker_fill_rate": round(100 * mfilled / posted, 1) if posted else None,
        "missed_entries": sum(1 for r in rows if r.get("entry_fill_status") in ("missed", "invalid")),
        "no_chase": sum(1 for r in rows if "no_chase" in str(r.get("skipped_shadow_reason") or "").lower()),
        "dir_flips": sum(1 for r in rows if r.get("direction_changed")),
    }


def _group_window(rows: list[dict]) -> dict:
    """A vs B for one (dimension-value, window) bucket; DATA_GAP excluded from edge stats but counted."""
    gap = sum(1 for r in rows if _is_data_gap(r))
    clean = [r for r in rows if not _is_data_gap(r)]
    A = _branch_book([r for r in clean if r["branch"] == "old_paper"])
    B = _branch_book([r for r in clean if r["branch"] == "new_logic_shadow"])
    return {"A": A, "B": B, "data_gap_excluded": gap,
            "delta_r": round(B["net_r"] - A["net_r"], 2),
            "delta_usd": round(B["net_usd"] - A["net_usd"], 2),
            "delta_fees": round(B["fees_usd"] - A["fees_usd"], 2)}


# dimension -> key function over a joined row (paper_shadow_execution_outcomes + proposed_signals)
_DIMS = {
    "mode": lambda r: f"{r.get('asset_class') or '?'} {r.get('ps_mode') or r.get('playbook') or '?'}".strip(),
    "asset_class": lambda r: r.get("asset_class") or "?",
    "symbol": lambda r: r.get("symbol") or "?",
    "sector": lambda r: r.get("sector") or "—",
    "regime": lambda r: r.get("market_regime") or "—",
    "entry_mode": lambda r: r.get("entry_mode") or "—",
    "tp_set": lambda r: r.get("structural_tp_set") or "—",
    "order_type": lambda r: r.get("entry_order_type") or "—",
}


def breakdown(min_trades: int = 1) -> dict:
    """PART 1 — forward A/B broken down by mode/asset/symbol/sector/regime/entry_mode/tp_set/maker-taker.
    Forward (valid) is reported separately from backfill (look-ahead hypothesis). Read-only."""
    conn = desk_adapter._ro_conn()
    if conn is None:
        return {"available": False, "dimensions": {}}
    try:
        try:
            rows = [dict(r) for r in conn.execute(
                "SELECT e.*, p.mode AS ps_mode, p.market_regime AS market_regime, p.sector AS sector "
                "FROM paper_shadow_execution_outcomes e "
                "LEFT JOIN proposed_signals p ON e.signal_id = p.signal_id").fetchall()]
        except Exception:
            return {"available": False, "dimensions": {}}
        activated = None
        try:
            row = conn.execute("SELECT v FROM paper_shadow_meta WHERE k='activated_at'").fetchone()
            activated = row[0] if row else None
        except Exception:
            pass
    finally:
        conn.close()

    fwd = [r for r in rows if r.get("window") == "forward_since_activation"]
    back = [r for r in rows if r.get("window") != "forward_since_activation"]
    dims: dict[str, list] = {}
    for dim, keyfn in _DIMS.items():
        groups: dict[str, dict] = {}
        for label_rows, win in ((fwd, "forward"), (back, "backfill")):
            buckets: dict[str, list] = {}
            for r in label_rows:
                buckets.setdefault(keyfn(r), []).append(r)
            for k, grp in buckets.items():
                groups.setdefault(k, {"key": k})[win] = _group_window(grp)
        # keep groups with at least min_trades forward rows; sort by |forward ΔR| desc then backfill
        out = []
        for g in groups.values():
            ftot = (g.get("forward", {}).get("A", {}).get("trades", 0)
                    + g.get("forward", {}).get("B", {}).get("trades", 0))
            g["_ftot"] = ftot
            out.append(g)
        out.sort(key=lambda g: (g["_ftot"] == 0, -abs(g.get("forward", {}).get("delta_r", 0) or 0)))
        for g in out:
            g.pop("_ftot", None)
        dims[dim] = [g for g in out if (g.get("forward") or g.get("backfill"))]
    return {"available": True, "activated_at": activated,
            "forward_rows": len(fwd), "backfill_rows": len(back),
            "primary_dimension": "mode", "dimensions": dims,
            "note": "FORWARD is the only valid evidence; backfill is look-ahead (hypothesis), labelled separately."}
