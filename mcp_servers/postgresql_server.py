"""
PostgreSQL MCP server implementation for `mcp_servers.postgresql_server`.

These modules expose selected local services through the Model Context Protocol for use
by workspace agents.

Important callables in this file include `postgres_execute`, `main`,
`postgres_describe_table`, `postgres_list_tables`, and `postgres_query`, which capture
the primary workflow implemented by the module.
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID

import psycopg
from dotenv import load_dotenv
from mcp.server import FastMCP
from psycopg.rows import dict_row

try:
    from psycopg.types.json import Json
except ImportError:  # pragma: no cover - older psycopg builds
    Json = None


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv_for_server() -> None:
    """Load local .env values for MCP server execution without polluting imports."""
    load_dotenv(REPO_ROOT / ".env", override=False)

SERVER_NAME = "postgresql"
DEFAULT_QUERY_LIMIT = 200
READ_ONLY_KEYWORDS = {"select", "show", "explain", "values", "table", "with"}
WRITE_KEYWORDS = {
    "alter",
    "analyze",
    "call",
    "checkpoint",
    "cluster",
    "comment",
    "commit",
    "copy",
    "create",
    "deallocate",
    "delete",
    "discard",
    "do",
    "drop",
    "grant",
    "insert",
    "lock",
    "merge",
    "refresh",
    "reindex",
    "reset",
    "revoke",
    "rollback",
    "set",
    "start",
    "truncate",
    "update",
    "vacuum",
}
DESTRUCTIVE_KEYWORDS = {"delete", "drop", "truncate"}

server = FastMCP("postgresql")


def _strip_sql_literals_and_comments(sql: str) -> str:
    """Internal helper to strip the SQL literals and comments."""
    result: list[str] = []
    index = 0
    length = len(sql)
    state = "normal"
    dollar_tag = ""

    while index < length:
        current = sql[index]
        nxt = sql[index + 1] if index + 1 < length else ""

        if state == "line_comment":
            if current == "\n":
                state = "normal"
                result.append("\n")
            else:
                result.append(" ")
            index += 1
            continue

        if state == "block_comment":
            if current == "*" and nxt == "/":
                result.extend("  ")
                index += 2
                state = "normal"
            else:
                result.append("\n" if current == "\n" else " ")
                index += 1
            continue

        if state == "single_quote":
            if current == "'" and nxt == "'":
                result.extend("  ")
                index += 2
                continue
            if current == "'":
                state = "normal"
            result.append("\n" if current == "\n" else " ")
            index += 1
            continue

        if state == "double_quote":
            if current == '"':
                state = "normal"
            result.append("\n" if current == "\n" else " ")
            index += 1
            continue

        if state == "dollar_quote":
            if dollar_tag and sql.startswith(dollar_tag, index):
                result.extend(" " * len(dollar_tag))
                index += len(dollar_tag)
                state = "normal"
            else:
                result.append("\n" if current == "\n" else " ")
                index += 1
            continue

        if current == "-" and nxt == "-":
            result.extend("  ")
            index += 2
            state = "line_comment"
            continue

        if current == "/" and nxt == "*":
            result.extend("  ")
            index += 2
            state = "block_comment"
            continue

        if current == "'":
            result.append(" ")
            index += 1
            state = "single_quote"
            continue

        if current == '"':
            result.append(" ")
            index += 1
            state = "double_quote"
            continue

        if current == "$":
            match = re.match(r"\$[A-Za-z0-9_]*\$", sql[index:])
            if match:
                dollar_tag = match.group(0)
                result.extend(" " * len(dollar_tag))
                index += len(dollar_tag)
                state = "dollar_quote"
                continue

        result.append(current)
        index += 1

    return "".join(result)


def _ensure_single_statement(sql: str) -> str:
    """Internal helper to ensure the single statement exists."""
    sanitized = _strip_sql_literals_and_comments(sql)
    trimmed = sanitized.strip()
    if not trimmed:
        raise ValueError("SQL cannot be empty.")

    while trimmed.endswith(";"):
        trimmed = trimmed[:-1].rstrip()

    if ";" in trimmed:
        raise ValueError("Only one SQL statement is allowed per tool call.")

    return trimmed


def _extract_keywords(sql: str) -> list[str]:
    """Internal helper to extract the keywords."""
    return [token.lower() for token in re.findall(r"\b[a-z_]+\b", sql)]


def _first_keyword(sql: str) -> str:
    """Internal helper for first keyword."""
    keywords = _extract_keywords(sql)
    if not keywords:
        raise ValueError("Could not determine the SQL command.")
    return keywords[0]


def _contains_write_keywords(sql: str) -> bool:
    """Return whether the value contains write keywords."""
    return any(token in WRITE_KEYWORDS for token in _extract_keywords(sql))


def _contains_where_clause(sql: str) -> bool:
    """Return whether the value contains where clause."""
    return bool(re.search(r"\bwhere\b", sql, flags=re.IGNORECASE))


def _normalize_limit(limit: int) -> int:
    """Internal helper to normalize the limit."""
    if limit <= 0:
        raise ValueError("limit must be greater than 0.")
    return min(limit, 1000)


def _resolve_conninfo(dsn: str | None = None) -> str:
    """Internal helper to resolve the conninfo."""
    if dsn:
        return dsn

    for env_name in ("POSTGRES_DSN", "DATABASE_URL", "SUPABASE_DB_URL"):
        value = os.getenv(env_name)
        if value:
            return value

    pg_env_vars = ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER", "PGPASSWORD")
    if any(os.getenv(name) for name in pg_env_vars):
        return ""

    raise ValueError(
        "No PostgreSQL connection settings were found. "
        "Set POSTGRES_DSN or DATABASE_URL, configure libpq PG* variables, "
        "or pass a dsn value to the tool call."
    )


def _adapt_params(params: list[Any] | dict[str, Any] | None) -> list[Any] | dict[str, Any] | None:
    """Internal helper for adapt params."""
    if params is None:
        return None
    if isinstance(params, dict):
        return {key: _adapt_param_value(value) for key, value in params.items()}
    if isinstance(params, list):
        return [_adapt_param_value(value) for value in params]
    raise ValueError("params must be a JSON object, a JSON array, or null.")


def _adapt_param_value(value: Any) -> Any:
    """Internal helper to return the adapt param value."""
    if isinstance(value, dict):
        if Json is None:
            return value
        return Json(value)
    if isinstance(value, list):
        return [_adapt_param_value(item) for item in value]
    return value


def _serialize_value(value: Any) -> Any:
    """Internal helper to serialize the value."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _serialize_value(item) for key, item in value.items()}
    return str(value)


