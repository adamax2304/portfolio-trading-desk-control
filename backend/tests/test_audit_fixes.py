"""Audit-fix tests (paper/read-model only; live locked; final_r untouched).
Covers: #1 fee/slippage split, #2 actionability terminal statuses, #3 per-asset cost split,
#11 A/B comparison integrity. DB-dependent tests skip when the desk DB is absent."""
from __future__ import annotations

import pytest

from app import actionability, portfolio


def _summary():
    s = portfolio.portfolio_summary()
    if not s.get("available"):
        pytest.skip("desk paper_portfolio_ledger not present")
    return s


# ---- #1: exchange fees vs slippage are SEPARATE ----
def test_fee_and_slippage_split():
    s = _summary()
    for k in ("exchange_fees_usdt", "slippage_usdt", "funding_usdt", "total_execution_cost_usdt"):
        assert k in s
    # total = exchange fees + slippage + funding
    assert s["total_execution_cost_usdt"] == pytest.approx(
        s["exchange_fees_usdt"] + s["slippage_usdt"] + s["funding_usdt"], abs=0.05)
    # deprecated alias equals the TOTAL execution cost (not just fees)
    assert s["fees_paid_usdt"] == s["total_execution_cost_usdt"]
    # they are genuinely distinct numbers (slippage is not folded into fees)
    if s["slippage_usdt"] > 0:
        assert s["exchange_fees_usdt"] != s["total_execution_cost_usdt"]


# ---- #2: stale_before_entry / entry_moved_away are terminal → never manually actionable ----
@pytest.mark.parametrize("status", ["stale_before_entry", "entry_moved_away"])
def test_non_entry_statuses_not_actionable(status):
    out = actionability.classify({"asset_class": "crypto", "mode": "intraday", "tier": "B",
                                  "status": status})
    assert out["actionable"] is False
    assert out["status"] == "closed"   # frontend gate is `actionable && status === 'actionable'`


def test_actionable_still_works_for_fresh_triggered():
    out = actionability.classify({"asset_class": "crypto", "mode": "intraday", "tier": "B",
                                  "status": "triggered", "entry_triggered_at": None})
    assert out["actionable"] is True   # waiting-for-entry path still actionable


# ---- #3: stocks priced with the equity/ETF model (not crypto-perp), crypto carries funding ----
def test_per_asset_cost_model_correct():
    ba = portfolio.portfolio_by_asset()
    if not ba.get("available"):
        pytest.skip("ledger absent")
    assert ba["crypto"]["cost_model_appropriate"] is True
    # after the engine cost-model fix, stocks are correctly priced (equity/ETF model)
    if ba["stocks"]["trades"] > 0:
        assert ba["stocks"]["cost_model_appropriate"] is True
    # per-asset cost split present
    for a in ("crypto", "stocks"):
        for k in ("exchange_fees_usdt", "slippage_usdt", "funding_usdt"):
            assert k in ba[a]


# ---- #11: A/B compare must report integrity (same trades / same period) ----
def test_compare_reports_integrity():
    c = portfolio.portfolio_compare()
    if not c.get("available"):
        pytest.skip("structural/maker ledger not built")
    ci = c["comparison_integrity"]
    assert "comparable" in ci and "warnings" in ci
    assert "A" in ci and "B" in ci and "common_trades" in ci


# ---- guardrails ----
def test_no_write_sql_in_portfolio_readmodel():
    from pathlib import Path
    src = Path(portfolio.__file__).read_text(encoding="utf-8").upper()
    for verb in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE"):
        assert verb not in src


# ---- RE-AUDIT #3: stock lifecycle is priced with the equity/ETF model, never the Bybit perp ----
def _mk_lifecycle_db(path, *, asset_class, symbol, mode):
    import sqlite3
    c = sqlite3.connect(path)
    c.execute("""CREATE TABLE proposed_signals (signal_id TEXT, symbol TEXT, direction TEXT,
        asset_class TEXT, mode TEXT, tier TEXT, setup_type TEXT, market_regime TEXT,
        suggested_entry REAL, entry_trigger REAL, entry_low REAL, invalidation REAL,
        stop_loss REAL, tp1 REAL, tp2 REAL, tp3 REAL, created_at TEXT)""")
    c.execute("""CREATE TABLE signal_outcomes (signal_id TEXT, entry_triggered INTEGER,
        entry_triggered_at TEXT, entry_price_used REAL, tp1_hit_at TEXT, tp2_hit_at TEXT,
        tp3_hit_at TEXT, stop_hit_at TEXT, final_outcome TEXT, final_r REAL,
        max_favorable_excursion_r REAL, max_adverse_excursion_r REAL, checked_at TEXT, id INTEGER)""")
    c.execute("INSERT INTO proposed_signals VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("x1", symbol, "long", asset_class, mode, "B", "breakout", "trend",
               100.0, 100.0, 99.5, 99.0, 99.0, 101.0, 102.0, 103.0, "2026-06-30T00:00:00Z"))
    c.execute("INSERT INTO signal_outcomes VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              ("x1", 1, "2026-06-30T00:10:00Z", 100.0, "2026-06-30T01:00:00Z",
               "2026-06-30T02:00:00Z", "2026-06-30T03:00:00Z", None, "win", 3.0, 3.1, -0.3,
               "2026-06-30T03:00:00Z", 1))
    c.commit(); c.close()


