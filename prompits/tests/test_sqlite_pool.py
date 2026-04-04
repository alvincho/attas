"""
Regression tests for SQLite Pool.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_sqlite_pool_create_table_honors_primary_key_for_replace_semantics`,
`test_sqlite_pool_creates_parent_directory_for_db_path`, and
`test_sqlite_pool_failed_connection_does_not_cascade_none_cursor_errors`, helping guard
against regressions as the packages evolve.
"""

from pathlib import Path

from ads.schema import jobs_schema_dict
from prompits.core.schema import TableSchema
from prompits.pools.sqlite import SQLitePool


def test_sqlite_pool_creates_parent_directory_for_db_path(tmp_path):
    """
    Exercise the test_sqlite_pool_creates_parent_directory_for_db_path regression
    scenario.
    """
    db_path = tmp_path / "nested" / "storage" / "pool.sqlite"
    pool = SQLitePool("demo", "demo sqlite pool", str(db_path))

    try:
        assert db_path.parent.exists()
        assert pool.is_connected is True
        assert pool._TableExists("missing_table") is False
    finally:
        pool.disconnect()


def test_sqlite_pool_failed_connection_does_not_cascade_none_cursor_errors(tmp_path):
    """
    Exercise the
    test_sqlite_pool_failed_connection_does_not_cascade_none_cursor_errors
    regression scenario.
    """
    blocked_parent = tmp_path / "blocked"
    blocked_parent.write_text("not a directory", encoding="utf-8")
    db_path = blocked_parent / "pool.sqlite"
    pool = SQLitePool("broken", "broken sqlite pool", str(db_path))

    schema = pool.memory_table_schema()

    assert pool.is_connected is False
    assert pool._TableExists("demo") is False
    assert pool._CreateTable("demo", schema) is False
    assert pool._Insert("demo", {"id": "r1", "content": "x"}) is False
    assert pool._InsertMany("demo", [{"id": "r1"}]) is False
    assert pool._Query("SELECT 1") == []
    assert pool._GetTableData("demo") == []


def test_sqlite_pool_create_table_honors_primary_key_for_replace_semantics(tmp_path):
    """
    Exercise the
    test_sqlite_pool_create_table_honors_primary_key_for_replace_semantics
    regression scenario.
    """
    db_path = tmp_path / "pool.sqlite"
    pool = SQLitePool("demo", "demo sqlite pool", str(db_path))

    try:
        schema = TableSchema(jobs_schema_dict())
        assert pool._CreateTable("ads_jobs", schema) is True

        assert pool._Insert("ads_jobs", {"id": "job-1", "status": "queued"}) is True
        assert pool._Insert("ads_jobs", {"id": "job-1", "status": "claimed"}) is True

        rows = pool._GetTableData("ads_jobs", {"id": "job-1"})
        assert len(rows) == 1
        assert rows[0]["status"] == "claimed"
    finally:
        pool.disconnect()
