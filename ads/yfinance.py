"""
YFinance module for `ads.yfinance`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace.

Core types exposed here include `YFinanceEODJobCap` and `YFinanceUSMarketEODJobCap`,
which carry the main behavior or state managed by this module.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, List, Mapping

YFTickerMissingErrorType: tuple[type[BaseException], ...] = ()

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    yf = None
else:  # pragma: no branch - exercised when dependency is present
    try:
        from yfinance.exceptions import YFTickerMissingError as _YFTickerMissingError
    except ImportError:
        pass
    else:
        YFTickerMissingErrorType = (_YFTickerMissingError,)

from ads.jobcap import JobCap, resolve_daily_price_start_date
from ads.models import JobDetail, JobResult
from ads.runtime import normalize_provider, normalize_string_list, normalize_symbol, parse_datetime_value, utcnow_iso
from ads.schema import TABLE_DAILY_PRICE, TABLE_SECURITY_MASTER, daily_price_schema_dict, security_master_schema_dict


TickerFactory = Callable[[str], Any]


def _coerce_date(value: Any) -> date | None:
    """Internal helper to coerce the date."""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    converter = getattr(value, "to_pydatetime", None)
    if callable(converter):
        try:
            converted = converter()
        except Exception:
            converted = None
        if isinstance(converted, datetime):
            return converted.date()
        if isinstance(converted, date):
            return converted
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


def _coerce_number(value: Any) -> float | int | None:
    """Internal helper to coerce the number."""
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _coerce_bool(value: Any) -> bool:
    """Internal helper to coerce the bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value or "").strip().lower() in {"1", "true", "t", "yes", "y"}


