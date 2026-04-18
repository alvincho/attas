"""
Maintenance job caps for `ads.archive_jobs`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace.
"""

from __future__ import annotations

from contextlib import nullcontext
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from ads.jobcap import JobCap
from ads.models import JobDetail, JobResult
from ads.runtime import parse_datetime_value, utcnow_iso
from ads.schema import TABLE_JOB_ARCHIVE, TABLE_JOBS, ensure_ads_tables


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
        raise RuntimeError("ADS Daily Job Archive requires a connected pool.")
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


class DailyJobArchiveJobCap(JobCap):
    """Sweep completed ADS jobs from the active queue into the archive table."""

    DEFAULT_NAME = "daily job archive"

    def __init__(self, name: str = "", *, batch_size: int = 500, **kwargs: Any):
        """Initialize the archive-sweep job cap."""
        super().__init__(name=name or self.DEFAULT_NAME, **kwargs)
        self.batch_size = _coerce_positive_int(batch_size, 500)

    def finish(self, job: JobDetail) -> JobResult:
        """Archive completed ADS jobs that still remain in the active queue."""
        worker = self.worker
        pool = getattr(worker, "pool", None)
        if pool is None:
            raise RuntimeError("DailyJobArchiveJobCap requires a bound worker with pool access.")

        ensure_ads_tables(pool, [TABLE_JOB_ARCHIVE])

        payload = dict(job.payload or {}) if isinstance(job.payload, Mapping) else {}
        batch_size = _coerce_positive_int(payload.get("batch_size"), self.batch_size)
        active_rows = _latest_job_rows(pool._GetTableData(TABLE_JOBS) or [])
        completed_rows = [
            dict(row)
            for row in active_rows
            if str(row.get("status") or "").strip().lower() == "completed"
        ]
        completed_rows.sort(
            key=lambda row: (
                parse_datetime_value(row.get("completed_at") or row.get("updated_at") or row.get("created_at")),
                parse_datetime_value(row.get("updated_at") or row.get("created_at")),
                str(row.get("id") or ""),
            )
        )
        candidates = completed_rows[:batch_size]

        archived_jobs = 0
        already_archived_jobs = 0
        deleted_active_rows = 0

        for row in candidates:
            job_id = str(row.get("id") or "").strip()
            if not job_id:
                continue
            archived_rows = _latest_job_rows(pool._GetTableData(TABLE_JOB_ARCHIVE, job_id) or [])
            archived_row = archived_rows[0] if archived_rows else None
            if _archive_covers_active_row(row, archived_row):
                already_archived_jobs += 1
                _delete_job_row(pool, TABLE_JOBS, job_id)
                deleted_active_rows += 1
                continue

            archived_at = utcnow_iso()
            archive_storage = dict(row)
            archive_storage["archived_at"] = archived_at
            if not pool._Insert(TABLE_JOB_ARCHIVE, archive_storage):
                raise RuntimeError(f"Failed to archive ADS job '{job_id}'.")
            archived_jobs += 1
            _delete_job_row(pool, TABLE_JOBS, job_id)
            deleted_active_rows += 1

        return JobResult(
            job_id=job.id,
            status="completed",
            raw_payload={
                "provider": "ads",
                "job_kind": "daily_job_archive",
                "processed_job_ids": [str(row.get("id") or "") for row in candidates],
            },
            result_summary={
                "provider": "ads",
                "job_kind": "daily_job_archive",
                "batch_size": batch_size,
                "completed_jobs_seen": len(completed_rows),
                "processed_jobs": len(candidates),
                "archived_jobs": archived_jobs,
                "already_archived_jobs": already_archived_jobs,
                "deleted_active_rows": deleted_active_rows,
                "remaining_completed_jobs": max(len(completed_rows) - len(candidates), 0),
            },
            target_table=TABLE_JOB_ARCHIVE,
        )
