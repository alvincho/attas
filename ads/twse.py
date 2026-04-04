"""
TWSE module for `ads.twse`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace.

Core types exposed here include `TWSEMarketEODJobCap`, which carry the main behavior or
state managed by this module.
"""

from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta, timezone
from json import JSONDecodeError
from typing import Any, Callable, Dict, Iterable, List, Mapping
from urllib.parse import urlencode

import requests

from ads.jobcap import JobCap
from ads.models import JobDetail, JobResult
from ads.runtime import normalize_provider, normalize_symbol
from ads.schema import TABLE_DAILY_PRICE, daily_price_schema_dict


RequestGetter = Callable[..., Any]
SleepFn = Callable[[float], None]

FIELD_ALIASES = {
    "code": ("Security Code", "證券代號"),
    "volume": ("Trade Volume", "成交股數"),
    "transaction": ("Transaction", "成交筆數"),
    "trade_value": ("Trade Value", "成交金額"),
    "open": ("Opening Price", "開盤價"),
    "high": ("Highest Price", "最高價"),
    "low": ("Lowest Price", "最低價"),
    "close": ("Closing Price", "收盤價"),
    "direction": ("Dir(+/-)", "漲跌(+/-)"),
    "change": ("Change", "漲跌價差"),
    "bid_price": ("Last Best Bid Price", "最後揭示買價"),
    "bid_volume": ("Last Best Bid Volume", "最後揭示買量"),
    "ask_price": ("Last Best Ask Price", "最後揭示賣價"),
    "ask_volume": ("Last Best Ask Volume", "最後揭示賣量"),
    "pe_ratio": ("Price-Earning ratio", "本益比"),
}

TWSE_MIN_SUPPORTED_DATE = date(2004, 2, 11)
TWSE_DEFAULT_BOOTSTRAP_DAYS = 7
TWSE_DEFAULT_REQUEST_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://www.twse.com.tw/en/trading/historical/stock-day.html",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/135.0.0.0 Safari/537.36"
    ),
}


