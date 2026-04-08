"""
Regression tests for Agent Pool Credentials.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_agent_can_delete_practice_at_runtime_and_persist_deletion`,
`test_agent_register_does_not_burn_through_retries_while_plaza_is_starting`,
`test_agent_register_retries_plaza_calls_with_long_timeout`, and
`test_agent_registers_pool_operation_practices_and_can_use_them`, helping guard against
regressions as the packages evolve.
"""

import os
import sys
import asyncio
import logging
import time
import uuid
from unittest.mock import patch
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import pytest
from fastapi import HTTPException
from prompits.agents.standby import StandbyAgent
from prompits.core.pit import Pit, PitAddress
from prompits.core.init_schema import plaza_credentials_table_schema
from prompits.core.pool import Pool, PoolCap
from prompits.core.practice import Practice
from prompits.practices.plaza import PlazaPractice
from prompits.practices.plaza import PlazaCredentialStore


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

    def _TableExists(self, table_name):
        """Return whether the table exists for value."""
        return table_name in self.tables

    def _CreateTable(self, table_name, schema):
        """Internal helper to create the table."""
        self.tables.setdefault(table_name, {})
        return True

    def _Insert(self, table_name, data):
        """Internal helper for insert."""
        self.tables.setdefault(table_name, {})
        row_id = data.get("id") or data.get("agent_id")
        self.tables[table_name][row_id] = dict(data)
        return True

    def _GetTableData(self, table_name, id_or_where=None, table_schema=None):
        """Internal helper to return the table data."""
        table = self.tables.get(table_name, {})
        rows = list(table.values())
        if isinstance(id_or_where, dict):
            matched = []
            for row in rows:
                if all(row.get(k) == v for k, v in id_or_where.items()):
                    matched.append(dict(row))
            return matched
        return [dict(r) for r in rows]

    def _Query(self, query, params=None):
        """Internal helper to query the value."""
        return []

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
            executor=lambda table_name, schema, **_: self._CreateTable(table_name, self._coerce_table_schema(schema)),
        )

    def table_exists_practice(self):
        """Return whether the table exists for practice."""
        return self._build_operation_practice(
            operation_id="pool-table-exists",
            name="Pool Table Exists",
            description="Check whether a table exists in the in-memory pool.",
            parameters={"table_name": {"type": "string"}},
            executor=lambda table_name, **_: self._TableExists(table_name),
        )

    def insert_practice(self):
        """Handle insert practice for the in memory pool."""
        return self._build_operation_practice(
            operation_id="pool-insert",
            name="Pool Insert",
            description="Insert one row into the in-memory pool.",
            parameters={"table_name": {"type": "string"}, "data": {"type": "object"}},
            executor=lambda table_name, data, **_: self._Insert(table_name, data),
        )

    def query_practice(self):
        """Query the practice."""
        return self._build_operation_practice(
            operation_id="pool-query",
            name="Pool Query",
            description="Execute a query against the in-memory pool.",
            parameters={"query": {"type": "string"}, "params": {"type": "object"}},
            executor=lambda query, params=None, **_: self._Query(query, params),
        )

    def get_table_data_practice(self):
        """Return the table data practice."""
        return self._build_operation_practice(
            operation_id="pool-get-table-data",
            name="Pool Get Table Data",
            description="Read rows from the in-memory pool.",
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
            description="Connect the in-memory pool.",
            parameters={},
            executor=lambda **_: self.connect(),
        )

    def disconnect_practice(self):
        """Disconnect the practice."""
        return self._build_operation_practice(
            operation_id="pool-disconnect",
            name="Pool Disconnect",
            description="Disconnect the in-memory pool.",
            parameters={},
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
            executor=lambda query, limit=10, table_name=None, **_: self.search_memory(
                query=query,
                limit=limit,
                table_name=table_name,
            ),
        )


class CountingBatchInMemoryPool(InMemoryPool):
    """Represent a counting batch in memory pool."""
    def __init__(self):
        """Initialize the counting batch in memory pool."""
        super().__init__()
        self.insert_calls = []
        self.insert_many_calls = []

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


class FakeResponse:
    """Response model for fake payloads."""
    def __init__(self, payload, status_code=200):
        """Initialize the fake response."""
        self._payload = payload
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        """Handle JSON for the fake response."""
        return self._payload


class EchoPractice(Practice):
    """Practice implementation for echo workflows."""
    def __init__(self):
        """Initialize the echo practice."""
        super().__init__(
            name="Echo Practice",
            description="Echoes content back",
            id="echo-practice"
        )

    def mount(self, app):
        """Mount the value."""
        return None

    def execute(self, **kwargs):
        """Handle execute for the echo practice."""
        return {"echo": kwargs}


