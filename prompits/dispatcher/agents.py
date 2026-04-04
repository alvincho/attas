"""
Agent implementations for `prompits.dispatcher.agents`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the dispatcher package
coordinates job routing, worker selection, and queue management.

Core types exposed here include `DispatcherAgent`, `DispatcherJobStopRequested`, and
`DispatcherWorkerAgent`, which carry the main behavior or state managed by this module.
"""

from __future__ import annotations

import json
import os
import platform
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

from prompits.agents.standby import StandbyAgent

from prompits.dispatcher.jobcap import JobCap, load_job_cap_map
from prompits.dispatcher.models import JobDetail, JobResult
from prompits.dispatcher.practices import (
    ControlDispatcherJobPractice,
    GetDispatcherJobPractice,
    ListDispatcherDbTablesPractice,
    PostDispatcherJobResultPractice,
    PreviewDispatcherDbTablePractice,
    QueryDispatcherDbPractice,
    RegisterDispatcherWorkerPractice,
    ReportDispatcherJobPractice,
    SubmitDispatcherJobPractice,
)
from prompits.dispatcher.runtime import (
    build_dispatch_job,
    build_id,
    build_raw_payload_row,
    build_result_row,
    build_worker_history_entry,
    build_worker_registration,
    coerce_job_detail,
    coerce_job_result,
    coerce_json_object,
    coerce_json_payload,
    coerce_record_list,
    job_is_ready,
    job_matches_capabilities,
    job_sort_key,
    normalize_capabilities,
    normalize_string_list,
    normalize_target,
    parse_datetime_value,
    prepare_table_records,
    read_dispatcher_config,
    utcnow_iso,
)
from prompits.dispatcher.schema import (
    CAPABILITY_TO_TABLE,
    TABLE_JOBS,
    TABLE_RAW_PAYLOADS,
    TABLE_RESULT_ROWS,
    TABLE_WORKER_HISTORY,
    TABLE_WORKERS,
    dispatcher_table_schema_map,
    ensure_dispatcher_tables,
    jobs_schema_dict,
)


DISPATCHER_DIRECT_TOKEN = "dispatcher-local-direct-token"
DISPATCHER_PARTY = "Prompits"
WORKER_HEARTBEAT_INTERVAL_SEC = 15.0
WORKER_JOB_TIMEOUT_SEC = 180.0
FAILED_REISSUE_PRIORITY = 1000
STALE_RECOVERY_INTERVAL_SEC = 30.0
JOB_CLAIM_CANDIDATE_LIMIT = 200
_POSTGRES_ENV_VARS = (
    "POSTGRES_DSN",
    "DATABASE_URL",
    "SUPABASE_DB_URL",
    "PGHOST",
    "PGPORT",
    "PGDATABASE",
    "PGUSER",
    "PGPASSWORD",
)


class DispatcherJobStopRequested(RuntimeError):
    """Exception raised when a dispatcher job stop is requested."""
    def __init__(self, job_id: str, reason: str = ""):
        """Initialize the dispatcher job stop requested."""
        message = f"Dispatcher job {job_id} was stopped."
        normalized_reason = str(reason or "").strip()
        if normalized_reason:
            message = f"{message} {normalized_reason}"
        super().__init__(message)
        self.job_id = str(job_id or "").strip()
        self.reason = normalized_reason


def _merge_tags(*groups: Any) -> list[str]:
    """Internal helper to merge the tags."""
    tags: list[str] = []
    for group in groups:
        for tag in normalize_string_list(group):
            if tag not in tags:
                tags.append(tag)
    return tags


def _resolve_executable_worker_capabilities(capabilities: Any, metadata: Any = None) -> list[str]:
    """Internal helper to resolve the executable worker capabilities."""
    advertised = normalize_capabilities(capabilities)
    if "*" in advertised:
        return advertised
    if not isinstance(metadata, Mapping):
        return advertised

    raw_job_capabilities = metadata.get("job_capabilities")
    if not isinstance(raw_job_capabilities, Sequence) or isinstance(raw_job_capabilities, (str, bytes, bytearray)):
        return advertised

    executable_names: list[str] = []
    for entry in raw_job_capabilities:
        if isinstance(entry, Mapping):
            raw_name = str(entry.get("name") or entry.get("capability") or "").strip()
        else:
            raw_name = str(entry or "").strip()
        normalized_name = raw_name.lower()
        if normalized_name and normalized_name not in executable_names:
            executable_names.append(normalized_name)
    if not executable_names:
        return advertised
    return [capability for capability in advertised if capability in executable_names]


def _resolve_dispatcher_settings(config: Any, config_path: Any = None) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Internal helper to resolve the dispatcher settings."""
    loaded = read_dispatcher_config(config_path or config)
    dispatcher_settings = loaded.get("dispatcher") if isinstance(loaded.get("dispatcher"), Mapping) else {}
    return loaded, dict(dispatcher_settings or {})


def _resolve_party(
    loaded_config: Mapping[str, Any] | None = None,
    agent_card: Mapping[str, Any] | None = None,
) -> str:
    """Internal helper to resolve the party."""
    return (
        str((loaded_config or {}).get("party") or (agent_card or {}).get("party") or DISPATCHER_PARTY).strip()
        or DISPATCHER_PARTY
    )


def _table_for_job(required_capability: str, target_table: str = "") -> str:
    """Internal helper to return the table for the job."""
    explicit = str(target_table or "").strip()
    if explicit:
        return explicit
    return CAPABILITY_TO_TABLE.get(str(required_capability or "").strip().lower(), "")


def _job_state_sort_key(row: Mapping[str, Any]) -> tuple[Any, Any, str]:
    """Internal helper to return the job state sort key."""
    return (
        parse_datetime_value(row.get("updated_at") or row.get("created_at")),
        parse_datetime_value(row.get("created_at")),
        str(row.get("id") or ""),
    )


def _collect_submitted_targets(targets: Any = None, payload: Any = None) -> list[str]:
    """Internal helper to collect the submitted targets."""
    submitted: list[str] = []
    for value in normalize_string_list(targets):
        normalized = normalize_target(value)
        if normalized and normalized not in submitted:
            submitted.append(normalized)

    if isinstance(payload, Mapping):
        payload_target = payload.get("target")
        if payload_target:
            normalized = normalize_target(payload_target)
            if normalized and normalized not in submitted:
                submitted.append(normalized)
        for value in normalize_string_list(payload.get("targets")):
            normalized = normalize_target(value)
            if normalized and normalized not in submitted:
                submitted.append(normalized)
    return submitted


def _decode_db_value(value: Any) -> Any:
    """Internal helper to decode the database value."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return value
    if (text.startswith("{") and text.endswith("}")) or (text.startswith("[") and text.endswith("]")):
        try:
            return json.loads(text)
        except Exception:
            return value
    return value


def _normalize_db_params(params: Any) -> Any:
    """Internal helper to normalize the database params."""
    if params is None:
        return []
    if isinstance(params, Mapping):
        return dict(params)
    if isinstance(params, Sequence) and not isinstance(params, (str, bytes, bytearray)):
        return list(params)
    return [params]


def _pool_dialect(pool: Any) -> str:
    """Internal helper to return the pool dialect."""
    normalized = pool.__class__.__name__.strip().lower() if pool is not None else ""
    if normalized == "postgrespool":
        return "postgres"
    if normalized == "sqlitepool":
        return "sqlite"
    return "unknown"


def _pool_failure_detail(pool: Any) -> str:
    """Internal helper to return the pool failure detail."""
    if pool is None:
        return "No storage pool is configured."

    pool_type = str(pool.__class__.__name__ or "Pool").strip() or "Pool"
    pool_name = str(getattr(pool, "name", "") or pool_type).strip() or pool_type
    last_error = str(getattr(pool, "last_error", "") or "").strip()
    is_connected = bool(getattr(pool, "is_connected", False))

    details: list[str] = []
    if pool_type == "PostgresPool":
        if is_connected:
            details.append(f"PostgreSQL pool '{pool_name}' rejected the write.")
        else:
            details.append(f"PostgreSQL pool '{pool_name}' is not connected.")
        has_connection_config = bool(str(getattr(pool, "dsn", "") or "").strip()) or any(
            os.getenv(env_name) for env_name in _POSTGRES_ENV_VARS
        )
        if has_connection_config:
            details.append("Verify the configured PostgreSQL DSN/PG* settings and that the server is reachable.")
        else:
            details.append(
                "Set POSTGRES_DSN, DATABASE_URL, SUPABASE_DB_URL, or PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD before starting the dispatcher."
            )
    elif not is_connected:
        details.append(f"{pool_type} '{pool_name}' is not connected.")

    if last_error:
        details.append(f"Last error: {last_error}")
    return " ".join(details).strip()


def _persistence_error_message(pool: Any, message: str) -> str:
    """Internal helper to return the persistence error message."""
    detail = _pool_failure_detail(pool)
    if detail:
        return f"{message} {detail}"
    return message


def _pool_schema(pool: Any) -> str:
    """Internal helper to return the pool schema."""
    return str(getattr(pool, "schema", "public") or "public").strip() or "public"


def _sql_placeholder(pool: Any) -> str:
    """Internal helper to return the SQL placeholder."""
    return "%s" if _pool_dialect(pool) == "postgres" else "?"


def _quote_sql_identifier(identifier: str) -> str:
    """Internal helper to quote the SQL identifier."""
    return '"' + str(identifier or "").replace('"', '""') + '"'


def _qualified_sql_table(pool: Any, table_name: str) -> str:
    """Internal helper to return the qualified SQL table."""
    if _pool_dialect(pool) == "postgres":
        return f"{_quote_sql_identifier(_pool_schema(pool))}.{_quote_sql_identifier(table_name)}"
    return _quote_sql_identifier(table_name)


def _preview_order_clause(columns: Sequence[str]) -> str:
    """Internal helper to preview the order clause."""
    normalized_columns = [str(column or "").strip() for column in columns if str(column or "").strip()]
    recency_columns = [
        column
        for column in (
            "updated_at",
            "created_at",
            "recorded_at",
            "collected_at",
            "captured_at",
            "last_seen_at",
            "claimed_at",
            "completed_at",
            "scheduled_for",
        )
        if column in normalized_columns
    ]
    order_parts: list[str] = []
    for column in recency_columns:
        quoted = _quote_sql_identifier(column)
        order_parts.append(f"CASE WHEN {quoted} IS NULL THEN 1 ELSE 0 END ASC")
        order_parts.append(f"{quoted} DESC")
    if "id" in normalized_columns:
        order_parts.append(f"{_quote_sql_identifier('id')} DESC")
    if not order_parts:
        return ""
    return " ORDER BY " + ", ".join(order_parts)


def _describe_pool(pool: Any) -> str:
    """Internal helper to describe the pool."""
    if pool is None:
        return "pool=None"
    pieces = [f"type={pool.__class__.__name__}"]
    for attribute in ("name", "db_path", "root_path", "schema", "dsn", "sslmode"):
        value = str(getattr(pool, attribute, "") or "").strip()
        if value:
            pieces.append(f"{attribute}={value}")
    return ", ".join(pieces)


def _coerce_error_history(value: Any) -> list[dict[str, Any]]:
    """Internal helper to coerce the error history."""
    if not isinstance(value, list):
        return []
    return [dict(entry) for entry in value if isinstance(entry, Mapping)]