def _coerce_date(value: Any) -> date | None:
    """Internal helper to coerce the date."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        text = text[:10]
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


def _strip_html(value: Any) -> str:
    """Internal helper to strip the HTML."""
    return re.sub(r"<[^>]+>", "", str(value or "")).strip()


def _coerce_number(value: Any) -> float | int | None:
    """Internal helper to coerce the number."""
    text = _strip_html(value).replace(",", "").replace(" ", "")
    if text in {"", "--", "---", "----", "N/A"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _normalize_twse_symbol(value: Any) -> str:
    """Internal helper to normalize the TWSE symbol."""
    normalized = normalize_symbol(value)
    if "." in normalized:
        base, suffix = normalized.split(".", 1)
        if base and suffix in {"TW", "TWO"}:
            return base
    return normalized


def _field_value(row: Mapping[str, Any], key: str) -> Any:
    """Internal helper to return the field value."""
    for alias in FIELD_ALIASES.get(key, ()):
        if alias in row:
            return row.get(alias)
    return None


def _parse_direction(value: Any) -> str:
    """Internal helper to parse the direction."""
    text = _strip_html(value)
    if text in {"+", "-", "X"}:
        return text
    raw_text = str(value or "")
    for marker in ("+", "-", "X"):
        if marker in raw_text:
            return marker
    return text


def _signed_change(direction: str, change: Any) -> float | int | None:
    """Internal helper for signed change."""
    numeric_change = _coerce_number(change)
    if numeric_change is None:
        return None
    if direction == "-":
        return -abs(numeric_change)
    if direction == "+":
        return abs(numeric_change)
    return numeric_change


class TWSEMarketEODJobCap(JobCap):
    """Job capability implementation for TWSE market EOD workflows."""
    DEFAULT_BASE_URL = "https://www.twse.com.tw"
    DEFAULT_REPORT_PATH = "/en/exchangeReport/MI_INDEX"

    def __init__(
        self,
        name: str = "TWSE Market EOD",
        *,
        base_url: str = DEFAULT_BASE_URL,
        report_path: str = DEFAULT_REPORT_PATH,
        report_type: str = "ALLBUT0999",
        provider: str = "twse",
        dispatcher_address: str = "",
        start_date: str = "",
        bootstrap_days: int = TWSE_DEFAULT_BOOTSTRAP_DAYS,
        timeout_sec: float = 30.0,
        request_headers: Mapping[str, Any] | None = None,
        request_retry_limit: int = 2,
        retry_sleep_sec: float = 1.0,
        request_get: RequestGetter | None = None,
        today_fn: Callable[[], date] | None = None,
        sleep_fn: SleepFn | None = None,
        source: str = "",
    ):
        """Initialize the TWSE market EOD job cap."""
        super().__init__(
            name=name,
            source=source or f"{self.__class__.__module__}:{self.__class__.__name__}",
        )
        self.base_url = str(base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.report_path = "/" + str(report_path or self.DEFAULT_REPORT_PATH).lstrip("/")
        self.report_type = str(report_type or "ALLBUT0999").strip() or "ALLBUT0999"
        self.provider = normalize_provider(provider or "twse") or "twse"
        self.dispatcher_address = str(dispatcher_address or "").strip()
        self.start_date = str(start_date or "").strip()
        self.bootstrap_days = max(int(bootstrap_days or 0), 0)
        self.timeout_sec = max(float(timeout_sec or 30.0), 1.0)
        self.request_headers = self._build_request_headers(request_headers)
        self.request_retry_limit = max(int(request_retry_limit or 0), 0)
        self.retry_sleep_sec = max(float(retry_sleep_sec or 0.0), 0.0)
        self.request_get = request_get or requests.get
        self.today_fn = today_fn or (lambda: datetime.now(timezone.utc).date())
        self.sleep_fn = sleep_fn or time.sleep

    def check_environment(self) -> tuple[bool, str]:
        """Handle check environment for the TWSE market EOD job cap."""
        report_url_ready, report_url_reason = self.check_url_configured(
            f"{self.base_url}{self.report_path}",
            label="TWSE report URL",
        )
        if not report_url_ready:
            return False, report_url_reason
        if not callable(self.request_get):
            return False, "TWSE request client is not callable."
        return True, ""

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the TWSE market EOD job cap."""
        payload = job.payload if isinstance(job.payload, Mapping) else {}
        configured_end_date = _coerce_date(payload.get("end_date")) or self.today_fn()
        configured_start_date = _coerce_date(payload.get("start_date")) or _coerce_date(self.start_date)
        latest_stored_date = self._latest_stored_trade_date()
        start_date = self._resolve_market_start_date(
            latest_stored_date,
            configured_start_date,
            configured_end_date,
        )

        collected_rows: List[Dict[str, Any]] = []
        raw_requests: List[Dict[str, Any]] = []

        if start_date is not None and start_date <= configured_end_date:
            trade_days = list(_date_range(start_date, configured_end_date))
        else:
            trade_days = []

        for trade_day in trade_days:
            self._raise_if_stop_requested(job)
            request_url, stat, payload_rows, notes = self._fetch_daily_quotes(trade_day)
            returned_symbols = sorted(
                {
                    _normalize_twse_symbol(_field_value(row, "code"))
                    for row in payload_rows
                    if _normalize_twse_symbol(_field_value(row, "code"))
                }
            )
            raw_requests.append(
                {
                    "trade_date": trade_day.isoformat(),
                    "url": request_url,
                    "stat": stat,
                    "scope": "market",
                    "returned_symbols": returned_symbols,
                    "row_count": len(payload_rows),
                    "table_row_count": len(payload_rows),
                    "payload": payload_rows,
                    "notes": notes,
                }
            )
            for payload_row in payload_rows:
                collected_rows.append(
                    self._normalize_daily_price_row(
                        symbol=_field_value(payload_row, "code"),
                        trade_day=trade_day,
                        payload_row=payload_row,
                        request_url=request_url,
                    )
                )

        raw_payload = {
            "provider": self.provider,
            "base_url": self.base_url,
            "report_path": self.report_path,
            "report_type": self.report_type,
            "scope": "market",
            "start_date": start_date.isoformat() if start_date else "",
            "end_date": configured_end_date.isoformat(),
            "latest_stored_trade_date": latest_stored_date.isoformat() if latest_stored_date else "",
            "requests": raw_requests,
        }
        result_summary = {
            "provider": self.provider,
            "scope": "market",
            "rows": len(collected_rows),
            "requests": len(raw_requests),
            "dates_requested": len(trade_days),
            "start_date": start_date.isoformat() if start_date else "",
            "latest_stored_trade_date": latest_stored_date.isoformat() if latest_stored_date else "",
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

    def _raise_if_stop_requested(self, job: JobDetail) -> None:
        """Internal helper for raise if stop requested."""
        worker = getattr(self, "worker", None)
        raise_if_stop_requested = getattr(worker, "raise_if_stop_requested", None)
        if callable(raise_if_stop_requested):
            raise_if_stop_requested(job)

    def _resolve_dispatcher_address(self) -> str:
        """Internal helper to resolve the dispatcher address."""
        worker = getattr(self, "worker", None)
        return self.dispatcher_address or str(getattr(worker, "dispatcher_address", "") or "").strip()

    def _latest_stored_trade_date(self) -> date | None:
        """Internal helper to return the latest stored trade date."""
        filter_payload = {"provider": self.provider}
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

    def _resolve_market_start_date(
        self,
        latest_stored_date: date | None,
        configured_start_date: date | None,
        configured_end_date: date,
    ) -> date:
        """Internal helper to resolve the market start date."""
        if latest_stored_date is not None:
            resolved = latest_stored_date
        elif configured_start_date is not None:
            resolved = configured_start_date
        else:
            resolved = configured_end_date - timedelta(days=self.bootstrap_days)
        return max(resolved, TWSE_MIN_SUPPORTED_DATE)

    def _fetch_daily_quotes(self, trade_day: date) -> tuple[str, str, List[Dict[str, Any]], List[str]]:
        """Internal helper to fetch the daily quotes."""
        url = f"{self.base_url}{self.report_path}"
        params = {
            "response": "json",
            "date": trade_day.strftime("%Y%m%d"),
            "type": self.report_type,
        }
        for attempt in range(self.request_retry_limit + 1):
            try:
                response = self.request_get(
                    url,
                    params=params,
                    timeout=self.timeout_sec,
                    headers=dict(self.request_headers),
                )
            except Exception as exc:
                if attempt < self.request_retry_limit:
                    self._sleep_before_retry()
                    continue
                raise RuntimeError(f"TWSE request failed for {trade_day.isoformat()}: {exc}") from exc

            request_url = str(getattr(response, "url", "") or self._build_request_url(url, params))
            status_code = int(getattr(response, "status_code", 200) or 200)
            if status_code >= 400:
                if attempt < self.request_retry_limit and status_code >= 500:
                    self._sleep_before_retry()
                    continue
                raise ValueError(f"TWSE request failed for {trade_day.isoformat()} with status {status_code}.")

            try:
                payload = response.json() if hasattr(response, "json") else {}
            except JSONDecodeError as exc:
                if attempt < self.request_retry_limit:
                    self._sleep_before_retry()
                    continue
                raise RuntimeError(
                    f"TWSE response was not valid JSON for {trade_day.isoformat()}: "
                    f"{self._response_text_snippet(response)}"
                ) from exc
            if not isinstance(payload, Mapping):
                if attempt < self.request_retry_limit:
                    self._sleep_before_retry()
                    continue
                raise ValueError(
                    f"Unexpected TWSE payload for {trade_day.isoformat()}: {type(payload).__name__}"
                )

            stat = str(payload.get("stat") or "").strip()
            if self._is_no_data_stat(stat):
                return request_url, stat or "No Data!", [], []
            if stat and stat.upper() != "OK":
                if self._is_retryable_stat(stat, trade_day):
                    if attempt < self.request_retry_limit:
                        self._sleep_before_retry()
                        continue
                    raise RuntimeError(
                        f"TWSE request returned a retryable response for {trade_day.isoformat()}: {stat}"
                    )
                raise ValueError(f"TWSE request failed for {trade_day.isoformat()}: {stat}")

            table = self._find_daily_quotes_table(payload.get("tables"))
            if table is None:
                if attempt < self.request_retry_limit:
                    self._sleep_before_retry()
                    continue
                raise ValueError(f"TWSE payload for {trade_day.isoformat()} is missing the daily quotes table.")

            fields = [str(field or "").strip() for field in table.get("fields") or []]
            rows: List[Dict[str, Any]] = []
            for raw_row in table.get("data") or []:
                if not isinstance(raw_row, list):
                    continue
                row = {
                    field_name: raw_row[index]
                    for index, field_name in enumerate(fields[: len(raw_row)])
                    if field_name
                }
                if row:
                    rows.append(row)
            notes = [str(note) for note in table.get("notes") or [] if str(note or "").strip()]
            return request_url, stat or "OK", rows, notes

        raise RuntimeError(f"TWSE request failed for {trade_day.isoformat()} after retries.")

    def _find_daily_quotes_table(self, tables: Any) -> Mapping[str, Any] | None:
        """Internal helper to find the daily quotes table."""
        if not isinstance(tables, list):
            return None
        required_keys = ("code", "open", "high", "low", "close", "volume")
        for table in tables:
            if not isinstance(table, Mapping):
                continue
            fields = [str(field or "").strip() for field in table.get("fields") or []]
            if all(any(alias in fields for alias in FIELD_ALIASES[key]) for key in required_keys):
                return table
        return None

    @staticmethod
    def _is_no_data_stat(stat: str) -> bool:
        """Return whether the value is a no data stat."""
        normalized = stat.strip().lower()
        return normalized == "no data!" or "沒有符合條件的資料" in stat

    @staticmethod
    def _build_request_headers(headers: Mapping[str, Any] | None) -> Dict[str, str]:
        """Internal helper to build the request headers."""
        merged = dict(TWSE_DEFAULT_REQUEST_HEADERS)
        if isinstance(headers, Mapping):
            for key, value in headers.items():
                normalized_key = str(key or "").strip()
                normalized_value = str(value or "").strip()
                if normalized_key and normalized_value:
                    merged[normalized_key] = normalized_value
        return merged

    @staticmethod
    def _is_retryable_stat(stat: str, trade_day: date) -> bool:
        """Return whether the value is a retryable stat."""
        normalized = stat.strip().lower()
        if "please retry" in normalized:
            return True
        if "search date less than 2004/02/11" in normalized and trade_day >= TWSE_MIN_SUPPORTED_DATE:
            return True
        return False

    def _sleep_before_retry(self) -> None:
        """Internal helper for sleep before retry."""
        if self.retry_sleep_sec <= 0:
            return
        self.sleep_fn(self.retry_sleep_sec)

    @staticmethod
    def _response_text_snippet(response: Any, limit: int = 160) -> str:
        """Internal helper for response text snippet."""
        text = str(getattr(response, "text", "") or "").strip()
        if not text:
            return "<empty response body>"
        collapsed = re.sub(r"\s+", " ", text)
        return collapsed[:limit]

    @staticmethod
    def _build_request_url(url: str, params: Mapping[str, Any]) -> str:
        """Internal helper to build the request URL."""
        if not params:
            return url
        return f"{url}?{urlencode(params)}"

    def _normalize_daily_price_row(
        self,
        *,
        symbol: Any,
        trade_day: date,
        payload_row: Mapping[str, Any],
        request_url: str,
    ) -> Dict[str, Any]:
        """Internal helper to normalize the daily price row."""
        close_value = _coerce_number(_field_value(payload_row, "close"))
        direction = _parse_direction(_field_value(payload_row, "direction"))
        return {
            "symbol": _normalize_twse_symbol(symbol),
            "trade_date": trade_day.isoformat(),
            "open": _coerce_number(_field_value(payload_row, "open")),
            "high": _coerce_number(_field_value(payload_row, "high")),
            "low": _coerce_number(_field_value(payload_row, "low")),
            "close": close_value,
            "adj_close": close_value,
            "volume": _coerce_number(_field_value(payload_row, "volume")),
            "provider": self.provider,
            "source_url": request_url,
            "metadata": {
                key: value
                for key, value in {
                    "exchange": "twse",
                    "currency": "TWD",
                    "transactions": _coerce_number(_field_value(payload_row, "transaction")),
                    "trade_value": _coerce_number(_field_value(payload_row, "trade_value")),
                    "change_direction": direction,
                    "change": _signed_change(direction, _field_value(payload_row, "change")),
                    "last_best_bid_price": _coerce_number(_field_value(payload_row, "bid_price")),
                    "last_best_bid_volume": _coerce_number(_field_value(payload_row, "bid_volume")),
                    "last_best_ask_price": _coerce_number(_field_value(payload_row, "ask_price")),
                    "last_best_ask_volume": _coerce_number(_field_value(payload_row, "ask_volume")),
                    "price_earnings_ratio": _coerce_number(_field_value(payload_row, "pe_ratio")),
                }.items()
                if value not in (None, "", [])
            },
        }


TWSEEODJobCap = TWSEMarketEODJobCap
