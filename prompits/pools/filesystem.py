"""
Filesystem module for `prompits.pools.filesystem`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the pools package implements
storage adapters and pool-specific helpers.

Core types exposed here include `FileSystemPool`, which carry the main behavior or state
managed by this module.
"""

import os
import json
import shutil
import uuid
from urllib.parse import quote
from typing import Dict, Any, List, Optional, Union
from prompits.core.pool import Pool, PoolCap
from prompits.core.schema import TableSchema

class FileSystemPool(Pool):
    """
    Pool implementation backed by filesystem directories and JSON files.

    Each table is a directory, each row is one JSON file keyed by `id`.
    This backend favors transparency and portability over query performance.
    """

    def __init__(self, name: str, description: str, root_path: str):
        """Initialize the file system pool."""
        super().__init__(
            name,
            description,
            capabilities=[PoolCap.TABLE, PoolCap.JSON, PoolCap.BLOB, PoolCap.SEARCH, PoolCap.MEMORY],
        )
        self.root_path = root_path
        self.connect()

    def connect(self):
        """Connect the value."""
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path, exist_ok=True)
        self.is_connected = True
        return True

    def disconnect(self):
        """Disconnect the value."""
        self.is_connected = False
        return True

    def _get_table_path(self, table_name: str) -> str:
        """Return on-disk directory path for a logical table."""
        return os.path.join(self.root_path, table_name)

    def _safe_item_id(self, item_id: str) -> str:
        # Encode IDs (e.g., containing URLs) into filesystem-safe filenames.
        """Internal helper for safe item ID."""
        return quote(str(item_id), safe="")

    def _TableExists(self, table_name: str) -> bool:
        """Return whether the table exists for value."""
        with self.lock:
            return os.path.exists(self._get_table_path(table_name))

    def _CreateTable(self, table_name: str, schema: TableSchema):
        """Internal helper to create the table."""
        with self.lock:
            table_path = self._get_table_path(table_name)
            if not os.path.exists(table_path):
                os.makedirs(table_path, exist_ok=True)
                with open(os.path.join(table_path, "_schema.json"), 'w') as f:
                    json.dump(schema.schema, f, indent=2)
                return True
            return True

    def _Insert(self, table_name: str, data: Dict[str, Any]):
        """Internal helper for insert."""
        with self.lock:
            table_path = self._get_table_path(table_name)
            if not os.path.exists(table_path):
                print(f"[{self.name}] Table {table_name} does not exist.")
                return False

            item_id = data.get("id")
            if not item_id:
                item_id = str(uuid.uuid4())
                data["id"] = item_id

            file_path = os.path.join(table_path, f"{self._safe_item_id(item_id)}.json")
            try:
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2)
                return True
            except Exception as e:
                print(f"[{self.name}] Error writing file: {e}")
                return False

    def _InsertMany(self, table_name: str, data_list: List[Dict[str, Any]]):
        """Internal helper for insert many."""
        for data in data_list or []:
            if not self._Insert(table_name, data):
                return False
        return True

    def _Query(self, query: str, params: Union[List[Any], Dict[str, Any]]=None):
        # FileSystemPool doesn't support complex queries easily.
        # Maybe basic listing?
        """Internal helper to query the value."""
        print(f"[{self.name}] Query not standardly supported in FileSystemPool. Use GetTableData.")
        return []

    def _GetTableData(self, table_name: str, id_or_where: Union[str, Dict]=None, table_schema: TableSchema=None) -> List[Dict[str, Any]]:
        """Internal helper to return the table data."""
        with self.lock:
            table_path = self._get_table_path(table_name)
            if not os.path.exists(table_path):
                return []

            results = []

            if isinstance(id_or_where, str):
                file_path = os.path.join(table_path, f"{self._safe_item_id(id_or_where)}.json")
                if os.path.exists(file_path):
                    try:
                        with open(file_path, 'r') as f:
                            results.append(json.load(f))
                    except Exception:
                        pass
                return results

            for filename in os.listdir(table_path):
                if not filename.endswith(".json") or filename.startswith("_"):
                    continue
                try:
                    with open(os.path.join(table_path, filename), 'r') as f:
                        item = json.load(f)

                        if isinstance(id_or_where, dict):
                            match = True
                            for k, v in id_or_where.items():
                                if item.get(k) != v:
                                    match = False
                                    break
                            if match:
                                results.append(item)
                        else:
                            results.append(item)
                except Exception:
                    pass

            return results

    def store_memory(
        self,
        content: Any,
        memory_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        memory_type: str = "text",
        table_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handle store memory for the file system pool."""
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
        rows = self._GetTableData(memory_table) if self._TableExists(memory_table) else []
        lowered = query.lower()
        matches = [row for row in rows if lowered in self._memory_search_text(row)]
        return matches[: max(int(limit), 0)]

    def create_table_practice(self):
        """Create the table practice."""
        return self._build_operation_practice(
            operation_id="pool-create-table",
            name="Pool Create Table",
            description="Create a table directory in the filesystem pool.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
                "schema": {"type": "object", "description": "Table schema definition."},
            },
            examples=[{"table_name": "agent_practices", "schema": {"name": "agent_practices"}}],
            tags=["pool", "filesystem", "storage", "create-table"],
            executor=lambda table_name, schema, **_: self._CreateTable(table_name, self._coerce_table_schema(schema)),
        )

    def table_exists_practice(self):
        """Return whether the table exists for practice."""
        return self._build_operation_practice(
            operation_id="pool-table-exists",
            name="Pool Table Exists",
            description="Check whether a filesystem-backed table exists.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
            },
            tags=["pool", "filesystem", "storage", "table-exists"],
            executor=lambda table_name, **_: self._TableExists(table_name),
        )

    def insert_practice(self):
        """Handle insert practice for the file system pool."""
        return self._build_operation_practice(
            operation_id="pool-insert",
            name="Pool Insert",
            description="Insert or replace one JSON row in the filesystem pool.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
                "data": {"type": "object", "description": "Row payload to persist."},
            },
            tags=["pool", "filesystem", "storage", "insert"],
            executor=lambda table_name, data, **_: self._Insert(table_name, data),
        )

    def query_practice(self):
        """Query the practice."""
        return self._build_operation_practice(
            operation_id="pool-query",
            name="Pool Query",
            description="Execute a query against the filesystem pool adapter.",
            parameters={
                "query": {"type": "string", "description": "Query or operation name."},
                "params": {"type": "object", "description": "Optional query parameters."},
            },
            tags=["pool", "filesystem", "storage", "query"],
            executor=lambda query, params=None, **_: self._Query(query, params),
        )

    def get_table_data_practice(self):
        """Return the table data practice."""
        return self._build_operation_practice(
            operation_id="pool-get-table-data",
            name="Pool Get Table Data",
            description="Read rows from a filesystem-backed table.",
            parameters={
                "table_name": {"type": "string", "description": "Logical table name."},
                "id_or_where": {"type": "object", "description": "Optional id or equality filter."},
                "table_schema": {"type": "object", "description": "Optional table schema for decoding."},
            },
            tags=["pool", "filesystem", "storage", "read"],
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
            description="Initialize the filesystem pool root.",
            parameters={},
            tags=["pool", "filesystem", "storage", "connect"],
            executor=lambda **_: self.connect(),
        )

    def disconnect_practice(self):
        """Disconnect the practice."""
        return self._build_operation_practice(
            operation_id="pool-disconnect",
            name="Pool Disconnect",
            description="Mark the filesystem pool as disconnected.",
            parameters={},
            tags=["pool", "filesystem", "storage", "disconnect"],
            executor=lambda **_: self.disconnect(),
        )

    def store_memory_practice(self):
        """Handle store memory practice for the file system pool."""
        return self._build_operation_practice(
            operation_id="pool-store-memory",
            name="Pool Store Memory",
            description="Store one memory record in the filesystem pool.",
            parameters={
                "content": {"type": "string", "description": "Memory content."},
                "memory_id": {"type": "string", "description": "Optional stable memory id."},
                "metadata": {"type": "object", "description": "Optional metadata payload."},
                "tags": {"type": "array", "description": "Optional string tags."},
                "memory_type": {"type": "string", "description": "Memory category."},
                "table_name": {"type": "string", "description": "Optional override table name."},
            },
            tags=["pool", "filesystem", "memory", "store"],
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
            description="Search stored memory records in the filesystem pool.",
            parameters={
                "query": {"type": "string", "description": "Case-insensitive search text."},
                "limit": {"type": "integer", "description": "Maximum number of matches."},
                "table_name": {"type": "string", "description": "Optional override table name."},
            },
            tags=["pool", "filesystem", "memory", "search"],
            executor=lambda query, limit=10, table_name=None, **_: self.search_memory(
                query=query,
                limit=limit,
                table_name=table_name,
            ),
        )
