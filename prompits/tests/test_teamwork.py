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
from prompits.teamwork.boss import TeamBossAgent
from prompits.teamwork.runtime import build_managed_work_metadata
from prompits.teamwork.schema import TABLE_JOBS


def _plaza_worker_entry(worker, *, address: str, last_active: float = 100.0):
    """Build a Plaza-style worker search result for teamwork tests."""
    card = dict(worker.agent_card)
    meta = dict(card.get("meta") or {})
    card["address"] = address
    card["capabilities"] = list(getattr(worker, "capabilities", []) or [])
    card["practices"] = [{"id": "worker-hire-manager"}]
    card["meta"] = meta
    return {
        "agent_id": worker.worker_id,
        "name": worker.name,
        "address": address,
        "last_active": last_active,
        "card": card,
    }


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


def test_team_worker_with_hire_required_waits_for_explicit_hire():
    """
    Exercise the
    test_team_worker_with_hire_required_waits_for_explicit_hire regression scenario.
    """
    worker = TeamWorkerAgent(
        name="TeamWorker",
        plaza_url="http://127.0.0.1:8011",
        capabilities=["echo job"],
        hire_required=True,
        auto_register=False,
    )

    practice_calls = []

    def fake_use_practice(practice_id, payload, pit_address=""):
        """Handle fake practice calls."""
        practice_calls.append((practice_id, pit_address, payload))
        return {"status": "unexpected"}

    worker.UsePractice = fake_use_practice

    response = worker.request_job()
    run_once_response = worker.run_once()
    practice_ids = {practice.id for practice in worker.practices}

    assert response["status"] == "waiting_for_hire"
    assert response["job"] is None
    assert response["manager_assignment"]["status"] == "awaiting_hire"
    assert response["manager_assignment"]["manager_address"] == ""
    assert run_once_response["status"] == "waiting_for_hire"
    assert worker.agent_card["meta"]["manager_assignment"]["hire_required"] is True
    assert "worker-hire-manager" in practice_ids
    assert practice_calls == []


def test_team_manager_can_hire_available_worker_via_plaza():
    """
    Exercise the
    test_team_manager_can_hire_available_worker_via_plaza regression scenario.
    """
    pool = SQLitePool("team_manager_pool", "team manager pool", ":memory:")
    manager = TeamManagerAgent(
        name="TeamManager",
        host="127.0.0.1",
        port=8070,
        plaza_url="http://127.0.0.1:8011",
        pool=pool,
        auto_register=False,
    )
    worker = TeamWorkerAgent(
        name="TeamWorker",
        host="127.0.0.1",
        port=8071,
        plaza_url="http://127.0.0.1:8011",
        capabilities=["echo job"],
        hire_required=True,
        auto_register=False,
    )

    search_calls = []
    manager.search = lambda **kwargs: (search_calls.append(kwargs) or [_plaza_worker_entry(worker, address="http://127.0.0.1:8071")])

    practice_calls = []

    def fake_use_practice(practice_id, payload, pit_address=""):
        """Handle fake practice calls."""
        practice_calls.append((practice_id, pit_address, payload))
        assert practice_id == "worker-hire-manager"
        assert pit_address == "http://127.0.0.1:8071"
        return worker.accept_manager_hire(**payload)

    manager.UsePractice = fake_use_practice

    response = manager.hire_worker(capability="echo job")

    assert search_calls[0]["role"] == "worker"
    assert search_calls[0]["capability"] == "echo job"
    assert response["status"] == "hired"
    assert response["worker_address"] == "http://127.0.0.1:8071"
    assert worker.manager_address == "http://127.0.0.1:8070"
    assert worker.agent_card["meta"]["manager_assignment"]["status"] == "hired"
    assert worker.agent_card["meta"]["manager_assignment"]["manager_name"] == "TeamManager"
    assert practice_calls[0][0] == "worker-hire-manager"


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


def test_team_manager_records_explicit_worker_assignment_for_managed_work(tmp_path):
    """
    Exercise the
    test_team_manager_records_explicit_worker_assignment_for_managed_work
    regression scenario.
    """
    pool = SQLitePool("team_manager_pool", "team manager pool", str(tmp_path / "managed_work.sqlite"))
    agent = TeamManagerAgent(
        name="TeamManager",
        pool=pool,
        auto_register=False,
    )

    agent.submit_job(
        required_capability="echo job",
        payload={"message": "hello"},
        metadata=build_managed_work_metadata(
            {"request_id": "req-1"},
            work_id="work-1",
            ticket_id="ticket-1",
            source="manual",
            manager_address="http://127.0.0.1:8070",
            manager_name="TeamManager",
            manager_party="Prompits",
            title="Echo Job",
        ),
        job_id="ticket-1",
    )

    claimed = agent.get_job(
        worker_id="worker-1",
        capabilities=["echo job"],
        name="Worker One",
        address="http://127.0.0.1:8071",
    )

    assert claimed["job"]["id"] == "ticket-1"

    claimed_row = agent._latest_job_rows(pool._GetTableData(TABLE_JOBS, "ticket-1") or [])[0]
    managed = claimed_row["metadata"]["managed_work"]

    assert managed["manager_assignment"]["manager_address"] == "http://127.0.0.1:8070"
    assert managed["worker_assignment"]["worker_id"] == "worker-1"
    assert managed["worker_assignment"]["status"] == "claimed"
    assert managed["execution_state"]["status"] == "claimed"

    agent.post_job_result(
        {
            "job_id": "ticket-1",
            "worker_id": "worker-1",
            "status": "completed",
            "result_summary": {"rows": 1},
        }
    )

    completed_row = agent._latest_job_rows(pool._GetTableData(TABLE_JOBS, "ticket-1") or [])[0]
    managed_completed = completed_row["metadata"]["managed_work"]

    assert managed_completed["worker_assignment"]["status"] == "completed"
    assert managed_completed["execution_state"]["status"] == "completed"
    assert managed_completed["result_summary"]["rows"] == 1


