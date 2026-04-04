"""
Schema definitions for `prompits.dispatcher.schema`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the dispatcher package
coordinates job routing, worker selection, and queue management.

Important callables in this file include `raw_payloads_schema_dict`,
`dispatcher_internal_schema_map`, `dispatcher_table_schema_map`,
`dispatcher_table_schemas`, and `ensure_dispatcher_tables`, which capture the primary
workflow implemented by the module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, List, Mapping

from prompits.core.schema import TableSchema


TABLE_JOBS = "dispatcher_jobs"
TABLE_WORKERS = "dispatcher_worker_capabilities"
TABLE_WORKER_HISTORY = "dispatcher_worker_history"
TABLE_RESULT_ROWS = "dispatcher_job_results"
TABLE_RAW_PAYLOADS = "dispatcher_raw_payloads"

CAPABILITY_TO_TABLE: dict[str, str] = {}


def jobs_schema_dict() -> Dict[str, object]:
    """Handle jobs schema dict."""
    return {
        "name": TABLE_JOBS,
        "description": "Queue-backed jobs for generic dispatcher workers.",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "job_type": {"type": "string"},
            "status": {"type": "string"},
            "required_capability": {"type": "string"},
            "capability_tags": {"type": "json"},
            "targets": {"type": "json"},
            "payload": {"type": "json"},
            "target_table": {"type": "string"},
            "source_url": {"type": "string"},
            "parse_rules": {"type": "json"},
            "priority": {"type": "integer"},
            "premium": {"type": "boolean"},
            "metadata": {"type": "json"},
            "scheduled_for": {"type": "datetime"},
            "claimed_by": {"type": "string"},
            "claimed_at": {"type": "datetime"},
            "completed_at": {"type": "datetime"},
            "result_summary": {"type": "json"},
            "error": {"type": "string"},
            "attempts": {"type": "integer"},
            "max_attempts": {"type": "integer"},
            "created_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
        },
    }


def worker_capabilities_schema_dict() -> Dict[str, object]:
    """Handle worker capabilities schema dict."""
    return {
        "name": TABLE_WORKERS,
        "description": "Latest advertised worker capabilities and heartbeat metadata.",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "worker_id": {"type": "string"},
            "name": {"type": "string"},
            "address": {"type": "string"},
            "capabilities": {"type": "json"},
            "metadata": {"type": "json"},
            "plaza_url": {"type": "string"},
            "status": {"type": "string"},
            "last_seen_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
        },
    }


def worker_history_schema_dict() -> Dict[str, object]:
    """Handle worker history schema dict."""
    return {
        "name": TABLE_WORKER_HISTORY,
        "description": "Append-only worker heartbeat and session history.",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "worker_id": {"type": "string"},
            "name": {"type": "string"},
            "address": {"type": "string"},
            "capabilities": {"type": "json"},
            "plaza_url": {"type": "string"},
            "status": {"type": "string"},
            "event_type": {"type": "string"},
            "session_started_at": {"type": "datetime"},
            "active_job_id": {"type": "string"},
            "active_job_status": {"type": "string"},
            "progress": {"type": "json"},
            "environment": {"type": "json"},
            "metadata": {"type": "json"},
            "captured_at": {"type": "datetime"},
        },
    }


def job_results_schema_dict() -> Dict[str, object]:
    """Handle job results schema dict."""
    return {
        "name": TABLE_RESULT_ROWS,
        "description": "Generic stored job rows when no concrete table schema is supplied.",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "job_id": {"type": "string"},
            "worker_id": {"type": "string"},
            "table_name": {"type": "string"},
            "source_url": {"type": "string"},
            "payload": {"type": "json"},
            "metadata": {"type": "json"},
            "recorded_at": {"type": "datetime"},
        },
    }


def raw_payloads_schema_dict() -> Dict[str, object]:
    """Handle raw payloads schema dict."""
    return {
        "name": TABLE_RAW_PAYLOADS,
        "description": "Raw payloads associated with completed dispatcher jobs.",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "job_id": {"type": "string"},
            "worker_id": {"type": "string"},
            "target_table": {"type": "string"},
            "source_url": {"type": "string"},
            "payload": {"type": "json"},
            "metadata": {"type": "json"},
            "collected_at": {"type": "datetime"},
        },
    }


def dispatcher_internal_schema_map() -> Dict[str, TableSchema]:
    """Return the dispatcher internal schema map."""
    return {
        TABLE_JOBS: TableSchema(jobs_schema_dict()),
        TABLE_WORKERS: TableSchema(worker_capabilities_schema_dict()),
        TABLE_WORKER_HISTORY: TableSchema(worker_history_schema_dict()),
        TABLE_RESULT_ROWS: TableSchema(job_results_schema_dict()),
        TABLE_RAW_PAYLOADS: TableSchema(raw_payloads_schema_dict()),
    }


def dispatcher_table_schema_map(
    extra_schemas: Mapping[str, TableSchema | Mapping[str, object]] | None = None,
) -> Dict[str, TableSchema]:
    """Return the dispatcher table schema map."""
    schema_map = dict(dispatcher_internal_schema_map())
    for table_name, schema in (extra_schemas or {}).items():
        if isinstance(schema, TableSchema):
            schema_map[str(table_name)] = schema
        elif isinstance(schema, Mapping):
            schema_map[str(table_name)] = TableSchema(dict(schema))
    return schema_map


def dispatcher_table_schemas() -> List[TableSchema]:
    """Handle dispatcher table schemas."""
    return list(dispatcher_internal_schema_map().values())


def _pool_dialect(pool) -> str:
    """Internal helper to return the pool dialect."""
    normalized = pool.__class__.__name__.strip().lower() if pool is not None else ""
    if normalized == "postgrespool":
        return "postgres"
    if normalized == "sqlitepool":
        return "sqlite"
    return "unknown"


def ensure_dispatcher_tables(
    pool,
    tables: Iterable[str] | None = None,
    *,
    extra_schemas: Mapping[str, TableSchema | Mapping[str, object]] | None = None,
) -> None:
    """Ensure the dispatcher tables exists."""
    if pool is None:
        return
    schema_map = dispatcher_table_schema_map(extra_schemas=extra_schemas)
    table_names = list(tables or schema_map.keys())
    for table_name in table_names:
        schema = schema_map.get(table_name)
        if schema is None:
            continue
        if not pool._TableExists(table_name):
            pool._CreateTable(table_name, schema)
    if TABLE_JOBS in table_names:
        _ensure_dispatcher_jobs_table_integrity(pool)


def _parse_schema_datetime(value) -> datetime:
    """Internal helper to parse the schema datetime."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or "").strip()
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def _job_row_sort_key(row: Dict[str, object], order_index: int) -> tuple[datetime, datetime, int]:
    """Internal helper to return the job row sort key."""
    return (
        _parse_schema_datetime(row.get("updated_at") or row.get("created_at")),
        _parse_schema_datetime(row.get("created_at")),
        order_index,
    )


