"""
Runtime helpers for `ads.runtime`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace.

Important callables in this file include `build_collection_job`, `build_daily_price_id`,
`build_id`, `build_worker_history_entry`, and `build_worker_registration`, which capture
the primary workflow implemented by the module.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from ads.models import JobDetail, JobResult
from ads.schema import TABLE_DAILY_PRICE


ConfigInput = str | Path | Mapping[str, Any] | None


def read_ads_config(config: ConfigInput) -> Dict[str, Any]:
    """Read the ADS config."""
    if config is None:
        return {}
    if isinstance(config, Mapping):
        return dict(config)
    path = Path(config)
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    return payload if isinstance(payload, dict) else {}


def utcnow_iso() -> str:
    """Handle utcnow iso."""
    return datetime.now(timezone.utc).isoformat()


def build_id(prefix: str) -> str:
    """Build the ID."""
    normalized = "-".join(part for part in str(prefix or "").split() if part).lower() or "ads"
    return f"{normalized}:{uuid.uuid4()}"


def normalize_string_list(values: Any) -> List[str]:
    """Normalize the string list."""
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = [part.strip() for part in values.split(",")]
    elif isinstance(values, Sequence) and not isinstance(values, (bytes, bytearray)):
        raw_values = [str(item).strip() for item in values]
    else:
        raw_values = [str(values).strip()]

    seen = set()
    normalized: List[str] = []
    for value in raw_values:
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def normalize_symbol(value: Any) -> str:
    """Normalize the symbol."""
    return str(value or "").strip().upper()


def normalize_provider(value: Any) -> str:
    """Normalize the provider."""
    return str(value or "").strip().lower()


def build_daily_price_id(symbol: Any, trade_date: Any, provider: Any) -> str:
    """Build the daily price ID."""
    normalized_symbol = normalize_symbol(symbol)
    normalized_trade_date = str(trade_date or "").strip()
    normalized_provider = normalize_provider(provider)
    return f"ads-daily-price:{normalized_symbol}:{normalized_trade_date}:{normalized_provider}"


def parse_datetime_value(value: Any) -> datetime:
    """Parse the datetime value."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def normalize_capabilities(values: Any) -> List[str]:
    """Normalize the capabilities."""
    capabilities: List[str] = []
    for entry in normalize_string_list(values):
        lowered = entry.strip().lower()
        if lowered and lowered not in capabilities:
            capabilities.append(lowered)
    return capabilities


def coerce_json_object(value: Any) -> Dict[str, Any]:
    """Coerce the JSON object."""
    return dict(value) if isinstance(value, Mapping) else {}


def coerce_json_payload(value: Any) -> Any:
    """Coerce the JSON payload."""
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, list):
        return list(value)
    if value is None:
        return {}
    return {"value": value}


def coerce_record_list(value: Any) -> List[Dict[str, Any]]:
    """Coerce the record list."""
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def coerce_job_detail(value: Mapping[str, Any] | JobDetail | None) -> JobDetail | None:
    """Coerce the job detail."""
    if value is None:
        return None
    return JobDetail.from_row(value)


def coerce_job_result(value: Mapping[str, Any] | JobResult | None, *, job_id: str = "", worker_id: str = "") -> JobResult:
    """Coerce the job result."""
    return JobResult.from_value(value).with_defaults(job_id=job_id, worker_id=worker_id)


def _job_data(job: Mapping[str, Any] | JobDetail) -> Dict[str, Any]:
    """Internal helper for job data."""
    if isinstance(job, JobDetail):
        return job.to_row()
    return dict(job)


def job_is_ready(job: Mapping[str, Any] | JobDetail, *, now: datetime | None = None) -> bool:
    """Return whether the job is ready."""
    job_data = _job_data(job)
    status = str(job_data.get("status") or "").strip().lower()
    if status not in {"queued", "retry", "unfinished"}:
        return False

    scheduled_for = parse_datetime_value(job_data.get("scheduled_for"))
    compare_at = now or datetime.now(timezone.utc)
    if scheduled_for > compare_at:
        return False

    try:
        attempts = int(job_data.get("attempts") or 0)
    except (TypeError, ValueError):
        attempts = 0
    try:
        max_attempts = int(job_data.get("max_attempts") or 1)
    except (TypeError, ValueError):
        max_attempts = 1
    return attempts < max(max_attempts, 1)


def job_matches_capabilities(job: Mapping[str, Any] | JobDetail, capabilities: Any) -> bool:
    """Return whether the job matches capabilities."""
    job_data = _job_data(job)
    normalized_capabilities = normalize_capabilities(capabilities)
    if "*" in normalized_capabilities:
        return True

    required_capability = str(job_data.get("required_capability") or "").strip().lower()
    if required_capability and required_capability in normalized_capabilities:
        return True

    required_tags = normalize_capabilities(job_data.get("capability_tags"))
    if required_tags and set(required_tags).intersection(normalized_capabilities):
        return True

    return not required_capability and not required_tags


def job_sort_key(job: Mapping[str, Any] | JobDetail) -> tuple[int, datetime, str]:
    """Return the job sort key."""
    job_data = _job_data(job)
    try:
        priority = int(job_data.get("priority") or 100)
    except (TypeError, ValueError):
        priority = 100
    created_at = parse_datetime_value(job_data.get("created_at"))
    return priority, created_at, str(job_data.get("id") or "")


