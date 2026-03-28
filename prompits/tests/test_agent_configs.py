import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.agents.user import UserAgent
from prompits.core.agent_config import AgentConfigStore, AgentLaunchManager
from prompits.core.plaza import PlazaAgent
from prompits.pools.filesystem import FileSystemPool


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = b"{}"
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class FakeProcess:
    def __init__(self, pid=43210):
        self.pid = pid

    def poll(self):
        return None

    def terminate(self):
        return None

    def wait(self, timeout=None):
        return 0

    def kill(self):
        return None


def test_agent_config_store_strips_runtime_network_fields(tmp_path):
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
                "pit_address": {"pit_id": "worker-a", "plazas": ["http://127.0.0.1:8011"]},
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
    assert "uuid" not in saved["config"]["agent_card"]
    assert "ip_address" not in saved["config"]["agent_card"]
    assert "address" not in saved["config"]["agent_card"]
    assert "pit_address" not in saved["config"]["agent_card"]
    assert "plaza_url" not in saved["config"]["user_agent"]
    assert "plaza_urls" not in saved["config"]["user_agent"]
    rows = pool._GetTableData("plaza_directory")
    assert len(rows) == 1
    assert rows[0]["id"] == "agent-config:worker-a"
    assert rows[0]["type"] == "AgentConfig"
    assert rows[0]["meta"]["config"]["name"] == "worker-a"
    assert "host" not in rows[0]["meta"]["config"]


def test_agent_launch_manager_injects_runtime_host_port_and_plaza_url(tmp_path):
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
    agent = UserAgent(
        name="attas-user",
        host="127.0.0.1",
        port=8614,
        plaza_url=None,
        plaza_urls=["http://plaza-a", "http://plaza-b"],
        pool=None,
        config={},
    )
    client = TestClient(agent.app)

    def fake_plaza_get(path, plaza_url=None, params=None, retries=0, **kwargs):
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