def _serialize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Internal helper to serialize the rows."""
    return [{str(key): _serialize_value(value) for key, value in row.items()} for row in rows]


@contextmanager
def _connect(dsn: str | None = None, *, autocommit: bool = True) -> Iterator[psycopg.Connection[Any]]:
    """Internal helper to connect the value."""
    connection = psycopg.connect(_resolve_conninfo(dsn), autocommit=autocommit, row_factory=dict_row)
    try:
        yield connection
    finally:
        connection.close()


@server.tool(
    name="postgres_server_status",
    description="Return basic PostgreSQL connection details and server metadata.",
)
def postgres_server_status(dsn: str | None = None) -> dict[str, Any]:
    """Return the Postgres server status."""
    with _connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    current_database() as database_name,
                    current_user as current_user,
                    current_setting('server_version') as server_version,
                    current_setting('default_transaction_read_only') as read_only,
                    current_setting('search_path') as search_path
                """
            )
            row = cursor.fetchone() or {}
    return _serialize_value(row)


@server.tool(
    name="postgres_list_tables",
    description="List tables, views, and materialized views for a PostgreSQL schema.",
)
def postgres_list_tables(
    schema_name: str = "public",
    include_views: bool = True,
    dsn: str | None = None,
) -> dict[str, Any]:
    """Handle Postgres list tables."""
    relation_types = ["BASE TABLE", "FOREIGN TABLE"]
    if include_views:
        relation_types.extend(["VIEW", "MATERIALIZED VIEW"])

    with _connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    table_schema,
                    table_name,
                    table_type
                from information_schema.tables
                where table_schema = %s
                  and table_type = any(%s)
                order by table_schema, table_name
                """,
                (schema_name, relation_types),
            )
            rows = cursor.fetchall()

    return {
        "schema": schema_name,
        "count": len(rows),
        "tables": _serialize_rows(rows),
    }


@server.tool(
    name="postgres_describe_table",
    description="Describe a PostgreSQL table, including columns, primary keys, and indexes.",
)
def postgres_describe_table(
    table_name: str,
    schema_name: str = "public",
    dsn: str | None = None,
) -> dict[str, Any]:
    """Return the Postgres describe table."""
    with _connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                    column_name,
                    data_type,
                    is_nullable,
                    column_default,
                    ordinal_position
                from information_schema.columns
                where table_schema = %s
                  and table_name = %s
                order by ordinal_position
                """,
                (schema_name, table_name),
            )
            columns = cursor.fetchall()

            if not columns:
                raise ValueError(f"Table '{schema_name}.{table_name}' was not found.")

            cursor.execute(
                """
                select
                    kcu.column_name
                from information_schema.table_constraints tc
                join information_schema.key_column_usage kcu
                  on tc.constraint_name = kcu.constraint_name
                 and tc.table_schema = kcu.table_schema
                where tc.table_schema = %s
                  and tc.table_name = %s
                  and tc.constraint_type = 'PRIMARY KEY'
                order by kcu.ordinal_position
                """,
                (schema_name, table_name),
            )
            primary_key = [row["column_name"] for row in cursor.fetchall()]

            cursor.execute(
                """
                select
                    indexname,
                    indexdef
                from pg_indexes
                where schemaname = %s
                  and tablename = %s
                order by indexname
                """,
                (schema_name, table_name),
            )
            indexes = cursor.fetchall()

    return {
        "schema": schema_name,
        "table_name": table_name,
        "columns": _serialize_rows(columns),
        "primary_key": primary_key,
        "indexes": _serialize_rows(indexes),
    }


