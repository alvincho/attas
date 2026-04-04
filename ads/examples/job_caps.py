"""
Job Caps module for `ads.examples.job_caps`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace. This subpackage collects small examples that
show how ADS job capabilities and providers can be composed.

Important callables in this file include `mock_daily_price_cap`,
`mock_financial_statements_cap`, `mock_fundamentals_cap`, `mock_news_cap`, and
`mock_security_master_cap`, which capture the primary workflow implemented by the
module.
"""

from __future__ import annotations

from ads.models import JobDetail, JobResult


def _job_symbol(job: JobDetail, default: str = "DEMO") -> str:
    """Internal helper for job symbol."""
    symbol = (job.payload or {}).get("symbol") if isinstance(job.payload, dict) else None
    return symbol or (job.symbols[0] if job.symbols else default)


def mock_security_master_cap(job: JobDetail) -> JobResult:
    """Handle mock security master cap."""
    symbol = _job_symbol(job)
    return JobResult(
        job_id=job.id,
        status="completed",
        collected_rows=[
            {
                "symbol": symbol,
                "name": f"{symbol} Holdings",
                "instrument_type": "equity",
                "exchange": "NASDAQ",
                "currency": "USD",
                "is_active": True,
                "provider": "mock",
                "metadata": {"source": "demo"},
            }
        ],
        raw_payload={"provider": "mock", "dataset": "security_master"},
        result_summary={"rows": 1},
    )


def mock_daily_price_cap(job: JobDetail) -> JobResult:
    """Handle mock daily price cap."""
    symbol = _job_symbol(job)
    return JobResult(
        job_id=job.id,
        status="completed",
        collected_rows=[
            {
                "symbol": symbol,
                "trade_date": "2026-03-28",
                "open": 100.0,
                "high": 102.0,
                "low": 99.5,
                "close": 101.25,
                "volume": 10000,
            }
        ],
        raw_payload={"provider": "mock"},
        result_summary={"rows": 1},
    )


def mock_fundamentals_cap(job: JobDetail) -> JobResult:
    """Handle mock fundamentals cap."""
    symbol = _job_symbol(job)
    return JobResult(
        job_id=job.id,
        status="completed",
        collected_rows=[
            {
                "symbol": symbol,
                "as_of_date": "2026-03-28",
                "market_cap": 2500000000000,
                "pe_ratio": 31.2,
                "dividend_yield": 0.006,
                "sector": "Technology",
                "industry": "Software",
                "provider": "mock",
                "data": {"source": "demo"},
            }
        ],
        raw_payload={"provider": "mock", "dataset": "fundamentals"},
        result_summary={"rows": 1},
    )


def mock_financial_statements_cap(job: JobDetail) -> JobResult:
    """Handle mock financial statements cap."""
    symbol = _job_symbol(job)
    statement_type = (
        (job.payload or {}).get("statement_type")
        if isinstance(job.payload, dict)
        else None
    ) or "income_statement"
    return JobResult(
        job_id=job.id,
        status="completed",
        collected_rows=[
            {
                "symbol": symbol,
                "statement_type": statement_type,
                "period_end": "2025-12-31",
                "fiscal_period": "FY2025",
                "currency": "USD",
                "provider": "mock",
                "data": {
                    "revenue": 123456789,
                    "net_income": 23456789,
                },
            }
        ],
        raw_payload={"provider": "mock", "dataset": "financial_statements"},
        result_summary={"rows": 1},
    )


def mock_news_cap(job: JobDetail) -> JobResult:
    """Handle mock news cap."""
    symbol = _job_symbol(job)
    return JobResult(
        job_id=job.id,
        status="completed",
        collected_rows=[
            {
                "symbol": symbol,
                "headline": f"{symbol} posts demo update",
                "summary": "Mock ADS news item for end-to-end local testing.",
                "url": f"https://example.com/{symbol.lower()}/demo-story",
                "source": "ExampleWire",
                "source_url": "https://example.com",
                "published_at": "2026-03-28T09:30:00+00:00",
                "sentiment": 0.42,
                "data": {"source": "demo"},
            }
        ],
        raw_payload={"provider": "mock", "dataset": "news"},
        result_summary={"rows": 1},
    )