class AsyncEchoPractice(Practice):
    """Practice implementation for async echo workflows."""
    def __init__(self):
        """Initialize the async echo practice."""
        super().__init__(
            name="Async Echo Practice",
            description="Echoes content asynchronously",
            id="async-echo-practice"
        )

    def mount(self, app):
        """Mount the value."""
        return None

    async def execute(self, **kwargs):
        """Handle execute for the async echo practice."""
        await asyncio.sleep(0)
        return {"async_echo": kwargs}


class MultiEndpointPractice(Practice):
    """Practice implementation for multi endpoint workflows."""
    def __init__(self):
        """Initialize the multi endpoint practice."""
        super().__init__(
            name="Multi Endpoint Practice",
            description="Provides multiple callable endpoints",
            id="multi-endpoint-practice"
        )

    def mount(self, app):
        """Mount the value."""
        return None

    def get_callable_endpoints(self):
        """Return the callable endpoints."""
        return [
            {
                "name": "Echo Endpoint",
                "description": "Echo endpoint",
                "id": "echo-endpoint",
                "cost": 5,
                "tags": ["echo"],
                "examples": [],
                "inputModes": ["json"],
                "outputModes": ["json"],
                "parameters": {},
                "path": "/echo"
            },
            {
                "name": "Ping Endpoint",
                "description": "Ping endpoint",
                "id": "ping-endpoint",
                "tags": ["ping"],
                "examples": [],
                "inputModes": ["json"],
                "outputModes": ["json"],
                "parameters": {},
                "path": "/ping"
            }
        ]


def test_pit_can_register_itself_on_plaza():
    """Exercise the test_pit_can_register_itself_on_plaza regression scenario."""
    pit = Pit(name="schema-x", description="schema pit")
    sent_payloads = []

    def fake_post(url, json=None, timeout=5, **kwargs):
        """Handle fake post."""
        sent_payloads.append({"url": url, "payload": dict(json or {}), "timeout": timeout})
        return FakeResponse({"status": "registered", "agent_id": "pit-123", "api_key": "key-123"})

    with patch("prompits.core.pit.requests.post", side_effect=fake_post):
        response = pit.register(
            plaza_url="http://127.0.0.1:8011",
            card={"pit_type": "Schema"},
            address="http://127.0.0.1:8123",
            pit_type="Schema",
            accepts_inbound_from_plaza=False,
        )

    assert response.status_code == 200
    assert pit.address.plazas == ["http://127.0.0.1:8011"]
    assert len(sent_payloads) == 1
    record = sent_payloads[0]
    assert record["url"] == "http://127.0.0.1:8011/register"
    assert record["payload"]["agent_name"] == "schema-x"
    assert record["payload"]["pit_type"] == "Schema"
    assert record["payload"]["accepts_inbound_from_plaza"] is False
    assert record["payload"]["accepts_direct_call"] is False
    assert "pit_address" in record["payload"]["card"]
    assert record["payload"]["card"]["accepts_inbound_from_plaza"] is False
    assert record["payload"]["card"]["accepts_direct_call"] is False
    assert record["payload"]["card"]["connectivity_mode"] == "outbound-only"


def test_agent_persists_and_reuses_plaza_credentials_from_pool():
    """
    Exercise the test_agent_persists_and_reuses_plaza_credentials_from_pool
    regression scenario.
    """
    pool = InMemoryPool()
    plaza_url = "http://127.0.0.1:8011"
    sent_payloads = []

    def fake_post(url, json=None, timeout=5, **kwargs):
        """Handle fake post."""
        sent_payloads.append(dict(json or {}))
        if json and json.get("agent_id") and json.get("api_key"):
            return FakeResponse({
                "status": "registered",
                "token": "token-reused",
                "expires_in": 3600,
                "agent_id": json["agent_id"],
                "api_key": json["api_key"]
            })
        return FakeResponse({
            "status": "registered",
            "token": "token-new",
            "expires_in": 3600,
            "agent_id": "issued-id-123",
            "api_key": "issued-key-abc"
        })

    with patch("prompits.agents.base.requests.post", side_effect=fake_post), patch(
        "prompits.agents.base.BaseAgent._start_heartbeat_thread",
        return_value=True,
    ):
        first = StandbyAgent(name="alice", plaza_url=plaza_url, pool=pool)
        first.register()
        assert first.agent_id == "issued-id-123"
        assert first.api_key == "issued-key-abc"

        second = StandbyAgent(name="alice", plaza_url=plaza_url, pool=pool)
        second.register()

    assert len(sent_payloads) >= 2
    first_payload = sent_payloads[0]
    second_payload = sent_payloads[1]
    assert "agent_id" not in first_payload
    assert "api_key" not in first_payload
    assert second_payload["agent_id"] == "issued-id-123"
    assert second_payload["api_key"] == "issued-key-abc"
    assert second.pit_address.pit_id == "issued-id-123"
    assert "http://127.0.0.1:8011" in second.pit_address.plazas
    assert second.agent_card.get("pit_address", {}).get("pit_id") == "issued-id-123"
    stored_rows = pool._GetTableData("plaza_credentials", {"agent_name": "alice"})
    assert len(stored_rows) == 1
    assert stored_rows[0]["id"] == str(
        uuid.uuid5(uuid.NAMESPACE_URL, "plaza-credentials:alice:http://127.0.0.1:8011")
    )
    assert stored_rows[0]["plaza_url"] == plaza_url


