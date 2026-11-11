"""Production News Catalysts / Risk-warnings read-model for the Mini App (2026-07-04) — READ-ONLY.

Reads the diagnostics JSON the crypto-ai-desk writes
(`<desk_root>/data/diagnostics/news_catalysts.json`, produced by `news-risk`) and returns it for
the UI. It surfaces the RISK-ONLY warnings (block_requires_operator_review / do_not_chase /
risk_warning / freshness / source_quality / conflicting_news) plus the normalized-event summary.

Guardrails, mirrored from the desk: these effects NEVER boost a score, upgrade a tier, create a
buy/sell, place a live order, or unlock live. Never fetches network, never writes, never affects
trading. Fail-open: if the artifact is missing it returns available=False with a hint.
"""
from __future__ import annotations

import json
from typing import Any

from . import desk_adapter


def catalysts() -> dict[str, Any]:
    try:
        root = desk_adapter._desk_root()
        p = root / "data" / "diagnostics" / "news_catalysts.json"
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"available": False, "live_locked": True,
                "reason": "news_catalysts.json not found — run `news-risk` on the desk",
                "symbols_requiring_operator_review": [], "warnings": [],
                "events_summary": {"available": False},
                "allowed_effects": [
                    "risk_warning", "block_requires_operator_review", "do_not_chase_warning",
                    "freshness_warning", "source_quality_warning", "conflicting_news_warning"],
                "not_allowed": ["score_boost", "tier_upgrade", "buy_sell_signal_from_news",
                                "live_order", "auto_live_or_manual_live_unlock"]}
    data["available"] = True
    data["live_locked"] = True
    return data
