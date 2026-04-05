"""
Regression tests for Castr Work Pulser.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the MapCastr-ready worker pulser that
advertises its job capability and executes manager-assigned Castr work.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.pulsers.castr_work_pulser import CastrWorkPulser
from prompits.pools.filesystem import FileSystemPool
from prompits.pools.sqlite import SQLitePool
from prompits.teamwork.agents import TeamManagerAgent
from prompits.teamwork.schema import TABLE_JOBS, TABLE_WORKERS
from prompits.tests.test_support import build_agent_from_config


class FakeResponse:
    """Response model for fake payloads."""

    def __init__(self, payload, status_code=200):
        """Initialize the fake response."""
        self._payload = payload
        self.status_code = status_code

    def json(self):
        """Return the fake payload."""
        return self._payload


def _simple_map_phema():
    """Return a compact MapPhemar-compatible phema fixture."""
    return {
        "phema_id": "daily-ohlc-diagram",
        "name": "Daily OHLC Diagram",
        "input_schema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
            },
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "bars": {"type": "array"},
                "symbol": {"type": "string"},
                "limit": {"type": "integer"},
                "interval": {"type": "string"},
            },
        },
        "meta": {
            "map_phemar": {
                "version": 1,
                "diagram": {
                    "plazaUrl": "http://127.0.0.1:8011",
                    "nodes": [
                        {
                            "id": "mind-boundary-input",
                            "role": "input",
                            "type": "pill",
                            "title": "Input",
                            "outputSchema": {"type": "object", "properties": {"symbol": {"type": "string"}}},
                        },
                        {
                            "id": "node-fetch",
                            "type": "rounded",
                            "title": "Fetch OHLC",
                            "pulserName": "ChartPulser",
                            "practiceId": "get_pulse_data",
                            "pulseName": "ohlc_bar_series",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "symbol": {"type": "string"},
                                    "limit": {"type": "integer"},
                                    "interval": {"type": "string"},
                                },
                            },
                            "outputSchema": {
                                "type": "object",
                                "properties": {
                                    "bars": {"type": "array"},
                                    "symbol": {"type": "string"},
                                    "limit": {"type": "integer"},
                                    "interval": {"type": "string"},
                                },
                            },
                        },
                        {
                            "id": "mind-boundary-output",
                            "role": "output",
                            "type": "pill",
                            "title": "Output",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "bars": {"type": "array"},
                                    "symbol": {"type": "string"},
                                    "limit": {"type": "integer"},
                                    "interval": {"type": "string"},
                                },
                            },
                        },
                    ],
                    "edges": [
                        {"id": "edge-input", "from": "mind-boundary-input", "to": "node-fetch", "mappingText": "{}"},
                        {"id": "edge-output", "from": "node-fetch", "to": "mind-boundary-output", "mappingText": "{}"},
                    ],
                },
            }
        },
    }


def _plaza_worker_entry(worker, *, address: str, last_active: float = 100.0):
    """Build a Plaza-style worker search result for Castr worker tests."""
    card = dict(worker.agent_card)
    card["address"] = address
    card["capabilities"] = list(worker.agent_card.get("capabilities") or [])
    card["practices"] = [{"id": "worker-hire-manager"}]
    return {
        "agent_id": worker.worker_id,
        "name": worker.name,
        "address": address,
        "last_active": last_active,
        "card": card,
    }


def test_castr_work_pulser_advertises_map_job_cap_metadata():
    """
    Exercise the test_castr_work_pulser_advertises_map_job_cap_metadata regression
    scenario.
    """
    pulser = CastrWorkPulser(auto_register=False)

    assert pulser.agent_card["role"] == "worker"
    assert "run map" in pulser.agent_card["capabilities"]
    assert pulser.agent_card["job_capabilities"][0]["name"] == "run map"
    assert pulser.agent_card["job_capabilities"][0]["callable"] == "phemacast.jobcaps.map_jobcap:RunMapJobCap"
    assert pulser.agent_card["meta"]["castr_profile"] == "map"
    assert pulser.hire_required is True
    assert pulser.agent_card["meta"]["manager_assignment"]["status"] == "awaiting_hire"
    assert pulser.agent_card["meta"]["manager_assignment"]["manager_address"] == ""
    assert pulser.agent_card["meta"].get("manager_address") is None


def test_castr_work_pulser_can_be_hired_by_manager_and_run_map_castr(tmp_path):
    """
    Exercise the
    test_castr_work_pulser_can_be_hired_by_manager_and_run_map_castr regression
    scenario.
    """
    manager_pool = SQLitePool("team_manager_pool", "team manager pool", str(tmp_path / "manager.sqlite"))
    manager = TeamManagerAgent(
        name="MapManager",
        host="127.0.0.1",
        port=8270,
        pool=manager_pool,
        auto_register=False,
    )
    worker_root = tmp_path / "worker_pool"
    worker_pool = FileSystemPool("castr_work_pool", "castr work pool", str(worker_root))
    worker = CastrWorkPulser(
        name="MapCastrWorkPulser",
        pool=worker_pool,
        auto_register=False,
        capabilities=["run map"],
        job_capabilities=[
            {
                "name": "run map",
                "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                "target_table": "dispatcher_map_runs",
            }
        ],
    )

    def fake_post(url, json=None, timeout=None):
        """Handle fake post."""
        return FakeResponse(
            {
                "status": "success",
                "result": {
                    "symbol": json["input"]["symbol"],
                    "limit": json["input"]["limit"],
                    "interval": json["input"]["interval"],
                    "bars": [8, 13, 21],
                },
            }
        )

    worker.job_capabilities["run map"].request_post = fake_post

    waiting = worker.request_job()

    assert waiting["status"] == "waiting_for_hire"
    assert waiting["manager_assignment"]["status"] == "awaiting_hire"
    assert worker.manager_address == ""

    manager.search = lambda **_kwargs: [_plaza_worker_entry(worker, address="http://127.0.0.1:8281")]

    hire_calls = []

    def fake_manager_use_practice(practice_id, payload, pit_address=""):
        """Handle fake manager-side practice calls."""
        hire_calls.append((practice_id, pit_address))
        assert practice_id == "worker-hire-manager"
        assert pit_address == "http://127.0.0.1:8281"
        return worker.accept_manager_hire(**payload)

    manager.UsePractice = fake_manager_use_practice

    hire_response = manager.hire_worker(capability="run map")

    assert hire_response["status"] == "hired"
    assert worker.manager_address == "http://127.0.0.1:8270"
    assert worker.agent_card["meta"]["manager_assignment"]["manager_name"] == "MapManager"
    assert hire_calls[0] == ("worker-hire-manager", "http://127.0.0.1:8281")

    practice_calls = []

    def fake_use_practice(practice_id, payload, pit_address=""):
        """Handle fake use practice."""
        practice_calls.append((practice_id, pit_address))
        assert pit_address == "http://127.0.0.1:8270"
        if practice_id == "manager-register-worker":
            return manager.register_worker(**payload)
        if practice_id == "manager-get-job":
            return manager.get_job(**payload)
        if practice_id == "manager-post-job-result":
            return manager.post_job_result(payload)
        raise AssertionError(f"Unexpected practice call: {practice_id}")

    worker.UsePractice = fake_use_practice

    manager.submit_job(
        required_capability="run map",
        payload={
            "phema": _simple_map_phema(),
            "input": {"symbol": "TSLA"},
            "extra_parameters": {"limit": 7},
            "node_parameters": {"node-fetch": {"interval": "4h"}},
        },
        job_id="manager-job:run-map:1",
    )

    outcome = worker.run_once()

    assert outcome["status"] == "completed"
    assert outcome["job_result"].target_table == "dispatcher_map_runs"
    assert outcome["job_result"].collected_rows[0]["result"]["bars"] == [8, 13, 21]
    assert outcome["report"]["stored_rows"] == 1
    manager_calls = [entry[0] for entry in practice_calls if entry[0].startswith("manager-")]
    assert manager_calls[0] == "manager-register-worker"
    assert "manager-get-job" in manager_calls
    assert "manager-post-job-result" in manager_calls
    assert manager_calls.index("manager-get-job") < manager_calls.index("manager-post-job-result")

    worker_rows = manager.pool._GetTableData(TABLE_WORKERS, worker.worker_id) or []
    latest_worker = worker_rows[-1]
    assert latest_worker["capabilities"] == ["run map"]
    assert latest_worker["metadata"]["job_capabilities"][0]["name"] == "run map"
    assert latest_worker["metadata"]["manager_assignment"]["status"] == "hired"
    assert latest_worker["metadata"]["manager_assignment"]["manager_address"] == "http://127.0.0.1:8270"

    job_rows = manager._latest_job_rows(manager.pool._GetTableData(TABLE_JOBS, "manager-job:run-map:1") or [])
    assert job_rows[0]["status"] == "completed"

    artifacts = list((worker_root / "media").glob("*.json"))
    assert len(artifacts) == 1
    artifact_payload = json.loads(artifacts[0].read_text(encoding="utf-8"))
    assert artifact_payload["execution"]["output"]["bars"] == [8, 13, 21]


def test_build_agent_from_config_loads_castr_work_pulser(tmp_path):
    """
    Exercise the test_build_agent_from_config_loads_castr_work_pulser regression
    scenario.
    """
    config_path = tmp_path / "castr_work.pulser"
    config_path.write_text(
        """{
  "name": "MapCastrWorkPulser",
  "role": "worker",
  "host": "127.0.0.1",
  "port": 8281,
  "party": "Phemacast",
  "type": "phemacast.pulsers.castr_work_pulser.CastrWorkPulser",
  "worker": {
    "auto_register": false
  },
  "pools": [
    {
      "type": "FileSystemPool",
      "name": "castr_work_pool",
      "description": "Local artifact storage for CastrWorkPulser outputs.",
      "root_path": "castr_work_storage"
    }
  ]
}""",
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))

    assert type(agent).__name__ == "CastrWorkPulser"
    assert agent.hire_required is True
    assert agent.agent_card["job_capabilities"][0]["name"] == "run map"
    assert "run map" in agent.agent_card["capabilities"]
    assert agent.agent_card["meta"]["manager_assignment"]["status"] == "awaiting_hire"
    assert agent.manager_address == ""
