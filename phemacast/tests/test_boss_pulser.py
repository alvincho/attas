"""
Regression tests for Boss Pulser.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_boss_pulser_create_manager_generates_manager_config`,
`test_boss_pulser_create_team_generates_teamwork_configs`,
`test_build_agent_from_config_loads_boss_pulser`, and
`test_boss_pulser_root_renders_independent_management_ui`, helping guard against
regressions as the packages evolve.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient

from phemacast.pulsers.boss_pulser import BossPulser
from prompits.pools.sqlite import SQLitePool
from prompits.teamwork.schema import TABLE_JOBS, TABLE_WORKER_HISTORY, TABLE_WORKERS
from prompits.tests.test_support import build_agent_from_config


def test_boss_pulser_create_team_generates_teamwork_configs():
    """
    Exercise the test_boss_pulser_create_team_generates_teamwork_configs regression
    scenario.
    """
    pulser = BossPulser(auto_register=False)

    result = pulser.get_pulse_data(
        {
            "team_name": "Map Runner",
            "party": "Phemacast",
            "plaza_url": "http://127.0.0.1:8011",
            "worker_count": 2,
            "job_capabilities": [
                {
                    "name": "run map",
                    "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                    "description": "Execute one saved map.",
                    "default_priority": 110,
                }
            ],
        },
        pulse_name="create_team",
    )

    assert result["party"] == "Phemacast"
    assert result["manager_address"] == "http://127.0.0.1:8170"
    assert result["boss_config"]["type"] == "prompits.teamwork.boss.TeamBossAgent"
    assert result["manager_config"]["type"] == "prompits.teamwork.agents.DispatcherManagerAgent"
    assert len(result["worker_configs"]) == 2
    assert result["team_manifest"]["api_version"] == "phemacast.team_manifest.v1"
    assert result["team_manifest"]["worker_defaults"]["count"] == 2
    assert result["worker_configs"][0]["worker"]["job_capabilities"][0]["name"] == "run map"
    assert result["boss_config"]["boss"]["job_capabilities"][0]["default_priority"] == 110
    assert result["config_paths"]["boss"].endswith("/boss.agent")


def test_boss_pulser_create_team_can_start_manager_hiring():
    """
    Exercise the test_boss_pulser_create_team_can_start_manager_hiring regression
    scenario.
    """
    pulser = BossPulser(auto_register=False)

    captured = []

    def fake_use_practice(practice_id, payload, pit_address=""):
        """Handle fake manager-pulser hire calls."""
        captured.append((practice_id, payload, pit_address))
        assert practice_id == "get_pulse_data"
        assert payload["pulse_name"] == "join_team"
        assert pit_address == "http://127.0.0.1:8320"
        return {
            "status": "success",
            "manager_address": "http://127.0.0.1:8270",
            "team_membership": {
                "status": "joined",
                "manager_name": "EastManager",
                "manager_address": "http://127.0.0.1:8270",
                "local_worker_count": 1,
            },
            "worker_configs": [
                {
                    "name": "EastWorker1",
                    "worker": {"manager_address": "http://127.0.0.1:8270"},
                }
            ],
        }

    pulser.UsePractice = fake_use_practice

    result = pulser.get_pulse_data(
        {
            "team_name": "Map Runner",
            "party": "Phemacast",
            "plaza_url": "http://127.0.0.1:8011",
            "worker_count": 1,
            "job_capabilities": [
                {
                    "name": "run map",
                    "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                    "description": "Execute one saved map.",
                }
            ],
            "start_hiring_managers": True,
            "require_manager_hire": True,
            "manager_hires": [
                {
                    "pulser_address": "http://127.0.0.1:8320",
                    "pulser_name": "EastManagerPulser",
                    "manager_name": "EastManager",
                    "worker_count": 1,
                    "worker_name_prefix": "EastWorker",
                    "worker_base_port": 8271,
                }
            ],
        },
        pulse_name="create_team",
    )

    assert captured[0][0] == "get_pulse_data"
    assert result["manager_hires"][0]["status"] == "joined"
    assert result["hiring"]["started"] == 1
    assert result["manager_address"] == "http://127.0.0.1:8270"
    assert result["boss_config"]["boss"]["manager_address"] == "http://127.0.0.1:8270"
    assert result["worker_configs"][0]["worker"]["manager_address"] == "http://127.0.0.1:8270"


def test_boss_pulser_supported_jobcaps_aggregates_from_managers_and_workers():
    """
    Exercise the
    test_boss_pulser_supported_jobcaps_aggregates_from_managers_and_workers
    regression scenario.
    """
    pulser = BossPulser(auto_register=False)

    def fake_search(**kwargs):
        """Handle fake search."""
        role = kwargs.get("role")
        if role in {"manager", "dispatcher"}:
            return [
                {
                    "name": "MapManager",
                    "last_active": 200.0,
                    "card": {
                        "address": "http://127.0.0.1:8170",
                        "party": "Phemacast",
                        "role": "manager",
                        "meta": {
                            "job_capabilities": [
                                {
                                    "name": "run map",
                                    "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                                    "description": "Execute one saved map.",
                                }
                            ]
                        },
                    },
                }
            ]
        if role == "worker":
            return [
                {
                    "name": "MapWorker1",
                    "last_active": 100.0,
                    "card": {
                        "address": "http://127.0.0.1:8171",
                        "party": "Phemacast",
                        "role": "worker",
                        "meta": {
                            "capabilities": ["run map"],
                            "job_capabilities": [
                                {
                                    "name": "run map",
                                    "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                                }
                            ],
                        },
                    },
                }
            ]
        return []

    pulser.search = fake_search

    result = pulser.get_pulse_data({"party": "Phemacast"}, pulse_name="supported_jobcaps")

    assert result["count"] == 1
    assert result["job_capabilities"][0]["name"] == "run map"
    provider_types = {provider["type"] for provider in result["job_capabilities"][0]["providers"]}
    assert provider_types == {"manager", "worker"}


def test_boss_pulser_provision_catalog_lists_jobcaps_managers_and_workers_for_hire():
    """
    Exercise the
    test_boss_pulser_provision_catalog_lists_jobcaps_managers_and_workers_for_hire
    regression scenario.
    """
    pulser = BossPulser(auto_register=False)
    client = TestClient(pulser.app)

    search_calls = []

    def fake_search(**kwargs):
        """Handle fake search."""
        search_calls.append(dict(kwargs))
        role = kwargs.get("role")
        pit_type = kwargs.get("pit_type")
        if role == "manager_pulser" and pit_type == "Pulser":
            return [
                {
                    "name": "EastManagerPulser",
                    "last_active": 400.0,
                    "card": {
                        "address": "http://127.0.0.1:8320",
                        "party": "Phemacast",
                        "role": "manager_pulser",
                        "description": "Ready to join one team manifest.",
                        "meta": {
                            "manager_address": "http://127.0.0.1:8270",
                            "supported_pulses": [
                                {"name": "join_team"},
                                {"name": "monitor_local_manager"},
                            ],
                        },
                    },
                }
            ]
        if role in {"manager", "dispatcher"}:
            return [
                {
                    "name": "MapManager",
                    "last_active": 200.0,
                    "card": {
                        "address": "http://127.0.0.1:8170",
                        "party": "Phemacast",
                        "role": "manager",
                        "meta": {
                            "job_capabilities": [
                                {
                                    "name": "run map",
                                    "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                                    "description": "Execute one saved map.",
                                }
                            ]
                        },
                    },
                }
            ]
        if role == "worker":
            return [
                {
                    "name": "MapWorkerPulser",
                    "last_active": 150.0,
                    "card": {
                        "address": "http://127.0.0.1:8310",
                        "party": "Phemacast",
                        "role": "worker",
                        "description": "Ready to run one map job.",
                        "practices": [{"id": "worker-hire-manager"}],
                        "meta": {
                            "capabilities": ["run map"],
                            "job_capabilities": [
                                {
                                    "name": "run map",
                                    "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                                }
                            ],
                            "manager_assignment": {"status": "awaiting_hire"},
                        },
                    },
                }
            ]
        return []

    pulser.search = fake_search
    pulser._manager_pulser_is_reachable = lambda address: address == "http://127.0.0.1:8320"
    pulser._worker_is_reachable = lambda address: address == "http://127.0.0.1:8310"

    response = client.get("/api/provision/catalog", params={"party": "Phemacast"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["counts"]["job_capabilities"] == 1
    assert payload["counts"]["managers_for_hire"] == 1
    assert payload["counts"]["workers_for_hire"] == 1
    assert payload["job_capabilities"][0]["name"] == "run map"
    assert payload["managers_for_hire"][0]["name"] == "EastManagerPulser"
    assert payload["managers_for_hire"][0]["hire_ready"] is True
    assert payload["managers_for_hire"][0]["pulser_address"] == "http://127.0.0.1:8320"
    assert payload["workers_for_hire"][0]["name"] == "MapWorkerPulser"
    assert payload["workers_for_hire"][0]["worker_address"] == "http://127.0.0.1:8310"
    assert payload["workers_for_hire"][0]["hire_ready"] is True
    assert any(call.get("pit_type") == "Pulser" and call.get("role") == "manager_pulser" for call in search_calls)


def test_boss_pulser_provision_catalog_skips_unreachable_manager_pulsers():
    """
    Exercise the
    test_boss_pulser_provision_catalog_skips_unreachable_manager_pulsers
    regression scenario.
    """
    pulser = BossPulser(auto_register=False)
    client = TestClient(pulser.app)

    def fake_search(**kwargs):
        """Handle fake search."""
        role = kwargs.get("role")
        pit_type = kwargs.get("pit_type")
        if role == "manager_pulser" and pit_type == "Pulser":
            return [
                {
                    "name": "ManagerPulser-8230",
                    "last_active": 500.0,
                    "card": {
                        "address": "http://127.0.0.1:8230",
                        "party": "Phemacast",
                        "role": "manager_pulser",
                        "meta": {"supported_pulses": [{"name": "join_team"}]},
                    },
                },
                {
                    "name": "ManagerPulser-8320",
                    "last_active": 450.0,
                    "card": {
                        "address": "http://127.0.0.1:8320",
                        "party": "Phemacast",
                        "role": "manager_pulser",
                        "meta": {"supported_pulses": [{"name": "join_team"}]},
                    },
                },
            ]
        return []

    pulser.search = fake_search
    pulser._manager_pulser_is_reachable = lambda address: address == "http://127.0.0.1:8230"

    response = client.get("/api/provision/catalog", params={"party": "Phemacast"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["counts"]["managers_for_hire"] == 1
    assert payload["managers_for_hire"][0]["pulser_address"] == "http://127.0.0.1:8230"


def test_boss_pulser_team_status_summarizes_latest_job_and_worker_state():
    """
    Exercise the test_boss_pulser_team_status_summarizes_latest_job_and_worker_state
    regression scenario.
    """
    pulser = BossPulser(auto_register=False)

    pulser.search = lambda **kwargs: [
        {
            "name": "MapManager",
            "last_active": 200.0,
            "card": {
                "address": "http://127.0.0.1:8170",
                "party": "Phemacast",
                "role": "manager",
            },
        }
    ]

    now = datetime.now(timezone.utc)

    def fake_use_practice(practice_id, payload, pit_address=""):
        """Handle fake use practice."""
        assert pit_address == "http://127.0.0.1:8170"
        assert practice_id == "manager-db-preview-table"
        if payload["table_name"] == TABLE_JOBS:
            return {
                "rows": [
                    {"id": "job-1", "status": "queued", "required_capability": "run map", "updated_at": "2026-04-01T09:00:00+00:00", "priority": 100},
                    {"id": "job-1", "status": "claimed", "required_capability": "run map", "claimed_by": "worker-1", "updated_at": "2026-04-01T09:00:20+00:00", "priority": 100},
                    {"id": "job-2", "status": "completed", "required_capability": "run map", "updated_at": "2026-04-01T08:59:50+00:00", "completed_at": "2026-04-01T08:59:50+00:00", "priority": 100},
                ],
                "total_rows": 3,
            }
        if payload["table_name"] == TABLE_WORKERS:
            return {
                "rows": [
                    {
                        "worker_id": "worker-1",
                        "name": "MapWorker1",
                        "status": "online",
                        "last_seen_at": now.isoformat(),
                        "metadata": {"heartbeat": {"heartbeat_interval_sec": 15}},
                    },
                    {
                        "worker_id": "worker-2",
                        "name": "MapWorker2",
                        "status": "online",
                        "last_seen_at": (now - timedelta(minutes=5)).isoformat(),
                        "metadata": {"heartbeat": {"heartbeat_interval_sec": 15}},
                    },
                ],
                "total_rows": 2,
            }
        raise AssertionError(f"Unexpected table {payload['table_name']}")

    pulser.UsePractice = fake_use_practice

    result = pulser.get_pulse_data({"manager_address": "http://127.0.0.1:8170"}, pulse_name="team_status")

    assert result["jobs"]["total"] == 2
    assert result["jobs"]["by_status"]["claimed"] == 1
    assert result["jobs"]["by_status"]["completed"] == 1
    assert result["workers"]["total"] == 2
    assert result["workers"]["by_health"]["online"] == 1
    assert result["workers"]["by_health"]["offline"] == 1


def test_boss_pulser_submit_team_job_uses_manager_submit_practice():
    """
    Exercise the test_boss_pulser_submit_team_job_uses_manager_submit_practice
    regression scenario.
    """
    pulser = BossPulser(auto_register=False)

    captured = {}

    def fake_use_practice(practice_id, payload, pit_address=""):
        """Handle fake use practice."""
        captured["practice_id"] = practice_id
        captured["payload"] = payload
        captured["pit_address"] = pit_address
        return {"status": "success", "job": {"id": "manager-job:1", "required_capability": payload["required_capability"]}}

    pulser.UsePractice = fake_use_practice

    result = pulser.get_pulse_data(
        {
            "manager_address": "http://127.0.0.1:8170",
            "required_capability": "run map",
            "payload": {"phema_path": "phemacast/configs/map.phemar"},
            "priority": 110,
        },
        pulse_name="submit_team_job",
    )

    assert captured["practice_id"] == "manager-submit-job"
    assert captured["pit_address"] == "http://127.0.0.1:8170"
    assert captured["payload"]["required_capability"] == "run map"
    assert result["submitted"]["job"]["id"] == "manager-job:1"


def test_boss_pulser_create_manager_generates_manager_config():
    """
    Exercise the test_boss_pulser_create_manager_generates_manager_config regression
    scenario.
    """
    pulser = BossPulser(auto_register=False)

    result = pulser.get_pulse_data(
        {
            "team_name": "Map Runner",
            "manager_name": "MapRunnerManager",
            "party": "Phemacast",
            "plaza_url": "http://127.0.0.1:8011",
            "job_capabilities": [
                {
                    "name": "run map",
                    "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                    "description": "Execute one saved map.",
                    "default_priority": 100,
                }
            ],
        },
        pulse_name="create_manager",
    )

    assert result["team_name"] == "Map Runner"
    assert result["manager_address"] == "http://127.0.0.1:8170"
    assert result["manager_config"]["manager"]["job_capabilities"][0]["name"] == "run map"
    assert result["config_path"].endswith("/manager.agent")


def test_boss_pulser_connect_manager_joins_team_and_generates_local_workers():
    """
    Exercise the
    test_boss_pulser_connect_manager_joins_team_and_generates_local_workers
    regression scenario.
    """
    pulser = BossPulser(auto_register=False)

    team_result = pulser.get_pulse_data(
        {
            "team_name": "Map Runner",
            "party": "Phemacast",
            "plaza_url": "http://127.0.0.1:8011",
            "worker_count": 2,
            "job_capabilities": [
                {
                    "name": "run map",
                    "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                    "description": "Execute one saved map.",
                    "default_priority": 100,
                }
            ],
        },
        pulse_name="create_team",
    )

    client = TestClient(pulser.app)
    response = client.post(
        "/api/provision/connect-manager",
        json={
            "team_manifest": team_result["team_manifest"],
            "manager_name": "MapRunnerManagerEast",
            "manager_port": 8270,
            "worker_count": 2,
            "worker_name_prefix": "EastWorker",
            "worker_base_port": 8271,
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert payload["manager_address"] == "http://127.0.0.1:8270"
    assert payload["team_membership"]["status"] == "joined"
    assert payload["team_membership"]["local_worker_count"] == 2
    assert len(payload["worker_configs"]) == 2
    assert payload["worker_configs"][0]["worker"]["manager_address"] == "http://127.0.0.1:8270"
    assert payload["worker_configs"][0]["name"] == "EastWorker1"
    assert payload["config_paths"]["manager"].endswith("/manager.agent")
    assert payload["config_paths"]["workers"][0].endswith("/eastworker1.agent")
    assert payload["team_manifest"]["team_slug"] == "map-runner"


def test_boss_pulser_add_team_manager_route_joins_selected_manager():
    """
    Exercise the test_boss_pulser_add_team_manager_route_joins_selected_manager
    regression scenario.
    """
    pulser = BossPulser(auto_register=False)
    client = TestClient(pulser.app)

    base_team = pulser.get_pulse_data(
        {
            "team_name": "Map Runner",
            "party": "Phemacast",
            "plaza_url": "http://127.0.0.1:8011",
            "worker_count": 1,
            "job_capabilities": [{"name": "run map", "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap"}],
        },
        pulse_name="create_team",
    )

    captured = {}

    def fake_use_practice(practice_id, payload, pit_address=""):
        captured["practice_id"] = practice_id
        captured["payload"] = payload
        captured["pit_address"] = pit_address
        return {
            "status": "success",
            "manager_address": "http://127.0.0.1:8270",
            "team_membership": {
                "status": "joined",
                "manager_name": "EastManager",
                "manager_address": "http://127.0.0.1:8270",
                "local_worker_count": 1,
            },
            "worker_configs": [{"name": "EastWorker1"}],
        }

    pulser.UsePractice = fake_use_practice

    response = client.post(
        "/api/team-actions/add-manager",
        json={
            "team_name": "Map Runner",
            "team_manifest": base_team["team_manifest"],
            "manager_hires": [
                {
                    "pulser_address": "http://127.0.0.1:8320",
                    "pulser_name": "EastManagerPulser",
                    "manager_name": "EastManager",
                    "worker_count": 1,
                    "worker_name_prefix": "EastWorker",
                    "worker_base_port": 8271,
                }
            ],
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert captured["practice_id"] == "get_pulse_data"
    assert captured["pit_address"] == "http://127.0.0.1:8320"
    assert captured["payload"]["pulse_name"] == "join_team"
    assert payload["added"] == 1
    assert payload["primary_manager_address"] == "http://127.0.0.1:8270"
    assert payload["manager_hires"][0]["status"] == "joined"


def test_boss_pulser_hire_team_worker_route_assigns_selected_worker():
    """
    Exercise the
    test_boss_pulser_hire_team_worker_route_assigns_selected_worker regression
    scenario.
    """
    pulser = BossPulser(auto_register=False)
    client = TestClient(pulser.app)

    captured = {}

    def fake_use_practice(practice_id, payload, pit_address=""):
        captured["practice_id"] = practice_id
        captured["payload"] = payload
        captured["pit_address"] = pit_address
        return {"status": "assigned"}

    pulser.UsePractice = fake_use_practice

    response = client.post(
        "/api/team-actions/hire-worker",
        json={
            "party": "Phemacast",
            "manager_address": "http://127.0.0.1:8270",
            "manager_name": "EastManager",
            "worker_address": "http://127.0.0.1:8310",
            "worker_name": "MapWorkerPulser",
            "capability": "run map",
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert captured["practice_id"] == "worker-hire-manager"
    assert captured["pit_address"] == "http://127.0.0.1:8310"
    assert captured["payload"]["manager_address"] == "http://127.0.0.1:8270"
    assert payload["assignment"]["worker_address"] == "http://127.0.0.1:8310"
    assert payload["assignment"]["manager_address"] == "http://127.0.0.1:8270"


def test_boss_pulser_create_local_team_worker_route_uses_manager_pulser():
    """
    Exercise the
    test_boss_pulser_create_local_team_worker_route_uses_manager_pulser
    regression scenario.
    """
    pulser = BossPulser(auto_register=False)
    client = TestClient(pulser.app)

    captured = {}

    def fake_use_practice(practice_id, payload, pit_address=""):
        captured["practice_id"] = practice_id
        captured["payload"] = payload
        captured["pit_address"] = pit_address
        return {"worker_config": {"config_path": "/tmp/eastworker1.agent"}}

    pulser.UsePractice = fake_use_practice

    response = client.post(
        "/api/team-actions/create-local-worker",
        json={
            "party": "Phemacast",
            "manager_pulser_address": "http://127.0.0.1:8320",
            "team_name": "Map Runner",
            "manager_address": "http://127.0.0.1:8270",
            "worker_name": "EastWorker1",
            "worker_port": 8271,
            "capabilities": ["run map"],
            "job_capabilities": [{"name": "run map", "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap"}],
        },
    )

    payload = response.json()

    assert response.status_code == 200
    assert captured["practice_id"] == "get_pulse_data"
    assert captured["pit_address"] == "http://127.0.0.1:8320"
    assert captured["payload"]["pulse_name"] == "create_local_worker"
    assert payload["worker"]["manager_pulser_address"] == "http://127.0.0.1:8320"
    assert payload["worker"]["worker_config"]["config_path"].endswith("/eastworker1.agent")


def test_boss_pulser_root_renders_independent_management_ui():
    """
    Exercise the test_boss_pulser_root_renders_independent_management_ui regression
    scenario.
    """
    pulser = BossPulser(config={"party": "Phemacast"}, auto_register=False)
    client = TestClient(pulser.app)

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert "Phemacast Boss Pulse Deck" in response.text
    assert "Create Team" in response.text
    assert "Mission Console" in response.text
    assert "Right Workspace" in response.text
    assert ">Teams<" in response.text
    assert "Expand Overview" in response.text
    assert "Managers For Hire" in response.text
    assert "Job Cap Catalog" in response.text
    assert "Shared Settings" in response.text
    assert "Create Team" in response.text
    assert "Manager Join" not in response.text
    assert "Full Team" not in response.text
    assert "Job Capabilities JSON" not in response.text
    assert "Payload JSON" not in response.text


def test_boss_pulser_context_returns_examples_and_supported_pulses():
    """
    Exercise the test_boss_pulser_context_returns_examples_and_supported_pulses
    regression scenario.
    """
    pulser = BossPulser(config={"party": "Phemacast"}, auto_register=False)
    client = TestClient(pulser.app)

    response = client.get("/api/context")
    payload = response.json()

    assert response.status_code == 200
    assert payload["party"] == "Phemacast"
    assert "create_manager" in payload["supported_pulses"]
    assert "connect_manager" in payload["supported_pulses"]
    assert payload["examples"]["job_payload"]["phema_path"] == "phemacast/configs/map.phemar"
    assert payload["examples"]["team_manifest"]["api_version"] == "phemacast.team_manifest.v1"
    assert payload["defaults"]["hire_worker_count"] == 1


def test_boss_pulser_team_route_requires_manager_hire_when_requested():
    """
    Exercise the
    test_boss_pulser_team_route_requires_manager_hire_when_requested regression
    scenario.
    """
    pulser = BossPulser(config={"party": "Phemacast"}, auto_register=False)
    client = TestClient(pulser.app)

    response = client.post(
        "/api/provision/team",
        json={
            "team_name": "Map Runner",
            "party": "Phemacast",
            "plaza_url": "http://127.0.0.1:8011",
            "require_manager_hire": True,
            "start_hiring_managers": True,
            "job_capabilities": [
                {
                    "name": "run map",
                    "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                }
            ],
        },
    )

    assert response.status_code == 400
    assert "Select at least one manager for hire" in response.json()["detail"]


def test_build_agent_from_config_loads_boss_pulser(tmp_path):
    """
    Exercise the test_build_agent_from_config_loads_boss_pulser regression scenario.
    """
    config_path = tmp_path / "boss.pulser"
    config_path.write_text(
        """{
  "name": "BossPulser",
  "role": "boss",
  "host": "127.0.0.1",
  "port": 8220,
  "plaza_url": "http://127.0.0.1:8011",
  "party": "Phemacast",
  "type": "phemacast.pulsers.boss_pulser.BossPulser",
  "pools": [
    {
      "type": "SQLitePool",
      "name": "boss_pulser_pool",
      "description": "Local cache for BossPulser",
      "db_path": "boss_pulser.sqlite"
    }
  ]
}""",
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))

    pulse_names = {pulse["name"] for pulse in agent.supported_pulses}
    assert "create_team" in pulse_names
    assert "create_manager" in pulse_names
    assert "team_status" in pulse_names
    assert agent.agent_card["party"] == "Phemacast"
    assert agent.agent_card["role"] == "boss"


def test_boss_pulser_managed_work_api_creates_and_monitors_tickets(tmp_path):
    """
    Exercise the
    test_boss_pulser_managed_work_api_creates_and_monitors_tickets regression
    scenario.
    """
    pool = SQLitePool("boss_pulser_pool", "boss pulser pool", str(tmp_path / "boss_pulser.sqlite"))
    pulser = BossPulser(config={"party": "Phemacast"}, pool=pool, auto_register=False)
    client = TestClient(pulser.app)

    submitted_jobs = []
    captured_practices = []
    now_text = "2026-04-04T09:00:00+00:00"

    pulser.search = lambda **_kwargs: [
        {
            "name": "MapManager",
            "last_active": 200.0,
            "card": {
                "address": "http://127.0.0.1:8170",
                "party": "Phemacast",
                "role": "manager",
            },
        }
    ]

    def fake_use_practice(practice_id, payload, pit_address=""):
        """Handle fake use practice."""
        captured_practices.append((practice_id, payload, pit_address))
        assert pit_address == "http://127.0.0.1:8170"
        if practice_id == "manager-submit-job":
            job = {
                "id": payload["job_id"],
                "required_capability": payload["required_capability"],
                "targets": list(payload.get("targets") or []),
                "payload": payload.get("payload"),
                "target_table": payload.get("target_table") or "",
                "source_url": payload.get("source_url") or "",
                "parse_rules": payload.get("parse_rules") or {},
                "capability_tags": list(payload.get("capability_tags") or []),
                "job_type": payload.get("job_type") or "run",
                "priority": payload.get("priority") or 100,
                "premium": bool(payload.get("premium")),
                "metadata": payload.get("metadata") or {},
                "scheduled_for": payload.get("scheduled_for") or "",
                "status": "queued",
                "attempts": 0,
                "max_attempts": payload.get("max_attempts") or 3,
                "created_at": now_text,
                "updated_at": now_text,
            }
            submitted_jobs.append(job)
            return {"status": "success", "job": job}
        if practice_id == "manager-db-preview-table":
            if payload["table_name"] == TABLE_JOBS:
                return {"rows": list(submitted_jobs), "total_rows": len(submitted_jobs)}
            if payload["table_name"] == TABLE_WORKERS:
                return {
                    "rows": [
                        {
                            "worker_id": "worker-1",
                            "name": "MapWorker1",
                            "status": "online",
                            "last_seen_at": now_text,
                            "metadata": {"heartbeat": {"heartbeat_interval_sec": 15}},
                        }
                    ],
                    "total_rows": 1,
                }
            if payload["table_name"] == TABLE_WORKER_HISTORY:
                return {"rows": [], "total_rows": 0}
        raise AssertionError(f"Unexpected practice call: {practice_id}")

    pulser.UsePractice = fake_use_practice

    ticket_response = client.post(
        "/api/managed-work/tickets",
        json={
            "manager_address": "http://127.0.0.1:8170",
            "required_capability": "run map",
            "payload": {"phema_path": "phemacast/configs/map.phemar"},
            "targets": ["taipei-basemap"],
        },
    )

    assert ticket_response.status_code == 200
    ticket_payload = ticket_response.json()
    assert ticket_payload["ticket"]["manager_assignment"]["manager_address"] == "http://127.0.0.1:8170"

    schedule_response = client.post(
        "/api/managed-work/schedules",
        json={
            "manager_address": "http://127.0.0.1:8170",
            "required_capability": "run map",
            "scheduled_for": "2026-04-05T08:00:00+00:00",
            "payload": {"phema_path": "phemacast/configs/map.phemar"},
            "targets": ["taipei-basemap"],
        },
    )

    assert schedule_response.status_code == 200
    schedule_id = schedule_response.json()["schedule"]["schedule"]["id"]

    control_response = client.post(
        f"/api/managed-work/schedules/{schedule_id}/control",
        json={"action": "issue"},
    )

    assert control_response.status_code == 200
    assert captured_practices[1][0] == "manager-submit-job"
    assert captured_practices[1][1]["metadata"]["managed_work"]["schedule_id"] == schedule_id

    monitor_response = client.get(
        "/api/managed-work/monitor",
        params={"manager_address": "http://127.0.0.1:8170"},
    )

    assert monitor_response.status_code == 200
    monitor_payload = monitor_response.json()
    assert monitor_payload["api_version"] == "teamwork.v1"
    assert monitor_payload["manager_assignment"]["manager_address"] == "http://127.0.0.1:8170"
    assert monitor_payload["manager"]["manager_address"] == "http://127.0.0.1:8170"
    assert monitor_payload["workers"][0]["worker_id"] == "worker-1"
    assert monitor_payload["counts"]["tickets"] == 2
    assert monitor_payload["managed_work"]["manager_assignment"]["manager_address"] == "http://127.0.0.1:8170"
    assert len(monitor_payload["tickets"]) == 2
    assert monitor_payload["summary"]["workers"]["total"] == 1
    assert monitor_payload["schedules"][0]["schedule"]["id"] == schedule_id
