"""
SEC module for `ads.sec`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace.

Core types exposed here include `USFilingBulkJobCap` and `USFilingMappingJobCap`, which
carry the main behavior or state managed by this module.
"""

from __future__ import annotations

import json
import re
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence

import requests

from ads.jobcap import JobCap
from ads.models import JobDetail, JobResult
from ads.runtime import normalize_provider, normalize_string_list, normalize_symbol, parse_datetime_value, utcnow_iso
from ads.schema import (
    TABLE_FINANCIAL_STATEMENTS,
    TABLE_FUNDAMENTALS,
    TABLE_SEC_COMPANYFACTS,
    TABLE_SEC_SUBMISSIONS,
    ads_table_schema_map,
    ensure_ads_tables,
)


RequestGetter = Callable[..., Any]

SEC_COMPANYFACTS_URL = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
SEC_SUBMISSIONS_URL = "https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip"
SEC_PROVIDER = "sec_edgar"
DEFAULT_USER_AGENT = "FinMAS USFilingJobCap/1.0 (contact: dev@local.test)"
DEFAULT_ARCHIVE_CACHE_DIR = Path(__file__).resolve().parent / "storage" / "sec_edgar"
ARCHIVE_CHUNK_SIZE = 65536
PERSIST_CHUNK_SIZE = 200
HEARTBEAT_FILE_INTERVAL = 500
DOWNLOAD_HEARTBEAT_INTERVAL_BYTES = 5 * 1024 * 1024
DEFAULT_ARCHIVE_CACHE_MAX_AGE_HOURS = 24.0

PRIMARY_SUBMISSIONS_FILENAME_RE = re.compile(r"^CIK\d{10}\.json$", re.IGNORECASE)
SUPPLEMENTAL_SUBMISSIONS_FILENAME_RE = re.compile(r"^CIK(\d{10})-submissions-\d+\.json$", re.IGNORECASE)
COMPANYFACTS_FILENAME_RE = re.compile(r"^CIK(\d{10})\.json$", re.IGNORECASE)

SUPPORTED_STATEMENT_FORMS = {
    "10-K",
    "10-K/A",
    "10-Q",
    "10-Q/A",
    "20-F",
    "20-F/A",
    "40-F",
    "40-F/A",
    "6-K",
    "6-K/A",
    "8-K",
    "8-K/A",
}

LATEST_FACT_METRICS: Dict[str, list[tuple[str, str]]] = {
    "shares_outstanding": [("dei", "EntityCommonStockSharesOutstanding")],
    "public_float": [("dei", "EntityPublicFloat")],
    "revenue": [
        ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
        ("us-gaap", "Revenues"),
        ("us-gaap", "SalesRevenueNet"),
    ],
    "net_income": [("us-gaap", "NetIncomeLoss")],
    "assets": [("us-gaap", "Assets")],
    "liabilities": [("us-gaap", "Liabilities")],
    "stockholders_equity": [
        ("us-gaap", "StockholdersEquity"),
        ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    ],
    "operating_cash_flow": [
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
        ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
    ],
}

STATEMENT_METRIC_CONCEPTS: Dict[str, Dict[str, list[tuple[str, str]]]] = {
    "income_statement": {
        "revenue": [
            ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
            ("us-gaap", "Revenues"),
            ("us-gaap", "SalesRevenueNet"),
        ],
        "gross_profit": [("us-gaap", "GrossProfit")],
        "operating_income": [("us-gaap", "OperatingIncomeLoss")],
        "net_income": [("us-gaap", "NetIncomeLoss")],
        "cost_of_revenue": [
            ("us-gaap", "CostOfRevenue"),
            ("us-gaap", "CostOfGoodsSold"),
            ("us-gaap", "CostOfSales"),
        ],
        "operating_expenses": [("us-gaap", "OperatingExpenses")],
        "pretax_income": [
            ("us-gaap", "IncomeBeforeTaxExpenseBenefit"),
            ("us-gaap", "PretaxIncome"),
        ],
        "eps_basic": [
            ("us-gaap", "EarningsPerShareBasic"),
            ("us-gaap", "EarningsPerShareBasicAndDiluted"),
        ],
        "eps_diluted": [
            ("us-gaap", "EarningsPerShareDiluted"),
            ("us-gaap", "EarningsPerShareBasicAndDiluted"),
        ],
    },
    "balance_sheet": {
        "assets": [("us-gaap", "Assets")],
        "current_assets": [("us-gaap", "AssetsCurrent")],
        "liabilities": [("us-gaap", "Liabilities")],
        "current_liabilities": [("us-gaap", "LiabilitiesCurrent")],
        "stockholders_equity": [
            ("us-gaap", "StockholdersEquity"),
            ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
        ],
        "cash_and_cash_equivalents": [
            ("us-gaap", "CashAndCashEquivalentsAtCarryingValue"),
            ("us-gaap", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"),
        ],
        "inventory": [("us-gaap", "InventoryNet")],
        "long_term_debt": [
            ("us-gaap", "LongTermDebt"),
            ("us-gaap", "LongTermDebtNoncurrent"),
        ],
        "shares_outstanding": [("dei", "EntityCommonStockSharesOutstanding")],
        "public_float": [("dei", "EntityPublicFloat")],
    },
    "cash_flow": {
        "operating_cash_flow": [
            ("us-gaap", "NetCashProvidedByUsedInOperatingActivities"),
            ("us-gaap", "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"),
        ],
        "investing_cash_flow": [
            ("us-gaap", "NetCashProvidedByUsedInInvestingActivities"),
            ("us-gaap", "NetCashProvidedByUsedInInvestingActivitiesContinuingOperations"),
        ],
        "financing_cash_flow": [
            ("us-gaap", "NetCashProvidedByUsedInFinancingActivities"),
            ("us-gaap", "NetCashProvidedByUsedInFinancingActivitiesContinuingOperations"),
        ],
        "capital_expenditures": [
            ("us-gaap", "PaymentsToAcquirePropertyPlantAndEquipment"),
            ("us-gaap", "CapitalExpendituresIncurredButNotYetPaid"),
        ],
        "depreciation_and_amortization": [
            ("us-gaap", "Depreciation"),
            ("us-gaap", "DepreciationDepletionAndAmortization"),
        ],
    },
}

METRIC_UNIT_PREFERENCES: Dict[str, tuple[str, ...]] = {
    "shares_outstanding": ("shares",),
    "public_float": ("USD",),
    "eps_basic": ("USD",),
    "eps_diluted": ("USD",),
}


def _normalize_cik(value: Any) -> str:
    """Internal helper to normalize the cik."""
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return ""
    return digits.zfill(10)


def _cik_archive_component(cik: Any) -> str:
    """Internal helper for cik archive component."""
    normalized = _normalize_cik(cik)
    if not normalized:
        return ""
    try:
        return str(int(normalized))
    except ValueError:
        return normalized


def _clean_id_part(value: Any) -> str:
    """Internal helper for clean ID part."""
    return re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(value or "").strip())


def _sec_row_id(prefix: str, *parts: Any) -> str:
    """Internal helper for SEC row ID."""
    cleaned_parts = [_clean_id_part(part) for part in parts if str(part or "").strip()]
    return ":".join([_clean_id_part(prefix), *cleaned_parts])


def _coerce_int(value: Any) -> int | None:
    """Internal helper to coerce the int."""
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
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


def _string_list(value: Any) -> list[str]:
    """Internal helper for string list."""
    return [str(item or "").strip() for item in normalize_string_list(value) if str(item or "").strip()]


def _first_submission_symbol(payload: Mapping[str, Any]) -> str:
    """Internal helper for first submission symbol."""
    tickers = payload.get("tickers")
    if isinstance(tickers, Sequence) and not isinstance(tickers, (str, bytes, bytearray)):
        for ticker in tickers:
            normalized = normalize_symbol(ticker)
            if normalized:
                return normalized
    return ""


def _count_companyfacts(payload: Mapping[str, Any]) -> int:
    """Internal helper for count companyfacts."""
    facts = payload.get("facts")
    if not isinstance(facts, Mapping):
        return 0
    return sum(len(taxonomy_facts) for taxonomy_facts in facts.values() if isinstance(taxonomy_facts, Mapping))


