"""FINAL UI VISIBILITY PASS tests — per-trade A/B detail, fee assumptions, maker realism,
forward-first ordering. Read-only; live locked; final_r never written by the read-model."""
from __future__ import annotations

from pathlib import Path

import pytest

from app import paper_shadow
from app.config import get_settings


# ---- PART 2: fee assumptions ----
def test_fee_assumptions_default_profile_after_fees():
    f = paper_shadow.fee_assumptions()
    assert f["active_profile"] == "bybit_non_vip_usdt_perp"
    assert f["all_numbers_after_fees"] is True
    assert f["maker_fee"] < f["taker_fee"]               # maker cheaper than taker
    assert f["custom_account_override"] is False


# ---- PART 1: per-trade A/B detail + forward-first ordering ----
def _trades():
    t = paper_shadow.trades(limit=40)
    if not t.get("available") or not t.get("trades"):
        pytest.skip("desk DB / shadow rows not present in this environment")
    return t["trades"]


def test_trades_have_ab_detail_and_delta():
    rows = _trades()
    t = rows[0]
    assert "delta" in t and "net_r" in t["delta"]
    assert "why" in t and "valid_forward" in t
    branch = t.get("B") or t.get("A")
    for k in ("side", "entry_mode", "fill_status", "gross_r", "net_r", "fees_usd"):
        assert k in branch


def test_forward_rows_surface_before_backfill():
    rows = _trades()
    seen_backfill = False
    for t in rows:
        if not t.get("valid_forward"):
            seen_backfill = True
        else:
            # once a backfill row appears, no valid-forward row may follow
            assert not seen_backfill, "forward rows must be ordered before backfill rows"


# ---- PART 3: maker realism present in the forward monitor ----
def test_forward_monitor_exposes_maker_block():
    fwd = paper_shadow.forward_monitor()
    if not fwd.get("available"):
        pytest.skip("forward monitor not available")
    assert "maker" in fwd
    for k in ("posted", "filled", "missed", "taker_fallback", "fill_rate_pct"):
        assert k in fwd["maker"]


# ---- guardrails: live locked + read-model never writes final_r ----
def test_live_locked():
    s = get_settings()
    assert getattr(s, "auto_live_locked", True) is True


def test_read_model_has_no_write_sql():
    src = Path(paper_shadow.__file__).read_text(encoding="utf-8").upper()
    assert "FINAL_R" not in src or "SET FINAL_R" not in src
    for verb in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE"):
        assert verb not in src, f"read-model must not contain write SQL: {verb}"


# ---- item 7 (2026-07-03): per-mode promotion readiness read-model (read-only, live locked) ----
def test_readiness_by_mode_shape_and_live_locked():
    r = paper_shadow.readiness_by_mode()
    assert r["live_locked"] is True
    assert r["executed"] is False
    assert isinstance(r["modes"], list)
    # never advertises auto-promotion; the only "ready" verdict is operator-review framed
    assert "operator sign-off" in r["note"].lower()
    assert "fee_profile_integrity_ok" in r
    for m in r["modes"]:
        assert m["verdict"] in ("NOT_READY", "WATCH", "READY_FOR_OPERATOR_REVIEW")
        for k in ("asset_class", "mode", "B_net_usd", "A_net_usd", "data_gap_late_share",
                  "fee_profile_integrity_ok"):
            assert k in m


def test_readiness_never_auto_promotes():
    r = paper_shadow.readiness_by_mode()
    # bare "READY" (auto-promotion wording) must never appear — only READY_FOR_OPERATOR_REVIEW
    verdicts = {m["verdict"] for m in r["modes"]}
    assert "READY" not in verdicts
