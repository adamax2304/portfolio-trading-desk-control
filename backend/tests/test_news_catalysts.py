"""News Catalysts / risk-only backend read-model (production news expansion, 2026-07-04).

Read-only, live locked. Verifies shape + the risk-only guardrails + no write SQL.
"""
from __future__ import annotations

from pathlib import Path

from app import news_catalysts


def test_catalysts_shape_and_live_locked():
    r = news_catalysts.catalysts()
    # available True (artifact present) or False (fail-open) — either way live_locked + shape hold.
    assert r["live_locked"] is True
    assert "symbols_requiring_operator_review" in r
    assert isinstance(r["symbols_requiring_operator_review"], list)
    assert isinstance(r["warnings"], list)
    if not r["available"]:
        assert "reason" in r


def test_catalysts_guardrails_are_risk_only():
    r = news_catalysts.catalysts()
    allowed = set(r.get("allowed_effects") or [])
    # Only the risk-only effects may ever appear — never a score/tier/buy/sell/live effect.
    assert allowed <= {
        "risk_warning", "block_requires_operator_review", "do_not_chase_warning",
        "freshness_warning", "source_quality_warning", "conflicting_news_warning",
    }
    for forbidden in ("score_boost", "tier_upgrade", "buy_sell_signal_from_news",
                      "live_order", "auto_live_or_manual_live_unlock"):
        assert forbidden in (r.get("not_allowed") or [])
    for w in r.get("warnings", []):
        assert w["effect"] in allowed or not allowed


def test_news_catalysts_module_is_read_only():
    src = Path(news_catalysts.__file__).read_text(encoding="utf-8").upper()
    for verb in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE"):
        assert verb not in src