def test_agent_loads_credentials_for_its_own_plaza_only():
    """
    Exercise the test_agent_loads_credentials_for_its_own_plaza_only regression
    scenario.
    """
    pool = InMemoryPool()
    PlazaCredentialStore(pool=pool).save("alice", "id-plaza-1", "key-plaza-1", "http://127.0.0.1:8011")
    PlazaCredentialStore(pool=pool).save("alice", "id-plaza-2", "key-plaza-2", "http://127.0.0.1:8012")

    agent = StandbyAgent(name="alice", plaza_url="http://127.0.0.1:8012", pool=pool)
    agent._load_plaza_credentials_from_pool()

    assert agent.agent_id == "id-plaza-2"
    assert agent.api_key == "key-plaza-2"


def test_agent_loads_legacy_string_key_credentials_from_pool():
    """
    Exercise the test_agent_loads_legacy_string_key_credentials_from_pool regression
    scenario.
    """
    pool = InMemoryPool()
    plaza_url = "http://127.0.0.1:8011"
    pool._CreateTable("plaza_credentials", plaza_credentials_table_schema())
    pool._Insert(
        "plaza_credentials",
        {
            "id": "alice:http://127.0.0.1:8011",
            "agent_id": "legacy-id",
            "agent_name": "alice",
            "api_key": "legacy-key",
            "plaza_url": plaza_url,
            "updated_at": "2026-03-20T00:00:00+00:00",
        },
    )

    agent = StandbyAgent(name="alice", plaza_url=plaza_url, pool=pool)
    agent._load_plaza_credentials_from_pool()

    assert agent.agent_id == "legacy-id"
    assert agent.api_key == "legacy-key"


def test_agent_waits_and_retries_same_stored_credentials_when_plaza_rejects_them():
    """
    Exercise the
    test_agent_waits_and_retries_same_stored_credentials_when_plaza_rejects_them
    regression scenario.
    """
    pool = InMemoryPool()
    plaza_url = "http://127.0.0.1:8011"
    sent_payloads = []
    sleep_calls = []

    # Seed stale credentials in pool.
    PlazaCredentialStore(pool=pool).save("alice", "stale-id", "stale-key", plaza_url)

    def fake_post(url, json=None, timeout=5, **kwargs):
        """Handle fake post."""
        sent_payloads.append(dict(json or {}))
        if json and json.get("agent_id") == "stale-id" and len(sent_payloads) == 1:
            return FakeResponse({"detail": "Invalid agent_id or api_key"}, status_code=401)
        if json and json.get("agent_id") == "stale-id":
            return FakeResponse({
                "status": "registered",
                "token": "token-retried",
                "expires_in": 3600,
                "agent_id": "stale-id",
                "api_key": "stale-key"
            })
        return FakeResponse({"detail": "unexpected request"}, status_code=500)

    def fake_sleep(seconds):
        """Handle fake sleep."""
        sleep_calls.append(seconds)

    with patch("prompits.agents.base.requests.post", side_effect=fake_post), patch(
        "prompits.agents.base.time.sleep",
        side_effect=fake_sleep,
    ), patch(
        "prompits.agents.base.BaseAgent._start_heartbeat_thread",
        return_value=True,
    ):
        agent = StandbyAgent(name="alice", plaza_url=plaza_url, pool=pool)
        agent.register()
        assert agent.agent_id == "stale-id"
        assert agent.api_key == "stale-key"
        assert agent.plaza_token == "token-retried"

    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(60, abs=0.1)
    assert len(sent_payloads) == 2
    assert all(payload.get("agent_id") == "stale-id" for payload in sent_payloads)
    assert all(payload.get("api_key") == "stale-key" for payload in sent_payloads)
    assert all("agent_id" in payload for payload in sent_payloads)