def _merge_job_result_summary(
    previous_summary: Any,
    current_summary: Any,
    *,
    result: JobResult,
    attempts: int,
    max_attempts: int,
    worker_id: str,
    recorded_at: str,
) -> dict[str, Any]:
    """Internal helper to merge the job result summary."""
    previous = coerce_json_object(previous_summary)
    current = coerce_json_object(current_summary)
    merged = dict(previous)
    merged.update(current)

    error_history = _coerce_error_history(previous.get("error_history"))
    incoming_history = _coerce_error_history(current.get("error_history"))
    if incoming_history:
        error_history.extend(incoming_history)

    status = str(result.status or "").strip().lower()
    error_message = str(result.error or "").strip()
    if not error_message and status == "retry":
        error_message = "Job handler requested retry."
    if not error_message and status in {"failed", "error"}:
        error_message = "Job handler returned failure."

    if error_message:
        error_history.append(
            {
                "status": status or "error",
                "error": error_message,
                "exception": str(current.get("exception") or ""),
                "retryable": bool(current.get("retryable")),
                "attempt": max(int(attempts or 0), 0),
                "max_attempts": max(int(max_attempts or 1), 1),
                "worker_id": str(worker_id or ""),
                "recorded_at": str(recorded_at or ""),
            }
        )

    if error_history:
        merged["error_history"] = error_history
        merged["error_count"] = len(error_history)
        merged["last_error"] = str(error_history[-1].get("error") or "")
    else:
        merged.pop("error_history", None)
        merged.pop("error_count", None)
        merged.pop("last_error", None)

    return merged


def _coerce_unfinished_history(value: Any) -> list[dict[str, Any]]:
    """Internal helper to coerce the unfinished history."""
    if not isinstance(value, list):
        return []
    return [dict(entry) for entry in value if isinstance(entry, Mapping)]


def _merge_unfinished_job_summary(
    previous_summary: Any,
    *,
    worker_id: str,
    worker_name: str,
    reason: str,
    previous_status: str,
    progress: Any,
    environment: Any,
    recorded_at: str,
) -> dict[str, Any]:
    """Internal helper to merge the unfinished job summary."""
    merged = coerce_json_object(previous_summary)
    unfinished_history = _coerce_unfinished_history(merged.get("unfinished_history"))
    unfinished_event = {
        "worker_id": str(worker_id or "").strip(),
        "worker_name": str(worker_name or "").strip(),
        "reason": str(reason or "").strip(),
        "previous_status": str(previous_status or "").strip().lower(),
        "progress": coerce_json_payload(progress),
        "environment": coerce_json_object(environment),
        "recorded_at": str(recorded_at or "").strip(),
    }
    unfinished_history.append(unfinished_event)
    merged["unfinished"] = True
    merged["unfinished_at"] = unfinished_event["recorded_at"]
    merged["unfinished_worker_id"] = unfinished_event["worker_id"]
    merged["unfinished_reason"] = unfinished_event["reason"]
    merged["unfinished_history"] = unfinished_history
    merged["unfinished_count"] = len(unfinished_history)
    merged["last_progress"] = unfinished_event["progress"]
    return merged


