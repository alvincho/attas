"""
Regression tests for Plaza directory entry UI.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down generic Plaza directory
behavior without depending on higher-level product terms.
"""

import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.core.plaza import PlazaAgent
from prompits.core.pool import Pool, PoolCap
from prompits.practices.plaza import PlazaPractice


class InMemoryPool(Pool):
    """Represent an in memory pool."""

    def __init__(self):
        """Initialize the in memory pool."""
        super().__init__(
            "mem",
            "memory pool",
            capabilities=[PoolCap.TABLE, PoolCap.JSON, PoolCap.SEARCH, PoolCap.MEMORY],
        )
        self.tables = {}
        self.connect()

    def connect(self):
        """Connect the value."""
        self.is_connected = True
        return True

    def disconnect(self):
        """Disconnect the value."""
        self.is_connected = False
        return True

    def _CreateTable(self, table_name, schema):
        """Internal helper to create the table."""
        self.tables.setdefault(table_name, {})
        return True

    def _TableExists(self, table_name):
        """Return whether the table exists for value."""
        return table_name in self.tables

    def _Insert(self, table_name, data):
        """Internal helper for insert."""
        self.tables.setdefault(table_name, {})
        row_id = data.get("id") or data.get("agent_id")
        self.tables[table_name][row_id] = dict(data)
        return True

    def _Query(self, query, params=None):
        """Internal helper to query the value."""
        return []

    def _GetTableData(self, table_name, id_or_where=None, table_schema=None):
        """Internal helper to return the table data."""
        table = self.tables.get(table_name, {})
        rows = list(table.values())
        if isinstance(id_or_where, dict):
            return [dict(row) for row in rows if all(row.get(key) == value for key, value in id_or_where.items())]
        return [dict(row) for row in rows]

    def store_memory(self, content, memory_id=None, metadata=None, tags=None, memory_type="text", table_name=None):
        """Handle store memory for the in memory pool."""
        memory_table = table_name or self.MEMORY_TABLE
        if not self._TableExists(memory_table):
            self._CreateTable(memory_table, self.memory_table_schema())
        record = self._normalize_memory_record(content, memory_id, metadata, tags, memory_type)
        self._Insert(memory_table, record)
        return record

    def search_memory(self, query, limit=10, table_name=None):
        """Search the memory."""
        if not query:
            return []
        memory_table = table_name or self.MEMORY_TABLE
        rows = self._GetTableData(memory_table) if self._TableExists(memory_table) else []
        lowered = query.lower()
        return [row for row in rows if lowered in self._memory_search_text(row)][: max(int(limit), 0)]

    def create_table_practice(self):
        """Create the table practice."""
        return self._build_operation_practice(
            operation_id="pool-create-table",
            name="Pool Create Table",
            description="Create a table in the in-memory pool.",
            parameters={"table_name": {"type": "string"}, "schema": {"type": "object"}},
            tags=["pool", "memory", "create-table"],
            executor=lambda table_name, schema, **_: self._CreateTable(table_name, self._coerce_table_schema(schema)),
        )

    def table_exists_practice(self):
        """Return whether the table exists for practice."""
        return self._build_operation_practice(
            operation_id="pool-table-exists",
            name="Pool Table Exists",
            description="Check whether a table exists in the in-memory pool.",
            parameters={"table_name": {"type": "string"}},
            tags=["pool", "memory", "table-exists"],
            executor=lambda table_name, **_: self._TableExists(table_name),
        )

    def insert_practice(self):
        """Handle insert practice for the in memory pool."""
        return self._build_operation_practice(
            operation_id="pool-insert",
            name="Pool Insert",
            description="Insert one row into the in-memory pool.",
            parameters={"table_name": {"type": "string"}, "data": {"type": "object"}},
            tags=["pool", "memory", "insert"],
            executor=lambda table_name, data, **_: self._Insert(table_name, data),
        )

    def query_practice(self):
        """Query the practice."""
        return self._build_operation_practice(
            operation_id="pool-query",
            name="Pool Query",
            description="Execute a query against the in-memory pool.",
            parameters={"query": {"type": "string"}, "params": {"type": "object"}},
            tags=["pool", "memory", "query"],
            executor=lambda query, params=None, **_: self._Query(query, params),
        )

    def get_table_data_practice(self):
        """Return the table data practice."""
        return self._build_operation_practice(
            operation_id="pool-get-table-data",
            name="Pool Get Table Data",
            description="Read rows from the in-memory pool.",
            parameters={"table_name": {"type": "string"}, "id_or_where": {"type": "object"}, "table_schema": {"type": "object"}},
            tags=["pool", "memory", "read"],
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
            description="Connect the in-memory pool.",
            parameters={},
            tags=["pool", "memory", "connect"],
            executor=lambda **_: self.connect(),
        )

    def disconnect_practice(self):
        """Disconnect the practice."""
        return self._build_operation_practice(
            operation_id="pool-disconnect",
            name="Pool Disconnect",
            description="Disconnect the in-memory pool.",
            parameters={},
            tags=["pool", "memory", "disconnect"],
            executor=lambda **_: self.disconnect(),
        )

    def store_memory_practice(self):
        """Handle store memory practice for the in memory pool."""
        return self._build_operation_practice(
            operation_id="pool-store-memory",
            name="Pool Store Memory",
            description="Store one memory record in the in-memory pool.",
            parameters={"content": {"type": "string"}},
            tags=["pool", "memory", "store"],
            executor=lambda content, memory_id=None, metadata=None, tags=None, memory_type="text", table_name=None, **_: self.store_memory(
                content,
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
            description="Search stored memory records in the in-memory pool.",
            parameters={"query": {"type": "string"}},
            tags=["pool", "memory", "search"],
            executor=lambda query, limit=10, table_name=None, **_: self.search_memory(query, limit=limit, table_name=table_name),
        )


class FailingInsertPool(InMemoryPool):
    """Represent a failing insert pool."""

    def _Insert(self, table_name, data):
        """Internal helper for insert."""
        if table_name == PlazaPractice.DIRECTORY_TABLE:
            return False
        return super()._Insert(table_name, data)


def test_plaza_ui_no_longer_advertises_phema_specific_editor():
    """Exercise the Plaza UI boundary cleanup regression scenario."""
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    with TestClient(agent.app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert 'data-create-kind="Phema"' not in root.text
        assert '<option value="Phema">Phema</option>' not in root.text
        assert "/phemas/editor" not in root.text
        assert "Phema sync enabled" not in root.text
        assert "renderPhemaModeLabel" not in root.text
        assert 'data-create-kind="Custom"' in root.text

        removed_route = client.get("/phemas/editor")
        assert removed_route.status_code == 404


def test_plaza_directory_api_accepts_custom_types_without_predefinition():
    """Exercise the generic directory entry registration regression scenario."""
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    payload = {
        "agent_id": "macro-notebook",
        "name": "Macro Notebook",
        "description": "Reusable desk note",
        "owner": "Desk",
        "address": "plaza://entries/macro-notebook",
        "pit_type": "Notebook",
        "card": {
            "name": "Macro Notebook",
            "description": "Reusable desk note",
            "owner": "Desk",
            "address": "plaza://entries/macro-notebook",
            "pit_type": "Notebook",
            "tags": ["macro", "daily"],
            "sections": [{"name": "Topline", "content": []}],
            "meta": {"audience": "pm"},
        },
    }

    with TestClient(agent.app) as client:
        create_resp = client.post("/api/directory/entries", json=payload)
        assert create_resp.status_code == 200
        created = create_resp.json()["entry"]
        assert created["agent_id"] == "macro-notebook"
        assert created["type"] == "Notebook"
        assert created["card"]["pit_type"] == "Notebook"
        assert created["card"]["sections"][0]["name"] == "Topline"

        status_resp = client.get("/api/plazas_status?pit_type=Notebook")
        assert status_resp.status_code == 200
        entries = status_resp.json()["plazas"][0]["agents"]
        assert len(entries) == 1
        assert entries[0]["agent_id"] == "macro-notebook"
        assert entries[0]["pit_type"] == "Notebook"
        assert entries[0]["card"]["tags"] == ["macro", "daily"]

        delete_resp = client.delete("/api/directory/entries/macro-notebook")
        assert delete_resp.status_code == 200

        empty_status = client.get("/api/plazas_status?pit_type=Notebook")
        assert empty_status.status_code == 200
        assert empty_status.json()["plazas"][0]["agents"] == []


def test_plaza_keeps_custom_entry_searchable_when_directory_persist_fails():
    """Exercise the in-memory fallback regression scenario for generic entry types."""
    pool = FailingInsertPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    with TestClient(agent.app) as client:
        create_resp = client.post(
            "/api/directory/entries",
            json={
                "entry": {
                    "agent_id": "fallback-notebook",
                    "name": "Fallback Notebook",
                    "description": "Should stay searchable",
                    "owner": "Ops",
                    "address": "plaza://entries/fallback-notebook",
                    "pit_type": "Notebook",
                    "card": {
                        "name": "Fallback Notebook",
                        "description": "Should stay searchable",
                        "owner": "Ops",
                        "address": "plaza://entries/fallback-notebook",
                        "pit_type": "Notebook",
                        "meta": {"audience": "ops"},
                    },
                }
            },
        )
        assert create_resp.status_code == 200
        assert create_resp.json()["entry"]["agent_id"] == "fallback-notebook"

        status_resp = client.get("/api/plazas_status?pit_type=Notebook")
        assert status_resp.status_code == 200
        entries = status_resp.json()["plazas"][0]["agents"]
        assert len(entries) == 1
        assert entries[0]["name"] == "Fallback Notebook"
        assert entries[0]["pit_type"] == "Notebook"
