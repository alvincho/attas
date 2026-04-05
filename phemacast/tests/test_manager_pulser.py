"""
Regression tests for Manager Pulser.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the manager-local pulser that joins a
team manifest, provisions local workers, and exposes a manager-focused UI.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient

from phemacast.pulsers.boss_pulser import BossPulser
from phemacast.pulsers.manager_pulser import ManagerPulser
from prompits.tests.test_support import build_agent_from_config


def _team_manifest() -> dict:
    """Create one stable team manifest for manager pulser tests."""
    boss = BossPulser(auto_register=False)
    result = boss.get_pulse_data(
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
    return result["team_manifest"]


def test_manager_pulser_join_team_creates_manager_and_local_workers():
    """
    Exercise the
    test_manager_pulser_join_team_creates_manager_and_local_workers
    regression scenario.
    """
    pulser = ManagerPulser(auto_register=False)

    result = pulser.get_pulse_data(
        {
            "team_manifest": _team_manifest(),
            "manager_name": "MapRunnerManagerEast",
            "manager_port": 8270,
            "worker_count": 2,
            "worker_name_prefix": "EastWorker",
            "worker_base_port": 8271,
        },
        pulse_name="join_team",
    )

    assert result["team_membership"]["status"] == "joined"
    assert result["manager_address"] == "http://127.0.0.1:8270"
    assert result["team_membership"]["local_worker_count"] == 2
    assert len(result["worker_configs"]) == 2
    assert result["worker_configs"][0]["name"] == "EastWorker1"
    assert result["worker_configs"][0]["worker"]["manager_address"] == "http://127.0.0.1:8270"


def test_manager_pulser_root_renders_manager_local_ui():
    """
    Exercise the test_manager_pulser_root_renders_manager_local_ui regression
    scenario.
    """
    pulser = ManagerPulser(config={"party": "Phemacast"}, auto_register=False)
    client = TestClient(pulser.app)

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 200
    assert "Phemacast Manager Pulse Deck" in response.text
    assert "Local Manager Command" in response.text
    assert "Join Team" in response.text


def test_manager_pulser_route_aliases_join_team_and_local_worker_creation():
    """
    Exercise the
    test_manager_pulser_route_aliases_join_team_and_local_worker_creation
    regression scenario.
    """
    pulser = ManagerPulser(
        config={
            "party": "Phemacast",
            "manager_address": "http://127.0.0.1:8270",
        },
        auto_register=False,
    )
    client = TestClient(pulser.app)

    join_response = client.post(
        "/api/team/join",
        json={
            "team_manifest": _team_manifest(),
            "manager_name": "MapRunnerManagerEast",
            "manager_port": 8270,
            "worker_count": 1,
            "worker_name_prefix": "EastWorker",
            "worker_base_port": 8271,
        },
    )
    worker_response = client.post(
        "/api/workers/local",
        json={
            "team_name": "Map Runner",
            "worker_name": "EastWorkerExtra",
            "manager_address": "http://127.0.0.1:8270",
            "job_capabilities": [
                {
                    "name": "run map",
                    "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                }
            ],
        },
    )

    assert join_response.status_code == 200
    assert join_response.json()["team_membership"]["local_worker_count"] == 1
    assert worker_response.status_code == 200
    assert worker_response.json()["worker_config"]["worker"]["manager_address"] == "http://127.0.0.1:8270"


def test_build_agent_from_config_loads_manager_pulser(tmp_path):
    """
    Exercise the test_build_agent_from_config_loads_manager_pulser regression
    scenario.
    """
    config_path = tmp_path / "manager.pulser"
    config_path.write_text(
        """{
  "name": "ManagerPulser",
  "role": "manager_pulser",
  "host": "127.0.0.1",
  "port": 8320,
  "plaza_url": "http://127.0.0.1:8011",
  "party": "Phemacast",
  "type": "phemacast.pulsers.manager_pulser.ManagerPulser",
  "pools": [
    {
      "type": "SQLitePool",
      "name": "manager_pulser_pool",
      "description": "Local cache for ManagerPulser",
      "db_path": "manager_pulser.sqlite"
    }
  ]
}""",
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))

    pulse_names = {pulse["name"] for pulse in agent.supported_pulses}
    assert "join_team" in pulse_names
    assert "create_local_worker" in pulse_names
    assert agent.name == "ManagerPulser-8320"
    assert agent.agent_card["name"] == "ManagerPulser-8320"
    assert agent.agent_card["role"] == "manager_pulser"
