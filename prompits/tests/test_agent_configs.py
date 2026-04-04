"""
Regression tests for Agent Configs.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_agent_config_store_strips_runtime_network_fields`,
`test_agent_launch_manager_injects_runtime_host_port_and_plaza_url`,
`test_plaza_agent_config_routes_save_list_and_launch`, and
`test_user_agent_agent_config_routes_aggregate_and_launch`, helping guard against
regressions as the packages evolve.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.agents.user import UserAgent
from prompits.core.pool import Pool, PoolCap
from prompits.core.agent_config import AgentConfigStore, AgentLaunchManager
from prompits.core.plaza import PlazaAgent
from prompits.pools.filesystem import FileSystemPool


class FakeResponse:
    """Response model for fake payloads."""
    def __init__(self, payload, status_code=200):
        """Initialize the fake response."""
        self._payload = payload
        self.status_code = status_code
        self.content = b"{}"
        self.text = json.dumps(payload)

    def json(self):
        """Handle JSON for the fake response."""
        return self._payload


class FakeProcess:
    """Represent a fake process."""
    def __init__(self, pid=43210):
        """Initialize the fake process."""
        self.pid = pid

    def poll(self):
        """Handle poll for the fake process."""
        return None

    def terminate(self):
        """Handle terminate for the fake process."""
        return None

    def wait(self, timeout=None):
        """Handle wait for the fake process."""
        return 0

    def kill(self):
        """Handle kill for the fake process."""
        return None


def test_agent_config_store_strips_runtime_network_fields(tmp_path):
    """
    Exercise the test_agent_config_store_strips_runtime_network_fields regression
    scenario.
    """
    pool = FileSystemPool("cfg_pool", "Agent Config Pool", str(tmp_path / "pool"))
    store = AgentConfigStore(pool=pool)

    saved = store.upsert(
        {
            "name": "worker-a",
            "uuid": "runtime-config-uuid",
            "ip_address": "127.0.0.1",
            "host": "127.0.0.1",
            "port": 8123,
            "plaza_url": "http://127.0.0.1:8011",
            "plaza_urls": ["http://127.0.0.1:8011"],
            "worker_id": "ads-worker:runtime",
            "updated_at": "2026-03-29T10:00:00+00:00",
            "plaza_owner_key": "plaza_ak_top_level_secret",
            "type": "prompits.agents.standby.StandbyAgent",
            "pools": [
                {
                    "type": "FileSystemPool",
                    "name": "worker_pool",
                    "description": "worker pool",
                    "root_path": "tests/storage",
                }
            ],
            "agent_card": {
                "name": "worker-a",
                "uuid": "runtime-card-uuid",
                "ip_address": "127.0.0.1",
                "address": "http://127.0.0.1:8123",
                "host": "127.0.0.1",
                "port": 8123,
                "plaza_owner_key_id": "owner-key-123",
                "pit_address": {"pit_id": "worker-a", "plazas": ["http://127.0.0.1:8011"]},
                "meta": {
                    "worker_id": "ads-worker:runtime",
                    "environment": {"hostname": "worker-host"},
                    "heartbeat": {"progress": {"phase": "working"}},
                    "plaza_owner_key": "plaza_ak_nested_secret",
                    "plaza_owner_key_id": "owner-key-123",
                },
            },
            "user_agent": {
                "plaza_url": "http://127.0.0.1:8011",
                "plaza_urls": ["http://127.0.0.1:8011"],
            },
        },
        owner="tests",
    )

    assert saved["id"] == "agent-config:worker-a"
    assert saved["name"] == "worker-a"
    assert saved["owner"] == "tests"
    assert "uuid" not in saved["config"]
    assert "ip_address" not in saved["config"]
    assert "host" not in saved["config"]
    assert "port" not in saved["config"]
    assert "plaza_url" not in saved["config"]
    assert "plaza_urls" not in saved["config"]
    assert "worker_id" not in saved["config"]
    assert "updated_at" not in saved["config"]
    assert "plaza_owner_key" not in saved["config"]
    assert "uuid" not in saved["config"]["agent_card"]
    assert "ip_address" not in saved["config"]["agent_card"]
    assert "address" not in saved["config"]["agent_card"]
    assert "pit_address" not in saved["config"]["agent_card"]
    assert saved["config"]["agent_card"]["plaza_owner_key_id"] == "owner-key-123"
    assert "worker_id" not in saved["config"]["agent_card"]["meta"]
    assert "environment" not in saved["config"]["agent_card"]["meta"]
    assert "heartbeat" not in saved["config"]["agent_card"]["meta"]
    assert "plaza_owner_key" not in saved["config"]["agent_card"]["meta"]
    assert saved["config"]["agent_card"]["meta"]["plaza_owner_key_id"] == "owner-key-123"
    assert "plaza_url" not in saved["config"]["user_agent"]
    assert "plaza_urls" not in saved["config"]["user_agent"]
    assert saved["owner_key_id"] == "owner-key-123"
    rows = pool._GetTableData("plaza_directory")
    assert len(rows) == 1
    assert rows[0]["id"] == "agent-config:worker-a"
    assert rows[0]["type"] == "AgentConfig"
    assert rows[0]["meta"]["config"]["name"] == "worker-a"
    assert "host" not in rows[0]["meta"]["config"]
    assert rows[0]["meta"]["config"]["agent_card"]["meta"]["plaza_owner_key_id"] == "owner-key-123"
    assert "plaza_owner_key" not in rows[0]["meta"]["config"]
    assert "plaza_owner_key" not in rows[0]["meta"]["config"]["agent_card"]["meta"]


def test_agent_config_store_marks_ads_workers_as_ephemeral_identity():
    """
    Exercise the test_agent_config_store_marks_ads_workers_as_ephemeral_identity
    regression scenario.
    """
    saved = AgentConfigStore.sanitize_config(
        {
            "name": "ADSWorker",
            "type": "ads.agents.ADSWorkerAgent",
            "worker_id": "ads-worker:runtime",
            "pools": [{"type": "SQLitePool", "db_path": "worker.sqlite"}],
        }
    )

    assert AgentConfigStore.prefers_ephemeral_identity(saved) is True


def test_agent_config_store_upsert_does_not_read_directory_before_insert(tmp_path):
    """
    Exercise the
    test_agent_config_store_upsert_does_not_read_directory_before_insert regression
    scenario.
    """
    class NoReadFileSystemPool(FileSystemPool):
        """Represent a no read file system pool."""
        def _GetTableData(self, table_name, id_or_where=None, table_schema=None):
            """Internal helper to return the table data."""
            raise AssertionError("Agent config upsert should not read plaza_directory before insert")

    pool = NoReadFileSystemPool("cfg_pool", "Agent Config Pool", str(tmp_path / "pool"))
    store = AgentConfigStore(pool=pool)

    saved = store.upsert(
        {
            "name": "worker-b",
            "type": "prompits.agents.standby.StandbyAgent",
            "pools": [
                {
                    "type": "FileSystemPool",
                    "name": "worker_pool",
                    "description": "worker pool",
                    "root_path": "tests/storage",
                }
            ],
        },
        owner="tests",
    )

    assert saved["id"] == "agent-config:worker-b"
    stored_path = tmp_path / "pool" / "plaza_directory" / "agent-config%3Aworker-b.json"
    assert stored_path.exists()


def test_agent_config_store_skips_table_exists_probe_for_batch_rpc_tables():
    """
    Exercise the
    test_agent_config_store_skips_table_exists_probe_for_batch_rpc_tables regression
    scenario.
    """
    class BatchRpcDirectoryPool(Pool):
        """Represent a batch rpc directory pool."""
        BATCH_UPSERT_RPC_BY_TABLE = {"plaza_directory": "batch_upsert_plaza_directory"}

        def __init__(self):
            """Initialize the batch rpc directory pool."""
            super().__init__("cfg_pool", "Agent Config Pool", capabilities=[PoolCap.TABLE, PoolCap.JSON])
            self.rows = {}
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
            raise AssertionError("Batch RPC-backed agent config registration should not create plaza_directory")

        def _TableExists(self, table_name):
            """Return whether the table exists for value."""
            raise AssertionError("Batch RPC-backed agent config registration should not probe plaza_directory")

        def _Insert(self, table_name, data):
            """Internal helper for insert."""
            self.rows[(table_name, data["id"])] = dict(data)
            return True

        def _Query(self, query, params=None):
            """Internal helper to query the value."""
            return []

        def _GetTableData(self, table_name, id_or_where=None, table_schema=None):
            """Internal helper to return the table data."""
            return []

        def store_memory(self, content, memory_id=None, metadata=None, tags=None, memory_type="text", table_name=None):
            """Handle store memory for the batch rpc directory pool."""
            raise NotImplementedError

        def search_memory(self, query, limit=10, table_name=None):
            """Search the memory."""
            return []

        def create_table_practice(self):
            """Create the table practice."""
            raise NotImplementedError

        def table_exists_practice(self):
            """Return whether the table exists for practice."""
            raise NotImplementedError

        def insert_practice(self):
            """Handle insert practice for the batch rpc directory pool."""
            raise NotImplementedError

        def query_practice(self):
            """Query the practice."""
            raise NotImplementedError

        def get_table_data_practice(self):
            """Return the table data practice."""
            raise NotImplementedError

        def connect_practice(self):
            """Connect the practice."""
            raise NotImplementedError

        def disconnect_practice(self):
            """Disconnect the practice."""
            raise NotImplementedError

        def store_memory_practice(self):
            """Handle store memory practice for the batch rpc directory pool."""
            raise NotImplementedError

        def search_memory_practice(self):
            """Search the memory practice."""
            raise NotImplementedError

    pool = BatchRpcDirectoryPool()
    store = AgentConfigStore(pool=pool)

    saved = store.upsert(
        {
            "name": "worker-c",
            "type": "prompits.agents.standby.StandbyAgent",
            "pools": [
                {
                    "type": "FileSystemPool",
                    "name": "worker_pool",
                    "description": "worker pool",
                    "root_path": "tests/storage",
                }
            ],
        },
        owner="tests",
    )

    assert saved["id"] == "agent-config:worker-c"
    assert ("plaza_directory", "agent-config:worker-c") in pool.rows


def test_agent_launch_manager_injects_runtime_host_port_and_plaza_url(tmp_path):
    """
    Exercise the test_agent_launch_manager_injects_runtime_host_port_and_plaza_url
    regression scenario.
    """
    manager = AgentLaunchManager(
        default_plaza_url="http://127.0.0.1:8511",
        workspace_root=str(tmp_path),
    )
    config_row = {
        "id": "cfg-1",
        "name": "worker-a",
        "config": {
            "name": "worker-a",
            "type": "prompits.agents.standby.StandbyAgent",
            "pools": [
                {
                    "type": "FileSystemPool",
                    "name": "worker_pool",
                    "description": "worker pool",
                    "root_path": "tests/storage",
                }
            ],
        },
    }

    with (
        patch("prompits.core.agent_config.subprocess.Popen", return_value=FakeProcess()),
        patch.object(manager, "_wait_for_health", return_value=True),
    ):
        launch = manager.launch_config(config_row, host="127.0.0.1", port=8602, plaza_url="http://127.0.0.1:8511")

    runtime_config = json.loads(Path(launch["config_path"]).read_text(encoding="utf-8"))
    assert runtime_config["host"] == "127.0.0.1"
    assert runtime_config["port"] == 8602
    assert runtime_config["plaza_url"] == "http://127.0.0.1:8511"


def test_plaza_agent_config_routes_save_list_and_launch(tmp_path):
    """
    Exercise the test_plaza_agent_config_routes_save_list_and_launch regression
    scenario.
    """
    pool = FileSystemPool("plaza_pool", "Plaza Pool", str(tmp_path / "plaza-pool"))
    agent = PlazaAgent(host="127.0.0.1", port=8511, pool=pool)
    client = TestClient(agent.app)

    config_payload = {
        "name": "worker-a",
        "type": "prompits.agents.standby.StandbyAgent",
        "role": "worker",
        "tags": ["worker", "demo"],
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "worker_pool",
                "description": "worker pool",
                "root_path": "tests/storage",
            }
        ],
    }

    save_response = client.post("/api/agent_configs", json={"config": config_payload, "owner": "tests"})
    assert save_response.status_code == 200
    saved = save_response.json()["agent_config"]
    assert saved["name"] == "worker-a"
    assert saved["owner"] == "tests"
    assert "host" not in saved["config"]
    assert "port" not in saved["config"]

    list_response = client.get("/api/agent_configs?q=worker")
    assert list_response.status_code == 200
    listed = list_response.json()["agent_configs"]
    assert len(listed) == 1
    assert listed[0]["id"] == saved["id"]

    with patch.object(
        agent.agent_launch_manager,
        "launch_config",
        return_value={
            "launch_id": "launch-1",
            "config_id": saved["id"],
            "pid": 9876,
            "address": "http://127.0.0.1:8601",
            "status": "running",
        },
    ) as launch_mock:
        launch_response = client.post(
            "/api/agent_configs/launch",
            json={
                "config_id": saved["id"],
                "agent_name": "worker-a-runtime",
                "pool_type": "FileSystemPool",
                "pool_location": "tests/storage/runtime",
            },
        )

    assert launch_response.status_code == 200
    launch = launch_response.json()["launch"]
    assert launch["launch_id"] == "launch-1"
    assert launch["agent_config"]["id"] == saved["id"]
    assert launch_mock.call_args.kwargs["plaza_url"] == "http://127.0.0.1:8511"
    assert launch_mock.call_args.kwargs["agent_name"] == "worker-a-runtime"
    assert launch_mock.call_args.kwargs["pool_type"] == "FileSystemPool"
    assert launch_mock.call_args.kwargs["pool_location"] == "tests/storage/runtime"


def test_user_agent_agent_config_routes_aggregate_and_launch():
    """
    Exercise the test_user_agent_agent_config_routes_aggregate_and_launch regression
    scenario.
    """
    agent = UserAgent(
        name="user-agent",
        host="127.0.0.1",
        port=8614,
        plaza_url=None,
        plaza_urls=["http://plaza-a", "http://plaza-b"],
        pool=None,
        config={},
    )
    client = TestClient(agent.app)

    def fake_plaza_get(path, plaza_url=None, params=None, retries=0, **kwargs):
        """Handle fake Plaza get."""
        assert path == "/api/agent_configs"
        if plaza_url == "http://plaza-a":
            return FakeResponse(
                {
                    "status": "success",
                    "agent_configs": [
                        {
                            "id": "cfg-a",
                            "name": "Macro Worker",
                            "description": "Macro config",
                            "owner": "plaza-a",
                            "role": "worker",
                            "agent_type": "prompits.agents.standby.StandbyAgent",
                            "tags": ["macro"],
                        }
                    ],
                }
            )
        return FakeResponse({"status": "success", "agent_configs": []})

    with patch.object(agent, "_plaza_get", side_effect=fake_plaza_get):
        response = client.get("/api/agent_configs?q=macro")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert len(payload["plazas"]) == 2
    assert len(payload["agent_configs"]) == 1
    assert payload["agent_configs"][0]["plaza_url"] == "http://plaza-a"

    def fake_plaza_post(path, plaza_url=None, json=None, retries=0, **kwargs):
        """Handle fake Plaza post."""
        assert path == "/api/agent_configs/launch"
        assert plaza_url == "http://plaza-a"
        assert json["config_id"] == "cfg-a"
        return FakeResponse(
            {
                "status": "success",
                "launch": {
                    "launch_id": "launch-a",
                    "config_id": "cfg-a",
                    "address": "http://127.0.0.1:8601",
                    "status": "running",
                },
            }
        )

    with patch.object(agent, "_plaza_post", side_effect=fake_plaza_post):
        launch_response = client.post(
            "/api/agent_configs/launch",
            json={"plaza_url": "http://plaza-a", "config_id": "cfg-a"},
        )

    assert launch_response.status_code == 200
    launch = launch_response.json()["launch"]
    assert launch["launch_id"] == "launch-a"
    assert launch["plaza_url"] == "http://plaza-a"
