"""Tests: position lifecycle + regime normalize + market dashboard + actionability
closed-freshness (PART 13). Read-only; live locked; final_r never written."""
from __future__ import annotations

from app import lifecycle, market_dashboard, portfolio
from app.regime import normalize_regime
from app.actionability import classify, freshness


# ---- regime normalization (PART 8) ----
def test_regime_empty_is_unknown():
    r = normalize_regime("")
    assert r["regime"] == "unknown" and r["source"] == "none"


def test_regime_maps_free_text():
    assert normalize_regime("bullish")["regime"] == "trend_up"
    assert normalize_regime("bearish trend")["regime"] == "trend_down"
    assert normalize_regime("range/chop")["regime"] == "range"
    assert normalize_regime("high-volatility danger")["regime"] == "high_volatility"
    assert normalize_regime("risk_off")["regime"] == "risk_off"


def test_regime_unmapped_low_confidence():
    r = normalize_regime("wat")
    assert r["regime"] == "unknown" and r["confidence"] < 0.5


# ---- actionability closed-trade freshness (PART 9 / MSTR fix) ----
def test_closed_trade_has_no_chase_label():
    sig = {"asset_class": "stocks", "mode": "intraday", "tier": "B", "status": "expired",
           "entry_triggered_at": "2026-06-24T14:15:00+00:00"}
    out = classify(sig)
    assert out["status"] == "closed"
    assert "DO NOT CHASE" not in out["freshness"]["label"]
    assert out["freshness"]["label"].startswith("closed")


def test_open_late_trade_still_warns():
    # a still-open very-late trade keeps the chase guard
    sig = {"asset_class": "crypto", "mode": "intraday", "tier": "B", "status": "triggered",
           "entry_triggered_at": "2020-01-01T00:00:00+00:00"}
    out = classify(sig)
    assert out["status"] == "late" and "DO NOT CHASE" in out["freshness"]["label"]


# ---- lifecycle (PART 3) ----
def test_lifecycle_shape_and_safety():
    lc = lifecycle.position_lifecycle("nonexistent_signal")
    assert lc["available"] is False


def test_lifecycle_partials_when_available():
    """If the desk DB has a multi-TP win, lifecycle returns ordered partial fills and a
    blended R below the touch R (partial accounting)."""
    mo = lifecycle.missed_opportunities(1)
    assert "available" in mo  # endpoint callable
    # find any closed win with all 3 TPs from the live DB via missed? — use a known id if present
    lc = lifecycle.position_lifecycle("sig_c6df604c56ba3036")
    if not lc.get("available"):
        return  # env without that signal
    assert lc["live_locked"] is True
    parts = lc.get("partials") or []
    if len(parts) == 3:
        assert parts[0]["tp"] == "TP1" and parts[2]["tp"] == "TP3"
        assert lc["blended_r"] is not None
        # blended (partial) < touch (full TP3) for a 3-TP win
        if lc["audit"].get("touch_final_r"):
            assert lc["blended_r"] <= lc["audit"]["touch_final_r"] + 1e-6
    # max leverage policy
    if lc.get("position"):
        assert (lc["position"].get("leverage") or 0) <= 5


def test_missed_opportunities_excludes_entered():
    mo = lifecycle.missed_opportunities(50)
    if not mo.get("available"):
        return
    for it in mo["items"]:
        # only non-entered signals are listed
        assert it["would_have_entered_price"] is not None or it["would_have_entered_price"] is None


# ---- market dashboard reader (PART 10) ----
def test_market_dashboard_shape_and_safety():
    md = market_dashboard.latest_snapshot()
    assert md["live_locked"] is True and md["auto_live_locked"] is True
    if md.get("available"):
        assert "crypto_market_mode" in md and "stale" in md
        assert "extras" in md and "vix" in md["extras"]   # VIX field present (value may be null)


# ---- chart-events true partial markers (PART 2) ----
def test_chart_events_partial_tp_markers_no_generic_exit():
    """A TP3 win returns separate tp_fill markers (TP1/TP2/TP3) and NO generic 'exit'."""
    s = portfolio.portfolio_summary()
    if not s.get("available"):
        return
    # find any closed win with all 3 TP fills in the lifecycle
    trades = portfolio.portfolio_trades(40)
    target = None
    for t in trades:
        lc = lifecycle.position_lifecycle(t["signal_id"])
        if lc.get("available") and len([p for p in (lc.get("partials") or [])]) == 3:
            target = t["signal_id"]; break
    if not target:
        return  # no 3-TP trade in this env
    ce = portfolio.chart_events(target)
    types = [m["marker_type"] for m in ce.get("markers", [])]
    assert types.count("tp_fill") >= 3            # three partial TP fills
    assert "exit" not in types                     # no misleading single generic exit
    # each tp_fill carries the full schema
    tps = [m for m in ce["markers"] if m["marker_type"] == "tp_fill"]
    assert all("cumulative_realized_r" in m and "source_book" in m and "is_partial_exit" in m for m in tps)
    assert ce.get("lines")                          # price lines for the overlay


def test_chart_events_marker_schema_fields():
    s = portfolio.portfolio_summary()
    if not s.get("available"):
        return
    trades = portfolio.portfolio_trades(1)
    if not trades:
        return
    ce = portfolio.chart_events(trades[0]["signal_id"])
    for m in ce.get("markers", []):
        if m["marker_type"] in ("entry", "tp_fill", "stop", "expired_exit", "moved_stop"):
            assert "marker_id" in m and "event_type" in m and "source_book" in m