def _patch_conn(monkeypatch, db):
    import sqlite3
    from app import lifecycle

    def _conn():
        c = sqlite3.connect(db); c.row_factory = sqlite3.Row; return c
    monkeypatch.setattr(lifecycle, "_ro_conn", _conn)


def test_stock_lifecycle_not_bybit_perp(tmp_path, monkeypatch):
    from app import lifecycle
    db = str(tmp_path / "life_stock.sqlite")
    _mk_lifecycle_db(db, asset_class="stocks", symbol="AAPL", mode="intraday")
    _patch_conn(monkeypatch, db)
    lc = lifecycle.position_lifecycle("x1")
    assert lc["available"]
    # stock must NOT be shown with the Bybit-perp fee model
    assert lc["position"]["fee_profile"] == "stock_etf_default"
    assert "bybit" not in lc["position"]["fee_profile"].lower()
    cm = lc["cost_model"]
    assert cm["fee_profile"] == "stock_etf_default"
    assert cm["funding_usdt"] == 0            # equities have no perp funding
    assert cm["funding_known"] is False
    for k in ("exchange_fees_usdt", "slippage_usdt", "funding_usdt"):
        assert k in cm


def test_crypto_lifecycle_is_perp(tmp_path, monkeypatch):
    from app import lifecycle
    db = str(tmp_path / "life_crypto.sqlite")
    _mk_lifecycle_db(db, asset_class="crypto", symbol="BTC/USDT", mode="intraday")
    _patch_conn(monkeypatch, db)
    lc = lifecycle.position_lifecycle("x1")
    assert lc["available"]
    assert lc["position"]["fee_profile"] == "bybit_non_vip_usdt_perp"
    assert lc["cost_model"]["funding_usdt"] > 0     # crypto intraday crosses ~1 funding interval
    assert lc["cost_model"]["funding_known"] is True


# ---- RE-AUDIT #4: /api/risk/update rejects a blank confirm token (shared confirm gate) ----
def test_risk_update_rejects_empty_confirm():
    from fastapi import HTTPException
    from app.main import api_risk_update, RiskUpdate, _require_confirm
    for tok in ("", "   "):
        req = RiskUpdate(key="risk_per_trade", value=0.01, confirm_token=tok)
        with pytest.raises(HTTPException) as ei:
            api_risk_update(req, user={"id": 0, "username": "t"})
        assert ei.value.status_code == 400
    # shared helper: a state-changing command with a blank token is rejected; always-safe passes
    with pytest.raises(HTTPException):
        _require_confirm("SET_RISK_PER_TRADE", "")
    _require_confirm("ADD_TRADE_NOTE", "")   # no raise for always-safe


# ---- LEGACY-R PURGE: profitability is USD net; legacy touch R never a PnL key ----
def test_portfolio_profitability_is_usd_net():
    s = portfolio.portfolio_summary()
    if not s.get("available"):
        pytest.skip("ledger absent")
    # authoritative profitability = USD net after fees/slippage/funding (not an R sum)
    assert "net_pnl_usdt_total" in s and "total_execution_cost_usdt" in s
    # the legacy touch metric is never exposed as a PnL key on the portfolio read-model
    for k in ("realized_r", "final_r", "touch_r"):
        assert k not in s


def test_dashboard_headline_usd_authoritative_and_legacy_r_renamed():
    from app import books
    from datetime import datetime, timedelta, timezone
    recent = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [{
        "signal_id": "z", "symbol": "AAA/USDT", "asset_class": "crypto", "mode": "intraday",
        "direction": "long", "tier": "B", "entry_alert_status": "sent", "entry_alert_sent": True,
        "actionability": {"status": "actionable"}, "entry_triggered": 1,
        "final_outcome": "win", "final_r": 2.0, "tp1_hit": 1, "mfe_r": 2.4,
        "display_status": "closed_win", "exit_at": recent,
    }]
    s = books.get_dashboard_summary(rows)
    # authoritative headline metric is USD net
    assert s["headline"]["authoritative_metric"] == "usd_net_after_fees_slippage_funding"
    w = s["operator"]["d7"]
    # the legacy touch total exists ONLY under its explicit name; old PnL-looking keys are gone
    assert "legacy_touch_r" in w and "paper_execution_r" in w and "touch_minus_paper_r" in w
    assert "realized_r" not in w and "touch_r" not in w
    assert "today_legacy_touch_r" in s["headline"] and "today_touch_r" not in s["headline"]
