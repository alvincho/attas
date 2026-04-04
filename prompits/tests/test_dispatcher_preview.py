"""
Regression tests for Dispatcher Preview.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_preview_db_table_orders_jobs_by_latest_timestamp_first`, helping guard against
regressions as the packages evolve.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.dispatcher.agents import DispatcherAgent
from prompits.dispatcher.schema import TABLE_JOBS, ensure_dispatcher_tables
from prompits.pools.sqlite import SQLitePool


def test_preview_db_table_orders_jobs_by_latest_timestamp_first(tmp_path):
    """
    Exercise the test_preview_db_table_orders_jobs_by_latest_timestamp_first
    regression scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool)
    agent = DispatcherAgent(pool=pool)

    pool._Insert(
        TABLE_JOBS,
        {
            "id": "job-old",
            "required_capability": "upu wns listing",
            "status": "completed",
            "priority": 110,
            "attempts": 1,
            "max_attempts": 5,
            "created_at": "2026-04-01T00:00:00+00:00",
            "updated_at": "2026-04-01T00:00:01+00:00",
        },
    )
    pool._Insert(
        TABLE_JOBS,
        {
            "id": "job-newest",
            "required_capability": "upu wns page",
            "status": "queued",
            "priority": 105,
            "attempts": 0,
            "max_attempts": 5,
            "created_at": "2026-04-01T00:00:02+00:00",
            "updated_at": "2026-04-01T00:00:03+00:00",
        },
    )
    pool._Insert(
        TABLE_JOBS,
        {
            "id": "job-middle",
            "required_capability": "upu wns item image",
            "status": "claimed",
            "priority": 120,
            "attempts": 1,
            "max_attempts": 5,
            "created_at": "2026-04-01T00:00:01+00:00",
            "updated_at": "2026-04-01T00:00:02+00:00",
        },
    )

    preview = agent.preview_db_table(TABLE_JOBS, limit=3, offset=0)

    assert [row["id"] for row in preview["rows"]] == [
        "job-newest",
        "job-middle",
        "job-old",
    ]
