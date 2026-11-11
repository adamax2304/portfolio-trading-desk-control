"""Regime normalization (PART 8) — free-text `market_regime` → canonical enum.

`proposed_signals.market_regime` is free text from the detector/LLM
(`bullish`, `chop`, `risk_off`, `bullish trend`, `''`, `range/chop`, `transition`,
`high-volatility danger`, …). The app showed "unknown" for the empty string and any
unmapped value. This maps to a stable label + source + confidence; "unknown" only when
the field is genuinely empty/missing.
"""
from __future__ import annotations

CANON = {"trend_up", "trend_down", "range", "chop", "transition", "risk_off", "risk_on",
         "high_volatility", "unknown"}

# substring rules applied in order (first match wins) on the lowercased raw value
_RULES = [
    ("bearish trend", "trend_down"), ("bear trend", "trend_down"), ("downtrend", "trend_down"),
    ("trend_down", "trend_down"),
    ("bullish trend", "trend_up"), ("bull trend", "trend_up"), ("uptrend", "trend_up"),
    ("trend_up", "trend_up"),
    ("range/chop", "range"), ("range", "range"),
    ("chop", "chop"), ("choppy", "chop"),
    ("transition", "transition"), ("mixed", "transition"),
    ("risk_off", "risk_off"), ("risk-off", "risk_off"), ("panic", "risk_off"),
    ("high-volatility", "high_volatility"), ("high volatility", "high_volatility"),
    ("danger", "high_volatility"), ("volatile", "high_volatility"),
    ("risk_on", "risk_on"), ("risk-on", "risk_on"), ("euphoria", "risk_on"),
    ("bullish", "trend_up"), ("bull", "trend_up"),
    ("bearish", "trend_down"), ("bear", "trend_down"),
]

_LABELS = {
    "trend_up": "Trend ↑", "trend_down": "Trend ↓", "range": "Range", "chop": "Chop",
    "transition": "Transition", "risk_off": "Risk-off", "risk_on": "Risk-on",
    "high_volatility": "High volatility", "unknown": "Unknown",
}


def normalize_regime(raw, source: str = "detector") -> dict:
    """Return {regime, label, raw, source, confidence}. Never raises."""
    s = (str(raw or "")).strip().lower()
    if not s:
        return {"regime": "unknown", "label": "Unknown", "raw": raw or "",
                "source": "none", "confidence": 0.0,
                "reason": "market_regime empty in signal"}
    for needle, canon in _RULES:
        if needle in s:
            # exact match → higher confidence than a loose substring hit
            conf = 0.9 if s == needle else 0.7
            return {"regime": canon, "label": _LABELS[canon], "raw": raw,
                    "source": source, "confidence": conf, "reason": f"matched '{needle}'"}
    return {"regime": "unknown", "label": "Unknown", "raw": raw, "source": source,
            "confidence": 0.2, "reason": f"unmapped free-text '{s}'"}
