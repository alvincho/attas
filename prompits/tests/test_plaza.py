"""
Regression tests for Plaza.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_plaza_register_accepts_multiple_pulse_pulser_pairs_in_single_request`,
`test_plaza_register_batches_new_pulse_directory_persistence`,
`test_plaza_register_batches_pulse_pulser_pair_persistence`, and
`test_plaza_register_dedupes_supported_pulses_and_explicit_batch_pairs`, helping guard
against regressions as the packages evolve.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import json
import logging
import pytest
import httpx
import time
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from prompits.agents.standby import StandbyAgent
from prompits.core.pit import PitAddress
from prompits.core.pool import Pool, PoolCap

from prompits.tests.test_support import start_agent_thread, stop_servers
from prompits.practices.plaza import PlazaPractice
from prompits.core.plaza import PlazaAgent


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
            return [dict(r) for r in rows if all(r.get(k) == v for k, v in id_or_where.items())]
        return [dict(r) for r in rows]

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
            parameters={
                "table_name": {"type": "string"},
                "schema": {"type": "object"},
            },
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
            parameters={
                "table_name": {"type": "string"},
                "data": {"type": "object"},
            },
            tags=["pool", "memory", "insert"],
            executor=lambda table_name, data, **_: self._Insert(table_name, data),
        )

    def query_practice(self):
        """Query the practice."""
        return self._build_operation_practice(
            operation_id="pool-query",
            name="Pool Query",
            description="Execute a query against the in-memory pool.",
            parameters={
                "query": {"type": "string"},
                "params": {"type": "object"},
            },
            tags=["pool", "memory", "query"],
            executor=lambda query, params=None, **_: self._Query(query, params),
        )

    def get_table_data_practice(self):
        """Return the table data practice."""
        return self._build_operation_practice(
            operation_id="pool-get-table-data",
            name="Pool Get Table Data",
            description="Read rows from the in-memory pool.",
            parameters={
                "table_name": {"type": "string"},
                "id_or_where": {"type": "object"},
                "table_schema": {"type": "object"},
            },
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
            parameters={
                "content": {"type": "string"},
                "memory_id": {"type": "string"},
                "metadata": {"type": "object"},
                "tags": {"type": "array"},
                "memory_type": {"type": "string"},
                "table_name": {"type": "string"},
            },
            tags=["pool", "memory", "store"],
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
            description="Search stored memory records in the in-memory pool.",
            parameters={
                "query": {"type": "string"},
                "limit": {"type": "integer"},
                "table_name": {"type": "string"},
            },
            tags=["pool", "memory", "search"],
            executor=lambda query, limit=10, table_name=None, **_: self.search_memory(
                query=query,
                limit=limit,
                table_name=table_name,
            ),
        )


class CountingInMemoryPool(InMemoryPool):
    """Represent a counting in memory pool."""
    def __init__(self):
        """Initialize the counting in memory pool."""
        super().__init__()
        self.get_calls = []

    def _GetTableData(self, table_name, id_or_where=None, table_schema=None):
        """Internal helper to return the table data."""
        self.get_calls.append((table_name, id_or_where))
        return super()._GetTableData(table_name, id_or_where, table_schema)


class CountingBatchInMemoryPool(InMemoryPool):
    """Represent a counting batch in memory pool."""
    def __init__(self):
        """Initialize the counting batch in memory pool."""
        super().__init__()
        self.insert_calls = []
        self.insert_many_calls = []
        self.table_exists_calls = []

    def _TableExists(self, table_name):
        """Return whether the table exists for value."""
        self.table_exists_calls.append(table_name)
        return super()._TableExists(table_name)

    def _Insert(self, table_name, data):
        """Internal helper for insert."""
        self.insert_calls.append((table_name, dict(data)))
        return super()._Insert(table_name, data)

    def _InsertMany(self, table_name, data_list):
        """Internal helper for insert many."""
        copied_rows = [dict(row) for row in (data_list or [])]
        self.insert_many_calls.append((table_name, copied_rows))
        self.tables.setdefault(table_name, {})
        for data in copied_rows:
            row_id = data.get("id") or data.get("agent_id")
            self.tables[table_name][row_id] = dict(data)
        return True


class MissingTokenTablePool(InMemoryPool):
    """Represent a missing token table pool."""
    def __init__(self):
        """Initialize the missing token table pool."""
        super().__init__()
        self.token_exists_checks = 0
        self.token_create_calls = 0
        self.token_insert_calls = 0

    def _TableExists(self, table_name):
        """Return whether the table exists for value."""
        if table_name == "plaza_tokens":
            self.token_exists_checks += 1
            return False
        return super()._TableExists(table_name)

    def _CreateTable(self, table_name, schema):
        """Internal helper to create the table."""
        if table_name == "plaza_tokens":
            self.token_create_calls += 1
            return True
        return super()._CreateTable(table_name, schema)

    def _Insert(self, table_name, data):
        """Internal helper for insert."""
        if table_name == "plaza_tokens":
            self.token_insert_calls += 1
            return False
        return super()._Insert(table_name, data)


class SlowInsertInMemoryPool(InMemoryPool):
    """Represent a slow insert in memory pool."""
    def __init__(self, delay=0.25):
        """Initialize the slow insert in memory pool."""
        super().__init__()
        self.delay = delay

    def _Insert(self, table_name, data):
        """Internal helper for insert."""
        if table_name in {"plaza_tokens", "plaza_directory", "pulse_pulser_pairs"}:
            time.sleep(self.delay)
        return super()._Insert(table_name, data)

    def _InsertMany(self, table_name, data_list):
        """Internal helper for insert many."""
        if table_name == "pulse_pulser_pairs":
            time.sleep(self.delay)
        return super()._InsertMany(table_name, data_list)


def test_pool_inherits_pit_identity_state():
    """Exercise the test_pool_inherits_pit_identity_state regression scenario."""
    address = PitAddress(pit_id="pool-123", plazas=["http://127.0.0.1:8011"])
    pool = InMemoryPool()

    class DirectPool(Pool):
        """Represent a direct pool."""
        def __init__(self):
            """Initialize the direct pool."""
            super().__init__(
                name="direct",
                description="direct pool",
                address=address,
                meta={"kind": "memory"},
                capabilities=[PoolCap.TABLE, PoolCap.JSON, PoolCap.SEARCH, PoolCap.MEMORY],
            )
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
            return True

        def _TableExists(self, table_name):
            """Return whether the table exists for value."""
            return False

        def _Insert(self, table_name, data):
            """Internal helper for insert."""
            return True

        def _Query(self, query, params=None):
            """Internal helper to query the value."""
            return []

        def _GetTableData(self, table_name, id_or_where=None, table_schema=None):
            """Internal helper to return the table data."""
            return []

        def store_memory(self, content, memory_id=None, metadata=None, tags=None, memory_type="text", table_name=None):
            """Handle store memory for the direct pool."""
            return self._normalize_memory_record(content, memory_id, metadata, tags, memory_type)

        def search_memory(self, query, limit=10, table_name=None):
            """Search the memory."""
            return []

        def create_table_practice(self):
            """Create the table practice."""
            return self._build_operation_practice(
                operation_id="pool-create-table",
                name="Pool Create Table",
                description="Create a table in the direct pool.",
                parameters={"table_name": {"type": "string"}, "schema": {"type": "object"}},
                executor=lambda table_name, schema, **_: self._CreateTable(table_name, self._coerce_table_schema(schema)),
            )

        def table_exists_practice(self):
            """Return whether the table exists for practice."""
            return self._build_operation_practice(
                operation_id="pool-table-exists",
                name="Pool Table Exists",
                description="Check table existence in the direct pool.",
                parameters={"table_name": {"type": "string"}},
                executor=lambda table_name, **_: self._TableExists(table_name),
            )

        def insert_practice(self):
            """Handle insert practice for the direct pool."""
            return self._build_operation_practice(
                operation_id="pool-insert",
                name="Pool Insert",
                description="Insert data into the direct pool.",
                parameters={"table_name": {"type": "string"}, "data": {"type": "object"}},
                executor=lambda table_name, data, **_: self._Insert(table_name, data),
            )

        def query_practice(self):
            """Query the practice."""
            return self._build_operation_practice(
                operation_id="pool-query",
                name="Pool Query",
                description="Query the direct pool.",
                parameters={"query": {"type": "string"}, "params": {"type": "object"}},
                executor=lambda query, params=None, **_: self._Query(query, params),
            )

        def get_table_data_practice(self):
            """Return the table data practice."""
            return self._build_operation_practice(
                operation_id="pool-get-table-data",
                name="Pool Get Table Data",
                description="Read data from the direct pool.",
                parameters={"table_name": {"type": "string"}, "id_or_where": {"type": "object"}, "table_schema": {"type": "object"}},
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
                description="Connect the direct pool.",
                parameters={},
                executor=lambda **_: self.connect(),
            )

        def disconnect_practice(self):
            """Disconnect the practice."""
            return self._build_operation_practice(
                operation_id="pool-disconnect",
                name="Pool Disconnect",
                description="Disconnect the direct pool.",
                parameters={},
                executor=lambda **_: self.disconnect(),
            )

        def store_memory_practice(self):
            """Handle store memory practice for the direct pool."""
            return self._build_operation_practice(
                operation_id="pool-store-memory",
                name="Pool Store Memory",
                description="Store memory in the direct pool.",
                parameters={"content": {"type": "string"}},
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
                description="Search memory in the direct pool.",
                parameters={"query": {"type": "string"}},
                executor=lambda query, limit=10, table_name=None, **_: self.search_memory(
                    query=query,
                    limit=limit,
                    table_name=table_name,
                ),
            )

    direct = DirectPool()
    assert isinstance(pool, Pool)
    assert isinstance(pool.address, PitAddress)
    assert PoolCap.MEMORY in pool.capabilities
    assert direct.address.pit_id == "pool-123"
    assert direct.meta["kind"] == "memory"
    assert direct.meta["capabilities"] == ["table", "json", "search", "memory"]


def test_pit_address_supports_compact_ref_round_trip():
    """
    Exercise the test_pit_address_supports_compact_ref_round_trip regression
    scenario.
    """
    address = PitAddress.from_value("11111111-1111-1111-1111-111111111111@http://127.0.0.1:8011")

    assert address.pit_id == "11111111-1111-1111-1111-111111111111"
    assert address.plazas == ["http://127.0.0.1:8011"]
    assert address.to_ref(reference_plaza="http://127.0.0.1:8011") == "11111111-1111-1111-1111-111111111111"
    assert address.to_ref(reference_plaza="http://127.0.0.1:9999") == "11111111-1111-1111-1111-111111111111@http://127.0.0.1:8011"

@pytest.fixture(scope="module")
def setup_agents():
    """Set up the agents."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'fixtures/configs'))
    plaza_cfg = os.path.join(base_dir, "plaza.agent")
    alice_cfg = os.path.join(base_dir, "alice.agent")
    bob_cfg = os.path.join(base_dir, "bob.agent")

    _, plaza_server, plaza_thread = start_agent_thread(plaza_cfg)
    _, alice_server, alice_thread = start_agent_thread(alice_cfg)
    _, bob_server, bob_thread = start_agent_thread(bob_cfg)
    
    # Wait for servers to start
    time.sleep(1)
    
    yield
    
    stop_servers([
        (plaza_server, plaza_thread),
        (alice_server, alice_thread),
        (bob_server, bob_thread)
    ])

