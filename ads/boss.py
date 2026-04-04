"""
Coordinator and boss-agent logic for `ads.boss`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace.

Key definitions include `ADSBossAgent`, `BossDbQueryRequest`, `BossDbTableRequest`,
`create_demo_app`, and `scheduled_jobs_schema_dict`, which provide the main entry points
used by neighboring modules and tests.
"""

from __future__ import annotations

from calendar import monthrange
from copy import deepcopy
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from ads.agents import ADS_DIRECT_TOKEN, ADS_PARTY, _collect_submitted_symbols, _job_requires_symbols, _resolve_ads_party
from ads.jobcap import job_cap_entry_is_disabled
from ads.runtime import build_id, normalize_string_list, parse_datetime_value, read_ads_config, utcnow_iso
from ads.schema import (
    TABLE_DAILY_PRICE,
    TABLE_JOBS,
    TABLE_NEWS,
    TABLE_RAW_DATA,
    TABLE_SEC_COMPANYFACTS,
    TABLE_SEC_SUBMISSIONS,
    TABLE_SECURITY_MASTER,
    TABLE_WORKER_HISTORY,
    TABLE_WORKERS,
    ads_table_schema_map,
    jobs_schema_dict,
    raw_data_schema_dict,
    worker_capabilities_schema_dict,
    worker_history_schema_dict,
)
from prompits.agents.standby import StandbyAgent
from prompits.core.pit import PitAddress
from prompits.core.schema import TableSchema


BASE_DIR = Path(__file__).resolve().parent / "boss_ui"
TABLE_SCHEDULED_JOBS = "ads_boss_scheduled_jobs"
WEEKDAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAY_INDEX = {name: index for index, name in enumerate(WEEKDAY_ORDER)}
SCHEDULE_TIMESTAMP_FIELDS = ("scheduled_for", "issued_at", "last_attempted_at", "created_at", "updated_at")
WORKER_STALE_AFTER_SEC = 45.0
WORKER_OFFLINE_AFTER_SEC = 180.0
HERO_METRIC_TABLES = (
    ("security_master", "Security Master", TABLE_SECURITY_MASTER),
    ("daily_price", "Daily Price", TABLE_DAILY_PRICE),
    ("news", "News", TABLE_NEWS),
    ("sec_companyfacts", "SEC Companyfacts", TABLE_SEC_COMPANYFACTS),
    ("sec_submissions", "SEC Submissions", TABLE_SEC_SUBMISSIONS),
)


def _pool_dialect(pool: Any) -> str:
    """Internal helper to return the pool dialect."""
    normalized = pool.__class__.__name__.strip().lower() if pool is not None else ""
    if normalized == "postgrespool":
        return "postgres"
    if normalized == "sqlitepool":
        return "sqlite"
    return "unknown"


def _pool_schema(pool: Any) -> str:
    """Internal helper to return the pool schema."""
    return str(getattr(pool, "schema", "public") or "public").strip() or "public"


def _quote_sql_identifier(identifier: str) -> str:
    """Internal helper to quote the SQL identifier."""
    return '"' + str(identifier or "").replace('"', '""') + '"'


def _qualified_sql_table(pool: Any, table_name: str) -> str:
    """Internal helper to return the qualified SQL table."""
    if _pool_dialect(pool) == "postgres":
        return f"{_quote_sql_identifier(_pool_schema(pool))}.{_quote_sql_identifier(table_name)}"
    return _quote_sql_identifier(table_name)


def _sql_placeholder(pool: Any) -> str:
    """Internal helper to return the SQL placeholder."""
    return "%s" if _pool_dialect(pool) == "postgres" else "?"


