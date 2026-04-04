"""
Postgres module for `prompits.pools.postgres`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the pools package implements
storage adapters and pool-specific helpers.

Core types exposed here include `PostgresPool`, which carry the main behavior or state
managed by this module.
"""

import json
import os
import traceback
from urllib.parse import parse_qsl, urlsplit
from typing import Any, Dict, List, Optional, Union

from prompits.core.pool import Pool, PoolCap
from prompits.core.schema import DataType, TableSchema

try:
    import psycopg
except ImportError:  # pragma: no cover - exercised when dependency is missing at runtime
    psycopg = None
    print("Warning: psycopg package not installed. PostgresPool will not work.")


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

    return ""


def _conninfo_has_sslmode(conninfo: str) -> bool:
    """Return whether the conninfo has sslmode."""
    normalized = str(conninfo or "").strip()
    if not normalized:
        return False
    if "://" in normalized:
        try:
            query_pairs = parse_qsl(urlsplit(normalized).query, keep_blank_values=True)
        except Exception:
            return "sslmode=" in normalized.lower()
        return any(str(key or "").strip().lower() == "sslmode" for key, _value in query_pairs)
    return "sslmode=" in normalized.lower()


def _requires_ssl(error: Exception) -> bool:
    """Return whether the value requires ssl."""
    message = str(error or "").strip().lower()
    return "server does not support ssl" in message and "ssl was required" in message