@pytest.mark.asyncio
async def test_plaza_flow(setup_agents):
    """Exercise the test_plaza_flow regression scenario."""
    async with httpx.AsyncClient() as client:
        # 1. Register Alice
        resp = await client.post("http://127.0.0.1:8011/register", json={
            "agent_name": "alice",
            "address": "http://127.0.0.1:8012"
        })
        assert resp.status_code == 200, f"Alice registration failed: {resp.text}"
        alice_data = resp.json()
        assert "token" in alice_data
        assert "agent_id" in alice_data
        assert "api_key" in alice_data
        assert alice_data.get("issued_new_identity") is True
        alice_token = alice_data["token"]
        
        # 2. Register Bob
        resp = await client.post("http://127.0.0.1:8011/register", json={
            "agent_name": "bob",
            "address": "http://127.0.0.1:8013",
            "pit_type": "Pulse"
        })
        assert resp.status_code == 200, f"Bob registration failed: {resp.text}"
        bob_data = resp.json()
        assert "token" in bob_data
        assert bob_data["pit_type"] == "Pulse"
        
        # 3. Authenticate Alice
        resp = await client.post(
            "http://127.0.0.1:8011/authenticate",
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert resp.status_code == 200, f"Alice authentication failed: {resp.text}"
        
        # 4. Relay Message from Alice to Bob
        relay_resp = await client.post(
            "http://127.0.0.1:8011/relay",
            json={
                "receiver": "bob",
                "content": "Hello Bob from Alice!",
                "msg_type": "message"
            },
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert relay_resp.status_code == 200, f"Relay message failed: {relay_resp.text}"

        # 4.1 Verify search can filter by PIT type
        resp = await client.get(
            "http://127.0.0.1:8011/search",
            params={"pit_type": "Pulse"},
            headers={"Authorization": f"Bearer {alice_token}"}
        )
        assert resp.status_code == 200, f"Search by pit_type failed: {resp.text}"
        search_data = resp.json()
        assert any(entry["name"] == "bob" and entry.get("pit_type") == "Pulse" for entry in search_data)
        assert all(entry.get("pit_type") == "Pulse" for entry in search_data)
        
        # 5. Relay response should include a downstream success payload from Bob's mailbox endpoint
        relay_data = relay_resp.json()
        assert relay_data.get("status") == "relayed"


def test_plaza_self_registered_in_search_directory():
    """
    Exercise the test_plaza_self_registered_in_search_directory regression scenario.
    """
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent"
        }
    ))
    practice.mount(app)

    client = TestClient(app)

    register = client.post("/register", json={
        "agent_name": "alice",
        "address": "http://127.0.0.1:8012"
    })
    assert register.status_code == 200
    token = register.json()["token"]

    search = client.get("/search", headers={"Authorization": f"Bearer {token}"})
    assert search.status_code == 200
    names = [entry["name"] for entry in search.json()]
    assert "Plaza" in names


def test_plaza_register_disables_optional_token_persistence_when_table_missing():
    """
    Exercise the
    test_plaza_register_disables_optional_token_persistence_when_table_missing
    regression scenario.
    """
    app = FastAPI()
    pool = MissingTokenTablePool()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent"
        }
    ))
    practice.mount(app)

    client = TestClient(app)

    register = client.post("/register", json={
        "agent_name": "alice",
        "address": "http://127.0.0.1:8012"
    })
    assert register.status_code == 200
    token = register.json()["token"]
    assert practice.state._token_store_available is False
    assert pool.token_exists_checks >= 1
    assert pool.token_create_calls == 1
    assert pool.token_insert_calls == 0

    search = client.get("/search", headers={"Authorization": f"Bearer {token}"})
    assert search.status_code == 200

    renew = client.post(
        "/renew",
        json={"agent_name": "alice", "expires_in": 3600},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert renew.status_code == 200
    assert pool.token_create_calls == 1
    assert pool.token_insert_calls == 0


def test_plaza_token_persistence_uses_token_column_without_id_field():
    """
    Exercise the test_plaza_token_persistence_uses_token_column_without_id_field
    regression scenario.
    """
    app = FastAPI()
    pool = CountingBatchInMemoryPool()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent"
        }
    ))
    practice.mount(app)

    client = TestClient(app)
    register = client.post("/register", json={
        "agent_name": "alice",
        "address": "http://127.0.0.1:8012"
    })
    assert register.status_code == 200

    token_rows = [data for table_name, data in pool.insert_calls if table_name == "plaza_tokens"]
    assert len(token_rows) == 1
    assert token_rows[0]["token"] == register.json()["token"]
    assert "id" not in token_rows[0]


def test_plaza_authenticate_error_includes_safe_detail_parameters():
    """
    Exercise the
    test_plaza_authenticate_error_includes_safe_detail_parameters regression
    scenario.
    """
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent"
        }
    ))
    practice.mount(app)
    client = TestClient(app)

    response = client.post(
        "/authenticate",
        headers={"Authorization": "Bearer not-a-real-token"},
    )

    assert response.status_code == 401
    payload = response.json()
    assert payload["detail"]["message"] == "Invalid token"
    assert payload["detail"]["parameters"] == {
        "auth_scheme": "Bearer",
        "token_provided": True,
        "token_length": len("not-a-real-token"),
    }


def test_base_agent_request_logging_includes_error_detail_parameters(caplog):
    """
    Exercise the
    test_base_agent_request_logging_includes_error_detail_parameters regression
    scenario.
    """
    agent = StandbyAgent(name="logger-agent")

    @agent.app.get("/boom")
    async def boom():
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Invalid token",
                "parameters": {"auth_scheme": "Bearer", "token_length": 4},
            },
        )

    client = TestClient(agent.app)

    with caplog.at_level(logging.INFO, logger="prompits.agents.base"):
        response = client.get("/boom")

    assert response.status_code == 401
    completed_logs = [
        record.getMessage()
        for record in caplog.records
        if "Completed request GET /boom" in record.getMessage()
    ]
    assert completed_logs
    assert "detail=Invalid token | parameters=" in completed_logs[-1]
    assert '"auth_scheme": "Bearer"' in completed_logs[-1]
    assert '"token_length": 4' in completed_logs[-1]


def test_plaza_bootstraps_builtin_schema_pits_on_startup():
    """
    Exercise the test_plaza_bootstraps_builtin_schema_pits_on_startup regression
    scenario.
    """
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent"
        }
    ))
    practice.mount(app)
    client = TestClient(app)

    register = client.post("/register", json={
        "agent_name": "alice",
        "address": "http://127.0.0.1:8012"
    })
    assert register.status_code == 200
    token = register.json()["token"]

    search = client.get("/search", headers={"Authorization": f"Bearer {token}"})
    assert search.status_code == 200
    results = search.json()
    schema_entries = [entry for entry in results if entry.get("pit_type") == "Schema"]
    schema_names = {entry.get("name") for entry in schema_entries}
    assert "Schema: plaza_credentials" in schema_names
    assert "Schema: plaza_login_history" in schema_names
    assert "Schema: plaza_directory" in schema_names
    assert "Schema: agent_practices" in schema_names
    assert "Schema: pulse_pulser_pairs" in schema_names


