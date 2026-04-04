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

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.dispatcher.agents import DispatcherAgent
from prompits.dispatcher.schema import TABLE_JOBS, TABLE_WORKER_HISTORY, ensure_dispatcher_tables
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
    history_rows = pool._GetTableData(TABLE_WORKER_HISTORY)
    assert len(history_rows) == 1
    assert history_rows[0]["event_type"] == "heartbeat"


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
