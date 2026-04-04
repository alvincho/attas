"""
US Listed module for `ads.us_listed`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace.

Core types exposed here include `USListedSecJobCap`, which carry the main behavior or
state managed by this module.
"""

from __future__ import annotations

import csv
from io import StringIO
from typing import Any, Callable, Dict, List, Mapping
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

import requests

from ads.jobcap import JobCap
from ads.models import JobDetail, JobResult
from ads.runtime import normalize_provider, normalize_symbol, utcnow_iso
from ads.schema import TABLE_SECURITY_MASTER, security_master_schema_dict


RequestGetter = Callable[..., Any]

MARKET_CATEGORY_LABELS = {
    "Q": "Nasdaq Global Select Market",
    "G": "Nasdaq Global Market",
    "S": "Nasdaq Capital Market",
}

FINANCIAL_STATUS_LABELS = {
    "D": "Deficient",
    "E": "Delinquent",
    "Q": "Bankrupt",
    "N": "Normal",
    "G": "Deficient and Bankrupt",
    "H": "Deficient and Delinquent",
    "J": "Delinquent and Bankrupt",
    "K": "Deficient, Delinquent, and Bankrupt",
}

OTHER_LISTED_EXCHANGE_LABELS = {
    "A": "NYSE MKT",
    "N": "NYSE",
    "P": "NYSE ARCA",
    "Z": "BATS",
    "V": "IEX",
}


def _truthy_flag(value: Any) -> bool:
    """Internal helper for truthy flag."""
    return str(value or "").strip().upper() == "Y"


def _coerce_integer(value: Any) -> int | None:
    """Internal helper to coerce the integer."""
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _security_master_id(symbol: Any) -> str:
    """Internal helper for security master ID."""
    return f"ads-security-master:{normalize_symbol(symbol)}"