def build_collection_job(
    *,
    required_capability: str,
    payload: Any = None,
    target_table: str = "",
    source_url: str = "",
    parse_rules: Any = None,
    symbols: Any = None,
    capability_tags: Any = None,
    job_type: str = "collect",
    priority: int = 100,
    premium: bool = False,
    metadata: Any = None,
    scheduled_for: Any = None,
    max_attempts: int = 3,
    job_id: str | None = None,
) -> JobDetail:
    """Build the collection job."""
    now = utcnow_iso()
    try:
        normalized_priority = int(priority)
    except (TypeError, ValueError):
        normalized_priority = 100
    try:
        normalized_max_attempts = max(int(max_attempts), 1)
    except (TypeError, ValueError):
        normalized_max_attempts = 3

    return JobDetail.model_validate({
        "id": str(job_id or build_id("ads-job")),
        "job_type": str(job_type or "collect"),
        "status": "queued",
        "required_capability": str(required_capability or "").strip().lower(),
        "capability_tags": normalize_capabilities(capability_tags),
        "symbols": [normalize_symbol(symbol) for symbol in normalize_string_list(symbols)],
        "payload": coerce_json_payload(payload),
        "target_table": str(target_table or "").strip(),
        "source_url": str(source_url or "").strip(),
        "parse_rules": coerce_json_payload(parse_rules),
        "priority": normalized_priority,
        "premium": bool(premium),
        "metadata": coerce_json_object(metadata),
        "scheduled_for": str(scheduled_for or now),
        "claimed_by": "",
        "claimed_at": "",
        "completed_at": "",
        "result_summary": {},
        "error": "",
        "attempts": 0,
        "max_attempts": normalized_max_attempts,
        "created_at": now,
        "updated_at": now,
    })


def build_worker_registration(
    *,
    worker_id: str,
    name: str = "",
    address: str = "",
    capabilities: Any = None,
    metadata: Any = None,
    plaza_url: str = "",
    status: str = "online",
) -> Dict[str, Any]:
    """Build the worker registration."""
    now = utcnow_iso()
    normalized_worker_id = str(worker_id or "").strip() or build_id("ads-worker")
    return {
        "id": normalized_worker_id,
        "worker_id": normalized_worker_id,
        "name": str(name or normalized_worker_id),
        "address": str(address or "").strip(),
        "capabilities": normalize_capabilities(capabilities),
        "metadata": coerce_json_object(metadata),
        "plaza_url": str(plaza_url or "").strip(),
        "status": str(status or "online"),
        "last_seen_at": now,
        "updated_at": now,
    }


def build_worker_history_entry(
    *,
    worker_id: str,
    name: str = "",
    address: str = "",
    capabilities: Any = None,
    metadata: Any = None,
    plaza_url: str = "",
    status: str = "online",
    event_type: str = "heartbeat",
    session_started_at: Any = None,
    active_job_id: str = "",
    active_job_status: str = "",
    progress: Any = None,
    environment: Any = None,
    captured_at: Any = None,
) -> Dict[str, Any]:
    """Build the worker history entry."""
    normalized_captured_at = str(captured_at or utcnow_iso()).strip() or utcnow_iso()
    normalized_session_started_at = (
        str(session_started_at or normalized_captured_at).strip() or normalized_captured_at
    )
    normalized_worker_id = str(worker_id or "").strip() or build_id("ads-worker")
    return {
        "id": build_id("ads-worker-history"),
        "worker_id": normalized_worker_id,
        "name": str(name or normalized_worker_id).strip() or normalized_worker_id,
        "address": str(address or "").strip(),
        "capabilities": normalize_capabilities(capabilities),
        "plaza_url": str(plaza_url or "").strip(),
        "status": str(status or "online").strip().lower() or "online",
        "event_type": str(event_type or "heartbeat").strip().lower() or "heartbeat",
        "session_started_at": normalized_session_started_at,
        "active_job_id": str(active_job_id or "").strip(),
        "active_job_status": str(active_job_status or "").strip().lower(),
        "progress": coerce_json_payload(progress),
        "environment": coerce_json_object(environment),
        "metadata": coerce_json_object(metadata),
        "captured_at": normalized_captured_at,
    }


def prepare_table_records(table_name: str, rows: Any, *, source_url: str = "", provider: str = "ads") -> List[Dict[str, Any]]:
    """Prepare the table records."""
    prepared: List[Dict[str, Any]] = []
    now = utcnow_iso()
    for row in coerce_record_list(rows):
        record = dict(row)
        if "symbol" in record:
            record["symbol"] = normalize_symbol(record.get("symbol"))
        if "trade_date" not in record and record.get("date"):
            record["trade_date"] = str(record.get("date"))
        if "as_of_date" not in record and record.get("date"):
            record["as_of_date"] = str(record.get("date"))
        if "published_at" not in record and record.get("timestamp"):
            record["published_at"] = str(record.get("timestamp"))
        if table_name == TABLE_DAILY_PRICE:
            normalized_provider = normalize_provider(record.get("provider") or provider)
            record["provider"] = normalized_provider
            if not record.get("symbol") or not record.get("trade_date") or not normalized_provider:
                raise ValueError("ads_daily_price rows require symbol, trade_date, and provider.")
            record["id"] = build_daily_price_id(
                record.get("symbol"),
                record.get("trade_date"),
                normalized_provider,
            )
        else:
            record.setdefault("id", build_id(table_name.rstrip("s") or "ads-row"))
        if "source_url" in record:
            record.setdefault("source_url", source_url)
        if "provider" in record:
            record.setdefault("provider", provider)
        record.setdefault("created_at", now)
        record["updated_at"] = now
        prepared.append(record)
    return prepared
