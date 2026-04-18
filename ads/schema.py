"""
Schema definitions for `ads.schema`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace.

Important callables in this file include `ads_table_schema_map`, `ads_table_schemas`,
`daily_price_schema_dict`, `ensure_ads_tables`, and `financial_statements_schema_dict`,
which capture the primary workflow implemented by the module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, List

from prompits.core.schema import TableSchema


TABLE_JOBS = "ads_jobs"
TABLE_JOB_ARCHIVE = "ads_jobs_archive"
TABLE_WORKERS = "ads_worker_capabilities"
TABLE_WORKER_HISTORY = "ads_worker_history"
TABLE_SECURITY_MASTER = "ads_security_master"
TABLE_DAILY_PRICE = "ads_daily_price"
TABLE_FUNDAMENTALS = "ads_fundamentals"
TABLE_FINANCIAL_STATEMENTS = "ads_financial_statements"
TABLE_NEWS = "ads_news"
TABLE_SEC_COMPANYFACTS = "ads_sec_companyfacts"
TABLE_SEC_SUBMISSIONS = "ads_sec_submissions"
TABLE_RAW_DATA = "ads_raw_data_collected"

SYMBOL_CHILD_TABLES = (
    TABLE_DAILY_PRICE,
    TABLE_FUNDAMENTALS,
    TABLE_FINANCIAL_STATEMENTS,
    TABLE_NEWS,
)


CAPABILITY_TO_TABLE = {
    "security_master": TABLE_SECURITY_MASTER,
    "daily_price": TABLE_DAILY_PRICE,
    "fundamentals": TABLE_FUNDAMENTALS,
    "financial_statements": TABLE_FINANCIAL_STATEMENTS,
    "news": TABLE_NEWS,
}


def jobs_schema_dict() -> Dict[str, object]:
    """Handle jobs schema dict."""
    return {
        "name": TABLE_JOBS,
        "description": "Queue-backed collection jobs for Attas Data Services workers.",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "job_type": {"type": "string"},
            "status": {"type": "string"},
            "required_capability": {"type": "string"},
            "capability_tags": {"type": "json"},
            "symbols": {"type": "json"},
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
        "description": "Archived completed ADS jobs kept out of the active queue hot path.",
        "rowSchema": archive_row_schema,
    }


def worker_capabilities_schema_dict() -> Dict[str, object]:
    """Handle worker capabilities schema dict."""
    return {
        "name": TABLE_WORKERS,
        "description": "Latest advertised ADS worker capabilities and heartbeat metadata.",
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
        "description": "Append-only ADS worker heartbeat and session history for analysis and recovery.",
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


def security_master_schema_dict() -> Dict[str, object]:
    """Handle security master schema dict."""
    return {
        "name": TABLE_SECURITY_MASTER,
        "description": "Normalized security master rows collected by ADS workers.",
        "primary_key": ["symbol"],
        "rowSchema": {
            "id": {"type": "string"},
            "symbol": {"type": "string", "sql_type": "VARCHAR(20)"},
            "name": {"type": "string"},
            "instrument_type": {"type": "string"},
            "exchange": {"type": "string"},
            "currency": {"type": "string"},
            "is_active": {"type": "boolean"},
            "provider": {"type": "string"},
            "metadata": {"type": "json"},
            "created_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
        },
    }


def daily_price_schema_dict() -> Dict[str, object]:
    """Handle daily price schema dict."""
    return {
        "name": TABLE_DAILY_PRICE,
        "description": "Normalized OHLCV bars at daily cadence.",
        "primary_key": ["id"],
        "unique_constraints": [["symbol", "trade_date", "provider"]],
        "foreign_keys": [
            {
                "columns": ["symbol"],
                "references": {"table": TABLE_SECURITY_MASTER, "columns": ["symbol"]},
                "on_delete": "RESTRICT",
                "on_update": "CASCADE",
            }
        ],
        "rowSchema": {
            "id": {"type": "string"},
            "symbol": {"type": "string", "sql_type": "VARCHAR(20)"},
            "trade_date": {"type": "string"},
            "open": {"type": "number"},
            "high": {"type": "number"},
            "low": {"type": "number"},
            "close": {"type": "number"},
            "adj_close": {"type": "number"},
            "volume": {"type": "number"},
            "provider": {"type": "string"},
            "source_url": {"type": "string"},
            "metadata": {"type": "json"},
            "created_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
        },
    }


def fundamentals_schema_dict() -> Dict[str, object]:
    """Handle fundamentals schema dict."""
    return {
        "name": TABLE_FUNDAMENTALS,
        "description": "Latest normalized company fundamentals.",
        "primary_key": ["id"],
        "foreign_keys": [
            {
                "columns": ["symbol"],
                "references": {"table": TABLE_SECURITY_MASTER, "columns": ["symbol"]},
                "on_delete": "RESTRICT",
                "on_update": "CASCADE",
            }
        ],
        "rowSchema": {
            "id": {"type": "string"},
            "symbol": {"type": "string", "sql_type": "VARCHAR(20)"},
            "as_of_date": {"type": "string"},
            "market_cap": {"type": "number"},
            "pe_ratio": {"type": "number"},
            "dividend_yield": {"type": "number"},
            "sector": {"type": "string"},
            "industry": {"type": "string"},
            "provider": {"type": "string"},
            "data": {"type": "json"},
            "created_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
        },
    }


def financial_statements_schema_dict() -> Dict[str, object]:
    """Handle financial statements schema dict."""
    return {
        "name": TABLE_FINANCIAL_STATEMENTS,
        "description": "Normalized financial statement payloads keyed by company and period.",
        "primary_key": ["id"],
        "foreign_keys": [
            {
                "columns": ["symbol"],
                "references": {"table": TABLE_SECURITY_MASTER, "columns": ["symbol"]},
                "on_delete": "RESTRICT",
                "on_update": "CASCADE",
            }
        ],
        "rowSchema": {
            "id": {"type": "string"},
            "symbol": {"type": "string", "sql_type": "VARCHAR(20)"},
            "statement_type": {"type": "string"},
            "period_end": {"type": "string"},
            "fiscal_period": {"type": "string"},
            "currency": {"type": "string"},
            "provider": {"type": "string"},
            "data": {"type": "json"},
            "created_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
        },
    }


def news_schema_dict() -> Dict[str, object]:
    """Handle news schema dict."""
    return {
        "name": TABLE_NEWS,
        "description": "Normalized company news, press releases, and filings metadata.",
        "primary_key": ["id"],
        "foreign_keys": [
            {
                "columns": ["symbol"],
                "references": {"table": TABLE_SECURITY_MASTER, "columns": ["symbol"]},
                "on_delete": "RESTRICT",
                "on_update": "CASCADE",
            }
        ],
        "rowSchema": {
            "id": {"type": "string"},
            "symbol": {"type": "string", "sql_type": "VARCHAR(20)"},
            "headline": {"type": "string"},
            "summary": {"type": "string"},
            "url": {"type": "string"},
            "source": {"type": "string"},
            "source_url": {"type": "string"},
            "published_at": {"type": "datetime"},
            "sentiment": {"type": "number"},
            "data": {"type": "json"},
            "created_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
        },
    }


def sec_companyfacts_schema_dict() -> Dict[str, object]:
    """Handle SEC companyfacts schema dict."""
    return {
        "name": TABLE_SEC_COMPANYFACTS,
        "description": "Raw SEC EDGAR companyfacts JSON payloads extracted from companyfacts.zip.",
        "primary_key": ["cik"],
        "rowSchema": {
            "id": {"type": "string"},
            "cik": {"type": "string", "sql_type": "VARCHAR(10)"},
            "entity_name": {"type": "string"},
            "file_name": {"type": "string"},
            "fact_count": {"type": "integer"},
            "source_url": {"type": "string"},
            "provider": {"type": "string"},
            "payload": {"type": "json"},
            "created_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
        },
    }


def sec_submissions_schema_dict() -> Dict[str, object]:
    """Handle SEC submissions schema dict."""
    return {
        "name": TABLE_SEC_SUBMISSIONS,
        "description": "Raw SEC EDGAR submissions JSON payloads extracted from submissions.zip.",
        "primary_key": ["cik", "file_name"],
        "rowSchema": {
            "id": {"type": "string"},
            "cik": {"type": "string", "sql_type": "VARCHAR(10)"},
            "entity_name": {"type": "string"},
            "symbol": {"type": "string"},
            "symbols": {"type": "json"},
            "exchanges": {"type": "json"},
            "file_name": {"type": "string"},
            "is_primary": {"type": "boolean"},
            "filing_count": {"type": "integer"},
            "source_url": {"type": "string"},
            "provider": {"type": "string"},
            "payload": {"type": "json"},
            "created_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
        },
    }


def raw_data_schema_dict() -> Dict[str, object]:
    """Handle raw data schema dict."""
    return {
        "name": TABLE_RAW_DATA,
        "description": "Raw upstream payloads associated with ADS collection jobs.",
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


def ads_table_schema_map() -> Dict[str, TableSchema]:
    """Return the ADS table schema map."""
    return {
        TABLE_JOBS: TableSchema(jobs_schema_dict()),
        TABLE_JOB_ARCHIVE: TableSchema(job_archive_schema_dict()),
        TABLE_WORKERS: TableSchema(worker_capabilities_schema_dict()),
        TABLE_WORKER_HISTORY: TableSchema(worker_history_schema_dict()),
        TABLE_SECURITY_MASTER: TableSchema(security_master_schema_dict()),
        TABLE_DAILY_PRICE: TableSchema(daily_price_schema_dict()),
        TABLE_FUNDAMENTALS: TableSchema(fundamentals_schema_dict()),
        TABLE_FINANCIAL_STATEMENTS: TableSchema(financial_statements_schema_dict()),
        TABLE_NEWS: TableSchema(news_schema_dict()),
        TABLE_SEC_COMPANYFACTS: TableSchema(sec_companyfacts_schema_dict()),
        TABLE_SEC_SUBMISSIONS: TableSchema(sec_submissions_schema_dict()),
        TABLE_RAW_DATA: TableSchema(raw_data_schema_dict()),
    }


def ads_table_schemas() -> List[TableSchema]:
    """Handle ADS table schemas."""
    return list(ads_table_schema_map().values())


def _pool_dialect(pool) -> str:
    """Internal helper to return the pool dialect."""
    normalized = pool.__class__.__name__.strip().lower() if pool is not None else ""
    if normalized == "postgrespool":
        return "postgres"
    if normalized == "sqlitepool":
        return "sqlite"
    return "unknown"


def ensure_ads_tables(pool, tables: Iterable[str] | None = None) -> None:
    """Ensure the ADS tables exists."""
    if pool is None:
        return
    schema_map = ads_table_schema_map()
    table_names = list(tables or schema_map.keys())
    if TABLE_JOBS in table_names and TABLE_JOB_ARCHIVE not in table_names:
        table_names.append(TABLE_JOB_ARCHIVE)
    if any(table_name in SYMBOL_CHILD_TABLES for table_name in table_names) and TABLE_SECURITY_MASTER not in table_names:
        table_names = [TABLE_SECURITY_MASTER, *table_names]
    for table_name in table_names:
        schema = schema_map.get(table_name)
        if schema is None:
            continue
        if not pool._TableExists(table_name):
            pool._CreateTable(table_name, schema)
    if TABLE_JOBS in table_names:
        _ensure_ads_jobs_table_integrity(pool)
        _ensure_ads_jobs_indexes(pool)
    if TABLE_JOB_ARCHIVE in table_names:
        _ensure_ads_job_archive_indexes(pool)
    if TABLE_SECURITY_MASTER in table_names:
        _ensure_ads_security_master_table_integrity(pool)
    for table_name in SYMBOL_CHILD_TABLES:
        if table_name in table_names:
            _ensure_ads_symbol_child_table_integrity(pool, table_name)


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


def _ensure_ads_jobs_table_integrity(pool) -> None:
    # These table-rebuild migrations are only needed for legacy SQLite files.
    # Postgres tables are created with the correct constraints by PostgresPool.
    """Internal helper to ensure the ADS jobs table integrity exists."""
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

    schema = ads_table_schema_map()[TABLE_JOBS]
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


def _ensure_ads_jobs_indexes(pool) -> None:
    """Create secondary indexes that keep ADS job-queue reads fast."""
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
        pool._Query(
            "CREATE INDEX IF NOT EXISTS ads_jobs_status_idx "
            f"ON {quoted_table_name} (({status_expr}))"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS ads_jobs_ready_order_idx "
            f"ON {quoted_table_name} ({priority_column}, {created_at_column}, {id_column}) "
            f"WHERE {status_expr} IN ('queued', 'retry', 'unfinished')"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS ads_jobs_ready_schedule_idx "
            f"ON {quoted_table_name} ({scheduled_for_column}, {priority_column}, {created_at_column}, {id_column}) "
            f"WHERE {status_expr} IN ('queued', 'retry', 'unfinished')"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS ads_jobs_ready_capability_idx "
            f"ON {quoted_table_name} (({capability_expr}), {priority_column}, {created_at_column}, {id_column}) "
            f"WHERE {status_expr} IN ('queued', 'retry', 'unfinished')"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS ads_jobs_claimed_worker_idx "
            f"ON {quoted_table_name} ({claimed_by_column}, ({status_expr})) "
            f"WHERE coalesce({claimed_by_column}, '') <> ''"
        )
        return
    if dialect == "sqlite":
        status_expr = "lower(coalesce(status, ''))"
        capability_expr = "lower(coalesce(required_capability, ''))"
        pool._Query(
            "CREATE INDEX IF NOT EXISTS ads_jobs_status_idx "
            f"ON {TABLE_JOBS} ({status_expr})"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS ads_jobs_ready_order_idx "
            f"ON {TABLE_JOBS} (priority, created_at, id) "
            f"WHERE {status_expr} IN ('queued', 'retry', 'unfinished')"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS ads_jobs_ready_schedule_idx "
            f"ON {TABLE_JOBS} (scheduled_for, priority, created_at, id) "
            f"WHERE {status_expr} IN ('queued', 'retry', 'unfinished')"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS ads_jobs_ready_capability_idx "
            f"ON {TABLE_JOBS} ({capability_expr}, priority, created_at, id) "
            f"WHERE {status_expr} IN ('queued', 'retry', 'unfinished')"
        )
        pool._Query(
            "CREATE INDEX IF NOT EXISTS ads_jobs_claimed_worker_idx "
            f"ON {TABLE_JOBS} (claimed_by, {status_expr}) "
            "WHERE coalesce(claimed_by, '') <> ''"
        )


def _ensure_ads_job_archive_indexes(pool) -> None:
    """Create secondary indexes that keep ADS archive reads bounded."""
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
            "CREATE INDEX IF NOT EXISTS ads_jobs_archive_completed_idx "
            f"ON {quoted_table_name} ({completed_at_column} DESC, {archived_at_column} DESC)"
        )
        return
    if dialect == "sqlite":
        pool._Query(
            "CREATE INDEX IF NOT EXISTS ads_jobs_archive_completed_idx "
            f"ON {TABLE_JOB_ARCHIVE} (completed_at DESC, archived_at DESC)"
        )


def _ensure_ads_daily_price_indexes(pool) -> None:
    """Internal helper to ensure the ADS daily price indexes exists."""
    if _pool_dialect(pool) != "sqlite":
        return
    conn = getattr(pool, "conn", None)
    if conn is None:
        return
    ensure_connection = getattr(pool, "_ensure_connection", None)
    if callable(ensure_connection):
        ensure_connection()
    try:
        with pool.lock:
            cursor = pool.conn.cursor()
            cursor.execute("PRAGMA index_list('ads_daily_price')")
            expected_columns = ["symbol", "trade_date", "provider"]
            for index_row in cursor.fetchall():
                if len(index_row) < 3 or not index_row[2]:
                    continue
                index_name = index_row[1]
                cursor.execute(f"PRAGMA index_info('{index_name}')")
                index_columns = [row[2] for row in cursor.fetchall()]
                if index_columns == expected_columns:
                    return
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS ads_daily_price_symbol_trade_date_provider_uq
                ON ads_daily_price (symbol, trade_date, provider)
                """
            )
            pool.conn.commit()
    except Exception:
        # Other pool implementations enforce this outside the runtime layer.
        return