def test_plaza_bootstraps_init_files_on_startup_without_duplicates(tmp_path):
    """
    Exercise the test_plaza_bootstraps_init_files_on_startup_without_duplicates
    regression scenario.
    """
    init_dir = tmp_path / "init_files"
    init_dir.mkdir()
    (init_dir / "init_pulse_market.json").write_text(json.dumps({
        "PitType": "Pulse",
        "data": [
            {
                "name": "last_price",
                "description": "Latest traded price for the stock.",
                "tags": ["price", "market-data"],
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "last_price": {"type": "number"},
                    },
                    "required": ["symbol", "last_price"],
                },
            }
        ]
    }))

    pool = InMemoryPool()
    app = FastAPI()
    practice = PlazaPractice(init_files=[str(init_dir)])
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)

    client = TestClient(app)
    register = client.post("/register", json={
        "agent_name": "alice",
        "address": "http://127.0.0.1:8012"
    })
    assert register.status_code == 200
    token = register.json()["token"]

    search = client.get("/search", headers={"Authorization": f"Bearer {token}"})
    assert search.status_code == 200
    seeded = [entry for entry in search.json() if entry.get("name") == "last_price"]
    assert len(seeded) == 1
    assert seeded[0]["pit_type"] == "Pulse"
    assert seeded[0]["agent_id"]
    assert seeded[0]["meta"]["output_schema"]["type"] == "object"
    assert "name" not in seeded[0]["meta"]
    first_count = len(pool.tables[PlazaPractice.DIRECTORY_TABLE])

    second_app = FastAPI()
    second_practice = PlazaPractice(init_files=[str(init_dir)])
    second_practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    second_practice.mount(second_app)

    assert len(pool.tables[PlazaPractice.DIRECTORY_TABLE]) == first_count


def test_plaza_bootstrap_skips_imported_init_files(tmp_path):
    """
    Exercise the test_plaza_bootstrap_skips_imported_init_files regression scenario.
    """
    init_dir = tmp_path / "init_files"
    init_dir.mkdir()
    (init_dir / "init_pulse_imported.json").write_text(json.dumps({
        "PitType": "Pulse",
        "data": [
            {
                "name": "last_price",
                "description": "Latest traded price for the stock.",
            }
        ]
    }))

    pool = InMemoryPool()
    app = FastAPI()
    practice = PlazaPractice(init_files=[str(init_dir)])
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)

    pulse_rows = [
        row for row in pool.tables.get(PlazaPractice.DIRECTORY_TABLE, {}).values()
        if row.get("type") == "Pulse"
    ]
    assert pulse_rows == []


def test_plaza_bootstrap_refreshes_existing_seeded_pulse_schema(tmp_path):
    """
    Exercise the test_plaza_bootstrap_refreshes_existing_seeded_pulse_schema
    regression scenario.
    """
    init_dir = tmp_path / "init_files"
    init_dir.mkdir()
    init_file = init_dir / "init_pulse_news.json"
    init_file.write_text(json.dumps({
        "PitType": "Pulse",
        "data": [
            {
                "name": "news_article",
                "description": "Single news article record relevant to the stock.",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "headline": {"type": "string"},
                    },
                    "required": ["symbol", "headline"],
                },
            }
        ]
    }))

    pool = InMemoryPool()
    app = FastAPI()
    practice = PlazaPractice(init_files=[str(init_dir)])
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)

    init_file.write_text(json.dumps({
        "PitType": "Pulse",
        "data": [
            {
                "name": "news_article",
                "description": "News article collection relevant to the stock.",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "number_of_articles": {"type": "integer"},
                        "articles": {"type": "array"},
                    },
                    "required": ["symbol", "articles"],
                },
            }
        ]
    }))

    second_app = FastAPI()
    second_practice = PlazaPractice(init_files=[str(init_dir)])
    second_practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    second_practice.mount(second_app)

    pulse_id = second_practice.state.stable_pulse_id("news_article")
    updated_card = second_practice.state.agent_cards[pulse_id]
    updated_schema = updated_card["meta"]["output_schema"]

    assert updated_card["meta"]["description"] == "News article collection relevant to the stock."
    assert "articles" in updated_schema["properties"]
    assert updated_schema["required"] == ["symbol", "articles"]


def test_plaza_bootstraps_init_files_with_single_directory_fetch(tmp_path):
    """
    Exercise the test_plaza_bootstraps_init_files_with_single_directory_fetch
    regression scenario.
    """
    init_dir = tmp_path / "init_files"
    init_dir.mkdir()
    (init_dir / "init_pulse_prices.json").write_text(json.dumps({
        "PitType": "Pulse",
        "data": [
            {"name": "last_price", "description": "Latest traded price."},
            {"name": "open_price", "description": "Open price."},
            {"name": "previous_close", "description": "Previous close."},
        ]
    }))

    pool = CountingInMemoryPool()
    app = FastAPI()
    practice = PlazaPractice(init_files=[str(init_dir)])
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)

    directory_reads = [
        call for call in pool.get_calls
        if call[0] == PlazaPractice.DIRECTORY_TABLE
    ]
    assert len(directory_reads) in {1, 2}
    assert all(call == (PlazaPractice.DIRECTORY_TABLE, None) for call in directory_reads)


def test_plaza_bootstraps_all_tagged_init_pulse_files_from_directory(tmp_path):
    """
    Exercise the test_plaza_bootstraps_all_tagged_init_pulse_files_from_directory
    regression scenario.
    """
    init_dir = tmp_path / "init_files"
    init_dir.mkdir()
    (init_dir / "init_pulse_market.json").write_text(json.dumps({
        "PitType": "Pulse",
        "data": [
            {"name": "last_price", "description": "Latest traded price."},
        ]
    }))
    (init_dir / "init_pulse_news.json").write_text(json.dumps({
        "PitType": "Pulse",
        "data": [
            {"name": "news_article", "description": "Latest news item."},
        ]
    }))
    (init_dir / "init_schema.json").write_text(json.dumps({
        "PitType": "Schema",
        "name": "ignored_schema",
        "rowSchema": {"id": {"type": "string"}},
    }))

    pool = InMemoryPool()
    app = FastAPI()
    practice = PlazaPractice(init_files=[str(init_dir)])
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)

    pulse_names = {
        row.get("name")
        for row in pool.tables.get(PlazaPractice.DIRECTORY_TABLE, {}).values()
        if row.get("type") == "Pulse"
    }

    assert pulse_names == {"last_price", "news_article"}


def test_plaza_registers_pulser_entry_with_supported_pulse_details():
    """
    Exercise the test_plaza_registers_pulser_entry_with_supported_pulse_details
    regression scenario.
    """
    pool = InMemoryPool()
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)

    client = TestClient(app)
    register = client.post("/register", json={
        "agent_name": "yfinance-pulser",
        "address": "http://127.0.0.1:8020",
        "pit_type": "Pulser",
        "card": {
            "name": "YFinancePulser",
            "pit_type": "Pulser",
            "role": "pulser",
            "tags": ["finance", "market-data"],
            "meta": {
                "pulse_address": "plaza://pulse/last_price",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"]
                },
                "supported_pulses": [
                    {
                        "name": "last_price",
                        "description": "Latest traded price for the stock.",
                        "pulse_address": "plaza://pulse/last_price",
                        "tags": ["price", "market-data"],
                        "input_schema": {
                            "type": "object",
                            "properties": {"symbol": {"type": "string"}},
                            "required": ["symbol"]
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "last_price": {"type": "number"}
                            },
                            "required": ["symbol", "last_price"]
                        }
                    }
                ]
            }
        }
    })
    assert register.status_code == 200
    headers = {"Authorization": f"Bearer {register.json()['token']}"}

    search = client.get("/search", params={"type": "Pulser", "name": "YFinancePulser"}, headers=headers)
    assert search.status_code == 200
    results = search.json()
    assert len(results) == 1
    assert results[0]["name"] == "YFinancePulser"
    assert results[0]["pit_type"] == "Pulser"
    assert results[0]["meta"]["pulse_address"] == "plaza://pulse/last_price"
    assert results[0]["meta"]["input_schema"]["properties"]["symbol"]["type"] == "string"
    assert len(results[0]["meta"]["supported_pulses"]) == 1
    assert results[0]["meta"]["supported_pulses"][0]["pulse_id"] == "urn:plaza:pulse:last.price"
    assert results[0]["meta"]["supported_pulses"][0]["pulse_definition"]["resource_type"] == "pulse_definition"
    assert results[0]["meta"]["supported_pulses"][0]["pulse_address"] == "plaza://pulse/last_price"
    assert results[0]["meta"]["supported_pulses"][0]["output_schema"]["properties"]["last_price"]["type"] == "number"

    assert PlazaPractice.PULSE_PULSER_TABLE in pool.tables
    pulse_pair_rows = list(pool.tables[PlazaPractice.PULSE_PULSER_TABLE].values())
    assert len(pulse_pair_rows) == 1
    assert pulse_pair_rows[0]["pulse_id"] == "urn:plaza:pulse:last.price"
    assert pulse_pair_rows[0]["pulse_directory_id"] == practice.state.stable_pulse_id("last_price")
    assert pulse_pair_rows[0]["pulse_name"] == "last_price"
    assert pulse_pair_rows[0]["pulse_address"] == "plaza://pulse/last_price"
    assert pulse_pair_rows[0]["pulser_address"] == register.json()["agent_id"]
    assert pulse_pair_rows[0]["pulser_directory_id"] == register.json()["agent_id"]
    assert pulse_pair_rows[0]["pulse_definition"]["resource_type"] == "pulse_definition"
    assert pulse_pair_rows[0]["input_schema"]["properties"]["symbol"]["type"] == "string"

    pulse_search = client.get("/search", params={"pulse_name": "last_price"}, headers=headers)
    assert pulse_search.status_code == 200
    pulse_results = pulse_search.json()
    assert len(pulse_results) == 1
    assert pulse_results[0]["name"] == "YFinancePulser"
    assert pulse_results[0]["pit_type"] == "Pulser"

    pulse_id_search = client.get("/search", params={"pulse_id": "urn:plaza:pulse:last.price"}, headers=headers)
    assert pulse_id_search.status_code == 200
    pulse_id_results = pulse_id_search.json()
    assert len(pulse_id_results) == 1
    assert pulse_id_results[0]["name"] == "YFinancePulser"


