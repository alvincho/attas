"""
Maintenance job caps for `prompits.dispatcher.archive_jobs`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the dispatcher package
coordinates job routing, worker selection, and queue management.
"""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from prompits.dispatcher.jobcap import JobCap
from prompits.dispatcher.models import JobDetail, JobResult
from prompits.dispatcher.runtime import parse_datetime_value, utcnow_iso
from prompits.dispatcher.schema import (
    TABLE_JOB_ARCHIVE,
    TABLE_JOBS,
    TABLE_RAW_PAYLOADS,
    TABLE_RAW_PAYLOADS_ARCHIVE,
    TABLE_RESULT_ROWS,
    TABLE_RESULT_ROWS_ARCHIVE,
    TABLE_WORKER_HISTORY,
    TABLE_WORKER_HISTORY_ARCHIVE,
    ensure_dispatcher_tables,
)


RELATED_ARCHIVE_TABLES: tuple[dict[str, str], ...] = (
    {
        "source_table": TABLE_WORKER_HISTORY,
        "archive_table": TABLE_WORKER_HISTORY_ARCHIVE,
        "timestamp_column": "captured_at",
        "summary_key": "worker_history",
    },
    {
        "source_table": TABLE_RESULT_ROWS,
        "archive_table": TABLE_RESULT_ROWS_ARCHIVE,
        "timestamp_column": "recorded_at",
        "summary_key": "job_results",
    },
    {
        "source_table": TABLE_RAW_PAYLOADS,
        "archive_table": TABLE_RAW_PAYLOADS_ARCHIVE,
        "timestamp_column": "collected_at",
        "summary_key": "raw_payloads",
    },
)

RETENTION_ARCHIVE_TABLES: tuple[dict[str, str], ...] = (
    {
        "archive_table": TABLE_JOB_ARCHIVE,
        "timestamp_column": "completed_at",
        "summary_key": "jobs",
    },
    {
        "archive_table": TABLE_WORKER_HISTORY_ARCHIVE,
        "timestamp_column": "captured_at",
        "summary_key": "worker_history",
    },
    {
        "archive_table": TABLE_RESULT_ROWS_ARCHIVE,
        "timestamp_column": "recorded_at",
        "summary_key": "job_results",
    },
    {
        "archive_table": TABLE_RAW_PAYLOADS_ARCHIVE,
        "timestamp_column": "collected_at",
        "summary_key": "raw_payloads",
    },
)

DEFAULT_RELATED_TABLE_BATCH_SIZE = 5000
DEFAULT_ARCHIVE_OLDER_THAN_HOURS = 24.0
DEFAULT_CLEANUP_RETENTION_DAYS = 30
DEFAULT_CLEANUP_BATCH_SIZE = 5000


def _pool_dialect(pool: Any) -> str:
    """Return the normalized pool dialect."""
    normalized = str(getattr(pool.__class__, "__name__", "") or "").strip().lower()
    if normalized == "postgrespool":
        return "postgres"
    if normalized == "sqlitepool":
        return "sqlite"
    return "unknown"


def _pool_schema(pool: Any) -> str:
    """Return the configured pool schema."""
    return str(getattr(pool, "schema", "public") or "public").strip() or "public"


def _quote_sql_identifier(identifier: str) -> str:
    """Return the quoted SQL identifier."""
    return '"' + str(identifier or "").replace('"', '""') + '"'


def _qualified_sql_table(pool: Any, table_name: str) -> str:
    """Return the fully-qualified SQL table reference."""
    if _pool_dialect(pool) == "postgres":
        return f"{_quote_sql_identifier(_pool_schema(pool))}.{_quote_sql_identifier(table_name)}"
    return _quote_sql_identifier(table_name)


def _sql_placeholder(pool: Any) -> str:
    """Return the parameter placeholder for the connected pool."""
    return "%s" if _pool_dialect(pool) == "postgres" else "?"


def _coerce_bool(value: Any, default: bool = False) -> bool:
    """Return a boolean from a config or job-payload value."""
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return bool(default)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return bool(default)


def _coerce_non_negative_float(value: Any, default: float) -> float:
    """Return a non-negative float with a fallback."""
    try:
        return max(float(value), 0.0)
    except (TypeError, ValueError):
        return max(float(default or 0.0), 0.0)


