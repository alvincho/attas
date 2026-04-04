"""
Regression tests for PostgreSQL MCP Server.

The top-level tests directory covers cross-package behavior and shared guardrails across
the repository.

The pytest cases in this file document expected behavior through checks such as
`test_execute_requires_ack_for_drop`, `test_execute_requires_where_for_delete`,
`test_resolve_conninfo_prefers_override`, and
`test_resolve_conninfo_raises_without_settings`, helping guard against regressions as
the packages evolve.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_servers import postgresql_server


def test_strip_sql_literals_and_comments_preserves_structure() -> None:
    """
    Exercise the test_strip_sql_literals_and_comments_preserves_structure regression
    scenario.
    """
    sql = """
    select 'drop table users;' as literal
    -- delete from ignored;
    /* update ignored set x = 1; */
    from demo
    """

    sanitized = postgresql_server._strip_sql_literals_and_comments(sql)

    assert "drop table users" not in sanitized.lower()
    assert "delete from ignored" not in sanitized.lower()
    assert "update ignored" not in sanitized.lower()
    assert "from demo" in sanitized.lower()


def test_ensure_single_statement_rejects_multiple_statements() -> None:
    """
    Exercise the test_ensure_single_statement_rejects_multiple_statements regression
    scenario.
    """
    with pytest.raises(ValueError, match="Only one SQL statement"):
        postgresql_server._ensure_single_statement("select 1; select 2;")


def test_query_detection_allows_read_only_sql() -> None:
    """Exercise the test_query_detection_allows_read_only_sql regression scenario."""
    sanitized = postgresql_server._ensure_single_statement(
        "with t as (select 1 as n) select n from t"
    )

    assert postgresql_server._first_keyword(sanitized) == "with"
    assert not postgresql_server._contains_write_keywords(sanitized)


def test_query_detection_rejects_write_cte() -> None:
    """Exercise the test_query_detection_rejects_write_cte regression scenario."""
    sanitized = postgresql_server._ensure_single_statement(
        "with changed as (update demo set active = true returning *) select * from changed"
    )

    assert postgresql_server._contains_write_keywords(sanitized)


def test_resolve_conninfo_prefers_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the test_resolve_conninfo_prefers_override regression scenario."""
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    assert postgresql_server._resolve_conninfo("postgresql://override") == "postgresql://override"


def test_resolve_conninfo_uses_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exercise the test_resolve_conninfo_uses_database_url regression scenario."""
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://from-env")

    assert postgresql_server._resolve_conninfo() == "postgresql://from-env"


def test_resolve_conninfo_uses_pg_env_without_dsn(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Exercise the test_resolve_conninfo_uses_pg_env_without_dsn regression scenario.
    """
    monkeypatch.delenv("POSTGRES_DSN", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("PGHOST", "localhost")
    monkeypatch.setenv("PGDATABASE", "finmas")
    monkeypatch.setenv("PGUSER", "postgres")

    assert postgresql_server._resolve_conninfo() == ""


def test_resolve_conninfo_raises_without_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Exercise the test_resolve_conninfo_raises_without_settings regression scenario.
    """
    for key in (
        "POSTGRES_DSN",
        "DATABASE_URL",
        "SUPABASE_DB_URL",
        "PGHOST",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValueError, match="No PostgreSQL connection settings"):
        postgresql_server._resolve_conninfo()


def test_adapt_params_wraps_json_objects() -> None:
    """Exercise the test_adapt_params_wraps_json_objects regression scenario."""
    adapted = postgresql_server._adapt_params({"payload": {"symbol": "AAPL"}})

    if postgresql_server.Json is None:
        assert adapted == {"payload": {"symbol": "AAPL"}}
    else:
        payload = adapted["payload"]
        assert payload.__class__.__name__ == "Json"
        assert payload.obj == {"symbol": "AAPL"}


def test_execute_requires_ack_for_drop() -> None:
    """Exercise the test_execute_requires_ack_for_drop regression scenario."""
    sanitized = postgresql_server._ensure_single_statement("drop table demo")
    assert postgresql_server._first_keyword(sanitized) == "drop"
    assert "drop" in postgresql_server.DESTRUCTIVE_KEYWORDS


def test_execute_requires_where_for_delete() -> None:
    """Exercise the test_execute_requires_where_for_delete regression scenario."""
    sanitized = postgresql_server._ensure_single_statement("delete from demo")
    assert postgresql_server._first_keyword(sanitized) == "delete"
    assert not postgresql_server._contains_where_clause(sanitized)