def test_agent_register_retries_plaza_calls_with_long_timeout():
    """
    Exercise the test_agent_register_retries_plaza_calls_with_long_timeout
    regression scenario.
    """
    attempts = []

    def fake_post(url, json=None, timeout=5, **kwargs):
        """Handle fake post."""
        attempts.append({"url": url, "payload": dict(json or {}), "timeout": timeout})
        if len(attempts) <= 5:
            raise requests.ReadTimeout("plaza timed out")
        return FakeResponse({
            "status": "registered",
            "token": "token-new",
            "expires_in": 3600,
            "agent_id": "issued-id-123",
            "api_key": "issued-key-abc"
        })

    with patch("prompits.agents.base.requests.post", side_effect=fake_post), patch(
        "prompits.agents.base.BaseAgent._start_heartbeat_thread",
        return_value=True,
    ):
        agent = StandbyAgent(name="alice", plaza_url="http://127.0.0.1:8011")
        response = agent.register()

    assert response.status_code == 200
    assert len(attempts) == 6
    assert all(entry["url"] == "http://127.0.0.1:8011/register" for entry in attempts)
    assert all(entry["timeout"] == 30 for entry in attempts)


def test_agent_reconnect_loop_waits_60_seconds_between_attempts_until_success():
    """
    Exercise the
    test_agent_reconnect_loop_waits_60_seconds_between_attempts_until_success
    regression scenario.
    """
    agent = StandbyAgent(name="alice", plaza_url="http://127.0.0.1:8011")
    sleep_calls = []
    register_calls = []

    def fake_sleep(seconds):
        """Handle fake sleep."""
        sleep_calls.append(seconds)

    def fake_register(*, start_reconnect_on_failure=True, request_retries=None):
        """Handle fake register."""
        register_calls.append(
            {
                "start_reconnect_on_failure": start_reconnect_on_failure,
                "request_retries": request_retries,
            }
        )
        if len(register_calls) == 1:
            return None
        agent.plaza_token = "token-restored"
        agent.token_expires_at = time.time() + 3600
        return FakeResponse({"status": "registered", "token": "token-restored"})

    with patch.object(agent, "register", side_effect=fake_register), patch(
        "prompits.agents.base.time.sleep",
        side_effect=fake_sleep,
    ):
        agent._reconnect_loop(initial_delay=60)

    assert sleep_calls == [60, 60]
    assert register_calls == [
        {"start_reconnect_on_failure": False, "request_retries": 0},
        {"start_reconnect_on_failure": False, "request_retries": 0},
    ]
    assert agent.plaza_token == "token-restored"


def test_agent_heartbeat_schedules_reconnect_once_while_waiting_for_token(caplog):
    """
    Exercise the
    test_agent_heartbeat_schedules_reconnect_once_while_waiting_for_token regression
    scenario.
    """
    agent = StandbyAgent(name="alice", plaza_url="http://127.0.0.1:8011")
    sleep_calls = []

    def fake_sleep(seconds):
        """Handle fake sleep."""
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 3:
            raise SystemExit()

    with caplog.at_level(logging.INFO, logger="prompits.agents.base"), patch(
        "prompits.agents.base.time.sleep",
        side_effect=fake_sleep,
    ), patch.object(
        agent,
        "_has_active_reconnect_thread",
        side_effect=[False, True],
    ), patch.object(agent, "_schedule_reconnect") as schedule_reconnect:
        with pytest.raises(SystemExit):
            agent._heartbeat_loop()

    assert sleep_calls == [agent.PLAZA_HEARTBEAT_INTERVAL] * 3
    schedule_reconnect.assert_called_once_with(
        "heartbeat waiting for plaza token",
        initial_delay=agent.PLAZA_RECONNECT_INTERVAL,
    )
    assert "Skipping heartbeat, no valid token." not in caplog.text


def test_agent_heartbeat_switches_to_reconnect_mode_when_plaza_is_starting():
    """
    Exercise the
    test_agent_heartbeat_switches_to_reconnect_mode_when_plaza_is_starting
    regression scenario.
    """
    agent = StandbyAgent(name="alice", plaza_url="http://127.0.0.1:8011")
    agent.agent_id = "alice-id"
    agent.plaza_token = "token-live"
    agent.token_expires_at = time.time() + 3600
    sleep_calls = []

    def fake_sleep(seconds):
        """Handle fake sleep."""
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 2:
            raise SystemExit()

    with patch("prompits.agents.base.time.sleep", side_effect=fake_sleep), patch.object(
        agent,
        "_plaza_post",
        return_value=FakeResponse({"detail": "Starting"}, status_code=503),
    ), patch.object(agent, "_schedule_reconnect") as schedule_reconnect:
        with pytest.raises(SystemExit):
            agent._heartbeat_loop()

    assert sleep_calls == [agent.PLAZA_HEARTBEAT_INTERVAL] * 2
    schedule_reconnect.assert_called_once_with("plaza starting")


