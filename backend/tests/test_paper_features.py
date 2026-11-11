"""Paper Feature Flags read-model tests."""
from __future__ import annotations

from app import paper_features


def test_summary_shape_and_safety():
    s = paper_features.paper_features_summary()
    assert s["live_locked"] is True and s["auto_live_locked"] is True
    assert s["risk_model"] == "early_mfe_protection_v1"
    for bucket in ("active", "shadow_or_measuring", "archived", "dangerous_locked"):
        assert isinstance(s[bucket], list)
    # No ACTIVE feature affects real trades.
    for f in s["active"]:
        assert f["affects_trades"] is False
    # Model F + touch-label are active; scalp/C-tier are dangerous_locked.
    active_keys = {f["key"] for f in s["active"]}
    assert "model_f_paper_execution" in active_keys
    assert "touch_r_optimistic_label" in active_keys
    danger_keys = {f["key"] for f in s["dangerous_locked"]}
    assert {"crypto_scalp_actionable", "stocks_c_tier_actionable"} <= danger_keys
    # archived contains the superseded shadow exit manager.
    assert "shadow_exit_manager_variants" in {f["key"] for f in s["archived"]}


def test_counts_match_lists():
    s = paper_features.paper_features_summary()
    assert s["counts"]["active"] == len(s["active"])
    assert s["counts"]["archived"] == len(s["archived"])
    assert s["counts"]["dangerous"] == len(s["dangerous_locked"])
