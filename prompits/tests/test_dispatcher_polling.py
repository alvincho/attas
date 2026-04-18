"""
Regression tests for Dispatcher Polling.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_get_job_uses_bounded_candidate_query_before_full_job_scan` and
`test_poll_registration_skips_history_and_stale_recovery`, helping guard against
regressions as the packages evolve.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.dispatcher.archive_jobs import DailyJobArchiveJobCap
from prompits.dispatcher.agents import DispatcherAgent, DispatcherWorkerAgent
from prompits.dispatcher.models import JobDetail, JobResult
from prompits.dispatcher.schema import (
    TABLE_JOB_ARCHIVE,
    TABLE_JOBS,
    TABLE_RAW_PAYLOADS,
    TABLE_RAW_PAYLOADS_ARCHIVE,
    TABLE_RESULT_ROWS,
    TABLE_RESULT_ROWS_ARCHIVE,
    TABLE_WORKER_HISTORY_ARCHIVE,
    TABLE_WORKER_HISTORY,
    ensure_dispatcher_tables,
)
from prompits.pools.sqlite import SQLitePool


def test_poll_registration_skips_history_and_stale_recovery(tmp_path, monkeypatch):
    """
    Exercise the test_poll_registration_skips_history_and_stale_recovery regression
    scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool)
    agent = DispatcherAgent(pool=pool)

    recover_calls: list[str] = []

    def fake_recover(*, now_text: str = "") -> int:
        """Handle fake recover."""
        recover_calls.append(str(now_text or ""))
        return 0

    monkeypatch.setattr(agent, "_recover_stale_worker_jobs", fake_recover)

    poll_response = agent.register_worker(
        worker_id="worker-a",
        name="Worker A",
        capabilities=["UPU WNS Listing"],
        event_type="poll",
    )

    assert poll_response["status"] == "success"
    assert recover_calls == []
    assert pool._GetTableData(TABLE_WORKER_HISTORY) == []

    agent.stale_recovery_interval_sec = 0.0
    heartbeat_response = agent.register_worker(
        worker_id="worker-a",
        name="Worker A",
        capabilities=["UPU WNS Listing"],
        event_type="heartbeat",
    )

    assert heartbeat_response["status"] == "success"
    assert len(recover_calls) == 1
    assert pool._GetTableData(TABLE_WORKER_HISTORY) == []


def test_ensure_dispatcher_tables_creates_ready_and_history_indexes(tmp_path):
    """Ensure dispatcher schema setup creates the composite indexes used at runtime."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool)

    job_indexes = {str(row[1]) for row in pool._Query(f"PRAGMA index_list('{TABLE_JOBS}')")}
    archive_indexes = {str(row[1]) for row in pool._Query(f"PRAGMA index_list('{TABLE_JOB_ARCHIVE}')")}
    worker_history_indexes = {str(row[1]) for row in pool._Query(f"PRAGMA index_list('{TABLE_WORKER_HISTORY}')")}
    worker_history_archive_indexes = {str(row[1]) for row in pool._Query(f"PRAGMA index_list('{TABLE_WORKER_HISTORY_ARCHIVE}')")}
    job_results_indexes = {str(row[1]) for row in pool._Query(f"PRAGMA index_list('{TABLE_RESULT_ROWS}')")}
    job_results_archive_indexes = {str(row[1]) for row in pool._Query(f"PRAGMA index_list('{TABLE_RESULT_ROWS_ARCHIVE}')")}
    raw_payloads_indexes = {str(row[1]) for row in pool._Query(f"PRAGMA index_list('{TABLE_RAW_PAYLOADS}')")}
    raw_payloads_archive_indexes = {str(row[1]) for row in pool._Query(f"PRAGMA index_list('{TABLE_RAW_PAYLOADS_ARCHIVE}')")}

    assert {
        "dispatcher_jobs_status_idx",
        "dispatcher_jobs_ready_order_idx",
        "dispatcher_jobs_ready_schedule_idx",
        "dispatcher_jobs_ready_capability_idx",
        "dispatcher_jobs_claimed_worker_idx",
        "dispatcher_jobs_status_pipeline_logical_key_idx",
    }.issubset(job_indexes)
    assert "dispatcher_jobs_archive_completed_idx" in archive_indexes
    assert "dispatcher_worker_history_worker_captured_idx" in worker_history_indexes
    assert "dispatcher_worker_history_captured_idx" in worker_history_indexes
    assert "dispatcher_worker_history_archive_captured_idx" in worker_history_archive_indexes
    assert "dispatcher_job_results_recorded_idx" in job_results_indexes
    assert "dispatcher_job_results_archive_recorded_idx" in job_results_archive_indexes
    assert "dispatcher_raw_payloads_collected_idx" in raw_payloads_indexes
    assert "dispatcher_raw_payloads_archive_collected_idx" in raw_payloads_archive_indexes


def test_daily_job_archive_job_cap_moves_completed_jobs_to_archive(tmp_path):
    """Ensure the dispatcher archive-sweep job cap moves completed rows into the archive."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool)

    completed_job_id = "dispatcher-job:completed-archive-me"
    assert pool._Insert(
        TABLE_JOBS,
        {
            "id": completed_job_id,
            "status": "completed",
            "required_capability": "UPU WNS Listing",
            "payload": {"page": 1},
            "priority": 105,
            "completed_at": "2026-04-13T01:59:00+00:00",
            "created_at": "2026-04-13T01:55:00+00:00",
            "updated_at": "2026-04-13T01:59:00+00:00",
        },
    )

    cap = DailyJobArchiveJobCap()
    cap.bind_worker(type("WorkerStub", (), {"pool": pool})())

    result = cap.finish(
        JobDetail(
            id="dispatcher-job:daily-archive-run",
            required_capability="daily job archive",
            status="claimed",
            payload={"batch_size": 10},
        )
    )

    assert result.status == "completed"
    assert result.result_summary["archived_jobs"] == 1
    assert result.result_summary["deleted_active_rows"] == 1
    assert pool._GetTableData(TABLE_JOBS, completed_job_id) == []
    archived_rows = pool._GetTableData(TABLE_JOB_ARCHIVE, completed_job_id)
    assert len(archived_rows) == 1
    assert archived_rows[0]["status"] == "completed"
    assert archived_rows[0]["archived_at"]