def _count_submission_filings(payload: Mapping[str, Any]) -> int:
    """Internal helper for count submission filings."""
    filings = payload.get("filings")
    if isinstance(filings, Mapping):
        recent = filings.get("recent")
        if isinstance(recent, Mapping):
            accession_numbers = recent.get("accessionNumber")
            if isinstance(accession_numbers, Sequence) and not isinstance(accession_numbers, (str, bytes, bytearray)):
                return len(accession_numbers)
    accession_numbers = payload.get("accessionNumber")
    if isinstance(accession_numbers, Sequence) and not isinstance(accession_numbers, (str, bytes, bytearray)):
        return len(accession_numbers)
    filing_count = _coerce_int(payload.get("filingCount"))
    return filing_count or 0


def _is_primary_submission_file(file_name: str) -> bool:
    """Return whether the value is a primary submission file."""
    return bool(PRIMARY_SUBMISSIONS_FILENAME_RE.match(str(file_name or "").strip()))


def _sector_from_owner_org(value: Any) -> str:
    """Internal helper for sector from owner org."""
    text = str(value or "").strip()
    if not text:
        return ""
    return re.sub(r"^\d+\s*", "", text).strip() or text


def _recent_filings_from_submission(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Internal helper for recent filings from submission."""
    filings = payload.get("filings")
    if not isinstance(filings, Mapping):
        return []
    recent = filings.get("recent")
    if not isinstance(recent, Mapping):
        return []
    arrays = {
        key: value
        for key, value in recent.items()
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))
    }
    if not arrays:
        return []
    row_count = max((len(value) for value in arrays.values()), default=0)
    rows: list[dict[str, Any]] = []
    for index in range(row_count):
        row = {
            key: values[index] if index < len(values) else None
            for key, values in arrays.items()
        }
        rows.append(row)
    rows.sort(
        key=lambda row: (
            parse_datetime_value(row.get("acceptanceDateTime") or row.get("filingDate")),
            parse_datetime_value(row.get("filingDate")),
            str(row.get("accessionNumber") or ""),
        ),
        reverse=True,
    )
    return rows


def _recent_filing_lookup_by_accession(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    """Internal helper for recent filing lookup by accession."""
    lookup: dict[str, dict[str, Any]] = {}
    for row in _recent_filings_from_submission(payload):
        accession = str(row.get("accessionNumber") or "").strip()
        if accession and accession not in lookup:
            lookup[accession] = row
    return lookup


def _normalize_currency_from_unit(unit_name: Any) -> str:
    """Internal helper to normalize the currency from unit."""
    normalized = str(unit_name or "").strip().upper()
    if not normalized or normalized in {"SHARES", "PURE"}:
        return ""
    for separator in ("-PER-", "/"):
        if separator in normalized:
            normalized = normalized.split(separator, 1)[0].strip()
            break
    if normalized in {"SHARES", "PURE"}:
        return ""
    return normalized


def _unit_matches_preference(unit_name: Any, preference: Any) -> bool:
    """Return whether the unit matches preference."""
    normalized_unit = str(unit_name or "").strip().upper()
    normalized_preference = str(preference or "").strip().upper()
    if not normalized_unit or not normalized_preference:
        return False
    if normalized_unit == normalized_preference:
        return True
    return normalized_unit.startswith(f"{normalized_preference}/") or normalized_unit.startswith(
        f"{normalized_preference}-PER-"
    )


def _fact_sort_key(entry: Mapping[str, Any]) -> tuple[datetime, datetime, datetime, str]:
    """Internal helper to return the fact sort key."""
    return (
        parse_datetime_value(entry.get("filed")),
        parse_datetime_value(entry.get("end")),
        parse_datetime_value(entry.get("start")),
        str(entry.get("accn") or ""),
    )


def _iter_matching_fact_entries(
    facts: Mapping[str, Any],
    concept_refs: Sequence[tuple[str, str]],
    *,
    preferred_units: Sequence[str] = (),
    allowed_forms: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Internal helper for iter matching fact entries."""
    normalized_forms = {str(form or "").strip().upper() for form in (allowed_forms or set()) if str(form or "").strip()}
    for taxonomy, concept_name in concept_refs:
        taxonomy_facts = facts.get(taxonomy)
        if not isinstance(taxonomy_facts, Mapping):
            continue
        concept = taxonomy_facts.get(concept_name)
        if not isinstance(concept, Mapping):
            continue
        units = concept.get("units")
        if not isinstance(units, Mapping):
            continue
        ordered_units = list(units.keys())
        if preferred_units:
            preferred = [unit_name for unit_name in ordered_units if any(_unit_matches_preference(unit_name, item) for item in preferred_units)]
            ordered_units = preferred or ordered_units
        for unit_name in ordered_units:
            unit_entries = units.get(unit_name)
            if not isinstance(unit_entries, Sequence) or isinstance(unit_entries, (str, bytes, bytearray)):
                continue
            rows: list[dict[str, Any]] = []
            for entry in unit_entries:
                if not isinstance(entry, Mapping):
                    continue
                normalized_form = str(entry.get("form") or "").strip().upper()
                if normalized_forms and normalized_form not in normalized_forms:
                    continue
                if entry.get("val") is None:
                    continue
                normalized_entry = dict(entry)
                normalized_entry["_taxonomy"] = taxonomy
                normalized_entry["_concept"] = concept_name
                normalized_entry["_unit"] = unit_name
                rows.append(normalized_entry)
            if rows:
                rows.sort(key=_fact_sort_key, reverse=True)
                return rows
    return []


def _latest_fact_entry(
    facts: Mapping[str, Any],
    concept_refs: Sequence[tuple[str, str]],
    *,
    preferred_units: Sequence[str] = (),
    allowed_forms: set[str] | None = None,
) -> dict[str, Any] | None:
    """Internal helper to return the latest fact entry."""
    entries = _iter_matching_fact_entries(
        facts,
        concept_refs,
        preferred_units=preferred_units,
        allowed_forms=allowed_forms,
    )
    return entries[0] if entries else None


def _fact_snapshot(entry: Mapping[str, Any] | None) -> dict[str, Any]:
    """Internal helper to return the fact snapshot."""
    if not isinstance(entry, Mapping):
        return {}
    return {
        "value": _coerce_number(entry.get("val")),
        "unit": str(entry.get("_unit") or "").strip(),
        "taxonomy": str(entry.get("_taxonomy") or "").strip(),
        "concept": str(entry.get("_concept") or "").strip(),
        "start": str(entry.get("start") or "").strip(),
        "end": str(entry.get("end") or "").strip(),
        "filed": str(entry.get("filed") or "").strip(),
        "form": str(entry.get("form") or "").strip(),
        "accn": str(entry.get("accn") or "").strip(),
        "fy": _coerce_int(entry.get("fy")),
        "fp": str(entry.get("fp") or "").strip(),
        "frame": str(entry.get("frame") or "").strip(),
    }


def _format_fiscal_period(entry: Mapping[str, Any]) -> str:
    """Internal helper to format the fiscal period."""
    fy = _coerce_int(entry.get("fy"))
    fp = str(entry.get("fp") or "").strip().upper()
    end = str(entry.get("end") or "").strip()
    if fy and fp:
        if fp == "FY":
            return f"FY{fy}"
        return f"FY{fy}-{fp}"
    if fy:
        return f"FY{fy}"
    return end


def _statement_row_sort_key(row: Mapping[str, Any]) -> tuple[datetime, datetime, str]:
    """Internal helper to return the statement row sort key."""
    data = row.get("data") if isinstance(row.get("data"), Mapping) else {}
    return (
        parse_datetime_value(row.get("period_end")),
        parse_datetime_value(data.get("filed")),
        str(row.get("id") or ""),
    )


def _build_filing_url(cik: Any, accession_number: Any, primary_document: Any = "") -> str:
    """Internal helper to build the filing URL."""
    archive_cik = _cik_archive_component(cik)
    accession = str(accession_number or "").strip()
    if not archive_cik or not accession:
        return ""
    accession_no_dashes = accession.replace("-", "")
    normalized_primary_document = str(primary_document or "").strip().lstrip("/")
    if normalized_primary_document:
        return (
            f"https://www.sec.gov/Archives/edgar/data/{archive_cik}/"
            f"{accession_no_dashes}/{normalized_primary_document}"
        )
    return f"https://www.sec.gov/Archives/edgar/data/{archive_cik}/{accession_no_dashes}/"


def _progress_percent(current: int, total: int, *, start: float, end: float) -> float:
    """Internal helper for progress percent."""
    normalized_total = max(int(total or 0), 1)
    normalized_current = min(max(int(current or 0), 1), normalized_total)
    if end <= start:
        return float(start)
    fraction = (normalized_current - 1) / normalized_total
    return float(start) + ((float(end) - float(start)) * fraction)


def _progress_percent_float(current: float, total: float, *, start: float, end: float) -> float:
    """Internal helper for progress percent float."""
    try:
        normalized_total = max(float(total or 0.0), 1.0)
    except (TypeError, ValueError):
        normalized_total = 1.0
    try:
        normalized_current = min(max(float(current or 0.0), 0.0), normalized_total)
    except (TypeError, ValueError):
        normalized_current = 0.0
    if end <= start:
        return float(start)
    fraction = normalized_current / normalized_total
    return float(start) + ((float(end) - float(start)) * fraction)


def _should_emit_file_heartbeat(index: int, total: int, *, interval: int = HEARTBEAT_FILE_INTERVAL) -> bool:
    """Return whether the value should emit file heartbeat."""
    normalized_total = max(int(total or 0), 0)
    normalized_index = max(int(index or 0), 0)
    normalized_interval = max(int(interval or HEARTBEAT_FILE_INTERVAL), 1)
    if normalized_total <= 1:
        return normalized_index >= 1
    return normalized_index in {1, normalized_total} or (normalized_index % normalized_interval) == 0


def _company_progress_label(*, cik: Any = "", symbol: Any = "") -> str:
    """Internal helper for company progress label."""
    normalized_cik = _normalize_cik(cik)
    normalized_symbol = normalize_symbol(symbol)
    if normalized_symbol and normalized_cik:
        return f"{normalized_symbol} (CIK {normalized_cik})"
    if normalized_symbol:
        return normalized_symbol
    if normalized_cik:
        return f"CIK {normalized_cik}"
    return "the requested company"


def _row_progress_label(row: Mapping[str, Any], *, fallback: str = "") -> str:
    """Internal helper to return the row progress label."""
    entity_name = str(row.get("entity_name") or "").strip()
    if entity_name:
        return entity_name
    symbol = normalize_symbol(row.get("symbol"))
    if symbol:
        return symbol
    cik = _normalize_cik(row.get("cik"))
    if cik:
        return cik
    file_name = str(row.get("file_name") or "").strip()
    if file_name:
        return file_name
    return str(fallback or "").strip()


def _download_progress_message(archive_name: str, downloaded_bytes: int, total_bytes: int | None) -> str:
    """Internal helper to return the download progress message."""
    if total_bytes and total_bytes > 0:
        return f"Downloading {archive_name} {downloaded_bytes}/{total_bytes} bytes."
    return f"Downloading {archive_name} {downloaded_bytes}/? bytes."


def _should_emit_download_heartbeat(
    downloaded_bytes: int,
    total_bytes: int | None,
    *,
    last_emitted_bytes: int,
    interval_bytes: int = DOWNLOAD_HEARTBEAT_INTERVAL_BYTES,
) -> bool:
    """Return whether the value should emit download heartbeat."""
    normalized_downloaded = max(int(downloaded_bytes or 0), 0)
    normalized_last = max(int(last_emitted_bytes or 0), 0)
    normalized_interval = max(int(interval_bytes or DOWNLOAD_HEARTBEAT_INTERVAL_BYTES), 1)
    normalized_total = max(int(total_bytes or 0), 0)
    if normalized_downloaded <= 0:
        return False
    if normalized_last <= 0:
        return True
    if normalized_total and normalized_downloaded >= normalized_total:
        return True
    return (normalized_downloaded - normalized_last) >= normalized_interval


def _report_worker_progress(
    worker: Any,
    *,
    phase: str,
    message: str,
    percent: Any = None,
    current: Any = None,
    total: Any = None,
    extra: Mapping[str, Any] | None = None,
    emit_heartbeat: bool = False,
) -> dict[str, Any]:
    """Internal helper to report the worker progress."""
    snapshot: dict[str, Any] = {}
    update_progress = getattr(worker, "update_progress", None)
    if callable(update_progress):
        snapshot = update_progress(
            phase=phase,
            message=message,
            percent=percent,
            current=current,
            total=total,
            extra=dict(extra or {}),
        )
    if emit_heartbeat:
        send_heartbeat = getattr(worker, "_send_worker_heartbeat", None)
        if callable(send_heartbeat):
            try:
                send_heartbeat(event_type="heartbeat")
            except Exception:
                pass
    return snapshot


def _raise_if_stop_requested(worker: Any, job: JobDetail) -> None:
    """Internal helper for raise if stop requested."""
    raise_if_stop_requested = getattr(worker, "raise_if_stop_requested", None)
    if callable(raise_if_stop_requested):
        raise_if_stop_requested(job)


class USFilingBulkJobCap(JobCap):
    """Job capability implementation for US filing bulk workflows."""
    DEFAULT_NAME = "US Filing Bulk"

    def __init__(
        self,
        name: str = DEFAULT_NAME,
        *,
        companyfacts_url: str = SEC_COMPANYFACTS_URL,
        submissions_url: str = SEC_SUBMISSIONS_URL,
        provider: str = SEC_PROVIDER,
        timeout_sec: float = 120.0,
        user_agent: str = DEFAULT_USER_AGENT,
        cache_dir: str | Path | None = None,
        cache_max_age_hours: float = DEFAULT_ARCHIVE_CACHE_MAX_AGE_HOURS,
        persist_chunk_size: int = PERSIST_CHUNK_SIZE,
        request_get: RequestGetter | None = None,
        source: str = "",
    ):
        """Initialize the US filing bulk job cap."""
        super().__init__(
            name=name,
            source=source or f"{self.__class__.__module__}:{self.__class__.__name__}",
        )
        self.companyfacts_url = str(companyfacts_url or SEC_COMPANYFACTS_URL).strip()
        self.submissions_url = str(submissions_url or SEC_SUBMISSIONS_URL).strip()
        self.provider = normalize_provider(provider or SEC_PROVIDER) or SEC_PROVIDER
        self.timeout_sec = max(float(timeout_sec or 120.0), 1.0)
        self.user_agent = str(user_agent or DEFAULT_USER_AGENT).strip() or DEFAULT_USER_AGENT
        resolved_cache_dir = Path(cache_dir).expanduser() if cache_dir else DEFAULT_ARCHIVE_CACHE_DIR
        if not resolved_cache_dir.is_absolute():
            resolved_cache_dir = (Path.cwd() / resolved_cache_dir).resolve()
        self.cache_dir = resolved_cache_dir
        self.cache_max_age_sec = max(float(cache_max_age_hours or DEFAULT_ARCHIVE_CACHE_MAX_AGE_HOURS), 0.0) * 3600.0
        self.persist_chunk_size = max(int(persist_chunk_size or PERSIST_CHUNK_SIZE), 1)
        self.request_get = request_get or requests.get

    def check_environment(self) -> tuple[bool, str]:
        """Handle check environment for the US filing bulk job cap."""
        companyfacts_url_ready, companyfacts_url_reason = self.check_url_configured(
            self.companyfacts_url,
            label="SEC companyfacts URL",
        )
        if not companyfacts_url_ready:
            return False, companyfacts_url_reason
        submissions_url_ready, submissions_url_reason = self.check_url_configured(
            self.submissions_url,
            label="SEC submissions URL",
        )
        if not submissions_url_ready:
            return False, submissions_url_reason
        if not str(self.cache_dir or "").strip():
            return False, "SEC archive cache directory is not configured."
        if not callable(self.request_get):
            return False, "SEC request client is not callable."
        return True, ""

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the US filing bulk job cap."""
        started_at = utcnow_iso()
        direct_pool = self._pool()
        direct_persist = direct_pool is not None
        if direct_persist:
            ensure_ads_tables(direct_pool, [TABLE_SEC_COMPANYFACTS, TABLE_SEC_SUBMISSIONS])

        companyfacts_rows: list[dict[str, Any]] = []
        submissions_rows: list[dict[str, Any]] = []
        companyfacts_written = 0
        submissions_written = 0
        companyfacts_buffer: list[dict[str, Any]] = []
        submissions_buffer: list[dict[str, Any]] = []

        self._ensure_cache_dir()
        self._raise_if_stop_requested(job)
        companyfacts_archive = self._download_archive(
            self.companyfacts_url,
            "companyfacts",
            current=1,
            total=2,
            percent_start=2,
            percent_end=4,
            table_name=TABLE_SEC_COMPANYFACTS,
        )
        self._raise_if_stop_requested(job)
        self._report_progress(
            phase="extracting",
            message="Extracting companyfacts.zip.",
            percent=5,
            current=0,
            total=0,
            extra={
                "job_kind": "us_filing_bulk",
                "dataset": "companyfacts",
                "archive_file": Path(companyfacts_archive["path"]).name,
                "file_name": "",
                "table_name": TABLE_SEC_COMPANYFACTS,
                "step": "extract_archive",
                "source_url": companyfacts_archive["url"],
                "local_path": companyfacts_archive["local_path"],
                "cache_status": companyfacts_archive["cache_status"],
                "cache_age_hours": companyfacts_archive["cache_age_hours"],
            },
            emit_heartbeat=True,
        )
        self._raise_if_stop_requested(job)
        submissions_archive = self._download_archive(
            self.submissions_url,
            "submissions",
            current=2,
            total=2,
            percent_start=55,
            percent_end=59,
            table_name=TABLE_SEC_SUBMISSIONS,
        )

        def consume_companyfacts(row: dict[str, Any], current: int, total: int) -> None:
            """Handle consume companyfacts for the US filing bulk job cap."""
            nonlocal companyfacts_written
            if not direct_persist:
                companyfacts_rows.append(row)
                return
            self._report_insert_progress(
                dataset="companyfacts",
                row=row,
                current=current,
                total=total,
                table_name=TABLE_SEC_COMPANYFACTS,
                percent_start=12,
                percent_end=54,
            )
            companyfacts_buffer.append(row)
            if len(companyfacts_buffer) >= self.persist_chunk_size:
                companyfacts_written += self._persist_rows(
                    TABLE_SEC_COMPANYFACTS,
                    companyfacts_buffer,
                    source_url=companyfacts_archive["url"],
                )
                companyfacts_buffer.clear()

        def consume_submissions(row: dict[str, Any], current: int, total: int) -> None:
            """Handle consume submissions for the US filing bulk job cap."""
            nonlocal submissions_written
            if not direct_persist:
                submissions_rows.append(row)
                return
            self._report_insert_progress(
                dataset="submissions",
                row=row,
                current=current,
                total=total,
                table_name=TABLE_SEC_SUBMISSIONS,
                percent_start=68,
                percent_end=98,
            )
            submissions_buffer.append(row)
            if len(submissions_buffer) >= self.persist_chunk_size:
                submissions_written += self._persist_rows(
                    TABLE_SEC_SUBMISSIONS,
                    submissions_buffer,
                    source_url=submissions_archive["url"],
                )
                submissions_buffer.clear()
        companyfacts_stats = self._walk_companyfacts_archive(
            Path(companyfacts_archive["path"]),
            job=job,
            source_url=companyfacts_archive["url"],
            consumer=consume_companyfacts,
        )
        self._raise_if_stop_requested(job)
        self._report_progress(
            phase="extracting",
            message="Extracting submissions.zip.",
            percent=60,
            current=0,
            total=0,
            extra={
                "job_kind": "us_filing_bulk",
                "dataset": "submissions",
                "archive_file": Path(submissions_archive["path"]).name,
                "file_name": "",
                "table_name": TABLE_SEC_SUBMISSIONS,
                "step": "extract_archive",
                "source_url": submissions_archive["url"],
                "local_path": submissions_archive["local_path"],
                "cache_status": submissions_archive["cache_status"],
                "cache_age_hours": submissions_archive["cache_age_hours"],
            },
            emit_heartbeat=True,
        )
        submissions_stats = self._walk_submissions_archive(
            Path(submissions_archive["path"]),
            job=job,
            source_url=submissions_archive["url"],
            consumer=consume_submissions,
        )

        if direct_persist and companyfacts_buffer:
            companyfacts_written += self._persist_rows(
                TABLE_SEC_COMPANYFACTS,
                companyfacts_buffer,
                source_url=companyfacts_archive["url"],
            )
        if direct_persist and submissions_buffer:
            submissions_written += self._persist_rows(
                TABLE_SEC_SUBMISSIONS,
                submissions_buffer,
                source_url=submissions_archive["url"],
            )

        if not direct_persist:
            companyfacts_written = len(companyfacts_rows)
            submissions_written = len(submissions_rows)

        raw_payload = {
            "provider": self.provider,
            "started_at": started_at,
            "archives": [
                {
                    "dataset": "companyfacts",
                    "url": companyfacts_archive["url"],
                    "local_path": companyfacts_archive["local_path"],
                    "cache_status": companyfacts_archive["cache_status"],
                    "cache_age_hours": companyfacts_archive["cache_age_hours"],
                    "file_count": companyfacts_stats["file_count"],
                    "row_count": companyfacts_written,
                },
                {
                    "dataset": "submissions",
                    "url": submissions_archive["url"],
                    "local_path": submissions_archive["local_path"],
                    "cache_status": submissions_archive["cache_status"],
                    "cache_age_hours": submissions_archive["cache_age_hours"],
                    "file_count": submissions_stats["file_count"],
                    "row_count": submissions_written,
                    "primary_rows": submissions_stats["primary_rows"],
                    "supplemental_rows": submissions_stats["supplemental_rows"],
                },
            ],
            "direct_persist": direct_persist,
        }
        result_summary = {
            "provider": self.provider,
            "direct_persist": direct_persist,
            "rows_by_table": {
                TABLE_SEC_COMPANYFACTS: companyfacts_written,
                TABLE_SEC_SUBMISSIONS: submissions_written,
            },
            "archives": {
                "companyfacts": companyfacts_stats,
                "submissions": submissions_stats,
            },
            "cache": {
                "companyfacts": {
                    "local_path": companyfacts_archive["local_path"],
                    "cache_status": companyfacts_archive["cache_status"],
                    "cache_age_hours": companyfacts_archive["cache_age_hours"],
                },
                "submissions": {
                    "local_path": submissions_archive["local_path"],
                    "cache_status": submissions_archive["cache_status"],
                    "cache_age_hours": submissions_archive["cache_age_hours"],
                },
            },
        }
        self._report_progress(
            phase="finalizing",
            message=(
                "Prepared SEC bulk ingest results: "
                f"{companyfacts_written} companyfacts rows and "
                f"{submissions_written} submissions rows."
            ),
            percent=99,
            current=2,
            total=2,
            extra={
                "job_kind": "us_filing_bulk",
                "dataset": "submissions",
                "archive_file": Path(submissions_archive["path"]).name,
                "file_name": "",
                "table_name": TABLE_SEC_SUBMISSIONS,
                "step": "finalize_bulk_ingest",
                "rows_by_table": dict(result_summary["rows_by_table"]),
            },
            emit_heartbeat=True,
        )

        if direct_persist:
            return JobResult(
                job_id=job.id,
                status="completed",
                target_table=TABLE_SEC_COMPANYFACTS,
                raw_payload=raw_payload,
                result_summary=result_summary,
            )

        return JobResult(
            job_id=job.id,
            status="completed",
            target_table=TABLE_SEC_COMPANYFACTS,
            collected_rows=companyfacts_rows,
            additional_targets=[
                {
                    "table_name": TABLE_SEC_SUBMISSIONS,
                    "rows": submissions_rows,
                    "source_url": submissions_archive["url"],
                }
            ],
            raw_payload=raw_payload,
            result_summary=result_summary,
        )

    def _request_headers(self) -> dict[str, str]:
        """Internal helper to request the headers."""
        return {
            "Accept": "application/zip, application/json;q=0.9, */*;q=0.8",
            "User-Agent": self.user_agent,
        }

    def _download_archive(
        self,
        url: str,
        dataset: str,
        *,
        current: int,
        total: int,
        percent_start: float,
        percent_end: float,
        table_name: str,
    ) -> dict[str, Any]:
        """Internal helper for download archive."""
        archive_path = self._archive_cache_path(dataset)
        cache_state = self._cache_state(archive_path)
        if cache_state["fresh"]:
            cache_age_hours = round(float(cache_state["age_hours"] or 0.0), 2)
            self._report_progress(
                phase="cached",
                message=f"Using cached {archive_path.name} from local SEC cache ({cache_age_hours:.2f}h old).",
                percent=percent_end,
                current=current,
                total=total,
                extra={
                    "job_kind": "us_filing_bulk",
                    "dataset": dataset,
                    "archive_file": archive_path.name,
                    "file_name": "",
                    "table_name": table_name,
                    "step": "use_cached_archive",
                    "source_url": url,
                    "local_path": str(archive_path),
                    "cache_status": "hit",
                    "cache_age_hours": cache_age_hours,
                },
                emit_heartbeat=True,
            )
            return {
                "path": str(archive_path),
                "url": url,
                "local_path": str(archive_path),
                "cache_status": "hit",
                "cache_age_hours": cache_age_hours,
            }

        cache_status = "stale" if cache_state["exists"] else "miss"
        cache_age_hours = round(float(cache_state["age_hours"] or 0.0), 2) if cache_state["exists"] else None
        response = self.request_get(
            url,
            headers=self._request_headers(),
            timeout=self.timeout_sec,
            stream=True,
        )
        try:
            raise_for_status = getattr(response, "raise_for_status", None)
            if callable(raise_for_status):
                raise_for_status()
            response_headers = getattr(response, "headers", {}) or {}
            try:
                total_bytes = max(int(response_headers.get("Content-Length") or 0), 0)
            except (TypeError, ValueError, AttributeError):
                total_bytes = 0
            if total_bytes > 0:
                self._report_progress(
                    phase="downloading",
                    message=_download_progress_message(archive_path.name, 0, total_bytes),
                    percent=percent_start,
                    current=0,
                    total=total_bytes,
                    extra={
                        "job_kind": "us_filing_bulk",
                        "dataset": dataset,
                        "archive_file": archive_path.name,
                        "file_name": "",
                        "table_name": table_name,
                        "step": "download_archive",
                        "source_url": url,
                        "local_path": str(archive_path),
                        "cache_status": cache_status,
                        "cache_age_hours": cache_age_hours,
                        "downloaded_bytes": 0,
                        "download_total_bytes": total_bytes,
                    },
                    emit_heartbeat=True,
                )
            with tempfile.NamedTemporaryFile(
                dir=str(self.cache_dir),
                prefix=f"{dataset}-",
                suffix=".zip.part",
                delete=False,
            ) as handle:
                wrote_any = False
                temp_path = Path(handle.name)
                downloaded_bytes = 0
                last_emitted_bytes = 0
                iter_content = getattr(response, "iter_content", None)
                if callable(iter_content):
                    for chunk in iter_content(chunk_size=ARCHIVE_CHUNK_SIZE):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        downloaded_bytes += len(chunk)
                        wrote_any = True
                        should_emit = _should_emit_download_heartbeat(
                            downloaded_bytes,
                            total_bytes or None,
                            last_emitted_bytes=last_emitted_bytes,
                        )
                        self._report_progress(
                            phase="downloading",
                            message=_download_progress_message(
                                archive_path.name,
                                downloaded_bytes,
                                total_bytes or None,
                            ),
                            percent=_progress_percent_float(
                                downloaded_bytes,
                                total_bytes or downloaded_bytes or 1,
                                start=percent_start,
                                end=percent_end,
                            ),
                            current=downloaded_bytes,
                            total=total_bytes or downloaded_bytes,
                            extra={
                                "job_kind": "us_filing_bulk",
                                "dataset": dataset,
                                "archive_file": archive_path.name,
                                "file_name": "",
                                "table_name": table_name,
                                "step": "download_archive",
                                "source_url": url,
                                "local_path": str(archive_path),
                                "cache_status": cache_status,
                                "cache_age_hours": cache_age_hours,
                                "downloaded_bytes": downloaded_bytes,
                                "download_total_bytes": total_bytes or None,
                            },
                            emit_heartbeat=should_emit,
                        )
                        if should_emit:
                            last_emitted_bytes = downloaded_bytes
                else:
                    payload = getattr(response, "content", b"")
                    if isinstance(payload, str):
                        payload = payload.encode("utf-8")
                    handle.write(payload)
                    downloaded_bytes = len(payload)
                    total_bytes = total_bytes or downloaded_bytes
                    wrote_any = bool(payload)
                    if wrote_any:
                        self._report_progress(
                            phase="downloading",
                            message=_download_progress_message(
                                archive_path.name,
                                downloaded_bytes,
                                total_bytes or None,
                            ),
                            percent=_progress_percent_float(
                                downloaded_bytes,
                                total_bytes or downloaded_bytes or 1,
                                start=percent_start,
                                end=percent_end,
                            ),
                            current=downloaded_bytes,
                            total=total_bytes or downloaded_bytes,
                            extra={
                                "job_kind": "us_filing_bulk",
                                "dataset": dataset,
                                "archive_file": archive_path.name,
                                "file_name": "",
                                "table_name": table_name,
                                "step": "download_archive",
                                "source_url": url,
                                "local_path": str(archive_path),
                                "cache_status": cache_status,
                                "cache_age_hours": cache_age_hours,
                                "downloaded_bytes": downloaded_bytes,
                                "download_total_bytes": total_bytes or None,
                            },
                            emit_heartbeat=True,
                        )
            if not wrote_any:
                raise RuntimeError(f"SEC archive download for '{dataset}' returned no content.")
            temp_path.replace(archive_path)
            return {
                "path": str(archive_path),
                "url": str(getattr(response, "url", "") or url),
                "local_path": str(archive_path),
                "cache_status": cache_status,
                "cache_age_hours": 0.0,
            }
        finally:
            close = getattr(response, "close", None)
            if callable(close):
                close()

    def _archive_cache_path(self, dataset: str) -> Path:
        """Internal helper to return the archive cache path."""
        return self.cache_dir / f"{str(dataset or '').strip()}.zip"

    def _cache_state(self, archive_path: Path) -> dict[str, Any]:
        """Internal helper to return the cache state."""
        if not archive_path.exists() or not archive_path.is_file():
            return {
                "exists": False,
                "fresh": False,
                "age_hours": None,
            }
        modified_at = datetime.fromtimestamp(archive_path.stat().st_mtime, tz=timezone.utc)
        age_sec = max((datetime.now(timezone.utc) - modified_at).total_seconds(), 0.0)
        return {
            "exists": True,
            "fresh": age_sec <= self.cache_max_age_sec,
            "age_hours": age_sec / 3600.0,
        }

    def _ensure_cache_dir(self) -> Path:
        """Internal helper to ensure the cache dir exists."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir

    def _walk_companyfacts_archive(
        self,
        archive_path: Path,
        *,
        job: JobDetail,
        source_url: str,
        consumer: Callable[[dict[str, Any], int, int], None],
    ) -> dict[str, int]:
        """Internal helper for walk companyfacts archive."""
        file_count = 0
        row_count = 0
        with zipfile.ZipFile(archive_path) as archive:
            entries = [
                info
                for info in archive.infolist()
                if not info.is_dir() and Path(info.filename).name.lower().endswith(".json")
            ]
            file_count = len(entries)
            for index, info in enumerate(entries, start=1):
                self._raise_if_stop_requested(job)
                file_name = Path(info.filename).name
                self._report_progress(
                    phase="extracting",
                    message=f"Extracting {archive_path.name}: {file_name} ({index}/{file_count}).",
                    percent=_progress_percent(index, file_count, start=5, end=52),
                    current=index,
                    total=file_count,
                    extra={
                        "job_kind": "us_filing_bulk",
                        "dataset": "companyfacts",
                        "archive_file": archive_path.name,
                        "file_name": file_name,
                        "table_name": TABLE_SEC_COMPANYFACTS,
                        "step": "extract_file",
                        "source_url": source_url,
                    },
                    emit_heartbeat=_should_emit_file_heartbeat(index, file_count),
                )
                with archive.open(info) as handle:
                    payload = json.loads(handle.read().decode("utf-8"))
                row = self._build_companyfacts_row(payload, file_name=file_name, source_url=source_url)
                if row is None:
                    continue
                consumer(row, index, file_count)
                row_count += 1
        return {
            "file_count": file_count,
            "row_count": row_count,
        }

    def _walk_submissions_archive(
        self,
        archive_path: Path,
        *,
        job: JobDetail,
        source_url: str,
        consumer: Callable[[dict[str, Any], int, int], None],
    ) -> dict[str, int]:
        """Internal helper for walk submissions archive."""
        file_count = 0
        row_count = 0
        primary_rows = 0
        supplemental_rows = 0
        with zipfile.ZipFile(archive_path) as archive:
            entries = [
                info
                for info in archive.infolist()
                if not info.is_dir() and Path(info.filename).name.lower().endswith(".json")
            ]
            file_count = len(entries)
            for index, info in enumerate(entries, start=1):
                self._raise_if_stop_requested(job)
                file_name = Path(info.filename).name
                self._report_progress(
                    phase="extracting",
                    message=f"Extracting {archive_path.name}: {file_name} ({index}/{file_count}).",
                    percent=_progress_percent(index, file_count, start=60, end=96),
                    current=index,
                    total=file_count,
                    extra={
                        "job_kind": "us_filing_bulk",
                        "dataset": "submissions",
                        "archive_file": archive_path.name,
                        "file_name": file_name,
                        "table_name": TABLE_SEC_SUBMISSIONS,
                        "step": "extract_file",
                        "source_url": source_url,
                    },
                    emit_heartbeat=_should_emit_file_heartbeat(index, file_count),
                )
                with archive.open(info) as handle:
                    payload = json.loads(handle.read().decode("utf-8"))
                row = self._build_submission_row(payload, file_name=file_name, source_url=source_url)
                if row is None:
                    continue
                consumer(row, index, file_count)
                row_count += 1
                if _coerce_bool(row.get("is_primary")):
                    primary_rows += 1
                else:
                    supplemental_rows += 1
        return {
            "file_count": file_count,
            "row_count": row_count,
            "primary_rows": primary_rows,
            "supplemental_rows": supplemental_rows,
        }

    def _build_companyfacts_row(
        self,
        payload: Mapping[str, Any],
        *,
        file_name: str,
        source_url: str,
    ) -> dict[str, Any] | None:
        """Internal helper to build the companyfacts row."""
        cik = _normalize_cik(payload.get("cik"))
        if not cik:
            match = COMPANYFACTS_FILENAME_RE.match(file_name)
            cik = match.group(1) if match else ""
        if not cik:
            return None
        return {
            "id": _sec_row_id("ads-sec-companyfacts", cik),
            "cik": cik,
            "entity_name": str(payload.get("entityName") or "").strip(),
            "file_name": file_name,
            "fact_count": _count_companyfacts(payload),
            "source_url": source_url,
            "provider": self.provider,
            "payload": dict(payload),
        }

    def _build_submission_row(
        self,
        payload: Mapping[str, Any],
        *,
        file_name: str,
        source_url: str,
    ) -> dict[str, Any] | None:
        """Internal helper to build the submission row."""
        cik = _normalize_cik(payload.get("cik"))
        if not cik:
            primary_match = PRIMARY_SUBMISSIONS_FILENAME_RE.match(file_name)
            if primary_match:
                cik = file_name[3:13]
            else:
                supplemental_match = SUPPLEMENTAL_SUBMISSIONS_FILENAME_RE.match(file_name)
                cik = supplemental_match.group(1) if supplemental_match else ""
        if not cik:
            return None

        tickers = _string_list(payload.get("tickers"))
        exchanges = _string_list(payload.get("exchanges"))
        is_primary = _is_primary_submission_file(file_name)
        return {
            "id": _sec_row_id("ads-sec-submissions", cik, file_name),
            "cik": cik,
            "entity_name": str(payload.get("name") or payload.get("entityName") or "").strip(),
            "symbol": normalize_symbol(_first_submission_symbol(payload)),
            "symbols": tickers,
            "exchanges": exchanges,
            "file_name": file_name,
            "is_primary": is_primary,
            "filing_count": _count_submission_filings(payload),
            "source_url": source_url,
            "provider": self.provider,
            "payload": dict(payload),
        }

    def _persist_rows(self, table_name: str, rows: list[dict[str, Any]], *, source_url: str) -> int:
        """Internal helper to persist the rows."""
        worker_pool = self._pool()
        if worker_pool is None or not rows:
            return 0
        from ads.runtime import prepare_table_records

        prepared = prepare_table_records(table_name, rows, source_url=source_url, provider=self.provider)
        if not worker_pool._InsertMany(table_name, prepared):
            raise RuntimeError(f"Failed to persist SEC bulk rows into '{table_name}'.")
        return len(prepared)

    def _pool(self) -> Any:
        """Internal helper for pool."""
        worker = getattr(self, "worker", None)
        return getattr(worker, "pool", None)

    def _raise_if_stop_requested(self, job: JobDetail) -> None:
        """Internal helper for raise if stop requested."""
        _raise_if_stop_requested(getattr(self, "worker", None), job)

    def _report_progress(
        self,
        *,
        phase: str,
        message: str,
        percent: Any = None,
        current: Any = None,
        total: Any = None,
        extra: Mapping[str, Any] | None = None,
        emit_heartbeat: bool = False,
    ) -> dict[str, Any]:
        """Internal helper to report the progress."""
        return _report_worker_progress(
            getattr(self, "worker", None),
            phase=phase,
            message=message,
            percent=percent,
            current=current,
            total=total,
            extra=extra,
            emit_heartbeat=emit_heartbeat,
        )

    def _report_insert_progress(
        self,
        *,
        dataset: str,
        row: Mapping[str, Any],
        current: int,
        total: int,
        table_name: str,
        percent_start: float,
        percent_end: float,
    ) -> None:
        """Internal helper to report the insert progress."""
        progress_current = max(int(current or 0), 1)
        progress_total = max(int(total or 0), 1)
        progress_label = _row_progress_label(row, fallback=dataset)
        self._report_progress(
            phase="persisting",
            message=f"{progress_current}/{progress_total} inserting {dataset}.",
            percent=_progress_percent(progress_current, progress_total, start=percent_start, end=percent_end),
            current=progress_current,
            total=progress_total,
            extra={
                "job_kind": "us_filing_bulk",
                "dataset": dataset,
                "archive_file": f"{dataset}.zip",
                "file_name": str(row.get("file_name") or "").strip(),
                "table_name": table_name,
                "step": "insert_row",
                "entity_name": str(row.get("entity_name") or "").strip(),
                "cik": _normalize_cik(row.get("cik")),
                "symbol": normalize_symbol(row.get("symbol")),
            },
            emit_heartbeat=_should_emit_file_heartbeat(progress_current, progress_total),
        )
        logger = getattr(getattr(self, "worker", None), "logger", None)
        debug = getattr(logger, "debug", None)
        if callable(debug):
            debug("%s/%s %s", progress_current, progress_total, progress_label)


class USFilingMappingJobCap(JobCap):
    """Job capability implementation for US filing mapping workflows."""
    DEFAULT_NAME = "US Filing Mapping"

    def __init__(
        self,
        name: str = DEFAULT_NAME,
        *,
        provider: str = SEC_PROVIDER,
        dispatcher_address: str = "",
        source: str = "",
    ):
        """Initialize the US filing mapping job cap."""
        super().__init__(
            name=name,
            source=source or f"{self.__class__.__module__}:{self.__class__.__name__}",
        )
        self.provider = normalize_provider(provider or SEC_PROVIDER) or SEC_PROVIDER
        self.dispatcher_address = str(dispatcher_address or "").strip()

    def check_environment(self) -> tuple[bool, str]:
        """Handle check environment for the US filing mapping job cap."""
        return True, ""

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the US filing mapping job cap."""
        payload = job.payload if isinstance(job.payload, Mapping) else {}
        requested_cik = _normalize_cik(payload.get("cik"))
        requested_symbol = normalize_symbol(payload.get("symbol") or (job.symbols[0] if job.symbols else ""))
        requested_label = _company_progress_label(cik=requested_cik, symbol=requested_symbol)
        self._raise_if_stop_requested(job)
        self._report_progress(
            phase="loading_raw",
            message=f"Loading SEC raw rows for {requested_label}.",
            percent=10,
            current=1,
            total=4,
            extra={
                "job_kind": "us_filing_mapping",
                "cik": requested_cik,
                "symbol": requested_symbol,
                "sub_job": "",
                "step": "load_raw_rows",
            },
            emit_heartbeat=True,
        )
        resolved = self._resolve_company_context(job)
        cik = resolved["cik"]
        if not cik:
            self._report_progress(
                phase="failed",
                message="US filing mapping requires a CIK or symbol.",
                percent=10,
                current=1,
                total=4,
                extra={
                    "job_kind": "us_filing_mapping",
                    "cik": requested_cik,
                    "symbol": requested_symbol,
                    "sub_job": "",
                    "step": "load_raw_rows",
                },
                emit_heartbeat=True,
            )
            raise ValueError("USFilingMappingJobCap requires a cik or symbol.")

        submissions_row = resolved["submission_row"]
        companyfacts_row = resolved["companyfacts_row"]
        if submissions_row is None or companyfacts_row is None:
            label = _company_progress_label(cik=cik, symbol=requested_symbol)
            result_summary = {
                "provider": self.provider,
                "cik": cik,
                "rows": 0,
                "skipped": True,
                "reason": "missing_raw_sec_rows",
                "has_companyfacts": companyfacts_row is not None,
                "has_submissions": submissions_row is not None,
            }
            self._report_progress(
                phase="mapping",
                message=f"Skipping SEC mapping for {label} because raw SEC rows are missing.",
                percent=100,
                current=4,
                total=4,
                extra={
                    "job_kind": "us_filing_mapping",
                    "cik": cik,
                    "symbol": requested_symbol,
                    "sub_job": "",
                    "step": "skip_missing_raw_rows",
                    "skip_reason": "missing_raw_sec_rows",
                },
                emit_heartbeat=True,
            )
            return JobResult(
                job_id=job.id,
                status="completed",
                raw_payload=result_summary,
                result_summary=result_summary,
            )

        submissions_payload = submissions_row.get("payload") if isinstance(submissions_row.get("payload"), Mapping) else {}
        companyfacts_payload = companyfacts_row.get("payload") if isinstance(companyfacts_row.get("payload"), Mapping) else {}
        symbol = normalize_symbol(
            submissions_row.get("symbol")
            or _first_submission_symbol(submissions_payload)
            or (job.payload or {}).get("symbol")
            or (job.symbols[0] if job.symbols else "")
        )
        if not symbol:
            label = _company_progress_label(cik=cik, symbol="")
            result_summary = {
                "provider": self.provider,
                "cik": cik,
                "rows": 0,
                "skipped": True,
                "reason": "missing_symbol",
            }
            self._report_progress(
                phase="mapping",
                message=f"Skipping SEC mapping for {label} because no symbol is present in SEC submissions.",
                percent=100,
                current=4,
                total=4,
                extra={
                    "job_kind": "us_filing_mapping",
                    "cik": cik,
                    "symbol": "",
                    "sub_job": "",
                    "step": "skip_missing_symbol",
                    "skip_reason": "missing_symbol",
                },
                emit_heartbeat=True,
            )
            return JobResult(
                job_id=job.id,
                status="completed",
                raw_payload=result_summary,
                result_summary=result_summary,
            )

        label = _company_progress_label(cik=cik, symbol=symbol)
        self._raise_if_stop_requested(job)
        self._report_progress(
            phase="mapping",
            message=f"Mapping fundamentals for {label}.",
            percent=40,
            current=2,
            total=4,
            extra={
                "job_kind": "us_filing_mapping",
                "cik": cik,
                "symbol": symbol,
                "sub_job": "fundamentals",
                "step": "map_fundamentals",
            },
            emit_heartbeat=True,
        )
        fundamental_row = self._build_fundamental_row(
            cik=cik,
            symbol=symbol,
            companyfacts_payload=companyfacts_payload,
            submissions_payload=submissions_payload,
        )
        self._raise_if_stop_requested(job)
        self._report_progress(
            phase="mapping",
            message=f"Mapping financial statements for {label}.",
            percent=70,
            current=3,
            total=4,
            extra={
                "job_kind": "us_filing_mapping",
                "cik": cik,
                "symbol": symbol,
                "sub_job": "financial_statements",
                "step": "map_financial_statements",
            },
            emit_heartbeat=True,
        )
        financial_statement_rows = self._build_financial_statement_rows(
            cik=cik,
            symbol=symbol,
            companyfacts_payload=companyfacts_payload,
            submissions_payload=submissions_payload,
        )
        raw_payload = {
            "provider": self.provider,
            "cik": cik,
            "symbol": symbol,
            "companyfacts_row_id": str(companyfacts_row.get("id") or ""),
            "submissions_row_id": str(submissions_row.get("id") or ""),
            "financial_statement_rows": len(financial_statement_rows),
        }
        result_summary = {
            "provider": self.provider,
            "cik": cik,
            "symbol": symbol,
            "rows": 1 + len(financial_statement_rows),
            "fundamental_rows": 1,
            "financial_statement_rows": len(financial_statement_rows),
            "statement_types": sorted(
                {
                    str(row.get("statement_type") or "").strip()
                    for row in financial_statement_rows
                    if str(row.get("statement_type") or "").strip()
                }
            ),
        }
        self._report_progress(
            phase="finalizing",
            message=(
                f"Prepared SEC mappings for {label}: "
                f"1 fundamentals row and {len(financial_statement_rows)} financial statement rows."
            ),
            percent=95,
            current=4,
            total=4,
            extra={
                "job_kind": "us_filing_mapping",
                "cik": cik,
                "symbol": symbol,
                "sub_job": "",
                "step": "finalize_mapping",
                "financial_statement_rows": len(financial_statement_rows),
            },
            emit_heartbeat=True,
        )
        return JobResult(
            job_id=job.id,
            status="completed",
            target_table=TABLE_FUNDAMENTALS,
            collected_rows=[fundamental_row],
            additional_targets=[
                {
                    "table_name": TABLE_FINANCIAL_STATEMENTS,
                    "rows": financial_statement_rows,
                }
            ],
            raw_payload=raw_payload,
            result_summary=result_summary,
        )

    def _resolve_company_context(self, job: JobDetail) -> dict[str, Any]:
        """Internal helper to resolve the company context."""
        payload = job.payload if isinstance(job.payload, Mapping) else {}
        cik = _normalize_cik(payload.get("cik"))
        symbol = normalize_symbol(payload.get("symbol") or (job.symbols[0] if job.symbols else ""))

        submission_rows: list[dict[str, Any]] = []
        if cik:
            submission_rows = self._read_rows(TABLE_SEC_SUBMISSIONS, {"cik": cik})
        elif symbol:
            submission_rows = self._read_rows(TABLE_SEC_SUBMISSIONS, {"symbol": symbol})
            selected = self._select_primary_submission_row(submission_rows)
            if selected is not None:
                cik = _normalize_cik(selected.get("cik"))
        submission_row = self._select_primary_submission_row(submission_rows)
        companyfacts_rows = self._read_rows(TABLE_SEC_COMPANYFACTS, {"cik": cik}) if cik else []
        companyfacts_row = companyfacts_rows[0] if companyfacts_rows else None
        return {
            "cik": cik,
            "submission_row": submission_row,
            "companyfacts_row": companyfacts_row,
        }

    def _resolve_dispatcher_address(self) -> str:
        """Internal helper to resolve the dispatcher address."""
        worker = getattr(self, "worker", None)
        return self.dispatcher_address or str(getattr(worker, "dispatcher_address", "") or "").strip()

    def _read_rows(self, table_name: str, where: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Internal helper to read the rows."""
        worker = getattr(self, "worker", None)
        if worker is None:
            return []
        schema = ads_table_schema_map().get(table_name)
        dispatcher_address = self._resolve_dispatcher_address()
        rows: Any = []
        if dispatcher_address:
            rows = worker.UsePractice(
                "pool-get-table-data",
                {
                    "table_name": table_name,
                    "id_or_where": dict(where),
                    "table_schema": dict(schema.schema) if schema is not None else {},
                },
                pit_address=dispatcher_address,
            )
        elif getattr(worker, "pool", None) is not None:
            rows = worker.pool._GetTableData(table_name, dict(where), table_schema=schema)
        if not isinstance(rows, list):
            return []
        return [dict(row) for row in rows if isinstance(row, Mapping)]

    @staticmethod
    def _select_primary_submission_row(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
        """Internal helper to return the select primary submission row."""
        if not rows:
            return None
        sorted_rows = sorted(
            (dict(row) for row in rows if isinstance(row, Mapping)),
            key=lambda row: (
                1 if _coerce_bool(row.get("is_primary")) else 0,
                1 if normalize_symbol(row.get("symbol")) else 0,
                str(row.get("file_name") or ""),
            ),
            reverse=True,
        )
        return sorted_rows[0] if sorted_rows else None

    def _build_fundamental_row(
        self,
        *,
        cik: str,
        symbol: str,
        companyfacts_payload: Mapping[str, Any],
        submissions_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Internal helper to build the fundamental row."""
        facts = companyfacts_payload.get("facts") if isinstance(companyfacts_payload.get("facts"), Mapping) else {}
        recent_filings = _recent_filings_from_submission(submissions_payload)
        latest_filing = recent_filings[0] if recent_filings else {}
        latest_annual_report = next(
            (
                row
                for row in recent_filings
                if str(row.get("form") or "").strip().upper() in {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}
            ),
            {},
        )
        latest_quarterly_report = next(
            (
                row
                for row in recent_filings
                if str(row.get("form") or "").strip().upper() in {"10-Q", "10-Q/A"}
            ),
            {},
        )

        latest_facts: dict[str, dict[str, Any]] = {}
        for metric_name, concept_refs in LATEST_FACT_METRICS.items():
            preferred_units = METRIC_UNIT_PREFERENCES.get(metric_name, ())
            latest_facts[metric_name] = _fact_snapshot(
                _latest_fact_entry(
                    facts,
                    concept_refs,
                    preferred_units=preferred_units,
                    allowed_forms=SUPPORTED_STATEMENT_FORMS,
                )
            )

        as_of_date = (
            str(latest_filing.get("filingDate") or "").strip()
            or str(latest_facts.get("shares_outstanding", {}).get("filed") or "").strip()
            or str(latest_facts.get("revenue", {}).get("filed") or "").strip()
            or str(latest_facts.get("assets", {}).get("filed") or "").strip()
            or str(latest_facts.get("shares_outstanding", {}).get("end") or "").strip()
            or str(latest_facts.get("revenue", {}).get("end") or "").strip()
            or str(latest_facts.get("assets", {}).get("end") or "").strip()
        )

        return {
            "id": _sec_row_id("ads-fundamental", symbol, self.provider),
            "symbol": symbol,
            "as_of_date": as_of_date,
            "market_cap": None,
            "pe_ratio": None,
            "dividend_yield": None,
            "sector": _sector_from_owner_org(submissions_payload.get("ownerOrg")),
            "industry": str(submissions_payload.get("sicDescription") or "").strip(),
            "provider": self.provider,
            "data": {
                "cik": cik,
                "entity_name": str(submissions_payload.get("name") or companyfacts_payload.get("entityName") or "").strip(),
                "entity_type": str(submissions_payload.get("entityType") or "").strip(),
                "sic": str(submissions_payload.get("sic") or "").strip(),
                "sic_description": str(submissions_payload.get("sicDescription") or "").strip(),
                "owner_org": str(submissions_payload.get("ownerOrg") or "").strip(),
                "category": str(submissions_payload.get("category") or "").strip(),
                "fiscal_year_end": str(submissions_payload.get("fiscalYearEnd") or "").strip(),
                "state_of_incorporation": str(submissions_payload.get("stateOfIncorporation") or "").strip(),
                "website": str(submissions_payload.get("website") or "").strip(),
                "investor_website": str(submissions_payload.get("investorWebsite") or "").strip(),
                "phone": str(submissions_payload.get("phone") or "").strip(),
                "tickers": _string_list(submissions_payload.get("tickers")),
                "exchanges": _string_list(submissions_payload.get("exchanges")),
                "latest_filing": dict(latest_filing or {}),
                "latest_annual_report": dict(latest_annual_report or {}),
                "latest_quarterly_report": dict(latest_quarterly_report or {}),
                "latest_facts": latest_facts,
                "former_names": list(submissions_payload.get("formerNames") or []),
                "flags": str(submissions_payload.get("flags") or "").strip(),
            },
        }

    def _build_financial_statement_rows(
        self,
        *,
        cik: str,
        symbol: str,
        companyfacts_payload: Mapping[str, Any],
        submissions_payload: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        """Internal helper to build the financial statement rows."""
        facts = companyfacts_payload.get("facts") if isinstance(companyfacts_payload.get("facts"), Mapping) else {}
        recent_lookup = _recent_filing_lookup_by_accession(submissions_payload)
        entity_name = str(submissions_payload.get("name") or companyfacts_payload.get("entityName") or "").strip()
        rows: list[dict[str, Any]] = []

        for statement_type, metric_map in STATEMENT_METRIC_CONCEPTS.items():
            rows_by_key: dict[str, dict[str, Any]] = {}
            for metric_name, concept_refs in metric_map.items():
                preferred_units = METRIC_UNIT_PREFERENCES.get(metric_name, ("USD",))
                for entry in _iter_matching_fact_entries(
                    facts,
                    concept_refs,
                    preferred_units=preferred_units,
                    allowed_forms=SUPPORTED_STATEMENT_FORMS,
                ):
                    period_end = str(entry.get("end") or "").strip()
                    accession = str(entry.get("accn") or "").strip()
                    if not period_end and not accession:
                        continue
                    row_key = accession or f"{statement_type}:{period_end}:{entry.get('fy')}:{entry.get('fp')}:{entry.get('form')}"
                    filing_row = recent_lookup.get(accession) or {}
                    statement_row = rows_by_key.get(row_key)
                    if statement_row is None:
                        filing_url = _build_filing_url(
                            cik,
                            accession,
                            filing_row.get("primaryDocument"),
                        )
                        statement_row = {
                            "id": _sec_row_id("ads-financial-statement", symbol, statement_type, row_key),
                            "symbol": symbol,
                            "statement_type": statement_type,
                            "period_end": period_end,
                            "fiscal_period": _format_fiscal_period(entry),
                            "currency": _normalize_currency_from_unit(entry.get("_unit")),
                            "provider": self.provider,
                            "data": {
                                "cik": cik,
                                "entity_name": entity_name,
                                "accn": accession,
                                "fy": _coerce_int(entry.get("fy")),
                                "fp": str(entry.get("fp") or "").strip(),
                                "form": str(entry.get("form") or "").strip(),
                                "filed": str(entry.get("filed") or "").strip(),
                                "start": str(entry.get("start") or "").strip(),
                                "end": period_end,
                                "frame": str(entry.get("frame") or "").strip(),
                                "filing_url": filing_url,
                                "recent_filing": dict(filing_row or {}),
                                "source_concepts": {},
                                "fact_metadata": {},
                            },
                        }
                        rows_by_key[row_key] = statement_row

                    if not statement_row.get("currency"):
                        statement_row["currency"] = _normalize_currency_from_unit(entry.get("_unit"))
                    statement_row["data"][metric_name] = _coerce_number(entry.get("val"))
                    statement_row["data"]["source_concepts"][metric_name] = {
                        "taxonomy": str(entry.get("_taxonomy") or "").strip(),
                        "concept": str(entry.get("_concept") or "").strip(),
                        "unit": str(entry.get("_unit") or "").strip(),
                    }
                    statement_row["data"]["fact_metadata"][metric_name] = {
                        "accn": accession,
                        "filed": str(entry.get("filed") or "").strip(),
                        "start": str(entry.get("start") or "").strip(),
                        "end": period_end,
                        "form": str(entry.get("form") or "").strip(),
                        "frame": str(entry.get("frame") or "").strip(),
                    }

            rows.extend(rows_by_key.values())

        rows.sort(key=_statement_row_sort_key, reverse=True)
        return rows

    def _raise_if_stop_requested(self, job: JobDetail) -> None:
        """Internal helper for raise if stop requested."""
        _raise_if_stop_requested(getattr(self, "worker", None), job)

    def _report_progress(
        self,
        *,
        phase: str,
        message: str,
        percent: Any = None,
        current: Any = None,
        total: Any = None,
        extra: Mapping[str, Any] | None = None,
        emit_heartbeat: bool = False,
    ) -> dict[str, Any]:
        """Internal helper to report the progress."""
        return _report_worker_progress(
            getattr(self, "worker", None),
            phase=phase,
            message=message,
            percent=percent,
            current=current,
            total=total,
            extra=extra,
            emit_heartbeat=emit_heartbeat,
        )


USFillingMappingJobCap = USFilingMappingJobCap
