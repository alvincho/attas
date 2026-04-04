"""
IEX module for `ads.iex`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace.

Core types exposed here include `IEXEODJobCap`, which carry the main behavior or state
managed by this module.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping
from urllib.parse import urlencode

import requests

from ads.jobcap import JobCap, resolve_daily_price_start_date
from ads.models import JobDetail, JobResult
from ads.runtime import normalize_provider, normalize_string_list, normalize_symbol
from ads.schema import TABLE_DAILY_PRICE, daily_price_schema_dict


RequestGetter = Callable[..., Any]


def _coerce_date(value: Any) -> date | None:
    """Internal helper to coerce the date."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    return None


def _date_range(start_date: date, end_date: date) -> Iterable[date]:
    """Internal helper for date range."""
    cursor = start_date
    while cursor <= end_date:
        yield cursor
        cursor += timedelta(days=1)


def _coerce_number(value: Any) -> float | int | None:
    """Internal helper to coerce the number."""
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


class IEXEODJobCap(JobCap):
    """Job capability implementation for iexeod workflows."""
    DEFAULT_BASE_URL = "https://cloud.iexapis.com/stable"
    DEFAULT_TOKEN_ENV_CANDIDATES = (
        "IEX_API_TOKEN",
        "IEX_TOKEN",
        "IEX_CLOUD_API_TOKEN",
    )

    def __init__(
        self,
        name: str = "daily_price",
        *,
        token: str = "",
        token_env: str = "",
        base_url: str = DEFAULT_BASE_URL,
        provider: str = "iex",
        dispatcher_address: str = "",
        start_date: str = "",
        timeout_sec: float = 20.0,
        request_get: RequestGetter | None = None,
        today_fn: Callable[[], date] | None = None,
        source: str = "",
    ):
        """Initialize the iexeod job cap."""
        super().__init__(
            name=name,
            source=source or f"{self.__class__.__module__}:{self.__class__.__name__}",
        )
        self.token = str(token or "").strip()
        self.token_env = str(token_env or "").strip()
        self.base_url = str(base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.provider = normalize_provider(provider or "iex") or "iex"
        self.dispatcher_address = str(dispatcher_address or "").strip()
        self.start_date = str(start_date or "").strip()
        self.timeout_sec = max(float(timeout_sec or 20.0), 1.0)
        self.request_get = request_get or requests.get
        self.today_fn = today_fn or (lambda: datetime.now(timezone.utc).date())

    def check_environment(self) -> tuple[bool, str]:
        """Handle check environment for the iexeod job cap."""
        url_ready, url_reason = self.check_url_configured(self.base_url, label="IEX base URL")
        if not url_ready:
            return False, url_reason
        if not callable(self.request_get):
            return False, "IEX request client is not callable."
        token = self._resolve_token()
        if not token:
            return False, "IEX API token is not configured."
        return True, ""

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the iexeod job cap."""
        symbols = self._resolve_symbols(job)
        if not symbols:
            raise ValueError("IEXEODJobCap requires at least one symbol.")

        token = self._resolve_token()
        if not token:
            raise ValueError(
                "IEX API token is required. Set IEX_API_TOKEN, IEX_TOKEN, or IEX_CLOUD_API_TOKEN."
            )

        payload = job.payload if isinstance(job.payload, Mapping) else {}
        configured_end_date = _coerce_date(payload.get("end_date")) or self.today_fn()
        configured_start_date = _coerce_date(payload.get("start_date")) or _coerce_date(self.start_date)

        collected_rows: List[Dict[str, Any]] = []
        raw_requests: List[Dict[str, Any]] = []
        latest_stored_dates: Dict[str, str] = {}

        for symbol in symbols:
            latest_stored_date = self._latest_stored_trade_date(symbol)
            latest_stored_dates[symbol] = latest_stored_date.isoformat() if latest_stored_date else ""
            start_date = resolve_daily_price_start_date(
                latest_stored_date,
                configured_start_date,
                configured_end_date,
            )
            if start_date is None or start_date > configured_end_date:
                continue

            for trade_day in _date_range(start_date, configured_end_date):
                request_url, payload_rows = self._fetch_chart_date(symbol, trade_day, token)
                raw_requests.append(
                    {
                        "symbol": symbol,
                        "trade_date": trade_day.isoformat(),
                        "url": request_url,
                        "row_count": len(payload_rows),
                        "payload": payload_rows,
                    }
                )
                for payload_row in payload_rows:
                    normalized_row = self._normalize_daily_price_row(
                        symbol=symbol,
                        trade_day=trade_day,
                        payload_row=payload_row,
                        request_url=request_url,
                    )
                    collected_rows.append(normalized_row)

        raw_payload = {
            "provider": self.provider,
            "base_url": self.base_url,
            "latest_stored_dates": latest_stored_dates,
            "requests": raw_requests,
        }
        result_summary = {
            "provider": self.provider,
            "symbols": symbols,
            "rows": len(collected_rows),
            "requests": len(raw_requests),
            "latest_stored_dates": latest_stored_dates,
            "end_date": configured_end_date.isoformat(),
        }
        return JobResult(
            job_id=job.id,
            status="completed",
            target_table=TABLE_DAILY_PRICE,
            collected_rows=collected_rows,
            raw_payload=raw_payload,
            result_summary=result_summary,
        )

    def _resolve_symbols(self, job: JobDetail) -> List[str]:
        """Internal helper to resolve the symbols."""
        payload = job.payload if isinstance(job.payload, Mapping) else {}
        symbol_values: List[str] = []
        symbol_values.extend(normalize_string_list(job.symbols))
        if isinstance(payload, Mapping):
            if payload.get("symbol"):
                symbol_values.append(str(payload.get("symbol")))
            symbol_values.extend(normalize_string_list(payload.get("symbols")))

        symbols: List[str] = []
        for value in symbol_values:
            normalized = normalize_symbol(value)
            if normalized and normalized not in symbols:
                symbols.append(normalized)
        return symbols

    def _resolve_token(self) -> str:
        """Internal helper to resolve the token."""
        if self.token:
            return self.token

        env_candidates = [self.token_env] if self.token_env else []
        env_candidates.extend(self.DEFAULT_TOKEN_ENV_CANDIDATES)
        for env_key in env_candidates:
            token = str(os.getenv(env_key) or "").strip()
            if token:
                return token
        return ""

    def _resolve_dispatcher_address(self) -> str:
        """Internal helper to resolve the dispatcher address."""
        worker = getattr(self, "worker", None)
        return self.dispatcher_address or str(getattr(worker, "dispatcher_address", "") or "").strip()

    def _latest_stored_trade_date(self, symbol: str) -> date | None:
        """Internal helper to return the latest stored trade date."""
        filter_payload = {"symbol": normalize_symbol(symbol), "provider": self.provider}
        worker = getattr(self, "worker", None)
        dispatcher_address = self._resolve_dispatcher_address()
        rows: Any = []

        if worker is not None and dispatcher_address:
            rows = worker.UsePractice(
                "pool-get-table-data",
                {
                    "table_name": TABLE_DAILY_PRICE,
                    "id_or_where": filter_payload,
                    "table_schema": daily_price_schema_dict(),
                },
                pit_address=dispatcher_address,
            )
        elif worker is not None and getattr(worker, "pool", None) is not None:
            rows = worker.pool._GetTableData(TABLE_DAILY_PRICE, filter_payload)

        latest_date: date | None = None
        if not isinstance(rows, list):
            return None
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            trade_date = _coerce_date(row.get("trade_date"))
            if trade_date and (latest_date is None or trade_date > latest_date):
                latest_date = trade_date
        return latest_date

    def _fetch_chart_date(self, symbol: str, trade_day: date, token: str) -> tuple[str, List[Dict[str, Any]]]:
        """Internal helper to fetch the chart date."""
        url = f"{self.base_url}/stock/{normalize_symbol(symbol)}/chart/date/{trade_day.strftime('%Y%m%d')}"
        params = {"chartByDay": "true", "token": token}
        response = self.request_get(url, params=params, timeout=self.timeout_sec)
        request_url = str(getattr(response, "url", "") or self._build_request_url(url, params))
        status_code = int(getattr(response, "status_code", 200) or 200)

        if status_code == 404:
            return request_url, []
        if status_code >= 400:
            raise ValueError(
                f"IEX request failed for {symbol} on {trade_day.isoformat()} with status {status_code}."
            )

        payload = response.json() if hasattr(response, "json") else []
        if payload in (None, ""):
            return request_url, []
        if isinstance(payload, Mapping):
            if payload.get("error"):
                raise ValueError(str(payload.get("error")))
            payload = payload.get("data") if isinstance(payload.get("data"), list) else [payload]
        if not isinstance(payload, list):
            raise ValueError(
                f"Unexpected IEX payload for {symbol} on {trade_day.isoformat()}: {type(payload).__name__}"
            )
        return request_url, [dict(row) for row in payload if isinstance(row, Mapping)]

    @staticmethod
    def _build_request_url(url: str, params: Mapping[str, Any]) -> str:
        """Internal helper to build the request URL."""
        if not params:
            return url
        return f"{url}?{urlencode(params)}"

    def _normalize_daily_price_row(
        self,
        *,
        symbol: str,
        trade_day: date,
        payload_row: Mapping[str, Any],
        request_url: str,
    ) -> Dict[str, Any]:
        """Internal helper to normalize the daily price row."""
        close_value = _coerce_number(
            payload_row.get("close")
            if payload_row.get("close") is not None
            else payload_row.get("uClose")
        )
        return {
            "symbol": normalize_symbol(symbol),
            "trade_date": str(payload_row.get("date") or trade_day.isoformat()),
            "open": _coerce_number(payload_row.get("open") if payload_row.get("open") is not None else payload_row.get("uOpen")),
            "high": _coerce_number(payload_row.get("high") if payload_row.get("high") is not None else payload_row.get("uHigh")),
            "low": _coerce_number(payload_row.get("low") if payload_row.get("low") is not None else payload_row.get("uLow")),
            "close": close_value,
            "adj_close": close_value,
            "volume": _coerce_number(
                payload_row.get("volume") if payload_row.get("volume") is not None else payload_row.get("uVolume")
            ),
            "provider": self.provider,
            "source_url": request_url,
            "metadata": {
                key: value
                for key, value in {
                    "label": payload_row.get("label"),
                    "change": payload_row.get("change"),
                    "change_percent": payload_row.get("changePercent"),
                    "change_over_time": payload_row.get("changeOverTime"),
                }.items()
                if value is not None
            },
        }
