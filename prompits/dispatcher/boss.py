"""
Coordinator and boss-agent logic for `prompits.dispatcher.boss`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the dispatcher package
coordinates job routing, worker selection, and queue management.

Key definitions include `DispatcherBossAgent`, `BossDbQueryRequest`,
`BossJobControlRequest`, `create_demo_app`, and `scheduled_jobs_schema_dict`, which
provide the main entry points used by neighboring modules and tests.
"""

from __future__ import annotations

from calendar import monthrange
import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from prompits.agents.standby import StandbyAgent
from prompits.dispatcher.agents import (
    DISPATCHER_DIRECT_TOKEN,
    DISPATCHER_PARTY,
    WORKER_HEARTBEAT_INTERVAL_SEC,
    WORKER_JOB_TIMEOUT_SEC,
)
from prompits.dispatcher.jobcap import job_cap_entry_is_disabled
from prompits.dispatcher.runtime import normalize_string_list, parse_datetime_value, read_dispatcher_config, utcnow_iso
from prompits.dispatcher.schema import (
    TABLE_JOBS,
    TABLE_RAW_PAYLOADS,
    TABLE_RESULT_ROWS,
    TABLE_WORKER_HISTORY,
    TABLE_WORKERS,
)
from prompits.core.schema import TableSchema


BASE_DIR = Path(__file__).resolve().parent / "boss_ui"
TABLE_SCHEDULED_JOBS = "dispatcher_boss_scheduled_jobs"
WEEKDAY_ORDER = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAY_INDEX = {name: index for index, name in enumerate(WEEKDAY_ORDER)}
SCHEDULE_TIMESTAMP_FIELDS = (
    "scheduled_for",
    "issued_at",
    "last_attempted_at",
    "created_at",
    "updated_at",
)
MONITOR_TABLES = (
    TABLE_JOBS,
    TABLE_WORKERS,
    TABLE_WORKER_HISTORY,
    TABLE_RESULT_ROWS,
    TABLE_RAW_PAYLOADS,
)
DISPATCHER_DISCOVERY_PRACTICES = (
    "dispatcher-get-job",
    "dispatcher-register-worker",
    "dispatcher-submit-job",
    "dispatcher-control-job",
)