def test_daily_job_archive_moves_related_tables_and_purges_old_archive_rows(tmp_path):
    """Daily archive can compact append-only dispatcher tables and enforce retention."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool)
    now = datetime.now(timezone.utc)
    old_at = (now - timedelta(hours=48)).isoformat()
    current_at = now.isoformat()
    too_old_at = (now - timedelta(days=31)).isoformat()

    assert pool._Insert(
        TABLE_WORKER_HISTORY,
        {
            "id": "worker-history-old",
            "worker_id": "worker-a",
            "name": "Worker A",
            "status": "online",
            "event_type": "heartbeat",
            "captured_at": old_at,
        },
    )
    assert pool._Insert(
        TABLE_WORKER_HISTORY,
        {
            "id": "worker-history-current",
            "worker_id": "worker-a",
            "name": "Worker A",
            "status": "online",
            "event_type": "heartbeat",
            "captured_at": current_at,
        },
    )
    assert pool._Insert(
        TABLE_RESULT_ROWS,
        {
            "id": "result-old",
            "job_id": "job-old",
            "worker_id": "worker-a",
            "table_name": "rows",
            "payload": {"ok": True},
            "recorded_at": old_at,
        },
    )
    assert pool._Insert(
        TABLE_RAW_PAYLOADS,
        {
            "id": "raw-old",
            "job_id": "job-old",
            "worker_id": "worker-a",
            "target_table": "rows",
            "payload": {"raw": True},
            "collected_at": old_at,
        },
    )
    assert pool._Insert(
        TABLE_WORKER_HISTORY_ARCHIVE,
        {
            "id": "worker-history-too-old",
            "worker_id": "worker-z",
            "name": "Worker Z",
            "status": "online",
            "event_type": "heartbeat",
            "captured_at": too_old_at,
            "archived_at": too_old_at,
        },
    )

    cap = DailyJobArchiveJobCap(archive_related_tables=True)
    cap.bind_worker(type("WorkerStub", (), {"pool": pool})())

    result = cap.finish(
        JobDetail(
            id="dispatcher-job:daily-archive-related",
            required_capability="daily job archive",
            status="claimed",
            payload={
                "archive_completed_jobs": False,
                "archive_related_tables": True,
                "archive_older_than_hours": 24,
                "related_table_batch_size": 10,
                "cleanup_retention_days": 30,
                "cleanup_batch_size": 10,
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["purged_rows"] == 1
    related_summaries = {
        summary["source_table"]: summary
        for summary in result.result_summary["related_table_archives"]
    }
    assert related_summaries[TABLE_WORKER_HISTORY]["archived_rows"] == 1
    assert related_summaries[TABLE_RESULT_ROWS]["archived_rows"] == 1
    assert related_summaries[TABLE_RAW_PAYLOADS]["archived_rows"] == 1
    assert pool._GetTableData(TABLE_WORKER_HISTORY, "worker-history-old") == []
    assert len(pool._GetTableData(TABLE_WORKER_HISTORY, "worker-history-current")) == 1
    assert len(pool._GetTableData(TABLE_WORKER_HISTORY_ARCHIVE, "worker-history-old")) == 1
    assert pool._GetTableData(TABLE_WORKER_HISTORY_ARCHIVE, "worker-history-too-old") == []
    assert len(pool._GetTableData(TABLE_RESULT_ROWS_ARCHIVE, "result-old")) == 1
    assert len(pool._GetTableData(TABLE_RAW_PAYLOADS_ARCHIVE, "raw-old")) == 1


def test_get_job_uses_bounded_candidate_query_before_full_job_scan(tmp_path, monkeypatch):
    """
    Exercise the test_get_job_uses_bounded_candidate_query_before_full_job_scan
    regression scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool)
    agent = DispatcherAgent(pool=pool)

    agent.submit_job(required_capability="UPU WNS Item Image", priority=5, payload={"kind": "image"})
    target_job = agent.submit_job(
        required_capability="UPU WNS Listing",
        priority=10,
        payload={"kind": "listing"},
    )["job"]

    original_get_table_data = pool._GetTableData

    def guarded_get_table_data(table_name, id_or_where=None, table_schema=None):
        """Handle guarded get table data."""
        if table_name == TABLE_JOBS and id_or_where is None:
            raise AssertionError("dispatcher get_job should not fall back to a full job scan here")
        return original_get_table_data(table_name, id_or_where, table_schema)

    monkeypatch.setattr(pool, "_GetTableData", guarded_get_table_data)

    response = agent.get_job(
        worker_id="worker-a",
        name="Worker A",
        address="http://127.0.0.1:9999",
        capabilities=["UPU WNS Listing"],
    )

    claimed_job = response["job"]
    assert claimed_job is not None
    assert claimed_job["id"] == target_job["id"]
    assert claimed_job["status"] == "claimed"
    assert pool._GetTableData(TABLE_WORKER_HISTORY) == []