def test_plaza_register_accepts_multiple_pulse_pulser_pairs_in_single_request():
    """
    Exercise the
    test_plaza_register_accepts_multiple_pulse_pulser_pairs_in_single_request
    regression scenario.
    """
    pool = InMemoryPool()
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)

    client = TestClient(app)
    register = client.post("/register", json={
        "agent_name": "batch-pulser",
        "address": "http://127.0.0.1:8025",
        "pit_type": "Pulser",
        "card": {
            "name": "BatchPulser",
            "pit_type": "Pulser",
            "role": "pulser",
            "meta": {}
        },
        "pulse_pulser_pairs": [
            {
                "pulse_name": "last_price",
                "pulse_address": "plaza://pulse/last_price",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"]
                }
            },
            {
                "pulse_name": "trade_volume",
                "pulse_address": "plaza://pulse/trade_volume",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}, "trade_date": {"type": "string"}},
                    "required": ["symbol"]
                }
            }
        ]
    })
    assert register.status_code == 200
    headers = {"Authorization": f"Bearer {register.json()['token']}"}

    assert PlazaPractice.PULSE_PULSER_TABLE in pool.tables
    pulse_pair_rows = list(pool.tables[PlazaPractice.PULSE_PULSER_TABLE].values())
    assert len(pulse_pair_rows) == 2
    assert {row["pulse_id"] for row in pulse_pair_rows} == {"urn:plaza:pulse:last.price", "urn:plaza:pulse:trade.volume"}
    assert {row["pulse_directory_id"] for row in pulse_pair_rows} == {
        practice.state.stable_pulse_id("last_price"),
        practice.state.stable_pulse_id("trade_volume"),
    }
    assert {row["pulse_name"] for row in pulse_pair_rows} == {"last_price", "trade_volume"}
    assert all(row["pulser_id"] == register.json()["agent_id"] for row in pulse_pair_rows)
    assert all(row["pulser_directory_id"] == register.json()["agent_id"] for row in pulse_pair_rows)

    price_search = client.get("/search", params={"pulse_name": "last_price"}, headers=headers)
    assert price_search.status_code == 200
    price_results = price_search.json()
    assert len(price_results) == 1
    assert price_results[0]["name"] == "BatchPulser"

    volume_search = client.get("/search", params={"pulse_name": "trade_volume"}, headers=headers)
    assert volume_search.status_code == 200
    volume_results = volume_search.json()
    assert len(volume_results) == 1
    assert volume_results[0]["name"] == "BatchPulser"


def test_plaza_can_restore_missing_pulse_directory_rows_from_pairs():
    """
    Exercise the test_plaza_can_restore_missing_pulse_directory_rows_from_pairs
    regression scenario.
    """
    pool = InMemoryPool()
    pool._CreateTable(PlazaPractice.DIRECTORY_TABLE, None)
    pool._CreateTable(PlazaPractice.PULSE_PULSER_TABLE, None)
    pool._Insert(
        PlazaPractice.PULSE_PULSER_TABLE,
        {
            "id": "pair-1",
            "pulse_id": "urn:plaza:pulse:last.price",
            "pulse_name": "last_price",
            "pulse_address": "plaza://pulse/last_price",
            "pulse_definition": {
                "resource_type": "pulse_definition",
                "id": "urn:plaza:pulse:last.price",
                "name": "last_price",
                "description": "Latest traded price for the stock.",
                "status": "stable",
                "interface": {
                    "request_schema": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}},
                        "required": ["symbol"],
                    },
                    "response_schema": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}, "last_price": {"type": "number"}},
                        "required": ["symbol", "last_price"],
                    },
                },
            },
            "input_schema": {
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
            "pulser_id": "pulser-1",
            "pulser_name": "YFinancePulser",
            "pulser_address": "http://127.0.0.1:8020",
        },
    )

    practice = PlazaPractice()
    practice.state.directory_pool = pool
    practice.state.plaza_url_for_store = "http://127.0.0.1:8011"

    restored = practice.state.ensure_pulse_directory_entries_from_pair_rows()
    pulse_row = pool.tables[PlazaPractice.DIRECTORY_TABLE][practice.state.stable_pulse_id("last_price")]

    assert restored == 1
    assert pulse_row["type"] == "Pulse"
    assert pulse_row["name"] == "last_price"
    assert pulse_row["meta"]["pulse_id"] == "urn:plaza:pulse:last.price"
    assert pulse_row["meta"]["pulse_definition"]["resource_type"] == "pulse_definition"


def test_plaza_status_exposes_available_pulsers_when_pair_id_differs_from_directory_id():
    """
    Exercise the test_plaza_status_exposes_available_pulsers_when_pair_id_differs_fr
    om_directory_id regression scenario.
    """
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    pool._Insert(
        PlazaPractice.DIRECTORY_TABLE,
        {
            "id": "pulse-1",
            "agent_id": "pulse-1",
            "name": "fifty_two_week_range",
            "type": "Pulse",
            "description": "52-week trading range.",
            "owner": "plaza",
            "address": "plaza://pulse/fifty_two_week_range",
            "meta": {"pulse_address": "plaza://pulse/fifty_two_week_range"},
            "card": {
                "agent_id": "pulse-1",
                "name": "fifty_two_week_range",
                "pit_type": "Pulse",
                "address": "plaza://pulse/fifty_two_week_range",
                "meta": {"pulse_address": "plaza://pulse/fifty_two_week_range"},
            },
        },
    )
    pool._Insert(
        PlazaPractice.DIRECTORY_TABLE,
        {
            "id": "pulser-directory-id",
            "agent_id": "pulser-directory-id",
            "name": "RangePulser",
            "type": "Pulser",
            "description": "Provides range data.",
            "owner": "plaza",
            "address": "http://127.0.0.1:8025",
            "meta": {},
            "card": {
                "agent_id": "pulser-directory-id",
                "name": "RangePulser",
                "pit_type": "Pulser",
                "address": "http://127.0.0.1:8025",
                "meta": {},
            },
        },
    )
    pool._Insert(
        PlazaPractice.PULSE_PULSER_TABLE,
        {
            "id": "pair-1",
            "pulse_name": "fifty_two_week_range",
            "pulse_address": "plaza://pulse/fifty_two_week_range",
            "pulser_id": "pulser-pair-id",
            "pulser_name": "RangePulser",
            "pulser_address": "http://127.0.0.1:8025",
            "input_schema": {"type": "object"},
        },
    )

    client = TestClient(agent.app)
    response = client.get("/api/plazas_status")
    assert response.status_code == 200

    agents = response.json()["plazas"][0]["agents"]
    pulse = next(entry for entry in agents if entry.get("pit_type") == "Pulse" and entry.get("name") == "fifty_two_week_range")
    assert pulse["available_pulser_count"] == 1
    assert len(pulse["available_pulsers"]) == 1
    assert pulse["available_pulsers"][0]["name"] == "RangePulser"
    assert pulse["available_pulsers"][0]["address"] == "http://127.0.0.1:8025"
    assert "last_active" in pulse["available_pulsers"][0]
    assert pulse["available_pulsers"][0]["pulse_definition"]["pulse_name"] == "fifty_two_week_range"
    assert pulse["available_pulsers"][0]["pulse_definition"]["input_schema"]["type"] == "object"


def test_plaza_status_hides_unfinished_pulse_pulser_pairs():
    """
    Exercise the test_plaza_status_hides_unfinished_pulse_pulser_pairs regression
    scenario.
    """
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    pool._Insert(
        PlazaPractice.DIRECTORY_TABLE,
        {
            "id": "pulse-1",
            "agent_id": "pulse-1",
            "name": "stock_snapshot",
            "type": "Pulse",
            "description": "Composite stock snapshot.",
            "owner": "plaza",
            "address": "plaza://pulse/stock_snapshot",
            "meta": {"pulse_address": "plaza://pulse/stock_snapshot"},
            "card": {
                "agent_id": "pulse-1",
                "name": "stock_snapshot",
                "pit_type": "Pulse",
                "address": "plaza://pulse/stock_snapshot",
                "meta": {"pulse_address": "plaza://pulse/stock_snapshot"},
            },
        },
    )
    pool._Insert(
        PlazaPractice.DIRECTORY_TABLE,
        {
            "id": "pulser-1",
            "agent_id": "pulser-1",
            "name": "PathPulser",
            "type": "Pulser",
            "description": "Path-based pulser.",
            "owner": "plaza",
            "address": "http://127.0.0.1:8030",
            "meta": {
                "supported_pulses": [
                    {
                        "name": "stock_snapshot",
                        "pulse_name": "stock_snapshot",
                        "pulse_address": "plaza://pulse/stock_snapshot",
                        "input_schema": {"type": "object"},
                        "is_complete": False,
                        "completion_status": "unfinished",
                        "completion_errors": ["result.currency is required."],
                    }
                ]
            },
            "card": {
                "agent_id": "pulser-1",
                "name": "PathPulser",
                "pit_type": "Pulser",
                "address": "http://127.0.0.1:8030",
                "meta": {
                    "supported_pulses": [
                        {
                            "name": "stock_snapshot",
                            "pulse_name": "stock_snapshot",
                            "pulse_address": "plaza://pulse/stock_snapshot",
                            "input_schema": {"type": "object"},
                            "is_complete": False,
                            "completion_status": "unfinished",
                            "completion_errors": ["result.currency is required."],
                        }
                    ]
                },
            },
        },
    )
    pool._Insert(
        PlazaPractice.PULSE_PULSER_TABLE,
        {
            "id": "pair-1",
            "pulse_name": "stock_snapshot",
            "pulse_address": "plaza://pulse/stock_snapshot",
            "pulser_id": "pulser-1",
            "pulser_name": "PathPulser",
            "pulser_address": "http://127.0.0.1:8030",
            "input_schema": {"type": "object"},
        },
    )

    client = TestClient(agent.app)
    response = client.get("/api/plazas_status")
    assert response.status_code == 200

    agents = response.json()["plazas"][0]["agents"]
    pulse = next(entry for entry in agents if entry.get("pit_type") == "Pulse" and entry.get("name") == "stock_snapshot")
    assert pulse["available_pulser_count"] == 0
    assert pulse["available_pulsers"] == []