def scheduled_jobs_schema_dict() -> Dict[str, object]:
    """Handle scheduled jobs schema dict."""
    return {
        "name": TABLE_SCHEDULED_JOBS,
        "description": "Boss-local scheduled jobs that are issued to the dispatcher when due.",
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
            "targets": {"type": "json"},
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
    targets: list[str] = Field(default_factory=list)
    symbols: list[str] = Field(default_factory=list)
    payload: dict | list | str | int | float | bool | None = None
    target_table: str = ""
    source_url: str = ""
    parse_rules: dict | list | str | int | float | bool | None = None
    capability_tags: list[str] = Field(default_factory=list)
    job_type: str = "run"
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


class BossSettingsRequest(BaseModel):
    """Request model for boss settings payloads."""
    dispatcher_address: str = ""
    dispatcher_party: str = ""
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


class BossDbQueryRequest(BaseModel):
    """Request model for boss database query payloads."""
    dispatcher_address: str | None = None
    sql: str = Field(min_length=1)
    params: dict | list | str | int | float | bool | None = None
    limit: int = 200


class DispatcherBossAgent(StandbyAgent):
    """Agent implementation for dispatcher boss workflows."""
    def __init__(
        self,
        name: str = "DispatcherBoss",
        host: str = "127.0.0.1",
        port: int = 8065,
        plaza_url: str | None = None,
        agent_card: Dict[str, Any] | None = None,
        pool: Any = None,
        config: Any = None,
        config_path: Any = None,
        dispatcher_address: str = "",
        dispatcher_party: str = "",
        auto_register: bool | None = None,
    ):
        """Initialize the dispatcher boss agent."""
        loaded = read_dispatcher_config(config_path or config)
        dispatcher_settings = loaded.get("dispatcher") if isinstance(loaded.get("dispatcher"), Mapping) else {}
        resolved_dispatcher_address = str(
            dispatcher_address or dispatcher_settings.get("dispatcher_address") or loaded.get("dispatcher_address") or ""
        ).strip()
        resolved_auto_register = bool(
            auto_register if auto_register is not None else dispatcher_settings.get("auto_register", False)
        )
        raw_card = dict(agent_card or loaded.get("agent_card") or {})
        raw_meta = dict(raw_card.get("meta") or {})
        resolved_dispatcher_party = self._normalize_party(
            dispatcher_party
            or dispatcher_settings.get("dispatcher_party")
            or loaded.get("dispatcher_party")
            or raw_meta.get("dispatcher_party")
            or loaded.get("party")
            or raw_card.get("party")
            or DISPATCHER_PARTY
        ) or DISPATCHER_PARTY
        direct_auth_token = str(
            dispatcher_settings.get("direct_auth_token")
            or loaded.get("direct_auth_token")
            or DISPATCHER_DIRECT_TOKEN
        ).strip()

        card = dict(raw_card)
        card.setdefault("name", str(loaded.get("name") or name))
        card["party"] = str(loaded.get("party") or card.get("party") or DISPATCHER_PARTY).strip() or DISPATCHER_PARTY
        card["role"] = str(loaded.get("role") or card.get("role") or "boss")
        card["description"] = str(
            loaded.get("description")
            or card.get("description")
            or "Dispatcher operator UI for issuing and monitoring jobs."
        )
        tags = list(card.get("tags") or loaded.get("tags") or [])
        for tag in ("prompits", "dispatcher-boss", "operator"):
            if tag not in tags:
                tags.append(tag)
        card["tags"] = tags
        meta = dict(card.get("meta") or {})
        meta["dispatcher_address"] = resolved_dispatcher_address
        meta["dispatcher_party"] = resolved_dispatcher_party
        meta.setdefault("party", card["party"])
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

        self.dispatcher_settings = dict(dispatcher_settings or {})
        self.agent_meta = dict(meta or {})
        self.raw_config = dict(loaded or {})
        self.dispatcher_address = resolved_dispatcher_address
        self.dispatcher_party = resolved_dispatcher_party
        self.monitor_refresh_sec = self._coerce_monitor_refresh_sec(self.dispatcher_settings.get("monitor_refresh_sec", 0))
        self.scheduler_poll_sec = self._coerce_scheduler_poll_sec(self.dispatcher_settings.get("scheduler_poll_sec", 5))
        self.job_options = self._load_job_options(self.dispatcher_settings, self.agent_meta, self.raw_config)
        self.hero_metric_configs = self._load_hero_metric_configs(self.dispatcher_settings, self.agent_meta, self.raw_config)
        self._schedule_issue_lock = threading.Lock()
        self._schedule_stop_event = threading.Event()
        self._schedule_thread: threading.Thread | None = None
        self._schedule_thread_lock = threading.Lock()
        self.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
        self.app.mount("/boss-static", StaticFiles(directory=str(BASE_DIR / "static")), name="boss_static")
        self.ensure_schedule_tables()
        self._setup_scheduler_events()
        self._setup_routes()

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

    @staticmethod
    def _normalize_url(value: Any) -> str:
        """Internal helper to normalize the URL."""
        return str(value or "").strip().rstrip("/")

    @staticmethod
    def _normalize_party(value: Any) -> str:
        """Internal helper to normalize the party."""
        return str(value or "").strip()

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
            return 0

    def ensure_schedule_tables(self) -> None:
        """Ensure the schedule tables exists."""
        if self.pool is None:
            return
        if not self.pool._TableExists(TABLE_SCHEDULED_JOBS):
            self.pool._CreateTable(TABLE_SCHEDULED_JOBS, SCHEDULED_JOBS_SCHEMA)

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
        for value in normalize_string_list(DispatcherBossAgent._decode_schedule_sequence(values)):
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
        for value in normalize_string_list(DispatcherBossAgent._decode_schedule_sequence(values)):
            parsed = DispatcherBossAgent._normalize_schedule_day_of_month(value)
            if parsed is not None and parsed not in normalized:
                normalized.append(parsed)
        return sorted(normalized)

    @staticmethod
    def _schedule_time_parts(value: str) -> tuple[int, int]:
        """Internal helper to schedule the time parts."""
        normalized = DispatcherBossAgent._normalize_schedule_time(value)
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
    def _build_schedule_name(name: Any, required_capability: str, targets: list[str]) -> str:
        """Internal helper to build the schedule name."""
        normalized_name = str(name or "").strip()
        if normalized_name:
            return normalized_name
        base = str(required_capability or "Scheduled Job").strip() or "Scheduled Job"
        if not targets:
            return base
        preview = ", ".join(targets[:3])
        if len(targets) > 3:
            preview = f"{preview} +{len(targets) - 3}"
        return f"{base}: {preview}"

    def _normalize_submit_payload(self, request: BossSubmitJobRequest) -> Dict[str, Any]:
        """Internal helper to normalize the submit payload."""
        dispatcher_address = self._resolve_dispatcher_address(request.dispatcher_address)
        payload = request.model_dump(mode="python")
        payload["dispatcher_address"] = dispatcher_address
        targets = normalize_string_list(payload.get("targets"))
        if not targets:
            targets = normalize_string_list(payload.get("symbols"))
        payload["targets"] = targets
        payload["required_capability"] = str(payload.get("required_capability") or "").strip()
        payload["target_table"] = str(payload.get("target_table") or "").strip()
        payload["source_url"] = str(payload.get("source_url") or "").strip()
        payload["job_type"] = str(payload.get("job_type") or "run").strip() or "run"
        payload["scheduled_for"] = str(payload.get("scheduled_for") or "").strip()
        payload["capability_tags"] = normalize_string_list(payload.get("capability_tags"))
        payload["metadata"] = dict(payload.get("metadata") or {})
        payload.pop("symbols", None)
        return payload

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
            list(payload.get("targets") or []),
        )
        return payload

    def _normalize_job_option_entries(self, entries: Any) -> list[dict[str, Any]]:
        """Internal helper to normalize the job option entries."""
        options: list[dict[str, Any]] = []
        seen = set()
        if not isinstance(entries, list):
            return options
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            if job_cap_entry_is_disabled(entry):
                continue
            raw_name = str(entry.get("name") or entry.get("job_name") or "").strip()
            if not raw_name:
                continue
            normalized = raw_name.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            option: dict[str, Any] = {
                "id": raw_name,
                "label": raw_name,
                "description": str(entry.get("description") or "").strip(),
            }
            if "default_priority" in entry:
                option["default_priority"] = self._safe_int(entry.get("default_priority"), 100)
            if "payload_template" in entry:
                option["payload_template"] = entry.get("payload_template")
            options.append(option)
        return options

    def _load_job_options(
        self,
        dispatcher_settings: Mapping[str, Any],
        agent_meta: Mapping[str, Any],
        raw_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        """Internal helper to load the job options."""
        candidate_lists = [
            dispatcher_settings.get("job_capabilities"),
            raw_config.get("job_capabilities"),
            agent_meta.get("job_capabilities"),
        ]
        agent_card = raw_config.get("agent_card")
        if isinstance(agent_card, Mapping):
            candidate_lists.append(agent_card.get("job_capabilities"))
            card_meta = agent_card.get("meta")
            if isinstance(card_meta, Mapping):
                candidate_lists.append(card_meta.get("job_capabilities"))
        for entries in candidate_lists:
            options = self._normalize_job_option_entries(entries)
            if options:
                return options
        return []

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
                "Starting dispatcher boss scheduler loop every %.1fs.",
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
        self.logger.info("Stopped dispatcher boss scheduler loop.")
        return True

    def _scheduler_loop(self) -> None:
        """Internal helper for scheduler loop."""
        interval = max(float(self.scheduler_poll_sec or 0), 0.2)
        while not self._schedule_stop_event.is_set():
            try:
                result = self.process_due_schedules()
                issued_count = int(result.get("issued_count") or 0)
                if issued_count:
                    self.logger.info("Dispatcher boss issued %s scheduled job(s).", issued_count)
            except Exception as exc:
                self.logger.exception("Dispatcher boss schedule iteration failed: %s", exc)
            if self._schedule_stop_event.wait(interval):
                break

    def _settings_defaults(self) -> Dict[str, Any]:
        """Internal helper to return the settings defaults."""
        return {
            "dispatcher_address": self.dispatcher_address,
            "dispatcher_party": self.dispatcher_party,
            "plaza_url": self._normalize_url(self.plaza_url),
            "monitor_refresh_sec": self.monitor_refresh_sec,
        }

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        """Internal helper for safe int."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """Internal helper for safe float."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _lower(value: Any) -> str:
        """Internal helper for lower."""
        return str(value or "").strip().lower()

    def _monitor_worker_health(self, worker: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
        """Internal helper for monitor worker health."""
        normalized = dict(worker or {})
        metadata = dict(normalized.get("metadata") or {}) if isinstance(normalized.get("metadata"), Mapping) else {}
        heartbeat = dict(metadata.get("heartbeat") or {}) if isinstance(metadata.get("heartbeat"), Mapping) else {}
        raw_status = self._lower(normalized.get("status"))
        now_value = now or datetime.now(timezone.utc)
        last_seen_text = str(
            normalized.get("last_seen_at")
            or normalized.get("updated_at")
            or heartbeat.get("captured_at")
            or ""
        ).strip()
        last_seen_at = parse_datetime_value(last_seen_text)
        heartbeat_age_sec = None
        if last_seen_at != datetime.min.replace(tzinfo=timezone.utc):
            heartbeat_age_sec = max((now_value - last_seen_at).total_seconds(), 0.0)

        heartbeat_interval_sec = max(
            self._safe_float(heartbeat.get("heartbeat_interval_sec"), WORKER_HEARTBEAT_INTERVAL_SEC),
            1.0,
        )
        online_threshold_sec = max(heartbeat_interval_sec * 2.5, heartbeat_interval_sec + 5.0)
        stale_threshold_sec = max(float(WORKER_JOB_TIMEOUT_SEC), online_threshold_sec + heartbeat_interval_sec)

        if raw_status in {"offline", "stopped", "error"}:
            health_status = "offline"
        elif heartbeat_age_sec is None:
            health_status = "offline"
        elif heartbeat_age_sec <= online_threshold_sec:
            health_status = "online"
        elif heartbeat_age_sec < stale_threshold_sec:
            health_status = "stale"
        else:
            health_status = "offline"

        normalized["health_status"] = health_status
        normalized["heartbeat_age_sec"] = heartbeat_age_sec
        normalized["heartbeat_interval_sec"] = heartbeat_interval_sec
        return normalized

    def _summarize_workers(self, rows: Any) -> tuple[list[dict[str, Any]], dict[str, int], str]:
        """Internal helper for summarize workers."""
        now = datetime.now(timezone.utc)
        workers: list[dict[str, Any]] = []
        counts = {"online": 0, "stale": 0, "offline": 0, "total": 0}
        latest_seen_at = datetime.min.replace(tzinfo=timezone.utc)
        latest_seen_text = ""
        for row in rows or []:
            if not isinstance(row, Mapping):
                continue
            worker = self._monitor_worker_health(row, now=now)
            workers.append(worker)
            counts["total"] += 1
            health_status = self._lower(worker.get("health_status"))
            if health_status in {"online", "stale", "offline"}:
                counts[health_status] += 1
            else:
                counts["offline"] += 1
            last_seen_text = str(worker.get("last_seen_at") or worker.get("updated_at") or "").strip()
            last_seen_at = parse_datetime_value(last_seen_text)
            if last_seen_at > latest_seen_at:
                latest_seen_at = last_seen_at
                latest_seen_text = last_seen_text
        return workers, counts, latest_seen_text

    def _normalize_hero_metric_entries(self, entries: Any) -> list[dict[str, Any]]:
        """Internal helper to normalize the hero metric entries."""
        metrics: list[dict[str, Any]] = []
        seen = set()
        if not isinstance(entries, list):
            return metrics
        for index, entry in enumerate(entries):
            if not isinstance(entry, Mapping):
                continue
            metric_id = str(entry.get("id") or entry.get("name") or f"metric_{index + 1}").strip()
            sql = str(entry.get("sql") or "").strip()
            if not metric_id or not sql:
                continue
            normalized_id = metric_id.lower()
            if normalized_id in seen:
                continue
            seen.add(normalized_id)
            metrics.append(
                {
                    "id": metric_id,
                    "label": str(entry.get("label") or metric_id).strip() or metric_id,
                    "sql": sql,
                    "params": entry.get("params"),
                    "value_key": str(entry.get("value_key") or entry.get("field") or "").strip(),
                    "table_name": str(entry.get("table_name") or "").strip(),
                    "available": bool(entry.get("available", True)),
                }
            )
        return metrics

    def _load_hero_metric_configs(
        self,
        dispatcher_settings: Mapping[str, Any],
        agent_meta: Mapping[str, Any],
        raw_config: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        """Internal helper to load the hero metric configs."""
        candidate_lists = [
            dispatcher_settings.get("hero_metrics"),
            dispatcher_settings.get("metrics"),
            raw_config.get("hero_metrics"),
            raw_config.get("metrics"),
            agent_meta.get("hero_metrics"),
            agent_meta.get("metrics"),
        ]
        agent_card = raw_config.get("agent_card")
        if isinstance(agent_card, Mapping):
            candidate_lists.append(agent_card.get("hero_metrics"))
            candidate_lists.append(agent_card.get("metrics"))
            card_meta = agent_card.get("meta")
            if isinstance(card_meta, Mapping):
                candidate_lists.append(card_meta.get("hero_metrics"))
                candidate_lists.append(card_meta.get("metrics"))
        for entries in candidate_lists:
            metrics = self._normalize_hero_metric_entries(entries)
            if metrics:
                return metrics
        return []

    def _runtime_summary(self) -> Dict[str, Any]:
        """Internal helper to return the runtime summary."""
        return {
            "boss_name": self.name,
            "agent_id": str(self.agent_id or ""),
            "plaza_url": self._normalize_url(self.plaza_url),
            "dispatcher_party": self.dispatcher_party,
            "dispatcher_address": self.dispatcher_address,
            "job_caps": [str(option.get("label") or option.get("id") or "") for option in self.job_options],
        }

    def _db_table_options(self) -> list[dict[str, str]]:
        """Internal helper to return the database table options."""
        return [{"name": table_name, "label": table_name, "description": ""} for table_name in MONITOR_TABLES]

    @staticmethod
    def _normalize_job_row(row: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to normalize the job row."""
        normalized = dict(row or {})
        targets = normalize_string_list(normalized.get("targets"))
        if not targets:
            targets = normalize_string_list(normalized.get("symbols"))
        normalized["targets"] = targets
        normalized["symbols"] = list(targets)
        normalized["capability_tags"] = normalize_string_list(normalized.get("capability_tags"))
        normalized["metadata"] = (
            dict(normalized.get("metadata") or {})
            if isinstance(normalized.get("metadata"), Mapping)
            else {}
        )
        payload = normalized.get("payload")
        if isinstance(payload, Mapping):
            normalized["payload"] = dict(payload)
        elif isinstance(payload, list):
            normalized["payload"] = list(payload)
        normalized["result_summary"] = (
            dict(normalized.get("result_summary") or {})
            if isinstance(normalized.get("result_summary"), Mapping)
            else {}
        )
        return normalized

    def _default_hero_metrics(self, *, dispatcher_address: str = "", status: str = "idle", error: str = "") -> Dict[str, Any]:
        """Internal helper to return the default hero metrics."""
        if self.hero_metric_configs:
            base_metrics = [
                {
                    "id": str(metric.get("id") or ""),
                    "label": str(metric.get("label") or metric.get("id") or ""),
                    "table_name": str(metric.get("table_name") or ""),
                    "count": 0,
                    "available": False,
                }
                for metric in self.hero_metric_configs
            ]
        else:
            base_metrics = [
                {"id": "dispatcher_workers", "label": "Workers", "table_name": TABLE_WORKERS, "count": 0, "available": False},
                {"id": "worker_history", "label": "Worker History", "table_name": TABLE_WORKER_HISTORY, "count": 0, "available": False},
                {"id": "result_rows", "label": "Result Rows", "table_name": TABLE_RESULT_ROWS, "count": 0, "available": False},
                {"id": "raw_payloads", "label": "Raw Payloads", "table_name": TABLE_RAW_PAYLOADS, "count": 0, "available": False},
            ]
        return {
            "status": str(status or "idle").strip().lower() or "idle",
            "dispatcher_address": str(dispatcher_address or "").strip(),
            "error": str(error or "").strip(),
            "last_refreshed_at": "",
            "metrics": base_metrics + [
                {"id": "queued_jobs", "label": "Queued Jobs", "count": 0, "available": False},
                {"id": "workers_online", "label": "Workers Online", "count": 0, "available": False},
            ],
        }

    def _run_configured_hero_metrics(self) -> list[dict[str, Any]]:
        """Internal helper to run the configured hero metrics."""
        results: list[dict[str, Any]] = []
        for metric in self.hero_metric_configs:
            metric_id = str(metric.get("id") or "").strip()
            label = str(metric.get("label") or metric_id).strip() or metric_id
            table_name = str(metric.get("table_name") or "").strip()
            query = str(metric.get("sql") or "").strip()
            params = metric.get("params")
            result = {
                "id": metric_id,
                "label": label,
                "table_name": table_name,
                "count": 0,
                "available": False,
            }
            if not query or self.pool is None or not hasattr(self.pool, "_Query"):
                results.append(result)
                continue
            try:
                rows = self.pool._Query(query, params)
                value = 0
                if rows:
                    first_row = rows[0]
                    if isinstance(first_row, Mapping):
                        value_key = str(metric.get("value_key") or "").strip()
                        if value_key and value_key in first_row:
                            value = first_row.get(value_key)
                        elif "count" in first_row:
                            value = first_row.get("count")
                        elif "value" in first_row:
                            value = first_row.get("value")
                        else:
                            value = next(iter(first_row.values()), 0)
                    elif isinstance(first_row, (list, tuple)):
                        value = first_row[0] if first_row else 0
                    else:
                        value = first_row
                result["count"] = self._safe_int(value)
                result["available"] = True
            except Exception:
                result["available"] = False
            results.append(result)
        return results

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
    def _extract_dispatcher_address(entry: Any) -> str:
        """Internal helper to extract the dispatcher address."""
        if not isinstance(entry, Mapping):
            return ""
        card = entry.get("card") if isinstance(entry.get("card"), Mapping) else {}
        for candidate in (entry.get("address"), card.get("address"), entry.get("pit_address")):
            normalized = str(candidate or "").strip().rstrip("/")
            if normalized:
                return normalized
        return ""

    @classmethod
    def _dispatcher_candidate_sort_key(cls, entry: Any) -> tuple[int, int, int, float]:
        """Internal helper to return the dispatcher candidate sort key."""
        if not isinstance(entry, Mapping):
            return (0, 0, 0, 0.0)
        card = entry.get("card") if isinstance(entry.get("card"), Mapping) else {}
        practices = card.get("practices") if isinstance(card.get("practices"), list) else []
        practice_ids = {
            str(practice.get("id") or "").strip().lower()
            for practice in practices
            if isinstance(practice, Mapping)
        }
        role = str(card.get("role") or entry.get("role") or "").strip().lower()
        tags = {str(tag or "").strip().lower() for tag in normalize_string_list(card.get("tags"))}
        try:
            last_active = float(entry.get("last_active") or 0.0)
        except (TypeError, ValueError):
            last_active = 0.0
        return (
            1 if role == "dispatcher" else 0,
            sum(1 for practice_id in DISPATCHER_DISCOVERY_PRACTICES if practice_id in practice_ids),
            1 if "dispatcher" in tags else 0,
            last_active,
        )

    def _normalize_dispatcher_entry(self, entry: Any) -> dict[str, Any]:
        """Internal helper to normalize the dispatcher entry."""
        card = entry.get("card") if isinstance(entry, Mapping) and isinstance(entry.get("card"), Mapping) else {}
        return {
            "agent_id": str(entry.get("agent_id") or card.get("agent_id") or "").strip(),
            "name": str(entry.get("name") or card.get("name") or "Dispatcher").strip() or "Dispatcher",
            "address": self._extract_dispatcher_address(entry),
            "party": self._normalize_party(card.get("party") or entry.get("party")),
            "role": str(card.get("role") or entry.get("role") or "").strip(),
            "description": str(card.get("description") or entry.get("description") or "").strip(),
            "last_active": self._safe_float(entry.get("last_active"), 0.0),
        }

    def _search_dispatcher_candidates(self) -> list[Any]:
        """Internal helper to search the dispatcher candidates."""
        if not self.plaza_url or not self.plaza_token:
            return []
        search_plans = (
            {"role": "dispatcher", "practice": "dispatcher-get-job", "pit_type": "Agent"},
            {"role": "dispatcher", "practice": "dispatcher-register-worker", "pit_type": "Agent"},
            {"role": "dispatcher", "pit_type": "Agent"},
            {"practice": "dispatcher-get-job", "pit_type": "Agent"},
            {"name": "Dispatcher", "pit_type": "Agent"},
        )
        candidates: dict[str, Any] = {}
        for search_params in search_plans:
            for entry in self.search(**search_params) or []:
                address = self._extract_dispatcher_address(entry)
                if not address:
                    continue
                candidate_key = str(entry.get("agent_id") or address)
                existing = candidates.get(candidate_key)
                if existing is None or self._dispatcher_candidate_sort_key(entry) > self._dispatcher_candidate_sort_key(existing):
                    candidates[candidate_key] = entry
        return sorted(candidates.values(), key=self._dispatcher_candidate_sort_key, reverse=True)

    def _plaza_dispatcher_directory(self, *, dispatcher_party: str = "") -> Dict[str, Any]:
        """Internal helper for Plaza dispatcher directory."""
        status = self._initial_plaza_status()
        selected_party = self._normalize_party(dispatcher_party or self.dispatcher_party or self.agent_card.get("party")) or DISPATCHER_PARTY
        selected_dispatcher_address = self._normalize_url(self.dispatcher_address)
        status["dispatcher_party"] = selected_party
        status["selected_dispatcher_address"] = selected_dispatcher_address
        status["parties"] = [selected_party] if selected_party else []
        status["dispatchers"] = []
        candidates = [self._normalize_dispatcher_entry(entry) for entry in self._search_dispatcher_candidates()]
        parties = sorted({entry["party"] for entry in candidates if entry.get("party")})
        if selected_party and selected_party not in parties:
            parties.insert(0, selected_party)
        filtered = [entry for entry in candidates if not selected_party or entry.get("party") == selected_party]
        filtered_addresses = {self._normalize_url(entry.get("address")) for entry in filtered if entry.get("address")}
        if selected_dispatcher_address and selected_dispatcher_address not in filtered_addresses:
            selected_dispatcher_address = ""
        if not selected_dispatcher_address and filtered:
            selected_dispatcher_address = self._normalize_url(filtered[0].get("address"))
        for entry in filtered:
            entry["selected"] = self._normalize_url(entry.get("address")) == selected_dispatcher_address
        status["parties"] = parties
        status["dispatchers"] = filtered
        status["selected_dispatcher_address"] = selected_dispatcher_address
        return status

    def _remember_dispatcher_address(self, address: Any) -> str:
        """Internal helper to remember the dispatcher address."""
        normalized = self._normalize_url(address)
        self.dispatcher_address = normalized
        meta = dict(self.agent_card.get("meta") or {})
        meta["dispatcher_address"] = normalized
        self.agent_card["meta"] = meta
        return normalized

    def _remember_dispatcher_party(self, dispatcher_party: Any) -> str:
        """Internal helper to remember the dispatcher party."""
        normalized = self._normalize_party(dispatcher_party) or DISPATCHER_PARTY
        self.dispatcher_party = normalized
        meta = dict(self.agent_card.get("meta") or {})
        meta["dispatcher_party"] = normalized
        self.agent_card["meta"] = meta
        return normalized

    def _ui_context(self, *, current_page: str = "issue") -> Dict[str, Any]:
        """Internal helper for UI context."""
        plaza_status = self._plaza_dispatcher_directory(dispatcher_party=self.dispatcher_party)
        initial_payload = {
            "current_page": current_page,
            "dispatcher_address": self.dispatcher_address,
            "dispatcher_party": self.dispatcher_party,
            "hero_metrics": self._default_hero_metrics(dispatcher_address=self.dispatcher_address),
            "job_options": self.job_options,
            "db_tables": self._db_table_options(),
            "plaza_status": plaza_status,
            "settings_defaults": self._settings_defaults(),
            "runtime_summary": self._runtime_summary(),
            "monitor_summary": None,
        }
        return {
            "application": "Dispatcher Boss",
            "asset_version": self._asset_version(),
            "initial_payload": initial_payload,
        }

    def _resolve_dispatcher_address(self, override: Any = None, *, dispatcher_party: str = "") -> str:
        """Internal helper to resolve the dispatcher address."""
        normalized = self._normalize_url(override or self.dispatcher_address)
        if normalized:
            return self._remember_dispatcher_address(normalized)
        directory = self._plaza_dispatcher_directory(dispatcher_party=dispatcher_party or self.dispatcher_party)
        discovered = self._normalize_url(directory.get("selected_dispatcher_address"))
        if discovered:
            return self._remember_dispatcher_address(discovered)
        raise ValueError("dispatcher_address is required.")

    def _call_dispatcher(self, practice_id: str, payload: Any, *, dispatcher_address: str = "") -> Any:
        """Internal helper for call dispatcher."""
        resolved = self._resolve_dispatcher_address(dispatcher_address)
        return self.UsePractice(practice_id, payload, pit_address=resolved)

    def _list_dispatcher_tables(self, dispatcher_address: str) -> Dict[str, Any]:
        """Internal helper to list the dispatcher tables."""
        return self._call_dispatcher("dispatcher-db-list-tables", {}, dispatcher_address=dispatcher_address)

    def _preview_dispatcher_table(
        self,
        dispatcher_address: str,
        table_name: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Internal helper to preview the dispatcher table."""
        return self._call_dispatcher(
            "dispatcher-db-preview-table",
            {"table_name": table_name, "limit": limit, "offset": offset},
            dispatcher_address=dispatcher_address,
        )

    def _iter_dispatcher_table_rows(
        self,
        dispatcher_address: str,
        table_name: str,
        *,
        page_size: int = 500,
        max_pages: int | None = None,
    ):
        """Internal helper to return the iter dispatcher table rows."""
        normalized_page_size = max(1, min(int(page_size), 500))
        offset = 0
        page_count = 0
        total_rows = None
        while True:
            preview = self._preview_dispatcher_table(
                dispatcher_address,
                table_name,
                limit=normalized_page_size,
                offset=offset,
            )
            rows = list(preview.get("rows") or [])
            if total_rows is None:
                total_rows = self._safe_int(preview.get("total_rows") or preview.get("count"), 0)
            if not rows:
                break
            for row in rows:
                yield row
            offset += len(rows)
            page_count += 1
            if len(rows) < normalized_page_size:
                break
            if total_rows and offset >= total_rows:
                break
            if max_pages is not None and page_count >= max(1, int(max_pages)):
                break

    def _monitor_snapshot(self, *, dispatcher_address: str) -> Dict[str, Any]:
        """Internal helper to return the monitor snapshot."""
        tables_response = self._list_dispatcher_tables(dispatcher_address)
        available_tables = {
            str(entry.get("name") or "")
            for entry in tables_response.get("tables", [])
            if isinstance(entry, Mapping)
        }
        previews: dict[str, Any] = {}
        metrics: list[dict[str, Any]] = []
        for table_name in MONITOR_TABLES:
            if table_name not in available_tables:
                previews[table_name] = {
                    "status": "missing",
                    "table_name": table_name,
                    "columns": [],
                    "rows": [],
                    "count": 0,
                    "total_rows": 0,
                }
                metrics.append({"table_name": table_name, "count": 0, "available": False})
                continue
            preview_limit = 200 if table_name in {TABLE_JOBS, TABLE_WORKERS} else 20
            preview = self._preview_dispatcher_table(dispatcher_address, table_name, limit=preview_limit, offset=0)
            previews[table_name] = preview
            metrics.append(
                {
                    "table_name": table_name,
                    "count": int(preview.get("total_rows") or preview.get("count") or 0),
                    "available": True,
                }
            )
        return {
            "status": "success",
            "dispatcher_address": dispatcher_address,
            "tables": previews,
            "metrics": metrics,
        }

    def _hero_metrics_summary(self, *, dispatcher_address: str) -> Dict[str, Any]:
        """Internal helper to return the hero metrics summary."""
        if self.hero_metric_configs:
            configured_metrics = self._run_configured_hero_metrics()
            snapshot = self._monitor_snapshot(dispatcher_address=dispatcher_address)
            jobs_preview = snapshot.get("tables", {}).get(TABLE_JOBS, {})
            workers_preview = snapshot.get("tables", {}).get(TABLE_WORKERS, {})
            queued_jobs = 0
            for row in jobs_preview.get("rows", []) or []:
                status = self._lower(row.get("status"))
                if status in {"queued", "retry", "paused"}:
                    queued_jobs += 1
            _, worker_counts, _ = self._summarize_workers(workers_preview.get("rows", []) or [])
            return {
                "status": "success",
                "dispatcher_address": dispatcher_address,
                "error": "",
                "last_refreshed_at": "",
                "metrics": configured_metrics + [
                    {"id": "queued_jobs", "label": "Queued Jobs", "count": queued_jobs, "available": True},
                    {"id": "workers_online", "label": "Workers Online", "count": worker_counts.get("online", 0), "available": True},
                ],
            }
        snapshot = self._monitor_snapshot(dispatcher_address=dispatcher_address)
        metrics_by_name = {str(metric.get("table_name") or ""): metric for metric in snapshot.get("metrics", [])}
        jobs_preview = snapshot.get("tables", {}).get(TABLE_JOBS, {})
        workers_preview = snapshot.get("tables", {}).get(TABLE_WORKERS, {})
        queued_jobs = 0
        _, worker_counts, _ = self._summarize_workers(workers_preview.get("rows", []) or [])
        for row in jobs_preview.get("rows", []) or []:
            status = self._lower(row.get("status"))
            if status in {"queued", "retry", "paused"}:
                queued_jobs += 1
        return {
            "status": "success",
            "dispatcher_address": dispatcher_address,
            "error": "",
            "last_refreshed_at": "",
            "metrics": [
                {
                    "id": "dispatcher_workers",
                    "label": "Workers",
                    "table_name": TABLE_WORKERS,
                    "count": self._safe_int(metrics_by_name.get(TABLE_WORKERS, {}).get("count")),
                    "available": TABLE_WORKERS in snapshot.get("tables", {}),
                },
                {
                    "id": "worker_history",
                    "label": "Worker History",
                    "table_name": TABLE_WORKER_HISTORY,
                    "count": self._safe_int(metrics_by_name.get(TABLE_WORKER_HISTORY, {}).get("count")),
                    "available": TABLE_WORKER_HISTORY in snapshot.get("tables", {}),
                },
                {
                    "id": "result_rows",
                    "label": "Result Rows",
                    "table_name": TABLE_RESULT_ROWS,
                    "count": self._safe_int(metrics_by_name.get(TABLE_RESULT_ROWS, {}).get("count")),
                    "available": TABLE_RESULT_ROWS in snapshot.get("tables", {}),
                },
                {
                    "id": "raw_payloads",
                    "label": "Raw Payloads",
                    "table_name": TABLE_RAW_PAYLOADS,
                    "count": self._safe_int(metrics_by_name.get(TABLE_RAW_PAYLOADS, {}).get("count")),
                    "available": TABLE_RAW_PAYLOADS in snapshot.get("tables", {}),
                },
                {"id": "queued_jobs", "label": "Queued Jobs", "count": queued_jobs, "available": True},
                {"id": "workers_online", "label": "Workers Online", "count": worker_counts.get("online", 0), "available": True},
            ],
        }

    def _list_jobs(self, *, dispatcher_address: str, status: str = "", capability: str = "", search: str = "") -> Dict[str, Any]:
        """Internal helper to list the jobs."""
        normalized_status = self._lower(status)
        normalized_capability = self._lower(capability)
        normalized_search = self._lower(search)
        filtered = []
        needs_deep_scan = bool(normalized_status or normalized_capability or normalized_search)
        rows = (
            self._iter_dispatcher_table_rows(dispatcher_address, TABLE_JOBS, page_size=500, max_pages=100 if needs_deep_scan else 1)
        )
        for row in rows:
            row = self._normalize_job_row(row)
            row_status = self._lower(row.get("status"))
            capability_name = str(row.get("required_capability") or row.get("job_name") or "").strip()
            searchable = " ".join(
                str(row.get(key) or "")
                for key in ("id", "required_capability", "job_name", "claimed_by", "target_table", "source_url")
            ).lower()
            searchable = f"{searchable} {' '.join(row.get('targets') or [])}".strip()
            if normalized_status and row_status != normalized_status:
                continue
            if normalized_capability and normalized_capability not in capability_name.lower():
                continue
            if normalized_search and normalized_search not in searchable:
                continue
            filtered.append(row)
            if len(filtered) >= 500:
                break
        return {"status": "success", "dispatcher_address": dispatcher_address, "jobs": filtered}

    def _job_detail(self, *, dispatcher_address: str, job_id: str) -> Dict[str, Any]:
        """Internal helper to return the job detail."""
        normalized_job_id = str(job_id or "").strip()
        job = next(
            (
                self._normalize_job_row(row)
                for row in self._iter_dispatcher_table_rows(dispatcher_address, TABLE_JOBS, page_size=500, max_pages=100)
                if str(row.get("id") or "") == normalized_job_id
            ),
            None,
        )
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        raw_records = []
        for record in self._iter_dispatcher_table_rows(dispatcher_address, TABLE_RAW_PAYLOADS, page_size=500, max_pages=100):
            if str(record.get("job_id") or "") == normalized_job_id:
                raw_records.append(record)
        latest_heartbeat = {}
        for record in self._iter_dispatcher_table_rows(dispatcher_address, TABLE_WORKER_HISTORY, page_size=500, max_pages=100):
            related_job_id = str(record.get("job_id") or "")
            if related_job_id == normalized_job_id:
                latest_heartbeat = record
                break
        return {
            "status": "success",
            "dispatcher_address": dispatcher_address,
            "job": job,
            "raw_records": raw_records,
            "latest_heartbeat": latest_heartbeat,
        }

    def _monitor_summary(self, *, dispatcher_address: str) -> Dict[str, Any]:
        """Internal helper to return the monitor summary."""
        snapshot = self._monitor_snapshot(dispatcher_address=dispatcher_address)
        jobs = [self._normalize_job_row(row) for row in (snapshot.get("tables", {}).get(TABLE_JOBS, {}).get("rows") or []) if isinstance(row, Mapping)]
        workers, worker_counts, last_worker_seen = self._summarize_workers(
            snapshot.get("tables", {}).get(TABLE_WORKERS, {}).get("rows") or []
        )
        worker_history = list(snapshot.get("tables", {}).get(TABLE_WORKER_HISTORY, {}).get("rows") or [])
        queued = sum(1 for row in jobs if self._lower(row.get("status")) in {"queued", "retry", "paused"})
        attention = sum(1 for row in jobs if self._lower(row.get("status")) in {"failed", "stopped", "cancelled"})
        active_workers = int(worker_counts.get("online", 0))
        jobs_by_worker: dict[str, list[dict[str, Any]]] = {}
        for job in jobs:
            worker_id = str(job.get("claimed_by") or "").strip()
            if worker_id:
                jobs_by_worker.setdefault(worker_id, []).append(job)
        for worker in workers:
            worker_id = str(worker.get("worker_id") or worker.get("id") or worker.get("name") or "").strip()
            worker["active_jobs"] = jobs_by_worker.get(worker_id, [])
            worker["active_job_ids"] = [str(job.get("id") or "") for job in worker["active_jobs"] if str(job.get("id") or "")]
        return {
            "status": "success",
            "dispatcher_address": dispatcher_address,
            "dispatcher": {
                "connection_status": "connected",
                "address": dispatcher_address,
                "queued_jobs": queued,
                "active_workers": active_workers,
                "total_workers": int(worker_counts.get("total", len(workers))),
                "stale_workers": int(worker_counts.get("stale", 0)),
                "attention_count": attention,
                "job_counts": {"queued": queued, "total": len(jobs)},
                "worker_counts": {
                    "online": int(worker_counts.get("online", 0)),
                    "stale": int(worker_counts.get("stale", 0)),
                    "offline": int(worker_counts.get("offline", 0)),
                    "total": int(worker_counts.get("total", len(workers))),
                },
                "history_count": len(worker_history),
                "last_worker_seen": last_worker_seen,
                "tables": snapshot.get("tables", {}),
            },
            "workers": workers,
        }

    def _worker_history(self, *, dispatcher_address: str, worker_id: str, limit: int = 10) -> Dict[str, Any]:
        """Internal helper to return the worker history."""
        history = self._preview_dispatcher_table(dispatcher_address, TABLE_WORKER_HISTORY, limit=200, offset=0).get("rows") or []
        jobs = []
        for row in history:
            row_worker_id = str(row.get("worker_id") or row.get("claimed_by") or row.get("name") or "").strip()
            if row_worker_id == worker_id:
                jobs.append(row)
        return {
            "status": "success",
            "dispatcher_address": dispatcher_address,
            "worker_id": worker_id,
            "worker": {"worker_id": worker_id, "name": worker_id},
            "jobs": jobs[:limit],
            "count": len(jobs),
            "limit": limit,
        }

    @staticmethod
    def _normalize_schedule_row(row: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to normalize the schedule row."""
        normalized = dict(row or {})
        normalized["name"] = str(normalized.get("name") or "").strip()
        normalized["status"] = str(normalized.get("status") or "scheduled").strip().lower() or "scheduled"
        normalized["dispatcher_address"] = str(normalized.get("dispatcher_address") or "").strip()
        normalized["repeat_frequency"] = DispatcherBossAgent._normalize_repeat_frequency(normalized.get("repeat_frequency"))
        normalized["schedule_timezone"] = DispatcherBossAgent._normalize_schedule_timezone(normalized.get("schedule_timezone"))
        normalized["schedule_times"] = DispatcherBossAgent._normalize_schedule_times(
            normalized.get("schedule_times") or normalized.get("schedule_time")
        )
        normalized["schedule_time"] = normalized["schedule_times"][0] if normalized["schedule_times"] else ""
        normalized["schedule_weekdays"] = DispatcherBossAgent._normalize_schedule_weekdays(normalized.get("schedule_weekdays"))
        normalized["schedule_days_of_month"] = DispatcherBossAgent._normalize_schedule_days_of_month(
            normalized.get("schedule_days_of_month") or normalized.get("schedule_day_of_month")
        )
        normalized["schedule_day_of_month"] = (
            normalized["schedule_days_of_month"][0] if normalized["schedule_days_of_month"] else None
        )
        targets = normalize_string_list(normalized.get("targets"))
        if not targets:
            targets = normalize_string_list(normalized.get("symbols"))
        normalized["targets"] = targets
        normalized["symbols"] = list(targets)
        normalized["required_capability"] = str(normalized.get("required_capability") or "").strip()
        payload = normalized.get("payload")
        if not isinstance(payload, (dict, list)):
            payload = {}
        normalized["payload"] = payload
        normalized["target_table"] = str(normalized.get("target_table") or "").strip()
        normalized["source_url"] = str(normalized.get("source_url") or "").strip()
        parse_rules = normalized.get("parse_rules")
        if not isinstance(parse_rules, (dict, list)):
            parse_rules = {}
        normalized["parse_rules"] = parse_rules
        normalized["capability_tags"] = normalize_string_list(normalized.get("capability_tags"))
        normalized["job_type"] = str(normalized.get("job_type") or "run").strip() or "run"
        try:
            normalized["priority"] = int(normalized.get("priority") or 100)
        except (TypeError, ValueError):
            normalized["priority"] = 100
        normalized["premium"] = bool(normalized.get("premium"))
        normalized["metadata"] = (
            dict(normalized.get("metadata") or {})
            if isinstance(normalized.get("metadata"), Mapping)
            else {}
        )
        normalized["scheduled_for"] = str(normalized.get("scheduled_for") or "").strip()
        try:
            normalized["max_attempts"] = max(int(normalized.get("max_attempts") or 3), 1)
        except (TypeError, ValueError):
            normalized["max_attempts"] = 3
        normalized["dispatcher_job_id"] = str(normalized.get("dispatcher_job_id") or "").strip()
        normalized["issued_at"] = str(normalized.get("issued_at") or "").strip()
        normalized["last_attempted_at"] = str(normalized.get("last_attempted_at") or "").strip()
        normalized["last_error"] = str(normalized.get("last_error") or "").strip()
        try:
            normalized["issue_attempts"] = max(int(normalized.get("issue_attempts") or 0), 0)
        except (TypeError, ValueError):
            normalized["issue_attempts"] = 0
        normalized["created_at"] = str(normalized.get("created_at") or "").strip()
        normalized["updated_at"] = str(normalized.get("updated_at") or normalized.get("created_at") or "").strip()
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
        storage_row.pop("symbols", None)
        for field_name in SCHEDULE_TIMESTAMP_FIELDS:
            value = storage_row.get(field_name)
            if isinstance(value, str) and not value.strip():
                storage_row[field_name] = None
        if not self.pool._Insert(TABLE_SCHEDULED_JOBS, storage_row):
            raise RuntimeError("Failed to persist scheduled dispatcher job.")
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
            "targets": list(normalized.get("targets") or []),
            "payload": normalized.get("payload"),
            "target_table": str(normalized.get("target_table") or ""),
            "source_url": str(normalized.get("source_url") or ""),
            "parse_rules": normalized.get("parse_rules"),
            "capability_tags": list(normalized.get("capability_tags") or []),
            "job_type": str(normalized.get("job_type") or "run"),
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
                        " ".join(row.get("targets") or []),
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
            "id": f"dispatcher-boss-schedule:{time.time_ns()}",
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
            "targets": list(payload.get("targets") or []),
            "payload": payload.get("payload"),
            "target_table": str(payload.get("target_table") or ""),
            "source_url": str(payload.get("source_url") or ""),
            "parse_rules": payload.get("parse_rules"),
            "capability_tags": list(payload.get("capability_tags") or []),
            "job_type": str(payload.get("job_type") or "run"),
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
        """Handle issue scheduled job for the dispatcher boss agent."""
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
                submission = self._call_dispatcher(
                    "dispatcher-submit-job",
                    payload,
                    dispatcher_address=dispatcher_address,
                )
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
        """Handle process due schedules for the dispatcher boss agent."""
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
                self.logger.exception("Failed issuing scheduled dispatcher job %s: %s", schedule_id, exc)
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

    def get_schedule_history_via_dispatcher(self, schedule_id: str, *, limit: int = 20) -> Dict[str, Any]:
        """Return the schedule history via dispatcher."""
        schedule = self._get_schedule_row(schedule_id)
        normalized_schedule_id = str(schedule.get("id") or "").strip()
        if not normalized_schedule_id:
            raise ValueError("schedule_id is required.")

        resolved_dispatcher_address = self._resolve_dispatcher_address(str(schedule.get("dispatcher_address") or ""))
        rows = [
            self._normalize_job_row(row)
            for row in self._iter_dispatcher_table_rows(resolved_dispatcher_address, TABLE_JOBS, page_size=500, max_pages=100)
        ]
        latest_rows_by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            row_id = str(row.get("id") or "").strip()
            if not row_id:
                continue
            existing = latest_rows_by_id.get(row_id)
            if existing is None or parse_datetime_value(row.get("updated_at") or row.get("created_at")) > parse_datetime_value(existing.get("updated_at") or existing.get("created_at")):
                latest_rows_by_id[row_id] = row

        filtered_rows = []
        for row in latest_rows_by_id.values():
            metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), Mapping) else {}
            if str(metadata.get("boss_schedule_id") or "").strip() == normalized_schedule_id:
                filtered_rows.append(row)
        filtered_rows.sort(
            key=lambda row: (
                parse_datetime_value(row.get("updated_at") or row.get("created_at")),
                parse_datetime_value(row.get("created_at")),
                str(row.get("id") or ""),
            ),
            reverse=True,
        )

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
        return self._call_dispatcher("dispatcher-submit-job", payload, dispatcher_address=dispatcher_address)

    def query_db_via_dispatcher(self, request: BossDbQueryRequest) -> Dict[str, Any]:
        """Query the database via dispatcher."""
        dispatcher_address = self._resolve_dispatcher_address(request.dispatcher_address)
        result = self._call_dispatcher(
            "dispatcher-db-query",
            {
                "sql": str(request.sql or "").strip(),
                "params": request.params,
                "limit": int(request.limit),
            },
            dispatcher_address=dispatcher_address,
        )
        payload = dict(result or {}) if isinstance(result, Mapping) else {"status": "success"}
        payload.setdefault("dispatcher_address", dispatcher_address)
        return payload

    def _control_job(self, *, dispatcher_address: str, job_id: str, action: str, reason: str = "") -> Dict[str, Any]:
        """Internal helper to control the job."""
        result = self._call_dispatcher(
            "dispatcher-control-job",
            {"job_id": job_id, "action": action, "reason": reason},
            dispatcher_address=dispatcher_address,
        )
        return {
            "status": "success",
            "dispatcher_address": dispatcher_address,
            "job": result.get("job") if isinstance(result, Mapping) else result,
        }

    def _update_runtime_settings(self, settings: BossSettingsRequest) -> Dict[str, Any]:
        """Internal helper to update the runtime settings."""
        self._remember_dispatcher_address(settings.dispatcher_address)
        self._remember_dispatcher_party(settings.dispatcher_party or self.dispatcher_party)
        self.monitor_refresh_sec = self._coerce_monitor_refresh_sec(settings.monitor_refresh_sec)
        normalized_plaza_url = self._normalize_url(settings.plaza_url)
        self.plaza_url = normalized_plaza_url
        meta = dict(self.agent_card.get("meta") or {})
        meta["dispatcher_address"] = self.dispatcher_address
        meta["dispatcher_party"] = self.dispatcher_party
        self.agent_card["meta"] = meta
        return {
            "status": "success",
            "settings": self._settings_defaults(),
            "runtime_summary": self._runtime_summary(),
        }

    def _connect_plaza(self, settings: BossSettingsRequest) -> Dict[str, Any]:
        """Internal helper to connect the Plaza."""
        response = self._update_runtime_settings(settings)
        if self.plaza_url:
            self.register()
        plaza_status = self._plaza_dispatcher_directory(dispatcher_party=self.dispatcher_party)
        selected_dispatcher_address = self._normalize_url(plaza_status.get("selected_dispatcher_address"))
        if selected_dispatcher_address:
            self._remember_dispatcher_address(selected_dispatcher_address)
            response["settings"] = self._settings_defaults()
            response["runtime_summary"] = self._runtime_summary()
        response["plaza_status"] = plaza_status
        response["dispatcher_address"] = self.dispatcher_address
        return response

    def _setup_routes(self) -> None:
        """Internal helper to set up the routes."""
        def render_page(request: Request, page_name: str):
            """Render the page."""
            context = self._ui_context(current_page=page_name)
            context["request"] = request
            return self.templates.TemplateResponse("index.html", context)

        @self.app.get("/")
        async def boss_home(request: Request):
            """Route handler for GET /."""
            return render_page(request, "issue")

        @self.app.get("/monitor", include_in_schema=False)
        async def boss_monitor_page(request: Request):
            """Route handler for GET /monitor."""
            return render_page(request, "monitor")

        @self.app.get("/schedule", include_in_schema=False)
        async def boss_schedule_page(request: Request):
            """Route handler for GET /schedule."""
            return render_page(request, "schedule")

        @self.app.get("/jobs", include_in_schema=False)
        async def boss_jobs_page(request: Request):
            """Route handler for GET /jobs."""
            return render_page(request, "monitor")

        @self.app.get("/settings", include_in_schema=False)
        async def boss_settings_page(request: Request):
            """Route handler for GET /settings."""
            return render_page(request, "settings")

        @self.app.get("/db", include_in_schema=False)
        async def boss_db_page(request: Request):
            """Route handler for GET /db."""
            return render_page(request, "db")

        @self.app.get("/api/context")
        async def boss_context():
            """Route handler for GET /api/context."""
            return self._ui_context(current_page="issue")

        @self.app.get("/api/boss/config")
        async def boss_config():
            """Route handler for GET /api/boss/config."""
            return {"status": "success", "settings": self._settings_defaults(), "runtime_summary": self._runtime_summary()}

        @self.app.get("/api/config")
        async def config_get():
            """Route handler for GET /api/config."""
            return {"status": "success", "settings": self._settings_defaults(), "runtime_summary": self._runtime_summary()}

        @self.app.post("/api/config")
        async def config_post(payload: BossSettingsRequest):
            """Route handler for POST /api/config."""
            try:
                return await run_in_threadpool(self._update_runtime_settings, payload)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/plaza/status")
        async def plaza_status(dispatcher_party: str = ""):
            """Route handler for GET /api/plaza/status."""
            return await run_in_threadpool(
                self._plaza_dispatcher_directory,
                dispatcher_party=dispatcher_party or self.dispatcher_party,
            )

        @self.app.post("/api/plaza/connect")
        async def plaza_connect(payload: BossSettingsRequest):
            """Route handler for POST /api/plaza/connect."""
            try:
                settings = BossSettingsRequest(
                    dispatcher_address=payload.dispatcher_address or self.dispatcher_address,
                    dispatcher_party=payload.dispatcher_party or self.dispatcher_party,
                    plaza_url=payload.plaza_url or self.plaza_url,
                    monitor_refresh_sec=self.monitor_refresh_sec if payload.monitor_refresh_sec in (None, "") else payload.monitor_refresh_sec,
                )
                return await run_in_threadpool(self._connect_plaza, settings)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/metrics/summary")
        async def metrics_summary(dispatcher_address: str = ""):
            """Route handler for GET /api/metrics/summary."""
            try:
                return await run_in_threadpool(
                    self._hero_metrics_summary,
                    dispatcher_address=self._resolve_dispatcher_address(dispatcher_address),
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/monitor")
        async def boss_monitor(dispatcher_address: str = ""):
            """Route handler for GET /api/monitor."""
            try:
                return await run_in_threadpool(
                    self._monitor_snapshot,
                    dispatcher_address=self._resolve_dispatcher_address(dispatcher_address),
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/monitor/summary")
        async def boss_monitor_summary(dispatcher_address: str = ""):
            """Route handler for GET /api/monitor/summary."""
            try:
                return await run_in_threadpool(
                    self._monitor_summary,
                    dispatcher_address=self._resolve_dispatcher_address(dispatcher_address),
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/jobs")
        async def boss_jobs(dispatcher_address: str = "", status: str = "", capability: str = "", search: str = ""):
            """Route handler for GET /api/jobs."""
            try:
                return await run_in_threadpool(
                    self._list_jobs,
                    dispatcher_address=self._resolve_dispatcher_address(dispatcher_address),
                    status=status,
                    capability=capability,
                    search=search,
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/jobs/{job_id}")
        async def boss_job_detail(job_id: str, dispatcher_address: str = ""):
            """Route handler for GET /api/jobs/{job_id}."""
            try:
                return await run_in_threadpool(
                    self._job_detail,
                    dispatcher_address=self._resolve_dispatcher_address(dispatcher_address),
                    job_id=job_id,
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/jobs")
        async def boss_submit_job(payload: BossSubmitJobRequest):
            """Route handler for POST /api/jobs."""
            try:
                result = await run_in_threadpool(self.submit_job_via_dispatcher, payload)
                resolved_dispatcher_address = self._resolve_dispatcher_address(payload.dispatcher_address)
                job_payload = result.get("job") if isinstance(result, Mapping) else result
                if isinstance(job_payload, Mapping):
                    job_payload = self._normalize_job_row(job_payload)
                return {
                    "status": "success",
                    "dispatcher_address": resolved_dispatcher_address,
                    "job": job_payload,
                }
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/jobs/submit")
        async def boss_submit_job_alias(payload: BossSubmitJobRequest):
            """Route handler for POST /api/jobs/submit."""
            return await boss_submit_job(payload)

        @self.app.post("/api/jobs/{job_id}/control")
        async def boss_control_job(job_id: str, payload: BossJobControlRequest):
            """Route handler for POST /api/jobs/{job_id}/control."""
            try:
                return await run_in_threadpool(
                    self._control_job,
                    dispatcher_address=self._resolve_dispatcher_address(payload.dispatcher_address),
                    job_id=job_id,
                    action=payload.action,
                    reason=payload.reason,
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/workers/{worker_id}/history")
        async def boss_worker_history(worker_id: str, dispatcher_address: str = "", limit: int = 10):
            """Route handler for GET /api/workers/{worker_id}/history."""
            try:
                return await run_in_threadpool(
                    self._worker_history,
                    dispatcher_address=self._resolve_dispatcher_address(dispatcher_address),
                    worker_id=worker_id,
                    limit=limit,
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

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
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/schedules")
        async def boss_create_schedule(payload: BossScheduleJobRequest):
            """Route handler for POST /api/schedules."""
            try:
                return await run_in_threadpool(self.create_schedule, payload)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

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
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/schedules/{schedule_id}/control")
        async def boss_schedule_control(schedule_id: str, payload: BossScheduleControlRequest):
            """Route handler for POST /api/schedules/{schedule_id}/control."""
            normalized_action = str(payload.action or "").strip().lower()
            try:
                if normalized_action == "issue":
                    result = await run_in_threadpool(self.issue_scheduled_job, schedule_id, force_now=True)
                elif normalized_action == "delete":
                    result = await run_in_threadpool(self.delete_schedule, schedule_id)
                else:
                    raise HTTPException(status_code=400, detail="action must be one of: issue, delete.")
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {"status": "success", "control": result}

        @self.app.get("/api/db/tables")
        async def boss_db_tables(dispatcher_address: str = ""):
            """Route handler for GET /api/db/tables."""
            try:
                response = await run_in_threadpool(
                    self._list_dispatcher_tables,
                    self._resolve_dispatcher_address(dispatcher_address),
                )
                return {
                    "status": "success",
                    "dispatcher_address": self._resolve_dispatcher_address(dispatcher_address),
                    "tables": response.get("tables", []),
                }
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/db/table")
        async def boss_db_table(dispatcher_address: str = "", table_name: str = "", limit: int = 100, offset: int = 0):
            """Route handler for GET /api/db/table."""
            try:
                resolved_dispatcher_address = self._resolve_dispatcher_address(dispatcher_address)
                preview = await run_in_threadpool(
                    self._preview_dispatcher_table,
                    resolved_dispatcher_address,
                    table_name,
                    limit=limit,
                    offset=offset,
                )
                preview["dispatcher_address"] = resolved_dispatcher_address
                return preview
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/db/query")
        async def boss_db_query(payload: BossDbQueryRequest):
            """Route handler for POST /api/db/query."""
            try:
                return await run_in_threadpool(self.query_db_via_dispatcher, payload)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/settings")
        async def boss_settings(payload: BossSettingsRequest):
            """Route handler for POST /api/settings."""
            try:
                return await run_in_threadpool(self._update_runtime_settings, payload)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc


def create_demo_app() -> DispatcherBossAgent:
    """Create the demo app."""
    return DispatcherBossAgent()