def test_post_job_result_archives_completed_job_when_enabled(tmp_path):
    """Completed jobs should move out of the active queue when archiving is enabled."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    agent = DispatcherAgent(pool=pool, config={"dispatcher": {"archive_completed_jobs": True}})

    job = agent.submit_job(required_capability="UPU WNS Listing", payload={"kind": "listing"})["job"]
    claimed = agent.get_job(worker_id="worker-a", capabilities=["UPU WNS Listing"])["job"]

    result = agent.post_job_result(
        JobResult(
            job_id=str(claimed["id"] or ""),
            worker_id="worker-a",
            status="completed",
            result_summary={"rows": 1},
        )
    )

    assert result["job"]["id"] == job["id"]
    assert result["job"]["status"] == "completed"
    assert pool._GetTableData(TABLE_JOBS, job["id"]) == []
    archived_rows = pool._GetTableData(TABLE_JOB_ARCHIVE, job["id"]) or []
    assert len(archived_rows) == 1
    assert archived_rows[0]["status"] == "completed"
    assert str(archived_rows[0].get("archived_at") or "").strip()


def test_dispatcher_startup_archives_legacy_completed_jobs_when_enabled(tmp_path):
    """Archiving-enabled dispatchers should compact legacy completed rows on startup."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    seed_agent = DispatcherAgent(pool=pool, config={"dispatcher": {"archive_completed_jobs": False}})

    completed_job_ids: list[str] = []
    for index in range(2):
        job = seed_agent.submit_job(
            required_capability="UPU WNS Listing",
            payload={"kind": f"listing-{index}"},
        )["job"]
        claimed = seed_agent.get_job(
            worker_id=f"worker-{index}",
            capabilities=["UPU WNS Listing"],
        )["job"]
        seed_agent.post_job_result(
            JobResult(
                job_id=str(claimed["id"] or ""),
                worker_id=f"worker-{index}",
                status="completed",
                result_summary={"rows": index + 1},
            )
        )
        completed_job_ids.append(str(job["id"] or ""))

    queued_job = seed_agent.submit_job(
        required_capability="UPU WNS Item Image",
        payload={"kind": "image"},
    )["job"]

    assert pool._GetTableData(TABLE_JOB_ARCHIVE) == []
    for job_id in completed_job_ids:
        active_rows = pool._GetTableData(TABLE_JOBS, job_id) or []
        assert len(active_rows) == 1
        assert active_rows[0]["status"] == "completed"

    DispatcherAgent(
        pool=pool,
        config={
            "dispatcher": {
                "archive_completed_jobs": True,
                "archive_completed_batch_size": 1,
            }
        },
    )

    for job_id in completed_job_ids:
        assert pool._GetTableData(TABLE_JOBS, job_id) == []
        archived_rows = pool._GetTableData(TABLE_JOB_ARCHIVE, job_id) or []
        assert len(archived_rows) == 1
        assert archived_rows[0]["status"] == "completed"
        assert str(archived_rows[0].get("archived_at") or "").strip()

    queued_rows = pool._GetTableData(TABLE_JOBS, queued_job["id"]) or []
    assert len(queued_rows) == 1
    assert queued_rows[0]["status"] == "queued"


