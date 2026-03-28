import os
import socket
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.core.init_schema import pulse_pulser_pairs_schema_dict
from prompits.pools.supabase import SupabasePool


class FakeUpsertExecutor:
    def __init__(self, rows=None):
        self.calls = []
        self.rows = list(rows or [])
        self._selected = False

    def upsert(self, payload):
        self.calls.append(payload)
        payload_has_is_complete = any(
            isinstance(row, dict) and "is_complete" in row
            for row in (payload if isinstance(payload, list) else [payload])
        )
        if payload_has_is_complete:
            raise Exception({
                "message": "Could not find the 'is_complete' column of 'pulse_pulser_pairs' in the schema cache",
                "code": "PGRST204",
            })
        return self

    def select(self, _fields):
        self._selected = True
        return self

    def limit(self, _size):
        return self

    def execute(self):
        if self._selected:
            self._selected = False
            return type("Response", (), {"data": self.rows})()
        return self


class FakeSupabaseClient:
    def __init__(self, executor):
        self.executor = executor

    def table(self, table_name):
        assert table_name == "pulse_pulser_pairs"
        return self.executor


class FakeRpcRequest:
    def __init__(self, client, function_name, params=None):
        self.client = client
        self.function_name = function_name
        self.params = params

    def execute(self):
        self.client.rpc_calls.append((self.function_name, self.params))
        if self.client.rpc_error is not None:
            raise self.client.rpc_error
        return type("Response", (), {"data": self.client.rpc_result})()


class FakeRpcSupabaseClient:
    def __init__(self, table_executor=None, rpc_error=None, rpc_result=1):
        self.table_executor = table_executor or FakeUpsertExecutor()
        self.rpc_error = rpc_error
        self.rpc_result = rpc_result
        self.rpc_calls = []
        self.table_calls = []

    def rpc(self, function_name, params=None):
        return FakeRpcRequest(self, function_name, params)

    def table(self, table_name):
        self.table_calls.append(table_name)
        return self.table_executor


class FailingTableExecutor:
    def __init__(self, error):
        self.error = error
        self.calls = 0

    def select(self, _fields):
        return self

    def limit(self, _size):
        return self

    def upsert(self, _payload):
        self.calls += 1
        raise self.error

    def execute(self):
        self.calls += 1
        raise self.error


class FailingSupabaseClient:
    def __init__(self, error):
        self.error = error
        self.table_calls = []
        self.executor = FailingTableExecutor(error)

    def table(self, table_name):
        self.table_calls.append(table_name)
        return self.executor


def make_pool_with_supabase_client(client):
    pool = SupabasePool.__new__(SupabasePool)
    pool.name = "plaza_pool"
    pool.description = "test"
    pool.url = "http://example.test"
    pool.key = "secret"
    pool.supabase = client
    pool.is_connected = True
    pool._unsupported_table_columns = {}
    pool._observed_table_columns = {}
    pool._create_table_notice_tables = set()
    pool._connectivity_retry_after = 0.0
    pool._last_connectivity_error = ""
    pool._last_connectivity_warning_at = 0.0

    class DummyLock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    pool.lock = DummyLock()
    pool._ensure_connection = lambda: True
    return pool


def make_test_pool(executor):
    return make_pool_with_supabase_client(FakeSupabaseClient(executor))


def test_supabase_pool_insert_many_uses_batch_rpc_for_supported_tables():
    client = FakeRpcSupabaseClient()
    pool = make_pool_with_supabase_client(client)
    payload = [
        {
            "id": "alice:echo-practice",
            "agent_name": "alice",
            "practice_id": "echo-practice",
            "practice_name": "Echo Practice",
            "practice_description": "Echoes content back",
            "practice_data": {"id": "echo-practice", "path": "/echo"},
            "is_deleted": False,
            "updated_at": "2026-03-27T12:00:00+00:00",
        },
        {
            "id": "alice:ping-practice",
            "agent_name": "alice",
            "practice_id": "ping-practice",
            "practice_name": "Ping Practice",
            "practice_description": "Returns pong",
            "practice_data": {"id": "ping-practice", "path": "/ping"},
            "is_deleted": False,
            "updated_at": "2026-03-27T12:00:01+00:00",
        },
    ]

    ok = pool._InsertMany("agent_practices", payload)

    assert ok is True
    assert client.rpc_calls == [("batch_upsert_agent_practices", {"entries": payload})]
    assert client.table_calls == []
    assert client.table_executor.calls == []