def test_plaza_status_merges_pair_sample_parameters_into_available_pulsers():
    """
    Exercise the
    test_plaza_status_merges_pair_sample_parameters_into_available_pulsers
    regression scenario.
    """
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    pool._Insert(
        PlazaPractice.DIRECTORY_TABLE,
        {
            "id": "pulse-1",
            "agent_id": "pulse-1",
            "name": "sma",
            "type": "Pulse",
            "description": "Simple moving average.",
            "owner": "plaza",
            "address": "ai.demo.finance.technical.sma",
            "meta": {"pulse_address": "ai.demo.finance.technical.sma"},
            "card": {
                "agent_id": "pulse-1",
                "name": "sma",
                "pit_type": "Pulse",
                "address": "ai.demo.finance.technical.sma",
                "meta": {"pulse_address": "ai.demo.finance.technical.sma"},
            },
        },
    )
    pool._Insert(
        PlazaPractice.DIRECTORY_TABLE,
        {
            "id": "pulser-1",
            "agent_id": "pulser-1",
            "name": "TechnicalAnalysisPulser",
            "type": "Pulser",
            "description": "Technical indicators.",
            "owner": "plaza",
            "address": "http://127.0.0.1:8030",
            "meta": {
                "supported_pulses": [
                    {
                        "name": "sma",
                        "pulse_name": "sma",
                        "pulse_address": "ai.demo.finance.technical.sma",
                        "input_schema": {"type": "object"},
                    }
                ]
            },
            "card": {
                "agent_id": "pulser-1",
                "name": "TechnicalAnalysisPulser",
                "pit_type": "Pulser",
                "address": "http://127.0.0.1:8030",
                "meta": {
                    "supported_pulses": [
                        {
                            "name": "sma",
                            "pulse_name": "sma",
                            "pulse_address": "ai.demo.finance.technical.sma",
                            "input_schema": {"type": "object"},
                        }
                    ]
                },
            },
        },
    )
    pool._Insert(
        PlazaPractice.PULSE_PULSER_TABLE,
        {
            "id": "pair-1",
            "pulse_name": "sma",
            "pulse_address": "ai.demo.finance.technical.sma",
            "pulser_id": "pulser-1",
            "pulser_name": "TechnicalAnalysisPulser",
            "pulser_address": "http://127.0.0.1:8030",
            "input_schema": {"type": "object"},
            "pulse_definition": {
                "resource_type": "pulse_definition",
                "name": "sma",
                "test_data": {"symbol": "AAPL", "window": 20},
            },
        },
    )

    client = TestClient(agent.app)
    response = client.get("/api/plazas_status")
    assert response.status_code == 200

    agents = response.json()["plazas"][0]["agents"]
    pulse = next(entry for entry in agents if entry.get("pit_type") == "Pulse" and entry.get("name") == "sma")
    available_pulser = pulse["available_pulsers"][0]
    assert available_pulser["name"] == "TechnicalAnalysisPulser"
    assert available_pulser["pulse_definition"]["test_data"]["symbol"] == "AAPL"
    assert available_pulser["pulse_definition"]["test_data"]["window"] == 20


def test_plaza_ui_template_preserves_pulser_test_sample_fields():
    """
    Exercise the test_plaza_ui_template_preserves_pulser_test_sample_fields
    regression scenario.
    """
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    client = TestClient(agent.app)
    response = client.get("/plazas")

    assert response.status_code == 200
    assert "test_data: testData," in response.text
    assert "resolved_test_data: resolvedTestData," in response.text
    assert "test_data_path: testDataPath," in response.text
    assert "typeof definition.resolved_test_data === 'object'" in response.text


def test_plaza_ui_template_switches_auth_card_to_signed_in_state():
    """
    Exercise the test_plaza_ui_template_switches_auth_card_to_signed_in_state
    regression scenario.
    """
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    client = TestClient(agent.app)
    response = client.get("/plazas")

    assert response.status_code == 200
    assert 'id="auth-form-shell"' in response.text
    assert 'id="auth-session-actions"' in response.text
    assert "document.getElementById('auth-form-shell').classList.toggle('hidden', hasSession);" in response.text
    assert "document.getElementById('auth-session-actions').classList.toggle('hidden', !hasSession);" in response.text
    assert "const userBadgeLabel = currentUser.display_name || currentUser.username || currentUser.email || currentUser.id || 'Signed In';" in response.text


def test_plaza_ui_template_exposes_agent_config_policy_editor():
    """
    Exercise the test_plaza_ui_template_exposes_agent_config_policy_editor
    regression scenario.
    """
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    client = TestClient(agent.app)
    response = client.get("/plazas")

    assert response.status_code == 200
    assert "Remote UsePractice Policy JSON" in response.text
    assert "Remote UsePractice Audit JSON" in response.text
    assert "summarizeAgentConfigAccess" in response.text
    assert "Edit the stored remote <code>UsePractice(...)</code> access rules and audit settings for this AgentConfig." in response.text


def test_plaza_search_matches_ohlc_alias_pulses_against_pair_rows():
    """
    Exercise the test_plaza_search_matches_ohlc_alias_pulses_against_pair_rows
    regression scenario.
    """
    pool = InMemoryPool()
    pool._CreateTable(PlazaPractice.DIRECTORY_TABLE, None)
    pool._CreateTable(PlazaPractice.PULSE_PULSER_TABLE, None)

    pool._Insert(
        PlazaPractice.DIRECTORY_TABLE,
        {
            "id": "pulser-1",
            "agent_id": "pulser-1",
            "name": "LegacyOhlcPulser",
            "type": "Pulser",
            "description": "Provides daily OHLC bars.",
            "owner": "plaza",
            "address": "http://127.0.0.1:8031",
            "meta": {
                "supported_pulses": [
                    {
                        "name": "daily_ohlcv_bar",
                        "pulse_name": "daily_ohlcv_bar",
                        "pulse_address": "plaza://pulse/daily_ohlcv_bar",
                        "input_schema": {"type": "object"},
                    }
                ]
            },
            "card": {
                "agent_id": "pulser-1",
                "name": "LegacyOhlcPulser",
                "pit_type": "Pulser",
                "address": "http://127.0.0.1:8031",
                "meta": {
                    "supported_pulses": [
                        {
                            "name": "daily_ohlcv_bar",
                            "pulse_name": "daily_ohlcv_bar",
                            "pulse_address": "plaza://pulse/daily_ohlcv_bar",
                            "input_schema": {"type": "object"},
                        }
                    ]
                },
            },
        },
    )
    pool._Insert(
        PlazaPractice.PULSE_PULSER_TABLE,
        {
            "id": "pair-1",
            "pulse_name": "daily_ohlcv_bar",
            "pulse_address": "plaza://pulse/daily_ohlcv_bar",
            "pulser_id": "pulser-1",
            "pulser_name": "LegacyOhlcPulser",
            "pulser_address": "http://127.0.0.1:8031",
            "input_schema": {"type": "object"},
        },
    )

    practice = PlazaPractice()
    practice.state.directory_pool = pool
    practice.state.plaza_url_for_store = "http://127.0.0.1:8011"

    results = practice.state.search_entries(pit_type="Pulser", pulse_name="ohlc_bar_series")

    assert len(results) == 1
    assert results[0]["name"] == "LegacyOhlcPulser"


