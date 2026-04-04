"""
Regression tests for Postgres Pool.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_postgres_pool_create_table_insert_and_get_table_data`,
`test_postgres_pool_passes_sslmode_with_pg_env_only`,
`test_postgres_pool_preserves_explicit_sslmode_in_dsn`, and
`test_postgres_pool_retries_without_ssl_when_server_rejects_ssl`, helping guard against
regressions as the packages evolve.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ads.schema import jobs_schema_dict
from prompits.core.schema import TableSchema
from prompits.pools import postgres as postgres_module
from prompits.pools.postgres import PostgresPool


class FakeCursor:
    """Represent a fake cursor."""
    def __init__(self, calls):
        """Initialize the fake cursor."""
        self.calls = calls
        self.description = []
        self.rows = []

    def execute(self, query, params=None):
        """Handle execute for the fake cursor."""
        normalized_query = str(query).strip()
        self.calls.append((normalized_query, params))
        if normalized_query == "SELECT 1":
            self.description = [("?column?",)]
            self.rows = [(1,)]
        elif normalized_query.startswith("SELECT to_regclass"):
            self.description = [("to_regclass",)]
            self.rows = [("public.ads_jobs",)]
        elif "FROM information_schema.table_constraints" in normalized_query:
            self.description = [("constraint_name",), ("constraint_type",), ("column_name",), ("ordinal_position",)]
            self.rows = [("ads_jobs_pkey", "PRIMARY KEY", "id", 1)]
        elif normalized_query.startswith('SELECT * FROM "public"."ads_jobs" WHERE "id" = %s'):
            self.description = [("id",), ("status",), ("metadata",)]
            self.rows = [("job-1", "queued", '{"retryable": true}')]
        else:
            self.description = []
            self.rows = []

    def executemany(self, query, params_seq):
        """Handle executemany for the fake cursor."""
        normalized_query = str(query).strip()
        self.calls.append((normalized_query, list(params_seq)))
        self.description = []
        self.rows = []

    def fetchall(self):
        """Handle fetchall for the fake cursor."""
        return list(self.rows)

    def fetchone(self):
        """Handle fetchone for the fake cursor."""
        return self.rows[0] if self.rows else None

    def __enter__(self):
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type, exc, tb):
        """Exit the context manager."""
        return False


class FakeConnection:
    """Represent a fake connection."""
    def __init__(self):
        """Initialize the fake connection."""
        self.calls = []
        self.closed = False

    def cursor(self):
        """Return the cursor."""
        return FakeCursor(self.calls)

    def close(self):
        """Handle close for the fake connection."""
        self.closed = True


def test_postgres_pool_create_table_insert_and_get_table_data(monkeypatch):
    """
    Exercise the test_postgres_pool_create_table_insert_and_get_table_data
    regression scenario.
    """
    fake_conn = FakeConnection()
    connect_calls = []

    def fake_connect(*args, **kwargs):
        """Handle fake connect."""
        connect_calls.append((args, kwargs))
        return fake_conn

    monkeypatch.setattr(postgres_module.psycopg, "connect", fake_connect)

    pool = PostgresPool("demo", "demo postgres pool", dsn="postgresql://demo", sslmode="disable")
    schema = TableSchema(jobs_schema_dict())

    try:
        assert pool.is_connected is True
        assert pool.last_error == ""
        assert pool._TableExists("ads_jobs") is True
        assert pool._CreateTable("ads_jobs", schema) is True
        assert pool._Insert("ads_jobs", {"id": "job-1", "status": "queued"}) is True

        rows = pool._GetTableData("ads_jobs", {"id": "job-1"}, table_schema=schema)
        assert rows == [{"id": "job-1", "status": "queued", "metadata": {"retryable": True}}]

        queries = [query for query, _params in fake_conn.calls]
        assert any('CREATE TABLE IF NOT EXISTS "public"."ads_jobs"' in query for query in queries)
        assert any(
            'ON CONFLICT ("id") DO UPDATE SET "status" = EXCLUDED."status"' in query
            for query in queries
        )
    finally:
        pool.disconnect()

    assert fake_conn.closed is True
    assert connect_calls[0][0][0] == "postgresql://demo"
    assert connect_calls[0][1]["sslmode"] == "disable"


def test_postgres_pool_tracks_last_error_when_connect_fails(monkeypatch):
    """
    Exercise the test_postgres_pool_tracks_last_error_when_connect_fails regression
    scenario.
    """
    connect_calls = []

    def fake_connect(*args, **kwargs):
        """Handle fake connect."""
        connect_calls.append((args, kwargs))
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(postgres_module.psycopg, "connect", fake_connect)

    pool = PostgresPool("demo", "demo postgres pool", dsn="postgresql://demo", sslmode="disable")

    assert pool.is_connected is False
    assert "database unavailable" in pool.last_error
    assert connect_calls[0][0][0] == "postgresql://demo"


def test_postgres_pool_preserves_explicit_sslmode_in_dsn(monkeypatch):
    """
    Exercise the test_postgres_pool_preserves_explicit_sslmode_in_dsn regression
    scenario.
    """
    connect_calls = []

    def fake_connect(*args, **kwargs):
        """Handle fake connect."""
        connect_calls.append((args, kwargs))
        return FakeConnection()

    monkeypatch.setattr(postgres_module.psycopg, "connect", fake_connect)

    pool = PostgresPool(
        "demo",
        "demo postgres pool",
        dsn="postgresql://demo?sslmode=require",
        sslmode="disable",
    )

    try:
        assert pool.is_connected is True
    finally:
        pool.disconnect()

    assert connect_calls[0][0][0] == "postgresql://demo?sslmode=require"
    assert "sslmode" not in connect_calls[0][1]


def test_postgres_pool_passes_sslmode_with_pg_env_only(monkeypatch):
    """
    Exercise the test_postgres_pool_passes_sslmode_with_pg_env_only regression
    scenario.
    """
    connect_calls = []

    def fake_connect(*args, **kwargs):
        """Handle fake connect."""
        connect_calls.append((args, kwargs))
        return FakeConnection()

    monkeypatch.setattr(postgres_module.psycopg, "connect", fake_connect)
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    monkeypatch.setenv("PGHOST", "127.0.0.1")
    monkeypatch.setenv("PGDATABASE", "ads")
    monkeypatch.setenv("PGUSER", "postgres")

    pool = PostgresPool("demo", "demo postgres pool", sslmode="disable")

    try:
        assert pool.is_connected is True
    finally:
        pool.disconnect()

    assert connect_calls[0][0][0] == ""
    assert connect_calls[0][1]["sslmode"] == "disable"


def test_postgres_pool_retries_without_ssl_when_server_rejects_ssl(monkeypatch):
    """
    Exercise the test_postgres_pool_retries_without_ssl_when_server_rejects_ssl
    regression scenario.
    """
    connect_calls = []
    fake_conn = FakeConnection()

    def fake_connect(*args, **kwargs):
        """Handle fake connect."""
        connect_calls.append((args, kwargs))
        if len(connect_calls) == 1:
            raise RuntimeError(
                'connection failed: connection to server at "127.0.0.1", port 5432 failed: '
                "server does not support SSL, but SSL was required"
            )
        return fake_conn

    monkeypatch.setattr(postgres_module.psycopg, "connect", fake_connect)

    pool = PostgresPool("demo", "demo postgres pool", dsn="postgresql://demo")

    try:
        assert pool.is_connected is True
    finally:
        pool.disconnect()

    assert len(connect_calls) == 2
    assert "sslmode" not in connect_calls[0][1]
    assert connect_calls[1][1]["sslmode"] == "disable"