def _utc_cutoff_iso(*, hours: float = 0.0, days: float = 0.0) -> str:
    """Return an ISO cutoff timestamp relative to now."""
    return (datetime.now(timezone.utc) - timedelta(hours=float(hours or 0.0), days=float(days or 0.0))).isoformat()


def _job_row_timestamp(row: Mapping[str, Any]) -> datetime:
    """Return the best timestamp available for one job row."""
    candidates = (
        parse_datetime_value(row.get("updated_at")),
        parse_datetime_value(row.get("completed_at")),
        parse_datetime_value(row.get("created_at")),
    )
    return max(candidates)


def _latest_job_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return the latest row for each job id."""
    latest_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        job_id = str(row.get("id") or "").strip()
        if not job_id:
            continue
        current = dict(row)
        existing = latest_by_id.get(job_id)
        if existing is None or _job_row_timestamp(current) >= _job_row_timestamp(existing):
            latest_by_id[job_id] = current
    return list(latest_by_id.values())


def _delete_job_row(pool: Any, table_name: str, job_id: str) -> None:
    """Delete one job row by id."""
    normalized_job_id = str(job_id or "").strip()
    if not normalized_job_id:
        return
    conn = getattr(pool, "conn", None)
    if conn is None:
        raise RuntimeError("Daily Job Archive requires a connected pool.")
    lock = getattr(pool, "lock", None)
    context = lock if lock is not None else nullcontext()
    with context:
        cursor = conn.cursor()
        cursor.execute(
            f"DELETE FROM {_qualified_sql_table(pool, table_name)} "
            f"WHERE {_quote_sql_identifier('id')} = {_sql_placeholder(pool)}",
            [normalized_job_id],
        )
        if hasattr(conn, "commit"):
            conn.commit()


def _fetch_rows_before(
    pool: Any,
    *,
    table_name: str,
    timestamp_column: str,
    cutoff: str,
    batch_size: int,
) -> list[dict[str, Any]]:
    """Fetch a bounded batch of rows older than a timestamp cutoff."""
    if not pool._TableExists(table_name):
        return []
    conn = getattr(pool, "conn", None)
    if conn is None:
        raise RuntimeError("Daily Job Archive requires a connected pool.")
    lock = getattr(pool, "lock", None)
    context = lock if lock is not None else nullcontext()
    placeholder = _sql_placeholder(pool)
    with context:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM {_qualified_sql_table(pool, table_name)} "
            f"WHERE {_quote_sql_identifier(timestamp_column)} < {placeholder} "
            f"ORDER BY ({_quote_sql_identifier(timestamp_column)} IS NULL) ASC, "
            f"{_quote_sql_identifier(timestamp_column)} ASC, {_quote_sql_identifier('id')} ASC "
            f"LIMIT {placeholder}",
            [cutoff, max(int(batch_size or 1), 1)],
        )
        columns = [desc[0] for desc in cursor.description or []]
        rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in rows]


def _fetch_completed_job_rows(pool: Any, *, batch_size: int) -> list[dict[str, Any]]:
    """Fetch a bounded batch of completed active jobs."""
    if not pool._TableExists(TABLE_JOBS):
        return []
    conn = getattr(pool, "conn", None)
    if conn is None:
        raise RuntimeError("Daily Job Archive requires a connected pool.")
    lock = getattr(pool, "lock", None)
    context = lock if lock is not None else nullcontext()
    placeholder = _sql_placeholder(pool)
    with context:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM {_qualified_sql_table(pool, TABLE_JOBS)} "
            f"WHERE lower(coalesce({_quote_sql_identifier('status')}, '')) = {placeholder} "
            f"ORDER BY ({_quote_sql_identifier('completed_at')} IS NULL) ASC, "
            f"{_quote_sql_identifier('completed_at')} ASC, "
            f"({_quote_sql_identifier('updated_at')} IS NULL) ASC, "
            f"{_quote_sql_identifier('updated_at')} ASC, "
            f"({_quote_sql_identifier('created_at')} IS NULL) ASC, "
            f"{_quote_sql_identifier('created_at')} ASC, "
            f"{_quote_sql_identifier('id')} ASC "
            f"LIMIT {placeholder}",
            ["completed", max(int(batch_size or 1), 1)],
        )
        columns = [desc[0] for desc in cursor.description or []]
        rows = cursor.fetchall()
    return [dict(zip(columns, row)) for row in rows]


def _count_completed_job_rows(pool: Any) -> int:
    """Return the active completed job count."""
    if not pool._TableExists(TABLE_JOBS):
        return 0
    rows = pool._Query(
        f"SELECT COUNT(*) FROM {_qualified_sql_table(pool, TABLE_JOBS)} "
        f"WHERE lower(coalesce({_quote_sql_identifier('status')}, '')) = {_sql_placeholder(pool)}",
        ["completed"],
    )
    try:
        return int(rows[0][0])
    except (IndexError, TypeError, ValueError):
        return 0


def _delete_rows_by_ids(pool: Any, table_name: str, row_ids: Iterable[Any]) -> int:
    """Delete rows by primary id and return the number deleted."""
    normalized_ids = [str(row_id or "").strip() for row_id in row_ids if str(row_id or "").strip()]
    if not normalized_ids:
        return 0
    conn = getattr(pool, "conn", None)
    if conn is None:
        raise RuntimeError("Daily Job Archive requires a connected pool.")
    lock = getattr(pool, "lock", None)
    context = lock if lock is not None else nullcontext()
    placeholder = _sql_placeholder(pool)
    placeholders = ", ".join(placeholder for _ in normalized_ids)
    with context:
        cursor = conn.cursor()
        cursor.execute(
            f"DELETE FROM {_qualified_sql_table(pool, table_name)} "
            f"WHERE {_quote_sql_identifier('id')} IN ({placeholders})",
            normalized_ids,
        )
        deleted_count = int(getattr(cursor, "rowcount", 0) or 0)
        if hasattr(conn, "commit"):
            conn.commit()
    return max(deleted_count, 0)


def _archive_covers_active_row(active_row: Mapping[str, Any], archive_row: Mapping[str, Any] | None) -> bool:
    """Return whether the archive already holds the latest completed state."""
    if not isinstance(archive_row, Mapping):
        return False
    return _job_row_timestamp(archive_row) >= _job_row_timestamp(active_row)


def _coerce_positive_int(value: Any, default: int) -> int:
    """Return one positive integer with a fallback."""
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return max(int(default or 1), 1)


def _archive_completed_jobs(pool: Any, *, batch_size: int) -> dict[str, Any]:
    """Archive completed jobs from the active queue."""
    ensure_dispatcher_tables(pool, [TABLE_JOBS, TABLE_JOB_ARCHIVE])
    completed_jobs_seen = _count_completed_job_rows(pool)
    candidates = _fetch_completed_job_rows(pool, batch_size=batch_size)

    archived_jobs = 0
    already_archived_jobs = 0
    deleted_active_rows = 0
    processed_job_ids: list[str] = []

    for row in candidates:
        job_id = str(row.get("id") or "").strip()
        if not job_id:
            continue
        processed_job_ids.append(job_id)
        archived_rows = _latest_job_rows(pool._GetTableData(TABLE_JOB_ARCHIVE, job_id) or [])
        archived_row = archived_rows[0] if archived_rows else None
        if _archive_covers_active_row(row, archived_row):
            already_archived_jobs += 1
            deleted_active_rows += _delete_rows_by_ids(pool, TABLE_JOBS, [job_id])
            continue

        archive_storage = dict(row)
        archive_storage["archived_at"] = utcnow_iso()
        if not pool._Insert(TABLE_JOB_ARCHIVE, archive_storage):
            raise RuntimeError(f"Failed to archive dispatcher job '{job_id}'.")
        archived_jobs += 1
        deleted_active_rows += _delete_rows_by_ids(pool, TABLE_JOBS, [job_id])

    return {
        "processed_job_ids": processed_job_ids,
        "completed_jobs_seen": completed_jobs_seen,
        "processed_jobs": len(candidates),
        "archived_jobs": archived_jobs,
        "already_archived_jobs": already_archived_jobs,
        "deleted_active_rows": deleted_active_rows,
        "remaining_completed_jobs": max(completed_jobs_seen - len(candidates), 0),
    }


def _archive_related_table(
    pool: Any,
    *,
    source_table: str,
    archive_table: str,
    timestamp_column: str,
    cutoff: str,
    batch_size: int,
) -> dict[str, Any]:
    """Archive one append-only dispatcher table in a bounded batch."""
    ensure_dispatcher_tables(pool, [source_table, archive_table])
    rows = _fetch_rows_before(
        pool,
        table_name=source_table,
        timestamp_column=timestamp_column,
        cutoff=cutoff,
        batch_size=batch_size,
    )
    archived_rows = 0
    deleted_rows = 0
    if rows:
        archived_at = utcnow_iso()
        archive_rows = []
        row_ids = []
        for row in rows:
            row_id = str(row.get("id") or "").strip()
            if not row_id:
                continue
            storage = dict(row)
            storage["archived_at"] = archived_at
            archive_rows.append(storage)
            row_ids.append(row_id)
        if archive_rows:
            if not pool._InsertMany(archive_table, archive_rows):
                raise RuntimeError(f"Failed to archive dispatcher table '{source_table}'.")
            archived_rows = len(archive_rows)
            deleted_rows = _delete_rows_by_ids(pool, source_table, row_ids)
    return {
        "source_table": source_table,
        "archive_table": archive_table,
        "timestamp_column": timestamp_column,
        "cutoff": cutoff,
        "processed_rows": len(rows),
        "archived_rows": archived_rows,
        "deleted_active_rows": deleted_rows,
    }


def _purge_archive_table(
    pool: Any,
    *,
    archive_table: str,
    timestamp_column: str,
    cutoff: str,
    batch_size: int,
) -> dict[str, Any]:
    """Delete archive rows older than the retention cutoff."""
    ensure_dispatcher_tables(pool, [archive_table])
    rows = _fetch_rows_before(
        pool,
        table_name=archive_table,
        timestamp_column=timestamp_column,
        cutoff=cutoff,
        batch_size=batch_size,
    )
    purged_rows = _delete_rows_by_ids(pool, archive_table, [row.get("id") for row in rows])
    return {
        "archive_table": archive_table,
        "timestamp_column": timestamp_column,
        "cutoff": cutoff,
        "processed_rows": len(rows),
        "purged_rows": purged_rows,
    }


class DailyJobArchiveJobCap(JobCap):
    """Sweep completed dispatcher jobs from the active queue into the archive table."""

    DEFAULT_NAME = "daily job archive"

    def __init__(
        self,
        name: str = "",
        *,
        batch_size: int = 500,
        archive_related_tables: bool = False,
        related_table_batch_size: int = DEFAULT_RELATED_TABLE_BATCH_SIZE,
        archive_older_than_hours: float = DEFAULT_ARCHIVE_OLDER_THAN_HOURS,
        cleanup_retention_days: int | None = None,
        cleanup_batch_size: int = DEFAULT_CLEANUP_BATCH_SIZE,
        **kwargs: Any,
    ):
        """Initialize the archive-sweep job cap."""
        super().__init__(name=name or self.DEFAULT_NAME, **kwargs)
        self.batch_size = _coerce_positive_int(batch_size, 500)
        self.archive_related_tables = bool(archive_related_tables)
        self.related_table_batch_size = _coerce_positive_int(
            related_table_batch_size,
            DEFAULT_RELATED_TABLE_BATCH_SIZE,
        )
        self.archive_older_than_hours = _coerce_non_negative_float(
            archive_older_than_hours,
            DEFAULT_ARCHIVE_OLDER_THAN_HOURS,
        )
        self.cleanup_retention_days = (
            _coerce_positive_int(cleanup_retention_days, DEFAULT_CLEANUP_RETENTION_DAYS)
            if cleanup_retention_days not in (None, "", 0)
            else None
        )
        self.cleanup_batch_size = _coerce_positive_int(cleanup_batch_size, DEFAULT_CLEANUP_BATCH_SIZE)

    def finish(self, job: JobDetail) -> JobResult:
        """Archive dispatcher rows and optionally enforce archive retention."""
        worker = self.worker
        pool = getattr(worker, "pool", None)
        if pool is None:
            raise RuntimeError("DailyJobArchiveJobCap requires a bound worker with pool access.")

        payload = dict(job.payload or {}) if isinstance(job.payload, Mapping) else {}
        batch_size = _coerce_positive_int(payload.get("batch_size"), self.batch_size)
        cleanup_only = _coerce_bool(payload.get("cleanup_only"), False)
        archive_completed_jobs = _coerce_bool(payload.get("archive_completed_jobs"), not cleanup_only)
        archive_related_tables = _coerce_bool(payload.get("archive_related_tables"), self.archive_related_tables)
        related_table_batch_size = _coerce_positive_int(
            payload.get("related_table_batch_size"),
            self.related_table_batch_size,
        )
        archive_older_than_hours = _coerce_non_negative_float(
            payload.get("archive_older_than_hours"),
            self.archive_older_than_hours,
        )
        cleanup_retention_days_value = payload.get("cleanup_retention_days", payload.get("purge_retention_days"))
        cleanup_retention_days = (
            _coerce_positive_int(cleanup_retention_days_value, DEFAULT_CLEANUP_RETENTION_DAYS)
            if cleanup_retention_days_value not in (None, "", 0)
            else self.cleanup_retention_days
        )
        cleanup_batch_size = _coerce_positive_int(payload.get("cleanup_batch_size"), self.cleanup_batch_size)

        job_archive_summary = {
            "processed_job_ids": [],
            "completed_jobs_seen": 0,
            "processed_jobs": 0,
            "archived_jobs": 0,
            "already_archived_jobs": 0,
            "deleted_active_rows": 0,
            "remaining_completed_jobs": 0,
        }
        if archive_completed_jobs:
            job_archive_summary = _archive_completed_jobs(pool, batch_size=batch_size)

        related_archive_summaries: list[dict[str, Any]] = []
        archive_cutoff = ""
        if archive_related_tables:
            archive_cutoff = _utc_cutoff_iso(hours=archive_older_than_hours)
            for spec in RELATED_ARCHIVE_TABLES:
                related_archive_summaries.append(
                    _archive_related_table(
                        pool,
                        source_table=spec["source_table"],
                        archive_table=spec["archive_table"],
                        timestamp_column=spec["timestamp_column"],
                        cutoff=archive_cutoff,
                        batch_size=related_table_batch_size,
                    )
                )

        cleanup_summaries: list[dict[str, Any]] = []
        cleanup_cutoff = ""
        if cleanup_retention_days is not None:
            cleanup_cutoff = _utc_cutoff_iso(days=float(cleanup_retention_days))
            for spec in RETENTION_ARCHIVE_TABLES:
                cleanup_summaries.append(
                    _purge_archive_table(
                        pool,
                        archive_table=spec["archive_table"],
                        timestamp_column=spec["timestamp_column"],
                        cutoff=cleanup_cutoff,
                        batch_size=cleanup_batch_size,
                    )
                )

        return JobResult(
            job_id=job.id,
            status="completed",
            raw_payload={
                "provider": "dispatcher",
                "job_kind": "daily_job_archive",
                "processed_job_ids": job_archive_summary["processed_job_ids"],
            },
            result_summary={
                "provider": "dispatcher",
                "job_kind": "daily_job_archive",
                "batch_size": batch_size,
                "completed_jobs_seen": job_archive_summary["completed_jobs_seen"],
                "processed_jobs": job_archive_summary["processed_jobs"],
                "archived_jobs": job_archive_summary["archived_jobs"],
                "already_archived_jobs": job_archive_summary["already_archived_jobs"],
                "deleted_active_rows": job_archive_summary["deleted_active_rows"],
                "remaining_completed_jobs": job_archive_summary["remaining_completed_jobs"],
                "archive_related_tables": archive_related_tables,
                "related_table_batch_size": related_table_batch_size,
                "archive_older_than_hours": archive_older_than_hours,
                "archive_cutoff": archive_cutoff,
                "related_table_archives": related_archive_summaries,
                "cleanup_retention_days": cleanup_retention_days,
                "cleanup_batch_size": cleanup_batch_size,
                "cleanup_cutoff": cleanup_cutoff,
                "cleanup_archives": cleanup_summaries,
                "purged_rows": sum(int(summary.get("purged_rows") or 0) for summary in cleanup_summaries),
            },
            target_table=TABLE_JOB_ARCHIVE,
        )
