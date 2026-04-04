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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.dispatcher.agents import DispatcherAgent
from prompits.dispatcher.schema import TABLE_JOBS, ensure_dispatcher_tables
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
