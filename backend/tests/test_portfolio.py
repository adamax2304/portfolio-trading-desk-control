"""Paper portfolio read-model tests (read-only, never live)."""
from __future__ import annotations

from app import portfolio


def test_summary_shape_and_safety():
    s = portfolio.portfolio_summary()
    # always returns a dict with the safety locks + deposit/risk, available or not
    assert s["initial_equity_usdt"] == 5000
    assert s["risk_per_trade_pct"] == 0.005
    assert s["live_locked"] is True and s["auto_live_locked"] is True
    if s.get("available"):
        assert s["equity_usdt"] >= 0
        assert "fee_profile" in s and "max_drawdown_pct" in s
        assert s["open_positions"] == 0  # derived/historical ledger has no live positions


def test_trades_and_chart_events_are_lists_dicts():
    t = portfolio.portfolio_trades(5)
    assert isinstance(t, list)
    ce = portfolio.chart_events("nonexistent_signal_id")
    assert ce["available"] is False and ce["levels"] == []


def test_chart_events_exact_r_and_exit_marker_when_available():
    """For a real ledger trade, chart-events returns exact TP R + an exit marker."""
    s = portfolio.portfolio_summary()
    if not s.get("available"):
        return  # no desk DB / ledger in this env — skip
    trades = portfolio.portfolio_trades(1)
    if not trades:
        return
    ce = portfolio.chart_events(trades[0]["signal_id"])
    if not ce.get("available"):
        return
    # exact TP R present (not forced 1/2/3)
    assert "tp_r_exact" in ce
    # at least one true execution marker exists (lifecycle vocabulary: partial TP fills,
    # stop, expired exit, or legacy exit). A winning trade shows tp_fill markers.
    kinds = {m["marker_type"] for m in ce.get("markers", [])}
    assert kinds & {"exit", "expired_exit", "tp_fill", "stop", "entry"}
    assert ce.get("tp_quality", {}).get("label") == "MECHANICAL_ATR_LADDER"


def test_portfolio_compare_structural_maker_first():
    """A (mechanical taker) vs B (structural + maker-first + 2x). Read-only, live locked."""
    c = portfolio.portfolio_compare()
    assert c["live_locked"] is True and c["auto_live_locked"] is True
    assert c["production_tp_unchanged"] is True
    if not c.get("available"):
        return  # B ledger not built in this env — skip
    assert "mechanical_taker" in c and "structural_maker_first" in c
    assert c["leverage_policy"] == "max_2x_safe"
    # B never uses more than 2x
    assert (c["structural_maker_first"].get("max_leverage") or 0) <= 2
    # maker counts present and sane
    assert c["maker_entries"] >= 0 and c["maker_exits"] >= 0
    assert c["fees_saved_usdt"] is not None


def test_b_max_leverage_never_exceeds_2():
    """The structural/maker-first paper book respects the max-2x policy."""
    b = portfolio.portfolio_summary(portfolio.STRUCTURAL_MAKER_PROFILE)
    if not b.get("available"):
        return
    assert (b.get("max_leverage") or 0) <= 2


def test_chart_events_paper_execution_b_when_available():
    s = portfolio.portfolio_summary()
    if not s.get("available"):
        return
    trades = portfolio.portfolio_trades(1)
    if not trades:
        return
    ce = portfolio.chart_events(trades[0]["signal_id"])
    if not ce.get("available") or not ce.get("paper_execution_b"):
        return
    b = ce["paper_execution_b"]
    assert b["stop_order_type"] == "taker"          # stops always taker
    assert b["entry_order_type"] in ("maker", "taker", None)
    assert b["tp_set_label"] in ("STRUCTURAL", "HYBRID", "STRUCTURAL_FALLBACK_ATR", "NO_VALID_TP", None)
