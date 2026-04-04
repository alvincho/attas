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
    assert result["worker_configs"][0]["worker"]["job_capabilities"][0]["name"] == "run map"
    assert result["boss_config"]["boss"]["job_capabilities"][0]["default_priority"] == 110
    assert result["config_paths"]["boss"].endswith("/boss.agent")


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
    assert "Provisioning Studio" in response.text
    assert "Mission Console" in response.text


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
    assert payload["examples"]["job_payload"]["phema_path"] == "phemacast/configs/map.phemar"


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
