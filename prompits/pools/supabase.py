import json
import re
import traceback
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

    def __init__(self, name: str, url: str, key: str, description: str = None):
        super().__init__(
            name,
            description,
            capabilities=[PoolCap.TABLE, PoolCap.JSON, PoolCap.SEARCH, PoolCap.MEMORY],
        )
        self.url = url
        self.key = key
        self.supabase: Client = None
        # attempt connect
        self.connect()

    def connect(self):
        try:
            from supabase import create_client
            self.supabase = create_client(self.url, self.key)
            self.is_connected = True
            return True
        except Exception as e:
            print(f"Error connecting to Supabase: {e}")
            return False

    def disconnect(self):
        self.supabase = None
        self.is_connected = False
        return True
            
    def _ensure_connection(self):
        if not self.is_connected or not self.supabase:
            return self.connect()
        return True

    def _TableExists(self, table_name: str) -> bool:
        if not self._ensure_connection(): return False
        try:
            with self.lock:
                self.supabase.table(table_name).select("*").limit(0).execute()
                return True
        except:
            return False

    def _CreateTable(self, table_name: str, schema: TableSchema):
        # Supabase API does not support table creation via client standardly
        # Log info
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

    def _upsert_with_schema_fallback(self, table_name: str, payload: Union[Dict[str, Any], List[Dict[str, Any]]], *, batch_label: str) -> bool:
        removed_columns: set[str] = set()
        current_payload: Union[Dict[str, Any], List[Dict[str, Any]]] = payload

        while True:
            try:
                self.supabase.table(table_name).upsert(current_payload).execute()
                if removed_columns:
                    print(f"[{self.name}] Warning: upsert to '{table_name}' skipped unsupported columns: {sorted(removed_columns)}")
                return True
            except Exception as e:
                missing_column = self._extract_missing_column_name(e)
                if missing_column and missing_column not in removed_columns:
                    removed_columns.add(missing_column)
                    current_payload = self._drop_columns_from_payload(payload, removed_columns)
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