def test_agent_register_does_not_burn_through_retries_while_plaza_is_starting():
    """
    Exercise the
    test_agent_register_does_not_burn_through_retries_while_plaza_is_starting
    regression scenario.
    """
    attempts = []

    def fake_post(url, json=None, timeout=5, **kwargs):
        """Handle fake post."""
        attempts.append({"url": url, "payload": dict(json or {}), "timeout": timeout})
        return FakeResponse({"detail": "Starting"}, status_code=503)

    with patch("prompits.agents.base.requests.post", side_effect=fake_post), patch(
        "prompits.agents.base.BaseAgent._start_reconnect_thread",
        return_value=True,
    ) as reconnect_thread:
        agent = StandbyAgent(name="alice", plaza_url="http://127.0.0.1:8011")
        response = agent.register()

    assert response.status_code == 503
    assert len(attempts) == 1
    reconnect_thread.assert_called_once_with(initial_delay=None)


def test_agent_persists_practice_metadata_in_pool():
    """
    Exercise the test_agent_persists_practice_metadata_in_pool regression scenario.
    """
    pool = InMemoryPool()
    agent = StandbyAgent(name="alice", pool=pool)
    agent.add_practice(EchoPractice())

    rows = pool._GetTableData("agent_practices", {"agent_name": "alice"})
    row_by_id = {row["practice_id"]: row for row in rows}

    assert "mailbox" in row_by_id
    assert "echo-practice" in row_by_id
    assert row_by_id["echo-practice"]["is_deleted"] is False
    assert row_by_id["echo-practice"]["practice_data"]["name"] == "Echo Practice"
    assert row_by_id["echo-practice"]["practice_data"]["cost"] == 0

    reloaded = StandbyAgent(name="alice", pool=pool)
    card_practice_ids = {p.get("id") for p in reloaded.agent_card.get("practices", [])}
    assert "echo-practice" in card_practice_ids
    echo_metadata = next(p for p in reloaded.agent_card.get("practices", []) if p.get("id") == "echo-practice")
    assert echo_metadata["cost"] == 0


def test_agent_batches_initial_practice_bootstrap_persistence():
    """
    Exercise the test_agent_batches_initial_practice_bootstrap_persistence
    regression scenario.
    """
    pool = CountingBatchInMemoryPool()
    StandbyAgent(name="alice", pool=pool)

    batch_calls = [
        call for call in pool.insert_many_calls
        if call[0] == "agent_practices"
    ]
    assert len(batch_calls) == 1
    persisted_ids = {row["practice_id"] for row in batch_calls[0][1]}
    assert "mailbox" in persisted_ids
    assert "pool-connect" in persisted_ids
    assert "pool-search-memory" in persisted_ids

    single_calls = [
        call for call in pool.insert_calls
        if call[0] == "agent_practices"
    ]
    assert single_calls == []


def test_agent_can_delete_practice_at_runtime_and_persist_deletion():
    """
    Exercise the test_agent_can_delete_practice_at_runtime_and_persist_deletion
    regression scenario.
    """
    pool = InMemoryPool()
    agent = StandbyAgent(name="alice", pool=pool)
    agent.add_practice(EchoPractice())

    assert agent.delete_practice("echo-practice") is True
    assert all(p.id != "echo-practice" for p in agent.practices)
    assert all(p.get("id") != "echo-practice" for p in agent.agent_card.get("practices", []))

    rows = pool._GetTableData("agent_practices", {"agent_name": "alice"})
    row_by_id = {row["practice_id"]: row for row in rows}
    assert row_by_id["echo-practice"]["is_deleted"] is True

    reloaded = StandbyAgent(name="alice", pool=pool)
    card_practice_ids = {p.get("id") for p in reloaded.agent_card.get("practices", [])}
    assert "echo-practice" not in card_practice_ids


def test_practice_persistence_tracks_callable_endpoints_not_bundle():
    """
    Exercise the test_practice_persistence_tracks_callable_endpoints_not_bundle
    regression scenario.
    """
    pool = InMemoryPool()
    agent = StandbyAgent(name="alice", pool=pool)
    agent.add_practice(MultiEndpointPractice())

    rows = pool._GetTableData("agent_practices", {"agent_name": "alice"})
    row_by_id = {row["practice_id"]: row for row in rows}
    assert "echo-endpoint" in row_by_id
    assert "ping-endpoint" in row_by_id
    assert "multi-endpoint-practice" not in row_by_id
    assert row_by_id["echo-endpoint"]["practice_data"]["cost"] == 5
    assert row_by_id["ping-endpoint"]["practice_data"]["cost"] == 0

    card_by_id = {p.get("id"): p for p in agent.agent_card.get("practices", [])}
    card_practice_ids = set(card_by_id)
    assert "echo-endpoint" in card_practice_ids
    assert "ping-endpoint" in card_practice_ids
    assert "multi-endpoint-practice" not in card_practice_ids
    assert card_by_id["echo-endpoint"]["cost"] == 5
    assert card_by_id["ping-endpoint"]["cost"] == 0


