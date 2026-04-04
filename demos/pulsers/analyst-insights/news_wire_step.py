"""
News Wire pipeline step for the Analyst Insights area.

The demos tree contains runnable examples that illustrate how higher-level pipelines fit
together.

It mainly publishes constants such as `SEEDED_NEWS`, `symbol`, and `count` that are
consumed elsewhere in the codebase.
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


def _coerce_count(value, default=3):
    """Internal helper to coerce the count."""
    if value in (None, ""):
        return default
    try:
        return max(1, int(value))
    except Exception:
        return default


SEEDED_NEWS = {
    "NVDA": [
        {
            "headline": "Nvidia expands sovereign AI pipeline with new Gulf cloud project",
            "published_at": "2026-04-02T07:10:00Z",
            "publisher": "SignalWire Markets",
            "summary": "A new sovereign AI buildout points to another quarter of strong accelerator and networking demand for regional cloud capacity.",
            "url": "https://example.test/news/nvda-sovereign-ai-pipeline",
            "sentiment_label": "positive",
        },
        {
            "headline": "ODM partners flag faster rack-level shipments for next Hopper refresh",
            "published_at": "2026-04-02T05:35:00Z",
            "publisher": "Supply Chain Ledger",
            "summary": "Channel checks suggest rack integration is moving faster than expected, with networking attach still contributing meaningfully to system value.",
            "url": "https://example.test/news/nvda-rack-refresh",
            "sentiment_label": "positive",
        },
        {
            "headline": "Export-control debate reopens questions on geographic mix durability",
            "published_at": "2026-04-01T23:45:00Z",
            "publisher": "Policy Desk",
            "summary": "Policy commentary highlights a potential risk to regional mix and near-term visibility if compliance rules tighten again.",
            "url": "https://example.test/news/nvda-export-control-risk",
            "sentiment_label": "mixed",
        },
    ],
    "AAPL": [
        {
            "headline": "Apple highlights enterprise rollout for on-device assistant tools",
            "published_at": "2026-04-02T06:20:00Z",
            "publisher": "Device Daily",
            "summary": "The company framed its new assistant features as a productivity and privacy story for premium enterprise customers.",
            "url": "https://example.test/news/aapl-enterprise-assistant",
            "sentiment_label": "positive",
        },
        {
            "headline": "Component lead times improve ahead of the next iPhone cycle",
            "published_at": "2026-04-01T22:15:00Z",
            "publisher": "Supply Tracker",
            "summary": "Supplier commentary suggests steadier logistics heading into the second half product ramp.",
            "url": "https://example.test/news/aapl-component-lead-times",
            "sentiment_label": "positive",
        },
    ],
}


symbol = _normalize_symbol(input_data.get("symbol"))
count = _coerce_count(input_data.get("number_of_articles"))

if not symbol:
    result = {"error": "symbol is required"}
else:
    articles = SEEDED_NEWS.get(symbol)
    if not isinstance(articles, list):
        result = {
            "error": f"symbol '{symbol}' is not covered by this demo news wire.",
            "supported_symbols": sorted(SEEDED_NEWS.keys()),
        }
    else:
        selected = [_clone(article) for article in articles[:count]]
        result = {
            "symbol": symbol,
            "number_of_articles": len(selected),
            "articles": selected,
            "source": "demo_news_wire",
        }