def test_plaza_status_collapses_ohlc_alias_pulses_into_canonical_card():
    """
    Exercise the test_plaza_status_collapses_ohlc_alias_pulses_into_canonical_card
    regression scenario.
    """
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    pulse_rows = [
        {
            "id": "pulse-daily",
            "agent_id": "pulse-daily",
            "name": "daily_ohlcv_bar",
            "type": "Pulse",
            "description": "Daily OHLC bars.",
            "owner": "plaza",
            "address": "plaza://pulse/daily_ohlcv_bar",
            "meta": {"pulse_address": "plaza://pulse/daily_ohlcv_bar"},
            "card": {
                "agent_id": "pulse-daily",
                "name": "daily_ohlcv_bar",
                "pit_type": "Pulse",
                "address": "plaza://pulse/daily_ohlcv_bar",
                "meta": {"pulse_address": "plaza://pulse/daily_ohlcv_bar"},
            },
        },
        {
            "id": "pulse-history",
            "agent_id": "pulse-history",
            "name": "daily_price_history",
            "type": "Pulse",
            "description": "Daily price history.",
            "owner": "plaza",
            "address": "plaza://pulse/daily_price_history",
            "meta": {"pulse_address": "plaza://pulse/daily_price_history"},
            "card": {
                "agent_id": "pulse-history",
                "name": "daily_price_history",
                "pit_type": "Pulse",
                "address": "plaza://pulse/daily_price_history",
                "meta": {"pulse_address": "plaza://pulse/daily_price_history"},
            },
        },
        {
            "id": "pulse-series",
            "agent_id": "pulse-series",
            "name": "ohlc_bar_series",
            "type": "Pulse",
            "description": "Canonical OHLC bar series.",
            "owner": "plaza",
            "address": "ai.demo.finance.price.ohlc_bar_series",
            "meta": {
                "pulse_address": "ai.demo.finance.price.ohlc_bar_series",
                "pulse_definition": {
                    "resource_type": "pulse_definition",
                    "name": "ohlc_bar_series",
                    "title": "Ohlc Bar Series",
                },
            },
            "card": {
                "agent_id": "pulse-series",
                "name": "ohlc_bar_series",
                "pit_type": "Pulse",
                "address": "ai.demo.finance.price.ohlc_bar_series",
                "meta": {
                    "pulse_address": "ai.demo.finance.price.ohlc_bar_series",
                    "pulse_definition": {
                        "resource_type": "pulse_definition",
                        "name": "ohlc_bar_series",
                        "title": "Ohlc Bar Series",
                    },
                },
            },
        },
    ]
    for row in pulse_rows:
        pool._Insert(PlazaPractice.DIRECTORY_TABLE, row)

    pulser_rows = [
        {
            "id": "pulser-daily",
            "agent_id": "pulser-daily",
            "name": "DailyPulser",
            "type": "Pulser",
            "description": "Returns daily bars.",
            "owner": "plaza",
            "address": "http://127.0.0.1:8031",
            "meta": {
                "supported_pulses": [
                    {
                        "name": "daily_ohlcv_bar",
                        "pulse_name": "daily_ohlcv_bar",
                        "pulse_address": "plaza://pulse/daily_ohlcv_bar",
                        "input_schema": {"type": "object"},
                    }
                ]
            },
            "card": {
                "agent_id": "pulser-daily",
                "name": "DailyPulser",
                "pit_type": "Pulser",
                "address": "http://127.0.0.1:8031",
                "meta": {
                    "supported_pulses": [
                        {
                            "name": "daily_ohlcv_bar",
                            "pulse_name": "daily_ohlcv_bar",
                            "pulse_address": "plaza://pulse/daily_ohlcv_bar",
                            "input_schema": {"type": "object"},
                        }
                    ]
                },
            },
        },
        {
            "id": "pulser-history",
            "agent_id": "pulser-history",
            "name": "HistoryPulser",
            "type": "Pulser",
            "description": "Returns daily price history.",
            "owner": "plaza",
            "address": "http://127.0.0.1:8032",
            "meta": {
                "supported_pulses": [
                    {
                        "name": "daily_price_history",
                        "pulse_name": "daily_price_history",
                        "pulse_address": "plaza://pulse/daily_price_history",
                        "input_schema": {"type": "object"},
                    }
                ]
            },
            "card": {
                "agent_id": "pulser-history",
                "name": "HistoryPulser",
                "pit_type": "Pulser",
                "address": "http://127.0.0.1:8032",
                "meta": {
                    "supported_pulses": [
                        {
                            "name": "daily_price_history",
                            "pulse_name": "daily_price_history",
                            "pulse_address": "plaza://pulse/daily_price_history",
                            "input_schema": {"type": "object"},
                        }
                    ]
                },
            },
        },
        {
            "id": "pulser-series",
            "agent_id": "pulser-series",
            "name": "SeriesPulser",
            "type": "Pulser",
            "description": "Returns canonical OHLC series.",
            "owner": "plaza",
            "address": "http://127.0.0.1:8033",
            "meta": {
                "supported_pulses": [
                    {
                        "name": "ohlc_bar_series",
                        "pulse_name": "ohlc_bar_series",
                        "pulse_address": "ai.demo.finance.price.ohlc_bar_series",
                        "input_schema": {"type": "object"},
                    }
                ]
            },
            "card": {
                "agent_id": "pulser-series",
                "name": "SeriesPulser",
                "pit_type": "Pulser",
                "address": "http://127.0.0.1:8033",
                "meta": {
                    "supported_pulses": [
                        {
                            "name": "ohlc_bar_series",
                            "pulse_name": "ohlc_bar_series",
                            "pulse_address": "ai.demo.finance.price.ohlc_bar_series",
                            "input_schema": {"type": "object"},
                        }
                    ]
                },
            },
        },
    ]
    for row in pulser_rows:
        pool._Insert(PlazaPractice.DIRECTORY_TABLE, row)

    pair_rows = [
        {
            "id": "pair-daily",
            "pulse_name": "daily_ohlcv_bar",
            "pulse_address": "plaza://pulse/daily_ohlcv_bar",
            "pulser_id": "pulser-daily",
            "pulser_name": "DailyPulser",
            "pulser_address": "http://127.0.0.1:8031",
            "input_schema": {"type": "object"},
        },
        {
            "id": "pair-history",
            "pulse_name": "daily_price_history",
            "pulse_address": "plaza://pulse/daily_price_history",
            "pulser_id": "pulser-history",
            "pulser_name": "HistoryPulser",
            "pulser_address": "http://127.0.0.1:8032",
            "input_schema": {"type": "object"},
        },
        {
            "id": "pair-series",
            "pulse_name": "ohlc_bar_series",
            "pulse_address": "ai.demo.finance.price.ohlc_bar_series",
            "pulser_id": "pulser-series",
            "pulser_name": "SeriesPulser",
            "pulser_address": "http://127.0.0.1:8033",
            "input_schema": {"type": "object"},
        },
    ]
    for row in pair_rows:
        pool._Insert(PlazaPractice.PULSE_PULSER_TABLE, row)

    client = TestClient(agent.app)
    response = client.get("/api/plazas_status")
    assert response.status_code == 200

    agents = response.json()["plazas"][0]["agents"]
    pulse_names = [entry.get("name") for entry in agents if entry.get("pit_type") == "Pulse"]
    assert pulse_names.count("ohlc_bar_series") == 1
    assert "daily_ohlcv_bar" not in pulse_names
    assert "daily_price_history" not in pulse_names

    pulse = next(entry for entry in agents if entry.get("pit_type") == "Pulse" and entry.get("name") == "ohlc_bar_series")
    assert pulse["available_pulser_count"] == 3
    assert {entry["name"] for entry in pulse["available_pulsers"]} == {
        "DailyPulser",
        "HistoryPulser",
        "SeriesPulser",
    }
    assert {entry["pulse_definition"]["pulse_name"] for entry in pulse["available_pulsers"]} == {
        "daily_ohlcv_bar",
        "daily_price_history",
        "ohlc_bar_series",
    }


def test_plaza_pulser_test_proxy_calls_remote_use_practice():
    """
    Exercise the test_plaza_pulser_test_proxy_calls_remote_use_practice regression
    scenario.
    """
    pool = InMemoryPool()
    agent = PlazaAgent(host="127.0.0.1", port=8011, pool=pool)
    agent.add_practice(PlazaPractice())

    pool._Insert(
        PlazaPractice.DIRECTORY_TABLE,
        {
            "id": "pulser-1",
            "agent_id": "pulser-1",
            "name": "RangePulser",
            "type": "Pulser",
            "description": "Provides range data.",
            "owner": "plaza",
            "address": "http://127.0.0.1:8025",
            "meta": {},
            "card": {
                "agent_id": "pulser-1",
                "name": "RangePulser",
                "pit_type": "Pulser",
                "address": "http://127.0.0.1:8025",
                "practices": [{"id": "get_pulse_data", "name": "Get Pulse Data", "tags": ["pulser", "pulse", "data"]}],
                "meta": {},
            },
        },
    )

    captured = {}

    class FakeAsyncResponse:
        """Response model for fake async payloads."""
        status_code = 200
        content = b'{"status":"ok","result":{"range":52}}'

        def json(self):
            """Handle JSON for the fake async response."""
            return {"status": "ok", "result": {"range": 52}}

    class FakeAsyncClient:
        """Represent a fake async client."""
        async def __aenter__(self):
            """Handle aenter for the fake async client."""
            return self

        async def __aexit__(self, exc_type, exc, tb):
            """Handle aexit for the fake async client."""
            return None

        async def post(self, url, json=None, timeout=30.0):
            """Post the value."""
            captured["url"] = url
            captured["json"] = json
            captured["timeout"] = timeout
            return FakeAsyncResponse()

    with patch("prompits.core.plaza.httpx.AsyncClient", return_value=FakeAsyncClient()):
        client = TestClient(agent.app)
        response = client.post(
            "/api/pulsers/test",
            json={
                "pulser_id": "pulser-1",
                "pulser_address": "http://127.0.0.1:8025",
                "practice_id": "get_pulse_data",
                "pulse_name": "fifty_two_week_range",
                "pulse_address": "plaza://pulse/fifty_two_week_range",
                "output_schema": {"type": "object", "properties": {"range": {"type": "number"}}},
                "input": {"symbol": "NVDA"},
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["result"]["range"] == 52
    assert captured["url"] == "http://127.0.0.1:8025/use_practice/get_pulse_data"
    assert captured["json"]["content"] == {
        "pulse_name": "fifty_two_week_range",
        "pulse_address": "plaza://pulse/fifty_two_week_range",
        "params": {"symbol": "NVDA"},
        "output_schema": {"type": "object", "properties": {"range": {"type": "number"}}},
    }
    assert captured["json"]["caller_agent_address"]["pit_id"]
    assert captured["json"]["caller_plaza_token"]


def test_plaza_register_batches_pulse_pulser_pair_persistence():
    """
    Exercise the test_plaza_register_batches_pulse_pulser_pair_persistence
    regression scenario.
    """
    pool = CountingBatchInMemoryPool()
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)

    client = TestClient(app)
    register = client.post("/register", json={
        "agent_name": "batch-pulser",
        "address": "http://127.0.0.1:8025",
        "pit_type": "Pulser",
        "card": {
            "name": "BatchPulser",
            "pit_type": "Pulser",
            "role": "pulser",
            "meta": {}
        },
        "pulse_pulser_pairs": [
            {"pulse_name": "last_price", "pulse_address": "plaza://pulse/last_price"},
            {"pulse_name": "trade_volume", "pulse_address": "plaza://pulse/trade_volume"},
            {"pulse_name": "company_profile", "pulse_address": "plaza://pulse/company_profile"},
        ]
    })
    assert register.status_code == 200

    pair_batch_calls = [
        call for call in pool.insert_many_calls
        if call[0] == PlazaPractice.PULSE_PULSER_TABLE
    ]
    assert len(pair_batch_calls) == 1
    assert len(pair_batch_calls[0][1]) == 3

    pair_single_calls = [
        call for call in pool.insert_calls
        if call[0] == PlazaPractice.PULSE_PULSER_TABLE
    ]
    assert pair_single_calls == []

    pair_table_exists_checks = [
        call for call in pool.table_exists_calls
        if call == PlazaPractice.PULSE_PULSER_TABLE
    ]
    assert len(pair_table_exists_checks) == 1


def test_plaza_register_batches_new_pulse_directory_persistence():
    """
    Exercise the test_plaza_register_batches_new_pulse_directory_persistence
    regression scenario.
    """
    pool = CountingBatchInMemoryPool()
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)

    client = TestClient(app)
    register = client.post("/register", json={
        "agent_name": "batch-pulser",
        "address": "http://127.0.0.1:8025",
        "pit_type": "Pulser",
        "card": {
            "name": "BatchPulser",
            "pit_type": "Pulser",
            "role": "pulser",
            "meta": {}
        },
        "pulse_pulser_pairs": [
            {"pulse_name": "last_price", "pulse_address": "plaza://pulse/last_price"},
            {"pulse_name": "trade_volume", "pulse_address": "plaza://pulse/trade_volume"},
            {"pulse_name": "company_profile", "pulse_address": "plaza://pulse/company_profile"},
        ]
    })
    assert register.status_code == 200

    pulse_directory_batch_calls = [
        call for call in pool.insert_many_calls
        if call[0] == PlazaPractice.DIRECTORY_TABLE and {row.get("type") for row in call[1]} == {"Pulse"}
    ]
    assert len(pulse_directory_batch_calls) == 1
    assert {row["name"] for row in pulse_directory_batch_calls[0][1]} == {
        "last_price",
        "trade_volume",
        "company_profile",
    }

    pulse_directory_single_calls = [
        call for call in pool.insert_calls
        if call[0] == PlazaPractice.DIRECTORY_TABLE and call[1].get("type") == "Pulse"
    ]
    assert pulse_directory_single_calls == []