def test_agent_batches_callable_practice_metadata_persistence():
    """
    Exercise the test_agent_batches_callable_practice_metadata_persistence
    regression scenario.
    """
    pool = CountingBatchInMemoryPool()
    agent = StandbyAgent(name="alice", pool=pool)
    pool.insert_calls.clear()
    pool.insert_many_calls.clear()

    agent.add_practice(MultiEndpointPractice())

    batch_calls = [
        call for call in pool.insert_many_calls
        if call[0] == "agent_practices"
    ]
    assert len(batch_calls) == 1
    assert {row["practice_id"] for row in batch_calls[0][1]} == {"echo-endpoint", "ping-endpoint"}

    single_calls = [
        call for call in pool.insert_calls
        if call[0] == "agent_practices" and call[1].get("practice_id") in {"echo-endpoint", "ping-endpoint"}
    ]
    assert single_calls == []


def test_agent_registers_pool_operation_practices_and_can_use_them():
    """
    Exercise the test_agent_registers_pool_operation_practices_and_can_use_them
    regression scenario.
    """
    pool = InMemoryPool()
    agent = StandbyAgent(name="alice", pool=pool)

    assert PoolCap.MEMORY in pool.capabilities
    assert PoolCap.SEARCH in pool.capabilities

    practice_ids = {practice.id for practice in agent.practices}
    assert "pool-connect" in practice_ids
    assert "pool-create-table" in practice_ids
    assert "pool-table-exists" in practice_ids
    assert "pool-insert" in practice_ids
    assert "pool-query" in practice_ids
    assert "pool-get-table-data" in practice_ids
    assert "pool-store-memory" in practice_ids
    assert "pool-search-memory" in practice_ids
    assert "pool-disconnect" in practice_ids

    card_practice_ids = {entry.get("id") for entry in agent.agent_card.get("practices", [])}
    assert "pool-create-table" in card_practice_ids
    assert "pool-get-table-data" in card_practice_ids
    assert "pool-store-memory" in card_practice_ids
    assert "pool-search-memory" in card_practice_ids

    schema = {
        "name": "demo",
        "description": "demo table",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "value": {"type": "string"},
        },
    }
    created = agent.UsePractice("pool-create-table", {"table_name": "demo", "schema": schema})
    exists = agent.UsePractice("pool-table-exists", {"table_name": "demo"})
    inserted = agent.UsePractice("pool-insert", {"table_name": "demo", "data": {"id": "r1", "value": "ok"}})
    rows = agent.UsePractice("pool-get-table-data", {"table_name": "demo"})
    stored_memory = agent.UsePractice(
        "pool-store-memory",
        {"content": "Alpha market note", "metadata": {"symbol": "BTC"}, "tags": ["btc", "note"]},
    )
    memory_results = agent.UsePractice("pool-search-memory", {"query": "market", "limit": 5})

    assert created is True
    assert exists is True
    assert inserted is True
    assert rows == [{"id": "r1", "value": "ok"}]
    assert stored_memory["content"] == "Alpha market note"
    assert memory_results[0]["id"] == stored_memory["id"]


def test_plaza_endpoint_details_persist_to_pool_and_agent_card():
    """
    Exercise the test_plaza_endpoint_details_persist_to_pool_and_agent_card
    regression scenario.
    """
    pool = InMemoryPool()
    agent = StandbyAgent(name="plaza", pool=pool, agent_card={"name": "Plaza", "role": "coordinator", "tags": []})
    agent.add_practice(PlazaPractice())

    rows = pool._GetTableData("agent_practices", {"agent_name": "plaza"})
    row_by_id = {row["practice_id"]: row for row in rows}
    assert "register" in row_by_id
    register_data = row_by_id["register"]["practice_data"]
    assert register_data.get("examples")
    assert "agent_name" in (register_data.get("parameters") or {})
    assert register_data.get("cost") == 0

    card_by_id = {entry.get("id"): entry for entry in agent.agent_card.get("practices", [])}
    assert "register" in card_by_id
    assert card_by_id["register"].get("examples")
    assert "agent_name" in (card_by_id["register"].get("parameters") or {})
    assert card_by_id["register"].get("cost") == 0


def test_use_practice_local_sync():
    """Exercise the test_use_practice_local_sync regression scenario."""
    agent = StandbyAgent(name="alice")
    agent.add_practice(EchoPractice())

    result = agent.UsePractice("echo-practice", {"value": 42})

    assert result["echo"]["value"] == 42


@pytest.mark.asyncio
async def test_use_practice_local_async():
    """Exercise the test_use_practice_local_async regression scenario."""
    agent = StandbyAgent(name="alice")
    agent.add_practice(AsyncEchoPractice())

    result = await agent.UsePractice("async-echo-practice", {"value": "ok"}, async_mode=True)

    assert result["async_echo"]["value"] == "ok"


