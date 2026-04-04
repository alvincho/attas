"""
Custom Sources module for `ads.examples.custom_sources`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace. This subpackage collects small examples that
show how ADS job capabilities and providers can be composed.

Important callables in this file include `demo_alt_price_cap` and
`demo_press_release_cap`, which capture the primary workflow implemented by the module.
"""

from __future__ import annotations

from ads.models import JobDetail, JobResult


def _job_payload(job: JobDetail) -> dict:
    """Internal helper to return the job payload."""
    return dict(job.payload or {}) if isinstance(job.payload, dict) else {}


def _job_symbol(job: JobDetail, default: str = "DEMO") -> str:
    """Internal helper for job symbol."""
    payload = _job_payload(job)
    symbol = payload.get("symbol")
    return symbol or (job.symbols[0] if job.symbols else default)


def demo_press_release_cap(job: JobDetail) -> JobResult:
    """Handle demo press release cap."""
    payload = _job_payload(job)
    symbol = _job_symbol(job)
    source_name = str(payload.get("source_name") or "UserFeed")
    source_url = str(payload.get("source_url") or "https://example.com/user-feed")
    published_at = str(payload.get("published_at") or "2026-04-02T09:30:00+00:00")
    article_url = str(payload.get("article_url") or f"{source_url.rstrip('/')}/{symbol.lower()}-custom-story")
    headline = str(payload.get("headline") or f"{symbol} custom source update")
    summary = str(payload.get("summary") or "Demo article collected from a user-defined ADS source.")

    collected_row = {
        "symbol": symbol,
        "headline": headline,
        "summary": summary,
        "url": article_url,
        "source": source_name,
        "source_url": source_url,
        "published_at": published_at,
        "sentiment": float(payload.get("sentiment") or 0.0),
        "data": {
            "source_kind": "user_defined",
            "collector": "ads.examples.custom_sources:demo_press_release_cap",
            "input_payload": payload,
        },
    }
    raw_payload = {
        "provider": source_name,
        "dataset": "custom_press_release",
        "content": payload,
    }
    return JobResult(
        job_id=job.id,
        status="completed",
        collected_rows=[collected_row],
        raw_payload=raw_payload,
        result_summary={"rows": 1, "dataset": "ads_news"},
    )


def demo_alt_price_cap(job: JobDetail) -> JobResult:
    """Handle demo alt price cap."""
    payload = _job_payload(job)
    symbol = _job_symbol(job)
    trade_date = str(payload.get("trade_date") or "2026-04-02")
    close = float(payload.get("close") or 101.25)
    open_price = float(payload.get("open") or close - 0.75)
    high = float(payload.get("high") or close + 1.2)
    low = float(payload.get("low") or close - 1.4)
    volume = int(payload.get("volume") or 125000)

    collected_row = {
        "symbol": symbol,
        "trade_date": trade_date,
        "open": open_price,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "source_url": str(payload.get("source_url") or "https://example.com/alt-prices"),
        "data": {
            "source_kind": "user_defined",
            "collector": "ads.examples.custom_sources:demo_alt_price_cap",
            "input_payload": payload,
        },
    }
    raw_payload = {
        "provider": str(payload.get("source_name") or "AltPriceFeed"),
        "dataset": "custom_daily_price",
        "content": payload,
    }
    return JobResult(
        job_id=job.id,
        status="completed",
        collected_rows=[collected_row],
        raw_payload=raw_payload,
        result_summary={"rows": 1, "dataset": "ads_daily_price"},
    )
