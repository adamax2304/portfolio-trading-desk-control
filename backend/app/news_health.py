"""News diagnostics read-models for the Mini App — READ-ONLY.

Reads the diagnostics JSON the crypto-ai-desk writes
(`<desk_root>/data/diagnostics/news_source_health.json`, produced by `news-source-health`) and
returns it for the UI. Never fetches network, never writes, never affects trading. Fail-open: if the
artifact is missing it returns available=False with a hint to run the desk command.
"""
from __future__ import annotations

import json
from typing import Any

from . import desk_adapter


def source_health() -> dict[str, Any]:
    try:
        root = desk_adapter._desk_root()
        p = root / "data" / "diagnostics" / "news_source_health.json"
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"available": False, "live_locked": True,
                "reason": "news_source_health.json not found — run `news-source-health` on the desk",
                "summary": {}, "sources": []}
    data["available"] = True
    data["live_locked"] = True
    return data


def entity_health() -> dict[str, Any]:
    """READ-ONLY entity resolver freshness/coverage.

    Mirrors `<desk_root>/data/diagnostics/news_entity_health.json`, produced by
    `news-entity-health` in the desk repo. Never resolves news, never writes, and
    never affects scoring/routing/live.
    """
    try:
        root = desk_adapter._desk_root()
        p = root / "data" / "diagnostics" / "news_entity_health.json"
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"available": False, "live_locked": True,
                "reason": "news_entity_health.json not found — run `news-entity-health` on the desk",
                "severity": "UNKNOWN", "windows": {}}
    data["available"] = True
    data["live_locked"] = True
    return data