def test_supabase_pool_insert_many_uses_batch_rpc_for_plaza_directory():
    client = FakeRpcSupabaseClient()
    pool = make_pool_with_supabase_client(client)
    payload = [
        {
            "id": "cfg-worker",
            "agent_id": "cfg-worker",
            "name": "Worker Config",
            "type": "AgentConfig",
            "description": "Standalone worker template",
            "owner": "tests",
            "address": "",
            "card": {
                "name": "Worker Config",
                "description": "Standalone worker template",
                "owner": "tests",
                "role": "worker",
                "tags": ["worker", "demo"],
                "pit_type": "AgentConfig",
                "meta": {
                    "resource_type": "agent_config",
                    "agent_type": "prompits.agents.standby.StandbyAgent",
                    "config_id": "cfg-worker",
                },
            },
            "meta": {
                "resource_type": "agent_config",
                "agent_type": "prompits.agents.standby.StandbyAgent",
                "role": "worker",
                "tags": ["worker", "demo"],
                "config": {
                    "name": "worker-a",
                    "type": "prompits.agents.standby.StandbyAgent",
                    "pools": [
                        {
                            "type": "FileSystemPool",
                            "name": "worker_pool",
                            "description": "test pool",
                            "root_path": "tests/storage",
                        }
                    ],
                },
                "created_at": "2026-03-27T12:00:00+00:00",
                "updated_at": "2026-03-27T12:00:01+00:00",
            },
            "updated_at": "2026-03-27T12:00:01+00:00",
        }
    ]

    ok = pool._InsertMany("plaza_directory", payload)

    assert ok is True
    assert client.rpc_calls == [("batch_upsert_plaza_directory", {"entries": payload})]
    assert client.table_calls == []
    assert client.table_executor.calls == []


def test_supabase_pool_insert_many_falls_back_when_batch_rpc_errors():
    executor = FakeUpsertExecutor()
    client = FakeRpcSupabaseClient(table_executor=executor, rpc_error=RuntimeError("rpc missing"))
    pool = make_pool_with_supabase_client(client)
    payload = [
        {
            "id": "alice:echo-practice",
            "agent_name": "alice",
            "practice_id": "echo-practice",
            "practice_name": "Echo Practice",
            "practice_description": "Echoes content back",
            "practice_data": {"id": "echo-practice", "path": "/echo"},
            "is_deleted": False,
            "updated_at": "2026-03-27T12:00:00+00:00",
        }
    ]

    ok = pool._InsertMany("agent_practices", payload)

    assert ok is True
    assert client.rpc_calls == [("batch_upsert_agent_practices", {"entries": payload})]
    assert client.table_calls == ["agent_practices", "agent_practices"]
    assert executor.calls == [payload]


def test_supabase_pool_insert_many_retries_without_unknown_columns():
    executor = FakeUpsertExecutor()
    pool = make_test_pool(executor)

    ok = pool._InsertMany(
        "pulse_pulser_pairs",
        [
            {
                "id": "pair-1",
                "pulse_id": "urn:plaza:pulse:news.sentiment.aggregate",
                "pulse_name": "news_sentiment_aggregate",
                "pulse_definition": {
                    "resource_type": "pulse_definition",
                    "id": "urn:plaza:pulse:news.sentiment.aggregate",
                    "status": "unfinished",
                },
                "is_complete": False,
                "status": "unfinished",
            }
        ],
    )

    assert ok is True
    assert len(executor.calls) == 2
    assert executor.calls[1] == [
        {
            "id": "pair-1",
            "pulse_id": "urn:plaza:pulse:news.sentiment.aggregate",
            "pulse_name": "news_sentiment_aggregate",
            "pulse_definition": {
                "resource_type": "pulse_definition",
                "id": "urn:plaza:pulse:news.sentiment.aggregate",
                "status": "unfinished",
            },
            "status": "unfinished",
        }
    ]
    assert pool._unsupported_table_columns["pulse_pulser_pairs"] == {"is_complete"}