def test_plaza_register_does_not_block_on_slow_pool_persistence():
    """
    Exercise the test_plaza_register_does_not_block_on_slow_pool_persistence
    regression scenario.
    """
    pool = SlowInsertInMemoryPool(delay=0.3)
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)

    client = TestClient(app)
    started = time.perf_counter()
    response = client.post("/register", json={
        "agent_name": "slow-pulser",
        "address": "http://127.0.0.1:8025",
        "pit_type": "Pulser",
        "card": {
            "name": "SlowPulser",
            "pit_type": "Pulser",
            "meta": {}
        },
        "pulse_pulser_pairs": [
            {"pulse_name": "last_price", "pulse_address": "plaza://pulse/last_price"},
        ]
    })
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert elapsed < 0.2

    time.sleep(0.7)
    assert "plaza_tokens" in pool.tables
    assert PlazaPractice.DIRECTORY_TABLE in pool.tables
    assert PlazaPractice.PULSE_PULSER_TABLE in pool.tables


def test_plaza_bootstrap_batches_directory_persistence():
    """
    Exercise the test_plaza_bootstrap_batches_directory_persistence regression
    scenario.
    """
    pool = CountingBatchInMemoryPool()
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)

    directory_batch_calls = [
        call for call in pool.insert_many_calls
        if call[0] == PlazaPractice.DIRECTORY_TABLE
    ]
    assert len(directory_batch_calls) == 1
    persisted_names = {row["name"] for row in directory_batch_calls[0][1]}
    assert "Plaza" in persisted_names
    assert "Schema: plaza_credentials" in persisted_names
    assert "Schema: agent_practices" in persisted_names

    directory_single_calls = [
        call for call in pool.insert_calls
        if call[0] == PlazaPractice.DIRECTORY_TABLE
    ]
    assert directory_single_calls == []


def test_plaza_register_dedupes_supported_pulses_and_explicit_batch_pairs():
    """
    Exercise the
    test_plaza_register_dedupes_supported_pulses_and_explicit_batch_pairs regression
    scenario.
    """
    pool = CountingBatchInMemoryPool()
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)

    client = TestClient(app)
    register = client.post("/register", json={
        "agent_name": "batch-pulser",
        "address": "http://127.0.0.1:8025",
        "pit_type": "Pulser",
        "card": {
            "name": "BatchPulser",
            "pit_type": "Pulser",
            "role": "pulser",
            "meta": {
                "supported_pulses": [
                    {
                        "name": "last_price",
                        "pulse_address": "plaza://pulse/last_price",
                        "input_schema": {
                            "type": "object",
                            "properties": {"symbol": {"type": "string"}},
                            "required": ["symbol"]
                        }
                    },
                    {
                        "name": "last_price",
                        "pulse_address": "plaza://pulse/last_price",
                        "input_schema": {
                            "type": "object",
                            "properties": {"symbol": {"type": "string"}},
                            "required": ["symbol"]
                        }
                    }
                ]
            }
        },
        "pulse_pulser_pairs": [
            {
                "pulse_name": "last_price",
                "pulse_address": "plaza://pulse/last_price",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"]
                }
            },
            {
                "pulse_name": "last_price",
                "pulse_address": "plaza://pulse/last_price",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"]
                }
            }
        ]
    })
    assert register.status_code == 200
    agent_id = register.json()["agent_id"]

    pair_batch_calls = [
        call for call in pool.insert_many_calls
        if call[0] == PlazaPractice.PULSE_PULSER_TABLE
    ]
    assert len(pair_batch_calls) == 1
    assert len(pair_batch_calls[0][1]) == 1

    pulse_pair_rows = list(pool.tables[PlazaPractice.PULSE_PULSER_TABLE].values())
    assert len(pulse_pair_rows) == 1
    assert pulse_pair_rows[0]["pulse_name"] == "last_price"
    assert len(practice.state.agent_cards[agent_id]["meta"]["supported_pulses"]) == 1


def test_plaza_search_dedupes_duplicate_pulsers_by_name_and_address():
    """
    Exercise the test_plaza_search_dedupes_duplicate_pulsers_by_name_and_address
    regression scenario.
    """
    practice = PlazaPractice()

    stale_card = practice.state.normalize_card_for_pit(
        {
            "name": "ADSPulser",
            "pit_type": "Pulser",
            "address": "http://127.0.0.1:8062",
            "meta": {
                "supported_pulses": [
                    {"pulse_name": "security_master_lookup", "pulse_address": "plaza://pulse/security_master_lookup"},
                    {"pulse_name": "security_master_lookup", "pulse_address": "plaza://pulse/security_master_lookup"},
                    {"pulse_name": "company_news", "pulse_address": "plaza://pulse/company_news"},
                ]
            },
        },
        "Pulser",
        agent_name="ADSPulser",
        address="http://127.0.0.1:8062",
    )
    fresh_card = practice.state.normalize_card_for_pit(
        {
            "name": "ADSPulser",
            "pit_type": "Pulser",
            "address": "http://127.0.0.1:8062",
            "meta": {
                "supported_pulses": [
                    {"pulse_name": "security_master_lookup", "pulse_address": "plaza://pulse/security_master_lookup"},
                    {"pulse_name": "company_profile", "pulse_address": "plaza://pulse/company_profile"},
                    {"pulse_name": "news_article", "pulse_address": "plaza://pulse/news_article"},
                ]
            },
        },
        "Pulser",
        agent_name="ADSPulser",
        address="http://127.0.0.1:8062",
    )

    practice.state.agent_cards = {
        "ads-stale": stale_card,
        "ads-fresh": fresh_card,
    }
    practice.state.agent_names_by_id = {
        "ads-stale": "ADSPulser",
        "ads-fresh": "ADSPulser",
    }
    practice.state.pit_types = {
        "ads-stale": "Pulser",
        "ads-fresh": "Pulser",
    }
    practice.state.last_active = {
        "ads-stale": 10.0,
        "ads-fresh": 20.0,
    }

    results = practice.state.search_entries(
        pit_type="Pulser",
        name="ADSPulser",
        use_persisted_fallback=False,
    )

    assert len(results) == 1
    assert results[0]["agent_id"] == "ads-fresh"
    assert len(results[0]["meta"]["supported_pulses"]) == 3