def _row_latest_sort_key(row: Dict[str, object], order_index: int) -> tuple[datetime, datetime, int]:
    """Internal helper to return the row latest sort key."""
    return (
        _parse_schema_datetime(row.get("updated_at") or row.get("created_at")),
        _parse_schema_datetime(row.get("created_at")),
        order_index,
    )


def _ensure_ads_security_master_table_integrity(pool) -> None:
    """Internal helper to ensure the ADS security master table integrity exists."""
    if _pool_dialect(pool) != "sqlite":
        return
    conn = getattr(pool, "conn", None)
    if conn is None or not pool._TableExists(TABLE_SECURITY_MASTER):
        return
    ensure_connection = getattr(pool, "_ensure_connection", None)
    if callable(ensure_connection):
        ensure_connection()

    with pool.lock:
        cursor = pool.conn.cursor()
        cursor.execute(f"PRAGMA table_info('{TABLE_SECURITY_MASTER}')")
        columns = cursor.fetchall()
    has_symbol_primary_key = any(
        len(column) > 5 and column[1] == "symbol" and int(column[5] or 0) > 0
        for column in columns
    )
    has_symbol_varchar = any(
        len(column) > 2 and column[1] == "symbol" and str(column[2] or "").strip().upper() == "VARCHAR(20)"
        for column in columns
    )

    schema = ads_table_schema_map()[TABLE_SECURITY_MASTER]
    rows = pool._GetTableData(TABLE_SECURITY_MASTER, table_schema=schema) or []
    normalized_rows = [dict(row) for row in rows if isinstance(row, dict)]
    latest_rows_by_symbol: Dict[str, Dict[str, object]] = {}
    latest_order_by_symbol: Dict[str, int] = {}
    for index, row in enumerate(normalized_rows):
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        row["symbol"] = symbol
        current = latest_rows_by_symbol.get(symbol)
        current_index = latest_order_by_symbol.get(symbol, -1)
        if current is None or _row_latest_sort_key(row, index) > _row_latest_sort_key(current, current_index):
            latest_rows_by_symbol[symbol] = row
            latest_order_by_symbol[symbol] = index
    compacted_rows = list(latest_rows_by_symbol.values())
    has_duplicates = len(compacted_rows) != len([row for row in normalized_rows if str(row.get("symbol") or "").strip()])

    if has_symbol_primary_key and has_symbol_varchar and not has_duplicates:
        return

    backup_table = f"{TABLE_SECURITY_MASTER}__legacy_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    with pool.lock:
        cursor = pool.conn.cursor()
        cursor.execute(f"ALTER TABLE {TABLE_SECURITY_MASTER} RENAME TO {backup_table}")
        pool.conn.commit()
    pool._CreateTable(TABLE_SECURITY_MASTER, schema)
    if compacted_rows:
        pool._InsertMany(TABLE_SECURITY_MASTER, compacted_rows)
    with pool.lock:
        cursor = pool.conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {backup_table}")
        pool.conn.commit()