def _normalize_timestamp_text(value: Any) -> str:
    """Internal helper to normalize the timestamp text."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.isoformat()
    return str(value or "").strip()


def scheduled_jobs_schema_dict() -> Dict[str, object]:
    """Handle scheduled jobs schema dict."""
    return {
        "name": TABLE_SCHEDULED_JOBS,
        "description": "Boss-local scheduled jobs that are issued to the ADS dispatcher when due.",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "name": {"type": "string"},
            "status": {"type": "string"},
            "dispatcher_address": {"type": "string"},
            "repeat_frequency": {"type": "string"},
            "schedule_timezone": {"type": "string"},
            "schedule_time": {"type": "string"},
            "schedule_times": {"type": "json"},
            "schedule_weekdays": {"type": "json"},
            "schedule_day_of_month": {"type": "integer"},
            "schedule_days_of_month": {"type": "json"},
            "required_capability": {"type": "string"},
            "symbols": {"type": "json"},
            "payload": {"type": "json"},
            "target_table": {"type": "string"},
            "source_url": {"type": "string"},
            "parse_rules": {"type": "json"},
            "capability_tags": {"type": "json"},
            "job_type": {"type": "string"},
            "priority": {"type": "integer"},
            "premium": {"type": "boolean"},
            "metadata": {"type": "json"},
            "scheduled_for": {"type": "datetime"},
            "max_attempts": {"type": "integer"},
            "dispatcher_job_id": {"type": "string"},
            "issued_at": {"type": "datetime"},
            "last_attempted_at": {"type": "datetime"},
            "last_error": {"type": "string"},
            "issue_attempts": {"type": "integer"},
            "created_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
        },
    }


SCHEDULED_JOBS_SCHEMA = TableSchema(scheduled_jobs_schema_dict())


class BossSubmitJobRequest(BaseModel):
    """Request model for boss submit job payloads."""
    dispatcher_address: str | None = None
    required_capability: str = Field(min_length=1)
    symbols: list[str] = Field(default_factory=list)
    payload: dict | list | str | int | float | bool | None = None
    target_table: str = ""
    source_url: str = ""
    parse_rules: dict | list | str | int | float | bool | None = None
    capability_tags: list[str] = Field(default_factory=list)
    job_type: str = "collect"
    priority: int = 100
    premium: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    scheduled_for: str = ""
    max_attempts: int = 3


class BossScheduleJobRequest(BossSubmitJobRequest):
    """Request model for boss schedule job payloads."""
    name: str = ""
    repeat_frequency: str = "once"
    schedule_timezone: str = "UTC"
    schedule_time: str = ""
    schedule_times: list[str] = Field(default_factory=list)
    schedule_weekdays: list[str] = Field(default_factory=list)
    schedule_day_of_month: int | None = None
    schedule_days_of_month: list[int] = Field(default_factory=list)
    scheduled_for: str = ""


class BossPlazaConnectRequest(BaseModel):
    """Request model for boss Plaza connect payloads."""
    plaza_url: str = Field(min_length=1)


class BossSettingsRequest(BaseModel):
    """Request model for boss settings payloads."""
    dispatcher_address: str = ""
    plaza_url: str = ""
    monitor_refresh_sec: int | str | None = 0


class BossJobControlRequest(BaseModel):
    """Request model for boss job control payloads."""
    dispatcher_address: str | None = None
    action: str = Field(min_length=1)
    reason: str = ""


class BossScheduleControlRequest(BaseModel):
    """Request model for boss schedule control payloads."""
    action: str = Field(min_length=1)


class BossDbTableRequest(BaseModel):
    """Request model for boss database table payloads."""
    dispatcher_address: str | None = None
    table_name: str = Field(min_length=1)
    limit: int = 100
    offset: int = 0


class BossDbQueryRequest(BaseModel):
    """Request model for boss database query payloads."""
    dispatcher_address: str | None = None
    sql: str = Field(min_length=1)
    params: dict | list | str | int | float | bool | None = None
    limit: int = 200


class ADSBossAgent(StandbyAgent):
    """Agent implementation for ADS boss workflows."""
    def __init__(
        self,
        name: str = "ADSBoss",
        host: str = "127.0.0.1",
        port: int = 8065,
        plaza_url: str | None = None,
        agent_card: Dict[str, Any] | None = None,
        pool: Any = None,
        config: Any = None,
        config_path: Any = None,
        dispatcher_address: str = "",
        auto_register: bool | None = None,
    ):
        """Initialize the ADS boss agent."""
        loaded = read_ads_config(config_path or config)
        resolved_config_path = self._resolve_runtime_config_path(config_path or config)
        config_root = resolved_config_path.parent if resolved_config_path else None
        ads_settings = loaded.get("ads") if isinstance(loaded.get("ads"), Mapping) else {}
        resolved_dispatcher_address = str(
            dispatcher_address
            or ads_settings.get("dispatcher_address")
            or loaded.get("dispatcher_address")
            or ""
        ).strip()
        resolved_auto_register = bool(
            auto_register if auto_register is not None else ads_settings.get("auto_register", False)
        )
        direct_auth_token = str(
            ads_settings.get("direct_auth_token")
            or loaded.get("direct_auth_token")
            or ADS_DIRECT_TOKEN
        ).strip()

        card = dict(agent_card or loaded.get("agent_card") or {})
        card.setdefault("name", str(loaded.get("name") or name))
        card["party"] = _resolve_ads_party(loaded, card)
        card["role"] = str(loaded.get("role") or card.get("role") or "boss")
        card["description"] = str(
            loaded.get("description")
            or card.get("description")
            or "ADS boss operator UI for issuing collection jobs to the dispatcher."
        )
        tags = list(card.get("tags") or loaded.get("tags") or [])
        for tag in ("ads", "boss", "operator"):
            if tag not in tags:
                tags.append(tag)
        card["tags"] = tags
        meta = dict(card.get("meta") or {})
        meta["dispatcher_address"] = resolved_dispatcher_address
        meta.setdefault("party", card["party"] or ADS_PARTY)
        meta.setdefault("direct_auth_token", direct_auth_token)
        card["meta"] = meta

        super().__init__(
            name=card["name"],
            host=host,
            port=port,
            plaza_url=plaza_url,
            agent_card=card,
            pool=pool,
        )

        self.ads_settings = dict(ads_settings or {})
        self.dispatcher_address = resolved_dispatcher_address
        self.config_path = resolved_config_path
        self.raw_config = loaded
        self.job_options = self._load_job_options(ads_settings, config_root=config_root)
        self.scheduler_poll_sec = self._coerce_scheduler_poll_sec(self.ads_settings.get("scheduler_poll_sec", 5))
        self._schedule_stop_event = threading.Event()
        self._schedule_thread: threading.Thread | None = None
        self._schedule_thread_lock = threading.Lock()
        self._schedule_issue_lock = threading.Lock()
        self.ensure_schedule_tables()
        self.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
        self.app.mount("/boss-static", StaticFiles(directory=str(BASE_DIR / "static")), name="boss_static")
        self._setup_boss_routes()
        self._setup_scheduler_events()

        if self.plaza_url and resolved_auto_register:
            self.register()

    @staticmethod
    def _asset_version() -> str:
        """Internal helper to return the asset version."""
        return str(
            max(
                int((BASE_DIR / "static" / "boss.css").stat().st_mtime),
                int((BASE_DIR / "static" / "boss.js").stat().st_mtime),
                int((BASE_DIR / "templates" / "index.html").stat().st_mtime),
            )
        )

    def _ui_context(self) -> Dict[str, Any]:
        """Internal helper for UI context."""
        return {
            "application": "ADS Boss Agent",
            "dispatcher_address": self.dispatcher_address,
            "hero_metrics": self._default_ads_metrics_summary(dispatcher_address=self.dispatcher_address),
            "job_options": self.job_options,
            "db_tables": self._db_table_options(),
            "plaza_status": self._initial_plaza_status(),
            "settings_defaults": self._settings_defaults(),
            "runtime_summary": self._runtime_summary(),
        }

    @staticmethod
    def _coerce_monitor_refresh_sec(value: Any) -> int:
        """Internal helper to coerce the monitor refresh SEC."""
        try:
            return max(0, min(int(value), 3600))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _coerce_scheduler_poll_sec(value: Any) -> int:
        """Internal helper to coerce the scheduler poll SEC."""
        try:
            return max(0, min(int(value), 3600))
        except (TypeError, ValueError):
            return 5

    def _settings_defaults(self) -> Dict[str, Any]:
        """Internal helper to return the settings defaults."""
        return {
            "dispatcher_address": self.dispatcher_address,
            "monitor_refresh_sec": self._coerce_monitor_refresh_sec(self.ads_settings.get("monitor_refresh_sec", 0)),
            "plaza_url": self._normalize_url(self.plaza_url),
        }

    @staticmethod
    def _default_ads_metrics_summary(*, dispatcher_address: str = "", status: str = "idle", error: str = "") -> Dict[str, Any]:
        """Internal helper to return the default ADS metrics summary."""
        return {
            "status": str(status or "idle").strip().lower() or "idle",
            "dispatcher_address": str(dispatcher_address or "").strip(),
            "error": str(error or "").strip(),
            "last_refreshed_at": "",
            "metrics": [
                {
                    "id": metric_id,
                    "label": label,
                    "table_name": table_name,
                    "count": 0,
                    "available": False,
                }
                for metric_id, label, table_name in HERO_METRIC_TABLES
            ],
        }

    @staticmethod
    def _resolve_runtime_config_path(config: Any) -> Path | None:
        """Internal helper to resolve the runtime config path."""
        if isinstance(config, Path):
            return config.resolve()
        if isinstance(config, str) and config.strip():
            return Path(config).expanduser().resolve()
        return None

    def _runtime_summary(self) -> Dict[str, Any]:
        """Internal helper to return the runtime summary."""
        return {
            "boss_name": self.name,
            "agent_id": str(self.agent_id or ""),
            "plaza_url": self._normalize_url(self.plaza_url),
            "dispatcher_address": self.dispatcher_address,
            "job_caps": [str(option.get("label") or option.get("id") or "") for option in self.job_options],
            "scheduler_poll_sec": self.scheduler_poll_sec,
        }

    @staticmethod
    def _db_table_options() -> list[dict[str, str]]:
        """Internal helper to return the database table options."""
        schema_map = ads_table_schema_map()
        return [
            {
                "name": name,
                "label": name,
                "description": getattr(schema, "description", ""),
            }
            for name, schema in schema_map.items()
        ]

    def _initial_plaza_status(self) -> Dict[str, Any]:
        """Internal helper to return the initial Plaza status."""
        normalized_plaza_url = self._normalize_url(self.plaza_url)
        if not normalized_plaza_url:
            return {
                "status": "success",
                "plaza_url": "",
                "agent_name": self.name,
                "agent_id": str(self.agent_id or ""),
                "online": False,
                "authenticated": False,
                "last_active": 0.0,
                "connection_status": "not_configured",
                "error": "",
            }

        last_active = float(self.last_plaza_heartbeat_at or 0)
        is_connected = bool(self.plaza_token) and self._heartbeat_is_active(last_active)
        connection_status = "connected" if is_connected else ("disconnected" if self._plaza_connection_error else "checking")
        return {
            "status": "success",
            "plaza_url": normalized_plaza_url,
            "agent_name": self.name,
            "agent_id": str(self.agent_id or ""),
            "online": is_connected,
            "authenticated": bool(self.plaza_token),
            "last_active": last_active,
            "connection_status": connection_status,
            "error": str(self._plaza_connection_error or ""),
        }

    @staticmethod
    def _resolve_config_relative_path(raw_path: Any, *, config_root: Path | None) -> Path | None:
        """Internal helper to resolve the config relative path."""
        text = str(raw_path or "").strip()
        if not text:
            return None
        candidate = Path(text).expanduser()
        if candidate.is_absolute():
            return candidate
        if config_root is not None:
            return (config_root / candidate).resolve()
        return candidate.resolve()

    @staticmethod
    def _job_options_from_cap_entries(entries: Any) -> list[dict[str, Any]]:
        """Internal helper for job options from cap entries."""
        options: list[dict[str, str]] = []
        seen = set()
        if not isinstance(entries, list):
            return options
        for entry in entries:
            if isinstance(entry, Mapping):
                if job_cap_entry_is_disabled(entry):
                    continue
                raw_name = str(entry.get("name") or entry.get("job_name") or "").strip()
                description = str(entry.get("description") or "").strip()
            else:
                raw_name = str(entry or "").strip()
                description = ""
            if not raw_name:
                continue
            normalized = raw_name.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            option: dict[str, Any] = {
                "id": raw_name,
                "label": raw_name,
                "description": description,
                "requires_symbols": _job_requires_symbols(raw_name),
            }
            if isinstance(entry, Mapping):
                if "requires_symbols" in entry:
                    option["requires_symbols"] = bool(entry.get("requires_symbols"))
                elif "symbols_required" in entry:
                    option["requires_symbols"] = bool(entry.get("symbols_required"))
                for key in ("payload_template", "parameters"):
                    if key in entry:
                        option[key] = deepcopy(entry.get(key))
            options.append(option)
        return options

    def _load_job_options(self, ads_settings: Mapping[str, Any], *, config_root: Path | None) -> list[dict[str, Any]]:
        """Internal helper to load the job options."""
        options = self._job_options_from_cap_entries(ads_settings.get("job_capabilities"))
        if options:
            return options

        worker_config_path = self._resolve_config_relative_path(
            ads_settings.get("worker_config_path"),
            config_root=config_root,
        )
        if worker_config_path and worker_config_path.exists():
            worker_config = read_ads_config(worker_config_path)
            worker_ads = worker_config.get("ads") if isinstance(worker_config.get("ads"), Mapping) else {}
            options = self._job_options_from_cap_entries(worker_ads.get("job_capabilities"))
            if options:
                return options

        return [{"id": "IEX EOD", "label": "IEX EOD", "description": "Fetch IEX end-of-day prices."}]

    def ensure_schedule_tables(self) -> None:
        """Ensure the schedule tables exists."""
        if self.pool is None:
            return
        if not self.pool._TableExists(TABLE_SCHEDULED_JOBS):
            self.pool._CreateTable(TABLE_SCHEDULED_JOBS, SCHEDULED_JOBS_SCHEMA)
        self._ensure_schedule_table_integrity()

    def _ensure_schedule_table_integrity(self) -> None:
        """Internal helper to ensure the schedule table integrity exists."""
        pool = self.pool
        conn = getattr(pool, "conn", None)
        if pool is None or conn is None:
            return
        cursor = conn.cursor()
        if _pool_dialect(pool) == "postgres":
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                (_pool_schema(pool), TABLE_SCHEDULED_JOBS),
            )
            existing_columns = {str(row[0]) for row in cursor.fetchall() if row and row[0]}
            column_specs = {
                "string": "TEXT",
                "integer": "BIGINT",
                "boolean": "BOOLEAN",
                "datetime": "TIMESTAMPTZ",
                "json": "JSONB",
            }
        else:
            cursor.execute(f"PRAGMA table_info('{TABLE_SCHEDULED_JOBS}')")
            existing_columns = {str(row[1]) for row in cursor.fetchall() if len(row) > 1 and row[1]}
            column_specs = {
                "string": "TEXT",
                "integer": "INTEGER",
                "boolean": "INTEGER",
                "datetime": "TIMESTAMP",
                "json": "TEXT",
            }
        for column_name, spec in SCHEDULED_JOBS_SCHEMA.rowSchema.columns.items():
            if column_name in existing_columns:
                continue
            column_type = column_specs.get(str(spec.get("type") or "").strip().lower(), "TEXT")
            cursor.execute(
                f"ALTER TABLE {_qualified_sql_table(pool, TABLE_SCHEDULED_JOBS)} "
                f"ADD COLUMN {_quote_sql_identifier(column_name)} {column_type}"
            )
        conn.commit()

    @staticmethod
    def _normalize_repeat_frequency(value: Any) -> str:
        """Internal helper to normalize the repeat frequency."""
        normalized = str(value or "once").strip().lower()
        return normalized if normalized in {"once", "daily", "weekly", "monthly"} else "once"

    @staticmethod
    def _normalize_schedule_timezone(value: Any) -> str:
        """Internal helper to normalize the schedule timezone."""
        candidate = str(value or "UTC").strip() or "UTC"
        try:
            ZoneInfo(candidate)
            return candidate
        except ZoneInfoNotFoundError:
            return "UTC"

    @staticmethod
    def _normalize_schedule_time(value: Any) -> str:
        """Internal helper to normalize the schedule time."""
        text = str(value or "").strip()
        if not text:
            return ""
        parts = text.split(":")
        if len(parts) < 2:
            raise ValueError("schedule_time must use HH:MM format.")
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except (TypeError, ValueError) as exc:
            raise ValueError("schedule_time must use HH:MM format.") from exc
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("schedule_time must use HH:MM format.")
        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def _decode_schedule_sequence(values: Any) -> Any:
        """Internal helper to decode the schedule sequence."""
        if not isinstance(values, str):
            return values
        text = values.strip()
        if not (text.startswith("[") and text.endswith("]")):
            return values
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return values
        return parsed if isinstance(parsed, list) else values

    @classmethod
    def _normalize_schedule_times(cls, values: Any) -> list[str]:
        """Internal helper to normalize the schedule times."""
        if values in (None, "", []):
            return []
        normalized: list[str] = []
        for value in normalize_string_list(cls._decode_schedule_sequence(values)):
            schedule_time = cls._normalize_schedule_time(value)
            if schedule_time and schedule_time not in normalized:
                normalized.append(schedule_time)
        return sorted(normalized)

    @staticmethod
    def _normalize_schedule_weekdays(values: Any) -> list[str]:
        """Internal helper to normalize the schedule weekdays."""
        normalized: list[str] = []
        for value in normalize_string_list(ADSBossAgent._decode_schedule_sequence(values)):
            lowered = str(value or "").strip().lower()[:3]
            if lowered in WEEKDAY_INDEX and lowered not in normalized:
                normalized.append(lowered)
        return sorted(normalized, key=lambda item: WEEKDAY_INDEX[item])

    @staticmethod
    def _normalize_schedule_day_of_month(value: Any) -> int | None:
        """Internal helper to normalize the schedule day of month."""
        if value in (None, "", 0):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("schedule_day_of_month must be between 1 and 31.") from exc
        if parsed < 1 or parsed > 31:
            raise ValueError("schedule_day_of_month must be between 1 and 31.")
        return parsed

    @staticmethod
    def _normalize_schedule_days_of_month(values: Any) -> list[int]:
        """Internal helper to normalize the schedule days of month."""
        if values in (None, "", 0, []):
            return []
        normalized: list[int] = []
        for value in normalize_string_list(ADSBossAgent._decode_schedule_sequence(values)):
            parsed = ADSBossAgent._normalize_schedule_day_of_month(value)
            if parsed is not None and parsed not in normalized:
                normalized.append(parsed)
        return sorted(normalized)

    @staticmethod
    def _schedule_time_parts(value: str) -> tuple[int, int]:
        """Internal helper to schedule the time parts."""
        normalized = ADSBossAgent._normalize_schedule_time(value)
        hour_text, minute_text = normalized.split(":")
        return int(hour_text), int(minute_text)

    @staticmethod
    def _resolve_schedule_zone(timezone_name: str) -> ZoneInfo:
        """Internal helper to resolve the schedule zone."""
        try:
            return ZoneInfo(str(timezone_name or "UTC").strip() or "UTC")
        except ZoneInfoNotFoundError:
            return ZoneInfo("UTC")

    @classmethod
    def _next_daily_occurrence(
        cls,
        *,
        schedule_times: list[str],
        timezone_name: str,
        after: datetime,
    ) -> datetime:
        """Internal helper for next daily occurrence."""
        normalized_times = cls._normalize_schedule_times(schedule_times)
        if not normalized_times:
            raise ValueError("schedule_times is required for repeating schedules.")
        zone = cls._resolve_schedule_zone(timezone_name)
        local_after = after.astimezone(zone)
        for delta_days in range(0, 367):
            candidate_date = (local_after + timedelta(days=delta_days)).date()
            for schedule_time in normalized_times:
                hour, minute = cls._schedule_time_parts(schedule_time)
                candidate = datetime(
                    candidate_date.year,
                    candidate_date.month,
                    candidate_date.day,
                    hour,
                    minute,
                    tzinfo=zone,
                )
                if candidate > local_after:
                    return candidate.astimezone(timezone.utc)
        raise ValueError("Unable to compute next daily occurrence.")

    @classmethod
    def _next_weekly_occurrence(
        cls,
        *,
        schedule_times: list[str],
        timezone_name: str,
        weekdays: list[str],
        after: datetime,
    ) -> datetime:
        """Internal helper for next weekly occurrence."""
        if not weekdays:
            raise ValueError("schedule_weekdays is required when repeat_frequency is weekly.")
        normalized_times = cls._normalize_schedule_times(schedule_times)
        if not normalized_times:
            raise ValueError("schedule_times is required for repeating schedules.")
        zone = cls._resolve_schedule_zone(timezone_name)
        local_after = after.astimezone(zone)
        weekday_indexes = [WEEKDAY_INDEX[day] for day in weekdays if day in WEEKDAY_INDEX]
        for delta_days in range(0, 15):
            candidate_date = (local_after + timedelta(days=delta_days)).date()
            if candidate_date.weekday() not in weekday_indexes:
                continue
            for schedule_time in normalized_times:
                hour, minute = cls._schedule_time_parts(schedule_time)
                candidate = datetime(
                    candidate_date.year,
                    candidate_date.month,
                    candidate_date.day,
                    hour,
                    minute,
                    tzinfo=zone,
                )
                if candidate > local_after:
                    return candidate.astimezone(timezone.utc)
        raise ValueError("Unable to compute next weekly occurrence.")

    @classmethod
    def _next_monthly_occurrence(
        cls,
        *,
        schedule_times: list[str],
        timezone_name: str,
        days_of_month: list[int],
        after: datetime,
    ) -> datetime:
        """Internal helper for next monthly occurrence."""
        normalized_days = cls._normalize_schedule_days_of_month(days_of_month)
        if not normalized_days:
            raise ValueError("schedule_days_of_month is required when repeat_frequency is monthly.")
        normalized_times = cls._normalize_schedule_times(schedule_times)
        if not normalized_times:
            raise ValueError("schedule_times is required for repeating schedules.")
        zone = cls._resolve_schedule_zone(timezone_name)
        local_after = after.astimezone(zone)
        year = local_after.year
        month = local_after.month
        for _ in range(0, 24):
            final_days = sorted({min(day, monthrange(year, month)[1]) for day in normalized_days})
            for final_day in final_days:
                for schedule_time in normalized_times:
                    hour, minute = cls._schedule_time_parts(schedule_time)
                    candidate = datetime(year, month, final_day, hour, minute, tzinfo=zone)
                    if candidate > local_after:
                        return candidate.astimezone(timezone.utc)
            month += 1
            if month > 12:
                month = 1
                year += 1
        raise ValueError("Unable to compute next monthly occurrence.")

    @classmethod
    def _compute_next_occurrence(
        cls,
        *,
        repeat_frequency: str,
        timezone_name: str,
        schedule_times: list[str],
        weekdays: list[str],
        days_of_month: list[int],
        after: datetime | None = None,
    ) -> str:
        """Internal helper for compute next occurrence."""
        reference_time = after or datetime.now(timezone.utc)
        normalized_frequency = cls._normalize_repeat_frequency(repeat_frequency)
        if normalized_frequency == "daily":
            return cls._next_daily_occurrence(
                schedule_times=schedule_times,
                timezone_name=timezone_name,
                after=reference_time,
            ).isoformat()
        if normalized_frequency == "weekly":
            return cls._next_weekly_occurrence(
                schedule_times=schedule_times,
                timezone_name=timezone_name,
                weekdays=weekdays,
                after=reference_time,
            ).isoformat()
        if normalized_frequency == "monthly":
            return cls._next_monthly_occurrence(
                schedule_times=schedule_times,
                timezone_name=timezone_name,
                days_of_month=days_of_month,
                after=reference_time,
            ).isoformat()
        raise ValueError(f"Unsupported repeat_frequency '{normalized_frequency}'.")

    def _setup_scheduler_events(self) -> None:
        """Internal helper to set up the scheduler events."""
        @self.app.on_event("startup")
        def _start_boss_scheduler():
            """Internal helper to start the boss scheduler."""
            self._start_scheduler_thread()

        @self.app.on_event("shutdown")
        def _stop_boss_scheduler():
            """Internal helper to stop the boss scheduler."""
            self._stop_scheduler_thread()

    def _start_scheduler_thread(self) -> bool:
        """Internal helper to start the scheduler thread."""
        if self.pool is None or self.scheduler_poll_sec <= 0:
            return False
        with self._schedule_thread_lock:
            current = self._schedule_thread
            if current and current.is_alive():
                return False
            self._schedule_stop_event = threading.Event()
            schedule_thread = threading.Thread(
                target=self._scheduler_loop,
                daemon=True,
                name=f"{self.name}-boss-scheduler",
            )
            self._schedule_thread = schedule_thread
            schedule_thread.start()
            self.logger.info(
                "Starting ADS boss scheduler loop every %.1fs.",
                float(self.scheduler_poll_sec),
            )
            return True

    def _stop_scheduler_thread(self, join_timeout: float | None = None) -> bool:
        """Internal helper to stop the scheduler thread."""
        with self._schedule_thread_lock:
            schedule_thread = self._schedule_thread
            if schedule_thread is None:
                return False
            self._schedule_stop_event.set()
        schedule_thread.join(timeout=max(float(join_timeout or (self.scheduler_poll_sec + 1.0)), 0.2))
        with self._schedule_thread_lock:
            if self._schedule_thread is schedule_thread and not schedule_thread.is_alive():
                self._schedule_thread = None
        self.logger.info("Stopped ADS boss scheduler loop.")
        return True

    def _scheduler_loop(self) -> None:
        """Internal helper for scheduler loop."""
        interval = max(float(self.scheduler_poll_sec or 0), 0.2)
        while not self._schedule_stop_event.is_set():
            try:
                result = self.process_due_schedules()
                issued_count = int(result.get("issued_count") or 0)
                if issued_count:
                    self.logger.info("ADS boss issued %s scheduled job(s).", issued_count)
            except Exception as exc:
                self.logger.exception("ADS boss schedule iteration failed: %s", exc)
            if self._schedule_stop_event.wait(interval):
                break

    def _normalize_submit_payload(self, request: BossSubmitJobRequest) -> Dict[str, Any]:
        """Internal helper to normalize the submit payload."""
        dispatcher_address = str(request.dispatcher_address or self.dispatcher_address or "").strip()
        if not dispatcher_address:
            raise ValueError("dispatcher_address is required.")

        payload = request.model_dump(mode="python")
        payload["dispatcher_address"] = dispatcher_address
        payload["required_capability"] = str(payload.get("required_capability") or "").strip()
        payload["target_table"] = str(payload.get("target_table") or "").strip()
        payload["source_url"] = str(payload.get("source_url") or "").strip()
        payload["job_type"] = str(payload.get("job_type") or "collect").strip() or "collect"
        payload["scheduled_for"] = str(payload.get("scheduled_for") or "").strip()
        payload["symbols"] = _collect_submitted_symbols(payload.get("symbols"), payload.get("payload"))
        if _job_requires_symbols(payload["required_capability"]) and not payload["symbols"]:
            raise ValueError(f"{payload['required_capability']} requires at least one symbol.")
        payload["capability_tags"] = normalize_string_list(payload.get("capability_tags"))
        payload["metadata"] = dict(payload.get("metadata") or {})
        return payload

    @staticmethod
    def _normalize_schedule_timestamp(value: Any) -> str:
        """Internal helper to normalize the schedule timestamp."""
        text = str(value or "").strip()
        if not text:
            raise ValueError("scheduled_for is required.")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("scheduled_for must be a valid ISO-8601 datetime.") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _build_schedule_name(name: Any, required_capability: str, symbols: list[str]) -> str:
        """Internal helper to build the schedule name."""
        normalized_name = str(name or "").strip()
        if normalized_name:
            return normalized_name
        base = str(required_capability or "Scheduled Job").strip() or "Scheduled Job"
        if not symbols:
            return base
        preview = ", ".join(symbols[:3])
        if len(symbols) > 3:
            preview = f"{preview} +{len(symbols) - 3}"
        return f"{base}: {preview}"

    def _normalize_schedule_payload(self, request: BossScheduleJobRequest) -> Dict[str, Any]:
        """Internal helper to normalize the schedule payload."""
        payload = self._normalize_submit_payload(request)
        repeat_frequency = self._normalize_repeat_frequency(request.repeat_frequency)
        schedule_timezone = self._normalize_schedule_timezone(request.schedule_timezone)
        schedule_times = self._normalize_schedule_times(request.schedule_times or request.schedule_time)
        schedule_weekdays = self._normalize_schedule_weekdays(request.schedule_weekdays)
        schedule_days_of_month = self._normalize_schedule_days_of_month(
            request.schedule_days_of_month or request.schedule_day_of_month
        )

        if repeat_frequency == "once":
            payload["scheduled_for"] = self._normalize_schedule_timestamp(payload.get("scheduled_for"))
            schedule_times = []
            schedule_weekdays = []
            schedule_days_of_month = []
        else:
            if not schedule_times:
                raise ValueError("schedule_times is required for repeating schedules.")
            payload["scheduled_for"] = self._compute_next_occurrence(
                repeat_frequency=repeat_frequency,
                timezone_name=schedule_timezone,
                schedule_times=schedule_times,
                weekdays=schedule_weekdays,
                days_of_month=schedule_days_of_month,
            )

        payload["repeat_frequency"] = repeat_frequency
        payload["schedule_timezone"] = schedule_timezone
        payload["schedule_time"] = schedule_times[0] if schedule_times else ""
        payload["schedule_times"] = schedule_times
        payload["schedule_weekdays"] = schedule_weekdays
        payload["schedule_day_of_month"] = schedule_days_of_month[0] if schedule_days_of_month else None
        payload["schedule_days_of_month"] = schedule_days_of_month
        payload["name"] = self._build_schedule_name(
            request.name,
            str(payload.get("required_capability") or ""),
            list(payload.get("symbols") or []),
        )
        return payload

    def _resolve_dispatcher_address(self, dispatcher_address: str = "") -> str:
        """Internal helper to resolve the dispatcher address."""
        resolved_dispatcher_address = str(dispatcher_address or self.dispatcher_address or "").strip()
        if not resolved_dispatcher_address:
            raise ValueError("dispatcher_address is required.")
        return resolved_dispatcher_address

    def _apply_plaza_url(self, plaza_url: str = "") -> str:
        """Internal helper to return the apply Plaza URL."""
        normalized_plaza_url = self._normalize_url(plaza_url)
        previous_plaza_url = self._normalize_url(self.plaza_url)
        plaza_changed = normalized_plaza_url != previous_plaza_url

        self.plaza_url = normalized_plaza_url
        meta = self.agent_card.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            self.agent_card["meta"] = meta
        if normalized_plaza_url:
            meta["plaza_url"] = normalized_plaza_url
        else:
            meta.pop("plaza_url", None)

        if plaza_changed:
            retained_pit_id = str(getattr(self.pit_address, "pit_id", "") or "")
            self.plaza_token = None
            self.token_expires_at = 0.0
            self._credential_retry_after = 0.0
            self.last_plaza_heartbeat_at = 0.0
            self._plaza_connection_error = ""
            self.agent_id = None
            self.api_key = None
            self.agent_card.pop("agent_id", None)
            self.address = PitAddress(pit_id=retained_pit_id, plazas=[])
            self.pit_address = self.address

        self._sync_connectivity_metadata()
        self.agent_card["address"] = self._resolve_advertised_address()
        self._refresh_pit_address()
        return normalized_plaza_url

    def _apply_settings(self, settings: Mapping[str, Any] | None = None) -> Dict[str, Any]:
        """Internal helper to return the apply settings."""
        current = self._settings_defaults()
        merged = dict(current)
        if isinstance(settings, Mapping):
            merged.update(dict(settings))

        self.dispatcher_address = str(merged.get("dispatcher_address") or "").strip()
        self.ads_settings["dispatcher_address"] = self.dispatcher_address
        self.ads_settings["monitor_refresh_sec"] = self._coerce_monitor_refresh_sec(merged.get("monitor_refresh_sec"))
        self._apply_plaza_url(str(merged.get("plaza_url") or ""))

        meta = self.agent_card.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            self.agent_card["meta"] = meta
        meta["dispatcher_address"] = self.dispatcher_address
        self.raw_config = self._build_config_document()
        return self._settings_defaults()

    def _build_config_document(self) -> Dict[str, Any]:
        """Internal helper to build the config document."""
        document = read_ads_config(self.config_path) if self.config_path else dict(self.raw_config or {})
        if not isinstance(document, dict):
            document = {}

        document["name"] = str(document.get("name") or self.name)
        document["host"] = str(document.get("host") or self.host)
        document["port"] = int(document.get("port") or self.port)
        document["type"] = str(
            document.get("type") or f"{self.__class__.__module__}.{self.__class__.__name__}"
        )
        document["description"] = str(document.get("description") or self.agent_card.get("description") or "")

        normalized_plaza_url = self._normalize_url(self.plaza_url)
        if normalized_plaza_url:
            document["plaza_url"] = normalized_plaza_url
        else:
            document.pop("plaza_url", None)

        ads = dict(document.get("ads") or {})
        ads["dispatcher_address"] = self.dispatcher_address
        ads["monitor_refresh_sec"] = self._coerce_monitor_refresh_sec(self.ads_settings.get("monitor_refresh_sec", 0))
        ads["scheduler_poll_sec"] = self.scheduler_poll_sec
        document["ads"] = ads
        return document

    def get_config_document(self) -> Dict[str, Any]:
        """Return the config document."""
        config = self._build_config_document()
        self.raw_config = dict(config)
        return {
            "status": "success",
            "config": config,
            "config_path": str(self.config_path) if self.config_path else None,
            "settings": self._settings_defaults(),
            "runtime_summary": self._runtime_summary(),
            "plaza_status": self._initial_plaza_status(),
        }

    def save_config_document(self, settings: Mapping[str, Any] | None = None) -> Dict[str, Any]:
        """Save the config document."""
        resolved_settings = self._apply_settings(settings)
        config = self._build_config_document()
        if self.config_path:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        self.raw_config = dict(config)
        return {
            "status": "success",
            "config": config,
            "config_path": str(self.config_path) if self.config_path else None,
            "settings": resolved_settings,
            "runtime_summary": self._runtime_summary(),
            "plaza_status": self._initial_plaza_status(),
        }

    def _fetch_dispatcher_rows(
        self,
        *,
        table_name: str,
        table_schema: Mapping[str, Any],
        dispatcher_address: str = "",
        id_or_where: Any = None,
    ) -> list[dict[str, Any]]:
        """Internal helper to fetch the dispatcher rows."""
        resolved_dispatcher_address = self._resolve_dispatcher_address(dispatcher_address)
        rows = self.UsePractice(
            "pool-get-table-data",
            {
                "table_name": table_name,
                "id_or_where": id_or_where,
                "table_schema": dict(table_schema),
            },
            pit_address=resolved_dispatcher_address,
        )
        if isinstance(rows, Mapping) and isinstance(rows.get("rows"), list):
            rows = rows.get("rows")
        if not isinstance(rows, list):
            return []
        return [dict(row) for row in rows if isinstance(row, Mapping)]

    @staticmethod
    def _is_missing_practice_error(exc: Exception, practice_id: str) -> bool:
        """Return whether the value is a missing practice error."""
        detail = str(getattr(exc, "detail", "") or "")
        message = f"{detail} {exc}".lower()
        return f"practice '{practice_id.lower()}' not found" in message

    @staticmethod
    def _normalize_job_row(row: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to normalize the job row."""
        normalized = dict(row)
        normalized["symbols"] = normalize_string_list(normalized.get("symbols"))
        normalized["capability_tags"] = normalize_string_list(normalized.get("capability_tags"))
        normalized["metadata"] = dict(normalized.get("metadata") or {}) if isinstance(normalized.get("metadata"), Mapping) else {}
        normalized["result_summary"] = (
            dict(normalized.get("result_summary") or {})
            if isinstance(normalized.get("result_summary"), Mapping)
            else {}
        )
        return normalized

    @staticmethod
    def _normalize_worker_row(row: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to normalize the worker row."""
        normalized = dict(row)
        normalized_worker_id = str(
            normalized.get("worker_id")
            or normalized.get("id")
            or normalized.get("name")
            or ""
        ).strip()
        normalized["id"] = str(normalized.get("id") or normalized_worker_id).strip()
        normalized["worker_id"] = normalized_worker_id
        normalized["name"] = str(normalized.get("name") or normalized_worker_id or "Worker").strip() or "Worker"
        normalized["address"] = str(normalized.get("address") or "").strip()
        normalized["capabilities"] = normalize_string_list(normalized.get("capabilities"))
        normalized["metadata"] = (
            dict(normalized.get("metadata") or {})
            if isinstance(normalized.get("metadata"), Mapping)
            else {}
        )
        normalized["plaza_url"] = str(normalized.get("plaza_url") or "").strip()
        normalized["status"] = str(normalized.get("status") or "online").strip().lower() or "online"
        normalized["last_seen_at"] = _normalize_timestamp_text(normalized.get("last_seen_at"))
        normalized["updated_at"] = _normalize_timestamp_text(
            normalized.get("updated_at") or normalized.get("last_seen_at")
        )
        return normalized

    @staticmethod
    def _normalize_worker_history_row(row: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to normalize the worker history row."""
        normalized = dict(row)
        normalized_worker_id = str(
            normalized.get("worker_id")
            or normalized.get("id")
            or normalized.get("name")
            or ""
        ).strip()
        normalized["worker_id"] = normalized_worker_id
        normalized["name"] = str(normalized.get("name") or normalized_worker_id or "Worker").strip() or "Worker"
        normalized["status"] = str(normalized.get("status") or "online").strip().lower() or "online"
        normalized["event_type"] = str(normalized.get("event_type") or "heartbeat").strip().lower() or "heartbeat"
        normalized["active_job_id"] = str(normalized.get("active_job_id") or "").strip()
        normalized["active_job_status"] = str(normalized.get("active_job_status") or "").strip().lower()
        normalized["progress"] = (
            dict(normalized.get("progress") or {})
            if isinstance(normalized.get("progress"), Mapping)
            else {}
        )
        normalized["environment"] = (
            dict(normalized.get("environment") or {})
            if isinstance(normalized.get("environment"), Mapping)
            else {}
        )
        normalized["metadata"] = (
            dict(normalized.get("metadata") or {})
            if isinstance(normalized.get("metadata"), Mapping)
            else {}
        )
        normalized["captured_at"] = _normalize_timestamp_text(normalized.get("captured_at"))
        normalized["session_started_at"] = _normalize_timestamp_text(normalized.get("session_started_at"))
        return normalized

    @staticmethod
    def _worker_sort_tuple(row: Mapping[str, Any]) -> tuple[Any, Any, str]:
        """Internal helper for worker sort tuple."""
        return (
            parse_datetime_value(row.get("updated_at") or row.get("last_seen_at")),
            parse_datetime_value(row.get("last_seen_at")),
            str(row.get("worker_id") or row.get("id") or ""),
        )

    @staticmethod
    def _job_heartbeat_sort_tuple(row: Mapping[str, Any]) -> tuple[Any, str]:
        """Internal helper for job heartbeat sort tuple."""
        return (
            parse_datetime_value(row.get("captured_at") or row.get("updated_at") or row.get("last_seen_at")),
            str(row.get("worker_id") or row.get("id") or ""),
        )

    @staticmethod
    def _job_heartbeat_payload_from_history_row(row: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to return the job heartbeat payload from history row."""
        progress = dict(row.get("progress") or {}) if isinstance(row.get("progress"), Mapping) else {}
        message = str(progress.get("message") or "").strip()
        phase = str(progress.get("phase") or row.get("active_job_status") or row.get("status") or "").strip().lower()
        if not (message or phase):
            return {}
        return {
            "worker_id": str(row.get("worker_id") or "").strip(),
            "worker_name": str(row.get("name") or row.get("worker_id") or "").strip(),
            "status": str(row.get("status") or "").strip().lower(),
            "event_type": str(row.get("event_type") or "heartbeat").strip().lower(),
            "phase": phase,
            "message": message,
            "captured_at": _normalize_timestamp_text(row.get("captured_at")),
        }

    @staticmethod
    def _job_heartbeat_payload_from_worker_row(row: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to return the job heartbeat payload from worker row."""
        metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), Mapping) else {}
        heartbeat = dict(metadata.get("heartbeat") or {}) if isinstance(metadata.get("heartbeat"), Mapping) else {}
        progress = dict(heartbeat.get("progress") or {}) if isinstance(heartbeat.get("progress"), Mapping) else {}
        active_job = dict(heartbeat.get("active_job") or {}) if isinstance(heartbeat.get("active_job"), Mapping) else {}
        message = str(progress.get("message") or "").strip()
        phase = str(progress.get("phase") or active_job.get("status") or row.get("status") or "").strip().lower()
        if not (message or phase):
            return {}
        return {
            "worker_id": str(row.get("worker_id") or row.get("id") or "").strip(),
            "worker_name": str(row.get("name") or row.get("worker_id") or "").strip(),
            "status": str(row.get("status") or "").strip().lower(),
            "event_type": "heartbeat",
            "phase": phase,
            "message": message,
            "captured_at": _normalize_timestamp_text(row.get("updated_at") or row.get("last_seen_at")),
        }

    @staticmethod
    def _monitor_dispatcher_base(
        dispatcher_address: str = "",
        *,
        connection_status: str = "connected",
        error: str = "",
    ) -> dict[str, Any]:
        """Internal helper for monitor dispatcher base."""
        return {
            "address": str(dispatcher_address or "").strip(),
            "connection_status": str(connection_status or "connected").strip().lower() or "connected",
            "queue_state": "idle",
            "error": str(error or "").strip(),
            "total_jobs": 0,
            "ready_jobs": 0,
            "inflight_jobs": 0,
            "completed_jobs": 0,
            "failed_jobs": 0,
            "paused_jobs": 0,
            "active_workers": 0,
            "stale_workers": 0,
            "offline_workers": 0,
            "total_workers": 0,
            "last_job_update": "",
            "last_worker_seen": "",
            "job_counts": {},
            "worker_counts": {},
            "capability_counts": [],
            "alerts": [],
        }

    @staticmethod
    def _job_status_counts(rows: list[Mapping[str, Any]]) -> dict[str, int]:
        """Internal helper for job status counts."""
        counts: dict[str, int] = {
            "queued": 0,
            "claimed": 0,
            "stopping": 0,
            "stopped": 0,
            "unfinished": 0,
            "paused": 0,
            "completed": 0,
            "failed": 0,
            "retry": 0,
            "cancelled": 0,
            "deleted": 0,
        }
        for row in rows:
            status = str(row.get("status") or "unknown").strip().lower() or "unknown"
            counts[status] = counts.get(status, 0) + 1
        return counts

    @staticmethod
    def _worker_health_status(worker: Mapping[str, Any], *, now: datetime) -> tuple[str, float | None]:
        """Internal helper to return the worker health status."""
        explicit_status = str(worker.get("status") or "online").strip().lower() or "online"
        last_seen_at = parse_datetime_value(worker.get("last_seen_at") or worker.get("updated_at"))
        heartbeat_age_sec: float | None = None
        if last_seen_at != datetime.min.replace(tzinfo=timezone.utc):
            heartbeat_age_sec = max((now - last_seen_at).total_seconds(), 0.0)

        if explicit_status in {"stopped", "offline", "error"}:
            return explicit_status, heartbeat_age_sec
        if heartbeat_age_sec is None:
            return "offline", None
        if heartbeat_age_sec <= WORKER_STALE_AFTER_SEC:
            return "online", heartbeat_age_sec
        if heartbeat_age_sec <= WORKER_OFFLINE_AFTER_SEC:
            return "stale", heartbeat_age_sec
        return "offline", heartbeat_age_sec

    @staticmethod
    def _monitor_active_job_preview(job: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper for monitor active job preview."""
        payload = job.get("payload")
        normalized_payload = dict(payload) if isinstance(payload, Mapping) else {}
        return {
            "id": str(job.get("id") or "").strip(),
            "required_capability": str(job.get("required_capability") or "").strip(),
            "symbols": normalize_string_list(job.get("symbols")),
            "target_table": str(job.get("target_table") or "").strip(),
            "source_url": str(job.get("source_url") or "").strip(),
            "payload": normalized_payload,
            "priority": job.get("priority"),
            "scheduled_for": _normalize_timestamp_text(job.get("scheduled_for")),
            "status": str(job.get("status") or "").strip(),
        }

    @staticmethod
    def _monitor_active_job_preview_from_worker(worker: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper for monitor active job preview from worker."""
        metadata = dict(worker.get("metadata") or {}) if isinstance(worker.get("metadata"), Mapping) else {}
        heartbeat = dict(metadata.get("heartbeat") or {}) if isinstance(metadata.get("heartbeat"), Mapping) else {}
        active_job = dict(heartbeat.get("active_job") or {}) if isinstance(heartbeat.get("active_job"), Mapping) else {}
        progress = dict(heartbeat.get("progress") or {}) if isinstance(heartbeat.get("progress"), Mapping) else {}
        if not progress and isinstance(active_job.get("progress"), Mapping):
            progress = dict(active_job.get("progress") or {})
        active_job_id = str(active_job.get("id") or "").strip()
        if not active_job_id:
            return {}
        extra = dict(progress.get("extra") or {}) if isinstance(progress.get("extra"), Mapping) else {}
        payload = active_job.get("payload")
        normalized_payload = dict(payload) if isinstance(payload, Mapping) else {}
        if not normalized_payload and isinstance(extra.get("payload"), Mapping):
            normalized_payload = dict(extra.get("payload") or {})
        return {
            "id": active_job_id,
            "required_capability": str(
                active_job.get("required_capability")
                or extra.get("required_capability")
                or ""
            ).strip(),
            "symbols": normalize_string_list(
                active_job.get("symbols")
                if active_job.get("symbols") not in (None, "")
                else (extra.get("symbols") if extra.get("symbols") not in (None, "") else extra.get("symbol"))
            ),
            "target_table": str(active_job.get("target_table") or extra.get("target_table") or "").strip(),
            "source_url": str(active_job.get("source_url") or extra.get("source_url") or "").strip(),
            "payload": normalized_payload,
            "priority": active_job.get("priority") if active_job.get("priority") is not None else extra.get("priority"),
            "scheduled_for": _normalize_timestamp_text(active_job.get("scheduled_for") or extra.get("scheduled_for")),
            "status": str(
                active_job.get("status")
                or progress.get("phase")
                or worker.get("status")
                or ""
            ).strip().lower(),
        }

    @staticmethod
    def _merge_monitor_active_job_preview(
        base: Mapping[str, Any],
        overlay: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Internal helper to merge the monitor active job preview."""
        merged = dict(base)
        if not str(merged.get("required_capability") or "").strip():
            merged["required_capability"] = str(overlay.get("required_capability") or "").strip()
        if not normalize_string_list(merged.get("symbols")):
            merged["symbols"] = normalize_string_list(overlay.get("symbols"))
        if not str(merged.get("target_table") or "").strip():
            merged["target_table"] = str(overlay.get("target_table") or "").strip()
        if not str(merged.get("source_url") or "").strip():
            merged["source_url"] = str(overlay.get("source_url") or "").strip()
        if not isinstance(merged.get("payload"), Mapping) and isinstance(overlay.get("payload"), Mapping):
            merged["payload"] = dict(overlay.get("payload") or {})
        if merged.get("priority") is None and overlay.get("priority") is not None:
            merged["priority"] = overlay.get("priority")
        if not str(merged.get("scheduled_for") or "").strip():
            merged["scheduled_for"] = _normalize_timestamp_text(overlay.get("scheduled_for"))
        if not str(merged.get("status") or "").strip():
            merged["status"] = str(overlay.get("status") or "").strip()
        return merged

    @staticmethod
    def _sort_timestamp_value(value: Any) -> float:
        """Internal helper to return the sort timestamp value."""
        parsed = parse_datetime_value(value)
        if parsed == datetime.min.replace(tzinfo=timezone.utc):
            return float("-inf")
        return parsed.timestamp()

    @staticmethod
    def _table_missing_error(exc: Exception, table_name: str) -> bool:
        """Internal helper to return the table missing error."""
        detail = str(getattr(exc, "detail", "") or "")
        message = f"{detail} {exc}".lower()
        normalized_table_name = str(table_name or "").strip().lower()
        if not normalized_table_name:
            return False
        return normalized_table_name in message and (
            "no such table" in message
            or "does not exist" in message
            or "undefined table" in message
            or "relation" in message
        )

    def get_monitor_snapshot(self, *, dispatcher_address: str = "") -> Dict[str, Any]:
        """Return the monitor snapshot."""
        resolved_dispatcher_address = str(dispatcher_address or self.dispatcher_address or "").strip()
        if not resolved_dispatcher_address:
            dispatcher = self._monitor_dispatcher_base(connection_status="not_configured")
            dispatcher["queue_state"] = "not_configured"
            dispatcher["alerts"] = [
                "Set a dispatcher address to load ADS dispatcher and worker status."
            ]
            return {
                "status": "success",
                "dispatcher_address": "",
                "dispatcher": dispatcher,
                "workers": [],
                "count": 0,
            }

        try:
            job_rows = [
                self._normalize_job_row(row)
                for row in self._fetch_dispatcher_rows(
                    table_name=TABLE_JOBS,
                    table_schema=jobs_schema_dict(),
                    dispatcher_address=resolved_dispatcher_address,
                )
            ]
            try:
                worker_rows = [
                    self._normalize_worker_row(row)
                    for row in self._fetch_dispatcher_rows(
                        table_name=TABLE_WORKERS,
                        table_schema=worker_capabilities_schema_dict(),
                        dispatcher_address=resolved_dispatcher_address,
                    )
                ]
            except Exception as exc:
                if self._table_missing_error(exc, TABLE_WORKERS):
                    worker_rows = []
                else:
                    raise
        except Exception as exc:
            dispatcher = self._monitor_dispatcher_base(
                dispatcher_address=resolved_dispatcher_address,
                connection_status="unreachable",
                error=str(exc),
            )
            dispatcher["queue_state"] = "unreachable"
            dispatcher["alerts"] = [str(exc)]
            return {
                "status": "success",
                "dispatcher_address": resolved_dispatcher_address,
                "dispatcher": dispatcher,
                "workers": [],
                "count": 0,
            }

        latest_jobs_by_id: dict[str, dict[str, Any]] = {}
        for row in job_rows:
            row_id = str(row.get("id") or "").strip()
            if not row_id:
                continue
            existing = latest_jobs_by_id.get(row_id)
            if existing is None or self._job_sort_tuple(row) > self._job_sort_tuple(existing):
                latest_jobs_by_id[row_id] = row
        latest_jobs = list(latest_jobs_by_id.values())

        latest_workers_by_id: dict[str, dict[str, Any]] = {}
        for row in worker_rows:
            worker_id = str(row.get("worker_id") or row.get("id") or "").strip()
            if not worker_id:
                continue
            existing = latest_workers_by_id.get(worker_id)
            if existing is None or self._worker_sort_tuple(row) > self._worker_sort_tuple(existing):
                latest_workers_by_id[worker_id] = row
        latest_workers = list(latest_workers_by_id.values())

        job_counts = self._job_status_counts(latest_jobs)
        ready_jobs = int(
            job_counts.get("queued", 0)
            + job_counts.get("retry", 0)
            + job_counts.get("unfinished", 0)
        )
        inflight_jobs = int(job_counts.get("claimed", 0) + job_counts.get("stopping", 0))

        active_jobs_by_worker: dict[str, list[dict[str, Any]]] = {}
        capability_counts: dict[str, dict[str, Any]] = {}
        last_job_update = ""
        for row in latest_jobs:
            status = str(row.get("status") or "").strip().lower()
            last_job_update = max(
                last_job_update,
                _normalize_timestamp_text(row.get("updated_at") or row.get("created_at")),
            )
            capability_name = str(row.get("required_capability") or "Unassigned").strip() or "Unassigned"
            capability_entry = capability_counts.setdefault(
                capability_name,
                {"capability": capability_name, "total": 0, "queued": 0, "active": 0, "failed": 0, "completed": 0},
            )
            capability_entry["total"] += 1
            if status in {"queued", "retry", "unfinished"}:
                capability_entry["queued"] += 1
            if status in {"claimed", "stopping"}:
                capability_entry["active"] += 1
            if status == "failed":
                capability_entry["failed"] += 1
            if status == "completed":
                capability_entry["completed"] += 1
            if status in {"claimed", "stopping"}:
                worker_id = str(row.get("claimed_by") or "").strip()
                if worker_id:
                    active_jobs_by_worker.setdefault(worker_id, []).append(row)

        now = datetime.now(timezone.utc)
        worker_counts: dict[str, int] = {"online": 0, "stale": 0, "offline": 0}
        last_worker_seen = ""
        enriched_workers: list[dict[str, Any]] = []
        for row in latest_workers:
            worker_id = str(row.get("worker_id") or row.get("id") or "").strip()
            health_status, heartbeat_age_sec = self._worker_health_status(row, now=now)
            active_job_rows = list(active_jobs_by_worker.get(worker_id) or [])
            active_job_previews = [self._monitor_active_job_preview(job) for job in active_job_rows]
            if health_status in {"online", "stale"}:
                heartbeat_active_job = self._monitor_active_job_preview_from_worker(row)
                heartbeat_active_job_id = str(heartbeat_active_job.get("id") or "").strip()
                if heartbeat_active_job_id:
                    existing_preview_index = next(
                        (
                            index
                            for index, preview in enumerate(active_job_previews)
                            if str(preview.get("id") or "").strip() == heartbeat_active_job_id
                        ),
                        -1,
                    )
                    if existing_preview_index >= 0:
                        active_job_previews[existing_preview_index] = self._merge_monitor_active_job_preview(
                            active_job_previews[existing_preview_index],
                            heartbeat_active_job,
                        )
                    else:
                        active_job_previews.append(heartbeat_active_job)
            worker_counts[health_status] = worker_counts.get(health_status, 0) + 1
            last_worker_seen = max(
                last_worker_seen,
                _normalize_timestamp_text(row.get("last_seen_at") or row.get("updated_at")),
            )
            active_symbols: list[str] = []
            active_capabilities: list[str] = []
            for job in active_job_previews:
                for symbol in normalize_string_list(job.get("symbols")):
                    if symbol not in active_symbols:
                        active_symbols.append(symbol)
                capability_name = str(job.get("required_capability") or "").strip()
                if capability_name and capability_name not in active_capabilities:
                    active_capabilities.append(capability_name)
            enriched = dict(row)
            enriched["health_status"] = health_status
            enriched["heartbeat_age_sec"] = (
                round(heartbeat_age_sec, 1) if heartbeat_age_sec is not None else None
            )
            enriched["active_job_count"] = len(active_job_previews)
            enriched["active_job_ids"] = [
                str(job.get("id") or "")
                for job in active_job_previews
                if str(job.get("id") or "").strip()
            ]
            enriched["active_jobs"] = active_job_previews
            enriched["active_symbols"] = active_symbols
            enriched["active_capabilities"] = active_capabilities
            enriched["last_job_update"] = max(
                (_normalize_timestamp_text(job.get("updated_at") or job.get("created_at")) for job in active_job_rows),
                default="",
            )
            heartbeat = (
                dict(enriched.get("metadata", {}).get("heartbeat") or {})
                if isinstance(enriched.get("metadata"), Mapping)
                else {}
            )
            active_job_meta = (
                dict(heartbeat.get("active_job") or {})
                if isinstance(heartbeat.get("active_job"), Mapping)
                else {}
            )
            progress_meta = (
                dict(heartbeat.get("progress") or {})
                if isinstance(heartbeat.get("progress"), Mapping)
                else {}
            )
            enriched["progress"] = progress_meta
            enriched["active_job"] = active_job_meta
            enriched["environment"] = (
                dict(enriched.get("metadata", {}).get("environment") or {})
                if isinstance(enriched.get("metadata"), Mapping)
                else {}
            )
            enriched_workers.append(enriched)

        health_rank = {"online": 0, "stale": 1, "offline": 2, "error": 3, "stopped": 4}
        enriched_workers.sort(
            key=lambda row: (
                health_rank.get(str(row.get("health_status") or "").strip().lower(), 5),
                -int(row.get("active_job_count") or 0),
                -self._sort_timestamp_value(row.get("last_seen_at") or row.get("updated_at")),
                str(row.get("name") or row.get("worker_id") or ""),
            )
        )

        dispatcher = self._monitor_dispatcher_base(
            dispatcher_address=resolved_dispatcher_address,
            connection_status="connected",
        )
        dispatcher["job_counts"] = job_counts
        dispatcher["worker_counts"] = worker_counts
        dispatcher["total_jobs"] = len(latest_jobs)
        dispatcher["ready_jobs"] = ready_jobs
        dispatcher["inflight_jobs"] = inflight_jobs
        dispatcher["completed_jobs"] = int(job_counts.get("completed", 0))
        dispatcher["failed_jobs"] = int(job_counts.get("failed", 0))
        dispatcher["unfinished_jobs"] = int(job_counts.get("unfinished", 0))
        dispatcher["paused_jobs"] = int(job_counts.get("paused", 0))
        dispatcher["active_workers"] = int(worker_counts.get("online", 0))
        dispatcher["stale_workers"] = int(worker_counts.get("stale", 0))
        dispatcher["offline_workers"] = int(worker_counts.get("offline", 0))
        dispatcher["total_workers"] = len(enriched_workers)
        dispatcher["last_job_update"] = last_job_update
        dispatcher["last_worker_seen"] = last_worker_seen
        dispatcher["capability_counts"] = sorted(
            capability_counts.values(),
            key=lambda entry: (
                int(entry.get("active") or 0),
                int(entry.get("queued") or 0),
                int(entry.get("total") or 0),
                str(entry.get("capability") or ""),
            ),
            reverse=True,
        )[:8]

        alerts: list[str] = []
        if ready_jobs and not worker_counts.get("online", 0):
            alerts.append("Queued jobs are waiting because no online worker heartbeat is available.")
        if worker_counts.get("stale", 0):
            alerts.append(f"{worker_counts['stale']} worker heartbeat(s) look stale.")
        if job_counts.get("unfinished", 0):
            alerts.append(f"{job_counts['unfinished']} job(s) were flagged unfinished after worker heartbeat loss.")
        if job_counts.get("failed", 0):
            alerts.append(f"{job_counts['failed']} job(s) are in failed status.")
        if job_counts.get("paused", 0):
            alerts.append(f"{job_counts['paused']} job(s) are paused.")
        dispatcher["alerts"] = alerts

        if ready_jobs and not worker_counts.get("online", 0):
            dispatcher["queue_state"] = "blocked"
        elif inflight_jobs:
            dispatcher["queue_state"] = "working"
        elif ready_jobs:
            dispatcher["queue_state"] = "queued"
        elif alerts:
            dispatcher["queue_state"] = "attention"
        else:
            dispatcher["queue_state"] = "idle"

        return {
            "status": "success",
            "dispatcher_address": resolved_dispatcher_address,
            "dispatcher": dispatcher,
            "workers": enriched_workers,
            "count": len(enriched_workers),
        }

    @staticmethod
    def _normalize_schedule_row(row: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to normalize the schedule row."""
        normalized = dict(row)
        normalized["name"] = str(normalized.get("name") or "").strip()
        normalized["status"] = str(normalized.get("status") or "scheduled").strip().lower() or "scheduled"
        normalized["dispatcher_address"] = str(normalized.get("dispatcher_address") or "").strip()
        normalized["repeat_frequency"] = ADSBossAgent._normalize_repeat_frequency(normalized.get("repeat_frequency"))
        normalized["schedule_timezone"] = ADSBossAgent._normalize_schedule_timezone(normalized.get("schedule_timezone"))
        normalized["schedule_times"] = ADSBossAgent._normalize_schedule_times(
            normalized.get("schedule_times") or normalized.get("schedule_time")
        )
        normalized["schedule_time"] = normalized["schedule_times"][0] if normalized["schedule_times"] else ""
        normalized["schedule_weekdays"] = ADSBossAgent._normalize_schedule_weekdays(normalized.get("schedule_weekdays"))
        normalized["schedule_days_of_month"] = ADSBossAgent._normalize_schedule_days_of_month(
            normalized.get("schedule_days_of_month") or normalized.get("schedule_day_of_month")
        )
        normalized["schedule_day_of_month"] = (
            normalized["schedule_days_of_month"][0] if normalized["schedule_days_of_month"] else None
        )
        normalized["required_capability"] = str(normalized.get("required_capability") or "").strip()
        normalized["symbols"] = normalize_string_list(normalized.get("symbols"))
        normalized["payload"] = normalized.get("payload") if isinstance(normalized.get("payload"), (dict, list)) else {}
        normalized["target_table"] = str(normalized.get("target_table") or "").strip()
        normalized["source_url"] = str(normalized.get("source_url") or "").strip()
        normalized["parse_rules"] = normalized.get("parse_rules") if isinstance(normalized.get("parse_rules"), (dict, list)) else {}
        normalized["capability_tags"] = normalize_string_list(normalized.get("capability_tags"))
        normalized["job_type"] = str(normalized.get("job_type") or "collect").strip() or "collect"
        try:
            normalized["priority"] = int(normalized.get("priority") or 100)
        except (TypeError, ValueError):
            normalized["priority"] = 100
        normalized["premium"] = bool(normalized.get("premium"))
        normalized["metadata"] = dict(normalized.get("metadata") or {}) if isinstance(normalized.get("metadata"), Mapping) else {}
        normalized["scheduled_for"] = _normalize_timestamp_text(normalized.get("scheduled_for"))
        try:
            normalized["max_attempts"] = max(int(normalized.get("max_attempts") or 3), 1)
        except (TypeError, ValueError):
            normalized["max_attempts"] = 3
        normalized["dispatcher_job_id"] = str(normalized.get("dispatcher_job_id") or "").strip()
        normalized["issued_at"] = _normalize_timestamp_text(normalized.get("issued_at"))
        normalized["last_attempted_at"] = _normalize_timestamp_text(normalized.get("last_attempted_at"))
        normalized["last_error"] = str(normalized.get("last_error") or "").strip()
        try:
            normalized["issue_attempts"] = max(int(normalized.get("issue_attempts") or 0), 0)
        except (TypeError, ValueError):
            normalized["issue_attempts"] = 0
        normalized["created_at"] = _normalize_timestamp_text(normalized.get("created_at"))
        normalized["updated_at"] = _normalize_timestamp_text(normalized.get("updated_at") or normalized.get("created_at"))
        return normalized

    @staticmethod
    def _schedule_sort_tuple(row: Mapping[str, Any]) -> tuple[int, Any, Any, str]:
        """Internal helper to schedule the sort tuple."""
        status = str(row.get("status") or "").strip().lower()
        status_rank = 0 if status == "scheduled" else (1 if status == "issued" else 2)
        return (
            status_rank,
            parse_datetime_value(row.get("scheduled_for")),
            parse_datetime_value(row.get("updated_at") or row.get("created_at")),
            str(row.get("id") or ""),
        )

    def _load_schedule_rows(self) -> list[dict[str, Any]]:
        """Internal helper to load the schedule rows."""
        if self.pool is None:
            return []
        self.ensure_schedule_tables()
        rows = self.pool._GetTableData(TABLE_SCHEDULED_JOBS, table_schema=SCHEDULED_JOBS_SCHEMA) or []
        return [self._normalize_schedule_row(row) for row in rows if isinstance(row, Mapping)]

    def _get_schedule_row(self, schedule_id: str) -> dict[str, Any]:
        """Internal helper to return the schedule row."""
        normalized_schedule_id = str(schedule_id or "").strip()
        if not normalized_schedule_id:
            raise ValueError("schedule_id is required.")
        if self.pool is None:
            raise ValueError("schedule storage is not configured.")
        self.ensure_schedule_tables()
        rows = self.pool._GetTableData(TABLE_SCHEDULED_JOBS, normalized_schedule_id, table_schema=SCHEDULED_JOBS_SCHEMA) or []
        if not rows:
            raise LookupError(f"Scheduled job '{normalized_schedule_id}' was not found.")
        return self._normalize_schedule_row(rows[0])

    def _save_schedule_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to save the schedule row."""
        if self.pool is None:
            raise ValueError("schedule storage is not configured.")
        normalized = self._normalize_schedule_row(row)
        storage_row = dict(normalized)
        for field_name in SCHEDULE_TIMESTAMP_FIELDS:
            value = storage_row.get(field_name)
            if isinstance(value, str) and not value.strip():
                storage_row[field_name] = None
        if not self.pool._Insert(TABLE_SCHEDULED_JOBS, storage_row):
            raise RuntimeError("Failed to persist scheduled ADS job.")
        return normalized

    def _schedule_submission_payload(self, row: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        """Internal helper to schedule the submission payload."""
        normalized = self._normalize_schedule_row(row)
        dispatcher_address = self._resolve_dispatcher_address(str(normalized.get("dispatcher_address") or ""))
        metadata = dict(normalized.get("metadata") or {})
        metadata["boss_schedule_id"] = str(normalized.get("id") or "")
        metadata.setdefault("boss_name", self.name)
        return dispatcher_address, {
            "required_capability": str(normalized.get("required_capability") or ""),
            "symbols": list(normalized.get("symbols") or []),
            "payload": normalized.get("payload"),
            "target_table": str(normalized.get("target_table") or ""),
            "source_url": str(normalized.get("source_url") or ""),
            "parse_rules": normalized.get("parse_rules"),
            "capability_tags": list(normalized.get("capability_tags") or []),
            "job_type": str(normalized.get("job_type") or "collect"),
            "priority": int(normalized.get("priority") or 100),
            "premium": bool(normalized.get("premium")),
            "metadata": metadata,
            "scheduled_for": str(normalized.get("scheduled_for") or ""),
            "max_attempts": int(normalized.get("max_attempts") or 3),
        }

    def list_schedules(self, *, status: str = "", search: str = "", limit: int = 100) -> Dict[str, Any]:
        """List the schedules."""
        normalized_status = str(status or "").strip().lower()
        normalized_search = str(search or "").strip().lower()
        filtered_rows: list[dict[str, Any]] = []
        for row in self._load_schedule_rows():
            row_status = str(row.get("status") or "").strip().lower()
            if not normalized_status and row_status == "deleted":
                continue
            if normalized_status and row_status != normalized_status:
                continue
            if normalized_search:
                haystack = " ".join(
                    [
                        str(row.get("id") or ""),
                        str(row.get("name") or ""),
                        str(row.get("required_capability") or ""),
                        str(row.get("dispatcher_job_id") or ""),
                        str(row.get("last_error") or ""),
                        " ".join(row.get("symbols") or []),
                    ]
                ).lower()
                if normalized_search not in haystack:
                    continue
            filtered_rows.append(row)

        filtered_rows.sort(key=self._schedule_sort_tuple)
        try:
            normalized_limit = max(1, min(int(limit), 200))
        except (TypeError, ValueError):
            normalized_limit = 100
        return {
            "status": "success",
            "schedules": filtered_rows[:normalized_limit],
            "count": len(filtered_rows),
        }

    def create_schedule(self, request: BossScheduleJobRequest) -> Dict[str, Any]:
        """Create the schedule."""
        payload = self._normalize_schedule_payload(request)
        now = utcnow_iso()
        record = {
            "id": build_id("ads-boss-schedule"),
            "name": str(payload.pop("name") or ""),
            "status": "scheduled",
            "dispatcher_address": str(payload.pop("dispatcher_address") or ""),
            "repeat_frequency": str(payload.get("repeat_frequency") or "once"),
            "schedule_timezone": str(payload.get("schedule_timezone") or "UTC"),
            "schedule_time": str(payload.get("schedule_time") or ""),
            "schedule_times": list(payload.get("schedule_times") or []),
            "schedule_weekdays": list(payload.get("schedule_weekdays") or []),
            "schedule_day_of_month": payload.get("schedule_day_of_month"),
            "schedule_days_of_month": list(payload.get("schedule_days_of_month") or []),
            "required_capability": str(payload.get("required_capability") or ""),
            "symbols": list(payload.get("symbols") or []),
            "payload": payload.get("payload"),
            "target_table": str(payload.get("target_table") or ""),
            "source_url": str(payload.get("source_url") or ""),
            "parse_rules": payload.get("parse_rules"),
            "capability_tags": list(payload.get("capability_tags") or []),
            "job_type": str(payload.get("job_type") or "collect"),
            "priority": int(payload.get("priority") or 100),
            "premium": bool(payload.get("premium")),
            "metadata": dict(payload.get("metadata") or {}),
            "scheduled_for": str(payload.get("scheduled_for") or ""),
            "max_attempts": int(payload.get("max_attempts") or 3),
            "dispatcher_job_id": "",
            "issued_at": "",
            "last_attempted_at": "",
            "last_error": "",
            "issue_attempts": 0,
            "created_at": now,
            "updated_at": now,
        }
        return {"status": "success", "schedule": self._save_schedule_row(record)}

    def issue_scheduled_job(self, schedule_id: str, *, force_now: bool = False) -> Dict[str, Any]:
        """Handle issue scheduled job for the ADS boss agent."""
        with self._schedule_issue_lock:
            schedule = self._get_schedule_row(schedule_id)
            status = str(schedule.get("status") or "").strip().lower()
            if status == "deleted":
                raise ValueError(f"Scheduled job '{schedule_id}' has been deleted.")
            if status == "issued" and str(schedule.get("repeat_frequency") or "once").strip().lower() == "once":
                return {"status": "success", "schedule": schedule, "submission": None, "already_issued": True}

            dispatcher_address, payload = self._schedule_submission_payload(schedule)
            now = utcnow_iso()
            if force_now:
                payload["scheduled_for"] = now
            next_attempt_count = int(schedule.get("issue_attempts") or 0) + 1
            try:
                submission = self.UsePractice("ads-submit-job", payload, pit_address=dispatcher_address)
            except Exception as exc:
                failed = dict(schedule)
                failed["last_attempted_at"] = now
                failed["last_error"] = str(exc)
                failed["issue_attempts"] = next_attempt_count
                failed["updated_at"] = now
                self._save_schedule_row(failed)
                raise

            job_payload = submission.get("job") if isinstance(submission, Mapping) and isinstance(submission.get("job"), Mapping) else {}
            issued = dict(schedule)
            repeat_frequency = self._normalize_repeat_frequency(schedule.get("repeat_frequency"))
            issued["status"] = "issued" if repeat_frequency == "once" else "scheduled"
            issued["dispatcher_job_id"] = str(job_payload.get("id") or "")
            issued["issued_at"] = now
            issued["last_attempted_at"] = now
            issued["last_error"] = ""
            issued["issue_attempts"] = next_attempt_count
            if repeat_frequency != "once":
                issued["scheduled_for"] = self._compute_next_occurrence(
                    repeat_frequency=repeat_frequency,
                    timezone_name=str(schedule.get("schedule_timezone") or "UTC"),
                    schedule_times=list(schedule.get("schedule_times") or []),
                    weekdays=list(schedule.get("schedule_weekdays") or []),
                    days_of_month=list(schedule.get("schedule_days_of_month") or []),
                    after=datetime.now(timezone.utc),
                )
            issued["updated_at"] = now
            return {"status": "success", "schedule": self._save_schedule_row(issued), "submission": submission}

    def delete_schedule(self, schedule_id: str) -> Dict[str, Any]:
        """Delete the schedule."""
        with self._schedule_issue_lock:
            schedule = self._get_schedule_row(schedule_id)
            if str(schedule.get("status") or "").strip().lower() == "deleted":
                return {"status": "success", "schedule": schedule}
            updated = dict(schedule)
            updated["status"] = "deleted"
            updated["updated_at"] = utcnow_iso()
            return {"status": "success", "schedule": self._save_schedule_row(updated)}

    def process_due_schedules(self, *, limit: int = 20) -> Dict[str, Any]:
        """Handle process due schedules for the ADS boss agent."""
        now = datetime.now(timezone.utc)
        due_rows = [
            row
            for row in self._load_schedule_rows()
            if str(row.get("status") or "").strip().lower() == "scheduled"
            and parse_datetime_value(row.get("scheduled_for")) <= now
        ]
        due_rows.sort(
            key=lambda row: (
                parse_datetime_value(row.get("scheduled_for")),
                parse_datetime_value(row.get("created_at")),
                str(row.get("id") or ""),
            )
        )

        attempted = 0
        issued_count = 0
        updated_rows: list[dict[str, Any]] = []
        for row in due_rows[: max(int(limit or 20), 1)]:
            attempted += 1
            schedule_id = str(row.get("id") or "").strip()
            if not schedule_id:
                continue
            try:
                issue_result = self.issue_scheduled_job(schedule_id)
                schedule = issue_result.get("schedule")
                if isinstance(schedule, Mapping):
                    updated_rows.append(dict(schedule))
                    issued_count += 1
            except Exception as exc:
                self.logger.exception("Failed issuing scheduled ADS job %s: %s", schedule_id, exc)
                try:
                    updated_rows.append(self._get_schedule_row(schedule_id))
                except Exception:
                    pass

        return {
            "status": "success",
            "attempted": attempted,
            "issued_count": issued_count,
            "schedules": updated_rows,
        }

    @staticmethod
    def _job_sort_tuple(row: Mapping[str, Any]) -> tuple[Any, Any, str]:
        """Internal helper for job sort tuple."""
        return (
            parse_datetime_value(row.get("updated_at") or row.get("created_at")),
            parse_datetime_value(row.get("created_at")),
            str(row.get("id") or ""),
        )

    def list_jobs_via_dispatcher(
        self,
        *,
        dispatcher_address: str = "",
        status: str = "",
        capability: str = "",
        search: str = "",
        limit: int = 80,
    ) -> Dict[str, Any]:
        """List the jobs via dispatcher."""
        resolved_dispatcher_address = self._resolve_dispatcher_address(dispatcher_address)
        rows = [
            self._normalize_job_row(row)
            for row in self._fetch_dispatcher_rows(
                table_name=TABLE_JOBS,
                table_schema=jobs_schema_dict(),
                dispatcher_address=resolved_dispatcher_address,
            )
        ]
        latest_rows_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = str(row.get("id") or "").strip()
            if not row_id:
                continue
            existing = latest_rows_by_id.get(row_id)
            if existing is None or self._job_sort_tuple(row) > self._job_sort_tuple(existing):
                latest_rows_by_id[row_id] = row
        rows = list(latest_rows_by_id.values())

        normalized_status = str(status or "").strip().lower()
        normalized_capability = str(capability or "").strip().lower()
        normalized_search = str(search or "").strip().lower()

        filtered_rows = []
        for row in rows:
            row_status = str(row.get("status") or "").strip().lower()
            row_capability = str(row.get("required_capability") or "").strip().lower()
            if not normalized_status and row_status == "deleted":
                continue
            if normalized_status and row_status != normalized_status:
                continue
            if normalized_capability and normalized_capability not in row_capability:
                continue
            if normalized_search:
                haystack = " ".join(
                    [
                        str(row.get("id") or ""),
                        row_capability,
                        str(row.get("claimed_by") or ""),
                        str(row.get("source_url") or ""),
                        " ".join(row.get("symbols") or []),
                    ]
                ).lower()
                if normalized_search not in haystack:
                    continue
            filtered_rows.append(row)

        filtered_rows.sort(key=self._job_sort_tuple, reverse=True)

        try:
            normalized_limit = max(1, min(int(limit), 200))
        except (TypeError, ValueError):
            normalized_limit = 80

        return {
            "status": "success",
            "dispatcher_address": resolved_dispatcher_address,
            "jobs": filtered_rows[:normalized_limit],
            "count": len(filtered_rows),
        }

    def get_job_detail_via_dispatcher(self, job_id: str, *, dispatcher_address: str = "") -> Dict[str, Any]:
        """Return the job detail via dispatcher."""
        resolved_dispatcher_address = self._resolve_dispatcher_address(dispatcher_address)
        normalized_job_id = str(job_id or "").strip()
        if not normalized_job_id:
            raise ValueError("job_id is required.")

        job_rows = [
            self._normalize_job_row(row)
            for row in self._fetch_dispatcher_rows(
                table_name=TABLE_JOBS,
                table_schema=jobs_schema_dict(),
                dispatcher_address=resolved_dispatcher_address,
                id_or_where={"id": normalized_job_id},
            )
        ]
        if not job_rows:
            raise LookupError(f"ADS job '{normalized_job_id}' was not found.")
        job_rows.sort(key=self._job_sort_tuple, reverse=True)

        raw_rows = self._fetch_dispatcher_rows(
            table_name=TABLE_RAW_DATA,
            table_schema=raw_data_schema_dict(),
            dispatcher_address=resolved_dispatcher_address,
            id_or_where={"job_id": normalized_job_id},
        )
        raw_rows.sort(
            key=lambda row: (
                parse_datetime_value(row.get("collected_at")),
                str(row.get("id") or ""),
            ),
            reverse=True,
        )

        latest_heartbeat: dict[str, Any] = {}
        try:
            history_rows = [
                self._normalize_worker_history_row(row)
                for row in self._fetch_dispatcher_rows(
                    table_name=TABLE_WORKER_HISTORY,
                    table_schema=worker_history_schema_dict(),
                    dispatcher_address=resolved_dispatcher_address,
                    id_or_where={"active_job_id": normalized_job_id},
                )
            ]
            history_rows.sort(key=self._job_heartbeat_sort_tuple, reverse=True)
            for row in history_rows:
                latest_heartbeat = self._job_heartbeat_payload_from_history_row(row)
                if latest_heartbeat:
                    break
        except Exception as exc:
            if not self._table_missing_error(exc, TABLE_WORKER_HISTORY):
                latest_heartbeat = {}

        if not latest_heartbeat:
            claimed_by = str(job_rows[0].get("claimed_by") or "").strip()
            try:
                worker_rows = [
                    self._normalize_worker_row(row)
                    for row in self._fetch_dispatcher_rows(
                        table_name=TABLE_WORKERS,
                        table_schema=worker_capabilities_schema_dict(),
                        dispatcher_address=resolved_dispatcher_address,
                    )
                ]
                latest_workers_by_id: dict[str, dict[str, Any]] = {}
                for row in worker_rows:
                    worker_id = str(row.get("worker_id") or row.get("id") or "").strip()
                    if not worker_id:
                        continue
                    existing = latest_workers_by_id.get(worker_id)
                    if existing is None or self._worker_sort_tuple(row) > self._worker_sort_tuple(existing):
                        latest_workers_by_id[worker_id] = row

                candidate_rows = list(latest_workers_by_id.values())
                if claimed_by and claimed_by in latest_workers_by_id:
                    candidate_rows = [latest_workers_by_id[claimed_by]]

                for row in sorted(candidate_rows, key=self._worker_sort_tuple, reverse=True):
                    metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), Mapping) else {}
                    heartbeat = dict(metadata.get("heartbeat") or {}) if isinstance(metadata.get("heartbeat"), Mapping) else {}
                    active_job = dict(heartbeat.get("active_job") or {}) if isinstance(heartbeat.get("active_job"), Mapping) else {}
                    active_job_id = str(active_job.get("id") or "").strip()
                    worker_id = str(row.get("worker_id") or row.get("id") or "").strip()
                    if active_job_id != normalized_job_id and worker_id != claimed_by:
                        continue
                    latest_heartbeat = self._job_heartbeat_payload_from_worker_row(row)
                    if latest_heartbeat:
                        break
            except Exception as exc:
                if not self._table_missing_error(exc, TABLE_WORKERS):
                    latest_heartbeat = latest_heartbeat or {}

        return {
            "status": "success",
            "dispatcher_address": resolved_dispatcher_address,
            "job": job_rows[0],
            "raw_records": raw_rows,
            "latest_heartbeat": latest_heartbeat,
        }

    def get_worker_history_via_dispatcher(
        self,
        worker_id: str,
        *,
        dispatcher_address: str = "",
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Return the worker history via dispatcher."""
        resolved_dispatcher_address = self._resolve_dispatcher_address(dispatcher_address)
        normalized_worker_id = str(worker_id or "").strip()
        if not normalized_worker_id:
            raise ValueError("worker_id is required.")

        rows = [
            self._normalize_job_row(row)
            for row in self._fetch_dispatcher_rows(
                table_name=TABLE_JOBS,
                table_schema=jobs_schema_dict(),
                dispatcher_address=resolved_dispatcher_address,
            )
        ]
        latest_rows_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = str(row.get("id") or "").strip()
            if not row_id:
                continue
            existing = latest_rows_by_id.get(row_id)
            if existing is None or self._job_sort_tuple(row) > self._job_sort_tuple(existing):
                latest_rows_by_id[row_id] = row

        filtered_rows = [
            row
            for row in latest_rows_by_id.values()
            if str(row.get("claimed_by") or "").strip() == normalized_worker_id
        ]
        filtered_rows.sort(key=self._job_sort_tuple, reverse=True)

        try:
            normalized_limit = max(1, min(int(limit), 50))
        except (TypeError, ValueError):
            normalized_limit = 10

        worker_row = None
        history_rows: list[dict[str, Any]] = []
        try:
            worker_rows = [
                self._normalize_worker_row(row)
                for row in self._fetch_dispatcher_rows(
                    table_name=TABLE_WORKERS,
                    table_schema=worker_capabilities_schema_dict(),
                    dispatcher_address=resolved_dispatcher_address,
                )
            ]
            latest_workers_by_id: dict[str, dict[str, Any]] = {}
            for row in worker_rows:
                row_worker_id = str(row.get("worker_id") or row.get("id") or "").strip()
                if not row_worker_id:
                    continue
                existing = latest_workers_by_id.get(row_worker_id)
                if existing is None or self._worker_sort_tuple(row) > self._worker_sort_tuple(existing):
                    latest_workers_by_id[row_worker_id] = row
            worker_row = latest_workers_by_id.get(normalized_worker_id)
        except Exception:
            worker_row = None

        try:
            raw_history_rows = self._fetch_dispatcher_rows(
                table_name=TABLE_WORKER_HISTORY,
                table_schema=worker_history_schema_dict(),
                dispatcher_address=resolved_dispatcher_address,
                id_or_where={"worker_id": normalized_worker_id},
            )
            history_rows = [dict(row) for row in raw_history_rows if isinstance(row, Mapping)]
            for row in history_rows:
                row["capabilities"] = normalize_string_list(row.get("capabilities"))
                row["metadata"] = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), Mapping) else {}
                row["progress"] = dict(row.get("progress") or {}) if isinstance(row.get("progress"), Mapping) else {}
                row["environment"] = (
                    dict(row.get("environment") or {}) if isinstance(row.get("environment"), Mapping) else {}
                )
                row["captured_at"] = _normalize_timestamp_text(row.get("captured_at"))
                row["session_started_at"] = _normalize_timestamp_text(row.get("session_started_at"))
            history_rows.sort(
                key=lambda row: (
                    parse_datetime_value(row.get("captured_at")),
                    str(row.get("id") or ""),
                ),
                reverse=True,
            )
        except Exception:
            history_rows = []

        return {
            "status": "success",
            "dispatcher_address": resolved_dispatcher_address,
            "worker_id": normalized_worker_id,
            "worker": worker_row,
            "jobs": filtered_rows[:normalized_limit],
            "history": history_rows[:normalized_limit],
            "count": len(filtered_rows),
            "limit": normalized_limit,
        }

    def get_schedule_history_via_dispatcher(
        self,
        schedule_id: str,
        *,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Return the schedule history via dispatcher."""
        schedule = self._get_schedule_row(schedule_id)
        normalized_schedule_id = str(schedule.get("id") or "").strip()
        if not normalized_schedule_id:
            raise ValueError("schedule_id is required.")

        resolved_dispatcher_address = self._resolve_dispatcher_address(
            str(schedule.get("dispatcher_address") or "")
        )
        rows = [
            self._normalize_job_row(row)
            for row in self._fetch_dispatcher_rows(
                table_name=TABLE_JOBS,
                table_schema=jobs_schema_dict(),
                dispatcher_address=resolved_dispatcher_address,
            )
        ]
        latest_rows_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = str(row.get("id") or "").strip()
            if not row_id:
                continue
            existing = latest_rows_by_id.get(row_id)
            if existing is None or self._job_sort_tuple(row) > self._job_sort_tuple(existing):
                latest_rows_by_id[row_id] = row

        filtered_rows = []
        for row in latest_rows_by_id.values():
            metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), Mapping) else {}
            related_schedule_id = str(metadata.get("boss_schedule_id") or "").strip()
            if related_schedule_id == normalized_schedule_id:
                filtered_rows.append(row)
        filtered_rows.sort(key=self._job_sort_tuple, reverse=True)

        try:
            normalized_limit = max(1, min(int(limit), 100))
        except (TypeError, ValueError):
            normalized_limit = 20

        return {
            "status": "success",
            "dispatcher_address": resolved_dispatcher_address,
            "schedule": schedule,
            "jobs": filtered_rows[:normalized_limit],
            "count": len(filtered_rows),
            "limit": normalized_limit,
        }

    def submit_job_via_dispatcher(self, request: BossSubmitJobRequest) -> Dict[str, Any]:
        """Submit the job via dispatcher."""
        payload = self._normalize_submit_payload(request)
        dispatcher_address = payload.pop("dispatcher_address")
        return self.UsePractice(
            "ads-submit-job",
            payload,
            pit_address=dispatcher_address,
        )

    def control_job_via_dispatcher(self, job_id: str, request: BossJobControlRequest) -> Dict[str, Any]:
        """Control the job via dispatcher."""
        normalized_job_id = str(job_id or "").strip()
        if not normalized_job_id:
            raise ValueError("job_id is required.")
        dispatcher_address = self._resolve_dispatcher_address(str(request.dispatcher_address or ""))
        normalized_action = str(request.action or "").strip().lower()
        if normalized_action not in {"pause", "stop", "resume", "cancel", "delete", "force_terminate"}:
            raise ValueError("action must be one of: pause, stop, resume, cancel, delete, force_terminate.")
        try:
            return self.UsePractice(
                "ads-control-job",
                {
                    "job_id": normalized_job_id,
                    "action": normalized_action,
                    "worker_id": str(self.agent_id or self.name or ""),
                    "reason": str(request.reason or "").strip(),
                },
                pit_address=dispatcher_address,
            )
        except ValueError:
            raise
        except Exception as exc:
            message = str(exc or "").strip()
            normalized_message = message.lower()
            extracted_message = message
            if ": " in message:
                _prefix, maybe_payload = message.split(": ", 1)
                if maybe_payload.startswith("{"):
                    try:
                        parsed_payload = json.loads(maybe_payload)
                    except Exception:
                        parsed_payload = None
                    if isinstance(parsed_payload, Mapping) and parsed_payload.get("detail"):
                        extracted_message = str(parsed_payload.get("detail") or "").strip() or message
                        normalized_message = extracted_message.lower()
            if normalized_action == "force_terminate" and "force terminated" in normalized_message:
                raise ValueError(extracted_message or "Unable to force terminate the job.") from exc
            raise

    def list_db_tables_via_dispatcher(self, dispatcher_address: str = "") -> Dict[str, Any]:
        """List the database tables via dispatcher."""
        resolved_dispatcher_address = self._resolve_dispatcher_address(dispatcher_address)
        try:
            result = self.UsePractice("ads-db-list-tables", {}, pit_address=resolved_dispatcher_address)
            payload = dict(result or {}) if isinstance(result, Mapping) else {"status": "success", "tables": []}
            payload.setdefault("dispatcher_address", resolved_dispatcher_address)
            return payload
        except Exception as exc:
            if not self._is_missing_practice_error(exc, "ads-db-list-tables"):
                raise
            rows = self.UsePractice(
                "pool-query",
                {
                    "query": "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                },
                pit_address=resolved_dispatcher_address,
            )
            schema_map = ads_table_schema_map()
            tables = []
            for row in rows or []:
                if not row:
                    continue
                table_name = str(row[0] or "").strip()
                if not table_name:
                    continue
                tables.append(
                    {
                        "name": table_name,
                        "description": getattr(schema_map.get(table_name), "description", "") if schema_map.get(table_name) else "",
                    }
                )
            return {
                "status": "success",
                "dispatcher_address": resolved_dispatcher_address,
                "tables": tables,
                "count": len(tables),
            }

    def preview_db_table_via_dispatcher(self, request: BossDbTableRequest) -> Dict[str, Any]:
        """Preview the database table via dispatcher."""
        dispatcher_address = self._resolve_dispatcher_address(str(request.dispatcher_address or ""))
        table_name = str(request.table_name or "").strip()
        limit = int(request.limit)
        offset = int(request.offset)
        available_tables = {table["name"] for table in self.list_db_tables_via_dispatcher(dispatcher_address).get("tables", [])}
        if table_name not in available_tables:
            raise ValueError(f"Unknown table '{table_name}'.")
        try:
            result = self.UsePractice(
                "ads-db-preview-table",
                {
                    "table_name": table_name,
                    "limit": limit,
                    "offset": offset,
                },
                pit_address=dispatcher_address,
            )
            payload = dict(result or {}) if isinstance(result, Mapping) else {"status": "success"}
            payload.setdefault("dispatcher_address", dispatcher_address)
            return payload
        except Exception as exc:
            if not self._is_missing_practice_error(exc, "ads-db-preview-table"):
                raise
            pragma_rows = self.UsePractice(
                "pool-query",
                {"query": f"PRAGMA table_info({table_name})"},
                pit_address=dispatcher_address,
            )
            columns = [str(row[1]) for row in pragma_rows or [] if len(row) > 1]
            data_rows = self.UsePractice(
                "pool-query",
                {"query": f"SELECT * FROM {table_name} LIMIT ? OFFSET ?", "params": [limit, offset]},
                pit_address=dispatcher_address,
            )
            count_rows = self.UsePractice(
                "pool-query",
                {"query": f"SELECT COUNT(*) FROM {table_name}"},
                pit_address=dispatcher_address,
            )
            rows = []
            for row in data_rows or []:
                if columns and len(columns) == len(row):
                    rows.append(dict(zip(columns, row)))
                else:
                    rows.append({f"column_{index + 1}": value for index, value in enumerate(row)})
            total_rows = 0
            if count_rows and count_rows[0]:
                total_rows = int(count_rows[0][0] or 0)
            resolved_columns = columns
            if not resolved_columns and rows:
                resolved_columns = [f"column_{index + 1}" for index in range(len(rows[0]))]
            return {
                "status": "success",
                "dispatcher_address": dispatcher_address,
                "table_name": table_name,
                "columns": resolved_columns,
                "rows": rows,
                "count": len(rows),
                "total_rows": total_rows,
                "limit": limit,
                "offset": offset,
            }

    def query_db_via_dispatcher(self, request: BossDbQueryRequest) -> Dict[str, Any]:
        """Query the database via dispatcher."""
        dispatcher_address = self._resolve_dispatcher_address(str(request.dispatcher_address or ""))
        normalized_sql = str(request.sql or "").strip()
        normalized_limit = int(request.limit)
        try:
            result = self.UsePractice(
                "ads-db-query",
                {
                    "sql": normalized_sql,
                    "params": request.params,
                    "limit": normalized_limit,
                },
                pit_address=dispatcher_address,
            )
            payload = dict(result or {}) if isinstance(result, Mapping) else {"status": "success"}
            payload.setdefault("dispatcher_address", dispatcher_address)
            return payload
        except Exception as exc:
            if not self._is_missing_practice_error(exc, "ads-db-query"):
                raise
            rows = self.UsePractice(
                "pool-query",
                {
                    "query": normalized_sql,
                    "params": request.params,
                },
                pit_address=dispatcher_address,
            )
            normalized_rows = list(rows or [])
            column_count = len(normalized_rows[0]) if normalized_rows else 0
            columns = [f"column_{index + 1}" for index in range(column_count)]
            result_rows = [
                {columns[index]: value for index, value in enumerate(row)}
                for row in normalized_rows[:normalized_limit]
            ]
            return {
                "status": "success",
                "dispatcher_address": dispatcher_address,
                "sql": normalized_sql,
                "columns": columns,
                "rows": result_rows,
                "count": len(result_rows),
                "limit": normalized_limit,
                "truncated": len(normalized_rows) > normalized_limit,
                "compatibility_mode": "pool-query",
            }

    @staticmethod
    def _extract_count_from_query_result(payload: Mapping[str, Any] | None) -> int:
        """Internal helper to extract the count from query result."""
        rows = payload.get("rows") if isinstance(payload, Mapping) else []
        if not isinstance(rows, list) or not rows:
            return 0
        first_row = rows[0]
        if isinstance(first_row, Mapping):
            if "row_count" in first_row:
                try:
                    return max(int(first_row.get("row_count") or 0), 0)
                except (TypeError, ValueError):
                    return 0
            if first_row:
                first_value = next(iter(first_row.values()))
                try:
                    return max(int(first_value or 0), 0)
                except (TypeError, ValueError):
                    return 0
        return 0

    def get_ads_metrics_summary(self, *, dispatcher_address: str = "") -> Dict[str, Any]:
        """Return the ADS metrics summary."""
        resolved_dispatcher_address = str(dispatcher_address or self.dispatcher_address or "").strip()
        if not resolved_dispatcher_address:
            summary = self._default_ads_metrics_summary(status="not_configured")
            summary["error"] = "Set a dispatcher address to load ADS metrics."
            return summary

        try:
            available_tables = {
                str(entry.get("name") or "").strip()
                for entry in self.list_db_tables_via_dispatcher(resolved_dispatcher_address).get("tables", [])
                if isinstance(entry, Mapping)
            }
        except Exception as exc:
            summary = self._default_ads_metrics_summary(
                dispatcher_address=resolved_dispatcher_address,
                status="unreachable",
                error=str(exc),
            )
            return summary

        metrics = []
        for metric_id, label, table_name in HERO_METRIC_TABLES:
            available = table_name in available_tables
            count = 0
            if available:
                result = self.query_db_via_dispatcher(
                    BossDbQueryRequest(
                        dispatcher_address=resolved_dispatcher_address,
                        sql=f"SELECT COUNT(*) AS row_count FROM {table_name}",
                        limit=1,
                    )
                )
                count = self._extract_count_from_query_result(result)
            metrics.append(
                {
                    "id": metric_id,
                    "label": label,
                    "table_name": table_name,
                    "count": count,
                    "available": available,
                }
            )

        return {
            "status": "success",
            "dispatcher_address": resolved_dispatcher_address,
            "error": "",
            "last_refreshed_at": utcnow_iso(),
            "metrics": metrics,
        }

    def connect_plaza(self, plaza_url: str) -> Dict[str, Any]:
        """Connect the Plaza."""
        normalized_plaza_url = self._apply_plaza_url(plaza_url)
        if not normalized_plaza_url:
            raise ValueError("plaza_url is required.")

        response = self.register(start_reconnect_on_failure=False, request_retries=0)
        if response is None:
            raise RuntimeError("Failed to contact Plaza.")
        if getattr(response, "status_code", None) != 200:
            detail = str(getattr(response, "text", "") or f"Plaza connect failed with status {response.status_code}.")
            raise RuntimeError(detail)

        return {
            "status": "success",
            "plaza_url": normalized_plaza_url,
            "plaza_status": self._initial_plaza_status(),
        }

    def _setup_boss_routes(self) -> None:
        """Internal helper to set up the boss routes."""
        def _template_context(request: Request, *, current_page: str) -> Dict[str, Any]:
            """Internal helper for template context."""
            ui_payload = self._ui_context()
            ui_payload["current_page"] = current_page
            return {
                "request": request,
                "asset_version": self._asset_version(),
                "initial_payload": ui_payload,
            }

        @self.app.get("/", include_in_schema=False)
        async def boss_home(request: Request):
            """Route handler for GET /."""
            return self.templates.TemplateResponse(
                request=request,
                name="index.html",
                context=_template_context(request, current_page="issue"),
            )

        @self.app.get("/monitor", include_in_schema=False)
        async def boss_monitor_page(request: Request):
            """Route handler for GET /monitor."""
            return self.templates.TemplateResponse(
                request=request,
                name="index.html",
                context=_template_context(request, current_page="monitor"),
            )

        @self.app.get("/schedule", include_in_schema=False)
        async def boss_schedule_page(request: Request):
            """Route handler for GET /schedule."""
            return self.templates.TemplateResponse(
                request=request,
                name="index.html",
                context=_template_context(request, current_page="schedule"),
            )

        @self.app.get("/jobs", include_in_schema=False)
        async def boss_jobs_page(request: Request):
            """Route handler for GET /jobs."""
            return self.templates.TemplateResponse(
                request=request,
                name="index.html",
                context=_template_context(request, current_page="monitor"),
            )

        @self.app.get("/settings", include_in_schema=False)
        async def boss_settings_page(request: Request):
            """Route handler for GET /settings."""
            return self.templates.TemplateResponse(
                request=request,
                name="index.html",
                context=_template_context(request, current_page="settings"),
            )

        @self.app.get("/db", include_in_schema=False)
        async def boss_db_page(request: Request):
            """Route handler for GET /db."""
            return self.templates.TemplateResponse(
                request=request,
                name="index.html",
                context=_template_context(request, current_page="db"),
            )

        @self.app.get("/api/boss/config")
        async def boss_config():
            """Route handler for GET /api/boss/config."""
            return {"status": "success", **self._ui_context()}

        @self.app.get("/api/config")
        async def boss_read_config():
            """Route handler for GET /api/config."""
            return await run_in_threadpool(self.get_config_document)

        @self.app.post("/api/config")
        async def boss_save_config(request: Request):
            """Route handler for POST /api/config."""
            payload = await request.json()
            settings = payload.get("settings") if isinstance(payload, dict) and isinstance(payload.get("settings"), Mapping) else payload
            if not isinstance(settings, Mapping):
                raise HTTPException(status_code=400, detail="Settings payload must be a JSON object.")
            return await run_in_threadpool(self.save_config_document, dict(settings))

        @self.app.get("/api/plaza/status")
        async def boss_plaza_status():
            """Route handler for GET /api/plaza/status."""
            return await run_in_threadpool(self.get_plaza_connection_status)

        @self.app.post("/api/plaza/connect")
        async def boss_plaza_connect(request: BossPlazaConnectRequest):
            """Route handler for POST /api/plaza/connect."""
            try:
                return await run_in_threadpool(self.connect_plaza, request.plaza_url)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @self.app.get("/api/metrics/summary")
        async def boss_metrics_summary(dispatcher_address: str = ""):
            """Route handler for GET /api/metrics/summary."""
            try:
                return await run_in_threadpool(
                    self.get_ads_metrics_summary,
                    dispatcher_address=dispatcher_address,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @self.app.get("/api/monitor/summary")
        async def boss_monitor_summary(dispatcher_address: str = ""):
            """Route handler for GET /api/monitor/summary."""
            try:
                return await run_in_threadpool(
                    self.get_monitor_snapshot,
                    dispatcher_address=dispatcher_address,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @self.app.get("/api/workers/{worker_id}/history")
        async def boss_worker_history(worker_id: str, dispatcher_address: str = "", limit: int = 10):
            """Route handler for GET /api/workers/{worker_id}/history."""
            try:
                return await run_in_threadpool(
                    self.get_worker_history_via_dispatcher,
                    worker_id,
                    dispatcher_address=dispatcher_address,
                    limit=limit,
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @self.app.get("/api/jobs")
        async def boss_jobs(
            dispatcher_address: str = "",
            status: str = "",
            capability: str = "",
            search: str = "",
            limit: int = 80,
        ):
            """Route handler for GET /api/jobs."""
            try:
                return await run_in_threadpool(
                    self.list_jobs_via_dispatcher,
                    dispatcher_address=dispatcher_address,
                    status=status,
                    capability=capability,
                    search=search,
                    limit=limit,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @self.app.get("/api/schedules/{schedule_id}/history")
        async def boss_schedule_history(schedule_id: str, limit: int = 20):
            """Route handler for GET /api/schedules/{schedule_id}/history."""
            try:
                return await run_in_threadpool(
                    self.get_schedule_history_via_dispatcher,
                    schedule_id,
                    limit=limit,
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @self.app.get("/api/jobs/{job_id}")
        async def boss_job_detail(job_id: str, dispatcher_address: str = ""):
            """Route handler for GET /api/jobs/{job_id}."""
            try:
                return await run_in_threadpool(
                    self.get_job_detail_via_dispatcher,
                    job_id,
                    dispatcher_address=dispatcher_address,
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @self.app.get("/api/schedules")
        async def boss_schedules(status: str = "", search: str = "", limit: int = 100):
            """Route handler for GET /api/schedules."""
            try:
                return await run_in_threadpool(
                    self.list_schedules,
                    status=status,
                    search=search,
                    limit=limit,
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @self.app.post("/api/schedules")
        async def boss_create_schedule(request: BossScheduleJobRequest):
            """Route handler for POST /api/schedules."""
            try:
                return await run_in_threadpool(self.create_schedule, request)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @self.app.post("/api/schedules/{schedule_id}/control")
        async def boss_schedule_control(schedule_id: str, request: BossScheduleControlRequest):
            """Route handler for POST /api/schedules/{schedule_id}/control."""
            normalized_action = str(request.action or "").strip().lower()
            try:
                if normalized_action == "issue":
                    result = await run_in_threadpool(self.issue_scheduled_job, schedule_id, force_now=True)
                elif normalized_action == "delete":
                    result = await run_in_threadpool(self.delete_schedule, schedule_id)
                else:
                    raise HTTPException(status_code=400, detail="action must be one of: issue, delete.")
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            return {"status": "success", "control": result}

        @self.app.post("/api/jobs/{job_id}/control")
        async def boss_job_control(job_id: str, request: BossJobControlRequest):
            """Route handler for POST /api/jobs/{job_id}/control."""
            try:
                result = await run_in_threadpool(self.control_job_via_dispatcher, job_id, request)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            return {"status": "success", "control": result}

        @self.app.get("/api/db/tables")
        async def boss_db_tables(dispatcher_address: str = ""):
            """Route handler for GET /api/db/tables."""
            try:
                return await run_in_threadpool(self.list_db_tables_via_dispatcher, dispatcher_address)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @self.app.get("/api/db/table")
        async def boss_db_table(dispatcher_address: str = "", table_name: str = "", limit: int = 100, offset: int = 0):
            """Route handler for GET /api/db/table."""
            try:
                return await run_in_threadpool(
                    self.preview_db_table_via_dispatcher,
                    BossDbTableRequest(
                        dispatcher_address=dispatcher_address,
                        table_name=table_name,
                        limit=limit,
                        offset=offset,
                    ),
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @self.app.post("/api/db/query")
        async def boss_db_query(request: BossDbQueryRequest):
            """Route handler for POST /api/db/query."""
            try:
                return await run_in_threadpool(self.query_db_via_dispatcher, request)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc

        @self.app.post("/api/jobs/submit")
        async def boss_submit_job(request: BossSubmitJobRequest):
            """Route handler for POST /api/jobs/submit."""
            try:
                result = await run_in_threadpool(self.submit_job_via_dispatcher, request)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            return {"status": "success", "submission": result}


def create_demo_app() -> ADSBossAgent:
    """Create the demo app."""
    from prompits.pools.postgres import PostgresPool

    pool = PostgresPool(
        "ads_boss_pool",
        "ADS boss shared PostgreSQL storage",
        schema=str(os.getenv("ADS_POSTGRES_SCHEMA") or "public").strip() or "public",
        sslmode=str(os.getenv("ADS_POSTGRES_SSLMODE") or "disable").strip() or "disable",
    )
    return ADSBossAgent(pool=pool)


if __name__ == "__main__":
    import uvicorn

    app_agent = create_demo_app()
    uvicorn.run(app_agent.app, host=app_agent.host, port=app_agent.port)