def test_register_relogin_with_agent_id_api_key_and_history_limit():
    """
    Exercise the test_register_relogin_with_agent_id_api_key_and_history_limit
    regression scenario.
    """
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent"
        }
    ))
    practice.mount(app)

    client = TestClient(app)

    first = client.post("/register", json={
        "agent_name": "alpha",
        "address": "http://127.0.0.1:9001"
    })
    assert first.status_code == 200
    first_data = first.json()
    agent_id = first_data["agent_id"]
    api_key = first_data["api_key"]
    assert first_data["issued_new_identity"] is True

    latest_token = first_data["token"]
    for i in range(12):
        relogin = client.post("/register", json={
            "agent_name": "alpha",
            "address": f"http://127.0.0.1:{9002 + i}",
            "agent_id": agent_id,
            "api_key": api_key
        })
        assert relogin.status_code == 200
        relogin_data = relogin.json()
        assert relogin_data["agent_id"] == agent_id
        assert relogin_data["api_key"] == api_key
        assert relogin_data["issued_new_identity"] is False
        latest_token = relogin_data["token"]

    search = client.get("/search", headers={"Authorization": f"Bearer {latest_token}"})
    assert search.status_code == 200
    records = [entry for entry in search.json() if entry["name"] == "alpha"]
    assert len(records) == 1
    entry = records[0]
    assert entry["agent_id"] == agent_id
    assert len(entry["login_history"]) == 10
    assert all(item["event"] == "relogin" for item in entry["login_history"])


def test_plaza_self_heartbeat_updates_last_active():
    """
    Exercise the test_plaza_self_heartbeat_updates_last_active regression scenario.
    """
    app = FastAPI()
    practice = PlazaPractice(self_heartbeat_interval=1)
    practice.bind(SimpleNamespace(
        name="Plaza",
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent"
        }
    ))
    practice.mount(app)

    first = practice.last_active.get("Plaza", 0)
    time.sleep(1.2)
    second = practice.last_active.get("Plaza", 0)
    assert second > first


def test_login_history_keeps_multiple_entries_for_same_agent_name():
    """
    Exercise the test_login_history_keeps_multiple_entries_for_same_agent_name
    regression scenario.
    """
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent"
        }
    ))
    practice.mount(app)
    client = TestClient(app)

    r1 = client.post("/register", json={
        "agent_name": "alice",
        "address": "http://127.0.0.1:8012"
    })
    assert r1.status_code == 200
    body1 = r1.json()
    agent_id = body1["agent_id"]
    api_key = body1["api_key"]

    r2 = client.post("/register", json={
        "agent_name": "alice",
        "address": "http://127.0.0.1:8012",
        "agent_id": agent_id,
        "api_key": api_key
    })
    assert r2.status_code == 200
    token2 = r2.json()["token"]

    search = client.get("/search", headers={"Authorization": f"Bearer {token2}"})
    assert search.status_code == 200
    alice = next(item for item in search.json() if item["agent_id"] == agent_id)
    history = alice.get("login_history", [])
    assert len(history) >= 2
    assert history[-1]["event"] == "relogin"


def test_plaza_registration_marks_agents_that_do_not_accept_inbound_from_plaza():
    """
    Exercise the
    test_plaza_registration_marks_agents_that_do_not_accept_inbound_from_plaza
    regression scenario.
    """
    app = FastAPI()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent"
        }
    ))
    practice.mount(app)
    client = TestClient(app)

    register = client.post("/register", json={
        "agent_name": "nat-agent",
        "address": "http://10.0.0.25:8012",
        "accepts_inbound_from_plaza": False,
        "card": {
            "name": "nat-agent",
            "meta": {"deployment": "private-subnet"}
        }
    })
    assert register.status_code == 200
    token = register.json()["token"]
    agent_id = register.json()["agent_id"]

    search = client.get("/search", headers={"Authorization": f"Bearer {token}"})
    assert search.status_code == 200
    entry = next(item for item in search.json() if item["agent_id"] == agent_id)
    assert entry["accepts_inbound_from_plaza"] is False
    assert entry["accepts_direct_call"] is False
    assert entry["connectivity_mode"] == "outbound-only"
    assert entry["card"]["accepts_inbound_from_plaza"] is False
    assert entry["card"]["accepts_direct_call"] is False
    assert entry["card"]["connectivity_mode"] == "outbound-only"
    assert entry["card"]["meta"]["accepts_inbound_from_plaza"] is False
    assert entry["card"]["meta"]["accepts_direct_call"] is False
    assert entry["card"]["meta"]["deployment"] == "private-subnet"


def test_plaza_restart_restores_registered_agent_state_from_pool():
    """
    Exercise the test_plaza_restart_restores_registered_agent_state_from_pool
    regression scenario.
    """
    pool = InMemoryPool()

    def build_practice():
        """Build the practice."""
        practice = PlazaPractice()
        practice.bind(SimpleNamespace(
            name="Plaza",
            pool=pool,
            host="127.0.0.1",
            port=8011,
            agent_card={
                "name": "Plaza",
                "role": "coordinator",
                "tags": ["mediator"],
                "address": "http://127.0.0.1:8011",
                "pit_type": "Agent",
                "agent_id": "plaza-self"
            }
        ))
        return practice

    app_one = FastAPI()
    practice_one = build_practice()
    practice_one.mount(app_one)
    client_one = TestClient(app_one)

    register = client_one.post("/register", json={
        "agent_name": "alpha",
        "address": "http://127.0.0.1:9001",
        "pit_type": "Agent",
        "card": {
            "name": "alpha",
            "description": "restorable agent",
            "owner": "ops",
            "meta": {"mode": "restored"},
            "practices": [{"id": "echo-practice", "path": "/echo"}],
        }
    })
    assert register.status_code == 200
    register_data = register.json()
    token = register_data["token"]
    agent_id = register_data["agent_id"]

    app_two = FastAPI()
    practice_two = build_practice()
    practice_two.mount(app_two)
    practice_two.state._hydrate_plaza_state()
    client_two = TestClient(app_two)

    search = client_two.get("/search", headers={"Authorization": f"Bearer {token}"})
    assert search.status_code == 200
    restored = next(item for item in search.json() if item["agent_id"] == agent_id)
    assert restored["name"] == "alpha"
    assert restored["card"]["meta"]["mode"] == "restored"
    assert restored["card"]["practices"][0]["id"] == "echo-practice"


def test_login_history_loads_lazily_once_per_agent():
    """
    Exercise the test_login_history_loads_lazily_once_per_agent regression scenario.
    """
    pool = InMemoryPool()
    login_history_reads = 0
    original_get_table_data = pool._GetTableData

    def counted_get_table_data(table_name, id_or_where=None, table_schema=None):
        """Handle counted get table data."""
        nonlocal login_history_reads
        if table_name == "plaza_login_history":
            login_history_reads += 1
        return original_get_table_data(table_name, id_or_where=id_or_where, table_schema=table_schema)

    pool._GetTableData = counted_get_table_data

    def build_practice():
        """Build the practice."""
        practice = PlazaPractice()
        practice.bind(SimpleNamespace(
            name="Plaza",
            pool=pool,
            host="127.0.0.1",
            port=8011,
            agent_card={
                "name": "Plaza",
                "role": "coordinator",
                "tags": ["mediator"],
                "address": "http://127.0.0.1:8011",
                "pit_type": "Agent",
                "agent_id": "plaza-self"
            }
        ))
        return practice

    app_one = FastAPI()
    practice_one = build_practice()
    practice_one.mount(app_one)
    client_one = TestClient(app_one)

    register = client_one.post("/register", json={
        "agent_name": "alpha",
        "address": "http://127.0.0.1:9001",
        "pit_type": "Agent",
        "card": {"name": "alpha"}
    })
    assert register.status_code == 200
    token = register.json()["token"]
    agent_id = register.json()["agent_id"]
    assert login_history_reads == 0

    app_two = FastAPI()
    practice_two = build_practice()
    practice_two.mount(app_two)
    practice_two.state._hydrate_plaza_state()
    assert login_history_reads == 0

    client_two = TestClient(app_two)
    search_one = client_two.get(
        "/search",
        params={"agent_id": agent_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert search_one.status_code == 200
    assert login_history_reads == 1

    search_two = client_two.get(
        "/search",
        params={"agent_id": agent_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert search_two.status_code == 200
    assert login_history_reads == 1


def test_directory_table_and_search_filters():
    """Exercise the test_directory_table_and_search_filters regression scenario."""
    app = FastAPI()
    pool = InMemoryPool()
    practice = PlazaPractice()
    practice.bind(SimpleNamespace(
        name="Plaza",
        pool=pool,
        host="127.0.0.1",
        port=8011,
        agent_card={
            "name": "Plaza",
            "role": "coordinator",
            "tags": ["mediator"],
            "address": "http://127.0.0.1:8011",
            "pit_type": "Agent",
            "agent_id": "plaza-self"
        }
    ))
    practice.mount(app)
    client = TestClient(app)

    register = client.post("/register", json={
        "agent_name": "pulse-node",
        "address": "http://127.0.0.1:9001",
        "pit_type": "Pulse",
        "card": {
            "name": "pulse-node",
            "description": "Realtime market pulse collector",
            "owner": "ops-team",
            "meta": {"domain": "finance", "region": "us"},
            "role": "worker"
        }
    })
    assert register.status_code == 200
    token = register.json()["token"]
    aid = register.json()["agent_id"]

    assert PlazaPractice.DIRECTORY_TABLE in pool.tables
    assert aid in pool.tables[PlazaPractice.DIRECTORY_TABLE]

    headers = {"Authorization": f"Bearer {token}"}
    resp_type = client.get("/search", params={"type": "Pulse"}, headers=headers)
    resp_name = client.get("/search", params={"name": "pulse-node"}, headers=headers)
    resp_desc = client.get("/search", params={"description": "market pulse"}, headers=headers)
    resp_owner = client.get("/search", params={"owner": "ops-team"}, headers=headers)
    resp_meta = client.get("/search", params={"meta": "finance"}, headers=headers)

    for r in [resp_type, resp_name, resp_desc, resp_owner, resp_meta]:
        assert r.status_code == 200
        assert any(item.get("agent_id") == aid for item in r.json())