def _table_has_symbol_foreign_key(pool, table_name: str) -> tuple[bool, bool]:
    """Return whether the table has symbol foreign key."""
    if _pool_dialect(pool) != "sqlite":
        return True, True
    has_foreign_key = False
    has_symbol_varchar = False
    with pool.lock:
        cursor = pool.conn.cursor()
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        for column in cursor.fetchall():
            if len(column) > 2 and column[1] == "symbol" and str(column[2] or "").strip().upper() == "VARCHAR(20)":
                has_symbol_varchar = True
                break
        cursor.execute(f"PRAGMA foreign_key_list('{table_name}')")
        for foreign_key in cursor.fetchall():
            if len(foreign_key) < 5:
                continue
            referenced_table = str(foreign_key[2] or "").strip()
            from_column = str(foreign_key[3] or "").strip()
            to_column = str(foreign_key[4] or "").strip()
            if referenced_table == TABLE_SECURITY_MASTER and from_column == "symbol" and to_column == "symbol":
                has_foreign_key = True
                break
    return has_symbol_varchar, has_foreign_key


def _ensure_security_master_parent_rows_for_existing_rows(pool, table_name: str, rows: List[Dict[str, object]]) -> None:
    """
    Internal helper to ensure the security master parent rows for the existing rows
    exists.
    """
    if not rows:
        return
    now = datetime.now(timezone.utc).isoformat()
    security_schema = ads_table_schema_map()[TABLE_SECURITY_MASTER]
    existing_rows = pool._GetTableData(TABLE_SECURITY_MASTER, table_schema=security_schema) or []
    existing_symbols = {
        str(row.get("symbol") or "").strip().upper()
        for row in existing_rows
        if isinstance(row, dict)
    }
    parent_rows: List[Dict[str, object]] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol or symbol in existing_symbols:
            continue
        existing_symbols.add(symbol)
        parent_rows.append(
            {
                "id": f"ads-security-master:{symbol}",
                "symbol": symbol,
                "name": symbol,
                "instrument_type": "",
                "exchange": "",
                "currency": "",
                "is_active": True,
                "provider": str(row.get("provider") or "ads"),
                "metadata": {"auto_created": True, "source": f"{table_name}_migration_parent"},
                "created_at": now,
                "updated_at": now,
            }
        )
    if parent_rows:
        pool._InsertMany(TABLE_SECURITY_MASTER, parent_rows)