def _ensure_dispatcher_jobs_table_integrity(pool) -> None:
    """Internal helper to ensure the dispatcher jobs table integrity exists."""
    if _pool_dialect(pool) != "sqlite":
        return
    conn = getattr(pool, "conn", None)
    if conn is None or not pool._TableExists(TABLE_JOBS):
        return
    ensure_connection = getattr(pool, "_ensure_connection", None)
    if callable(ensure_connection):
        ensure_connection()

    with pool.lock:
        cursor = pool.conn.cursor()
        cursor.execute(f"PRAGMA table_info('{TABLE_JOBS}')")
        columns = cursor.fetchall()
    has_primary_key = any(len(column) > 5 and column[1] == "id" and int(column[5] or 0) > 0 for column in columns)

    schema = dispatcher_internal_schema_map()[TABLE_JOBS]
    rows = pool._GetTableData(TABLE_JOBS, table_schema=schema) or []
    normalized_rows = [dict(row) for row in rows if isinstance(row, dict)]
    duplicate_ids = [str(row.get("id") or "").strip() for row in normalized_rows if str(row.get("id") or "").strip()]
    has_duplicates = len(duplicate_ids) != len(set(duplicate_ids))

    if has_primary_key and not has_duplicates:
        return

    latest_rows_by_id: Dict[str, Dict[str, object]] = {}
    latest_order_by_id: Dict[str, int] = {}
    for index, row in enumerate(normalized_rows):
        row_id = str(row.get("id") or "").strip()
        if not row_id:
            continue
        current = latest_rows_by_id.get(row_id)
        current_index = latest_order_by_id.get(row_id, -1)
        if current is None or _job_row_sort_key(row, index) > _job_row_sort_key(current, current_index):
            latest_rows_by_id[row_id] = row
            latest_order_by_id[row_id] = index
    compacted_rows = list(latest_rows_by_id.values())

    backup_table = f"{TABLE_JOBS}__legacy_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    with pool.lock:
        cursor = pool.conn.cursor()
        cursor.execute(f"ALTER TABLE {TABLE_JOBS} RENAME TO {backup_table}")
        pool.conn.commit()
    pool._CreateTable(TABLE_JOBS, schema)
    if compacted_rows:
        pool._InsertMany(TABLE_JOBS, compacted_rows)
    with pool.lock:
        cursor = pool.conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {backup_table}")
        pool.conn.commit()