def test_use_practice_remote_sync_via_pit_address():
    """
    Exercise the test_use_practice_remote_sync_via_pit_address regression scenario.
    """
    agent = StandbyAgent(name="alice", plaza_url="http://127.0.0.1:8011")
    agent.agent_id = "alice-id"
    agent.plaza_token = "alice-token"
    agent.token_expires_at = time.time() + 3600
    agent._refresh_pit_address()

    remote_address = PitAddress(pit_id="bob-id", plazas=["http://127.0.0.1:8011"])

    def fake_lookup(_name):
        """Handle fake lookup."""
        return {
            "agent_id": "bob-id",
            "card": {
                "address": "http://127.0.0.1:8013",
                "practices": [{"id": "echo-practice", "path": "/echo"}]
            }
        }

    def fake_post(url, json=None, timeout=30, **kwargs):
        """Handle fake post."""
        assert url == "http://127.0.0.1:8013/use_practice/echo-practice"
        assert json.get("msg_type") == "echo-practice"
        assert json.get("caller_agent_address", {}).get("pit_id") == "alice-id"
        assert json.get("caller_plaza_token") == "alice-token"
        return FakeResponse({"status": "ok", "result": {"echo": json["content"]}})

    with patch.object(agent, "lookup_agent_info", side_effect=fake_lookup):
        with patch("prompits.agents.base.requests.post", side_effect=fake_post):
            result = agent.UsePractice("echo-practice", {"x": 1}, pit_address=remote_address)

    assert result["echo"]["x"] == 1


def test_use_practice_remote_sync_via_direct_url_hint():
    """
    Exercise the test_use_practice_remote_sync_via_direct_url_hint regression
    scenario.
    """
    agent = StandbyAgent(
        name="alice",
        agent_card={"name": "alice", "meta": {"direct_auth_token": "shared-secret"}},
    )
    agent.agent_id = "alice-id"
    agent._refresh_pit_address()

    def fake_post(url, json=None, timeout=30, **kwargs):
        """Handle fake post."""
        assert url == "http://10.0.0.8:8013/use_practice/echo-practice"
        assert json.get("msg_type") == "echo-practice"
        assert json.get("caller_agent_address", {}).get("pit_id") == "alice-id"
        assert json.get("caller_plaza_token") is None
        assert json.get("caller_direct_token") == "shared-secret"
        return FakeResponse({"status": "ok", "result": {"echo": json["content"]}})

    with patch("prompits.agents.base.requests.post", side_effect=fake_post):
        result = agent.UsePractice(
            "echo-practice",
            {"x": 1},
            pit_address={"pit_id": "bob-id", "address": "http://10.0.0.8:8013"},
        )

    assert result["echo"]["x"] == 1


@pytest.mark.asyncio
async def test_use_practice_remote_async_via_pit_address():
    """
    Exercise the test_use_practice_remote_async_via_pit_address regression scenario.
    """
    agent = StandbyAgent(name="alice", plaza_url="http://127.0.0.1:8011")
    agent.agent_id = "alice-id"
    agent.plaza_token = "alice-token"
    agent.token_expires_at = time.time() + 3600
    agent._refresh_pit_address()

    remote_address = PitAddress(pit_id="bob-id", plazas=["http://127.0.0.1:8011"])

    def fake_lookup(_name):
        """Handle fake lookup."""
        return {
            "agent_id": "bob-id",
            "card": {
                "address": "http://127.0.0.1:8013",
                "practices": [{"id": "echo-practice", "path": "/echo"}]
            }
        }

    class FakeAsyncResponse:
        """Response model for fake async payloads."""
        status_code = 200
        content = b"{}"

        def raise_for_status(self):
            """Return the raise for the status."""
            return None

        def json(self):
            """Handle JSON for the fake async response."""
            return {"status": "ok"}

    async def fake_async_post(self, url, json=None, timeout=30, **kwargs):
        """Handle fake async post."""
        assert url == "http://127.0.0.1:8013/use_practice/echo-practice"
        assert json.get("msg_type") == "echo-practice"
        assert json.get("caller_agent_address", {}).get("pit_id") == "alice-id"
        assert json.get("caller_plaza_token") == "alice-token"
        return FakeAsyncResponse()

    with patch.object(agent, "lookup_agent_info", side_effect=fake_lookup):
        with patch("httpx.AsyncClient.post", new=fake_async_post):
            result = await agent.UsePractice("echo-practice", {"x": 1}, pit_address=remote_address, async_mode=True)

    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_use_practice_remote_async_via_direct_url_hint():
    """
    Exercise the test_use_practice_remote_async_via_direct_url_hint regression
    scenario.
    """
    agent = StandbyAgent(
        name="alice",
        agent_card={"name": "alice", "meta": {"direct_auth_token": "shared-secret"}},
    )
    agent.agent_id = "alice-id"
    agent._refresh_pit_address()

    class FakeAsyncResponse:
        """Response model for fake async payloads."""
        status_code = 200
        content = b"{}"

        def raise_for_status(self):
            """Return the raise for the status."""
            return None

        def json(self):
            """Handle JSON for the fake async response."""
            return {"status": "ok"}

    async def fake_async_post(self, url, json=None, timeout=30, **kwargs):
        """Handle fake async post."""
        assert url == "http://10.0.0.8:8013/use_practice/echo-practice"
        assert json.get("msg_type") == "echo-practice"
        assert json.get("caller_agent_address", {}).get("pit_id") == "alice-id"
        assert json.get("caller_plaza_token") is None
        assert json.get("caller_direct_token") == "shared-secret"
        return FakeAsyncResponse()

    with patch("httpx.AsyncClient.post", new=fake_async_post):
        result = await agent.UsePractice(
            "echo-practice",
            {"x": 1},
            pit_address={"pit_id": "bob-id", "address": "http://10.0.0.8:8013"},
            async_mode=True,
        )

    assert result["status"] == "ok"