def test_supabase_pool_connectivity_failure_enables_backoff_and_dedupes_create_notice(capsys):
    error = socket.gaierror(8, "nodename nor servname provided, or not known")
    client = FailingSupabaseClient(error)
    pool = make_pool_with_supabase_client(client)
    pool._ensure_connection = SupabasePool._ensure_connection.__get__(pool, SupabasePool)

    exists = pool._TableExists("agent_practices")
    created_first = pool._CreateTable("agent_practices", None)
    created_second = pool._CreateTable("agent_practices", None)
    inserted = pool._Insert("agent_practices", {"id": "alice:echo-practice"})

    assert exists is True
    assert created_first is True
    assert created_second is True
    assert inserted is False
    assert pool._connectivity_backoff_active() is True
    assert client.table_calls == ["agent_practices"]

    output = capsys.readouterr().out
    assert "Supabase connectivity failed while checking table 'agent_practices'" in output
    assert output.count("Table 'agent_practices' creation should be done via Supabase Dashboard or SQL Editor.") == 1


def test_supabase_pool_reuses_cached_unsupported_columns():
    executor = FakeUpsertExecutor()
    pool = make_test_pool(executor)
    pool._unsupported_table_columns = {"pulse_pulser_pairs": {"is_complete"}}

    ok = pool._InsertMany(
        "pulse_pulser_pairs",
        [
            {
                "id": "pair-2",
                "pulse_id": "urn:plaza:pulse:macro.cpi.latest",
                "pulse_name": "macro_cpi_latest",
                "is_complete": True,
                "status": "complete",
            }
        ],
    )

    assert ok is True
    assert len(executor.calls) == 1
    assert executor.calls[0] == [
        {
            "id": "pair-2",
            "pulse_id": "urn:plaza:pulse:macro.cpi.latest",
            "pulse_name": "macro_cpi_latest",
            "status": "complete",
        }
    ]


def test_supabase_pool_infers_missing_columns_from_existing_rows():
    executor = FakeUpsertExecutor(
        rows=[
            {
                "id": "existing-pair",
                "pulse_id": "urn:plaza:pulse:macro.cpi.latest",
                "pulse_name": "macro_cpi_latest",
                "status": "complete",
            }
        ]
    )
    pool = make_test_pool(executor)

    ok = pool._InsertMany(
        "pulse_pulser_pairs",
        [
            {
                "id": "pair-3",
                "pulse_id": "urn:plaza:pulse:macro.ppi.latest",
                "pulse_name": "macro_ppi_latest",
                "pulse_directory_id": "dir-pulse-3",
                "pulser_directory_id": "dir-pulser-3",
                "status": "complete",
            }
        ],
    )

    assert ok is True
    assert len(executor.calls) == 1
    assert executor.calls[0] == [
        {
            "id": "pair-3",
            "pulse_id": "urn:plaza:pulse:macro.ppi.latest",
            "pulse_name": "macro_ppi_latest",
            "status": "complete",
        }
    ]
    assert pool._unsupported_table_columns["pulse_pulser_pairs"] == {
        "pulse_directory_id",
        "pulser_directory_id",
    }


def test_pulse_pulser_pairs_schema_dict_includes_runtime_columns():
    row_schema = pulse_pulser_pairs_schema_dict()["rowSchema"]

    assert row_schema["pulse_id"]["type"] == "string"
    assert row_schema["pulse_directory_id"]["type"] == "string"
    assert row_schema["pulse_definition"]["type"] == "json"
    assert row_schema["status"]["type"] == "string"
    assert row_schema["is_complete"]["type"] == "boolean"
    assert row_schema["completion_status"]["type"] == "string"
    assert row_schema["completion_errors"]["type"] == "json"
    assert row_schema["pulser_directory_id"]["type"] == "string"