def test_team_boss_routes_manual_and_scheduled_work_through_manager_practices(tmp_path):
    """
    Exercise the
    test_team_boss_routes_manual_and_scheduled_work_through_manager_practices
    regression scenario.
    """
    pool = SQLitePool("team_boss_pool", "team boss pool", str(tmp_path / "team_boss.sqlite"))
    agent = TeamBossAgent(
        name="TeamBoss",
        pool=pool,
        manager_address="http://127.0.0.1:8070",
        auto_register=False,
    )

    practice_calls = []

    def fake_use_practice(practice_id, payload, pit_address=""):
        """Handle fake use practice."""
        practice_calls.append((practice_id, payload, pit_address))
        if practice_id == "manager-submit-job":
            return {
                "status": "success",
                "job": {
                    "id": payload["job_id"],
                    "required_capability": payload["required_capability"],
                    "targets": payload["targets"],
                    "payload": payload.get("payload"),
                    "metadata": payload.get("metadata"),
                    "status": "queued",
                    "priority": payload.get("priority", 100),
                    "max_attempts": payload.get("max_attempts", 3),
                    "created_at": "2026-04-04T00:00:00+00:00",
                    "updated_at": "2026-04-04T00:00:00+00:00",
                },
            }
        raise AssertionError(f"Unexpected practice call: {practice_id}")

    agent.UsePractice = fake_use_practice

    ticket = agent.create_managed_ticket(
        {
            "required_capability": "echo job",
            "payload": {"message": "hello"},
        }
    )

    assert practice_calls[0][0] == "manager-submit-job"
    assert practice_calls[0][2] == "http://127.0.0.1:8070"
    assert ticket["ticket"]["manager_assignment"]["manager_address"] == "http://127.0.0.1:8070"
    assert practice_calls[0][1]["metadata"]["managed_work"]["ticket_id"] == ticket["ticket"]["ticket"]["id"]

    schedule = agent.create_managed_schedule(
        {
            "required_capability": "echo job",
            "scheduled_for": "2026-04-05T00:00:00+00:00",
            "payload": {"message": "later"},
        }
    )
    schedule_id = schedule["schedule"]["schedule"]["id"]

    issued = agent.issue_scheduled_job(schedule_id, force_now=True)

    assert practice_calls[1][0] == "manager-submit-job"
    assert practice_calls[1][2] == "http://127.0.0.1:8070"
    assert practice_calls[1][1]["metadata"]["managed_work"]["schedule_id"] == schedule_id
    assert issued["submission"]["job"]["id"] == practice_calls[1][1]["job_id"]

    schedules = agent.list_managed_schedules()

    assert schedules["schedules"][0]["schedule"]["id"] == schedule_id


def test_team_boss_managed_monitor_summary_exposes_stable_work_contract(tmp_path):
    """
    Exercise the
    test_team_boss_managed_monitor_summary_exposes_stable_work_contract regression
    scenario.
    """
    pool = SQLitePool("team_boss_pool", "team boss pool", str(tmp_path / "team_boss_monitor.sqlite"))
    agent = TeamBossAgent(
        name="TeamBoss",
        pool=pool,
        manager_address="http://127.0.0.1:8070",
        auto_register=False,
    )

    agent._monitor_summary = lambda *, dispatcher_address: {
        "status": "success",
        "dispatcher": {
            "address": dispatcher_address,
            "queued_jobs": 1,
            "active_workers": 1,
            "total_workers": 1,
        },
        "workers": [
            {
                "worker_id": "worker-1",
                "name": "Worker One",
                "status": "online",
            }
        ],
    }
    agent.list_managed_tickets = lambda **_kwargs: {
        "status": "success",
        "tickets": [
            {
                "ticket": {"id": "ticket-1", "title": "Morning Desk Briefing"},
                "work_item": {"title": "Morning Desk Briefing", "required_capability": "publish briefing"},
                "manager_assignment": {"manager_address": "http://127.0.0.1:8070"},
                "worker_assignment": {"worker_id": "worker-1", "status": "completed"},
                "execution_state": {"status": "completed"},
                "result_summary": {"status": "completed", "summary": {"rows": 1}},
            }
        ],
    }
    agent.list_managed_schedules = lambda **_kwargs: {
        "status": "success",
        "schedules": [
            {
                "schedule": {"id": "schedule-1", "status": "scheduled"},
                "work_item": {"title": "Morning Desk Briefing", "required_capability": "publish briefing"},
                "manager_assignment": {"manager_address": "http://127.0.0.1:8070"},
            }
        ],
    }

    payload = agent.managed_monitor_summary(manager_address="http://127.0.0.1:8070")

    assert payload["api_version"] == "teamwork.v1"
    assert payload["manager_assignment"]["manager_address"] == "http://127.0.0.1:8070"
    assert payload["manager"]["manager_address"] == "http://127.0.0.1:8070"
    assert payload["workers"][0]["worker_id"] == "worker-1"
    assert payload["counts"]["tickets"] == 1
    assert payload["managed_work"]["tickets"][0]["ticket"]["id"] == "ticket-1"
    assert payload["managed_work"]["schedules"][0]["schedule"]["id"] == "schedule-1"
