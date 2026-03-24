import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.pools.supabase import SupabasePool


class FakeUpsertExecutor:
    def __init__(self):
        self.calls = []

    def upsert(self, payload):
        self.calls.append(payload)
        if len(self.calls) == 1:
            raise Exception({
                "message": "Could not find the 'is_complete' column of 'pulse_pulser_pairs' in the schema cache",
                "code": "PGRST204",
            })
        return self

    def execute(self):
        return self


class FakeSupabaseClient:
    def __init__(self, executor):
        self.executor = executor

    def table(self, table_name):
        assert table_name == "pulse_pulser_pairs"
        return self.executor


def test_supabase_pool_insert_many_retries_without_unknown_columns():
    executor = FakeUpsertExecutor()
    pool = SupabasePool.__new__(SupabasePool)
    pool.name = "plaza_pool"
    pool.description = "test"
    pool.url = "http://example.test"
    pool.key = "secret"
    pool.supabase = FakeSupabaseClient(executor)
    pool.is_connected = True

    class DummyLock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    pool.lock = DummyLock()
    pool._ensure_connection = lambda: True

    ok = pool._InsertMany(
        "pulse_pulser_pairs",
        [
            {
                "id": "pair-1",
                "pulse_name": "news_sentiment_aggregate",
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
            "pulse_name": "news_sentiment_aggregate",
            "status": "unfinished",
        }
    ]