class USListedSecJobCap(JobCap):
    """Job capability implementation for US listed SEC workflows."""
    DEFAULT_NAME = "US Listed Sec to security master"
    DEFAULT_BASE_URL = "https://www.nasdaqtrader.com/dynamic/SymDir"
    DEFAULT_FALLBACK_BASE_URLS = ("ftp://ftp.nasdaqtrader.com/symboldirectory",)
    DEFAULT_NASDAQ_LISTED_PATH = "nasdaqlisted.txt"
    DEFAULT_OTHER_LISTED_PATH = "otherlisted.txt"
    DEFAULT_PROVIDER = "nasdaqtrader"

    def __init__(
        self,
        name: str = DEFAULT_NAME,
        *,
        base_url: str = DEFAULT_BASE_URL,
        nasdaq_listed_path: str = DEFAULT_NASDAQ_LISTED_PATH,
        other_listed_path: str = DEFAULT_OTHER_LISTED_PATH,
        provider: str = DEFAULT_PROVIDER,
        dispatcher_address: str = "",
        timeout_sec: float = 30.0,
        deactivate_missing: bool = True,
        fallback_base_urls: Any = None,
        request_get: RequestGetter | None = None,
        source: str = "",
    ):
        """Initialize the US listed SEC job cap."""
        super().__init__(
            name=name,
            source=source or f"{self.__class__.__module__}:{self.__class__.__name__}",
        )
        self.base_url = str(base_url or self.DEFAULT_BASE_URL).rstrip("/")
        if fallback_base_urls is None:
            fallback_candidates = self.DEFAULT_FALLBACK_BASE_URLS if self.base_url == self.DEFAULT_BASE_URL else ()
        else:
            if isinstance(fallback_base_urls, (list, tuple, set)):
                fallback_candidates = list(fallback_base_urls)
            else:
                fallback_candidates = [fallback_base_urls]
        self.fallback_base_urls = [
            str(candidate or "").rstrip("/")
            for candidate in fallback_candidates
            if str(candidate or "").strip() and str(candidate or "").rstrip("/") != self.base_url
        ]
        self.nasdaq_listed_path = str(nasdaq_listed_path or self.DEFAULT_NASDAQ_LISTED_PATH).strip()
        self.other_listed_path = str(other_listed_path or self.DEFAULT_OTHER_LISTED_PATH).strip()
        self.provider = normalize_provider(provider or self.DEFAULT_PROVIDER) or self.DEFAULT_PROVIDER
        self.dispatcher_address = str(dispatcher_address or "").strip()
        self.timeout_sec = max(float(timeout_sec or 30.0), 1.0)
        self.deactivate_missing = bool(deactivate_missing)
        self.request_get = request_get

    def check_environment(self) -> tuple[bool, str]:
        """Handle check environment for the US listed SEC job cap."""
        url_candidates = [self.base_url, *self.fallback_base_urls]
        for url in url_candidates:
            url_ready, _ = self.check_url_configured(url, label="Nasdaq Trader base URL")
            if url_ready:
                return True, ""
        return False, "Nasdaq Trader base URL is not configured."

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the US listed SEC job cap."""
        fetched_at = utcnow_iso()
        file_payloads = [
            self._fetch_directory_file("nasdaqlisted", self.nasdaq_listed_path),
            self._fetch_directory_file("otherlisted", self.other_listed_path),
        ]

        rows_by_symbol: Dict[str, Dict[str, Any]] = {}
        active_symbols: List[str] = []
        file_summaries: Dict[str, Dict[str, Any]] = {}

        for file_payload in file_payloads:
            dataset = file_payload["dataset"]
            records = file_payload["records"]
            stored_count = 0
            for record in records:
                if dataset == "nasdaqlisted":
                    normalized = self._normalize_nasdaq_listed_row(
                        record,
                        file_creation_time=file_payload["file_creation_time"],
                        source_url=file_payload["url"],
                    )
                else:
                    normalized = self._normalize_other_listed_row(
                        record,
                        file_creation_time=file_payload["file_creation_time"],
                        source_url=file_payload["url"],
                    )
                if normalized is None:
                    continue

                symbol = normalized["symbol"]
                existing = rows_by_symbol.get(symbol)
                if existing is not None:
                    metadata = dict(existing.get("metadata") or {})
                    source_datasets = [
                        str(value)
                        for value in metadata.get("source_datasets") or []
                        if str(value or "").strip()
                    ]
                    if dataset not in source_datasets:
                        source_datasets.append(dataset)
                    metadata["source_datasets"] = source_datasets
                    existing["metadata"] = metadata
                    continue

                rows_by_symbol[symbol] = normalized
                active_symbols.append(symbol)
                stored_count += 1

            file_summaries[dataset] = {
                "url": file_payload["url"],
                "file_creation_time": file_payload["file_creation_time"],
                "source_rows": len(records),
                "stored_rows": stored_count,
            }

        deactivated_symbols: List[str] = []
        if self.deactivate_missing:
            current_by_symbol = {
                normalize_symbol(row.get("symbol")): row
                for row in self._existing_provider_rows()
                if isinstance(row, Mapping) and normalize_symbol(row.get("symbol"))
            }
            active_symbol_set = set(active_symbols)
            snapshot_file_times = {
                payload["dataset"]: payload["file_creation_time"]
                for payload in file_payloads
                if payload.get("file_creation_time")
            }
            for symbol, row in current_by_symbol.items():
                if symbol in active_symbol_set:
                    continue
                deactivated_symbols.append(symbol)
                rows_by_symbol[symbol] = self._build_inactive_row(
                    row,
                    snapshot_file_times=snapshot_file_times,
                    fetched_at=fetched_at,
                )

        raw_payload = {
            "provider": self.provider,
            "base_url": self.base_url,
            "fetched_at": fetched_at,
            "deactivate_missing": self.deactivate_missing,
            "files": [
                {
                    "dataset": payload["dataset"],
                    "url": payload["url"],
                    "file_creation_time": payload["file_creation_time"],
                    "row_count": len(payload["records"]),
                    "payload": payload["records"],
                }
                for payload in file_payloads
            ],
            "deactivated_symbols": deactivated_symbols,
        }
        result_summary = {
            "provider": self.provider,
            "rows": len(rows_by_symbol),
            "active_rows": len(active_symbols),
            "inactive_rows": len(deactivated_symbols),
            "files": file_summaries,
        }
        return JobResult(
            job_id=job.id,
            status="completed",
            target_table=TABLE_SECURITY_MASTER,
            collected_rows=list(rows_by_symbol.values()),
            raw_payload=raw_payload,
            result_summary=result_summary,
        )

    def _resolve_dispatcher_address(self) -> str:
        """Internal helper to resolve the dispatcher address."""
        worker = getattr(self, "worker", None)
        return self.dispatcher_address or str(getattr(worker, "dispatcher_address", "") or "").strip()

    def _existing_provider_rows(self) -> List[Dict[str, Any]]:
        """Internal helper to return the existing provider rows."""
        worker = getattr(self, "worker", None)
        dispatcher_address = self._resolve_dispatcher_address()
        rows: Any = []

        if worker is not None and dispatcher_address:
            rows = worker.UsePractice(
                "pool-get-table-data",
                {
                    "table_name": TABLE_SECURITY_MASTER,
                    "id_or_where": {"provider": self.provider},
                    "table_schema": security_master_schema_dict(),
                },
                pit_address=dispatcher_address,
            )
        elif worker is not None and getattr(worker, "pool", None) is not None:
            rows = worker.pool._GetTableData(TABLE_SECURITY_MASTER, {"provider": self.provider})

        if not isinstance(rows, list):
            return []
        return [dict(row) for row in rows if isinstance(row, Mapping)]

    def _fetch_directory_file(self, dataset: str, path: str) -> Dict[str, Any]:
        """Internal helper to fetch the directory file."""
        errors: list[str] = []
        for url in self._candidate_file_urls(path):
            try:
                payload_text, request_url = self._download_text(url, dataset)
            except Exception as exc:
                errors.append(str(exc))
                continue

            records, file_creation_time = self._parse_symbol_directory_text(payload_text)
            return {
                "dataset": dataset,
                "url": request_url,
                "file_creation_time": file_creation_time,
                "records": records,
            }

        joined_errors = " | ".join(error for error in errors if error)
        raise RuntimeError(
            f"Nasdaq Trader download failed for {dataset} after trying {len(self._candidate_file_urls(path))} source(s): {joined_errors}"
        )

    def _build_file_url(self, path: str) -> str:
        """Internal helper to build the file URL."""
        return urljoin(f"{self.base_url}/", str(path or "").lstrip("/"))

    def _candidate_file_urls(self, path: str) -> list[str]:
        """Internal helper to return the candidate file URLs."""
        relative_path = str(path or "").lstrip("/")
        candidates = [urljoin(f"{self.base_url}/", relative_path)]
        for base_url in self.fallback_base_urls:
            candidate = urljoin(f"{base_url}/", relative_path)
            if candidate not in candidates:
                candidates.append(candidate)
        return candidates

    def _download_text(self, url: str, dataset: str) -> tuple[str, str]:
        """Internal helper for download text."""
        parsed = urlparse(url)

        if self.request_get is not None:
            try:
                response = self.request_get(url, timeout=self.timeout_sec)
            except Exception as exc:
                raise RuntimeError(f"Nasdaq Trader download failed for {dataset} from {url}: {exc}") from exc
            request_url = str(getattr(response, "url", "") or url)
            status_code = int(getattr(response, "status_code", 200) or 200)
            if status_code >= 400:
                raise ValueError(f"Nasdaq Trader request failed for {dataset} with status {status_code}.")
            payload_text = str(getattr(response, "text", "") or "")
            if not payload_text.strip():
                raise ValueError(f"Nasdaq Trader response for {dataset} was empty.")
            return payload_text, request_url

        if parsed.scheme in {"http", "https"}:
            try:
                response = requests.get(url, timeout=self.timeout_sec)
            except Exception as exc:
                raise RuntimeError(f"Nasdaq Trader download failed for {dataset} from {url}: {exc}") from exc
            request_url = str(getattr(response, "url", "") or url)
            status_code = int(getattr(response, "status_code", 200) or 200)
            if status_code >= 400:
                raise ValueError(f"Nasdaq Trader request failed for {dataset} with status {status_code}.")
            payload_text = str(getattr(response, "text", "") or "")
            if not payload_text.strip():
                raise ValueError(f"Nasdaq Trader response for {dataset} was empty.")
            return payload_text, request_url

        if parsed.scheme == "ftp":
            try:
                with urlopen(url, timeout=self.timeout_sec) as response:
                    payload_bytes = response.read()
                    request_url = str(getattr(response, "url", "") or getattr(response, "geturl", lambda: url)() or url)
                    charset = ""
                    headers = getattr(response, "headers", None)
                    if headers is not None:
                        get_charset = getattr(headers, "get_content_charset", None)
                        if callable(get_charset):
                            charset = str(get_charset() or "")
                    payload_text = payload_bytes.decode(charset or "utf-8", errors="replace")
            except Exception as exc:
                raise RuntimeError(f"Nasdaq Trader FTP download failed for {dataset} from {url}: {exc}") from exc
            if not payload_text.strip():
                raise ValueError(f"Nasdaq Trader FTP response for {dataset} was empty.")
            return payload_text, request_url

        raise ValueError(f"Unsupported URL scheme for Nasdaq Trader source: {parsed.scheme or 'unknown'}")

    @staticmethod
    def _parse_symbol_directory_text(payload_text: str) -> tuple[List[Dict[str, str]], str]:
        """Internal helper to parse the symbol directory text."""
        text = str(payload_text or "").replace("\ufeff", "")
        stream = StringIO(text)
        reader = csv.reader(stream, delimiter="|")
        try:
            headers = [str(value or "").strip() for value in next(reader)]
        except StopIteration:
            return [], ""

        records: List[Dict[str, str]] = []
        file_creation_time = ""
        for row in reader:
            if not row:
                continue
            values = [str(value or "").strip() for value in row]
            first_value = values[0] if values else ""
            if not first_value:
                continue
            if first_value.startswith("File Creation Time:"):
                file_creation_time = first_value.split(":", 1)[1].strip()
                continue
            record = {
                header: values[index] if index < len(values) else ""
                for index, header in enumerate(headers)
                if header
            }
            if record:
                records.append(record)
        return records, file_creation_time

    def _normalize_nasdaq_listed_row(
        self,
        record: Mapping[str, Any],
        *,
        file_creation_time: str,
        source_url: str,
    ) -> Dict[str, Any] | None:
        """Internal helper to normalize the nasdaq listed row."""
        symbol = normalize_symbol(record.get("Symbol"))
        if not symbol or _truthy_flag(record.get("Test Issue")):
            return None

        name = str(record.get("Security Name") or "").strip() or symbol
        market_category = str(record.get("Market Category") or "").strip().upper()
        financial_status = str(record.get("Financial Status") or "").strip().upper()
        is_etf = _truthy_flag(record.get("ETF"))
        is_nextshares = _truthy_flag(record.get("NextShares"))

        return {
            "id": _security_master_id(symbol),
            "symbol": symbol,
            "name": name,
            "instrument_type": self._infer_instrument_type(name, is_etf=is_etf, is_nextshares=is_nextshares),
            "exchange": "NASDAQ",
            "currency": "USD",
            "is_active": True,
            "provider": self.provider,
            "metadata": {
                "listing_source": "nasdaqlisted",
                "source_datasets": ["nasdaqlisted"],
                "source_url": source_url,
                "file_creation_time": file_creation_time,
                "market_category": market_category,
                "market_category_label": MARKET_CATEGORY_LABELS.get(market_category, ""),
                "financial_status": financial_status,
                "financial_status_label": FINANCIAL_STATUS_LABELS.get(financial_status, ""),
                "round_lot_size": _coerce_integer(record.get("Round Lot Size")),
                "is_etf": is_etf,
                "is_nextshares": is_nextshares,
            },
        }

    def _normalize_other_listed_row(
        self,
        record: Mapping[str, Any],
        *,
        file_creation_time: str,
        source_url: str,
    ) -> Dict[str, Any] | None:
        """Internal helper to normalize the other listed row."""
        act_symbol = normalize_symbol(record.get("ACT Symbol"))
        if not act_symbol or _truthy_flag(record.get("Test Issue")):
            return None

        cqs_symbol = normalize_symbol(record.get("CQS Symbol"))
        nasdaq_symbol = normalize_symbol(record.get("NASDAQ Symbol"))
        name = str(record.get("Security Name") or "").strip() or act_symbol
        exchange_code = str(record.get("Exchange") or "").strip().upper()
        is_etf = _truthy_flag(record.get("ETF"))
        aliases: List[str] = []
        for candidate in (act_symbol, cqs_symbol, nasdaq_symbol):
            if candidate and candidate not in aliases:
                aliases.append(candidate)

        return {
            "id": _security_master_id(act_symbol),
            "symbol": act_symbol,
            "name": name,
            "instrument_type": self._infer_instrument_type(name, is_etf=is_etf, is_nextshares=False),
            "exchange": OTHER_LISTED_EXCHANGE_LABELS.get(exchange_code, exchange_code or "OTHER"),
            "currency": "USD",
            "is_active": True,
            "provider": self.provider,
            "metadata": {
                "listing_source": "otherlisted",
                "source_datasets": ["otherlisted"],
                "source_url": source_url,
                "file_creation_time": file_creation_time,
                "exchange_code": exchange_code,
                "exchange_label": OTHER_LISTED_EXCHANGE_LABELS.get(exchange_code, ""),
                "act_symbol": act_symbol,
                "cqs_symbol": cqs_symbol,
                "nasdaq_symbol": nasdaq_symbol,
                "aliases": aliases,
                "round_lot_size": _coerce_integer(record.get("Round Lot Size")),
                "is_etf": is_etf,
            },
        }

    def _build_inactive_row(
        self,
        record: Mapping[str, Any],
        *,
        snapshot_file_times: Mapping[str, str],
        fetched_at: str,
    ) -> Dict[str, Any]:
        """Internal helper to build the inactive row."""
        symbol = normalize_symbol(record.get("symbol"))
        metadata = dict(record.get("metadata") or {}) if isinstance(record.get("metadata"), Mapping) else {}
        metadata.update(
            {
                "deactivated_reason": "missing_from_latest_us_listed_snapshot",
                "deactivated_at": fetched_at,
                "latest_snapshot_file_creation_times": dict(snapshot_file_times),
            }
        )
        return {
            "id": str(record.get("id") or _security_master_id(symbol)),
            "symbol": symbol,
            "name": str(record.get("name") or symbol),
            "instrument_type": str(record.get("instrument_type") or ""),
            "exchange": str(record.get("exchange") or ""),
            "currency": str(record.get("currency") or "USD"),
            "is_active": False,
            "provider": self.provider,
            "metadata": metadata,
            "created_at": str(record.get("created_at") or ""),
        }

    @staticmethod
    def _infer_instrument_type(name: str, *, is_etf: bool, is_nextshares: bool) -> str:
        """Internal helper for infer instrument type."""
        upper_name = str(name or "").upper()
        if is_nextshares:
            return "nextshares"
        if is_etf or " ETF" in upper_name or upper_name.endswith("ETF"):
            return "etf"
        if "WARRANT" in upper_name:
            return "warrant"
        if "RIGHT" in upper_name:
            return "right"
        if "UNIT" in upper_name:
            return "unit"
        if "PREFERRED" in upper_name or "PREFERENCE" in upper_name or "DEPOSITARY SHARE" in upper_name:
            return "preferred"
        if "NOTE" in upper_name or "NOTES" in upper_name or "DEBENTURE" in upper_name or "BOND" in upper_name:
            return "debt"
        if "AMERICAN DEPOSITARY" in upper_name:
            return "adr"
        return "equity"
