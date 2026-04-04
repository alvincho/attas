"""
SQLite module for `prompits.pools.sqlite`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the pools package implements
storage adapters and pool-specific helpers.

Core types exposed here include `SQLitePool`, which carry the main behavior or state
managed by this module.
"""

import sqlite3
import json
import os
import traceback
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import uuid
from prompits.core.pool import Pool, PoolCap
from prompits.core.schema import DataType, TableSchema

class SQLitePool(Pool):
    """
    Pool implementation backed by SQLite.

    Uses WAL mode and busy timeout for better multi-thread/process behavior in
    local agent environments.
    """

    def __init__(self, name: str, description: str, db_path: str):
        """Initialize the sq lite pool."""
        super().__init__(
            name,
            description,
            capabilities=[PoolCap.TABLE, PoolCap.JSON, PoolCap.SEARCH, PoolCap.MEMORY],
        )
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect()

    def _prepare_db_path(self):
        """Internal helper to prepare the database path."""
        db_path = str(self.db_path or "").strip()
        if not db_path or db_path == ":memory:" or db_path.startswith("file:"):
            return
        parent_dir = os.path.dirname(os.path.abspath(db_path))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

    def connect(self):
        """Connect the value."""
        try:
            self._prepare_db_path()
            self.conn = sqlite3.connect(
                self.db_path,
                timeout=60.0,
                isolation_level='IMMEDIATE',
                check_same_thread=False
            )
            self.conn.execute('PRAGMA journal_mode=WAL')
            self.conn.execute('PRAGMA busy_timeout=30000')
            self.conn.execute('PRAGMA foreign_keys=ON')
            self.cursor = self.conn.cursor()
            self.is_connected = True
            return True
        except Exception as e:
            self.conn = None
            self.cursor = None
            self.is_connected = False
            print(f"Error connecting to database '{self.db_path}': {e}")
            return False

    def disconnect(self):
        """Disconnect the value."""
        try:
            if self.conn:
                self.conn.close()
            self.conn = None
            self.cursor = None
            self.is_connected = False
            return True
        except Exception as e:
            print(f"Error disconnecting from database: {e}")
            return False

    def _ensure_connection(self):
        """Validate/recover the SQLite connection before operations."""
        if not self.is_connected or not self.conn:
            return self.connect()
        try:
            self.conn.execute("SELECT 1")
            return True
        except:
            return self.connect()

    def _get_sqlite_type(self, column_type: DataType) -> str:
        """Internal helper to return the SQLite type."""
        type_map = {
            DataType.STRING: 'TEXT',
            DataType.INTEGER: 'INTEGER',
            DataType.FLOAT: 'REAL',
            DataType.BOOLEAN: 'INTEGER',
            DataType.DATETIME: 'TIMESTAMP',
            DataType.JSON: 'TEXT'
        }
        return type_map.get(column_type, 'TEXT')

    def _TableExists(self, table_name: str) -> bool:
        """Return whether the table exists for value."""
        try:
            with self.lock:
                if not self._ensure_connection() or not self.conn:
                    return False
                cursor = self.conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                return bool(cursor.fetchone())
        except Exception as e:
            print(f"Error checking table: {e}")
            return False

    def _CreateTable(self, table_name: str, schema: TableSchema):
        """Internal helper to create the table."""
        try:
            with self.lock:
                if not self._ensure_connection() or not self.conn:
                    return False
                column_definitions = []
                for column_name, column_spec in schema.rowSchema.columns.items():
                    explicit_sql_type = str(column_spec.get("sql_type") or "").strip()
                    if explicit_sql_type:
                        sqlite_type = explicit_sql_type
                    else:
                        col_type = DataType.from_string(column_spec["type"])
                        sqlite_type = self._get_sqlite_type(col_type)
                    column_definitions.append(f"{column_name} {sqlite_type}")

                primary_key_columns = [
                    column
                    for column in getattr(schema, "primary_key", []) or []
                    if column in schema.rowSchema.columns
                ]
                unique_constraints = []
                for constraint in getattr(schema, "unique_constraints", []) or []:
                    unique_columns = [column for column in constraint if column in schema.rowSchema.columns]
                    if unique_columns:
                        unique_constraints.append(f"UNIQUE ({', '.join(unique_columns)})")

                foreign_keys = []
                for foreign_key in getattr(schema, "foreign_keys", []) or []:
                    foreign_key_columns = [column for column in foreign_key.get("columns", []) if column in schema.rowSchema.columns]
                    references = foreign_key.get("references") if isinstance(foreign_key.get("references"), dict) else {}
                    reference_table = str(references.get("table") or "").strip()
                    reference_columns = [column for column in references.get("columns", []) if column]
                    if not foreign_key_columns or not reference_table or not reference_columns or len(foreign_key_columns) != len(reference_columns):
                        continue
                    clause = (
                        f"FOREIGN KEY ({', '.join(foreign_key_columns)}) "
                        f"REFERENCES {reference_table} ({', '.join(reference_columns)})"
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
                    table_parts.append(f"PRIMARY KEY ({', '.join(primary_key_columns)})")
                table_parts.extend(unique_constraints)
                table_parts.extend(foreign_keys)
                create_table_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(table_parts)})"
                cursor = self.conn.cursor()
                cursor.execute(create_table_sql)
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Error creating table: {e}")
            return False

    def _Insert(self, table_name: str, data: Dict[str, Any]):
        """Internal helper for insert."""
        try:
            with self.lock:
                if not self._ensure_connection() or not self.conn:
                    return False
                columns = list(data.keys())
                values = list(data.values())
                placeholders = ', '.join(['?' for _ in columns])
                columns_str = ', '.join(columns)

                serialized_values = []
                for v in values:
                    if isinstance(v, (dict, list)):
                        serialized_values.append(json.dumps(v))
                    else:
                        serialized_values.append(v)

                sql = self._build_insert_sql(table_name, columns)
                cursor = self.conn.cursor()
                cursor.execute(sql, serialized_values)
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Error inserting data: {e}")
            traceback.print_exc()
            return False

    def _InsertMany(self, table_name: str, data_list: List[Dict[str, Any]]):
        """Internal helper for insert many."""
        try:
            if not data_list:
                return True
            with self.lock:
                if not self._ensure_connection() or not self.conn:
                    return False
                columns = list(data_list[0].keys())
                placeholders = ', '.join(['?' for _ in columns])
                columns_str = ', '.join(columns)

                serialized_rows = []
                for data in data_list:
                    row = []
                    for column in columns:
                        value = data.get(column)
                        if isinstance(value, (dict, list)):
                            row.append(json.dumps(value))
                        else:
                            row.append(value)
                    serialized_rows.append(row)

                sql = self._build_insert_sql(table_name, columns)
                cursor = self.conn.cursor()
                cursor.executemany(sql, serialized_rows)
                self.conn.commit()
                return True
        except Exception as e:
            print(f"Error inserting batch data: {e}")
            traceback.print_exc()
            return False

    def _Query(self, query: str, params: List[Any]=None):
        """Internal helper to query the value."""
        try:
            with self.lock:
                if not self._ensure_connection() or not self.conn:
                    return []
                cursor = self.conn.cursor()
                cursor.execute(query, params or [])
                return cursor.fetchall()
        except Exception as e:
            print(f"Error querying: {e}")
            return []

    def _GetTableData(self, table_name: str, id_or_where: Union[str, Dict]=None, table_schema: TableSchema=None) -> List[Dict[str, Any]]:
        """Internal helper to return the table data."""
        try:
            with self.lock:
                if not self._ensure_connection() or not self.conn:
                    return []
                if not id_or_where:
                    sql = f"SELECT * FROM {table_name}"
                    params = []
                elif isinstance(id_or_where, str):
                    sql = f"SELECT * FROM {table_name} WHERE id = ?"
                    params = [id_or_where]
                elif isinstance(id_or_where, dict):
                    conditions = []
                    params = []
                    for k, v in id_or_where.items():
                        conditions.append(f"{k} = ?")
                        params.append(v)
                    where_clause = " AND ".join(conditions)
                    sql = f"SELECT * FROM {table_name} WHERE {where_clause}"

                cursor = self.conn.cursor()
                cursor.execute(sql, params)
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
            
            results = []
            for row in rows:
                row_dict = dict(zip(columns, row))
                # Auto-convert JSON/types
                for k, v in row_dict.items():
                    if isinstance(v, str):
                        if table_schema and k in table_schema.rowSchema.columns:
                            col_type = DataType.from_string(table_schema.rowSchema.columns[k]["type"])
                            if col_type == DataType.JSON or col_type == DataType.OBJECT or col_type == DataType.ARRAY:
                                try:
                                    row_dict[k] = json.loads(v)
                                except: pass
                        else:
                             # Auto-detect JSON
                             if (v.startswith('{') and v.endswith('}')) or (v.startswith('[') and v.endswith(']')):
                                 try:
                                     row_dict[k] = json.loads(v)
                                 except: pass
                results.append(row_dict)
            return results
        except Exception as e:
            print(f"GetTableData Error: {e}")
            return []

    def _table_unique_conflict_targets(self, table_name: str) -> List[List[str]]:
        """Internal helper to return the table unique conflict targets."""
        if not self.conn:
            return []
        cursor = self.conn.cursor()
        candidates: List[List[str]] = []

        cursor.execute(f"PRAGMA table_info('{table_name}')")
        pk_rows = cursor.fetchall()
        pk_columns = [
            row[1]
            for row in sorted((row for row in pk_rows if len(row) > 5 and int(row[5] or 0) > 0), key=lambda item: int(item[5] or 0))
            if row[1]
        ]
        if pk_columns:
            candidates.append(pk_columns)

        cursor.execute(f"PRAGMA index_list('{table_name}')")
        for index_row in cursor.fetchall():
            if len(index_row) < 3 or not int(index_row[2] or 0):
                continue
            if len(index_row) > 4 and int(index_row[4] or 0):
                continue
            index_name = index_row[1]
            cursor.execute(f"PRAGMA index_info('{index_name}')")
            index_columns = [row[2] for row in cursor.fetchall() if len(row) > 2 and row[2]]
            if index_columns:
                candidates.append(index_columns)

        seen = set()
        normalized: List[List[str]] = []
        for candidate in candidates:
            key = tuple(candidate)
            if not candidate or key in seen:
                continue
            seen.add(key)
            normalized.append(candidate)
        return normalized

    def _build_insert_sql(self, table_name: str, columns: List[str]) -> str:
        """Internal helper to build the insert SQL."""
        placeholders = ', '.join(['?' for _ in columns])
        columns_str = ', '.join(columns)
        candidates = self._table_unique_conflict_targets(table_name)
        matching_candidates = [candidate for candidate in candidates if all(column in columns for column in candidate)]
        if matching_candidates:
            conflict_columns = sorted(
                matching_candidates,
                key=lambda candidate: (len(candidate), tuple(column != "id" for column in candidate)),
                reverse=True,
            )[0]
            update_columns = [column for column in columns if column not in conflict_columns]
            if update_columns:
                updates = ', '.join(f"{column}=excluded.{column}" for column in update_columns)
                return (
                    f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({', '.join(conflict_columns)}) DO UPDATE SET {updates}"
                )
            return (
                f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders}) "
                f"ON CONFLICT ({', '.join(conflict_columns)}) DO NOTHING"
            )
        return f"INSERT INTO {table_name} ({columns_str}) VALUES ({placeholders})"

    def store_memory(
        self,
        content: Any,
        memory_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        memory_type: str = "text",
        table_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle store memory for the sq lite pool."""
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
        with self.lock:
            self._ensure_connection()
            like = f"%{query.lower()}%"
            sql = (
                f"SELECT * FROM {memory_table} "
                "WHERE lower(content) LIKE ? OR lower(metadata) LIKE ? OR lower(tags) LIKE ? "
                "ORDER BY updated_at DESC LIMIT ?"
            )
            cursor = self.conn.cursor()
            cursor.execute(sql, [like, like, like, max(int(limit), 0)])
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
        results = []
        for row in rows:
            row_dict = dict(zip(columns, row))
            for key in ("metadata", "tags"):
                value = row_dict.get(key)
                if isinstance(value, str):
                    try:
                        row_dict[key] = json.loads(value)
                    except Exception:
                        pass
            results.append(row_dict)
        return results

    def create_table_practice(self):
        """Create the table practice."""
        return self._build_operation_practice(
            operation_id="pool-create-table",
            name="Pool Create Table",
            description="Create a table in the SQLite pool.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
                "schema": {"type": "object", "description": "Table schema definition."},
            },
            tags=["pool", "sqlite", "storage", "create-table"],
            executor=lambda table_name, schema, **_: self._CreateTable(table_name, self._coerce_table_schema(schema)),
        )

    def table_exists_practice(self):
        """Return whether the table exists for practice."""
        return self._build_operation_practice(
            operation_id="pool-table-exists",
            name="Pool Table Exists",
            description="Check whether a SQLite table exists.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
            },
            tags=["pool", "sqlite", "storage", "table-exists"],
            executor=lambda table_name, **_: self._TableExists(table_name),
        )

    def insert_practice(self):
        """Handle insert practice for the sq lite pool."""
        return self._build_operation_practice(
            operation_id="pool-insert",
            name="Pool Insert",
            description="Insert or replace one row in the SQLite pool.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
                "data": {"type": "object", "description": "Row payload to persist."},
            },
            tags=["pool", "sqlite", "storage", "insert"],
            executor=lambda table_name, data, **_: self._Insert(table_name, data),
        )

    def query_practice(self):
        """Query the practice."""
        return self._build_operation_practice(
            operation_id="pool-query",
            name="Pool Query",
            description="Execute a SQL query against the SQLite pool.",
            parameters={
                "query": {"type": "string", "description": "SQL query string."},
                "params": {"type": "object", "description": "Optional query parameters."},
            },
            tags=["pool", "sqlite", "storage", "query"],
            executor=lambda query, params=None, **_: self._Query(query, params),
        )

    def get_table_data_practice(self):
        """Return the table data practice."""
        return self._build_operation_practice(
            operation_id="pool-get-table-data",
            name="Pool Get Table Data",
            description="Read rows from a SQLite table.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
                "id_or_where": {"type": "object", "description": "Optional id or equality filter."},
                "table_schema": {"type": "object", "description": "Optional table schema for decoding."},
            },
            tags=["pool", "sqlite", "storage", "read"],
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
            description="Connect the SQLite pool to its database file.",
            parameters={},
            tags=["pool", "sqlite", "storage", "connect"],
            executor=lambda **_: self.connect(),
        )

    def disconnect_practice(self):
        """Disconnect the practice."""
        return self._build_operation_practice(
            operation_id="pool-disconnect",
            name="Pool Disconnect",
            description="Close the SQLite pool database connection.",
            parameters={},
            tags=["pool", "sqlite", "storage", "disconnect"],
            executor=lambda **_: self.disconnect(),
        )

    def store_memory_practice(self):
        """Handle store memory practice for the sq lite pool."""
        return self._build_operation_practice(
            operation_id="pool-store-memory",
            name="Pool Store Memory",
            description="Store one memory record in the SQLite pool.",
            parameters={
                "content": {"type": "string", "description": "Memory content."},
                "memory_id": {"type": "string", "description": "Optional stable memory id."},
                "metadata": {"type": "object", "description": "Optional metadata payload."},
                "tags": {"type": "array", "description": "Optional string tags."},
                "memory_type": {"type": "string", "description": "Memory category."},
                "table_name": {"type": "string", "description": "Optional override table name."},
            },
            tags=["pool", "sqlite", "memory", "store"],
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
            description="Search stored memory records in the SQLite pool.",
            parameters={
                "query": {"type": "string", "description": "Case-insensitive search text."},
                "limit": {"type": "integer", "description": "Maximum number of matches."},
                "table_name": {"type": "string", "description": "Optional override table name."},
            },
            tags=["pool", "sqlite", "memory", "search"],
            executor=lambda query, limit=10, table_name=None, **_: self.search_memory(
                query=query,
                limit=limit,
                table_name=table_name,
            ),
        )
