from __future__ import annotations

import json
import logging
import os
import uuid
from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    yf = None

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from attas.pds import derive_pulse_id, normalize_runtime_pulse_entry
from phemacast.agents.pulser import ConfigInput, _assign_path, _read_config, _resolve_path
from phemacast.practices.pulser import GetPulseDataPractice
from prompits.agents.standby import StandbyAgent
from prompits.core.pit import PitAddress
from starlette.concurrency import run_in_threadpool


logger = logging.getLogger(__name__)


COMMON_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {
            "type": "string",
            "description": "Ticker symbol, for example AAPL.",
        }
    },
    "required": ["symbol"],
}

COMMON_INTERVAL_ENUM = ["1m", "5m", "15m", "30m", "1h", "4h", "1d", "1wk", "1mo"]

OHLC_BAR_SERIES_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {
            "type": "string",
            "description": "Ticker symbol, for example AAPL.",
        },
        "interval": {
            "type": "string",
            "enum": COMMON_INTERVAL_ENUM,
            "description": "Bar interval for the requested time series.",
        },
        "start_date": {
            "type": "string",
            "description": "Inclusive lower bound for the requested time series, as an ISO date or datetime.",
        },
        "end_date": {
            "type": "string",
            "description": "Inclusive upper bound for the requested time series, as an ISO date or datetime.",
        },
    },
    "required": ["symbol", "interval", "start_date", "end_date"],
}

OHLC_BAR_SERIES_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        "interval": {"type": "string"},
        "start_date": {"type": "string"},
        "end_date": {"type": "string"},
        "ohlc_series": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "timestamp": {"type": "string"},
                    "open": {"type": "number"},
                    "high": {"type": "number"},
                    "low": {"type": "number"},
                    "close": {"type": "number"},
                    "volume": {"type": "number"},
                },
                "required": ["timestamp", "open", "high", "low", "close"],
            },
        },
        "source": {"type": "string"},
    },
    "required": ["symbol", "interval", "start_date", "end_date", "ohlc_series"],
}


def _build_output_schema(properties: Dict[str, Dict[str, Any]], required: list[str]) -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _pulse_definition(
    *,
    name: str,
    description: str,
    tags: list[str],
    properties: Dict[str, Dict[str, Any]],
    required: list[str],
    mapping: Dict[str, Any],
    input_schema: Optional[Dict[str, Any]] = None,
    output_schema: Optional[Dict[str, Any]] = None,
    test_data: Optional[Dict[str, Any]] = None,
    pulse_address: Optional[str] = None,
    pulse_id: Optional[str] = None,
    include_source: bool = True,
) -> Dict[str, Any]:
    pulse_mapping: Dict[str, Any] = {
        "symbol": "symbol",
        **mapping,
    }
    if include_source:
        pulse_mapping["source"] = {"value": "yfinance"}

    return {
        "name": name,
        "description": description,
        "tags": tags,
        "input_schema": input_schema or COMMON_INPUT_SCHEMA,
        "output_schema": output_schema or _build_output_schema(properties, required),
        "mapping": pulse_mapping,
        "test_data": test_data or {"symbol": "AAPL"},
        "cost": 0,
        "party": "attas",
        **({"pulse_address": pulse_address} if pulse_address else {}),
        **({"pulse_id": pulse_id} if pulse_id else {}),
    }


def _stable_shared_pulse_address(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"plaza-pulse:{str(name).strip().lower()}"))


def _shared_income_statement_pulse(
    *,
    name: str,
    description: str,
    tags: list[str],
    properties: Dict[str, Dict[str, Any]],
    required: list[str],
    mapping: Dict[str, Any],
) -> Dict[str, Any]:
    return _pulse_definition(
        name=name,
        description=description,
        tags=tags,
        properties=properties,
        required=required,
        mapping=mapping,
        pulse_address=_stable_shared_pulse_address(name),
        pulse_id=derive_pulse_id({"name": name}),
        include_source=False,
    )


def _normalize_statement_label(value: Any) -> str:
    text = str(value or "").strip().lower()
    for old, new in (
        ("&", " and "),
        ("/", " "),
        ("-", " "),
        ("_", " "),
        (".", " "),
    ):
        text = text.replace(old, new)
    return " ".join(text.split())


def _format_statement_period(value: Any) -> str:
    candidate = value
    if hasattr(candidate, "to_pydatetime"):
        try:
            candidate = candidate.to_pydatetime()
        except Exception:
            pass
    if isinstance(candidate, datetime):
        return candidate.date().isoformat()
    if isinstance(candidate, date):
        return candidate.isoformat()
    text = str(candidate or "").strip()
    if not text:
        return ""
    if " " in text:
        text = text.split(" ", 1)[0]
    if "T" in text:
        text = text.split("T", 1)[0]
    return text


def _coerce_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, str):
        value = value.replace(",", "").strip()
        if not value:
            return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if numeric != numeric:
        return None
    return numeric


