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
from typing import Any, Dict, Iterable, List, Mapping

from prompits.core.schema import DataType, TableSchema


TABLE_JOBS = "dispatcher_jobs"
TABLE_JOB_ARCHIVE = "dispatcher_jobs_archive"
TABLE_WORKERS = "dispatcher_worker_capabilities"
TABLE_WORKER_HISTORY = "dispatcher_worker_history"
TABLE_WORKER_HISTORY_ARCHIVE = "dispatcher_worker_history_archive"
TABLE_RESULT_ROWS = "dispatcher_job_results"
TABLE_RESULT_ROWS_ARCHIVE = "dispatcher_job_results_archive"
TABLE_RAW_PAYLOADS = "dispatcher_raw_payloads"
TABLE_RAW_PAYLOADS_ARCHIVE = "dispatcher_raw_payloads_archive"

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


def job_archive_schema_dict() -> Dict[str, object]:
    """Handle job archive schema dict."""
    schema = jobs_schema_dict()
    archive_row_schema = dict(schema["rowSchema"])
    archive_row_schema["archived_at"] = {"type": "datetime"}
    return {
        **schema,
        "name": TABLE_JOB_ARCHIVE,
        "description": "Archived completed dispatcher jobs kept out of the active queue hot path.",
        "rowSchema": archive_row_schema,
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


def worker_history_archive_schema_dict() -> Dict[str, object]:
    """Handle worker history archive schema dict."""
    schema = worker_history_schema_dict()
    archive_row_schema = dict(schema["rowSchema"])
    archive_row_schema["archived_at"] = {"type": "datetime"}
    return {
        **schema,
        "name": TABLE_WORKER_HISTORY_ARCHIVE,
        "description": "Archived worker heartbeat and session history kept out of the active hot path.",
        "rowSchema": archive_row_schema,
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


def job_results_archive_schema_dict() -> Dict[str, object]:
    """Handle job results archive schema dict."""
    schema = job_results_schema_dict()
    archive_row_schema = dict(schema["rowSchema"])
    archive_row_schema["archived_at"] = {"type": "datetime"}
    return {
        **schema,
        "name": TABLE_RESULT_ROWS_ARCHIVE,
        "description": "Archived generic job result rows kept out of the active hot path.",
        "rowSchema": archive_row_schema,
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


def raw_payloads_archive_schema_dict() -> Dict[str, object]:
    """Handle raw payload archive schema dict."""
    schema = raw_payloads_schema_dict()
    archive_row_schema = dict(schema["rowSchema"])
    archive_row_schema["archived_at"] = {"type": "datetime"}
    return {
        **schema,
        "name": TABLE_RAW_PAYLOADS_ARCHIVE,
        "description": "Archived raw dispatcher payloads kept out of the active hot path.",
        "rowSchema": archive_row_schema,
    }


def dispatcher_internal_schema_map() -> Dict[str, TableSchema]:
    """Return the dispatcher internal schema map."""
    return {
        TABLE_JOBS: TableSchema(jobs_schema_dict()),
        TABLE_JOB_ARCHIVE: TableSchema(job_archive_schema_dict()),
        TABLE_WORKERS: TableSchema(worker_capabilities_schema_dict()),
        TABLE_WORKER_HISTORY: TableSchema(worker_history_schema_dict()),
        TABLE_WORKER_HISTORY_ARCHIVE: TableSchema(worker_history_archive_schema_dict()),
        TABLE_RESULT_ROWS: TableSchema(job_results_schema_dict()),
        TABLE_RESULT_ROWS_ARCHIVE: TableSchema(job_results_archive_schema_dict()),
        TABLE_RAW_PAYLOADS: TableSchema(raw_payloads_schema_dict()),
        TABLE_RAW_PAYLOADS_ARCHIVE: TableSchema(raw_payloads_archive_schema_dict()),
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
    if TABLE_JOBS in table_names and TABLE_JOB_ARCHIVE not in table_names:
        table_names.append(TABLE_JOB_ARCHIVE)
    archive_table_pairs = {
        TABLE_WORKER_HISTORY: TABLE_WORKER_HISTORY_ARCHIVE,
        TABLE_RESULT_ROWS: TABLE_RESULT_ROWS_ARCHIVE,
        TABLE_RAW_PAYLOADS: TABLE_RAW_PAYLOADS_ARCHIVE,
    }
    for source_table, archive_table in archive_table_pairs.items():
        if source_table in table_names and archive_table not in table_names:
            table_names.append(archive_table)
    for table_name in table_names:
        schema = schema_map.get(table_name)
        if schema is None:
            continue
        if not pool._TableExists(table_name):
            pool._CreateTable(table_name, schema)
        _ensure_table_columns(pool, table_name, schema)
    if TABLE_JOBS in table_names:
        _ensure_dispatcher_jobs_table_integrity(pool)
        _ensure_dispatcher_jobs_indexes(pool)
    if TABLE_JOB_ARCHIVE in table_names:
        _ensure_dispatcher_job_archive_indexes(pool)
    if TABLE_WORKER_HISTORY in table_names:
        _ensure_dispatcher_worker_history_indexes(pool)
    if TABLE_WORKER_HISTORY_ARCHIVE in table_names:
        _ensure_dispatcher_worker_history_archive_indexes(pool)
    if TABLE_RESULT_ROWS in table_names:
        _ensure_dispatcher_job_results_indexes(pool)
    if TABLE_RESULT_ROWS_ARCHIVE in table_names:
        _ensure_dispatcher_job_results_archive_indexes(pool)
    if TABLE_RAW_PAYLOADS in table_names:
        _ensure_dispatcher_raw_payloads_indexes(pool)
    if TABLE_RAW_PAYLOADS_ARCHIVE in table_names:
        _ensure_dispatcher_raw_payloads_archive_indexes(pool)


def _column_sql_type_for_pool(pool, column_spec: Mapping[str, Any]) -> str:
    """Return the SQL type for one column on the active pool dialect."""
    explicit_sql_type = str(column_spec.get("sql_type") or "").strip()
    if explicit_sql_type:
        return explicit_sql_type
    column_type = DataType.from_string(str(column_spec.get("type") or "string"))
    if _pool_dialect(pool) == "postgres":
        return pool._get_postgres_type(column_type)
    return pool._get_sqlite_type(column_type)


def _existing_table_columns(pool, table_name: str) -> set[str]:
    """Return the currently materialized columns for one table."""
    dialect = _pool_dialect(pool)
    if dialect == "postgres":
        split_table_name = getattr(pool, "_split_table_name", None)
        if not callable(split_table_name):
            return set()
        schema_name, relation_name = split_table_name(table_name)
        rows = pool._Query(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
            """,
            [schema_name, relation_name],
        )
        return {str(row[0] or "").strip() for row in rows if row and str(row[0] or "").strip()}
    if dialect == "sqlite":
        rows = pool._Query(f"PRAGMA table_info('{table_name}')")
        return {str(row[1] or "").strip() for row in rows if len(row) > 1 and str(row[1] or "").strip()}
    return set()


def _ensure_table_columns(pool, table_name: str, schema: TableSchema) -> None:
    """Add missing nullable columns for existing tables when schemas evolve."""
    if pool is None or schema is None or not pool._TableExists(table_name):
        return
    dialect = _pool_dialect(pool)
    if dialect not in {"postgres", "sqlite"}:
        return

    existing_columns = _existing_table_columns(pool, table_name)
    if not existing_columns:
        return

    missing_columns = [
        column_name
        for column_name in schema.rowSchema.columns.keys()
        if column_name not in existing_columns
    ]
    if not missing_columns:
        return

    if dialect == "postgres":
        quoted_table_name = pool._quoted_table_name(table_name)
        for column_name in missing_columns:
            column_spec = schema.rowSchema.columns[column_name]
            sql_type = _column_sql_type_for_pool(pool, column_spec)
            pool._Query(
                f"ALTER TABLE {quoted_table_name} "
                f"ADD COLUMN IF NOT EXISTS {pool._quote_identifier(column_name)} {sql_type}"
            )
        return

    for column_name in missing_columns:
        column_spec = schema.rowSchema.columns[column_name]
        sql_type = _column_sql_type_for_pool(pool, column_spec)
        pool._Query(f'ALTER TABLE "{table_name}" ADD COLUMN "{column_name}" {sql_type}')


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


def _ensure_dispatcher_jobs_indexes(pool) -> None:
    """Create secondary indexes that keep dispatcher-job lookups fast."""
    dialect = _pool_dialect(pool)
    if not pool or not pool._TableExists(TABLE_JOBS):
        return
    if dialect == "postgres":
        if not all(hasattr(pool, attribute) for attribute in ("_quoted_table_name", "_quote_identifier", "_Query")):
            return
        quoted_table_name = pool._quoted_table_name(TABLE_JOBS)
        status_expr = f"lower(coalesce({pool._quote_identifier('status')}, ''))"
        capability_expr = f"lower(coalesce({pool._quote_identifier('required_capability')}, ''))"
        priority_column = pool._quote_identifier("priority")
        scheduled_for_column = pool._quote_identifier("scheduled_for")
        created_at_column = pool._quote_identifier("created_at")
        id_column = pool._quote_identifier("id")
        claimed_by_column = pool._quote_identifier("claimed_by")
        logical_key_expr = (
            "coalesce("
            "(metadata -> 'stamp_auction_network' ->> 'logical_job_key'), "
            "(metadata -> 'ebay_active_stamp' ->> 'logical_job_key'), "
            "(metadata ->> 'logical_job_key'), "
            "''"
            ")"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_status_idx "
            f"ON {quoted_table_name} (({status_expr}))"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_ready_order_idx "
            f"ON {quoted_table_name} ({priority_column}, {created_at_column}, {id_column}) "
            f"WHERE {status_expr} IN ('queued', 'retry', 'unfinished')"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_ready_schedule_idx "
            f"ON {quoted_table_name} ({scheduled_for_column}, {priority_column}, {created_at_column}, {id_column}) "
            f"WHERE {status_expr} IN ('queued', 'retry', 'unfinished')"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_ready_capability_idx "
            f"ON {quoted_table_name} (({capability_expr}), {priority_column}, {created_at_column}, {id_column}) "
            f"WHERE {status_expr} IN ('queued', 'retry', 'unfinished')"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_claimed_worker_idx "
            f"ON {quoted_table_name} ({claimed_by_column}, ({status_expr})) "
            f"WHERE coalesce({claimed_by_column}, '') <> ''"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_status_pipeline_logical_key_idx "
            f"ON {quoted_table_name} ("
            f"({status_expr}), "
            f"({logical_key_expr})"
            ")"
        )
        return
    if dialect == "sqlite":
        status_expr = "lower(coalesce(status, ''))"
        capability_expr = "lower(coalesce(required_capability, ''))"
        logical_key_expr = (
            "coalesce("
            "json_extract(metadata, '$.stamp_auction_network.logical_job_key'), "
            "json_extract(metadata, '$.ebay_active_stamp.logical_job_key'), "
            "json_extract(metadata, '$.logical_job_key'), "
            "''"
            ")"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_status_idx "
            f"ON {TABLE_JOBS} ({status_expr})"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_ready_order_idx "
            f"ON {TABLE_JOBS} (priority, created_at, id) "
            f"WHERE {status_expr} IN ('queued', 'retry', 'unfinished')"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_ready_schedule_idx "
            f"ON {TABLE_JOBS} (scheduled_for, priority, created_at, id) "
            f"WHERE {status_expr} IN ('queued', 'retry', 'unfinished')"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_ready_capability_idx "
            f"ON {TABLE_JOBS} ({capability_expr}, priority, created_at, id) "
            f"WHERE {status_expr} IN ('queued', 'retry', 'unfinished')"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_claimed_worker_idx "
            f"ON {TABLE_JOBS} (claimed_by, {status_expr}) "
            "WHERE coalesce(claimed_by, '') <> ''"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_status_pipeline_logical_key_idx "
            f"ON {TABLE_JOBS} ("
            f"{status_expr}, "
            f"{logical_key_expr}"
            ")"
        )
        return


def _ensure_dispatcher_job_archive_indexes(pool) -> None:
    """Create secondary indexes that keep completed-job archive reads bounded."""
    dialect = _pool_dialect(pool)
    if not pool or not pool._TableExists(TABLE_JOB_ARCHIVE):
        return
    if dialect == "postgres":
        if not all(hasattr(pool, attribute) for attribute in ("_quoted_table_name", "_quote_identifier", "_Query")):
            return
        quoted_table_name = pool._quoted_table_name(TABLE_JOB_ARCHIVE)
        completed_at_column = pool._quote_identifier("completed_at")
        archived_at_column = pool._quote_identifier("archived_at")
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_archive_completed_idx "
            f"ON {quoted_table_name} ({completed_at_column} DESC, {archived_at_column} DESC)"
        )
        return
    if dialect == "sqlite":
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_jobs_archive_completed_idx "
            f"ON {TABLE_JOB_ARCHIVE} (completed_at DESC, archived_at DESC)"
        )
        return


def _ensure_dispatcher_worker_history_indexes(pool) -> None:
    """Create secondary indexes that keep worker-history reads bounded."""
    dialect = _pool_dialect(pool)
    if not pool or not pool._TableExists(TABLE_WORKER_HISTORY):
        return
    if dialect == "postgres":
        quoted_table_name = pool._quoted_table_name(TABLE_WORKER_HISTORY)
        worker_id_column = pool._quote_identifier("worker_id")
        captured_at_column = pool._quote_identifier("captured_at")
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_worker_history_worker_captured_idx "
            f"ON {quoted_table_name} ({worker_id_column}, {captured_at_column} DESC)"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_worker_history_captured_idx "
            f"ON {quoted_table_name} ({captured_at_column} DESC)"
        )
        return
    if dialect == "sqlite":
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_worker_history_worker_captured_idx "
            f"ON {TABLE_WORKER_HISTORY} (worker_id, captured_at DESC)"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS dispatcher_worker_history_captured_idx "
            f"ON {TABLE_WORKER_HISTORY} (captured_at DESC)"
        )
        return


def _ensure_timestamp_index(
    pool,
    *,
    table_name: str,
    index_name: str,
    timestamp_column: str,
    secondary_column: str = "",
) -> None:
    """Create one timestamp-based index for archive movement and pruning."""
    dialect = _pool_dialect(pool)
    if not pool or not pool._TableExists(table_name):
        return
    if dialect == "postgres":
        quoted_table_name = pool._quoted_table_name(table_name)
        timestamp_sql = pool._quote_identifier(timestamp_column)
        if secondary_column:
            secondary_sql = pool._quote_identifier(secondary_column)
            columns = f"{timestamp_sql} DESC, {secondary_sql}"
        else:
            columns = f"{timestamp_sql} DESC"
        pool._Query(f"CREATE INDEX IF NOT EXISTS {index_name} ON {quoted_table_name} ({columns})")
        return
    if dialect == "sqlite":
        if secondary_column:
            columns = f"{timestamp_column} DESC, {secondary_column}"
        else:
            columns = f"{timestamp_column} DESC"
        pool._Query(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})")
        return


def _ensure_dispatcher_worker_history_archive_indexes(pool) -> None:
    """Create indexes for archived worker-history pruning and lookups."""
    _ensure_timestamp_index(
        pool,
        table_name=TABLE_WORKER_HISTORY_ARCHIVE,
        index_name="dispatcher_worker_history_archive_captured_idx",
        timestamp_column="captured_at",
        secondary_column="worker_id",
    )


def _ensure_dispatcher_job_results_indexes(pool) -> None:
    """Create indexes for job-result archive movement."""
    _ensure_timestamp_index(
        pool,
        table_name=TABLE_RESULT_ROWS,
        index_name="dispatcher_job_results_recorded_idx",
        timestamp_column="recorded_at",
        secondary_column="job_id",
    )


def _ensure_dispatcher_job_results_archive_indexes(pool) -> None:
    """Create indexes for archived job-result pruning."""
    _ensure_timestamp_index(
        pool,
        table_name=TABLE_RESULT_ROWS_ARCHIVE,
        index_name="dispatcher_job_results_archive_recorded_idx",
        timestamp_column="recorded_at",
        secondary_column="job_id",
    )


def _ensure_dispatcher_raw_payloads_indexes(pool) -> None:
    """Create indexes for raw-payload archive movement."""
    _ensure_timestamp_index(
        pool,
        table_name=TABLE_RAW_PAYLOADS,
        index_name="dispatcher_raw_payloads_collected_idx",
        timestamp_column="collected_at",
        secondary_column="job_id",
    )


def _ensure_dispatcher_raw_payloads_archive_indexes(pool) -> None:
    """Create indexes for archived raw-payload pruning."""
    _ensure_timestamp_index(
        pool,
        table_name=TABLE_RAW_PAYLOADS_ARCHIVE,
        index_name="dispatcher_raw_payloads_archive_collected_idx",
        timestamp_column="collected_at",
        secondary_column="job_id",
    )
