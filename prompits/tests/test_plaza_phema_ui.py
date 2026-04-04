"""
Regression tests for Plaza Phema UI.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_plaza_keeps_phema_searchable_when_pool_persist_fails`,
`test_plaza_monitor_can_infer_legacy_phema_mode_from_metadata`,
`test_plaza_supports_info_only_and_hosted_phema_registration_modes`, and
`test_plaza_ui_can_crud_phema_in_directory`, helping guard against regressions as the
packages evolve.
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
        if table_name == PlazaAgent.PHEMA_TABLE:
            return False
        return super()._Insert(table_name, data)


def test_plaza_ui_can_crud_phema_in_directory():
    """Exercise the test_plaza_ui_can_crud_phema_in_directory regression scenario."""
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    with TestClient(agent.app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert 'data-create-kind="Phema"' in root.text
        assert '<option value="Phema">Phema</option>' in root.text
        assert "/phemas/editor" in root.text
        assert "Info Only" in root.text
        assert "Hosted" in root.text

        editor = client.get("/phemas/editor")
        assert editor.status_code == 200
        assert "Phema Editor" in editor.text
        assert "+ Add Section" in editor.text
        assert "Available Pulses" in editor.text
        assert "Input Schema" in editor.text
        assert "Name Or Description" in editor.text
        assert "Sort By" in editor.text

        create_payload = {
            "phema": {
                "name": "Macro Morning Brief",
                "description": "Daily macro framing",
                "owner": "Plaza",
                "tags": ["macro", "daily"],
                "input_schema": {"symbol": {"type": "string"}},
                "sections": [
                    {
                        "name": "Topline",
                        "description": "Opening readout",
                        "modifier": "Keep it concise",
                        "content": ["price", "volume"],
                    }
                ],
                "meta": {"audience": "trader"},
            }
        }
        create_resp = client.post("/api/phemas", json=create_payload)
        assert create_resp.status_code == 200
        created = create_resp.json()["phema"]
        phema_id = created["phema_id"]
        assert created["name"] == "Macro Morning Brief"
        assert created["input_schema"]["symbol"]["type"] == "string"
        assert created["sections"][0]["name"] == "Topline"

        list_resp = client.get("/api/phemas")
        assert list_resp.status_code == 200
        assert len(list_resp.json()["phemas"]) == 1

        status_resp = client.get("/api/plazas_status?pit_type=Phema")
        assert status_resp.status_code == 200
        entries = status_resp.json()["plazas"][0]["agents"]
        assert len(entries) == 1
        assert entries[0]["pit_type"] == "Phema"
        assert entries[0]["meta"]["sections"][0]["name"] == "Topline"

        update_payload = {
            "phema": {
                "phema_id": phema_id,
                "name": "Macro Morning Brief",
                "description": "Updated market framing",
                "owner": "Desk",
                "address": created["address"],
                "tags": ["macro", "updated"],
                "input_schema": {"symbol": {"type": "string"}, "window": {"type": "integer"}},
                "sections": [
                    {
                        "name": "Topline",
                        "description": "Opening readout",
                        "modifier": "Focus on delta",
                        "content": ["price", "volume", "news"],
                    }
                ],
                "meta": {"audience": "pm"},
            }
        }
        update_resp = client.post("/api/phemas", json=update_payload)
        assert update_resp.status_code == 200
        updated = update_resp.json()["phema"]
        assert updated["description"] == "Updated market framing"
        assert updated["owner"] == "Desk"
        assert updated["input_schema"]["window"]["type"] == "integer"

        get_resp = client.get(f"/api/phemas/{phema_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["phema"]["tags"] == ["macro", "updated"]

        delete_resp = client.delete(f"/api/phemas/{phema_id}")
        assert delete_resp.status_code == 200

        empty_list = client.get("/api/phemas")
        assert empty_list.status_code == 200
        assert empty_list.json()["phemas"] == []

        empty_status = client.get("/api/plazas_status?pit_type=Phema")
        assert empty_status.status_code == 200
        assert empty_status.json()["plazas"][0]["agents"] == []


def test_plaza_keeps_phema_searchable_when_pool_persist_fails():
    """
    Exercise the test_plaza_keeps_phema_searchable_when_pool_persist_fails
    regression scenario.
    """
    pool = FailingInsertPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    with TestClient(agent.app) as client:
        create_resp = client.post(
            "/api/phemas",
            json={
                "phema": {
                    "phema_id": "fallback-phema",
                    "name": "Fallback Phema",
                    "description": "Should stay searchable",
                    "owner": "Plaza",
                    "tags": ["fallback"],
                    "input_schema": {"symbol": {"type": "string"}},
                    "sections": [{"name": "Only", "content": []}],
                    "meta": {"audience": "ops"},
                }
            },
        )
        assert create_resp.status_code == 200
        created = create_resp.json()["phema"]
        assert created["phema_id"] == "fallback-phema"

        list_resp = client.get("/api/phemas")
        assert list_resp.status_code == 200
        assert list_resp.json()["phemas"][0]["phema_id"] == "fallback-phema"

        get_resp = client.get("/api/phemas/fallback-phema")
        assert get_resp.status_code == 200
        assert get_resp.json()["phema"]["name"] == "Fallback Phema"

        status_resp = client.get("/api/plazas_status?pit_type=Phema")
        assert status_resp.status_code == 200
        entries = status_resp.json()["plazas"][0]["agents"]
        assert entries[0]["name"] == "Fallback Phema"


def test_plaza_supports_info_only_and_hosted_phema_registration_modes():
    """
    Exercise the test_plaza_supports_info_only_and_hosted_phema_registration_modes
    regression scenario.
    """
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    with TestClient(agent.app) as client:
        info_only_resp = client.post(
            "/api/phemas",
            json={
                "phema": {
                    "phema_id": "info-only-phema",
                    "name": "Info Only Phema",
                    "description": "Registered by reference",
                    "owner": "StockReportPhemar",
                    "tags": ["reference"],
                    "input_schema": {"symbol": {"type": "string"}},
                    "sections": [
                        {
                            "name": "Hidden",
                            "content": [
                                {
                                    "type": "pulse",
                                    "pulse_name": "company_profile",
                                    "pulse_address": "plaza://pulse/company_profile",
                                }
                            ],
                        }
                    ],
                    "meta": {
                        "registration_mode": "info_only",
                        "host_phemar_name": "StockReportPhemar",
                        "host_phemar_agent_id": "phemar-123",
                        "host_phemar_pit_address": {"pit_id": "phemar-123", "plazas": ["http://127.0.0.1:8011"]},
                        "registered_by_phemar": "StockReportPhemar",
                    },
                }
            },
        )
        assert info_only_resp.status_code == 200
        info_only = info_only_resp.json()["phema"]
        assert info_only["registration_mode"] == "info_only"
        assert info_only["downloadable"] is False
        assert info_only["resolution_mode"] == "dynamic"
        assert info_only["sections"] == []
        assert info_only["input_schema"] == {}

        hosted_resp = client.post(
            "/api/phemas",
            json={
                "phema": {
                    "phema_id": "hosted-phema",
                    "name": "Hosted Phema",
                    "description": "Hosted on plaza",
                    "owner": "StockReportPhemar",
                    "tags": ["hosted"],
                    "input_schema": {"symbol": {"type": "string"}},
                    "sections": [
                        {
                            "name": "Visible",
                            "content": [
                                {
                                    "type": "pulse",
                                    "pulse_name": "last_price",
                                    "pulse_address": "plaza://pulse/last_price",
                                }
                            ],
                        }
                    ],
                    "meta": {
                        "registration_mode": "hosted",
                        "host_phemar_name": "StockReportPhemar",
                        "host_phemar_agent_id": "phemar-123",
                        "host_phemar_pit_address": {"pit_id": "phemar-123", "plazas": ["http://127.0.0.1:8011"]},
                    },
                }
            },
        )
        assert hosted_resp.status_code == 200
        hosted = hosted_resp.json()["phema"]
        assert hosted["registration_mode"] == "hosted"
        assert hosted["downloadable"] is True
        assert hosted["resolution_mode"] == "dynamic"
        assert hosted["sections"][0]["name"] == "Visible"
        assert hosted["input_schema"]["symbol"]["type"] == "string"

        list_resp = client.get("/api/phemas")
        assert list_resp.status_code == 200
        rows = {entry["phema_id"]: entry for entry in list_resp.json()["phemas"]}
        assert rows["info-only-phema"]["registration_mode"] == "info_only"
        assert rows["info-only-phema"]["downloadable"] is False
        assert rows["info-only-phema"]["resolution_mode"] == "dynamic"
        assert rows["hosted-phema"]["registration_mode"] == "hosted"
        assert rows["hosted-phema"]["downloadable"] is True
        assert rows["hosted-phema"]["resolution_mode"] == "dynamic"

        status_resp = client.get("/api/plazas_status?pit_type=Phema")
        assert status_resp.status_code == 200
        entries = {entry["agent_id"]: entry for entry in status_resp.json()["plazas"][0]["agents"]}
        assert entries["info-only-phema"]["meta"]["registration_mode"] == "info_only"
        assert "sections" not in (entries["info-only-phema"].get("meta") or {})
        assert entries["hosted-phema"]["meta"]["registration_mode"] == "hosted"
        assert entries["hosted-phema"]["meta"]["sections"][0]["name"] == "Visible"


def test_plaza_monitor_can_infer_legacy_phema_mode_from_metadata():
    """
    Exercise the test_plaza_monitor_can_infer_legacy_phema_mode_from_metadata
    regression scenario.
    """
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    practice = agent._get_plaza_practice()
    practice.state.upsert_directory_entry(
        "legacy-hosted-phema",
        "Legacy Hosted Phema",
        "plaza://phema/legacy-hosted-phema",
        "Phema",
        {
            "agent_id": "legacy-hosted-phema",
            "name": "Legacy Hosted Phema",
            "description": "Older hosted record",
            "owner": "StockReportPhemar",
            "pit_type": "Phema",
            "meta": {"sections": [{"name": "Visible", "content": []}]},
        },
    )
    practice.state.upsert_directory_entry(
        "legacy-info-phema",
        "Legacy Info Phema",
        "plaza://phema/legacy-info-phema",
        "Phema",
        {
            "agent_id": "legacy-info-phema",
            "name": "Legacy Info Phema",
            "description": "Older info-only record",
            "owner": "StockReportPhemar",
            "pit_type": "Phema",
            "meta": {"host_phemar_name": "StockReportPhemar", "access_practice_id": "generate_phema"},
        },
    )

    with TestClient(agent.app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "renderPhemaModeLabel" in root.text
        assert "host_phemar_name" in root.text