def _row_metadata(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Internal helper to return the row metadata."""
    metadata = row.get("metadata")
    if isinstance(metadata, Mapping):
        return dict(metadata)
    legacy_meta = row.get("meta")
    if isinstance(legacy_meta, Mapping):
        return dict(legacy_meta)
    return {}


def _yfinance_eod_timestamp(row: Mapping[str, Any]) -> str:
    """Internal helper for YFinance EOD timestamp."""
    metadata = _row_metadata(row)
    yfinance_meta = metadata.get("yfinance")
    if not isinstance(yfinance_meta, Mapping):
        return ""
    return str(yfinance_meta.get("eod_at") or "").strip()


def _is_yfinance_eod_supported_symbol(symbol: Any) -> bool:
    """Return whether the value is a YFinance EOD supported symbol."""
    normalized = normalize_symbol(symbol)
    return bool(normalized) and "$" not in normalized


def _should_trigger_yfinance_cooldown(exc: BaseException) -> bool:
    """Return whether the value should trigger YFinance cooldown."""
    class_name = str(exc.__class__.__name__ or "").strip().lower()
    if "ratelimit" in class_name or "timeout" in class_name:
        return True
    message = str(exc or "").strip().lower()
    return any(
        token in message
        for token in (
            "too many requests",
            "rate limited",
            "response code=429",
            "http 429",
            "operation timed out",
            "timed out after",
            "curl: (28)",
        )
    )


class YFinanceEODJobCap(JobCap):
    """Job capability implementation for y finance EOD workflows."""
    DEFAULT_BASE_URL = "https://finance.yahoo.com"

    def __init__(
        self,
        name: str = "YFinance EOD",
        *,
        base_url: str = DEFAULT_BASE_URL,
        provider: str = "yfinance",
        dispatcher_address: str = "",
        start_date: str = "",
        interval: str = "1d",
        ticker_factory: TickerFactory | None = None,
        today_fn: Callable[[], date] | None = None,
        source: str = "",
    ):
        """Initialize the y finance EOD job cap."""
        super().__init__(
            name=name,
            source=source or f"{self.__class__.__module__}:{self.__class__.__name__}",
        )
        self.base_url = str(base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.provider = normalize_provider(provider or "yfinance") or "yfinance"
        self.dispatcher_address = str(dispatcher_address or "").strip()
        self.start_date = str(start_date or "").strip()
        self.interval = str(interval or "1d").strip() or "1d"
        self.ticker_factory = ticker_factory
        self.today_fn = today_fn or (lambda: datetime.now(timezone.utc).date())

    def check_environment(self) -> tuple[bool, str]:
        """Handle check environment for the y finance EOD job cap."""
        url_ready, url_reason = self.check_url_configured(self.base_url, label="Yahoo Finance base URL")
        if not url_ready:
            return False, url_reason
        if self.ticker_factory is not None:
            return True, ""
        return self.check_module_available("yfinance")

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the y finance EOD job cap."""
        symbols = self._resolve_symbols(job)
        if not symbols:
            raise ValueError("YFinanceEODJobCap requires at least one symbol.")

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

            history_url, payload_rows, request_note = self._fetch_history(symbol, start_date, configured_end_date)
            request_record = {
                "symbol": symbol,
                "start_date": start_date.isoformat(),
                "end_date": configured_end_date.isoformat(),
                "url": history_url,
                "row_count": len(payload_rows),
                "payload": payload_rows,
            }
            if request_note:
                request_record["notes"] = [request_note]
            raw_requests.append(request_record)
            for payload_row in payload_rows:
                collected_rows.append(
                    self._normalize_daily_price_row(
                        symbol=symbol,
                        payload_row=payload_row,
                        history_url=history_url,
                    )
                )

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

    def _fetch_history(self, symbol: str, start_date: date, end_date: date) -> tuple[str, List[Dict[str, Any]], str]:
        """Internal helper to fetch the history."""
        ticker = self._build_ticker(symbol)
        fetch_end = end_date + timedelta(days=1)
        history_url = f"{self.base_url}/quote/{normalize_symbol(symbol)}/history"
        try:
            history = self._request_history(ticker, start_date=start_date, fetch_end=fetch_end)
        except Exception as exc:
            if self._is_missing_history_error(exc):
                return history_url, [], str(exc)
            if _should_trigger_yfinance_cooldown(exc):
                worker = getattr(self, "worker", None)
                trigger_yfinance_cooldown = getattr(worker, "trigger_yfinance_cooldown", None)
                if callable(trigger_yfinance_cooldown):
                    trigger_yfinance_cooldown(
                        reason=(
                            f"YFinance rate limit for {normalize_symbol(symbol)} "
                            f"({start_date.isoformat()} to {end_date.isoformat()})"
                        )
                    )
            raise RuntimeError(
                "YFinance history request failed for "
                f"{normalize_symbol(symbol)} from {start_date.isoformat()} to {end_date.isoformat()}: {exc}"
            ) from exc
        if history is None or getattr(history, "empty", False):
            return history_url, [], ""

        rows: List[Dict[str, Any]] = []
        iterator = history.iterrows() if hasattr(history, "iterrows") else self._iter_history_rows(history)
        for index, row in iterator:
            trade_day = _coerce_date(index) or _coerce_date(self._row_value(row, "Date"))
            if trade_day is None or trade_day < start_date or trade_day > end_date:
                continue
            close_value = _coerce_number(self._row_value(row, "Close"))
            adj_close_value = _coerce_number(self._row_value(row, "Adj Close"))
            rows.append(
                {
                    "date": trade_day.isoformat(),
                    "open": _coerce_number(self._row_value(row, "Open")),
                    "high": _coerce_number(self._row_value(row, "High")),
                    "low": _coerce_number(self._row_value(row, "Low")),
                    "close": close_value,
                    "adj_close": adj_close_value if adj_close_value is not None else close_value,
                    "volume": _coerce_number(self._row_value(row, "Volume")),
                }
            )
        return history_url, rows, ""

    def _request_history(self, ticker: Any, *, start_date: date, fetch_end: date) -> Any:
        """Internal helper to request the history."""
        request_kwargs = {
            "start": start_date,
            "end": fetch_end,
            "interval": self.interval,
            "auto_adjust": False,
            "actions": False,
        }
        try:
            return ticker.history(**request_kwargs, raise_errors=True)
        except TypeError as exc:
            if not self._is_unsupported_raise_errors_argument(exc):
                raise
        return ticker.history(**request_kwargs)

    @staticmethod
    def _is_missing_history_error(exc: BaseException) -> bool:
        """Return whether the value is a missing history error."""
        return bool(YFTickerMissingErrorType) and isinstance(exc, YFTickerMissingErrorType)

    @staticmethod
    def _is_unsupported_raise_errors_argument(exc: TypeError) -> bool:
        """Return whether the value is an unsupported raise errors argument."""
        message = str(exc or "")
        return "raise_errors" in message and "unexpected keyword argument" in message

    def _build_ticker(self, symbol: str) -> Any:
        """Internal helper to build the ticker."""
        if self.ticker_factory is not None:
            return self.ticker_factory(normalize_symbol(symbol))
        if yf is None:
            raise RuntimeError("yfinance is not installed.")
        return yf.Ticker(normalize_symbol(symbol))

    def _iter_history_rows(self, history: Any) -> Iterable[tuple[Any, Any]]:
        """Internal helper to return the iter history rows."""
        index_values = list(getattr(history, "index", []))
        opens = self._series_to_dict(self._history_column(history, "Open"))
        highs = self._series_to_dict(self._history_column(history, "High"))
        lows = self._series_to_dict(self._history_column(history, "Low"))
        closes = self._series_to_dict(self._history_column(history, "Close"))
        adj_closes = self._series_to_dict(self._history_column(history, "Adj Close"))
        volumes = self._series_to_dict(self._history_column(history, "Volume"))
        for index in index_values:
            yield index, {
                "Open": opens.get(index),
                "High": highs.get(index),
                "Low": lows.get(index),
                "Close": closes.get(index),
                "Adj Close": adj_closes.get(index),
                "Volume": volumes.get(index),
            }

    @staticmethod
    def _history_column(history: Any, name: str) -> Any:
        """Internal helper to return the history column."""
        if isinstance(history, Mapping):
            return history.get(name)
        try:
            return history[name]
        except Exception:
            return getattr(history, name, None)

    @staticmethod
    def _series_to_dict(series: Any) -> Dict[Any, Any]:
        """Internal helper for series to dict."""
        if isinstance(series, Mapping):
            return dict(series)
        items = getattr(series, "items", None)
        if callable(items):
            try:
                return dict(items())
            except Exception:
                return {}
        return {}

    @staticmethod
    def _row_value(row: Any, name: str) -> Any:
        """Internal helper to return the row value."""
        if isinstance(row, Mapping):
            return row.get(name)
        getter = getattr(row, "get", None)
        if callable(getter):
            try:
                return getter(name)
            except Exception:
                pass
        return getattr(row, name, None)

    def _normalize_daily_price_row(
        self,
        *,
        symbol: str,
        payload_row: Mapping[str, Any],
        history_url: str,
    ) -> Dict[str, Any]:
        """Internal helper to normalize the daily price row."""
        close_value = _coerce_number(payload_row.get("close"))
        adj_close_value = _coerce_number(payload_row.get("adj_close"))
        return {
            "symbol": normalize_symbol(symbol),
            "trade_date": str(payload_row.get("date") or ""),
            "open": _coerce_number(payload_row.get("open")),
            "high": _coerce_number(payload_row.get("high")),
            "low": _coerce_number(payload_row.get("low")),
            "close": close_value,
            "adj_close": adj_close_value if adj_close_value is not None else close_value,
            "volume": _coerce_number(payload_row.get("volume")),
            "provider": self.provider,
            "source_url": history_url,
            "metadata": {"interval": self.interval},
        }


class YFinanceUSMarketEODJobCap(JobCap):
    """Job capability implementation for y finance US market EOD workflows."""
    DEFAULT_NAME = "YFinance US Market EOD"
    DEFAULT_CURRENCY = "USD"
    DEFAULT_YFINANCE_CAPABILITY = "YFinance EOD"

    def __init__(
        self,
        name: str = DEFAULT_NAME,
        *,
        currency: str = DEFAULT_CURRENCY,
        yfinance_capability: str = DEFAULT_YFINANCE_CAPABILITY,
        dispatcher_address: str = "",
        timestamp_fn: Callable[[], str] | None = None,
        source: str = "",
    ):
        """Initialize the y finance US market EOD job cap."""
        super().__init__(
            name=name,
            source=source or f"{self.__class__.__module__}:{self.__class__.__name__}",
        )
        self.currency = normalize_symbol(currency or self.DEFAULT_CURRENCY) or self.DEFAULT_CURRENCY
        self.yfinance_capability = (
            str(yfinance_capability or self.DEFAULT_YFINANCE_CAPABILITY).strip()
            or self.DEFAULT_YFINANCE_CAPABILITY
        )
        self.dispatcher_address = str(dispatcher_address or "").strip()
        self.timestamp_fn = timestamp_fn or utcnow_iso

    def check_environment(self) -> tuple[bool, str]:
        """Handle check environment for the y finance US market EOD job cap."""
        if not str(self.yfinance_capability or "").strip():
            return False, "downstream YFinance capability name is required."
        return True, ""

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the y finance US market EOD job cap."""
        rows = self._eligible_security_rows()
        submissions: List[Dict[str, Any]] = []

        for row in rows:
            self._raise_if_stop_requested(job)
            symbol = normalize_symbol(row.get("symbol"))
            if not symbol:
                continue

            issued_at = str(self.timestamp_fn() or "").strip() or utcnow_iso()
            updated_row = self._mark_symbol_issued(row, issued_at)
            self._persist_security_row(updated_row)
            submission = self._submit_symbol_job(job, symbol=symbol, issued_at=issued_at)
            queued_job = submission.get("job") if isinstance(submission, Mapping) else {}
            submissions.append(
                {
                    "symbol": symbol,
                    "issued_at": issued_at,
                    "queued_job_id": str(queued_job.get("id") or ""),
                    "submission": dict(submission or {}) if isinstance(submission, Mapping) else submission,
                }
            )

        raw_payload = {
            "currency": self.currency,
            "downstream_capability": self.yfinance_capability,
            "submitted_symbols": [entry["symbol"] for entry in submissions],
            "submissions": submissions,
        }
        result_summary = {
            "currency": self.currency,
            "downstream_capability": self.yfinance_capability,
            "eligible_symbols": len(rows),
            "queued_jobs": len(submissions),
            "symbols": [entry["symbol"] for entry in submissions],
        }
        return JobResult(
            job_id=job.id,
            status="completed",
            raw_payload=raw_payload,
            result_summary=result_summary,
        )

    def _resolve_dispatcher_address(self) -> str:
        """Internal helper to resolve the dispatcher address."""
        worker = getattr(self, "worker", None)
        return self.dispatcher_address or str(getattr(worker, "dispatcher_address", "") or "").strip()

    def _raise_if_stop_requested(self, job: JobDetail) -> None:
        """Internal helper for raise if stop requested."""
        worker = getattr(self, "worker", None)
        raise_if_stop_requested = getattr(worker, "raise_if_stop_requested", None)
        if callable(raise_if_stop_requested):
            raise_if_stop_requested(job)

    def _security_master_rows(self) -> List[Dict[str, Any]]:
        """Internal helper to return the security master rows."""
        worker = getattr(self, "worker", None)
        dispatcher_address = self._resolve_dispatcher_address()
        rows: Any = []

        if worker is not None and dispatcher_address:
            rows = worker.UsePractice(
                "pool-get-table-data",
                {
                    "table_name": TABLE_SECURITY_MASTER,
                    "table_schema": security_master_schema_dict(),
                },
                pit_address=dispatcher_address,
            )
        elif worker is not None and getattr(worker, "pool", None) is not None:
            rows = worker.pool._GetTableData(TABLE_SECURITY_MASTER)

        if not isinstance(rows, list):
            return []
        return [dict(row) for row in rows if isinstance(row, Mapping)]

    def _eligible_security_rows(self) -> List[Dict[str, Any]]:
        """Internal helper to return the eligible security rows."""
        eligible: List[Dict[str, Any]] = []
        seen_symbols: set[str] = set()
        for row in self._security_master_rows():
            symbol = normalize_symbol(row.get("symbol"))
            if not symbol or symbol in seen_symbols:
                continue
            if not _is_yfinance_eod_supported_symbol(symbol):
                continue
            if normalize_symbol(row.get("currency")) != self.currency:
                continue
            if not _coerce_bool(row.get("is_active")):
                continue
            normalized_row = dict(row)
            normalized_row["symbol"] = symbol
            eligible.append(normalized_row)
            seen_symbols.add(symbol)
        eligible.sort(
            key=lambda row: (
                parse_datetime_value(_yfinance_eod_timestamp(row)),
                str(row.get("symbol") or ""),
            )
        )
        return eligible

    def _mark_symbol_issued(self, row: Mapping[str, Any], issued_at: str) -> Dict[str, Any]:
        """Internal helper for mark symbol issued."""
        updated = dict(row)
        symbol = normalize_symbol(updated.get("symbol"))
        metadata = _row_metadata(updated)
        yfinance_meta = dict(metadata.get("yfinance") or {}) if isinstance(metadata.get("yfinance"), Mapping) else {}
        yfinance_meta["eod_at"] = issued_at
        metadata["yfinance"] = yfinance_meta
        updated["id"] = str(updated.get("id") or f"ads-security-master:{symbol}")
        updated["symbol"] = symbol
        updated["metadata"] = metadata
        updated.setdefault("created_at", issued_at)
        updated["updated_at"] = issued_at
        return updated

    def _persist_security_row(self, row: Mapping[str, Any]) -> None:
        """Internal helper to persist the security row."""
        worker = getattr(self, "worker", None)
        dispatcher_address = self._resolve_dispatcher_address()

        if worker is not None and dispatcher_address:
            persisted = worker.UsePractice(
                "pool-insert",
                {
                    "table_name": TABLE_SECURITY_MASTER,
                    "data": dict(row),
                },
                pit_address=dispatcher_address,
            )
            if persisted is False:
                raise RuntimeError(
                    f"Failed to update {TABLE_SECURITY_MASTER} for {normalize_symbol(row.get('symbol'))}."
                )
            return

        if worker is not None and getattr(worker, "pool", None) is not None:
            if not worker.pool._Insert(TABLE_SECURITY_MASTER, dict(row)):
                raise RuntimeError(
                    f"Failed to update {TABLE_SECURITY_MASTER} for {normalize_symbol(row.get('symbol'))}."
                )
            return

        raise RuntimeError("YFinanceUSMarketEODJobCap requires a bound worker with dispatcher or pool access.")

    def _submit_symbol_job(self, job: JobDetail, *, symbol: str, issued_at: str) -> Dict[str, Any]:
        """Internal helper to submit the symbol job."""
        worker = getattr(self, "worker", None)
        dispatcher_address = self._resolve_dispatcher_address()
        parent_payload = dict(job.payload or {}) if isinstance(job.payload, Mapping) else {}
        downstream_payload = {
            key: value
            for key, value in parent_payload.items()
            if key not in {"symbol", "symbols"}
        }
        downstream_payload["symbol"] = symbol
        request = {
            "required_capability": self.yfinance_capability,
            "symbols": [symbol],
            "payload": downstream_payload,
            "priority": int(job.priority or 100),
            "max_attempts": int(job.max_attempts or 3),
            "metadata": {
                "submitted_by_job_id": job.id,
                "submitted_by_capability": self.name,
                "submitted_at": issued_at,
            },
        }

        if worker is not None and dispatcher_address:
            response = worker.UsePractice(
                "ads-submit-job",
                request,
                pit_address=dispatcher_address,
            )
            return dict(response or {}) if isinstance(response, Mapping) else {"response": response}

        submit_job = getattr(worker, "submit_job", None)
        if callable(submit_job):
            response = submit_job(**request)
            return dict(response or {}) if isinstance(response, Mapping) else {"response": response}

        raise RuntimeError("YFinanceUSMarketEODJobCap requires dispatcher access to submit YFinance EOD jobs.")