class DispatcherAgent(StandbyAgent):
    """Agent implementation for dispatcher workflows."""
    def __init__(
        self,
        name: str = "Dispatcher",
        host: str = "127.0.0.1",
        port: int = 8060,
        plaza_url: str | None = None,
        agent_card: Dict[str, Any] | None = None,
        pool: Any = None,
        config: Any = None,
        config_path: Any = None,
        auto_register: bool | None = None,
    ):
        """Initialize the dispatcher agent."""
        if pool is None:
            raise ValueError("DispatcherAgent requires a pool for queue and result storage.")

        loaded_config, dispatcher_settings = _resolve_dispatcher_settings(config, config_path=config_path)
        resolved_name = str(loaded_config.get("name") or name)
        resolved_auto_register = bool(
            auto_register if auto_register is not None else dispatcher_settings.get("auto_register", False)
        )
        direct_auth_token = str(
            dispatcher_settings.get("direct_auth_token")
            or loaded_config.get("direct_auth_token")
            or DISPATCHER_DIRECT_TOKEN
        ).strip()

        card = dict(agent_card or loaded_config.get("agent_card") or {})
        card.setdefault("name", resolved_name)
        card["party"] = _resolve_party(loaded_config, card)
        card["role"] = str(loaded_config.get("role") or card.get("role") or "dispatcher")
        card["description"] = str(
            loaded_config.get("description") or card.get("description") or "Queue-based Prompits dispatcher."
        )
        card["tags"] = _merge_tags(card.get("tags"), loaded_config.get("tags"), ["prompits", "dispatcher", "queue"])
        meta = dict(card.get("meta") or {})
        meta["dispatcher_tables"] = [
            TABLE_JOBS,
            TABLE_WORKERS,
            TABLE_WORKER_HISTORY,
            TABLE_RESULT_ROWS,
            TABLE_RAW_PAYLOADS,
        ]
        if isinstance(dispatcher_settings.get("job_capabilities"), list):
            meta["job_capabilities"] = list(dispatcher_settings.get("job_capabilities") or [])
        meta.setdefault("party", card["party"])
        meta.setdefault("direct_auth_token", direct_auth_token)
        card["meta"] = meta

        super().__init__(
            name=resolved_name,
            host=host,
            port=port,
            plaza_url=plaza_url,
            agent_card=card,
            pool=pool,
        )

        self.dispatcher_settings = dispatcher_settings
        self._job_claim_lock = threading.Lock()
        self._stale_recovery_lock = threading.Lock()
        self._last_stale_recovery_monotonic = 0.0
        self.record_poll_history = bool(dispatcher_settings.get("record_poll_history", False))
        try:
            self.stale_recovery_interval_sec = max(
                float(dispatcher_settings.get("stale_recovery_interval_sec", STALE_RECOVERY_INTERVAL_SEC)),
                0.0,
            )
        except (TypeError, ValueError):
            self.stale_recovery_interval_sec = STALE_RECOVERY_INTERVAL_SEC
        try:
            self.job_claim_candidate_limit = max(
                int(dispatcher_settings.get("job_claim_candidate_limit", JOB_CLAIM_CANDIDATE_LIMIT)),
                1,
            )
        except (TypeError, ValueError):
            self.job_claim_candidate_limit = JOB_CLAIM_CANDIDATE_LIMIT
        self.ensure_tables()
        self.add_practice(SubmitDispatcherJobPractice())
        self.add_practice(RegisterDispatcherWorkerPractice())
        self.add_practice(GetDispatcherJobPractice())
        self.add_practice(PostDispatcherJobResultPractice())
        self.add_practice(ControlDispatcherJobPractice())
        self.add_practice(ListDispatcherDbTablesPractice())
        self.add_practice(PreviewDispatcherDbTablePractice())
        self.add_practice(QueryDispatcherDbPractice())
        self.add_practice(ReportDispatcherJobPractice())
        self.logger.info(
            "Dispatcher initialized from config=%s with %s",
            str(config_path or config or ""),
            _describe_pool(self.pool),
        )

        if self.plaza_url and resolved_auto_register:
            self.register()

    def ensure_tables(self) -> None:
        """Ensure the tables exists."""
        ensure_dispatcher_tables(self.pool)

    @staticmethod
    def _latest_job_rows(rows: Any) -> list[dict[str, Any]]:
        """Internal helper to return the latest job rows."""
        latest_rows_by_id: dict[str, dict[str, Any]] = {}
        for row in rows or []:
            if not isinstance(row, Mapping):
                continue
            row_id = str(row.get("id") or "").strip()
            if not row_id:
                continue
            normalized_row = dict(row)
            current = latest_rows_by_id.get(row_id)
            if current is None or _job_state_sort_key(normalized_row) > _job_state_sort_key(current):
                latest_rows_by_id[row_id] = normalized_row
        return list(latest_rows_by_id.values())

    @staticmethod
    def _latest_worker_rows(rows: Any) -> list[dict[str, Any]]:
        """Internal helper to return the latest worker rows."""
        latest_rows_by_id: dict[str, dict[str, Any]] = {}
        for row in rows or []:
            if not isinstance(row, Mapping):
                continue
            normalized_row = dict(row)
            worker_id = str(normalized_row.get("worker_id") or normalized_row.get("id") or normalized_row.get("name") or "").strip()
            if not worker_id:
                continue
            current = latest_rows_by_id.get(worker_id)
            current_updated_at = parse_datetime_value(current.get("updated_at") if isinstance(current, Mapping) else "")
            candidate_updated_at = parse_datetime_value(normalized_row.get("updated_at") or normalized_row.get("last_seen_at"))
            if current is None or candidate_updated_at > current_updated_at:
                normalized_row["worker_id"] = worker_id
                latest_rows_by_id[worker_id] = normalized_row
        return list(latest_rows_by_id.values())

    def _should_record_worker_history(self, *, event_type: str = "heartbeat") -> bool:
        """Return whether the value should record worker history."""
        normalized_event_type = str(event_type or "heartbeat").strip().lower() or "heartbeat"
        if normalized_event_type == "poll" and not self.record_poll_history:
            return False
        return True

    def _nonempty_json_value_sql(self, column_sql: str) -> str:
        """Internal helper for nonempty JSON value SQL."""
        if _pool_dialect(self.pool) == "postgres":
            return (
                f"({column_sql} IS NOT NULL AND {column_sql} <> '[]'::jsonb "
                f"AND {column_sql} <> '{{}}'::jsonb)"
            )
        return f"({column_sql} IS NOT NULL AND TRIM({column_sql}) NOT IN ('', '[]', '{{}}'))"

    def _query_ready_job_candidates(
        self,
        capabilities: Any,
        *,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Internal helper to query the ready job candidates."""
        normalized_limit = max(int(limit or self.job_claim_candidate_limit or JOB_CLAIM_CANDIDATE_LIMIT), 1)
        fetch_limit = normalized_limit + 1
        placeholder = _sql_placeholder(self.pool)
        table_ref = _qualified_sql_table(self.pool, TABLE_JOBS)
        status_column = _quote_sql_identifier("status")
        scheduled_column = _quote_sql_identifier("scheduled_for")
        attempts_column = _quote_sql_identifier("attempts")
        max_attempts_column = _quote_sql_identifier("max_attempts")
        required_capability_column = _quote_sql_identifier("required_capability")
        capability_tags_column = _quote_sql_identifier("capability_tags")
        priority_column = _quote_sql_identifier("priority")
        created_at_column = _quote_sql_identifier("created_at")
        id_column = _quote_sql_identifier("id")

        statuses = ("queued", "retry", "unfinished")
        params: list[Any] = list(statuses)
        conditions = [
            f"LOWER(COALESCE({status_column}, '')) IN ({', '.join([placeholder] * len(statuses))})"
        ]
        if _pool_dialect(self.pool) == "postgres":
            conditions.append(f"({scheduled_column} IS NULL OR {scheduled_column} <= {placeholder})")
            params.append(datetime.now(timezone.utc))
            conditions.append(
                f"COALESCE({attempts_column}, 0) < GREATEST(COALESCE({max_attempts_column}, 1), 1)"
            )
        else:
            conditions.append(
                f"({scheduled_column} IS NULL OR {scheduled_column} = '' OR {scheduled_column} <= {placeholder})"
            )
            params.append(datetime.now(timezone.utc).isoformat())
            conditions.append(
                f"COALESCE({attempts_column}, 0) < "
                f"CASE WHEN COALESCE({max_attempts_column}, 1) < 1 THEN 1 ELSE COALESCE({max_attempts_column}, 1) END"
            )

        normalized_capabilities = normalize_capabilities(capabilities)
        if "*" not in normalized_capabilities:
            executable_capabilities = [capability for capability in normalized_capabilities if capability]
            if executable_capabilities:
                capability_conditions = [
                    f"LOWER(COALESCE({required_capability_column}, '')) "
                    f"IN ({', '.join([placeholder] * len(executable_capabilities))})",
                    f"COALESCE({required_capability_column}, '') = ''",
                    self._nonempty_json_value_sql(capability_tags_column),
                ]
                params.extend(executable_capabilities)
            else:
                capability_conditions = [f"COALESCE({required_capability_column}, '') = ''"]
            conditions.append("(" + " OR ".join(capability_conditions) + ")")

        params.append(fetch_limit)
        sql = (
            f"SELECT * FROM {table_ref} "
            f"WHERE {' AND '.join(conditions)} "
            f"ORDER BY {priority_column} ASC, {created_at_column} ASC, {id_column} ASC "
            f"LIMIT {placeholder}"
        )
        with self.pool.lock:
            cursor = self._db_cursor()
            cursor.execute(sql, params)
            columns = [desc[0] for desc in cursor.description or []]
            raw_rows = cursor.fetchall()
        truncated = len(raw_rows) > normalized_limit
        rows = [
            {column: _decode_db_value(value) for column, value in zip(columns, row)}
            for row in raw_rows[:normalized_limit]
        ]
        return rows, truncated

    def _next_ready_job_row(self, capabilities: Any) -> dict[str, Any] | None:
        """Internal helper to return the next ready job row."""
        try:
            candidate_rows, truncated = self._query_ready_job_candidates(capabilities)
        except Exception as exc:
            self.logger.warning("Ready job candidate query failed; falling back to full scan: %s", exc)
        else:
            for row in candidate_rows:
                if isinstance(row, Mapping) and job_is_ready(row) and job_matches_capabilities(row, capabilities):
                    return dict(row)
            if not truncated:
                return None
            self.logger.debug(
                "Ready job candidate query hit the scan limit without a match; falling back to full scan."
            )

        latest_rows = self._latest_job_rows(self.pool._GetTableData(TABLE_JOBS) or [])
        ready_rows = [
            row
            for row in latest_rows
            if isinstance(row, Mapping) and job_is_ready(row) and job_matches_capabilities(row, capabilities)
        ]
        if not ready_rows:
            return None
        return dict(sorted(ready_rows, key=job_sort_key)[0])

    def _append_worker_history(self, *, record: Mapping[str, Any], event_type: str = "heartbeat") -> None:
        """Internal helper to append the worker history."""
        metadata = dict(record.get("metadata") or {}) if isinstance(record.get("metadata"), Mapping) else {}
        heartbeat = dict(metadata.get("heartbeat") or {}) if isinstance(metadata.get("heartbeat"), Mapping) else {}
        active_job = dict(heartbeat.get("active_job") or {}) if isinstance(heartbeat.get("active_job"), Mapping) else {}
        history_entry = build_worker_history_entry(
            worker_id=str(record.get("worker_id") or record.get("id") or ""),
            name=str(record.get("name") or ""),
            address=str(record.get("address") or ""),
            capabilities=record.get("capabilities"),
            metadata=metadata,
            plaza_url=str(record.get("plaza_url") or ""),
            status=str(record.get("status") or "online"),
            event_type=event_type,
            session_started_at=heartbeat.get("session_started_at") or record.get("updated_at"),
            active_job_id=str(active_job.get("id") or ""),
            active_job_status=str(active_job.get("status") or ""),
            progress=heartbeat.get("progress"),
            environment=metadata.get("environment"),
            captured_at=record.get("updated_at") or record.get("last_seen_at"),
        )
        if not self.pool._Insert(TABLE_WORKER_HISTORY, history_entry):
            raise RuntimeError(_persistence_error_message(self.pool, "Failed to persist worker history."))

    def _recover_stale_worker_jobs(self, *, now_text: str = "") -> int:
        """Internal helper to recover the stale worker jobs."""
        now = parse_datetime_value(now_text or utcnow_iso())
        worker_rows = self._latest_worker_rows(self.pool._GetTableData(TABLE_WORKERS) or [])
        stale_workers: dict[str, dict[str, Any]] = {}
        for worker_row in worker_rows:
            status = str(worker_row.get("status") or "online").strip().lower() or "online"
            if status in {"stopped", "offline", "error"}:
                continue
            last_seen_at = parse_datetime_value(worker_row.get("last_seen_at") or worker_row.get("updated_at"))
            if last_seen_at == datetime.min.replace(tzinfo=timezone.utc):
                continue
            heartbeat_age = max((now - last_seen_at).total_seconds(), 0.0)
            if heartbeat_age < WORKER_JOB_TIMEOUT_SEC:
                continue
            stale_workers[str(worker_row.get("worker_id") or worker_row.get("id") or "")] = dict(worker_row)

        if not stale_workers:
            return 0

        latest_jobs = self._latest_job_rows(self.pool._GetTableData(TABLE_JOBS) or [])
        recovered_count = 0
        for row in latest_jobs:
            current_status = str(row.get("status") or "").strip().lower()
            if current_status not in {"claimed", "stopping"}:
                continue
            claimed_by = str(row.get("claimed_by") or "").strip()
            worker_row = stale_workers.get(claimed_by)
            if worker_row is None:
                continue

            metadata = dict(row.get("metadata") or {}) if isinstance(row.get("metadata"), Mapping) else {}
            recovery = dict(metadata.get("recovery") or {}) if isinstance(metadata.get("recovery"), Mapping) else {}
            if recovery.get("unfinished_at") and recovery.get("unfinished_worker_id") == claimed_by:
                continue

            heartbeat = dict((worker_row.get("metadata") or {}).get("heartbeat") or {}) if isinstance(worker_row.get("metadata"), Mapping) else {}
            recorded_at = now.isoformat()
            reason = f"Worker '{claimed_by}' missed dispatcher heartbeats for at least {int(WORKER_JOB_TIMEOUT_SEC)}s."
            recovery.update(
                {
                    "source": "worker_heartbeat_timeout",
                    "unfinished_at": recorded_at,
                    "unfinished_worker_id": claimed_by,
                    "unfinished_worker_name": str(worker_row.get("name") or "").strip(),
                    "recovered_from_status": current_status,
                }
            )
            metadata["recovery"] = recovery

            previous_summary = row.get("result_summary")
            updated_job = JobDetail.from_row(row).model_copy(
                update={
                    "status": "unfinished",
                    "updated_at": recorded_at,
                    "completed_at": "",
                    "claimed_by": "",
                    "claimed_at": "",
                    "error": reason,
                    "metadata": metadata,
                    "result_summary": _merge_unfinished_job_summary(
                        previous_summary,
                        worker_id=claimed_by,
                        worker_name=str(worker_row.get("name") or ""),
                        reason=reason,
                        previous_status=current_status,
                        progress=heartbeat.get("progress"),
                        environment=(worker_row.get("metadata") or {}).get("environment")
                        if isinstance(worker_row.get("metadata"), Mapping)
                        else {},
                        recorded_at=recorded_at,
                    ),
                }
            )
            if not self.pool._Insert(TABLE_JOBS, updated_job.to_row()):
                raise RuntimeError(_persistence_error_message(self.pool, "Failed to mark stale job as unfinished."))
            recovered_count += 1
        return recovered_count

    def _maybe_recover_stale_worker_jobs(self, *, event_type: str = "heartbeat", now_text: str = "") -> int:
        """Internal helper for maybe recover stale worker jobs."""
        normalized_event_type = str(event_type or "heartbeat").strip().lower() or "heartbeat"
        if normalized_event_type == "poll":
            return 0
        if self.stale_recovery_interval_sec <= 0:
            return self._recover_stale_worker_jobs(now_text=now_text)

        now_monotonic = time.monotonic()
        with self._stale_recovery_lock:
            if self._last_stale_recovery_monotonic:
                elapsed = now_monotonic - self._last_stale_recovery_monotonic
                if elapsed < self.stale_recovery_interval_sec:
                    return 0
            self._last_stale_recovery_monotonic = now_monotonic
        try:
            return self._recover_stale_worker_jobs(now_text=now_text)
        except Exception:
            with self._stale_recovery_lock:
                self._last_stale_recovery_monotonic = 0.0
            raise

    def submit_job(
        self,
        required_capability: str = "",
        payload: Any = None,
        target_table: str = "",
        source_url: str = "",
        parse_rules: Any = None,
        targets: Any = None,
        capability_tags: Any = None,
        job_type: str = "run",
        priority: int = 100,
        premium: bool = False,
        metadata: Any = None,
        scheduled_for: Any = None,
        max_attempts: int = 3,
        job_id: str | None = None,
        content: Any = None,
    ) -> Dict[str, Any]:
        """Submit the job."""
        effective_payload = payload if payload is not None else content
        normalized_targets = _collect_submitted_targets(targets, effective_payload)
        normalized_table = _table_for_job(required_capability, target_table)
        job = build_dispatch_job(
            required_capability=required_capability,
            payload=effective_payload,
            target_table=normalized_table,
            source_url=source_url,
            parse_rules=parse_rules,
            targets=normalized_targets,
            capability_tags=capability_tags,
            job_type=job_type,
            priority=priority,
            premium=premium,
            metadata=metadata,
            scheduled_for=scheduled_for,
            max_attempts=max_attempts,
            job_id=job_id,
        )
        if not self.pool._Insert(TABLE_JOBS, job.to_row()):
            raise RuntimeError(_persistence_error_message(self.pool, "Failed to persist dispatcher job."))
        return {"status": "success", "job": job.to_payload()}

    def _should_reissue_failed_job(self, job: JobDetail) -> bool:
        """Return whether the value should reissue failed job."""
        if str(job.status or "").strip().lower() != "failed":
            return False
        attempts = max(int(job.attempts or 0), 0)
        max_attempts = max(int(job.max_attempts or 1), 1)
        if attempts < max_attempts:
            return False
        result_summary = dict(job.result_summary or {}) if isinstance(job.result_summary, Mapping) else {}
        if bool(result_summary.get("force_terminated")):
            return False
        metadata = dict(job.metadata or {}) if isinstance(job.metadata, Mapping) else {}
        controls = dict(metadata.get("control") or {}) if isinstance(metadata.get("control"), Mapping) else {}
        effective_action = str(controls.get("effective_action") or controls.get("action") or "").strip().lower()
        if effective_action in {"force_terminate", "cancel", "delete"}:
            return False
        return True

    def _reissue_failed_job(self, job: JobDetail) -> JobDetail:
        """Internal helper for reissue failed job."""
        now = utcnow_iso()
        metadata = dict(job.metadata or {}) if isinstance(job.metadata, Mapping) else {}
        metadata.pop("control", None)
        reissue = dict(metadata.get("reissue") or {}) if isinstance(metadata.get("reissue"), Mapping) else {}
        reissue_count = max(int(reissue.get("count") or 0), 0) + 1
        metadata["reissue"] = {
            **reissue,
            "count": reissue_count,
            "source_job_id": str(job.id or ""),
            "source_completed_at": str(job.completed_at or ""),
            "source_attempts": max(int(job.attempts or 0), 0),
            "source_max_attempts": max(int(job.max_attempts or 1), 1),
            "trigger": "failed_max_attempts",
            "reissued_at": now,
        }
        reissued_job = build_dispatch_job(
            required_capability=job.required_capability,
            payload=job.payload,
            target_table=job.target_table,
            source_url=job.source_url,
            parse_rules=job.parse_rules,
            targets=job.targets,
            capability_tags=job.capability_tags,
            job_type=job.job_type,
            priority=max(int(job.priority or FAILED_REISSUE_PRIORITY), FAILED_REISSUE_PRIORITY),
            premium=job.premium,
            metadata=metadata,
            scheduled_for=now,
            max_attempts=max(int(job.max_attempts or 1), 1),
        )
        if not self.pool._Insert(TABLE_JOBS, reissued_job.to_row()):
            raise RuntimeError(_persistence_error_message(self.pool, "Failed to persist reissued dispatcher job."))
        return reissued_job

    def register_worker(
        self,
        worker_id: str,
        name: str = "",
        address: str = "",
        capabilities: Any = None,
        metadata: Any = None,
        plaza_url: str = "",
        status: str = "online",
        event_type: str = "heartbeat",
    ) -> Dict[str, Any]:
        """Register the worker."""
        normalized_event_type = str(event_type or "heartbeat").strip().lower() or "heartbeat"
        executable_capabilities = _resolve_executable_worker_capabilities(capabilities, metadata)
        record = build_worker_registration(
            worker_id=worker_id,
            name=name,
            address=address,
            capabilities=executable_capabilities,
            metadata=metadata,
            plaza_url=plaza_url,
            status=status,
        )
        if not self.pool._Insert(TABLE_WORKERS, record):
            raise RuntimeError(_persistence_error_message(self.pool, "Failed to persist worker registration."))
        if self._should_record_worker_history(event_type=normalized_event_type):
            self._append_worker_history(record=record, event_type=normalized_event_type)
        self._maybe_recover_stale_worker_jobs(
            event_type=normalized_event_type,
            now_text=str(record.get("updated_at") or ""),
        )
        return {"status": "success", "worker": record}

    def get_job(
        self,
        worker_id: str,
        capabilities: Any = None,
        name: str = "",
        address: str = "",
        metadata: Any = None,
        plaza_url: str = "",
    ) -> Dict[str, Any]:
        """Return the job."""
        executable_capabilities = _resolve_executable_worker_capabilities(capabilities, metadata)
        self.register_worker(
            worker_id=worker_id,
            name=name,
            address=address,
            capabilities=executable_capabilities,
            metadata=metadata,
            plaza_url=plaza_url,
            status="online",
            event_type="poll",
        )

        with self._job_claim_lock:
            next_job_row = self._next_ready_job_row(executable_capabilities)
            if not next_job_row:
                return {"status": "success", "job": None}

            job = JobDetail.from_row(next_job_row)
            now = utcnow_iso()
            claim_result_summary = dict(job.result_summary or {}) if isinstance(job.result_summary, Mapping) else {}
            if "unfinished" in claim_result_summary:
                claim_result_summary["unfinished"] = False
                claim_result_summary["unfinished_recovered_at"] = now
                claim_result_summary["unfinished_recovered_by"] = str(worker_id or "")
            claimed_job = job.model_copy(
                update={
                    "status": "claimed",
                    "claimed_by": str(worker_id or ""),
                    "claimed_at": now,
                    "updated_at": now,
                    "attempts": int(job.attempts or 0) + 1,
                    "completed_at": "",
                    "error": "",
                    "result_summary": claim_result_summary,
                }
            )

            if not self.pool._Insert(TABLE_JOBS, claimed_job.to_row()):
                raise RuntimeError(_persistence_error_message(self.pool, "Failed to claim dispatcher job."))
            return {"status": "success", "job": claimed_job.to_payload()}

    def claim_job(
        self,
        worker_id: str,
        capabilities: Any = None,
        name: str = "",
        address: str = "",
        metadata: Any = None,
        plaza_url: str = "",
    ) -> Dict[str, Any]:
        """Claim the job."""
        return self.get_job(
            worker_id=worker_id,
            capabilities=capabilities,
            name=name,
            address=address,
            metadata=metadata,
            plaza_url=plaza_url,
        )

    def post_job_result(
        self,
        job_result: JobResult | Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Post the job result."""
        result = coerce_job_result(job_result or kwargs)
        job_id = result.job_id
        rows = self._latest_job_rows(self.pool._GetTableData(TABLE_JOBS, job_id) or [])
        if not rows:
            raise ValueError(f"Dispatcher job '{job_id}' was not found.")

        rows.sort(key=_job_state_sort_key, reverse=True)
        job = JobDetail.from_row(rows[0])
        current_status = str(job.status or "").strip().lower()
        current_claimed_by = str(job.claimed_by or "").strip()
        reported_worker_id = str(result.worker_id or "").strip()
        if current_status in {"unfinished", "completed", "failed", "stopped", "cancelled", "deleted"}:
            return {
                "status": "success",
                "ignored": True,
                "job": job.to_payload(),
                "job_result": result.to_payload(),
                "stored_rows": 0,
                "target_table": str(job.target_table or ""),
                "raw_record": None,
                "reissued_job": None,
            }
        if current_claimed_by and reported_worker_id and current_claimed_by != reported_worker_id:
            return {
                "status": "success",
                "ignored": True,
                "job": job.to_payload(),
                "job_result": result.to_payload(),
                "stored_rows": 0,
                "target_table": str(job.target_table or ""),
                "raw_record": None,
                "reissued_job": None,
            }
        metadata = dict(job.metadata or {}) if isinstance(job.metadata, Mapping) else {}
        controls = dict(metadata.get("control") or {}) if isinstance(metadata.get("control"), Mapping) else {}
        effective_action = str(controls.get("effective_action") or controls.get("action") or "").strip().lower()
        if effective_action == "force_terminate" and str(job.status or "").strip().lower() in {"failed", "cancelled", "deleted", "stopped"}:
            return {
                "status": "success",
                "ignored": True,
                "job": job.to_payload(),
                "job_result": result.to_payload(),
                "stored_rows": 0,
                "target_table": str(job.target_table or ""),
                "raw_record": None,
                "reissued_job": None,
            }
        now = utcnow_iso()
        merged_result_summary = _merge_job_result_summary(
            job.result_summary,
            result.result_summary,
            result=result,
            attempts=int(job.attempts or 0),
            max_attempts=int(job.max_attempts or 1),
            worker_id=str(result.worker_id or job.claimed_by or ""),
            recorded_at=now,
        )
        updated_job = job.model_copy(
            update={
                "status": result.status,
                "updated_at": now,
                "completed_at": now if result.status in {"completed", "failed", "stopped"} else "",
                "claimed_by": str(result.worker_id or job.claimed_by or ""),
                "error": str(result.error or ""),
                "result_summary": merged_result_summary,
                "target_table": str(result.target_table or job.target_table or ""),
            }
        )

        if not self.pool._Insert(TABLE_JOBS, updated_job.to_row()):
            raise RuntimeError(_persistence_error_message(self.pool, "Failed to update dispatcher job state."))

        saved_rows: list[dict[str, Any]] = []
        stored_rows_by_table: dict[str, int] = {}
        resolved_target_table = _table_for_job(updated_job.required_capability, result.target_table or updated_job.target_table)
        raw_targets: list[dict[str, Any]] = []
        primary_records = coerce_record_list(result.collected_rows)
        if resolved_target_table and primary_records:
            raw_targets.append(
                {
                    "table_name": resolved_target_table,
                    "rows": primary_records,
                    "source_url": str(updated_job.source_url or ""),
                    "table_schema": None,
                }
            )
        for extra_target in list(result.additional_targets or []):
            if not isinstance(extra_target, Mapping):
                continue
            extra_table_name = str(extra_target.get("table_name") or extra_target.get("target_table") or "").strip()
            extra_rows = coerce_record_list(extra_target.get("rows"))
            if not extra_table_name or not extra_rows:
                continue
            raw_targets.append(
                {
                    "table_name": extra_table_name,
                    "rows": extra_rows,
                    "source_url": str(extra_target.get("source_url") or updated_job.source_url or ""),
                    "table_schema": extra_target.get("table_schema"),
                }
            )

        merged_targets: dict[str, dict[str, Any]] = {}
        for target in raw_targets:
            target_table_name = str(target.get("table_name") or "").strip()
            if not target_table_name:
                continue
            merged = merged_targets.setdefault(
                target_table_name,
                {
                    "table_name": target_table_name,
                    "rows": [],
                    "source_url": str(target.get("source_url") or updated_job.source_url or ""),
                    "table_schema": target.get("table_schema"),
                },
            )
            if not merged.get("source_url") and target.get("source_url"):
                merged["source_url"] = str(target.get("source_url") or "")
            if merged.get("table_schema") is None and target.get("table_schema") is not None:
                merged["table_schema"] = target.get("table_schema")
            merged["rows"].extend(coerce_record_list(target.get("rows")))

        if not resolved_target_table and merged_targets:
            resolved_target_table = next(iter(merged_targets))

        if result.status == "completed":
            for target in merged_targets.values():
                target_table_name = str(target.get("table_name") or "").strip()
                target_rows = coerce_record_list(target.get("rows"))
                target_schema = target.get("table_schema")
                if not target_table_name or not target_rows:
                    continue

                table_exists = bool(getattr(self.pool, "_TableExists", lambda _name: False)(target_table_name))
                if target_schema is not None or table_exists:
                    ensure_dispatcher_tables(
                        self.pool,
                        [target_table_name],
                        extra_schemas={target_table_name: target_schema} if target_schema is not None else None,
                    )
                    prepared = prepare_table_records(
                        target_table_name,
                        target_rows,
                        source_url=str(target.get("source_url") or updated_job.source_url or ""),
                    )
                    if not self.pool._InsertMany(target_table_name, prepared):
                        raise RuntimeError(
                            _persistence_error_message(
                                self.pool,
                                f"Failed to persist dispatcher rows into '{target_table_name}'.",
                            )
                        )
                    stored_rows_by_table[target_table_name] = stored_rows_by_table.get(target_table_name, 0) + len(prepared)
                    saved_rows.extend(prepared)
                    continue

                ensure_dispatcher_tables(self.pool, [TABLE_RESULT_ROWS])
                generic_rows = [
                    build_result_row(
                        job_id=job_id,
                        worker_id=str(result.worker_id or updated_job.claimed_by or ""),
                        table_name=target_table_name,
                        payload=row,
                        source_url=str(target.get("source_url") or updated_job.source_url or ""),
                        metadata=merged_result_summary,
                        recorded_at=now,
                    )
                    for row in target_rows
                ]
                if not self.pool._InsertMany(TABLE_RESULT_ROWS, generic_rows):
                    raise RuntimeError(_persistence_error_message(self.pool, "Failed to persist generic dispatcher results."))
                stored_rows_by_table[target_table_name] = stored_rows_by_table.get(target_table_name, 0) + len(generic_rows)
                saved_rows.extend(generic_rows)

        raw_record = None
        reissued_job = None
        if result.raw_payload is not None:
            ensure_dispatcher_tables(self.pool, [TABLE_RAW_PAYLOADS])
            raw_record = build_raw_payload_row(
                job_id=str(job_id),
                worker_id=str(result.worker_id or updated_job.claimed_by or ""),
                target_table=resolved_target_table,
                source_url=str(updated_job.source_url or ""),
                payload=result.raw_payload,
                metadata=merged_result_summary,
                collected_at=now,
            )
            if not self.pool._Insert(TABLE_RAW_PAYLOADS, raw_record):
                raise RuntimeError(_persistence_error_message(self.pool, "Failed to persist raw dispatcher payload."))

        if self._should_reissue_failed_job(updated_job):
            reissued_job = self._reissue_failed_job(updated_job)

        return {
            "status": "success",
            "job": updated_job.to_payload(),
            "job_result": result.to_payload(),
            "stored_rows": len(saved_rows),
            "stored_rows_by_table": stored_rows_by_table,
            "target_table": resolved_target_table,
            "raw_record": raw_record,
            "reissued_job": reissued_job.to_payload() if isinstance(reissued_job, JobDetail) else None,
        }

    def report_job_result(
        self,
        job_id: str,
        worker_id: str = "",
        status: str = "completed",
        collected_rows: Any = None,
        raw_payload: Any = None,
        result_summary: Any = None,
        error: str = "",
        target_table: str = "",
        additional_targets: Any = None,
    ) -> Dict[str, Any]:
        """Report the job result."""
        return self.post_job_result(
            JobResult(
                job_id=job_id,
                worker_id=worker_id,
                status=status,
                collected_rows=coerce_record_list(collected_rows),
                additional_targets=list(additional_targets or []),
                raw_payload=raw_payload,
                result_summary=coerce_json_object(result_summary),
                error=error,
                target_table=target_table,
            )
        )

    def control_job(self, job_id: str, action: str, worker_id: str = "", reason: str = "") -> Dict[str, Any]:
        """Control the job."""
        normalized_job_id = str(job_id or "").strip()
        if not normalized_job_id:
            raise ValueError("job_id is required.")
        normalized_action = str(action or "").strip().lower()
        if normalized_action not in {"pause", "delete", "stop", "resume", "cancel", "force_terminate"}:
            raise ValueError("action must be one of: pause, stop, resume, cancel, delete, force_terminate.")

        rows = self._latest_job_rows(self.pool._GetTableData(TABLE_JOBS, normalized_job_id) or [])
        if not rows:
            raise ValueError(f"Dispatcher job '{normalized_job_id}' was not found.")

        rows.sort(key=_job_state_sort_key, reverse=True)
        job = JobDetail.from_row(rows[0])
        current_status = str(job.status or "").strip().lower()
        effective_action = normalized_action
        next_status = current_status
        completed_at = str(job.completed_at or "")
        claimed_by = str(job.claimed_by or "")
        claimed_at = str(job.claimed_at or "")
        error = str(job.error or "")
        result_summary = coerce_json_object(job.result_summary)

        if effective_action == "pause":
            if current_status == "paused":
                return {"status": "success", "action": normalized_action, "job": job.to_payload()}
            if current_status in {"claimed", "stopping"}:
                raise ValueError("Claimed jobs cannot be paused. Use stop instead.")
            if current_status == "stopped":
                raise ValueError("Stopped jobs cannot be paused. Use resume or cancel instead.")
            if current_status in {"completed", "failed", "cancelled", "deleted"}:
                raise ValueError(f"{job.id} is already terminal and cannot be paused.")
            next_status = "paused"
            completed_at = ""
        elif effective_action == "stop":
            if current_status == "stopping":
                return {"status": "success", "action": normalized_action, "job": job.to_payload()}
            if current_status != "claimed":
                raise ValueError("Only claimed jobs can be stopped.")
            next_status = "stopping"
            completed_at = ""
        elif effective_action == "resume":
            if current_status == "queued":
                return {"status": "success", "action": normalized_action, "job": job.to_payload()}
            if current_status not in {"paused", "stopped"}:
                raise ValueError("Only paused or stopped jobs can be resumed.")
            next_status = "queued"
            completed_at = ""
            claimed_by = ""
            claimed_at = ""
            error = ""
            result_summary = {}
        elif effective_action == "force_terminate":
            if current_status == "failed":
                metadata = dict(job.metadata or {})
                controls = dict(metadata.get("control") or {}) if isinstance(metadata.get("control"), Mapping) else {}
                if str(controls.get("effective_action") or controls.get("action") or "").strip().lower() == "force_terminate":
                    return {"status": "success", "action": normalized_action, "job": job.to_payload()}
            if current_status in {"completed", "cancelled", "deleted"}:
                raise ValueError(f"{job.id} is already terminal and cannot be force terminated.")
            if current_status not in {"claimed", "working"}:
                raise ValueError("Only claimed or working jobs can be force terminated.")
            next_status = "failed"
            completed_at = str(job.completed_at or utcnow_iso())
            error = str(reason or job.error or "Dispatcher job was force terminated.").strip()
            result_summary = coerce_json_object(job.result_summary)
            result_summary["force_terminated"] = True
            result_summary["force_terminated_at"] = completed_at
            result_summary["force_terminated_by"] = str(worker_id or "")
            if error:
                result_summary["last_error"] = error
        elif effective_action == "cancel":
            if current_status == "cancelled":
                return {"status": "success", "action": normalized_action, "job": job.to_payload()}
            if current_status in {"claimed", "stopping"}:
                raise ValueError("Claimed jobs cannot be cancelled while a worker is processing them.")
            if current_status == "deleted":
                raise ValueError(f"{job.id} has already been deleted.")
            next_status = "cancelled"
            completed_at = str(job.completed_at or utcnow_iso())
        else:
            if current_status == "deleted":
                return {"status": "success", "action": normalized_action, "job": job.to_payload()}
            if current_status in {"claimed", "stopping"}:
                raise ValueError("Claimed jobs cannot be deleted while a worker is processing them.")
            next_status = "deleted"
            completed_at = str(job.completed_at or utcnow_iso())

        metadata = dict(job.metadata or {})
        controls = dict(metadata.get("control") or {}) if isinstance(metadata.get("control"), Mapping) else {}
        controls.update(
            {
                "action": normalized_action,
                "effective_action": effective_action,
                "requested_by": str(worker_id or ""),
                "reason": str(reason or ""),
                "updated_at": utcnow_iso(),
            }
        )
        metadata["control"] = controls

        updated_job = job.model_copy(
            update={
                "status": next_status,
                "updated_at": controls["updated_at"],
                "completed_at": completed_at,
                "claimed_by": claimed_by,
                "claimed_at": claimed_at,
                "error": error,
                "result_summary": result_summary,
                "metadata": metadata,
            }
        )
        if not self.pool._Insert(TABLE_JOBS, updated_job.to_row()):
            raise RuntimeError(
                _persistence_error_message(self.pool, f"Failed to {normalized_action} dispatcher job '{normalized_job_id}'.")
            )
        return {"status": "success", "action": normalized_action, "job": updated_job.to_payload()}

    def _db_cursor(self):
        """Internal helper to return the database cursor."""
        ensure_connection = getattr(self.pool, "_ensure_connection", None)
        if callable(ensure_connection) and not ensure_connection():
            raise RuntimeError(_persistence_error_message(self.pool, "Dispatcher database connection is unavailable."))
        conn = getattr(self.pool, "conn", None)
        if conn is None:
            raise RuntimeError(_persistence_error_message(self.pool, "Dispatcher database connection is unavailable."))
        return conn.cursor()

    def list_db_tables(self) -> Dict[str, Any]:
        """List the database tables."""
        schema_map = dispatcher_table_schema_map()
        with self.pool.lock:
            cursor = self._db_cursor()
            if _pool_dialect(self.pool) == "postgres":
                cursor.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                      AND table_type IN ('BASE TABLE', 'VIEW', 'FOREIGN TABLE')
                    ORDER BY table_name
                    """,
                    (_pool_schema(self.pool),),
                )
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            names = [str(row[0]) for row in cursor.fetchall() if row and row[0]]
        tables = [
            {
                "name": name,
                "description": getattr(schema_map.get(name), "description", "") if schema_map.get(name) else "",
            }
            for name in names
        ]
        return {"status": "success", "tables": tables, "count": len(tables)}

    def preview_db_table(self, table_name: str, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Preview the database table."""
        normalized_table = str(table_name or "").strip()
        if not normalized_table:
            raise ValueError("table_name is required.")
        table_names = {entry["name"] for entry in self.list_db_tables().get("tables", [])}
        if normalized_table not in table_names:
            raise ValueError(f"Unknown table '{normalized_table}'.")

        try:
            normalized_limit = max(1, min(int(limit), 500))
        except (TypeError, ValueError):
            normalized_limit = 100
        try:
            normalized_offset = max(0, int(offset))
        except (TypeError, ValueError):
            normalized_offset = 0

        with self.pool.lock:
            cursor = self._db_cursor()
            table_ref = _qualified_sql_table(self.pool, normalized_table)
            placeholder = _sql_placeholder(self.pool)
            cursor.execute(f"SELECT * FROM {table_ref} LIMIT 0")
            columns = [desc[0] for desc in cursor.description or []]
            order_clause = _preview_order_clause(columns)
            cursor.execute(
                f"SELECT * FROM {table_ref}{order_clause} LIMIT {placeholder} OFFSET {placeholder}",
                (normalized_limit, normalized_offset),
            )
            rows = [
                {column: _decode_db_value(value) for column, value in zip(columns, row)}
                for row in cursor.fetchall()
            ]
            cursor.execute(f"SELECT COUNT(*) FROM {table_ref}")
            total_rows = int(cursor.fetchone()[0] or 0)

        return {
            "status": "success",
            "table_name": normalized_table,
            "columns": columns,
            "rows": rows,
            "count": len(rows),
            "total_rows": total_rows,
            "limit": normalized_limit,
            "offset": normalized_offset,
        }

    def query_db(self, sql: str, params: Any = None, limit: int = 200) -> Dict[str, Any]:
        """Query the database."""
        normalized_sql = str(sql or "").strip()
        if not normalized_sql:
            raise ValueError("sql is required.")
        first_token = normalized_sql.split(None, 1)[0].lower() if normalized_sql.split(None, 1) else ""
        allowed_tokens = {"select", "with", "explain"}
        if _pool_dialect(self.pool) == "sqlite":
            allowed_tokens.add("pragma")
        if _pool_dialect(self.pool) == "postgres":
            allowed_tokens.add("show")
        if first_token not in allowed_tokens:
            raise ValueError("DB Viewer only supports read-only SQL queries.")
        try:
            normalized_limit = max(1, min(int(limit), 1000))
        except (TypeError, ValueError):
            normalized_limit = 200

        with self.pool.lock:
            cursor = self._db_cursor()
            cursor.execute(normalized_sql, _normalize_db_params(params))
            columns = [desc[0] for desc in cursor.description or []]
            raw_rows = cursor.fetchmany(normalized_limit)
            truncated = len(raw_rows) == normalized_limit and cursor.fetchone() is not None
        rows = [
            {column: _decode_db_value(value) for column, value in zip(columns, row)}
            for row in raw_rows
        ]
        return {
            "status": "success",
            "sql": normalized_sql,
            "columns": columns,
            "rows": rows,
            "count": len(rows),
            "limit": normalized_limit,
            "truncated": truncated,
        }


class DispatcherWorkerAgent(StandbyAgent):
    """Agent implementation for dispatcher worker workflows."""
    DISPATCHER_DISCOVERY_PRACTICES = (
        "dispatcher-get-job",
        "dispatcher-register-worker",
        "dispatcher-post-job-result",
    )

    def __init__(
        self,
        name: str = "DispatcherWorker",
        host: str = "127.0.0.1",
        port: int = 8061,
        plaza_url: str | None = None,
        agent_card: Dict[str, Any] | None = None,
        pool: Any = None,
        dispatcher_address: str = "",
        capabilities: Any = None,
        job_capabilities: Any = None,
        poll_interval_sec: float | int | None = None,
        config: Any = None,
        config_path: Any = None,
        auto_register: bool | None = None,
    ):
        """Initialize the dispatcher worker agent."""
        loaded_config, dispatcher_settings = _resolve_dispatcher_settings(config, config_path=config_path)
        resolved_name = str(loaded_config.get("name") or name)
        resolved_dispatcher_address = str(
            dispatcher_address or dispatcher_settings.get("dispatcher_address") or loaded_config.get("dispatcher_address") or ""
        ).strip()
        resolved_capabilities = normalize_capabilities(
            capabilities or dispatcher_settings.get("capabilities") or loaded_config.get("capabilities") or []
        )
        configured_job_cap_entries = (
            job_capabilities
            or dispatcher_settings.get("job_capabilities")
            or loaded_config.get("job_capabilities")
            or []
        )
        resolved_job_cap_result = load_job_cap_map(configured_job_cap_entries)
        resolved_job_caps = resolved_job_cap_result.capabilities
        if resolved_job_cap_result.unavailable:
            unavailable_job_capabilities = set(resolved_job_cap_result.unavailable)
            resolved_capabilities = [
                capability_name
                for capability_name in resolved_capabilities
                if capability_name not in unavailable_job_capabilities
            ]
        if resolved_job_caps:
            for capability_name in resolved_job_caps:
                if capability_name not in resolved_capabilities:
                    resolved_capabilities.append(capability_name)
        resolved_poll_interval = poll_interval_sec if poll_interval_sec is not None else dispatcher_settings.get("poll_interval_sec", 10)
        try:
            resolved_poll_interval = max(float(resolved_poll_interval), 0.1)
        except (TypeError, ValueError):
            resolved_poll_interval = 10.0
        resolved_heartbeat_interval = dispatcher_settings.get("heartbeat_interval_sec", WORKER_HEARTBEAT_INTERVAL_SEC)
        try:
            resolved_heartbeat_interval = max(float(resolved_heartbeat_interval), 1.0)
        except (TypeError, ValueError):
            resolved_heartbeat_interval = WORKER_HEARTBEAT_INTERVAL_SEC
        resolved_auto_register = bool(
            auto_register if auto_register is not None else dispatcher_settings.get("auto_register", False)
        )
        direct_auth_token = str(
            dispatcher_settings.get("direct_auth_token")
            or loaded_config.get("direct_auth_token")
            or DISPATCHER_DIRECT_TOKEN
        ).strip()

        card = dict(agent_card or loaded_config.get("agent_card") or {})
        card.setdefault("name", resolved_name)
        card["party"] = _resolve_party(loaded_config, card)
        card["role"] = str(loaded_config.get("role") or card.get("role") or "worker")
        card["description"] = str(
            loaded_config.get("description") or card.get("description") or "Dispatcher worker that polls for matching jobs."
        )
        card["tags"] = _merge_tags(card.get("tags"), loaded_config.get("tags"), ["prompits", "dispatcher-worker", *resolved_capabilities])
        meta = dict(card.get("meta") or {})
        meta["capabilities"] = resolved_capabilities
        meta["job_capabilities"] = [capability.to_metadata() for capability in resolved_job_caps.values()]
        if resolved_dispatcher_address:
            meta["dispatcher_address"] = resolved_dispatcher_address
        meta.setdefault("party", card["party"])
        meta.setdefault("direct_auth_token", direct_auth_token)
        meta.setdefault("worker_template_name", resolved_name)
        meta.setdefault("reuse_plaza_identity", False)
        card["meta"] = meta

        super().__init__(
            name=resolved_name,
            host=host,
            port=port,
            plaza_url=plaza_url,
            agent_card=card,
            pool=pool,
        )

        self.dispatcher_settings = dispatcher_settings
        self.dispatcher_address = resolved_dispatcher_address
        self.capabilities = resolved_capabilities
        self.job_capabilities: Dict[str, JobCap] = resolved_job_caps
        self.unavailable_job_capabilities = dict(resolved_job_cap_result.unavailable)
        self.poll_interval_sec = resolved_poll_interval
        self.heartbeat_interval_sec = resolved_heartbeat_interval
        self.worker_id = build_id("dispatcher-worker")
        self.worker_session_started_at = utcnow_iso()
        self.worker_environment = self._build_worker_environment_snapshot(config=config, config_path=config_path)
        for capability_name, reason in self.unavailable_job_capabilities.items():
            self.logger.warning(
                "Skipping dispatcher job capability '%s' during startup: %s",
                capability_name,
                reason or "environment check failed.",
            )
        self._poll_stop_event = threading.Event()
        self._poll_thread: Optional[threading.Thread] = None
        self._poll_thread_lock = threading.Lock()
        self._heartbeat_stop_event = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_thread_lock = threading.Lock()
        self._active_job_id = ""
        self._active_job_lock = threading.Lock()
        self._worker_progress_lock = threading.Lock()
        self._worker_progress: dict[str, Any] = self._build_progress_snapshot(phase="idle", message="Worker initialized.")
        self._dispatcher_discovery_log_message = ""
        self._dispatcher_discovery_log_at = 0.0
        for capability in self.job_capabilities.values():
            bind_worker = getattr(capability, "bind_worker", None)
            if callable(bind_worker):
                bind_worker(self)
        self.logger.info(
            "Dispatcher worker initialized from config=%s with %s and dispatcher=%s",
            str(config_path or config or ""),
            _describe_pool(self.pool),
            self.dispatcher_address,
        )

        self._setup_worker_polling_events()

        if self.plaza_url and resolved_auto_register:
            self.register()

    def _log_dispatcher_discovery_message(
        self,
        message: str,
        *,
        level: str = "info",
        min_interval_sec: float = 30.0,
    ) -> None:
        """Internal helper to log the dispatcher discovery message."""
        normalized = str(message or "").strip()
        if not normalized:
            return
        now = time.time()
        if (
            normalized == self._dispatcher_discovery_log_message
            and (now - self._dispatcher_discovery_log_at) < max(float(min_interval_sec), 0.0)
        ):
            return
        getattr(self.logger, level, self.logger.info)(normalized)
        self._dispatcher_discovery_log_message = normalized
        self._dispatcher_discovery_log_at = now

    @staticmethod
    def _extract_dispatcher_address(entry: Any) -> str:
        """Internal helper to extract the dispatcher address."""
        if not isinstance(entry, Mapping):
            return ""
        card = entry.get("card") if isinstance(entry.get("card"), Mapping) else {}
        for candidate in (entry.get("address"), card.get("address") if isinstance(card, Mapping) else ""):
            normalized = str(candidate or "").strip().rstrip("/")
            if normalized:
                return normalized
        return ""

    @classmethod
    def _dispatcher_candidate_sort_key(cls, entry: Any) -> tuple[int, int, int, int, float]:
        """Internal helper to return the dispatcher candidate sort key."""
        if not isinstance(entry, Mapping):
            return (0, 0, 0, 0, 0.0)
        card = entry.get("card") if isinstance(entry.get("card"), Mapping) else {}
        tags = {tag.lower() for tag in normalize_string_list(card.get("tags"))}
        practices = card.get("practices") if isinstance(card.get("practices"), list) else []
        practice_ids = {
            str(practice.get("id") or "").strip().lower()
            for practice in practices
            if isinstance(practice, Mapping)
        }
        role = str(card.get("role") or entry.get("role") or "").strip().lower()
        name = str(entry.get("name") or card.get("name") or "").strip().lower()
        last_active = entry.get("last_active")
        try:
            normalized_last_active = float(last_active or 0.0)
        except (TypeError, ValueError):
            normalized_last_active = 0.0
        return (
            1 if role == "dispatcher" else 0,
            sum(1 for practice_id in cls.DISPATCHER_DISCOVERY_PRACTICES if practice_id in practice_ids),
            1 if "dispatcher" in tags else 0,
            1 if name == "dispatcher" else 0,
            normalized_last_active,
        )

    def _remember_dispatcher_address(self, address: Any, *, source: str = "") -> str:
        """Internal helper to remember the dispatcher address."""
        normalized = str(address or "").strip().rstrip("/")
        if not normalized:
            return ""
        previous = str(self.dispatcher_address or "").strip().rstrip("/")
        self.dispatcher_address = normalized
        meta = dict(self.agent_card.get("meta") or {})
        meta["dispatcher_address"] = normalized
        self.agent_card["meta"] = meta
        if normalized != previous:
            suffix = f" via {source}" if str(source or "").strip() else ""
            self.logger.info("Resolved dispatcher at %s%s.", normalized, suffix)
        return normalized

    def _discover_dispatcher_address(self, *, force: bool = False) -> str:
        """Internal helper to discover the dispatcher address."""
        if self.dispatcher_address and not force:
            return self.dispatcher_address
        if not self.plaza_url:
            return ""
        party = str(self.agent_card.get("party") or DISPATCHER_PARTY).strip() or DISPATCHER_PARTY

        search_plans = (
            {"role": "dispatcher", "practice": "dispatcher-get-job", "pit_type": "Agent", "party": party},
            {"role": "dispatcher", "practice": "dispatcher-register-worker", "pit_type": "Agent", "party": party},
            {"role": "dispatcher", "pit_type": "Agent", "party": party},
            {"practice": "dispatcher-get-job", "pit_type": "Agent", "party": party},
            {"name": "Dispatcher", "pit_type": "Agent", "party": party},
        )

        candidates: dict[str, Any] = {}
        for search_params in search_plans:
            results = self.search(**search_params) or []
            for entry in results:
                address = self._extract_dispatcher_address(entry)
                if not address:
                    continue
                candidate_key = str(entry.get("agent_id") or address)
                existing = candidates.get(candidate_key)
                if existing is None or self._dispatcher_candidate_sort_key(entry) > self._dispatcher_candidate_sort_key(existing):
                    candidates[candidate_key] = entry

        if candidates:
            selected = max(candidates.values(), key=self._dispatcher_candidate_sort_key)
            return self._remember_dispatcher_address(self._extract_dispatcher_address(selected), source="Plaza search")

        if not self.plaza_token:
            self._log_dispatcher_discovery_message(
                "Worker is waiting for Plaza registration before dispatcher discovery.",
                level="info",
            )
        else:
            self._log_dispatcher_discovery_message(
                "Worker could not find a dispatcher via Plaza yet.",
                level="warning",
            )
        return ""

    def _resolve_dispatcher_address(self) -> str:
        """Internal helper to resolve the dispatcher address."""
        return self._remember_dispatcher_address(self.dispatcher_address) or self._discover_dispatcher_address()

    def _build_worker_environment_snapshot(self, *, config: Any = None, config_path: Any = None) -> dict[str, Any]:
        """Internal helper to build the worker environment snapshot."""
        environment = {
            "hostname": str(socket.gethostname() or "").strip(),
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": sys.version.split()[0],
            "pid": os.getpid(),
            "cwd": os.getcwd(),
            "dispatcher_address": str(self.dispatcher_address or "").strip(),
            "plaza_url": str(self.plaza_url or "").strip(),
            "worker_address": str(self.agent_card.get("address") or f"http://{self.host}:{self.port}").strip(),
            "pool": {
                "type": self.pool.__class__.__name__ if self.pool is not None else "",
                "name": str(getattr(self.pool, "name", "") or "").strip(),
                "schema": str(getattr(self.pool, "schema", "") or "").strip(),
                "db_path": str(getattr(self.pool, "db_path", "") or "").strip(),
                "root_path": str(getattr(self.pool, "root_path", "") or "").strip(),
            },
        }
        if config_path:
            environment["config_path"] = str(config_path)
        config_reference = str(config or "").strip()
        if config_reference and "config_path" not in environment:
            environment["config"] = config_reference
        return environment

    @staticmethod
    def _build_progress_snapshot(
        *,
        phase: str = "",
        message: str = "",
        percent: Any = None,
        current: Any = None,
        total: Any = None,
        extra: Any = None,
    ) -> dict[str, Any]:
        """Internal helper to build the progress snapshot."""
        snapshot: dict[str, Any] = {
            "phase": str(phase or "").strip().lower() or "idle",
            "message": str(message or "").strip(),
            "updated_at": utcnow_iso(),
        }
        if percent is not None:
            try:
                snapshot["percent"] = max(0.0, min(float(percent), 100.0))
            except (TypeError, ValueError):
                pass
        if current is not None:
            snapshot["current"] = current
        if total is not None:
            snapshot["total"] = total
        if isinstance(extra, Mapping):
            snapshot["extra"] = dict(extra)
        return snapshot

    def update_progress(
        self,
        *,
        phase: str = "",
        message: str = "",
        percent: Any = None,
        current: Any = None,
        total: Any = None,
        extra: Any = None,
    ) -> dict[str, Any]:
        """Update the progress."""
        with self._worker_progress_lock:
            updated = dict(self._worker_progress)
            if phase:
                updated["phase"] = str(phase).strip().lower()
            if message:
                updated["message"] = str(message).strip()
            if percent is not None:
                try:
                    updated["percent"] = max(0.0, min(float(percent), 100.0))
                except (TypeError, ValueError):
                    updated.pop("percent", None)
            if current is not None:
                updated["current"] = current
            if total is not None:
                updated["total"] = total
            if isinstance(extra, Mapping):
                merged_extra = dict(updated.get("extra") or {})
                merged_extra.update(dict(extra))
                updated["extra"] = merged_extra
            updated["updated_at"] = utcnow_iso()
            self._worker_progress = updated
            return dict(updated)

    def _reset_progress(self, *, phase: str = "idle", message: str = "") -> dict[str, Any]:
        """Internal helper to reset the progress."""
        with self._worker_progress_lock:
            self._worker_progress = self._build_progress_snapshot(phase=phase, message=message)
            return dict(self._worker_progress)

    def _current_progress_snapshot(self) -> dict[str, Any]:
        """Internal helper to return the current progress snapshot."""
        with self._worker_progress_lock:
            return dict(self._worker_progress)

    def _active_job_snapshot(self) -> dict[str, Any]:
        """Internal helper to return the active job snapshot."""
        with self._active_job_lock:
            active_job_id = str(self._active_job_id or "").strip()
        progress = self._current_progress_snapshot()
        if not active_job_id:
            return {"id": "", "status": "idle", "progress": progress, "started_at": ""}
        return {
            "id": active_job_id,
            "status": "working",
            "progress": progress,
            "started_at": str(progress.get("started_at") or progress.get("updated_at") or ""),
        }

    def _worker_status(self) -> str:
        """Internal helper to return the worker status."""
        active_job = self._active_job_snapshot()
        return "working" if active_job.get("id") else "online"

    def _worker_metadata(self) -> dict[str, Any]:
        """Internal helper for worker metadata."""
        meta = dict(self.agent_card.get("meta") or {})
        meta["worker_id"] = self.worker_id
        meta["environment"] = dict(self.worker_environment)
        meta["heartbeat"] = {
            "session_started_at": self.worker_session_started_at,
            "active_job": self._active_job_snapshot(),
            "progress": self._current_progress_snapshot(),
            "heartbeat_interval_sec": self.heartbeat_interval_sec,
        }
        return meta

    def _send_worker_heartbeat(self, *, event_type: str = "heartbeat") -> Dict[str, Any]:
        """Internal helper to send the worker heartbeat."""
        dispatcher_address = self._resolve_dispatcher_address()
        if not dispatcher_address:
            return {"status": "pending", "worker_id": self._worker_identity(), "error": "Dispatcher is not available yet."}
        return self.UsePractice(
            "dispatcher-register-worker",
            {
                "worker_id": self._worker_identity(),
                "name": self.name,
                "address": self.agent_card.get("address") or f"http://{self.host}:{self.port}",
                "capabilities": self.advertised_capabilities(),
                "metadata": self._worker_metadata(),
                "plaza_url": self.plaza_url or "",
                "status": self._worker_status(),
                "event_type": event_type,
            },
            pit_address=dispatcher_address,
        )

    def _setup_worker_polling_events(self) -> None:
        """Internal helper to set up the worker polling events."""
        @self.app.on_event("startup")
        def _start_worker_polling():
            """Internal helper to start the worker polling."""
            self._start_polling_thread()
            self._start_heartbeat_thread()

        @self.app.on_event("shutdown")
        def _stop_worker_polling():
            """Internal helper to stop the worker polling."""
            self._stop_polling_thread()
            self._stop_heartbeat_thread()

    def _start_polling_thread(self) -> bool:
        """Internal helper to start the polling thread."""
        if not self.dispatcher_address and not self.plaza_url:
            self.logger.warning(
                "Worker polling is disabled because neither dispatcher_address nor plaza_url is configured."
            )
            return False
        with self._poll_thread_lock:
            current = self._poll_thread
            if current and current.is_alive():
                return False
            self._poll_stop_event = threading.Event()
            poll_thread = threading.Thread(target=self._poll_loop, daemon=True, name=f"{self.name}-dispatcher-poll")
            self._poll_thread = poll_thread
            poll_thread.start()
            if self.dispatcher_address:
                self.logger.info(
                    "Starting worker poll loop against %s every %.1fs.",
                    self.dispatcher_address,
                    self.poll_interval_sec,
                )
            else:
                self.logger.info(
                    "Starting worker poll loop with Plaza-based dispatcher discovery every %.1fs.",
                    self.poll_interval_sec,
                )
            return True

    def _start_heartbeat_thread(self) -> bool:
        """Internal helper to start the heartbeat thread."""
        with self._heartbeat_thread_lock:
            current = self._heartbeat_thread
            if current and current.is_alive():
                return False
            self._heartbeat_stop_event = threading.Event()
            heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                daemon=True,
                name=f"{self.name}-dispatcher-heartbeat",
            )
            self._heartbeat_thread = heartbeat_thread
            heartbeat_thread.start()
            self.logger.info("Starting worker heartbeat loop every %.1fs.", self.heartbeat_interval_sec)
            return True

    def _stop_heartbeat_thread(self, join_timeout: float | None = None) -> bool:
        """Internal helper to stop the heartbeat thread."""
        with self._heartbeat_thread_lock:
            heartbeat_thread = self._heartbeat_thread
            if heartbeat_thread is None:
                return False
            self._heartbeat_stop_event.set()
        heartbeat_thread.join(timeout=max(float(join_timeout or (self.heartbeat_interval_sec + 1.0)), 0.2))
        with self._heartbeat_thread_lock:
            if self._heartbeat_thread is heartbeat_thread and not heartbeat_thread.is_alive():
                self._heartbeat_thread = None
        self.logger.info("Stopped worker heartbeat loop.")
        return True

    def _stop_polling_thread(self, join_timeout: float | None = None) -> bool:
        """Internal helper to stop the polling thread."""
        with self._poll_thread_lock:
            poll_thread = self._poll_thread
            if poll_thread is None:
                return False
            self._poll_stop_event.set()
        poll_thread.join(timeout=max(float(join_timeout or (self.poll_interval_sec + 1.0)), 0.2))
        with self._poll_thread_lock:
            if self._poll_thread is poll_thread and not poll_thread.is_alive():
                self._poll_thread = None
        self.logger.info("Stopped worker poll loop.")
        return True

    def _poll_loop(self) -> None:
        """Internal helper for poll loop."""
        interval = max(float(self.poll_interval_sec), 0.1)
        while not self._poll_stop_event.is_set():
            try:
                self.logger.info("Polling dispatcher for matching jobs...")
                self.run_once()
            except Exception as exc:
                self.logger.exception("Worker poll iteration failed: %s", exc)
            if self._poll_stop_event.wait(interval):
                break

    def _heartbeat_loop(self) -> None:
        """Internal helper for heartbeat loop."""
        interval = max(float(self.heartbeat_interval_sec), 1.0)
        while not self._heartbeat_stop_event.is_set():
            try:
                self._send_worker_heartbeat(event_type="heartbeat")
            except Exception as exc:
                self.logger.warning("Worker heartbeat failed: %s", exc)
            if self._heartbeat_stop_event.wait(interval):
                break

    def _worker_identity(self) -> str:
        """Internal helper to return the worker identity."""
        return str(self.worker_id or self.name)

    def advertised_capabilities(self) -> list[str]:
        """Handle advertised capabilities for the dispatcher worker agent."""
        return list(self.capabilities)

    def register_capabilities(self) -> Dict[str, Any]:
        """Register the capabilities."""
        return self._send_worker_heartbeat(event_type="register")

    def request_job(self) -> Dict[str, Any]:
        """Request the job."""
        dispatcher_address = self._resolve_dispatcher_address()
        if not dispatcher_address:
            return {"status": "pending", "job": None, "error": "Dispatcher is not available yet."}
        response = self.UsePractice(
            "dispatcher-get-job",
            {
                "worker_id": self._worker_identity(),
                "name": self.name,
                "address": self.agent_card.get("address") or f"http://{self.host}:{self.port}",
                "capabilities": self.advertised_capabilities(),
                "metadata": self._worker_metadata(),
                "plaza_url": self.plaza_url or "",
            },
            pit_address=dispatcher_address,
        )
        payload = dict(response or {}) if isinstance(response, Mapping) else {}
        payload["job"] = coerce_job_detail(payload.get("job"))
        job = payload.get("job")
        if isinstance(job, JobDetail):
            self.logger.info("Claimed dispatcher job %s for capability '%s'.", job.id, job.required_capability)
        else:
            self.logger.info("No matching dispatcher job available.")
        return payload

    def post_job_result(self, job_result: JobResult | Mapping[str, Any]) -> Dict[str, Any]:
        """Post the job result."""
        dispatcher_address = self._resolve_dispatcher_address()
        if not dispatcher_address:
            raise ValueError("dispatcher_address is required for job reporting.")
        result = coerce_job_result(job_result, worker_id=self._worker_identity())
        return self.UsePractice("dispatcher-post-job-result", result.to_payload(), pit_address=dispatcher_address)

    def report_job_result(
        self,
        *,
        job_id: str,
        status: str = "completed",
        collected_rows: Any = None,
        raw_payload: Any = None,
        result_summary: Any = None,
        error: str = "",
        target_table: str = "",
    ) -> Dict[str, Any]:
        """Report the job result."""
        return self.post_job_result(
            JobResult(
                job_id=job_id,
                worker_id=self._worker_identity(),
                status=status,
                collected_rows=coerce_record_list(collected_rows),
                raw_payload=raw_payload,
                result_summary=coerce_json_object(result_summary),
                error=error,
                target_table=target_table,
            )
        )

    def process_job(self, job: JobDetail) -> Any:
        """Handle process job for the dispatcher worker agent."""
        capability_name = str(job.required_capability or "").strip().lower()
        capability = self.job_capabilities.get(capability_name)
        if capability is None:
            raise ValueError(f"No JobCap is registered for capability '{capability_name or job.id}'.")
        return capability(job)

    def _set_active_job(self, job: JobDetail | Mapping[str, Any] | str | None = None) -> None:
        """Internal helper to set the active job."""
        normalized_job_id = ""
        capability_name = ""
        targets: list[str] = []
        if isinstance(job, JobDetail):
            normalized_job_id = str(job.id or "").strip()
            capability_name = str(job.required_capability or "").strip()
            targets = list(job.targets or [])
        elif isinstance(job, Mapping):
            normalized_job_id = str(job.get("id") or "").strip()
            capability_name = str(job.get("required_capability") or "").strip()
            targets = normalize_string_list(job.get("targets"))
        else:
            normalized_job_id = str(job or "").strip()
        with self._active_job_lock:
            self._active_job_id = normalized_job_id
        if normalized_job_id:
            progress = self._build_progress_snapshot(
                phase="working",
                message=f"Processing {capability_name}." if capability_name else f"Processing job {normalized_job_id}.",
                extra={"job_id": normalized_job_id, "required_capability": capability_name, "targets": targets},
            )
            progress["started_at"] = utcnow_iso()
            with self._worker_progress_lock:
                self._worker_progress = progress
        else:
            self._reset_progress(phase="idle", message="Waiting for the next job.")

    def _fetch_job_control_row(self, job_id: str) -> dict[str, Any] | None:
        """Internal helper to fetch the job control row."""
        normalized_job_id = str(job_id or "").strip()
        if not normalized_job_id:
            return None
        rows: Any = []
        dispatcher_address = self._resolve_dispatcher_address()
        if dispatcher_address:
            rows = self.UsePractice(
                "pool-get-table-data",
                {"table_name": TABLE_JOBS, "id_or_where": normalized_job_id, "table_schema": jobs_schema_dict()},
                pit_address=dispatcher_address,
            )
        elif getattr(self, "pool", None) is not None:
            rows = self.pool._GetTableData(TABLE_JOBS, normalized_job_id)
        latest_rows = DispatcherAgent._latest_job_rows(rows if isinstance(rows, list) else [])
        return dict(latest_rows[0]) if latest_rows else None

    def is_stop_requested(self, job: JobDetail | Mapping[str, Any] | str) -> bool:
        """Return whether the value is a stop requested."""
        job_id = str(job.id if isinstance(job, JobDetail) else job.get("id") if isinstance(job, Mapping) else job or "").strip()
        if not job_id:
            return False
        try:
            row = self._fetch_job_control_row(job_id)
        except Exception:
            return False
        if not isinstance(row, Mapping):
            return False
        status = str(row.get("status") or "").strip().lower()
        if status == "stopping":
            return True
        metadata = row.get("metadata")
        controls = dict(metadata.get("control") or {}) if isinstance(metadata, Mapping) and isinstance(metadata.get("control"), Mapping) else {}
        effective_action = str(controls.get("effective_action") or controls.get("action") or "").strip().lower()
        if effective_action == "force_terminate":
            return status not in {"completed", "cancelled", "deleted"}
        return effective_action == "stop" and status in {"claimed", "stopping"}

    def raise_if_stop_requested(self, job: JobDetail | Mapping[str, Any] | str) -> None:
        """Handle raise if stop requested for the dispatcher worker agent."""
        job_id = str(job.id if isinstance(job, JobDetail) else job.get("id") if isinstance(job, Mapping) else job or "").strip()
        if not job_id or not self.is_stop_requested(job_id):
            return
        try:
            row = self._fetch_job_control_row(job_id)
        except Exception:
            row = None
        metadata = row.get("metadata") if isinstance(row, Mapping) else {}
        controls = dict(metadata.get("control") or {}) if isinstance(metadata, Mapping) and isinstance(metadata.get("control"), Mapping) else {}
        raise DispatcherJobStopRequested(job_id, str(controls.get("reason") or ""))

    def _normalize_handler_result(self, job: JobDetail, result: Any) -> JobResult:
        """Internal helper to normalize the handler result."""
        worker_id = self._worker_identity()
        if isinstance(result, JobResult):
            return result.with_defaults(job_id=job.id, worker_id=worker_id)
        if isinstance(result, Mapping):
            status_text = str(result.get("status") or "").strip().lower()
            has_job_fields = any(key in result for key in ("collected_rows", "raw_payload", "result_summary", "error", "target_table"))
            if status_text in {"completed", "failed", "retry", "stopped"}:
                return coerce_job_result(result, job_id=job.id, worker_id=worker_id)
            if has_job_fields:
                normalized_result = dict(result)
                normalized_result["status"] = "completed"
                return coerce_job_result(normalized_result, job_id=job.id, worker_id=worker_id)
            if status_text:
                raise ValueError(
                    "Job capability returned unsupported status "
                    f"'{status_text}'. Return one of completed/failed/retry/stopped, "
                    "or return job data without a generic practice envelope."
                )
            return JobResult(
                job_id=job.id,
                worker_id=worker_id,
                status="completed",
                collected_rows=[dict(result)],
                raw_payload=dict(result),
                result_summary={"rows": 1},
            )
        if isinstance(result, list):
            return JobResult(
                job_id=job.id,
                worker_id=worker_id,
                status="completed",
                collected_rows=[dict(item) for item in result if isinstance(item, Mapping)],
                raw_payload=result,
                result_summary={"rows": len(result)},
            )
        if result is None:
            raise ValueError(
                "Job capability returned None. Return a JobResult, a row mapping/list, "
                "or raise an exception when the job cannot be completed."
            )
        return JobResult(
            job_id=job.id,
            worker_id=worker_id,
            status="completed",
            collected_rows=[],
            raw_payload=coerce_json_payload(result),
            result_summary={"value": result},
        )

    def run_once(self, handler: Optional[Callable[[JobDetail], Any]] = None) -> Dict[str, Any]:
        """Run the once."""
        self.register_capabilities()
        response = self.request_job()
        job = response.get("job") if isinstance(response, Mapping) else None
        if not isinstance(job, JobDetail):
            self._reset_progress(phase="idle", message="Waiting for the next job.")
            return {"status": "idle", "job": None}

        self._set_active_job(job)
        try:
            self._send_worker_heartbeat(event_type="job_start")
        except Exception:
            pass
        self.logger.info("Starting dispatcher job %s for capability '%s'.", job.id, job.required_capability)
        try:
            self.raise_if_stop_requested(job)
            outcome = handler(job) if handler else self.process_job(job)
            normalized = self._normalize_handler_result(job, outcome)
            normalized_status = str(normalized.status or "completed").strip().lower()
            if normalized_status == "stopped":
                self.update_progress(phase="stopped", message=f"Job {job.id} was stopped.")
                report = self.post_job_result(normalized)
                self.logger.warning("Stopped dispatcher job %s for capability '%s'.", job.id, job.required_capability)
                return {"status": "stopped", "job": job, "job_result": normalized, "report": report}
            if normalized_status == "retry":
                self.update_progress(phase="retry", message=f"Job {job.id} requested retry.")
                report = self.post_job_result(normalized)
                self.logger.warning(
                    "Dispatcher job %s requested retry for capability '%s': %s",
                    job.id,
                    job.required_capability,
                    normalized.error or "Job handler requested retry.",
                )
                return {"status": "retry", "job": job, "job_result": normalized, "report": report}
            if normalized_status in {"error", "failed"}:
                normalized = normalized.model_copy(
                    update={"status": "failed", "error": str(normalized.error or "Job handler returned failure.")}
                )
                self.update_progress(phase="failed", message=f"Job {job.id} failed.")
                report = self.post_job_result(normalized)
                self.logger.warning(
                    "Dispatcher job %s finished with failure for capability '%s': %s",
                    job.id,
                    job.required_capability,
                    normalized.error or "Job handler returned failure.",
                )
                return {"status": "failed", "job": job, "job_result": normalized, "report": report}

            self.update_progress(phase="completed", message=f"Job {job.id} completed.")
            report = self.post_job_result(normalized)
            self.logger.info("Completed dispatcher job %s for capability '%s'.", job.id, job.required_capability)
            return {"status": "completed", "job": job, "job_result": normalized, "report": report}
        except DispatcherJobStopRequested as exc:
            normalized = JobResult(
                job_id=job.id,
                worker_id=self._worker_identity(),
                status="stopped",
                result_summary={"stopped": True, "exception": exc.__class__.__name__},
                error=str(exc),
            )
            self.update_progress(phase="stopped", message=f"Job {job.id} was stopped.")
            report = self.post_job_result(normalized)
            self.logger.warning("Reported dispatcher job %s as stopped for capability '%s'.", job.id, job.required_capability)
            return {"status": "stopped", "job": job, "job_result": normalized, "report": report}
        except Exception as exc:
            max_attempts = max(int(job.max_attempts or 1), 1)
            attempts = max(int(job.attempts or 0), 0)
            should_retry = attempts < max_attempts and not isinstance(exc, ValueError)
            reported_status = "retry" if should_retry else "failed"
            self.logger.exception(
                "Dispatcher job %s failed while processing capability '%s': %s",
                job.id,
                job.required_capability,
                exc,
            )
            normalized = JobResult(
                job_id=job.id,
                worker_id=self._worker_identity(),
                status=reported_status,
                result_summary={
                    "exception": exc.__class__.__name__,
                    "retryable": should_retry,
                    "attempts": attempts,
                    "max_attempts": max_attempts,
                },
                error=str(exc),
            )
            self.update_progress(
                phase="retry" if should_retry else "failed",
                message=f"Job {job.id} failed: {exc}",
            )
            report = self.post_job_result(normalized)
            if should_retry:
                self.logger.warning(
                    "Reported dispatcher job %s for retry on capability '%s' (%s/%s attempts used).",
                    job.id,
                    job.required_capability,
                    attempts,
                    max_attempts,
                )
                return {"status": "retry", "job": job, "job_result": normalized, "report": report}
            self.logger.warning("Reported dispatcher job %s as failed for capability '%s'.", job.id, job.required_capability)
            return {"status": "failed", "job": job, "job_result": normalized, "report": report}
        finally:
            self._set_active_job("")
            try:
                self._send_worker_heartbeat(event_type="job_finish")
            except Exception:
                pass

    def run_forever(
        self,
        handler: Optional[Callable[[JobDetail], Any]] = None,
        *,
        iterations: Optional[int] = None,
        stop_event: Any = None,
        sleep_interval_sec: Optional[float] = None,
    ) -> int:
        """Run the forever."""
        interval = self.poll_interval_sec if sleep_interval_sec is None else float(sleep_interval_sec)
        completed_iterations = 0
        while True:
            if stop_event is not None and getattr(stop_event, "is_set", lambda: False)():
                break
            if iterations is not None and completed_iterations >= int(iterations):
                break
            self.run_once(handler=handler)
            completed_iterations += 1
            time.sleep(max(interval, 0.1))
        return completed_iterations
