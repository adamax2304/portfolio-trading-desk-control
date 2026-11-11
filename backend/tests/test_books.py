"""Canonical trade-book read-model tests (PART 3 assertions).

These lock the fix for the old -26R bug: economic dedup, latest/terminal outcome,
shadow excluded from Operator R, expired-after-entry not counted as realized PnL,
and Operator/Paper/Shadow totals intentionally differing.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import books

# Recent, IN-WINDOW timestamp for the d7 (rolling 7-day) dashboard assertions.
# Absolute dates (e.g. "2026-06-20") silently age out of the window and fail on a
# later run; anchoring to now-2d keeps these tests durable (inside d7, outside d1).
_RECENT = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sig(**kw):
    base = dict(signal_id="s1", symbol="AAA/USDT", asset_class="crypto", mode="intraday",
                direction="long", tier="B", entry_trigger=100.0, stop_loss=95.0,
                entry_alert_status="sent", entry_alert_sent=True,
                actionability={"status": "actionable"})
    base.update(kw)
    return base


# ---- books ----------------------------------------------------------------
def test_operator_book_is_delivered_actionable():
    s = _sig(entry_alert_status="sent", entry_alert_sent=True)
    assert books.derive_trade_book(s)["book"] == "operator"
    assert books.in_book(s, "operator") and books.in_book(s, "paper")


def test_paper_undelivered_not_operator():
    s = _sig(entry_alert_status="error:ReadTimeout", entry_alert_sent=False)
    c = books.derive_trade_book(s)
    assert c["book"] == "paper" and c["delivered"] is False
    assert books.in_book(s, "paper") and not books.in_book(s, "operator")


def test_shadow_book_excludes_scalp_ctier_lateshadow():
    assert books.derive_trade_book(_sig(mode="scalp"))["book"] == "shadow"
    assert books.derive_trade_book(_sig(tier="C"))["book"] == "shadow"
    assert books.derive_trade_book(_sig(asset_class="stocks", mode="swing"))["book"] == "shadow"
    assert books.derive_trade_book(_sig(entry_alert_status="late_shadow"))["book"] == "shadow"
    assert books.derive_trade_book(_sig(entry_alert_status="shadow_sector_cap"))["book"] == "shadow"
    s = _sig(mode="scalp")
    assert not books.in_book(s, "operator") and books.in_book(s, "shadow")


# ---- outcomes / realized R ------------------------------------------------
def test_expired_after_entry_is_unresolved_not_pnl():
    s = _sig(final_outcome="expired", final_r=0, entry_triggered=1)
    assert books.outcome_class(s) == books.EXPIRED_UNRESOLVED
    assert books.realized_r(s) is None          # NOT counted as a 0R realized loss/flat


def test_win_loss_realized():
    assert books.realized_r(_sig(final_outcome="win", final_r=2.0)) == 2.0
    assert books.realized_r(_sig(final_outcome="loss", final_r=-1.0)) == -1.0


def test_win_with_negative_r_is_needs_review():
    s = _sig(final_outcome="win", final_r=-1.0)
    assert books.outcome_class(s) == books.NEEDS_REVIEW
    assert books.realized_r(s) is None


# ---- economic dedup -------------------------------------------------------
def test_ten_duplicates_collapse_to_one():
    rows = []
    for i in range(10):
        rows.append(_sig(signal_id=f"dup{i}", final_outcome="loss", final_r=-1.0,
                         checked_at=f"2026-06-20T0{i}:00:00Z",
                         exit_at="2026-06-20T05:00:00Z"))
    collapsed = books.collapse_economic_trades(rows)
    assert len(collapsed) == 1
    assert collapsed[0]["duplicates_collapsed_count"] == 9
    assert len(collapsed[0]["duplicate_signal_ids"]) == 9


def test_raw_rows_do_not_inflate_r():
    # 10 duplicate -1R rows of ONE setup must sum to -1R, not -10R.
    rows = [_sig(signal_id=f"d{i}", final_outcome="loss", final_r=-1.0,
                 exit_at="2026-06-20T05:00:00Z") for i in range(10)]
    trades = books.collapse_economic_trades(rows)
    total = sum(r for r in (books.realized_r(t) for t in trades) if r is not None)
    assert total == -1.0


def test_terminal_outcome_preferred_over_stale_open():
    # same setup: one stale 'open' row (later checked_at) + one terminal 'win'
    rows = [
        _sig(signal_id="a", final_outcome="win", final_r=2.0, exit_at="2026-06-20T05:00:00Z",
             checked_at="2026-06-20T05:00:00Z"),
        _sig(signal_id="b", final_outcome=None, entry_triggered=1, status="triggered",
             checked_at="2026-06-20T09:00:00Z"),
    ]
    collapsed = books.collapse_economic_trades(rows)
    assert len(collapsed) == 1
    assert books.outcome_class(collapsed[0]) == books.WIN   # terminal wins over later open


def test_shadow_excluded_from_operator_r():
    rows = [
        _sig(signal_id="op", final_outcome="loss", final_r=-1.0, exit_at="2026-06-20T05:00:00Z"),
        _sig(signal_id="sh", mode="scalp", final_outcome="loss", final_r=-5.0,
             exit_at="2026-06-20T05:00:00Z"),
    ]
    op = books.get_closed_trades(rows, "operator")
    op_r = sum(r for r in (books.realized_r(t) for t in op) if r is not None)
    assert op_r == -1.0          # the -5R scalp shadow must NOT leak into Operator R


def test_books_totals_differ_intentionally():
    rows = [
        _sig(signal_id="op", symbol="AAA/USDT", entry_triggered=1,
             final_outcome="loss", final_r=-1.0, exit_at=_RECENT),
        _sig(signal_id="pp", symbol="BBB/USDT", entry_triggered=1,
             entry_alert_status="error:ReadTimeout", entry_alert_sent=False,
             final_outcome="loss", final_r=-1.0, exit_at=_RECENT),
        _sig(signal_id="sh", symbol="CCC/USDT", mode="scalp", final_outcome="win", final_r=3.0,
             exit_at=_RECENT),
    ]
    s = books.get_dashboard_summary(rows)
    # legacy touch total (old `realized_r`/`touch_r` key, now the single explicit `legacy_touch_r`)
    assert s["operator"]["d7"]["legacy_touch_r"] == -1.0
    assert s["paper"]["d7"]["legacy_touch_r"] == -2.0     # operator + undelivered (distinct setups)
    assert s["shadow"]["d7"]["legacy_touch_r"] == 3.0
    assert "realized_r" not in s["operator"]["d7"]        # the legacy key is GONE (never PnL)
    assert s["delivery_gaps"] == 1  # pp entered but delivery errored → a real gap


# ---- paper execution accounting (Model F) ---------------------------------
def test_paper_execution_be_at_0_6r():
    # TP1 touched (touch +final_r) then stop, MFE +0.7R -> BE = 0R paper.
    s = _sig(entry_triggered=1, final_outcome="loss", final_r=-1.0, stop_hit=1,
             tp1_hit=1, mfe_r=0.7, display_status="closed_loss")
    assert books.touch_r(s) == -1.0
    assert books.paper_execution_r(s) == 0.0
    assert books.paper_exec_flags(s)["giveback"] is True


def test_paper_execution_lock_at_1r_and_stop_below_0_6():
    s_lock = _sig(entry_triggered=1, final_outcome="loss", final_r=-1.0, stop_hit=1,
                  mfe_r=1.4, display_status="closed_loss")
    assert books.paper_execution_r(s_lock) == 0.5
    s_full = _sig(entry_triggered=1, final_outcome="loss", final_r=-1.0, stop_hit=1,
                  mfe_r=0.3, display_status="closed_loss")
    assert books.paper_execution_r(s_full) == -1.0


def test_paper_execution_tp3_runner_and_unavailable():
    win = _sig(entry_triggered=1, final_outcome="win", final_r=3.0, tp3_hit=1,
               mfe_r=3.1, display_status="closed_win")
    assert books.paper_execution_r(win) == 3.0
    # missing MFE on a resolved entered trade -> unavailable (NOT silently 0)
    miss = _sig(entry_triggered=1, final_outcome="loss", final_r=-1.0, stop_hit=1,
                mfe_r=None, display_status="closed_loss")
    assert books.paper_execution_r(miss) is None
    assert books.paper_execution_available(miss) is False


def test_dashboard_headline_uses_paper_execution_and_labels_touch():
    rows = [
        # give-back: touch says +1R (TP1), paper says 0R (BE after +0.6R)
        _sig(signal_id="g", symbol="AAA/USDT", entry_triggered=1, final_outcome="win",
             final_r=1.0, tp1_hit=1, stop_hit=1, mfe_r=0.7, display_status="closed_loss",
             exit_at=_RECENT),
    ]
    s = books.get_dashboard_summary(rows)
    assert "today_paper_execution_r" in s["headline"]
    assert s["headline"]["risk_model"] == books.PAPER_RISK_MODEL
    # operator d7 paper number is present and distinct from the legacy touch on the giveback
    assert s["operator"]["d7"]["paper_execution_r"] == 0.0
    assert s["operator"]["d7"]["legacy_touch_r"] == 1.0
    # headline exposes the legacy touch under its explicit name, never as PnL / "touch_r"
    assert "today_legacy_touch_r" in s["headline"] and "today_touch_r" not in s["headline"]
    assert s["headline"]["authoritative_metric"] == "usd_net_after_fees_slippage_funding"
    assert "Touch R" in s["headline"]["label"]


def test_closed_trade_analytics_prefers_usd_and_builds_calendar():
    rows = [
        _sig(signal_id="a", symbol="AAA/USDT", entry_triggered=1,
             final_outcome="win", final_r=2.0, tp2_hit=1, mfe_r=2.1,
             display_status="closed_win", exit_at="2026-07-01T10:00:00Z"),
        _sig(signal_id="b", symbol="BBB/USDT", entry_triggered=1,
             final_outcome="loss", final_r=-1.0, stop_hit=1, mfe_r=0.2,
             display_status="closed_loss", exit_at="2026-07-01T12:00:00Z"),
    ]
    ledger = {"a": {"net_pnl_usdt": 80.0}, "b": {"net_pnl_usdt": -25.5}}
    out = books.closed_trade_analytics(rows, ledger)
    assert out["metric"] == "usd_net"
    assert out["total_pnl_usd"] == 54.5
    assert out["total_r"] == 1.0
    assert out["series"][-1]["cumulative_usd"] == 54.5
    assert out["days"][0]["date"] == "2026-07-01"
    assert out["days"][0]["trades"] == 2
    assert out["days"][0]["net_pnl_usd"] == 54.5
