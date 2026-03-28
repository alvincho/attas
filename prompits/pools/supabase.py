import json
import os
import re
import time
import traceback
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Union
from prompits.core.pool import Pool, PoolCap, DataItem
from prompits.core.schema import TableSchema, DataType

try:
    from supabase import create_client, Client
except ImportError:
    Client = Any # Fallback for type hinting if package not installed
    print("Warning: supabase package not installed. SupabasePool will not work.")

class SupabasePool(Pool):
    """
    Pool implementation backed by Supabase/PostgREST.

    Provides table upsert/select and RPC execution through the Supabase client.
    Table creation is intentionally out-of-band (SQL migration/dashboard).
    """

    BATCH_UPSERT_RPC_BY_TABLE = {
        "agent_practices": "batch_upsert_agent_practices",
        "plaza_directory": "batch_upsert_plaza_directory",
        "pulse_pulser_pairs": "batch_upsert_pulse_pulser_pairs",
    }
    CONNECTIVITY_RETRY_BACKOFF_SEC = 120.0
    DEFAULT_HTTP_TIMEOUT_SEC = 8.0
    CONNECTIVITY_ERROR_MARKERS = (
        "nodename nor servname provided",
        "name or service not known",
        "temporary failure in name resolution",
        "failed to resolve host",
        "getaddrinfo failed",
        "network is unreachable",
        "connection refused",
        "connection reset by peer",
        "server disconnected without sending a response",
        "connect timeout",
        "timed out",
    )

    def __init__(self, name: str, url: str, key: str, description: str = None):
        super().__init__(
            name,
            description,
            capabilities=[PoolCap.TABLE, PoolCap.JSON, PoolCap.SEARCH, PoolCap.MEMORY],
        )
        self.url = url
        self.key = key
        self.supabase: Client = None
        self._unsupported_table_columns: Dict[str, set[str]] = {}
        self._observed_table_columns: Dict[str, set[str]] = {}
        self._create_table_notice_tables: set[str] = set()
        self._connectivity_retry_after: float = 0.0
        self._last_connectivity_error: str = ""
        self._last_connectivity_warning_at: float = 0.0
        # attempt connect
        self.connect()

    @classmethod
    def _http_timeout_seconds(cls) -> float:
        raw_value = str(
            os.getenv("PLAZA_SUPABASE_TIMEOUT_SEC")
            or os.getenv("SUPABASE_HTTP_TIMEOUT_SEC")
            or cls.DEFAULT_HTTP_TIMEOUT_SEC
        ).strip()
        try:
            timeout = float(raw_value)
        except (TypeError, ValueError):
            timeout = cls.DEFAULT_HTTP_TIMEOUT_SEC
        return max(3.0, timeout)

    @staticmethod
    def _normalize_url(value: Any) -> str:
        return str(value or "").strip().rstrip("/")

    @classmethod
    def _validated_url(cls, value: Any) -> str:
        normalized = cls._normalize_url(value)
        if not normalized:
            return ""
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return ""
        return normalized

    @classmethod
    def _is_connectivity_error(cls, error: Exception) -> bool:
        message = str(error or "").strip().lower()
        if not message:
            return False
        return any(marker in message for marker in cls.CONNECTIVITY_ERROR_MARKERS)

    def _connectivity_backoff_active(self) -> bool:
        retry_after = float(getattr(self, "_connectivity_retry_after", 0.0) or 0.0)
        return retry_after > time.time()

    def _record_connectivity_issue(self, error: Exception, *, context: str):
        message = str(error or "").strip() or error.__class__.__name__
        normalized_url = self._validated_url(self.url)
        parsed = urlparse(normalized_url) if normalized_url else None
        host = parsed.netloc if parsed else ""
        hint = (
            f" Check `SUPABASE_URL`/`PLAZA_SUPABASE_URL` and DNS reachability for '{host}'."
            if host
            else " Check `SUPABASE_URL`/`PLAZA_SUPABASE_URL`."
        )
        now = time.time()
        self.supabase = None
        self.is_connected = False
        self._connectivity_retry_after = now + float(self.CONNECTIVITY_RETRY_BACKOFF_SEC)
        if (
            message != getattr(self, "_last_connectivity_error", "")
            or (now - float(getattr(self, "_last_connectivity_warning_at", 0.0) or 0.0)) >= 30.0
        ):
            print(f"[{self.name}] Warning: Supabase connectivity failed while {context}: {message}.{hint}")
            self._last_connectivity_error = message
            self._last_connectivity_warning_at = now

    def _build_client_options(self):
        try:
            import httpx
            from supabase.lib.client_options import ClientOptions
        except Exception:
            return None

        timeout_seconds = self._http_timeout_seconds()
        try:
            httpx_client = httpx.Client(
                timeout=httpx.Timeout(timeout=timeout_seconds, connect=min(timeout_seconds, 5.0))
            )
            return ClientOptions(
                httpx_client=httpx_client,
                postgrest_client_timeout=timeout_seconds,
                storage_client_timeout=timeout_seconds,
                function_client_timeout=min(timeout_seconds, 10.0),
            )
        except Exception:
            return None

    def connect(self):
        normalized_url = self._validated_url(self.url)
        if not normalized_url or not str(self.key or "").strip():
            self.supabase = None
            self.is_connected = False
            self._connectivity_retry_after = time.time() + float(self.CONNECTIVITY_RETRY_BACKOFF_SEC)
            print(f"[{self.name}] Error connecting to Supabase: missing or invalid Supabase URL/key.")
            return False
        try:
            from supabase import create_client
            options = self._build_client_options()
            if options is None:
                self.supabase = create_client(normalized_url, self.key)
            else:
                self.supabase = create_client(normalized_url, self.key, options=options)
            self.url = normalized_url
            self.is_connected = True
            self._connectivity_retry_after = 0.0
            return True
        except Exception as e:
            self.supabase = None
            self.is_connected = False
            print(f"[{self.name}] Error connecting to Supabase: {e}")
            return False

    def disconnect(self):
        self.supabase = None
        self.is_connected = False
        return True
            
    def _ensure_connection(self):
        if self._connectivity_backoff_active():
            return False
        if not self.is_connected or not self.supabase:
            return self.connect()
        return True

    def _TableExists(self, table_name: str) -> bool:
        if self._connectivity_backoff_active():
            return True
        if not self._ensure_connection(): return False
        try:
            with self.lock:
                self.supabase.table(table_name).select("*").limit(0).execute()
                return True
        except Exception as e:
            if self._is_connectivity_error(e):
                self._record_connectivity_issue(e, context=f"checking table '{table_name}'")
                return True
            return False

    def _CreateTable(self, table_name: str, schema: TableSchema):
        # Supabase API does not support table creation via client standardly
        notice_tables = getattr(self, "_create_table_notice_tables", None)
        if notice_tables is None:
            notice_tables = set()
            self._create_table_notice_tables = notice_tables
        if table_name in notice_tables:
            return True
        notice_tables.add(table_name)
        print(f"[{self.name}] Info: Table '{table_name}' creation should be done via Supabase Dashboard or SQL Editor.")
        return True

    def _Insert(self, table_name: str, data: Dict[str, Any]):
        if not self._ensure_connection(): return False
        with self.lock:
            return self._upsert_with_schema_fallback(table_name, data, batch_label="data")

    def _InsertMany(self, table_name: str, data_list: List[Dict[str, Any]]):
        if not data_list:
            return True
        if not self._ensure_connection():
            return False
        with self.lock:
            batch_rpc = self.BATCH_UPSERT_RPC_BY_TABLE.get(table_name)
            if batch_rpc:
                try:
                    self.supabase.rpc(batch_rpc, {"entries": data_list}).execute()
                    return True
                except Exception as e:
                    if self._is_connectivity_error(e):
                        self._record_connectivity_issue(e, context=f"batch upserting into '{table_name}'")
                        return False
                    print(
                        f"[{self.name}] Warning: batch RPC '{batch_rpc}' failed for '{table_name}'; "
                        f"falling back to table upsert: {e}"
                    )
            return self._upsert_with_schema_fallback(table_name, data_list, batch_label="batch data")

    @staticmethod
    def _extract_missing_column_name(error: Exception) -> Optional[str]:
        message = str(error or "")
        match = re.search(r"Could not find the '([^']+)' column", message)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _drop_columns_from_payload(payload: Union[Dict[str, Any], List[Dict[str, Any]]], columns: set[str]) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        if isinstance(payload, dict):
            return {key: value for key, value in payload.items() if key not in columns}
        return [
            {key: value for key, value in row.items() if key not in columns}
            for row in payload
            if isinstance(row, dict)
        ]

    @staticmethod
    def _payload_columns(payload: Union[Dict[str, Any], List[Dict[str, Any]]]) -> set[str]:
        if isinstance(payload, dict):
            return set(payload.keys())
        columns: set[str] = set()
        for row in payload:
            if isinstance(row, dict):
                columns.update(row.keys())
        return columns

    def _get_observed_table_columns(self, table_name: str) -> set[str]:
        observed_table_columns = getattr(self, "_observed_table_columns", None)
        if observed_table_columns is None:
            observed_table_columns = {}
            self._observed_table_columns = observed_table_columns
        if table_name in observed_table_columns:
            return observed_table_columns[table_name]
        try:
            response = self.supabase.table(table_name).select("*").limit(1).execute()
            rows = getattr(response, "data", None)
            if isinstance(rows, list) and rows and isinstance(rows[0], dict):
                observed_table_columns[table_name] = set(rows[0].keys())
            else:
                observed_table_columns[table_name] = set()
        except Exception:
            observed_table_columns[table_name] = set()
        return observed_table_columns[table_name]

    def _upsert_with_schema_fallback(self, table_name: str, payload: Union[Dict[str, Any], List[Dict[str, Any]]], *, batch_label: str) -> bool:
        unsupported_table_columns = getattr(self, "_unsupported_table_columns", None)
        if unsupported_table_columns is None:
            unsupported_table_columns = {}
            self._unsupported_table_columns = unsupported_table_columns

        removed_columns: set[str] = set(unsupported_table_columns.get(table_name, set()))
        observed_columns = self._get_observed_table_columns(table_name)
        if observed_columns:
            inferred_missing_columns = self._payload_columns(payload) - observed_columns
            if inferred_missing_columns:
                removed_columns.update(inferred_missing_columns)
                unsupported_table_columns[table_name] = set(removed_columns)
        current_payload: Union[Dict[str, Any], List[Dict[str, Any]]] = (
            self._drop_columns_from_payload(payload, removed_columns)
            if removed_columns
            else payload
        )

        while True:
            try:
                self.supabase.table(table_name).upsert(current_payload).execute()
                if removed_columns:
                    unsupported_table_columns[table_name] = set(removed_columns)
                    print(f"[{self.name}] Warning: upsert to '{table_name}' skipped unsupported columns: {sorted(removed_columns)}")
                return True
            except Exception as e:
                if self._is_connectivity_error(e):
                    self._record_connectivity_issue(e, context=f"upserting into '{table_name}'")
                    return False
                missing_column = self._extract_missing_column_name(e)
                if missing_column and missing_column not in removed_columns:
                    removed_columns.add(missing_column)
                    current_payload = self._drop_columns_from_payload(payload, removed_columns)
                    unsupported_table_columns[table_name] = set(removed_columns)
                    continue
                print(f"[{self.name}] Error inserting {batch_label}: {e}")
                return False

    def _Query(self, query: str, params: Union[List[Any], Dict[str, Any]]=None):
        """Execute Supabase RPC where `query` is treated as function name."""
        # query is treated as RPC function name for Supabase
        if not self._ensure_connection(): return []
        try:
            with self.lock:
                if params:
                    if isinstance(params, list):
                        print(f"[{self.name}] Warning: RPC params as list might not work effectively unless function expects array.")
                    res = self.supabase.rpc(query, params).execute()
                else:
                    res = self.supabase.rpc(query).execute()
                return res.data
        except Exception as e:
            if self._is_connectivity_error(e):
                self._record_connectivity_issue(e, context=f"executing RPC '{query}'")
                return []
            print(f"[{self.name}] Error executing RPC '{query}': {e}")
            return []

    def _GetTableData(self, table_name: str, id_or_where: Union[str, Dict]=None, table_schema: TableSchema=None) -> List[Dict[str, Any]]:
        if not self._ensure_connection(): return []
        try:
            with self.lock:
                query = self.supabase.table(table_name).select("*")
                if id_or_where:
                    if isinstance(id_or_where, str):
                        query = query.eq('id', id_or_where)
                    elif isinstance(id_or_where, dict):
                        for k, v in id_or_where.items():
                            query = query.eq(k, v)

                res = query.execute()
                return res.data
        except Exception as e:
            if self._is_connectivity_error(e):
                self._record_connectivity_issue(e, context=f"reading from '{table_name}'")
                return []
            print(f"[{self.name}] Error getting table data: {e}")
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
        memory_table = table_name or self.MEMORY_TABLE
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
        if not query:
            return []
        memory_table = table_name or self.MEMORY_TABLE
        rows = self._GetTableData(memory_table) or []
        lowered = query.lower()
        matches = [row for row in rows if lowered in self._memory_search_text(row)]
        return matches[: max(int(limit), 0)]

    def create_table_practice(self):
        return self._build_operation_practice(
            operation_id="pool-create-table",
            name="Pool Create Table",
            description="Request table creation for the Supabase pool.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
                "schema": {"type": "object", "description": "Table schema definition."},
            },
            tags=["pool", "supabase", "storage", "create-table"],
            executor=lambda table_name, schema, **_: self._CreateTable(table_name, self._coerce_table_schema(schema)),
        )

    def table_exists_practice(self):
        return self._build_operation_practice(
            operation_id="pool-table-exists",
            name="Pool Table Exists",
            description="Check whether a Supabase table exists.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
            },
            tags=["pool", "supabase", "storage", "table-exists"],
            executor=lambda table_name, **_: self._TableExists(table_name),
        )

    def insert_practice(self):
        return self._build_operation_practice(
            operation_id="pool-insert",
            name="Pool Insert",
            description="Upsert one row through the Supabase pool.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
                "data": {"type": "object", "description": "Row payload to persist."},
            },
            tags=["pool", "supabase", "storage", "insert"],
            executor=lambda table_name, data, **_: self._Insert(table_name, data),
        )

    def query_practice(self):
        return self._build_operation_practice(
            operation_id="pool-query",
            name="Pool Query",
            description="Execute an RPC-style query through the Supabase pool.",
            parameters={
                "query": {"type": "string", "description": "RPC function name."},
                "params": {"type": "object", "description": "Optional RPC parameters."},
            },
            tags=["pool", "supabase", "storage", "query"],
            executor=lambda query, params=None, **_: self._Query(query, params),
        )

    def get_table_data_practice(self):
        return self._build_operation_practice(
            operation_id="pool-get-table-data",
            name="Pool Get Table Data",
            description="Read rows from a Supabase table.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
                "id_or_where": {"type": "object", "description": "Optional id or equality filter."},
                "table_schema": {"type": "object", "description": "Optional table schema for decoding."},
            },
            tags=["pool", "supabase", "storage", "read"],
            executor=lambda table_name, id_or_where=None, table_schema=None, **_: self._GetTableData(
                table_name,
                id_or_where,
                self._coerce_table_schema(table_schema),
            ),
        )

    def connect_practice(self):
        return self._build_operation_practice(
            operation_id="pool-connect",
            name="Pool Connect",
            description="Connect the Supabase pool client.",
            parameters={},
            tags=["pool", "supabase", "storage", "connect"],
            executor=lambda **_: self.connect(),
        )

    def disconnect_practice(self):
        return self._build_operation_practice(
            operation_id="pool-disconnect",
            name="Pool Disconnect",
            description="Drop the current Supabase pool client connection.",
            parameters={},
            tags=["pool", "supabase", "storage", "disconnect"],
            executor=lambda **_: self.disconnect(),
        )

    def store_memory_practice(self):
        return self._build_operation_practice(
            operation_id="pool-store-memory",
            name="Pool Store Memory",
            description="Store one memory record in the Supabase pool.",
            parameters={
                "content": {"type": "string", "description": "Memory content."},
                "memory_id": {"type": "string", "description": "Optional stable memory id."},
                "metadata": {"type": "object", "description": "Optional metadata payload."},
                "tags": {"type": "array", "description": "Optional string tags."},
                "memory_type": {"type": "string", "description": "Memory category."},
                "table_name": {"type": "string", "description": "Optional override table name."},
            },
            tags=["pool", "supabase", "memory", "store"],
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
        return self._build_operation_practice(
            operation_id="pool-search-memory",
            name="Pool Search Memory",
            description="Search stored memory records in the Supabase pool.",
            parameters={
                "query": {"type": "string", "description": "Case-insensitive search text."},
                "limit": {"type": "integer", "description": "Maximum number of matches."},
                "table_name": {"type": "string", "description": "Optional override table name."},
            },
            tags=["pool", "supabase", "memory", "search"],
            executor=lambda query, limit=10, table_name=None, **_: self.search_memory(
                query=query,
                limit=limit,
                table_name=table_name,
            ),
        )