class PostgresPool(Pool):
    """
    Pool implementation backed by a direct PostgreSQL connection.

    Unlike `SupabasePool`, this talks to PostgreSQL over psycopg and is suited
    for shared ADS dispatcher/worker deployments where all agents should point
    at the same relational database.
    """

    def __init__(
        self,
        name: str,
        description: str | None = None,
        dsn: str = "",
        schema: str = "public",
        sslmode: str = "",
    ):
        """Initialize the Postgres pool."""
        super().__init__(
            name,
            description,
            capabilities=[PoolCap.TABLE, PoolCap.JSON, PoolCap.SEARCH, PoolCap.MEMORY],
        )
        self.dsn = str(dsn or "")
        self.schema = str(schema or "public").strip() or "public"
        self.sslmode = str(sslmode or "").strip()
        self.conn = None
        self.connect()

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        """Internal helper to quote the identifier."""
        return f'"{str(identifier or "").replace(chr(34), chr(34) * 2)}"'

    def _split_table_name(self, table_name: str) -> tuple[str, str]:
        """Internal helper to return the split table name."""
        raw_name = str(table_name or "").strip()
        if not raw_name:
            raise ValueError("table_name is required.")
        if "." in raw_name:
            schema_name, relation_name = raw_name.split(".", 1)
            return schema_name.strip() or self.schema, relation_name.strip()
        return self.schema, raw_name

    def _qualified_table_name(self, table_name: str) -> str:
        """Internal helper to return the qualified table name."""
        schema_name, relation_name = self._split_table_name(table_name)
        if schema_name:
            return f"{schema_name}.{relation_name}"
        return relation_name

    def _quoted_table_name(self, table_name: str) -> str:
        """Internal helper to return the quoted table name."""
        schema_name, relation_name = self._split_table_name(table_name)
        if schema_name:
            return f"{self._quote_identifier(schema_name)}.{self._quote_identifier(relation_name)}"
        return self._quote_identifier(relation_name)

    @staticmethod
    def _get_postgres_type(column_type: DataType) -> str:
        """Internal helper to return the Postgres type."""
        type_map = {
            DataType.STRING: "TEXT",
            DataType.INTEGER: "BIGINT",
            DataType.FLOAT: "DOUBLE PRECISION",
            DataType.BOOLEAN: "BOOLEAN",
            DataType.DATETIME: "TIMESTAMPTZ",
            DataType.DATE: "DATE",
            DataType.TIME: "TIME",
            DataType.JSON: "JSONB",
            DataType.OBJECT: "JSONB",
            DataType.ARRAY: "JSONB",
            DataType.UUID: "UUID",
        }
        return type_map.get(column_type, "TEXT")

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """Internal helper to serialize the value."""
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value

    @staticmethod
    def _decode_row_value(value: Any, column_name: str = "", table_schema: TableSchema | None = None) -> Any:
        """Internal helper to decode the row value."""
        if not isinstance(value, str):
            return value
        if table_schema and column_name in table_schema.rowSchema.columns:
            column_type = DataType.from_string(table_schema.rowSchema.columns[column_name]["type"])
            if column_type in {DataType.JSON, DataType.OBJECT, DataType.ARRAY}:
                try:
                    return json.loads(value)
                except Exception:
                    return value
        if (value.startswith("{") and value.endswith("}")) or (value.startswith("[") and value.endswith("]")):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

    def connect(self):
        """Connect the value."""
        if psycopg is None:
            self.conn = None
            self.is_connected = False
            self.last_error = "psycopg package is not installed."
            return False
        conninfo = _resolve_conninfo(self.dsn)
        connect_kwargs: Dict[str, Any] = {"autocommit": True}
        if self.sslmode and not _conninfo_has_sslmode(conninfo):
            connect_kwargs["sslmode"] = self.sslmode
        try:
            self.conn = psycopg.connect(conninfo, **connect_kwargs)
            self.is_connected = True
            self.last_error = ""
            return True
        except Exception as exc:
            if _requires_ssl(exc):
                retry_kwargs = dict(connect_kwargs)
                retry_kwargs["sslmode"] = "disable"
                try:
                    self.conn = psycopg.connect(conninfo, **retry_kwargs)
                    self.is_connected = True
                    self.last_error = ""
                    print(f"[{self.name}] Info: PostgreSQL server rejected SSL; retried with sslmode=disable.")
                    return True
                except Exception as retry_exc:
                    exc = retry_exc
            self.conn = None
            self.is_connected = False
            self.last_error = f"Error connecting to PostgreSQL: {exc}"
            print(f"[{self.name}] {self.last_error}")
            return False

    def disconnect(self):
        """Disconnect the value."""
        try:
            if self.conn is not None:
                self.conn.close()
            self.conn = None
            self.is_connected = False
            self.last_error = ""
            return True
        except Exception as exc:
            self.last_error = f"Error disconnecting from PostgreSQL: {exc}"
            print(f"[{self.name}] {self.last_error}")
            return False

    def _ensure_connection(self):
        """Internal helper to ensure the connection exists."""
        if not self.is_connected or self.conn is None:
            return self.connect()
        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except Exception:
            return self.connect()

    def _TableExists(self, table_name: str) -> bool:
        """Return whether the table exists for value."""
        try:
            with self.lock:
                if not self._ensure_connection() or self.conn is None:
                    return False
                with self.conn.cursor() as cursor:
                    cursor.execute("SELECT to_regclass(%s)", [self._qualified_table_name(table_name)])
                    row = cursor.fetchone()
                self.last_error = ""
                return bool(row and row[0])
        except Exception as exc:
            self.last_error = f"Error checking PostgreSQL table '{table_name}': {exc}"
            print(f"[{self.name}] {self.last_error}")
            return False

    def _CreateTable(self, table_name: str, schema: TableSchema):
        """Internal helper to create the table."""
        try:
            with self.lock:
                if not self._ensure_connection() or self.conn is None:
                    return False
                schema_name, _relation_name = self._split_table_name(table_name)
                with self.conn.cursor() as cursor:
                    if schema_name:
                        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {self._quote_identifier(schema_name)}")

                    column_definitions = []
                    for column_name, column_spec in schema.rowSchema.columns.items():
                        explicit_sql_type = str(column_spec.get("sql_type") or "").strip()
                        postgres_type = (
                            explicit_sql_type
                            if explicit_sql_type
                            else self._get_postgres_type(DataType.from_string(column_spec["type"]))
                        )
                        column_definitions.append(
                            f"{self._quote_identifier(column_name)} {postgres_type}"
                        )

                    primary_key_columns = [
                        column
                        for column in getattr(schema, "primary_key", []) or []
                        if column in schema.rowSchema.columns
                    ]
                    unique_constraints = []
                    for constraint in getattr(schema, "unique_constraints", []) or []:
                        unique_columns = [column for column in constraint if column in schema.rowSchema.columns]
                        if unique_columns:
                            unique_constraints.append(
                                "UNIQUE ("
                                + ", ".join(self._quote_identifier(column) for column in unique_columns)
                                + ")"
                            )

                    foreign_keys = []
                    for foreign_key in getattr(schema, "foreign_keys", []) or []:
                        foreign_key_columns = [
                            column
                            for column in foreign_key.get("columns", [])
                            if column in schema.rowSchema.columns
                        ]
                        references = (
                            foreign_key.get("references")
                            if isinstance(foreign_key.get("references"), dict)
                            else {}
                        )
                        reference_table = str(references.get("table") or "").strip()
                        reference_columns = [column for column in references.get("columns", []) if column]
                        if (
                            not foreign_key_columns
                            or not reference_table
                            or not reference_columns
                            or len(foreign_key_columns) != len(reference_columns)
                        ):
                            continue
                        clause = (
                            "FOREIGN KEY ("
                            + ", ".join(self._quote_identifier(column) for column in foreign_key_columns)
                            + ") REFERENCES "
                            + self._quoted_table_name(reference_table)
                            + " ("
                            + ", ".join(self._quote_identifier(column) for column in reference_columns)
                            + ")"
                        )
                        on_delete = str(foreign_key.get("on_delete") or "").strip().upper()
                        if on_delete:
                            clause += f" ON DELETE {on_delete}"
                        on_update = str(foreign_key.get("on_update") or "").strip().upper()
                        if on_update:
                            clause += f" ON UPDATE {on_update}"
                        foreign_keys.append(clause)

                    table_parts = list(column_definitions)
                    if primary_key_columns:
                        table_parts.append(
                            "PRIMARY KEY ("
                            + ", ".join(self._quote_identifier(column) for column in primary_key_columns)
                            + ")"
                        )
                    table_parts.extend(unique_constraints)
                    table_parts.extend(foreign_keys)

                    cursor.execute(
                        f"CREATE TABLE IF NOT EXISTS {self._quoted_table_name(table_name)} ({', '.join(table_parts)})"
                    )
                self.last_error = ""
                return True
        except Exception as exc:
            self.last_error = f"Error creating PostgreSQL table '{table_name}': {exc}"
            print(f"[{self.name}] {self.last_error}")
            traceback.print_exc()
            return False

    def _table_unique_conflict_targets(self, table_name: str) -> List[List[str]]:
        """Internal helper to return the table unique conflict targets."""
        if self.conn is None:
            return []
        schema_name, relation_name = self._split_table_name(table_name)
        candidates: List[List[str]] = []
        with self.conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    tc.constraint_name,
                    tc.constraint_type,
                    kcu.column_name,
                    kcu.ordinal_position
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                 AND tc.table_name = kcu.table_name
                WHERE tc.table_schema = %s
                  AND tc.table_name = %s
                  AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
                ORDER BY tc.constraint_name, kcu.ordinal_position
                """,
                [schema_name, relation_name],
            )
            rows = cursor.fetchall()
        grouped: Dict[str, List[str]] = {}
        for row in rows:
            if not row or len(row) < 4:
                continue
            constraint_name = str(row[0] or "").strip()
            column_name = str(row[2] or "").strip()
            if not constraint_name or not column_name:
                continue
            grouped.setdefault(constraint_name, []).append(column_name)
        seen = set()
        for candidate in grouped.values():
            key = tuple(candidate)
            if candidate and key not in seen:
                seen.add(key)
                candidates.append(candidate)
        return candidates

    def _build_insert_sql(self, table_name: str, columns: List[str]) -> str:
        """Internal helper to build the insert SQL."""
        placeholders = ", ".join(["%s" for _ in columns])
        columns_sql = ", ".join(self._quote_identifier(column) for column in columns)
        matching_candidates = [
            candidate
            for candidate in self._table_unique_conflict_targets(table_name)
            if all(column in columns for column in candidate)
        ]
        if matching_candidates:
            conflict_columns = sorted(
                matching_candidates,
                key=lambda candidate: (len(candidate), tuple(column != "id" for column in candidate)),
                reverse=True,
            )[0]
            update_columns = [column for column in columns if column not in conflict_columns]
            conflict_sql = ", ".join(self._quote_identifier(column) for column in conflict_columns)
            if update_columns:
                updates = ", ".join(
                    f"{self._quote_identifier(column)} = EXCLUDED.{self._quote_identifier(column)}"
                    for column in update_columns
                )
                return (
                    f"INSERT INTO {self._quoted_table_name(table_name)} ({columns_sql}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({conflict_sql}) DO UPDATE SET {updates}"
                )
            return (
                f"INSERT INTO {self._quoted_table_name(table_name)} ({columns_sql}) VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict_sql}) DO NOTHING"
            )
        return f"INSERT INTO {self._quoted_table_name(table_name)} ({columns_sql}) VALUES ({placeholders})"

    def _Insert(self, table_name: str, data: Dict[str, Any]):
        """Internal helper for insert."""
        try:
            with self.lock:
                if not self._ensure_connection() or self.conn is None:
                    return False
                columns = list(data.keys())
                sql = self._build_insert_sql(table_name, columns)
                values = [self._serialize_value(data.get(column)) for column in columns]
                with self.conn.cursor() as cursor:
                    cursor.execute(sql, values)
                self.last_error = ""
                return True
        except Exception as exc:
            self.last_error = f"Error inserting PostgreSQL row into '{table_name}': {exc}"
            print(f"[{self.name}] {self.last_error}")
            traceback.print_exc()
            return False

    def _InsertMany(self, table_name: str, data_list: List[Dict[str, Any]]):
        """Internal helper for insert many."""
        try:
            if not data_list:
                return True
            with self.lock:
                if not self._ensure_connection() or self.conn is None:
                    return False
                columns = list(data_list[0].keys())
                sql = self._build_insert_sql(table_name, columns)
                rows = [
                    [self._serialize_value(data.get(column)) for column in columns]
                    for data in data_list
                ]
                with self.conn.cursor() as cursor:
                    cursor.executemany(sql, rows)
                self.last_error = ""
                return True
        except Exception as exc:
            self.last_error = f"Error inserting PostgreSQL batch into '{table_name}': {exc}"
            print(f"[{self.name}] {self.last_error}")
            traceback.print_exc()
            return False

    def _Query(self, query: str, params: Union[List[Any], Dict[str, Any]] = None):
        """Internal helper to query the value."""
        try:
            with self.lock:
                if not self._ensure_connection() or self.conn is None:
                    return []
                normalized_params: Any = params
                if isinstance(params, list):
                    normalized_params = [self._serialize_value(value) for value in params]
                elif isinstance(params, dict):
                    normalized_params = {
                        key: self._serialize_value(value) for key, value in params.items()
                    }
                with self.conn.cursor() as cursor:
                    cursor.execute(query, normalized_params)
                    if cursor.description is None:
                        self.last_error = ""
                        return []
                    self.last_error = ""
                    return cursor.fetchall()
        except Exception as exc:
            self.last_error = f"Error querying PostgreSQL: {exc}"
            print(f"[{self.name}] {self.last_error}")
            return []

    def _GetTableData(
        self,
        table_name: str,
        id_or_where: Union[str, Dict] = None,
        table_schema: TableSchema = None,
    ) -> List[Dict[str, Any]]:
        """Internal helper to return the table data."""
        try:
            with self.lock:
                if not self._ensure_connection() or self.conn is None:
                    return []
                params: List[Any] = []
                if not id_or_where:
                    sql = f"SELECT * FROM {self._quoted_table_name(table_name)}"
                elif isinstance(id_or_where, str):
                    sql = f"SELECT * FROM {self._quoted_table_name(table_name)} WHERE {self._quote_identifier('id')} = %s"
                    params = [id_or_where]
                elif isinstance(id_or_where, dict):
                    conditions = []
                    for key, value in id_or_where.items():
                        conditions.append(f"{self._quote_identifier(key)} = %s")
                        params.append(self._serialize_value(value))
                    sql = f"SELECT * FROM {self._quoted_table_name(table_name)} WHERE {' AND '.join(conditions)}"
                else:
                    return []

                with self.conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    columns = [desc[0] for desc in cursor.description or []]
                    rows = cursor.fetchall()
                self.last_error = ""

            results = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                for key, value in list(row_dict.items()):
                    row_dict[key] = self._decode_row_value(value, key, table_schema)
                results.append(row_dict)
            return results
        except Exception as exc:
            self.last_error = f"Error reading PostgreSQL table '{table_name}': {exc}"
            print(f"[{self.name}] {self.last_error}")
            return []

    def store_memory(
        self,
        content: Any,
        memory_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        memory_type: str = "text",
        table_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle store memory for the Postgres pool."""
        memory_table = table_name or self.MEMORY_TABLE
        if not self._TableExists(memory_table):
            self._CreateTable(memory_table, self.memory_table_schema())
        record = self._normalize_memory_record(
            content=content,
            memory_id=memory_id,
            metadata=metadata,
            tags=tags,
            memory_type=memory_type,
        )
        if not self._Insert(memory_table, record):
            raise ValueError(f"Failed storing memory in table '{memory_table}'")
        return record

    def search_memory(
        self,
        query: str,
        limit: int = 10,
        table_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search the memory."""
        if not query:
            return []
        memory_table = table_name or self.MEMORY_TABLE
        if not self._TableExists(memory_table):
            return []
        try:
            with self.lock:
                if not self._ensure_connection() or self.conn is None:
                    return []
                with self.conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT * FROM {self._quoted_table_name(memory_table)}
                        WHERE CAST(content AS TEXT) ILIKE %s
                           OR CAST(metadata AS TEXT) ILIKE %s
                           OR CAST(tags AS TEXT) ILIKE %s
                        ORDER BY updated_at DESC
                        LIMIT %s
                        """,
                        [f"%{query}%", f"%{query}%", f"%{query}%", max(int(limit), 0)],
                    )
                    columns = [desc[0] for desc in cursor.description or []]
                    rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]
        except Exception as exc:
            print(f"[{self.name}] Error searching PostgreSQL memory records: {exc}")
            return []

    def create_table_practice(self):
        """Create the table practice."""
        return self._build_operation_practice(
            operation_id="pool-create-table",
            name="Pool Create Table",
            description="Create a table in the PostgreSQL pool.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
                "schema": {"type": "object", "description": "Table schema definition."},
            },
            tags=["pool", "postgres", "storage", "create-table"],
            executor=lambda table_name, schema, **_: self._CreateTable(table_name, self._coerce_table_schema(schema)),
        )

    def table_exists_practice(self):
        """Return whether the table exists for practice."""
        return self._build_operation_practice(
            operation_id="pool-table-exists",
            name="Pool Table Exists",
            description="Check whether a PostgreSQL table exists.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
            },
            tags=["pool", "postgres", "storage", "table-exists"],
            executor=lambda table_name, **_: self._TableExists(table_name),
        )

    def insert_practice(self):
        """Handle insert practice for the Postgres pool."""
        return self._build_operation_practice(
            operation_id="pool-insert",
            name="Pool Insert",
            description="Insert or upsert one row in the PostgreSQL pool.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
                "data": {"type": "object", "description": "Row payload to persist."},
            },
            tags=["pool", "postgres", "storage", "insert"],
            executor=lambda table_name, data, **_: self._Insert(table_name, data),
        )

    def query_practice(self):
        """Query the practice."""
        return self._build_operation_practice(
            operation_id="pool-query",
            name="Pool Query",
            description="Execute a SQL query against the PostgreSQL pool.",
            parameters={
                "query": {"type": "string", "description": "SQL query string."},
                "params": {"type": "object", "description": "Optional query parameters."},
            },
            tags=["pool", "postgres", "storage", "query"],
            executor=lambda query, params=None, **_: self._Query(query, params),
        )

    def get_table_data_practice(self):
        """Return the table data practice."""
        return self._build_operation_practice(
            operation_id="pool-get-table-data",
            name="Pool Get Table Data",
            description="Read rows from a PostgreSQL table.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
                "id_or_where": {"type": "object", "description": "Optional id or equality filter."},
                "table_schema": {"type": "object", "description": "Optional table schema for decoding."},
            },
            tags=["pool", "postgres", "storage", "read"],
            executor=lambda table_name, id_or_where=None, table_schema=None, **_: self._GetTableData(
                table_name,
                id_or_where,
                self._coerce_table_schema(table_schema),
            ),
        )

    def connect_practice(self):
        """Connect the practice."""
        return self._build_operation_practice(
            operation_id="pool-connect",
            name="Pool Connect",
            description="Connect the PostgreSQL pool to its database.",
            parameters={},
            tags=["pool", "postgres", "storage", "connect"],
            executor=lambda **_: self.connect(),
        )

    def disconnect_practice(self):
        """Disconnect the practice."""
        return self._build_operation_practice(
            operation_id="pool-disconnect",
            name="Pool Disconnect",
            description="Close the PostgreSQL pool connection.",
            parameters={},
            tags=["pool", "postgres", "storage", "disconnect"],
            executor=lambda **_: self.disconnect(),
        )

    def store_memory_practice(self):
        """Handle store memory practice for the Postgres pool."""
        return self._build_operation_practice(
            operation_id="pool-store-memory",
            name="Pool Store Memory",
            description="Store one memory record in the PostgreSQL pool.",
            parameters={
                "content": {"type": "string", "description": "Memory content."},
                "memory_id": {"type": "string", "description": "Optional stable memory id."},
                "metadata": {"type": "object", "description": "Optional metadata payload."},
                "tags": {"type": "array", "description": "Optional string tags."},
                "memory_type": {"type": "string", "description": "Memory category."},
                "table_name": {"type": "string", "description": "Optional override table name."},
            },
            tags=["pool", "postgres", "memory", "store"],
            executor=lambda content, memory_id=None, metadata=None, tags=None, memory_type="text", table_name=None, **_: self.store_memory(
                content=content,
                memory_id=memory_id,
                metadata=metadata,
                tags=tags,
                memory_type=memory_type,
                table_name=table_name,
            ),
        )

    def search_memory_practice(self):
        """Search the memory practice."""
        return self._build_operation_practice(
            operation_id="pool-search-memory",
            name="Pool Search Memory",
            description="Search stored memory records in the PostgreSQL pool.",
            parameters={
                "query": {"type": "string", "description": "Case-insensitive search text."},
                "limit": {"type": "integer", "description": "Maximum number of matches."},
                "table_name": {"type": "string", "description": "Optional override table name."},
            },
            tags=["pool", "postgres", "memory", "search"],
            executor=lambda query, limit=10, table_name=None, **_: self.search_memory(
                query=query,
                limit=limit,
                table_name=table_name,
            ),
        )
