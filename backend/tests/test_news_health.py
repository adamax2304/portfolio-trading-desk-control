"""News Source Health backend read-model (item 1/7 control-plane) — read-only, live locked."""
from __future__ import annotations

from pathlib import Path

from app import news_health


def test_source_health_shape_and_live_locked():
    r = news_health.source_health()
    # available True (artifact present) or False (fail-open) — either way live_locked + shape hold
    assert r["live_locked"] is True
    assert "summary" in r and "sources" in r
    assert isinstance(r["sources"], list)
    if not r["available"]:
        assert "reason" in r


def test_entity_health_shape_and_live_locked():
    r = news_health.entity_health()
    assert r["live_locked"] is True
    assert "severity" in r and "windows" in r
    if not r["available"]:
        assert "reason" in r


def test_news_health_module_is_read_only():
    src = Path(news_health.__file__).read_text(encoding="utf-8").upper()
    for verb in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE"):
        assert verb not in src
