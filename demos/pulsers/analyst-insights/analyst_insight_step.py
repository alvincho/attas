"""
Analyst Insight pipeline step for the Analyst Insights area.

The demos tree contains runnable examples that illustrate how higher-level pipelines fit
together.

It mainly publishes constants such as `ANALYST_COVERAGE` and `symbol` that are consumed
elsewhere in the codebase.
"""

def _normalize_symbol(value):
    """Internal helper to normalize the symbol."""
    return str(value or "").strip().upper()


def _clone(value):
    """Internal helper for clone."""
    if isinstance(value, dict):
        cloned = {}
        for key, item in value.items():
            cloned[str(key)] = _clone(item)
        return cloned
    if isinstance(value, list):
        return [_clone(item) for item in value]
    return value


ANALYST_COVERAGE = {
    "NVDA": {
        "analyst": "North Harbor Research",
        "updated_at": "2026-04-02T08:30:00Z",
        "rating_summary": {
            "rating_label": "outperform",
            "target_price": 1280.0,
            "current_price_reference": 1105.0,
            "time_horizon": "12m",
            "confidence_label": "high",
            "summary": "The desk expects AI compute demand to stay tight enough to support another year of elevated revenue growth and durable margin performance."
        },
        "thesis_bullets": {
            "time_horizon": "12m",
            "confidence_score": 0.84,
            "bullets": [
                "Hyperscaler and sovereign demand still supports a strong multi-quarter accelerator backlog.",
                "Software and networking attach can keep mix improving even if GPU unit growth moderates.",
                "Management has continued to execute through product transitions without losing pricing power."
            ]
        },
        "risk_watch": {
            "risks": [
                {
                    "risk": "Large customers stretch deployment cycles after major cluster buildouts.",
                    "signal_to_watch": "Cloud capex commentary and lead-time compression during earnings calls.",
                    "severity": "high"
                },
                {
                    "risk": "Export controls pressure mix and make geographic demand harder to replace cleanly.",
                    "signal_to_watch": "Management disclosure on regional revenue composition and channel inventory.",
                    "severity": "medium"
                },
                {
                    "risk": "Competition improves enough to reduce pricing leverage in the next platform cycle.",
                    "signal_to_watch": "Gross margin guidance and customer comments around alternative accelerator adoption.",
                    "severity": "medium"
                }
            ]
        },
        "scenario_grid": {
            "scenarios": [
                {
                    "case": "bull",
                    "probability": 0.25,
                    "fair_value": 1400.0,
                    "narrative": "Demand remains supply constrained through the full planning cycle and software monetization expands faster than expected."
                },
                {
                    "case": "base",
                    "probability": 0.5,
                    "fair_value": 1280.0,
                    "narrative": "Revenue growth moderates from peak levels but stays well above large-cap semiconductor peers, with margins remaining structurally higher."
                },
                {
                    "case": "bear",
                    "probability": 0.25,
                    "fair_value": 930.0,
                    "narrative": "Customer digestion arrives sooner than expected and forces a reset in near-term revenue and valuation multiples."
                }
            ]
        }
    }
}


symbol = _normalize_symbol(input_data.get("symbol"))
if not symbol:
    result = {"error": "symbol is required"}
else:
    coverage = ANALYST_COVERAGE.get(symbol)
    if not isinstance(coverage, dict):
        supported_symbols = sorted(ANALYST_COVERAGE.keys())
        result = {
            "error": f"symbol '{symbol}' is not covered by this analyst pulser demo.",
            "supported_symbols": supported_symbols
        }
    else:
        view = str(pulse.get("insight_view") or "").strip()
        payload = _clone(coverage.get(view) or {})
        payload["symbol"] = symbol
        payload["analyst"] = str(coverage.get("analyst") or "Unknown Analyst")
        payload["updated_at"] = str(coverage.get("updated_at") or "")
        if view not in {"rating_summary", "thesis_bullets", "risk_watch", "scenario_grid"}:
            result = {"error": f"Unsupported insight_view '{view}'."}
        else:
            result = payload