def _ensure_ads_symbol_child_table_integrity(pool, table_name: str) -> None:
    """Internal helper to ensure the ADS symbol child table integrity exists."""
    if _pool_dialect(pool) != "sqlite":
        return
    conn = getattr(pool, "conn", None)
    if conn is None or not pool._TableExists(table_name):
        return
    ensure_connection = getattr(pool, "_ensure_connection", None)
    if callable(ensure_connection):
        ensure_connection()

    if table_name == TABLE_DAILY_PRICE:
        _ensure_ads_daily_price_indexes(pool)

    try:
        has_symbol_varchar, has_foreign_key = _table_has_symbol_foreign_key(pool, table_name)
    except Exception:
        return

    if has_foreign_key and has_symbol_varchar:
        return

    schema = ads_table_schema_map()[table_name]
    security_schema = ads_table_schema_map()[TABLE_SECURITY_MASTER]
    table_rows = [
        dict(row)
        for row in (pool._GetTableData(table_name, table_schema=schema) or [])
        if isinstance(row, dict)
    ]
    _ensure_security_master_parent_rows_for_existing_rows(pool, table_name, table_rows)
    security_rows = pool._GetTableData(TABLE_SECURITY_MASTER, table_schema=security_schema) or []
    valid_symbols = {str(row.get("symbol") or "").strip().upper() for row in security_rows if isinstance(row, dict)}
    preserved_rows = []
    for row in table_rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        row["symbol"] = symbol
        if symbol and symbol in valid_symbols:
            preserved_rows.append(row)

    backup_table = f"{table_name}__legacy_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    with pool.lock:
        cursor = pool.conn.cursor()
        cursor.execute(f"ALTER TABLE {table_name} RENAME TO {backup_table}")
        pool.conn.commit()
    pool._CreateTable(table_name, schema)
    if preserved_rows:
        pool._InsertMany(table_name, preserved_rows)
    with pool.lock:
        cursor = pool.conn.cursor()
        cursor.execute(f"DROP TABLE IF EXISTS {backup_table}")
        pool.conn.commit()