def _calculate_growth_percent(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous is None or previous == 0:
        return None
    return ((current - previous) / abs(previous)) * 100.0


def _calculate_margin_percent(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    return (numerator / denominator) * 100.0


def _series_to_dict(series: Any) -> Dict[Any, Any]:
    if series is None:
        return {}
    if hasattr(series, "to_dict"):
        try:
            data = series.to_dict()
        except Exception:
            data = None
        if isinstance(data, dict):
            return data
    if isinstance(series, Mapping):
        return dict(series)
    index = list(getattr(series, "index", []))
    values = list(getattr(series, "values", []))
    if index and len(index) == len(values):
        return dict(zip(index, values))
    return {}


def _coerce_iso_bound(value: Any) -> tuple[datetime, str, bool]:
    has_time_component = False
    if isinstance(value, datetime):
        parsed = value
        has_time_component = True
    elif isinstance(value, date):
        parsed = datetime.combine(value, datetime.min.time())
    else:
        text = str(value or "").strip()
        if not text:
            raise ValueError("start_date and end_date are required")
        has_time_component = "T" in text or " " in text
        candidate = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            parsed = datetime.combine(date.fromisoformat(text), datetime.min.time())
    return parsed, _format_history_timestamp(parsed), has_time_component


def _format_history_timestamp(value: Any) -> str:
    candidate = value
    if hasattr(candidate, "to_pydatetime"):
        try:
            candidate = candidate.to_pydatetime()
        except Exception:
            pass
    if isinstance(candidate, date) and not isinstance(candidate, datetime):
        return f"{candidate.isoformat()}T00:00:00Z"
    if isinstance(candidate, datetime):
        if candidate.tzinfo is None:
            candidate = candidate.replace(tzinfo=timezone.utc)
        else:
            candidate = candidate.astimezone(timezone.utc)
        text = candidate.isoformat()
        if text.endswith("+00:00"):
            text = f"{text[:-6]}Z"
        return text.replace(" ", "T")
    text = str(candidate or "").strip()
    if not text:
        return ""
    if " " in text:
        text = text.replace(" ", "T", 1)
    if text.endswith("+00:00"):
        return f"{text[:-6]}Z"
    return text


INCOME_STATEMENT_ROW_ALIASES = {
    "revenue": ("Total Revenue", "Operating Revenue", "Revenue", "Sales Revenue"),
    "gross_profit": ("Gross Profit",),
    "operating_income": ("Operating Income", "EBIT", "Operating Profit"),
    "net_income": ("Net Income", "Net Income Common Stockholders", "Net Income Applicable To Common Shares"),
    "eps_basic": ("Basic EPS", "Basic EPS Continuing Operations"),
    "eps_diluted": ("Diluted EPS", "Diluted EPS Continuing Operations"),
}


INCOME_STATEMENT_PULSE_BEHAVIOR = {
    "income_statement_revenue": {"period_type": "annual", "required_field": "revenue"},
    "income_statement_gross_profit": {"period_type": "annual", "required_field": "gross_profit"},
    "income_statement_operating_income": {"period_type": "annual", "required_field": "operating_income"},
    "income_statement_net_income": {"period_type": "annual", "required_field": "net_income"},
    "income_statement_eps": {"period_type": "quarterly", "required_field": "eps_diluted"},
}


SHARED_INCOME_STATEMENT_PULSES = [
    _shared_income_statement_pulse(
        name="income_statement_revenue",
        description="Latest annual revenue line item from Yahoo Finance income statements.",
        tags=["finance", "fundamentals", "income-statement", "annual"],
        properties={
            "symbol": {"type": "string"},
            "period_end": {"type": "string"},
            "period_type": {"type": "string"},
            "revenue": {"type": "number"},
            "currency": {"type": "string"},
            "year_over_year_growth_percent": {"type": "number"},
        },
        required=["symbol", "period_end", "revenue"],
        mapping={
            "period_end": "period_end",
            "period_type": "period_type",
            "revenue": "revenue",
            "currency": "currency",
            "year_over_year_growth_percent": "revenue_year_over_year_growth_percent",
        },
    ),
    _shared_income_statement_pulse(
        name="income_statement_gross_profit",
        description="Latest annual gross profit line item from Yahoo Finance income statements.",
        tags=["finance", "fundamentals", "income-statement", "annual"],
        properties={
            "symbol": {"type": "string"},
            "period_end": {"type": "string"},
            "period_type": {"type": "string"},
            "gross_profit": {"type": "number"},
            "gross_margin_percent": {"type": "number"},
            "currency": {"type": "string"},
            "year_over_year_growth_percent": {"type": "number"},
        },
        required=["symbol", "period_end", "gross_profit"],
        mapping={
            "period_end": "period_end",
            "period_type": "period_type",
            "gross_profit": "gross_profit",
            "gross_margin_percent": "gross_margin_percent",
            "currency": "currency",
            "year_over_year_growth_percent": "gross_profit_year_over_year_growth_percent",
        },
    ),
    _shared_income_statement_pulse(
        name="income_statement_operating_income",
        description="Latest annual operating income line item from Yahoo Finance income statements.",
        tags=["finance", "fundamentals", "income-statement", "annual"],
        properties={
            "symbol": {"type": "string"},
            "period_end": {"type": "string"},
            "period_type": {"type": "string"},
            "operating_income": {"type": "number"},
            "operating_margin_percent": {"type": "number"},
            "currency": {"type": "string"},
            "year_over_year_growth_percent": {"type": "number"},
        },
        required=["symbol", "period_end", "operating_income"],
        mapping={
            "period_end": "period_end",
            "period_type": "period_type",
            "operating_income": "operating_income",
            "operating_margin_percent": "operating_margin_percent",
            "currency": "currency",
            "year_over_year_growth_percent": "operating_income_year_over_year_growth_percent",
        },
    ),
    _shared_income_statement_pulse(
        name="income_statement_net_income",
        description="Latest annual net income line item from Yahoo Finance income statements.",
        tags=["finance", "fundamentals", "income-statement", "annual"],
        properties={
            "symbol": {"type": "string"},
            "period_end": {"type": "string"},
            "period_type": {"type": "string"},
            "net_income": {"type": "number"},
            "net_margin_percent": {"type": "number"},
            "currency": {"type": "string"},
            "year_over_year_growth_percent": {"type": "number"},
        },
        required=["symbol", "period_end", "net_income"],
        mapping={
            "period_end": "period_end",
            "period_type": "period_type",
            "net_income": "net_income",
            "net_margin_percent": "net_margin_percent",
            "currency": "currency",
            "year_over_year_growth_percent": "net_income_year_over_year_growth_percent",
        },
    ),
    _shared_income_statement_pulse(
        name="income_statement_eps",
        description="Latest quarterly basic and diluted EPS from Yahoo Finance income statements.",
        tags=["finance", "fundamentals", "income-statement", "quarterly"],
        properties={
            "symbol": {"type": "string"},
            "period_end": {"type": "string"},
            "period_type": {"type": "string"},
            "eps_basic": {"type": "number"},
            "eps_diluted": {"type": "number"},
            "currency": {"type": "string"},
            "year_over_year_growth_percent": {"type": "number"},
        },
        required=["symbol", "period_end", "eps_diluted"],
        mapping={
            "period_end": "period_end",
            "period_type": "period_type",
            "eps_basic": "eps_basic",
            "eps_diluted": "eps_diluted",
            "currency": "currency",
            "year_over_year_growth_percent": "eps_diluted_year_over_year_growth_percent",
        },
    ),
]


DEFAULT_SUPPORTED_PULSES = [
    _pulse_definition(
        name="last_price",
        description="Latest traded market price from Yahoo Finance.",
        tags=["finance", "quote", "price"],
        properties={
            "symbol": {"type": "string"},
            "last_price": {"type": "number"},
            "currency": {"type": "string"},
            "source": {"type": "string"},
        },
        required=["symbol", "last_price"],
        mapping={"last_price": "last_price", "currency": "currency"},
    ),
    _pulse_definition(
        name="ohlc_bar_series",
        description="Historical OHLCV bar series from Yahoo Finance for a requested symbol, interval, and date range.",
        tags=["finance", "market-data", "ohlc", "timeseries"],
        properties={},
        required=[],
        mapping={
            "interval": "interval",
            "start_date": "start_date",
            "end_date": "end_date",
            "ohlc_series": "ohlc_series",
        },
        input_schema=OHLC_BAR_SERIES_INPUT_SCHEMA,
        output_schema=OHLC_BAR_SERIES_OUTPUT_SCHEMA,
        test_data={
            "symbol": "AAPL",
            "interval": "1d",
            "start_date": "2025-01-01",
            "end_date": "2025-03-31",
        },
        pulse_address="ai.attas.finance.price.ohlc_bar_series",
        pulse_id=derive_pulse_id({"name": "ohlc_bar_series"}),
    ),
    _pulse_definition(
        name="previous_close",
        description="Previous close from Yahoo Finance.",
        tags=["finance", "quote", "close"],
        properties={
            "symbol": {"type": "string"},
            "previous_close": {"type": "number"},
            "currency": {"type": "string"},
            "source": {"type": "string"},
        },
        required=["symbol", "previous_close"],
        mapping={"previous_close": "previous_close", "currency": "currency"},
    ),
    _pulse_definition(
        name="open_price",
        description="Session open price from Yahoo Finance.",
        tags=["finance", "quote", "open"],
        properties={
            "symbol": {"type": "string"},
            "open_price": {"type": "number"},
            "currency": {"type": "string"},
            "source": {"type": "string"},
        },
        required=["symbol", "open_price"],
        mapping={"open_price": "open_price", "currency": "currency"},
    ),
    _pulse_definition(
        name="market_state",
        description="Current Yahoo Finance session state for the ticker.",
        tags=["finance", "quote", "session"],
        properties={
            "symbol": {"type": "string"},
            "market_state": {"type": "string"},
            "exchange": {"type": "string"},
            "source": {"type": "string"},
        },
        required=["symbol", "market_state"],
        mapping={"market_state": "market_state", "exchange": "exchange"},
    ),
    _pulse_definition(
        name="day_high_low",
        description="Intraday high and low from Yahoo Finance.",
        tags=["finance", "quote", "range"],
        properties={
            "symbol": {"type": "string"},
            "day_high": {"type": "number"},
            "day_low": {"type": "number"},
            "currency": {"type": "string"},
            "source": {"type": "string"},
        },
        required=["symbol", "day_high", "day_low"],
        mapping={"day_high": "day_high", "day_low": "day_low", "currency": "currency"},
    ),
    _pulse_definition(
        name="trade_volume",
        description="Live and average volume snapshot from Yahoo Finance.",
        tags=["finance", "quote", "volume", "liquidity"],
        properties={
            "symbol": {"type": "string"},
            "volume": {"type": "number"},
            "average_daily_volume_10d": {"type": "number"},
            "average_daily_volume_30d": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["symbol", "volume"],
        mapping={
            "volume": "volume",
            "average_daily_volume_10d": "average_daily_volume_10d",
            "average_daily_volume_30d": "average_daily_volume_30d",
        },
    ),
    _pulse_definition(
        name="bid_ask",
        description="Bid, ask, and spread snapshot for trading and execution views.",
        tags=["finance", "quote", "market-microstructure"],
        properties={
            "symbol": {"type": "string"},
            "bid": {"type": "number"},
            "ask": {"type": "number"},
            "bid_size": {"type": "number"},
            "ask_size": {"type": "number"},
            "currency": {"type": "string"},
            "source": {"type": "string"},
        },
        required=["symbol"],
        mapping={
            "bid": "bid",
            "ask": "ask",
            "bid_size": "bid_size",
            "ask_size": "ask_size",
            "currency": "currency",
        },
    ),
    _pulse_definition(
        name="market_cap",
        description="Company market capitalization and share count indicators.",
        tags=["finance", "valuation", "size"],
        properties={
            "symbol": {"type": "string"},
            "market_cap": {"type": "number"},
            "shares_outstanding": {"type": "number"},
            "float_shares": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["symbol", "market_cap"],
        mapping={
            "market_cap": "market_cap",
            "shares_outstanding": "shares_outstanding",
            "float_shares": "float_shares",
        },
    ),
    _pulse_definition(
        name="valuation_multiples",
        description="Common public market valuation multiples for equity analysis.",
        tags=["finance", "valuation", "fundamentals"],
        properties={
            "symbol": {"type": "string"},
            "trailing_pe": {"type": "number"},
            "forward_pe": {"type": "number"},
            "peg_ratio": {"type": "number"},
            "price_to_sales": {"type": "number"},
            "price_to_book": {"type": "number"},
            "enterprise_to_revenue": {"type": "number"},
            "enterprise_to_ebitda": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["symbol"],
        mapping={
            "trailing_pe": "trailing_pe",
            "forward_pe": "forward_pe",
            "peg_ratio": "peg_ratio",
            "price_to_sales": "price_to_sales",
            "price_to_book": "price_to_book",
            "enterprise_to_revenue": "enterprise_to_revenue",
            "enterprise_to_ebitda": "enterprise_to_ebitda",
        },
    ),
    _pulse_definition(
        name="profitability_metrics",
        description="Margins and return metrics for financial quality analysis.",
        tags=["finance", "fundamentals", "profitability"],
        properties={
            "symbol": {"type": "string"},
            "gross_margin": {"type": "number"},
            "operating_margin": {"type": "number"},
            "ebitda_margin": {"type": "number"},
            "profit_margin": {"type": "number"},
            "return_on_assets": {"type": "number"},
            "return_on_equity": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["symbol"],
        mapping={
            "gross_margin": "gross_margin",
            "operating_margin": "operating_margin",
            "ebitda_margin": "ebitda_margin",
            "profit_margin": "profit_margin",
            "return_on_assets": "return_on_assets",
            "return_on_equity": "return_on_equity",
        },
    ),
    _pulse_definition(
        name="balance_sheet_strength",
        description="Liquidity and leverage indicators from Yahoo Finance fundamentals.",
        tags=["finance", "fundamentals", "balance-sheet", "risk"],
        properties={
            "symbol": {"type": "string"},
            "current_ratio": {"type": "number"},
            "quick_ratio": {"type": "number"},
            "debt_to_equity": {"type": "number"},
            "total_cash": {"type": "number"},
            "total_debt": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["symbol"],
        mapping={
            "current_ratio": "current_ratio",
            "quick_ratio": "quick_ratio",
            "debt_to_equity": "debt_to_equity",
            "total_cash": "total_cash",
            "total_debt": "total_debt",
        },
    ),
    _pulse_definition(
        name="cashflow_snapshot",
        description="Cash flow and free cash flow metrics for funding analysis.",
        tags=["finance", "fundamentals", "cash-flow"],
        properties={
            "symbol": {"type": "string"},
            "operating_cashflow": {"type": "number"},
            "free_cashflow": {"type": "number"},
            "ebitda": {"type": "number"},
            "enterprise_value": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["symbol"],
        mapping={
            "operating_cashflow": "operating_cashflow",
            "free_cashflow": "free_cashflow",
            "ebitda": "ebitda",
            "enterprise_value": "enterprise_value",
        },
    ),
    _pulse_definition(
        name="revenue_and_growth",
        description="Revenue scale and growth expectations for top-line analysis.",
        tags=["finance", "fundamentals", "growth"],
        properties={
            "symbol": {"type": "string"},
            "total_revenue": {"type": "number"},
            "revenue_growth": {"type": "number"},
            "earnings_growth": {"type": "number"},
            "earnings_quarterly_growth": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["symbol"],
        mapping={
            "total_revenue": "total_revenue",
            "revenue_growth": "revenue_growth",
            "earnings_growth": "earnings_growth",
            "earnings_quarterly_growth": "earnings_quarterly_growth",
        },
    ),
    *SHARED_INCOME_STATEMENT_PULSES,
    _pulse_definition(
        name="eps_metrics",
        description="EPS, analyst expectations, and earnings surprise inputs.",
        tags=["finance", "earnings", "fundamentals"],
        properties={
            "symbol": {"type": "string"},
            "trailing_eps": {"type": "number"},
            "forward_eps": {"type": "number"},
            "target_mean_price": {"type": "number"},
            "target_median_price": {"type": "number"},
            "recommendation_mean": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["symbol"],
        mapping={
            "trailing_eps": "trailing_eps",
            "forward_eps": "forward_eps",
            "target_mean_price": "target_mean_price",
            "target_median_price": "target_median_price",
            "recommendation_mean": "recommendation_mean",
        },
    ),
    _pulse_definition(
        name="dividend_profile",
        description="Dividend and payout metrics for income-oriented workflows.",
        tags=["finance", "dividend", "income"],
        properties={
            "symbol": {"type": "string"},
            "dividend_rate": {"type": "number"},
            "dividend_yield": {"type": "number"},
            "payout_ratio": {"type": "number"},
            "five_year_avg_dividend_yield": {"type": "number"},
            "ex_dividend_date": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["symbol"],
        mapping={
            "dividend_rate": "dividend_rate",
            "dividend_yield": "dividend_yield",
            "payout_ratio": "payout_ratio",
            "five_year_avg_dividend_yield": "five_year_avg_dividend_yield",
            "ex_dividend_date": "ex_dividend_date",
        },
    ),
    _pulse_definition(
        name="fifty_two_week_range",
        description="52-week trading range and relative positioning.",
        tags=["finance", "technical", "range"],
        properties={
            "symbol": {"type": "string"},
            "fifty_two_week_low": {"type": "number"},
            "fifty_two_week_high": {"type": "number"},
            "fifty_day_average": {"type": "number"},
            "two_hundred_day_average": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["symbol"],
        mapping={
            "fifty_two_week_low": "fifty_two_week_low",
            "fifty_two_week_high": "fifty_two_week_high",
            "fifty_day_average": "fifty_day_average",
            "two_hundred_day_average": "two_hundred_day_average",
        },
    ),
    _pulse_definition(
        name="beta_and_volatility",
        description="Systematic risk and implied movement indicators.",
        tags=["finance", "risk", "volatility"],
        properties={
            "symbol": {"type": "string"},
            "beta": {"type": "number"},
            "52_week_change": {"type": "number"},
            "sandp_52_week_change": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["symbol"],
        mapping={
            "beta": "beta",
            "52_week_change": "52_week_change",
            "sandp_52_week_change": "sandp_52_week_change",
        },
    ),
    _pulse_definition(
        name="analyst_sentiment",
        description="Analyst recommendation counts and consensus summary.",
        tags=["finance", "analyst", "sentiment"],
        properties={
            "symbol": {"type": "string"},
            "recommendation_key": {"type": "string"},
            "number_of_analyst_opinions": {"type": "number"},
            "target_high_price": {"type": "number"},
            "target_low_price": {"type": "number"},
            "target_mean_price": {"type": "number"},
            "source": {"type": "string"},
        },
        required=["symbol"],
        mapping={
            "recommendation_key": "recommendation_key",
            "number_of_analyst_opinions": "number_of_analyst_opinions",
            "target_high_price": "target_high_price",
            "target_low_price": "target_low_price",
            "target_mean_price": "target_mean_price",
        },
    ),
    _pulse_definition(
        name="company_profile",
        description="Operational identity data useful for screening and reporting.",
        tags=["finance", "profile", "company"],
        properties={
            "symbol": {"type": "string"},
            "short_name": {"type": "string"},
            "long_name": {"type": "string"},
            "sector": {"type": "string"},
            "industry": {"type": "string"},
            "country": {"type": "string"},
            "website": {"type": "string"},
            "exchange": {"type": "string"},
            "currency": {"type": "string"},
            "source": {"type": "string"},
        },
        required=["symbol"],
        mapping={
            "short_name": "short_name",
            "long_name": "long_name",
            "sector": "sector",
            "industry": "industry",
            "country": "country",
            "website": "website",
            "exchange": "exchange",
            "currency": "currency",
        },
    ),
]


def _coerce_mapping(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    try:
        return dict(value)
    except Exception:
        return {}


def _pick_first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


class YFinancePulser(StandbyAgent):
    def __init__(
        self,
        config: Optional[ConfigInput] = None,
        *,
        config_path: Optional[ConfigInput] = None,
        name: str = "YFinancePulser",
        host: str = "127.0.0.1",
        port: int = 8020,
        plaza_url: Optional[str] = None,
        agent_card: Optional[Dict[str, Any]] = None,
        pool: Any = None,
        supported_pulses: Optional[list[Dict[str, Any]]] = None,
        auto_register: bool = True,
    ):
        config_data = _read_config(config) if config is not None else {}
        resolved_config_path = config_path
        if resolved_config_path is None and isinstance(config, (str, Path)):
            resolved_config_path = config

        self.config_path = Path(resolved_config_path).resolve() if resolved_config_path else None
        self.raw_config = dict(config_data)
        self.config: Dict[str, Any] = {}
        self.supported_pulses: list[Dict[str, Any]] = []
        self.pulse_address: Optional[str] = None
        self.input_schema: Dict[str, Any] = {}
        self.mapping: Dict[str, Any] = {}
        self.output_schema: Dict[str, Any] = {}
        self.last_fetch_debug: Dict[str, Any] = {}

        pulser_config = config_data.get("pulser", config_data)
        resolved_name = pulser_config.get("name") or config_data.get("name") or name
        resolved_description = (
            pulser_config.get("description")
            or config_data.get("description")
            or "Provides market pulse data from the yfinance Python module."
        )
        resolved_tags = list(
            pulser_config.get("tags")
            or config_data.get("tags")
            or ["finance", "yahoo", "market-data", "stocks"]
        )

        card = dict(agent_card or pulser_config.get("agent_card") or {})
        card.setdefault("name", resolved_name)
        card.setdefault("role", "pulser")
        card.setdefault("pit_type", "Pulser")
        card.setdefault("description", resolved_description)
        card.setdefault("tags", resolved_tags)
        card.setdefault("meta", {})

        super().__init__(
            name=str(resolved_name),
            host=host,
            port=port,
            plaza_url=plaza_url,
            agent_card=card,
            pool=pool,
        )

        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        self.templates = Jinja2Templates(directory=template_dir)

        self.apply_pulser_config(config_data or pulser_config, supported_pulses=supported_pulses, agent_card_overrides=card)
        self.add_practice(GetPulseDataPractice())
        self._setup_ui_routes()

        if self.plaza_url and auto_register:
            self.register()

        logger.info("[%s] Standing by with %s supported pulses.", self.name, len(self.supported_pulses))

    @classmethod
    def from_config(cls, config: ConfigInput, **kwargs: Any) -> "YFinancePulser":
        return cls(config=config, **kwargs)

    def _setup_ui_routes(self) -> None:
        @self.app.get("/")
        async def yfinance_pulser_ui(request: Request):
            return self.templates.TemplateResponse(
                request=request,
                name="attas/pulsers/templates/yfinance_pulser_editor.html",
                context={
                    "agent_name": self.agent_card.get("name", self.name),
                    "config_path": str(self.config_path) if self.config_path else "",
                },
            )

        @self.app.get("/api/config")
        async def get_yfinance_pulser_config():
            config = await run_in_threadpool(self._load_config_document)
            return {
                "status": "success",
                "config": config,
                "config_path": str(self.config_path) if self.config_path else None,
            }

        @self.app.get("/api/plaza/pulses")
        async def get_plaza_pulses(search: str = ""):
            rows = await run_in_threadpool(self._search_plaza_directory, pit_type="Pulse", name=search.strip() or None)
            pulses = []
            for row in rows or []:
                card = row.get("card") or {}
                meta = card.get("meta") or {}
                pit_address = PitAddress.from_value(card.get("pit_address"))
                pulses.append(
                    {
                        "pit_address": pit_address.to_ref(reference_plaza=self.plaza_url),
                        "pit_id": pit_address.pit_id,
                        "name": card.get("name") or row.get("name"),
                        "description": card.get("description") or row.get("description") or meta.get("description", ""),
                        "tags": list(card.get("tags") or meta.get("tags") or []),
                        "output_schema": meta.get("output_schema") if isinstance(meta.get("output_schema"), dict) else {},
                    }
                )
            return {"status": "success", "pulses": pulses}

        @self.app.post("/api/config")
        async def save_yfinance_pulser_config(request: Request):
            payload = await request.json()
            config = payload.get("config") if isinstance(payload, dict) and isinstance(payload.get("config"), dict) else payload
            if not isinstance(config, dict):
                raise HTTPException(status_code=400, detail="Config payload must be a JSON object.")
            saved = await run_in_threadpool(self._save_config_document, config)
            return {
                "status": "success",
                "config": saved,
                "config_path": str(self.config_path) if self.config_path else None,
            }

        @self.app.post("/api/test-pulse")
        async def test_yfinance_pulser_pulse(request: Request):
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Test payload must be a JSON object.")

            pulse_name = payload.get("pulse_name")
            params = payload.get("params") or {}
            config = payload.get("config")
            include_debug = bool(payload.get("debug"))
            if not pulse_name:
                raise HTTPException(status_code=400, detail="pulse_name is required.")
            if not isinstance(params, dict):
                raise HTTPException(status_code=400, detail="params must be a JSON object.")
            if config is not None and not isinstance(config, dict):
                raise HTTPException(status_code=400, detail="config must be a JSON object when provided.")

            def _run_test_sync():
                runtime_config = config if isinstance(config, dict) else self._load_config_document()
                runner = self.__class__(config=runtime_config, auto_register=False)
                pulse_definition = runner.resolve_pulse_definition(pulse_name=str(pulse_name))
                raw_payload = runner.fetch_pulse_payload(str(pulse_name), params, pulse_definition) or {}
                mapping_rules = pulse_definition.get("mapping") or runner.mapping
                if isinstance(raw_payload, dict) and raw_payload.get("error"):
                    result = raw_payload
                elif mapping_rules:
                    result = runner.transform(
                        raw_payload,
                        pulse_name=str(pulse_name),
                        pulse_address=pulse_definition.get("pulse_address"),
                        output_schema=pulse_definition.get("output_schema"),
                        mapping=mapping_rules,
                    )
                else:
                    result = raw_payload
                return runner, pulse_definition, raw_payload, mapping_rules, result

            try:
                runner, pulse_definition, raw_payload, mapping_rules, result = await run_in_threadpool(_run_test_sync)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            response = {
                "status": "success",
                "pulse_name": str(pulse_name),
                "params": params,
                "result": result,
            }
            if include_debug:
                response["debug"] = {
                    "pulse_definition": pulse_definition,
                    "fetch": dict(runner.last_fetch_debug or {}),
                    "mapping": mapping_rules,
                    "raw_payload": raw_payload,
                    "result": result,
                }
            return response

    def _load_config_document(self) -> Dict[str, Any]:
        if self.config_path and self.config_path.exists():
            with self.config_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            self.raw_config = dict(loaded)
            return self._build_editor_config_document(loaded)
        return self._build_editor_config_document(self.raw_config or self._synthesize_runtime_config())

    def _save_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        if not self.config_path:
            raise HTTPException(status_code=400, detail="This YFinancePulser was not started from a config file.")

        normalized = self._normalize_config_document(config)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(normalized, indent=4), encoding="utf-8")

        self.apply_pulser_config(normalized)
        return self._build_editor_config_document(normalized)

    def _normalize_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        document = dict(config or {})
        document.setdefault("name", self.agent_card.get("name", self.name))
        document.setdefault("type", "attas.pulsers.yfinance_pulser.YFinancePulser")
        document.setdefault("host", self.host)
        document.setdefault("port", self.port)
        if self.plaza_url and "plaza_url" not in document:
            document["plaza_url"] = self.plaza_url
        document.setdefault("role", "pulser")
        document.setdefault("description", self.agent_card.get("description", ""))
        document["tags"] = list(document.get("tags") or [])
        document["supported_pulses"] = [
            self._normalize_config_pulse(pulse)
            for pulse in (document.get("supported_pulses") or self.supported_pulses or [])
            if isinstance(pulse, dict)
        ]
        if "pools" in self.raw_config and "pools" not in document:
            document["pools"] = self.raw_config["pools"]
        if "practices" in self.raw_config and "practices" not in document:
            document["practices"] = self.raw_config["practices"]
        return document

    def _build_editor_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        document = self._normalize_config_document(config)
        if self.supported_pulses:
            document["supported_pulses"] = [dict(pulse) for pulse in self.supported_pulses]
        return document

    @staticmethod
    def _normalize_config_pulse(pulse: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(pulse)
        pulse_address = PitAddress.from_value(normalized.get("pulse_address"))
        if pulse_address.pit_id:
            normalized["pulse_address"] = pulse_address.to_ref()
            normalized.pop("output_schema", None)
        return normalized

    def _synthesize_runtime_config(self) -> Dict[str, Any]:
        return {
            "name": self.agent_card.get("name", self.name),
            "type": "attas.pulsers.yfinance_pulser.YFinancePulser",
            "host": self.host,
            "port": self.port,
            "plaza_url": self.plaza_url,
            "role": self.agent_card.get("role", "pulser"),
            "description": self.agent_card.get("description", ""),
            "tags": list(self.agent_card.get("tags") or []),
            "supported_pulses": [dict(pulse) for pulse in self.supported_pulses],
            "pools": list(self.raw_config.get("pools") or []),
            "practices": list(self.raw_config.get("practices") or []),
        }

    def _build_supported_pulses(
        self,
        *,
        config: Dict[str, Any],
        supported_pulses: Optional[list[Dict[str, Any]]],
    ) -> list[Dict[str, Any]]:
        raw_pulses = supported_pulses
        if raw_pulses is None:
            raw_pulses = config.get("supported_pulses")
        if raw_pulses is None:
            raw_pulses = DEFAULT_SUPPORTED_PULSES
        normalized: list[Dict[str, Any]] = []
        for pulse in raw_pulses:
            if isinstance(pulse, Mapping):
                normalized.append(self._normalize_pulse_definition(pulse))
        if not normalized:
            raise ValueError("YFinancePulser requires at least one configured pulse.")
        return normalized

    def _normalize_pulse_definition(self, pulse: Mapping[str, Any]) -> Dict[str, Any]:
        normalized = dict(pulse)
        normalized.setdefault("name", "default_pulse")
        pulse_address = normalized.get("pulse_address")
        if pulse_address:
            normalized["pulse_address"] = self._compact_pit_ref(pulse_address)
        normalized = normalize_runtime_pulse_entry(
            normalized,
            default_name=str(normalized.get("name") or "default_pulse"),
            default_description=str(normalized.get("description") or ""),
            default_pulse_address=normalized.get("pulse_address"),
        )
        normalized["input_schema"] = dict(normalized.get("input_schema") or {})
        normalized["mapping"] = dict(normalized.get("mapping") or {})
        normalized["output_schema"] = dict(normalized.get("output_schema") or {})
        normalized["tags"] = list(normalized.get("tags") or [])
        normalized["cost"] = normalized.get("cost", 0)
        return normalized

    def _compact_pit_ref(self, value: Any) -> str:
        pit_address = PitAddress.from_value(value)
        if pit_address.pit_id:
            return pit_address.to_ref(reference_plaza=self.plaza_url)
        return str(value or "")

    @staticmethod
    def _same_pit_ref(left: Any, right: Any) -> bool:
        left_address = PitAddress.from_value(left)
        right_address = PitAddress.from_value(right)
        if left_address.pit_id and right_address.pit_id:
            return left_address.pit_id == right_address.pit_id
        return str(left or "").strip() == str(right or "").strip()

    def apply_pulser_config(
        self,
        config_data: Dict[str, Any],
        *,
        supported_pulses: Optional[list[Dict[str, Any]]] = None,
        agent_card_overrides: Optional[Dict[str, Any]] = None,
    ) -> None:
        raw_config = dict(config_data or {})
        pulser_config = raw_config.get("pulser", raw_config)
        self.raw_config = raw_config
        self.config = dict(pulser_config)
        self.supported_pulses = self._build_supported_pulses(config=self.config, supported_pulses=supported_pulses)

        primary_pulse = self.supported_pulses[0]
        self.pulse_address = primary_pulse.get("pulse_address")
        self.input_schema = dict(primary_pulse.get("input_schema") or {})
        self.mapping = dict(primary_pulse.get("mapping") or {})
        self.output_schema = dict(primary_pulse.get("output_schema") or {})

        card = dict(self.agent_card or {})
        if agent_card_overrides:
            card.update(agent_card_overrides)
        card["name"] = str(raw_config.get("name") or self.config.get("name") or card.get("name") or self.name)
        card["role"] = raw_config.get("role") or self.config.get("role") or card.get("role") or "pulser"
        card["pit_type"] = "Pulser"
        card["description"] = (
            self.config.get("description")
            or raw_config.get("description")
            or card.get("description")
            or "Provides yfinance-backed pulse data."
        )
        card["tags"] = list(raw_config.get("tags") or self.config.get("tags") or card.get("tags") or ["finance", "yahoo", "market-data"])
        card["address"] = f"http://{self.host}:{self.port}"

        meta = dict(card.get("meta") or {})
        meta["pulse_address"] = self.pulse_address
        meta["input_schema"] = self.input_schema
        meta["supported_pulses"] = [dict(pulse) for pulse in self.supported_pulses]
        card["meta"] = meta

        self.name = card["name"]
        self.agent_card = card
        self.app.title = self.name
        self._refresh_pit_address()
        self._refresh_get_pulse_practice_metadata()

    def _refresh_get_pulse_practice_metadata(self) -> None:
        practice = next((entry for entry in self.practices if entry.id == "get_pulse_data"), None)
        if practice is None:
            return
        practice.bind(self)
        for practice_entry in self._resolve_callable_practice_entries(practice):
            self._upsert_practice_metadata_in_card(practice_entry)

    def build_register_payload(
        self,
        plaza_url: str,
        card: Optional[Dict[str, Any]] = None,
        address: Optional[str] = None,
        expires_in: int = 3600,
        pit_type: Optional[str] = None,
        pit_id: Optional[str] = None,
        api_key: Optional[str] = None,
        accepts_inbound_from_plaza: Optional[bool] = None,
    ) -> Dict[str, Any]:
        payload = super().build_register_payload(
            plaza_url=plaza_url,
            card=card,
            address=address,
            expires_in=expires_in,
            pit_type=pit_type or "Pulser",
            pit_id=pit_id,
            api_key=api_key,
            accepts_inbound_from_plaza=accepts_inbound_from_plaza,
        )
        payload["pulse_pulser_pairs"] = [
            {
                "pulse_id": pulse.get("pulse_id"),
                "pulse_name": pulse.get("pulse_name") or pulse.get("name"),
                "pulse_address": pulse.get("pulse_address"),
                "pulse_definition": pulse.get("pulse_definition"),
                "input_schema": pulse.get("input_schema"),
                **(
                    {
                        "is_complete": pulse.get("is_complete"),
                        "completion_status": pulse.get("completion_status"),
                        "completion_errors": pulse.get("completion_errors"),
                        "status": pulse.get("completion_status") or pulse.get("status"),
                    }
                    if any(key in pulse for key in ("is_complete", "completion_status", "completion_errors", "status"))
                    else {}
                ),
            }
            for pulse in self.supported_pulses
            if isinstance(pulse, dict) and (pulse.get("pulse_name") or pulse.get("name"))
        ]
        return payload

    def resolve_pulse_definition(
        self,
        pulse_name: Optional[str] = None,
        pulse_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        if pulse_name:
            for pulse in self.supported_pulses:
                if pulse.get("name") == pulse_name or pulse.get("pulse_name") == pulse_name:
                    return pulse
        if pulse_address:
            for pulse in self.supported_pulses:
                if self._same_pit_ref(pulse.get("pulse_address"), pulse_address):
                    return pulse
        return self.supported_pulses[0]

    def transform(
        self,
        input_data: Dict[str, Any],
        pulse_name: Optional[str] = None,
        pulse_address: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        mapping: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        pulse_definition = self.resolve_pulse_definition(pulse_name=pulse_name, pulse_address=pulse_address)
        schema = output_schema or pulse_definition.get("output_schema") or self.output_schema or {}
        mapping_rules = mapping or pulse_definition.get("mapping") or self.mapping
        properties = schema.get("properties", {})

        output_fields = list(properties.keys()) if properties else list(mapping_rules.keys())
        transformed: Dict[str, Any] = {}
        for output_field in output_fields:
            rule = mapping_rules.get(output_field)
            if rule is None:
                continue
            value, found = self._resolve_mapping_value(rule, input_data)
            if found:
                _assign_path(transformed, output_field, value)
        return transformed

    def _resolve_mapping_value(self, rule: Any, input_data: Dict[str, Any]) -> tuple[Any, bool]:
        if isinstance(rule, str):
            value = _resolve_path(input_data, rule)
            return value, value is not None

        if isinstance(rule, Mapping):
            if "value" in rule:
                return rule["value"], True
            source = rule.get("source") or rule.get("from") or rule.get("path") or rule.get("input")
            if source:
                value = _resolve_path(input_data, str(source))
                if value is not None:
                    return value, True
            if "default" in rule:
                return rule["default"], True
        return None, False

    def get_pulse_data(
        self,
        input_data: Dict[str, Any],
        pulse_name: Optional[str] = None,
        pulse_address: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        pulse_definition = self.resolve_pulse_definition(pulse_name=pulse_name, pulse_address=pulse_address)
        active_name = pulse_name or pulse_definition.get("name")
        raw_payload = self.fetch_pulse_payload(active_name, input_data, pulse_definition) or {}
        if not isinstance(raw_payload, dict):
            raise TypeError("fetch_pulse_payload() must return a dict.")
        if raw_payload.get("error"):
            return raw_payload

        mapping_rules = pulse_definition.get("mapping") or self.mapping
        if mapping_rules:
            return self.transform(
                raw_payload,
                pulse_name=active_name,
                pulse_address=pulse_definition.get("pulse_address"),
                output_schema=output_schema or pulse_definition.get("output_schema"),
                mapping=mapping_rules,
            )
        return raw_payload

    def fetch_pulse_payload(
        self,
        pulse_name: str,
        input_data: Dict[str, Any],
        pulse_definition: Dict[str, Any],
    ) -> Dict[str, Any]:
        symbol = str((input_data or {}).get("symbol") or "").strip().upper()
        self.last_fetch_debug = {
            "pulse_name": pulse_name,
            "input_data": dict(input_data or {}),
            "provider": "yfinance",
        }
        if not symbol:
            self.last_fetch_debug["error"] = "symbol is required"
            return {"error": "symbol is required"}

        if pulse_name == "ohlc_bar_series":
            interval = str((input_data or {}).get("interval") or "").strip()
            start_date = str((input_data or {}).get("start_date") or "").strip()
            end_date = str((input_data or {}).get("end_date") or (input_data or {}).get("timestamp") or "").strip()
            if not interval:
                self.last_fetch_debug["error"] = "interval is required"
                return {"error": "interval is required", "symbol": symbol}
            if not start_date or not end_date:
                self.last_fetch_debug["error"] = "start_date and end_date are required"
                return {"error": "start_date and end_date are required", "symbol": symbol}
            try:
                snapshot = self._load_ohlc_bar_series(
                    symbol,
                    interval=interval,
                    start_date=start_date,
                    end_date=end_date,
                )
            except Exception as exc:
                logger.error("[%s] Error fetching '%s' for '%s': %s", self.name, pulse_name, symbol, exc)
                self.last_fetch_debug["error"] = str(exc)
                return {"error": str(exc), "symbol": symbol, "source": "yfinance"}
            snapshot["symbol"] = symbol
            snapshot.setdefault("source", "yfinance")
            self.last_fetch_debug["snapshot"] = dict(snapshot)
            return snapshot

        income_statement_behavior = INCOME_STATEMENT_PULSE_BEHAVIOR.get(pulse_name)
        try:
            if income_statement_behavior:
                snapshot = self._load_latest_income_statement_snapshot(
                    symbol,
                    period_type=str(income_statement_behavior["period_type"]),
                )
                required_field = str(income_statement_behavior["required_field"])
                if snapshot.get(required_field) is None:
                    message = f"{required_field} is unavailable for {symbol}"
                    self.last_fetch_debug["error"] = message
                    return {"error": message, "symbol": symbol}
                self.last_fetch_debug["statement"] = dict(snapshot)
            else:
                snapshot = self._load_ticker_snapshot(symbol)
        except Exception as exc:
            logger.error("[%s] Error fetching '%s' for '%s': %s", self.name, pulse_name, symbol, exc)
            self.last_fetch_debug["error"] = str(exc)
            return {"error": str(exc), "symbol": symbol, "source": "yfinance"}

        snapshot["symbol"] = symbol
        snapshot.setdefault("source", "yfinance")
        self.last_fetch_debug["snapshot"] = dict(snapshot)
        return snapshot

    def _load_ohlc_bar_series(
        self,
        symbol: str,
        *,
        interval: str,
        start_date: str,
        end_date: str,
    ) -> Dict[str, Any]:
        if yf is None:
            raise RuntimeError("yfinance is not installed.")

        ticker = yf.Ticker(symbol)
        start_bound, normalized_start, _ = _coerce_iso_bound(start_date)
        end_bound, normalized_end, end_has_time_component = _coerce_iso_bound(end_date)
        fetch_end = end_bound + (timedelta(seconds=1) if end_has_time_component else timedelta(days=1))
        effective_end = normalized_end if end_has_time_component else _format_history_timestamp(fetch_end - timedelta(seconds=1))
        history = ticker.history(start=start_bound, end=fetch_end, interval=interval, auto_adjust=False, actions=False)
        if history is None or getattr(history, "empty", False):
            raise ValueError(f"No OHLC bars returned for {symbol} ({interval}) between {start_date} and {end_date}")

        rows = []
        if hasattr(history, "iterrows"):
            iterator = history.iterrows()
        else:
            iterator = self._iter_history_rows(history)

        for index, row in iterator:
            timestamp = _format_history_timestamp(index)
            if not timestamp:
                continue
            if timestamp < normalized_start or timestamp > effective_end:
                continue
            rows.append(
                {
                    "timestamp": timestamp,
                    "open": float(_coerce_number(self._row_value(row, "Open")) or 0.0),
                    "high": float(_coerce_number(self._row_value(row, "High")) or 0.0),
                    "low": float(_coerce_number(self._row_value(row, "Low")) or 0.0),
                    "close": float(_coerce_number(self._row_value(row, "Close")) or 0.0),
                    "volume": float(_coerce_number(self._row_value(row, "Volume")) or 0.0),
                }
            )

        if not rows:
            raise ValueError(f"No OHLC bars returned for {symbol} ({interval}) between {start_date} and {end_date}")

        return {
            "symbol": symbol,
            "interval": interval,
            "start_date": normalized_start,
            "end_date": effective_end,
            "ohlc_series": rows,
            "source": "yfinance",
        }

    def _iter_history_rows(self, history: Any):
        index_values = list(getattr(history, "index", []))
        opens = _series_to_dict(self._history_column(history, "Open"))
        highs = _series_to_dict(self._history_column(history, "High"))
        lows = _series_to_dict(self._history_column(history, "Low"))
        closes = _series_to_dict(self._history_column(history, "Close"))
        volumes = _series_to_dict(self._history_column(history, "Volume"))
        for index in index_values:
            yield index, {
                "Open": opens.get(index),
                "High": highs.get(index),
                "Low": lows.get(index),
                "Close": closes.get(index),
                "Volume": volumes.get(index),
            }

    def _history_column(self, history: Any, name: str) -> Any:
        if isinstance(history, Mapping):
            return history.get(name)
        try:
            return history[name]
        except Exception:
            return getattr(history, name, None)

    def _row_value(self, row: Any, name: str) -> Any:
        if isinstance(row, Mapping):
            return row.get(name)
        getter = getattr(row, "get", None)
        if callable(getter):
            try:
                return getter(name)
            except Exception:
                pass
        return getattr(row, name, None)

    def _load_ticker_snapshot(self, symbol: str) -> Dict[str, Any]:
        if yf is None:
            raise RuntimeError("yfinance is not installed.")

        ticker = yf.Ticker(symbol)
        fast_info = self._get_ticker_fast_info(ticker, symbol)
        info = self._get_ticker_info(ticker, symbol)

        snapshot = {
            "symbol": symbol,
            "currency": _pick_first(fast_info.get("currency"), info.get("currency")),
            "exchange": _pick_first(fast_info.get("exchange"), info.get("exchange"), info.get("fullExchangeName")),
            "market_state": _pick_first(
                fast_info.get("marketState"),
                fast_info.get("market_state"),
                info.get("marketState"),
            ),
            "last_price": _pick_first(
                fast_info.get("lastPrice"),
                fast_info.get("last_price"),
                info.get("currentPrice"),
                info.get("regularMarketPrice"),
            ),
            "previous_close": _pick_first(
                fast_info.get("previousClose"),
                fast_info.get("previous_close"),
                info.get("previousClose"),
                info.get("regularMarketPreviousClose"),
            ),
            "open_price": _pick_first(
                fast_info.get("open"),
                info.get("open"),
                info.get("regularMarketOpen"),
            ),
            "day_high": _pick_first(
                fast_info.get("dayHigh"),
                fast_info.get("day_high"),
                info.get("dayHigh"),
                info.get("regularMarketDayHigh"),
            ),
            "day_low": _pick_first(
                fast_info.get("dayLow"),
                fast_info.get("day_low"),
                info.get("dayLow"),
                info.get("regularMarketDayLow"),
            ),
            "volume": _pick_first(
                fast_info.get("lastVolume"),
                fast_info.get("last_volume"),
                fast_info.get("volume"),
                info.get("volume"),
                info.get("regularMarketVolume"),
            ),
            "average_daily_volume_30d": _pick_first(
                fast_info.get("threeMonthAverageVolume"),
                fast_info.get("three_month_average_volume"),
                info.get("averageVolume"),
            ),
            "average_daily_volume_10d": _pick_first(
                fast_info.get("tenDayAverageVolume"),
                fast_info.get("ten_day_average_volume"),
                info.get("averageDailyVolume10Day"),
            ),
            "bid": info.get("bid"),
            "ask": info.get("ask"),
            "bid_size": info.get("bidSize"),
            "ask_size": info.get("askSize"),
            "market_cap": _pick_first(fast_info.get("marketCap"), fast_info.get("market_cap"), info.get("marketCap")),
            "shares_outstanding": info.get("sharesOutstanding"),
            "float_shares": info.get("floatShares"),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "price_to_book": info.get("priceToBook"),
            "enterprise_to_revenue": info.get("enterpriseToRevenue"),
            "enterprise_to_ebitda": info.get("enterpriseToEbitda"),
            "gross_margin": info.get("grossMargins"),
            "operating_margin": info.get("operatingMargins"),
            "ebitda_margin": info.get("ebitdaMargins"),
            "profit_margin": info.get("profitMargins"),
            "return_on_assets": info.get("returnOnAssets"),
            "return_on_equity": info.get("returnOnEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "debt_to_equity": info.get("debtToEquity"),
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
            "operating_cashflow": info.get("operatingCashflow"),
            "free_cashflow": info.get("freeCashflow"),
            "ebitda": info.get("ebitda"),
            "enterprise_value": info.get("enterpriseValue"),
            "total_revenue": info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
            "trailing_eps": info.get("trailingEps"),
            "forward_eps": info.get("forwardEps"),
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "target_mean_price": info.get("targetMeanPrice"),
            "target_median_price": info.get("targetMedianPrice"),
            "recommendation_mean": info.get("recommendationMean"),
            "recommendation_key": info.get("recommendationKey"),
            "number_of_analyst_opinions": info.get("numberOfAnalystOpinions"),
            "dividend_rate": info.get("dividendRate"),
            "dividend_yield": info.get("dividendYield"),
            "payout_ratio": info.get("payoutRatio"),
            "five_year_avg_dividend_yield": info.get("fiveYearAvgDividendYield"),
            "ex_dividend_date": info.get("exDividendDate"),
            "fifty_two_week_low": _pick_first(
                fast_info.get("yearLow"),
                fast_info.get("year_low"),
                info.get("fiftyTwoWeekLow"),
            ),
            "fifty_two_week_high": _pick_first(
                fast_info.get("yearHigh"),
                fast_info.get("year_high"),
                info.get("fiftyTwoWeekHigh"),
            ),
            "fifty_day_average": info.get("fiftyDayAverage"),
            "two_hundred_day_average": info.get("twoHundredDayAverage"),
            "beta": info.get("beta"),
            "52_week_change": info.get("52WeekChange"),
            "sandp_52_week_change": info.get("SandP52WeekChange"),
            "short_name": info.get("shortName"),
            "long_name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "country": info.get("country"),
            "website": info.get("website"),
            "source": "yfinance",
        }
        return {key: value for key, value in snapshot.items() if value is not None}

    def _get_income_statement_frame(self, ticker: Any, symbol: str, period_type: str) -> Any:
        candidate_attrs = (
            ("quarterly_income_stmt", "quarterly_financials")
            if period_type == "quarterly"
            else ("income_stmt", "financials")
        )
        for attr_name in candidate_attrs:
            try:
                frame = getattr(ticker, attr_name, None)
            except Exception as exc:
                logger.debug("[%s] Could not load %s for %s: %s", self.name, attr_name, symbol, exc)
                continue
            if frame is None or getattr(frame, "empty", False):
                continue
            if list(getattr(frame, "columns", [])):
                return frame
        return None

    def _get_statement_row_values(self, frame: Any, aliases: tuple[str, ...]) -> Dict[Any, Any]:
        normalized_rows: Dict[str, Any] = {}
        for label in list(getattr(frame, "index", [])):
            normalized_rows.setdefault(_normalize_statement_label(label), label)

        for alias in aliases:
            actual_label = normalized_rows.get(_normalize_statement_label(alias))
            if actual_label is None:
                continue
            try:
                series = frame.loc[actual_label]
            except Exception:
                continue
            values = _series_to_dict(series)
            if values:
                return values
        return {}

    def _load_latest_income_statement_snapshot(self, symbol: str, *, period_type: str) -> Dict[str, Any]:
        if yf is None:
            raise RuntimeError("yfinance is not installed.")

        ticker = yf.Ticker(symbol)
        frame = self._get_income_statement_frame(ticker, symbol, period_type)
        if frame is None:
            raise RuntimeError(f"No {period_type} income statement data available for {symbol}.")

        columns = sorted(
            list(getattr(frame, "columns", [])),
            key=lambda value: (_format_statement_period(value), str(value)),
            reverse=True,
        )
        if not columns:
            raise RuntimeError(f"No {period_type} income statement periods available for {symbol}.")

        current_column = columns[0]
        compare_column: Any = None
        if period_type == "quarterly":
            if len(columns) > 4:
                compare_column = columns[4]
        elif len(columns) > 1:
            compare_column = columns[1]

        info = self._get_ticker_info(ticker, symbol)
        revenue_row = self._get_statement_row_values(frame, INCOME_STATEMENT_ROW_ALIASES["revenue"])
        gross_profit_row = self._get_statement_row_values(frame, INCOME_STATEMENT_ROW_ALIASES["gross_profit"])
        operating_income_row = self._get_statement_row_values(frame, INCOME_STATEMENT_ROW_ALIASES["operating_income"])
        net_income_row = self._get_statement_row_values(frame, INCOME_STATEMENT_ROW_ALIASES["net_income"])
        eps_basic_row = self._get_statement_row_values(frame, INCOME_STATEMENT_ROW_ALIASES["eps_basic"])
        eps_diluted_row = self._get_statement_row_values(frame, INCOME_STATEMENT_ROW_ALIASES["eps_diluted"])

        revenue = _coerce_number(revenue_row.get(current_column))
        gross_profit = _coerce_number(gross_profit_row.get(current_column))
        operating_income = _coerce_number(operating_income_row.get(current_column))
        net_income = _coerce_number(net_income_row.get(current_column))
        eps_basic = _coerce_number(eps_basic_row.get(current_column))
        eps_diluted = _pick_first(
            _coerce_number(eps_diluted_row.get(current_column)),
            eps_basic,
        )

        revenue_compare = _coerce_number(revenue_row.get(compare_column)) if compare_column is not None else None
        gross_profit_compare = _coerce_number(gross_profit_row.get(compare_column)) if compare_column is not None else None
        operating_income_compare = _coerce_number(operating_income_row.get(compare_column)) if compare_column is not None else None
        net_income_compare = _coerce_number(net_income_row.get(compare_column)) if compare_column is not None else None
        eps_basic_compare = _coerce_number(eps_basic_row.get(compare_column)) if compare_column is not None else None
        eps_diluted_compare = _pick_first(
            _coerce_number(eps_diluted_row.get(compare_column)) if compare_column is not None else None,
            eps_basic_compare,
        )

        snapshot = {
            "symbol": symbol,
            "period_end": _format_statement_period(current_column),
            "period_type": period_type,
            "currency": _pick_first(info.get("financialCurrency"), info.get("currency")),
            "revenue": revenue,
            "revenue_year_over_year_growth_percent": _calculate_growth_percent(revenue, revenue_compare),
            "gross_profit": gross_profit,
            "gross_margin_percent": _calculate_margin_percent(gross_profit, revenue),
            "gross_profit_year_over_year_growth_percent": _calculate_growth_percent(gross_profit, gross_profit_compare),
            "operating_income": operating_income,
            "operating_margin_percent": _calculate_margin_percent(operating_income, revenue),
            "operating_income_year_over_year_growth_percent": _calculate_growth_percent(operating_income, operating_income_compare),
            "net_income": net_income,
            "net_margin_percent": _calculate_margin_percent(net_income, revenue),
            "net_income_year_over_year_growth_percent": _calculate_growth_percent(net_income, net_income_compare),
            "eps_basic": eps_basic,
            "eps_diluted": eps_diluted,
            "eps_diluted_year_over_year_growth_percent": _calculate_growth_percent(eps_diluted, eps_diluted_compare),
        }
        return {key: value for key, value in snapshot.items() if value is not None}

    def _get_ticker_fast_info(self, ticker: Any, symbol: str) -> Dict[str, Any]:
        try:
            return _coerce_mapping(getattr(ticker, "fast_info", None))
        except Exception as exc:
            logger.debug("[%s] Could not load fast_info for %s: %s", self.name, symbol, exc)
            return {}

    def _get_ticker_info(self, ticker: Any, symbol: str) -> Dict[str, Any]:
        try:
            return _coerce_mapping(getattr(ticker, "info", None))
        except Exception as exc:
            logger.debug("[%s] Could not load info for %s: %s", self.name, symbol, exc)
            return {}