@pytest.mark.asyncio
async def test_verify_remote_caller_accepts_direct_shared_token():
    """
    Exercise the test_verify_remote_caller_accepts_direct_shared_token regression
    scenario.
    """
    agent = StandbyAgent(
        name="bob",
        agent_card={"name": "bob", "meta": {"direct_auth_token": "shared-secret"}},
    )

    verified = await agent._verify_remote_caller(
        caller_agent_address={"pit_id": "alice-id", "plazas": []},
        caller_plaza_token=None,
        caller_direct_token="shared-secret",
    )

    assert verified["agent_id"] == "alice-id"
    assert verified["auth_mode"] == "direct"


@pytest.mark.asyncio
async def test_verify_remote_caller_skips_plaza_when_direct_shared_token_is_valid():
    """
    Exercise the direct-token-first regression scenario for remote caller
    verification.
    """
    agent = StandbyAgent(
        name="bob",
        plaza_url="http://127.0.0.1:8011",
        agent_card={"name": "bob", "meta": {"direct_auth_token": "shared-secret"}},
    )

    with patch.object(
        agent,
        "_plaza_request_async",
        side_effect=AssertionError("Plaza auth should not run when direct auth already succeeded"),
    ):
        verified = await agent._verify_remote_caller(
            caller_agent_address={"pit_id": "alice-id", "plazas": ["http://127.0.0.1:8011"]},
            caller_plaza_token="stale-plaza-token",
            caller_direct_token="shared-secret",
        )

    assert verified["agent_id"] == "alice-id"
    assert verified["auth_mode"] == "direct"


@pytest.mark.asyncio
async def test_verify_remote_caller_only_checks_receiver_trusted_plazas():
    """
    Exercise the receiver-side trusted Plaza allowlist regression scenario for
    remote caller verification.
    """
    agent = StandbyAgent(name="bob", plaza_url="http://127.0.0.1:8011")
    seen_plazas = []

    class FakeAsyncResponse:
        """Response model for fake async auth payloads."""

        status_code = 200
        content = b'{"agent_id":"alice-id","agent_name":"alice"}'

        def json(self):
            """Handle JSON for the fake async response."""
            return {"agent_id": "alice-id", "agent_name": "alice"}

    async def fake_plaza_request(method, path, plaza_url=None, headers=None, **kwargs):
        """Handle fake Plaza auth verification."""
        seen_plazas.append(plaza_url)
        assert method == "post"
        assert path == "/authenticate"
        assert headers == {"Authorization": "Bearer alice-token"}
        return FakeAsyncResponse()

    with patch.object(agent, "_plaza_request_async", side_effect=fake_plaza_request):
        verified = await agent._verify_remote_caller(
            caller_agent_address={
                "pit_id": "alice-id",
                "plazas": ["http://evil.example:8011", "http://127.0.0.1:8011"],
            },
            caller_plaza_token="alice-token",
        )

    assert seen_plazas == ["http://127.0.0.1:8011"]
    assert verified["agent_id"] == "alice-id"
    assert verified["plaza_url"] == "http://127.0.0.1:8011"
    assert verified["auth_mode"] == "plaza"


@pytest.mark.asyncio
async def test_verify_remote_caller_rejects_when_no_trusted_plaza_is_configured():
    """
    Exercise the missing trusted Plaza configuration regression scenario for
    remote caller verification.
    """
    agent = StandbyAgent(name="bob")

    with pytest.raises(HTTPException) as exc_info:
        await agent._verify_remote_caller(
            caller_agent_address={"pit_id": "alice-id", "plazas": ["http://127.0.0.1:8011"]},
            caller_plaza_token="alice-token",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Trusted Plaza verification is not configured"