def test_worker_run_forever_polls_immediately_after_completed_job(monkeypatch):
    """Workers should skip the idle backoff after finishing a job."""
    worker = DispatcherWorkerAgent(
        dispatcher_address="http://127.0.0.1:8060",
        poll_interval_sec=10,
    )
    run_results = [
        {"status": "completed", "job": JobDetail(id="job-1", required_capability="UPU WNS Listing", status="completed")},
        {"status": "idle", "job": None},
    ]
    sleep_calls: list[float] = []

    monkeypatch.setattr(worker, "run_once", lambda handler=None: run_results.pop(0))
    monkeypatch.setattr("prompits.dispatcher.agents.time.sleep", lambda seconds: sleep_calls.append(float(seconds)))

    completed_iterations = worker.run_forever(iterations=2)

    assert completed_iterations == 2
    assert sleep_calls == [10.0]


def test_worker_backoff_only_when_poll_result_is_idle_like():
    """Workers should only wait again when no job is available."""
    assert DispatcherWorkerAgent._should_wait_after_poll_result({"status": "idle"}) is True
    assert DispatcherWorkerAgent._should_wait_after_poll_result({"status": "pending"}) is True
    assert DispatcherWorkerAgent._should_wait_after_poll_result({"status": "waiting_for_hire"}) is True
    assert DispatcherWorkerAgent._should_wait_after_poll_result({"status": "completed"}) is False
    assert DispatcherWorkerAgent._should_wait_after_poll_result({"status": "failed"}) is False
    assert DispatcherWorkerAgent._should_wait_after_poll_result({"status": "retry"}) is False


def test_request_job_skips_dispatch_when_no_claimable_capabilities(monkeypatch):
    """Workers should not call dispatcher-get-job when every dynamic capability is hidden."""
    worker = DispatcherWorkerAgent(
        dispatcher_address="http://127.0.0.1:8060",
        poll_interval_sec=10,
    )
    practice_calls: list[tuple[str, dict[str, object], str]] = []

    monkeypatch.setattr(worker, "advertised_capabilities", lambda: [])

    def fake_use_practice(practice_id, payload, pit_address=""):
        practice_calls.append((practice_id, dict(payload or {}), str(pit_address or "")))
        return {"status": "unexpected"}

    worker.UsePractice = fake_use_practice

    response = worker.request_job()

    assert response["status"] == "idle"
    assert response["job"] is None
    assert response["backoff_sec"] == 30.0
    assert practice_calls == []


def test_request_job_waits_when_dispatcher_assigns_no_job(monkeypatch):
    """A successful no-job response should use the idle backoff instead of spinning."""
    worker = DispatcherWorkerAgent(
        dispatcher_address="http://127.0.0.1:8060",
        poll_interval_sec=0,
    )
    practice_calls: list[tuple[str, dict[str, object], str]] = []

    monkeypatch.setattr(worker, "advertised_capabilities", lambda: ["UPU WNS Listing"])

    def fake_use_practice(practice_id, payload, pit_address=""):
        practice_calls.append((practice_id, dict(payload or {}), str(pit_address or "")))
        return {"status": "success", "job": None}

    worker.UsePractice = fake_use_practice

    response = worker.request_job()

    assert response["status"] == "idle"
    assert response["job"] is None
    assert response["backoff_sec"] == 30.0
    assert DispatcherWorkerAgent._should_wait_after_poll_result(response) is True
    assert worker._poll_wait_interval_sec(response, default_sec=0.1) == 30.0
    assert [call[0] for call in practice_calls] == ["dispatcher-get-job"]


def test_worker_run_forever_uses_dynamic_idle_backoff(monkeypatch):
    """Workers should honor the returned backoff when nothing is currently claimable."""
    worker = DispatcherWorkerAgent(
        dispatcher_address="http://127.0.0.1:8060",
        poll_interval_sec=10,
    )
    run_results = [
        {"status": "idle", "job": None, "backoff_sec": 30},
        {"status": "idle", "job": None},
    ]
    sleep_calls: list[float] = []

    monkeypatch.setattr(worker, "run_once", lambda handler=None: run_results.pop(0))
    monkeypatch.setattr("prompits.dispatcher.agents.time.sleep", lambda seconds: sleep_calls.append(float(seconds)))

    completed_iterations = worker.run_forever(iterations=2)

    assert completed_iterations == 2
    assert sleep_calls == [30.0, 10.0]
