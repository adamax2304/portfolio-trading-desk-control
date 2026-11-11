"""Guardrail contract tests for the legacy-R / USD-net purge (paper/read-model only; live locked).

Locks the single contract:
  * authoritative profitability = USD net (paper_portfolio_ledger.net_pnl_usdt)
  * auxiliary realistic R = paper_execution_r
  * legacy final_r/touch = legacy_touch_r ONLY — never PnL, never headline, never realized_r/touch_r
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import books
from app.main import app, current_user


def _client() -> TestClient:
    app.dependency_overrides[current_user] = lambda: {"id": 0, "username": "test", "_auth": "test"}
    return TestClient(app)


def _teardown():
    app.dependency_overrides.pop(current_user, None)


# ---- endpoint contract: 200 + live locked + legacy_touch_r fields (never touch_r/realized_r) ----
def test_dashboard_summary_uses_legacy_touch_and_usd_authoritative():
    c = _client()
    try:
        r = c.get("/api/dashboard/summary")
        assert r.status_code == 200
        h = r.json()["headline"]
        assert h["authoritative_metric"] == "usd_net_after_fees_slippage_funding"
        for k in ("today_paper_execution_r", "h48_paper_execution_r", "d7_paper_execution_r",
                  "today_legacy_touch_r", "h48_legacy_touch_r", "today_touch_minus_paper_r"):
            assert k in h, f"missing headline field {k}"
        assert "today_touch_r" not in h and "today_realized_r" not in h
        w = r.json()["operator"]["d7"]
        assert "legacy_touch_r" in w and "paper_execution_r" in w
        assert "touch_r" not in w and "realized_r" not in w   # never PnL-facing book-window keys
    finally:
        _teardown()


@pytest.mark.parametrize("path", [
    "/api/portfolio", "/api/portfolio/compare", "/api/portfolio/by-asset",
    "/api/paper-shadow/summary", "/api/paper-shadow/forward", "/api/paper-shadow/fees",
])
def test_paper_endpoints_200_and_live_locked(path):
    c = _client()
    try:
        r = c.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
        body = r.json()
        # every paper read-model asserts the hard live lock
        if "live_locked" in body:
            assert body["live_locked"] is True
        if "auto_live_locked" in body:
            assert body["auto_live_locked"] is True
    finally:
        _teardown()


def test_by_asset_stocks_not_bybit_label():
    c = _client()
    try:
        r = c.get("/api/portfolio/by-asset")
        assert r.status_code == 200
        body = r.json()
        if not body.get("available"):
            pytest.skip("ledger absent")
        st = body.get("stocks") or {}
        if (st.get("trades") or 0) > 0:
            fp = (st.get("fee_profile_used") or "").lower()
            assert "bybit" not in fp and "perp" not in fp   # stocks NEVER a Bybit perp label
            assert "stock" in fp or "etf" in fp
            assert st.get("funding_usdt") == 0               # equities: no perp funding
    finally:
        _teardown()


# ---- unit: a trade with legacy touch +1R but paper-exec 0R → headline main=0R, legacy=+1R ----
def _sig(**kw):
    base = dict(signal_id="s1", symbol="AAA/USDT", asset_class="crypto", mode="intraday",
                direction="long", tier="B", entry_trigger=100.0, stop_loss=95.0,
                entry_alert_status="sent", entry_alert_sent=True,
                actionability={"status": "actionable"})
    base.update(kw)
    return base


def test_headline_shows_paper_r_main_legacy_touch_secondary():
    recent = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    # TP1 touched (legacy touch books +1R) then reversed to stop after arming BE at +0.6R MFE →
    # Model F paper-execution R = 0R. USD net is the authoritative PnL; this R is the diagnostic.
    row = _sig(entry_triggered=1, final_outcome="win", final_r=1.0, tp1_hit=1, stop_hit=1,
               mfe_r=0.7, display_status="closed_loss", exit_at=recent)
    # per-trade contract
    assert books.paper_execution_r(row) == 0.0
    assert books.touch_r(row) == 1.0                # legacy touch calculator = +1R (highest TP)
    flags = books.paper_exec_flags(row)
    assert flags["paper_execution_r"] == 0.0 and flags["legacy_touch_r"] == 1.0
    assert "touch_r" not in flags   # the PnL-facing key is gone
    # headline contract
    s = books.get_dashboard_summary([row])
    assert s["headline"]["today_paper_execution_r"] == 0.0          # MAIN = 0R
    assert s["headline"]["today_legacy_touch_r"] == 1.0             # secondary legacy = +1R


# ---- BookWindow does not require realized_r / touch_r ----
def test_book_window_has_no_legacy_pnl_keys():
    s = books.get_dashboard_summary([])
    for book in ("operator", "paper", "shadow"):
        for win in ("today", "h48", "d7"):
            w = s[book][win]
            assert "realized_r" not in w and "touch_r" not in w
            assert "legacy_touch_r" in w and "paper_execution_r" in w


# ---- chart-events legacy_touch_r comes from paper_execution_outcomes.touch_r (never the ledger) ----
def test_chart_events_legacy_touch_from_paper_execution_outcomes():
    from app import portfolio
    conn = portfolio._ro_conn()
    if conn is None:
        pytest.skip("desk DB absent (demo mode)")
    try:
        if not portfolio._has_table(conn, "paper_execution_outcomes"):
            pytest.skip("paper_execution_outcomes table absent")
        # a trade whose touch_r genuinely diverges from paper_execution_r, and that still exists in
        # proposed_signals (so chart_events resolves available=True).
        row = conn.execute(
            "SELECT pe.signal_id AS sid, pe.touch_r AS t, pe.paper_execution_r AS p "
            "FROM paper_execution_outcomes pe JOIN proposed_signals ps ON ps.signal_id = pe.signal_id "
            "WHERE pe.touch_r IS NOT NULL AND pe.paper_execution_r IS NOT NULL "
            "AND ABS(pe.touch_r - pe.paper_execution_r) > 0.001 LIMIT 1").fetchone()
    finally:
        conn.close()
    if not row:
        pytest.skip("no divergent touch_r / paper_execution_r row available")
    sid, exp_touch, exp_pe = row["sid"], float(row["t"]), float(row["p"])
    c = _client()
    try:
        r = c.get(f"/api/trades/{sid}/chart-events")
        assert r.status_code == 200
        data = r.json()
        assert data.get("available") is True
        assert data["paper_execution_r"] == pytest.approx(exp_pe)
        # legacy_touch_r must be the (non-null) touch_r from paper_execution_outcomes — the OLD bug
        # returned null because it read the ledger (which has no touch_r column).
        assert data["legacy_touch_r"] == pytest.approx(exp_touch)
        assert data["legacy_touch_r"] is not None
        assert data["legacy_touch_r"] != data["paper_execution_r"]   # genuinely divergent
        assert "touch_r" not in data                                 # top-level touch_r is gone
        # net USD PnL, when present, stays a SEPARATE USD field — never conflated with the R metrics
        assert "net_pnl_usdt" in data
    finally:
        _teardown()
