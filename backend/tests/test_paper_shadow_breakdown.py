"""PART 1/7 — per-mode A/B breakdown endpoint tests. Read-only; forward separated from backfill."""
from __future__ import annotations

from pathlib import Path

import pytest

from app import paper_shadow


def _bd():
    b = paper_shadow.breakdown()
    if not b.get("available"):
        pytest.skip("shadow lane not populated in this environment")
    return b


def test_breakdown_has_dimensions_and_window_split():
    b = _bd()
    for dim in ("mode", "entry_mode", "order_type", "regime", "symbol", "sector", "tp_set"):
        assert dim in b["dimensions"]
    # forward and backfill counted separately
    assert "forward_rows" in b and "backfill_rows" in b


def test_breakdown_group_shape():
    b = _bd()
    groups = b["dimensions"]["mode"]
    assert isinstance(groups, list) and groups
    g = groups[0]
    win = g.get("forward") or g.get("backfill")
    for branch in ("A", "B"):
        for k in ("trades", "net_r", "net_usd", "fees_usd", "win_rate", "maker_fill_rate",
                  "missed_entries", "no_chase", "dir_flips"):
            assert k in win[branch]
    assert "delta_r" in win and "data_gap_excluded" in win


def test_breakdown_filled_only_trades_nonnegative():
    b = _bd()
    for g in b["dimensions"]["mode"]:
        for win in ("forward", "backfill"):
            if g.get(win):
                assert g[win]["A"]["trades"] >= 0 and g[win]["B"]["trades"] >= 0


def test_breakdown_read_model_no_write_sql():
    src = Path(paper_shadow.__file__).read_text(encoding="utf-8").upper()
    for verb in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE"):
        assert verb not in src