@server.tool(
    name="postgres_query",
    description="Run a read-only SQL query against PostgreSQL and return rows.",
)
def postgres_query(
    sql: str,
    params: list[Any] | dict[str, Any] | None = None,
    limit: int = DEFAULT_QUERY_LIMIT,
    dsn: str | None = None,
) -> dict[str, Any]:
    """Handle Postgres query."""
    sanitized = _ensure_single_statement(sql)
    first_keyword = _first_keyword(sanitized)
    if first_keyword not in READ_ONLY_KEYWORDS or _contains_write_keywords(sanitized):
        raise ValueError(
            "postgres_query only accepts read-only SQL such as SELECT, SHOW, EXPLAIN, VALUES, or TABLE."
        )

    safe_limit = _normalize_limit(limit)
    bound_params = _adapt_params(params)

    with _connect(dsn, autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, bound_params)
            rows = cursor.fetchmany(safe_limit + 1)
            column_names = [column.name for column in cursor.description or []]

    truncated = len(rows) > safe_limit
    visible_rows = rows[:safe_limit]
    return {
        "columns": column_names,
        "row_count": len(visible_rows),
        "truncated": truncated,
        "limit": safe_limit,
        "rows": _serialize_rows(visible_rows),
    }


@server.tool(
    name="postgres_execute",
    description="Run a single write or DDL SQL statement against PostgreSQL with safety checks.",
)
def postgres_execute(
    sql: str,
    params: list[Any] | dict[str, Any] | None = None,
    acknowledge_destructive: bool = False,
    allow_full_table_write: bool = False,
    dsn: str | None = None,
) -> dict[str, Any]:
    """Handle Postgres execute."""
    sanitized = _ensure_single_statement(sql)
    first_keyword = _first_keyword(sanitized)
    if first_keyword in READ_ONLY_KEYWORDS and not _contains_write_keywords(sanitized):
        raise ValueError("Use postgres_query for read-only SQL.")

    if first_keyword in DESTRUCTIVE_KEYWORDS and not acknowledge_destructive:
        raise ValueError(
            "This statement is destructive. Re-run with acknowledge_destructive=true if it is intentional."
        )

    if first_keyword in {"update", "delete"} and not allow_full_table_write and not _contains_where_clause(sanitized):
        raise ValueError(
            "UPDATE and DELETE statements require a WHERE clause unless allow_full_table_write=true."
        )

    bound_params = _adapt_params(params)

    with _connect(dsn, autocommit=False) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql, bound_params)
            returned_rows: list[dict[str, Any]] = []
            columns: list[str] = []
            if cursor.description:
                returned_rows = cursor.fetchall()
                columns = [column.name for column in cursor.description]
            row_count = cursor.rowcount
        connection.commit()

    return {
        "command": first_keyword.upper(),
        "row_count": row_count,
        "columns": columns,
        "rows": _serialize_rows(returned_rows),
    }


def main() -> None:
    """Run the main entry point."""
    _load_dotenv_for_server()
    server.run("stdio")


if __name__ == "__main__":
    main()
