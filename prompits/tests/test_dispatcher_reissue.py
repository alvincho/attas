"""
Regression tests for Dispatcher Reissue.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_force_terminated_job_is_not_reissued` and
`test_terminal_failed_job_is_reissued_with_low_priority`, helping guard against
regressions as the packages evolve.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.dispatcher.agents import DispatcherAgent
from prompits.dispatcher.models import JobDetail
from prompits.dispatcher.schema import TABLE_JOBS, TABLE_WORKERS, ensure_dispatcher_tables
from prompits.pools.sqlite import SQLitePool


def test_terminal_failed_job_is_reissued_with_low_priority(tmp_path):
    """
    Exercise the test_terminal_failed_job_is_reissued_with_low_priority regression
    scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool)
    agent = DispatcherAgent(pool=pool)

    submitted = agent.submit_job(
        required_capability="UPU WNS Catalog",
        payload={"message": "hello"},
        targets=["item-a"],
        priority=100,
        max_attempts=1,
        metadata={"project": "collectibles"},
    )["job"]

    claimed = agent.claim_job(worker_id="worker-a", capabilities=["upu wns catalog"])["job"]
    assert claimed["id"] == submitted["id"]
    assert claimed["attempts"] == 1

    report = agent.report_job_result(
        job_id=claimed["id"],
        worker_id="worker-a",
        status="failed",
        error="upstream failure",
    )

    failed_job = report["job"]
    reissued_job = report["reissued_job"]

    assert failed_job["status"] == "failed"
    assert reissued_job is not None
    assert reissued_job["id"] != failed_job["id"]
    assert reissued_job["status"] == "queued"
    assert reissued_job["priority"] > 100
    assert reissued_job["attempts"] == 0
    assert reissued_job["max_attempts"] == failed_job["max_attempts"]
    assert reissued_job["metadata"]["reissue"]["source_job_id"] == failed_job["id"]
    assert reissued_job["metadata"]["reissue"]["trigger"] == "failed_max_attempts"

    rows = pool._GetTableData(TABLE_JOBS) or []
    assert len(rows) == 2
    assert any(str(row.get("id") or "") == reissued_job["id"] for row in rows)


def test_force_terminated_job_is_not_reissued(tmp_path):
    """Exercise the test_force_terminated_job_is_not_reissued regression scenario."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool)
    agent = DispatcherAgent(pool=pool)

    submitted = agent.submit_job(
        required_capability="UPU WNS Catalog",
        priority=5,
        max_attempts=1,
    )["job"]

    claimed = agent.claim_job(worker_id="worker-a", capabilities=["upu wns catalog"])["job"]
    assert claimed["id"] == submitted["id"]

    agent.control_job(claimed["id"], "force_terminate", worker_id="boss", reason="manual stop")
    report = agent.report_job_result(
        job_id=claimed["id"],
        worker_id="worker-a",
        status="failed",
        error="manual stop",
    )

    assert report.get("reissued_job") is None


def test_failed_job_can_explicitly_suppress_reissue(tmp_path):
    """A failed job can opt out of dispatcher reissue with a result-summary flag."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool)
    agent = DispatcherAgent(pool=pool)

    submitted = agent.submit_job(
        required_capability="UPU WNS Catalog",
        priority=5,
        max_attempts=1,
    )["job"]

    claimed = agent.claim_job(worker_id="worker-a", capabilities=["upu wns catalog"])["job"]
    assert claimed["id"] == submitted["id"]

    report = agent.report_job_result(
        job_id=claimed["id"],
        worker_id="worker-a",
        status="failed",
        error="upstream throttled",
        result_summary={"suppress_failed_reissue": True},
    )

    assert report["job"]["status"] == "failed"
    assert report["job"]["result_summary"]["suppress_failed_reissue"] is True
    assert report.get("reissued_job") is None


def test_jobdetail_from_row_normalizes_nullable_text_fields():
    """Dispatcher rows with nullable text fields should still build a JobDetail."""
    job = JobDetail.from_row(
        {
            "id": "dispatcher-job:test-nullable-text",
            "required_capability": "UPU WNS Catalog",
            "status": "queued",
            "claimed_by": None,
            "error": None,
            "result_summary": None,
            "metadata": None,
        }
    )

    assert job.claimed_by == ""
    assert job.error == ""
    assert job.result_summary == {}
    assert job.metadata == {}


def test_stale_stopping_job_is_marked_stopped_not_unfinished(tmp_path):
    """Stopping jobs should not re-enter the ready queue during stale recovery."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool)
    agent = DispatcherAgent(pool=pool)

    submitted = agent.submit_job(
        required_capability="UPU WNS Catalog",
        priority=5,
        max_attempts=3,
    )["job"]

    claimed = agent.claim_job(worker_id="worker-a", capabilities=["upu wns catalog"], name="Worker A")["job"]
    assert claimed["id"] == submitted["id"]

    agent.control_job(claimed["id"], "stop", worker_id="boss", reason="manual stop")

    worker_rows = pool._GetTableData(TABLE_WORKERS) or []
    worker_row = next(row for row in worker_rows if str(row.get("worker_id") or "") == "worker-a")
    stale_at = (datetime.now(timezone.utc) - timedelta(seconds=600)).isoformat()
    stale_worker_row = dict(worker_row)
    stale_worker_row["last_seen_at"] = stale_at
    stale_worker_row["updated_at"] = stale_at
    assert pool._Insert(TABLE_WORKERS, stale_worker_row)

    recovered = agent._recover_stale_worker_jobs(now_text=datetime.now(timezone.utc).isoformat())
    assert recovered == 1

    latest_rows = pool._GetTableData(TABLE_JOBS, claimed["id"]) or []
    assert latest_rows
    latest = latest_rows[0]
    assert latest["status"] == "stopped"
    assert latest["claimed_by"] in ("", None)
    assert latest["completed_at"]
    assert latest["result_summary"]["stopped"] is True
    assert latest["result_summary"]["stopped_due_to_stale_worker"] is True
