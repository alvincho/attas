"""
Regression tests for Teamwork.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_team_manager_registers_manager_alias_practices`,
`test_team_manager_can_delegate_as_worker_to_parent_manager`, and
`test_team_worker_discovers_manager_and_requests_jobs_via_manager_practices`, helping
guard against regressions as the packages evolve.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.pools.sqlite import SQLitePool
from prompits.teamwork.agents import TeamManagerAgent, TeamWorkerAgent


def test_team_manager_registers_manager_alias_practices(tmp_path):
    """
    Exercise the test_team_manager_registers_manager_alias_practices regression
    scenario.
    """
    pool = SQLitePool("team_manager_pool", "team manager pool", str(tmp_path / "team_manager.sqlite"))
    agent = TeamManagerAgent(
        name="TeamManager",
        pool=pool,
        auto_register=False,
    )

    practice_ids = {practice.id for practice in agent.practices}

    assert "dispatcher-submit-job" in practice_ids
    assert "manager-submit-job" in practice_ids
    assert "manager-get-job" in practice_ids
    assert "manager-post-job-result" in practice_ids
    assert "manager-db-preview-table" in practice_ids


def test_team_worker_discovers_manager_and_requests_jobs_via_manager_practices():
    """
    Exercise the
    test_team_worker_discovers_manager_and_requests_jobs_via_manager_practices
    regression scenario.
    """
    worker = TeamWorkerAgent(
        name="TeamWorker",
        plaza_url="http://127.0.0.1:8011",
        capabilities=["echo job"],
        auto_register=False,
    )
    worker.plaza_token = "token"

    worker.search = lambda **_kwargs: [
        {
            "agent_id": "manager-1",
            "name": "TeamManager",
            "last_active": 100.0,
            "card": {
                "address": "http://127.0.0.1:8070",
                "party": "Prompits",
                "role": "manager",
                "tags": ["manager"],
                "practices": [{"id": "manager-get-job"}],
            },
        }
    ]

    practice_calls = []

    def fake_use_practice(practice_id, payload, pit_address=""):
        """Handle fake use practice."""
        practice_calls.append((practice_id, pit_address))
        if practice_id == "manager-get-job":
            return {
                "job": {
                    "id": "manager-job:1",
                    "required_capability": "echo job",
                    "status": "claimed",
                    "payload": {"message": "hello"},
                    "attempts": 1,
                    "max_attempts": 3,
                }
            }
        return {"status": "success"}

    worker.UsePractice = fake_use_practice

    response = worker.request_job()

    assert worker.manager_address == "http://127.0.0.1:8070"
    assert response["job"].id == "manager-job:1"
    assert practice_calls[0] == ("manager-get-job", "http://127.0.0.1:8070")


def test_team_manager_can_delegate_as_worker_to_parent_manager(tmp_path):
    """
    Exercise the test_team_manager_can_delegate_as_worker_to_parent_manager
    regression scenario.
    """
    pool = SQLitePool("team_manager_pool", "team manager pool", str(tmp_path / "delegating_manager.sqlite"))
    agent = TeamManagerAgent(
        name="DelegatingManager",
        pool=pool,
        plaza_url="http://127.0.0.1:8011",
        auto_register=False,
    )
    agent.plaza_token = "token"

    agent.search = lambda **_kwargs: [
        {
            "agent_id": "manager-parent",
            "name": "ParentManager",
            "last_active": 100.0,
            "card": {
                "address": "http://127.0.0.1:8079",
                "party": "Prompits",
                "role": "manager",
                "tags": ["manager"],
                "practices": [{"id": "manager-get-job"}],
            },
        }
    ]

    practice_calls = []

    def fake_use_practice(practice_id, payload, pit_address=""):
        """Handle fake use practice."""
        practice_calls.append((practice_id, pit_address))
        if practice_id == "manager-get-job":
            return {
                "job": {
                    "id": "parent-job:1",
                    "required_capability": "echo job",
                    "status": "claimed",
                    "payload": {"message": "delegate me"},
                    "attempts": 1,
                    "max_attempts": 3,
                }
            }
        return {"status": "success", "job": payload}

    agent.UsePractice = fake_use_practice

    result = agent.run_delegate_once(
        lambda job: {"status": "completed", "result_summary": {"message": job.payload["message"]}},
        capabilities=["echo job"],
    )

    assert result["status"] == "completed"
    assert [entry[0] for entry in practice_calls] == [
        "manager-register-worker",
        "manager-get-job",
        "manager-register-worker",
        "manager-post-job-result",
    ]
    assert all(entry[1] == "http://127.0.0.1:8079" for entry in practice_calls)
