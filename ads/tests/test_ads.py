"""
Regression tests for ADS.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace. These tests protect the ADS data-service
behaviors, scheduling rules, and provider integrations.

The pytest cases in this file document expected behavior through checks such as
`test_ads_daily_price_results_create_missing_security_master_parent_rows`,
`test_build_job_cap_can_instantiate_job_cap_type`,
`test_build_job_cap_can_instantiate_rss_news_job_cap_type`, and
`test_build_job_cap_can_instantiate_twse_job_cap_type`, helping guard against
regressions as the packages evolve.
"""

import json
import os
import sys
import threading
import time
from datetime import date, datetime, timedelta, timezone
from json import JSONDecodeError
from pathlib import Path
from typing import Any
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from yfinance.exceptions import YFPricesMissingError

from ads.agents import ADSDispatcherAgent, ADSWorkerAgent
from ads.archive_jobs import DailyJobArchiveJobCap
from ads.examples.live_data_pipeline import LiveSECFinancialStatementsJobCap, LiveSECFundamentalsJobCap
from ads.iex import IEXEODJobCap
from ads.jobcap import JobCap, build_job_cap, build_job_cap_map, resolve_daily_price_start_date, subtract_years
from ads.models import JobDetail, JobResult
from ads.pulser import ADSPulser
from ads.rss_news import RSSNewsJobCap
from ads.runtime import build_daily_price_id, normalize_capabilities, read_ads_config, utcnow_iso
from ads.sec import USFilingBulkJobCap, USFilingMappingJobCap
from ads.schema import (
    SYMBOL_CHILD_TABLES,
    TABLE_DAILY_PRICE,
    TABLE_FINANCIAL_STATEMENTS,
    TABLE_FUNDAMENTALS,
    TABLE_JOB_ARCHIVE,
    TABLE_JOBS,
    TABLE_NEWS,
    TABLE_RAW_DATA,
    TABLE_SEC_COMPANYFACTS,
    TABLE_SEC_SUBMISSIONS,
    TABLE_SECURITY_MASTER,
    TABLE_WORKER_HISTORY,
    TABLE_WORKERS,
    ads_table_schema_map,
    ensure_ads_tables,
)
from ads.twse import TWSEMarketEODJobCap
from ads.us_listed import USListedSecJobCap
from ads.yfinance import YFinanceEODJobCap, YFinanceUSMarketEODJobCap
from prompits.pools.sqlite import SQLitePool
from prompits.tests.test_support import build_agent_from_config, start_agent_thread, stop_servers


def collect_daily_price_for_test(job: JobDetail) -> JobResult:
    """Collect the daily price for the test."""
    symbol = (job.payload or {}).get("symbol") if isinstance(job.payload, dict) else None
    symbol = symbol or (job.symbols[0] if job.symbols else "MSFT")
    return JobResult(
        job_id=job.id,
        status="completed",
        collected_rows=[
            {
                "symbol": symbol,
                "trade_date": "2026-03-28",
                "open": 400.0,
                "high": 404.0,
                "low": 398.0,
                "close": 402.0,
                "volume": 1200,
            }
        ],
        raw_payload={"provider": "mock"},
        result_summary={"rows": 1},
    )


def seed_security_master_symbol(pool: SQLitePool, symbol: str, provider: str = "ads", name: str | None = None) -> None:
    """Handle seed security master symbol."""
    assert pool._Insert(
        TABLE_SECURITY_MASTER,
        {
            "id": f"ads-security-master:{symbol.upper()}",
            "symbol": symbol.upper(),
            "name": name or symbol.upper(),
            "provider": provider,
        },
    )


class AutoPollingYFinanceJobCap(JobCap):
    """Job capability implementation for auto polling y finance workflows."""
    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the auto polling y finance job cap."""
        symbol = (job.payload or {}).get("symbol") if isinstance(job.payload, dict) else None
        symbol = symbol or (job.symbols[0] if job.symbols else "MSFT")
        return JobResult(
            job_id=job.id,
            status="completed",
            target_table=TABLE_DAILY_PRICE,
            collected_rows=[
                {
                    "symbol": symbol,
                    "trade_date": "2026-03-28",
                    "provider": "yfinance",
                    "open": 400.0,
                    "high": 404.0,
                    "low": 398.0,
                    "close": 402.0,
                    "adj_close": 401.5,
                    "volume": 1200,
                }
            ],
            raw_payload={"provider": "yfinance", "symbol": symbol},
            result_summary={"rows": 1},
        )


class RecordingJobCap(JobCap):
    """Job capability implementation for recording workflows."""
    def __init__(self, calls: list[str], name: str = "YFinance EOD"):
        """Initialize the recording job cap."""
        super().__init__(name=name)
        self.calls = calls

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the recording job cap."""
        self.calls.append(job.id)
        return JobResult(
            job_id=job.id,
            status="completed",
            result_summary={"executed": True},
        )


class StaticJobCap(JobCap):
    """Job capability implementation for static result workflows."""

    def __init__(self, name: str, result: JobResult):
        """Initialize the static job cap."""
        super().__init__(name=name)
        self.result = result
        self.calls = 0

    def finish(self, job: JobDetail) -> JobResult:
        """Return the configured static result."""
        self.calls += 1
        return self.result.model_copy(update={"job_id": job.id})


class FailingJobCap(JobCap):
    """Job capability implementation for failing workflows."""
    def __init__(self, message: str = "upstream unavailable", name: str = "YFinance EOD", error_type=RuntimeError):
        """Initialize the failing job cap."""
        super().__init__(name=name)
        self.message = message
        self.error_type = error_type

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the failing job cap."""
        raise self.error_type(self.message)


class StopCheckingJobCap(JobCap):
    """Job capability implementation for stop checking workflows."""
    def __init__(self, name: str = "news"):
        """Initialize the stop checking job cap."""
        super().__init__(name=name)

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the stop checking job cap."""
        self.worker.raise_if_stop_requested(job)
        return JobResult(
            job_id=job.id,
            status="completed",
            result_summary={"executed": True},
        )


class SuccessEnvelopeJobCap(JobCap):
    """Job capability implementation for success envelope workflows."""
    def __init__(self, name: str = "news"):
        """Initialize the success envelope job cap."""
        super().__init__(name=name)

    def finish(self, job: JobDetail) -> dict[str, Any]:
        """Handle finish for the success envelope job cap."""
        return {"status": "success", "message": "started"}


class NoneReturningJobCap(JobCap):
    """Job capability implementation for none returning workflows."""
    def __init__(self, name: str = "news"):
        """Initialize the none returning job cap."""
        super().__init__(name=name)

    def finish(self, job: JobDetail) -> None:
        """Handle finish for the none returning job cap."""
        return None


class UnavailableJobCap(JobCap):
    """Job capability implementation for unavailable workflows."""
    def __init__(self, name: str = "Unavailable Cap", reason: str = "missing dependency"):
        """Initialize the unavailable job cap."""
        super().__init__(name=name)
        self.reason = reason

    def check_environment(self) -> tuple[bool, str]:
        """Handle check environment for the unavailable job cap."""
        return False, self.reason

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the unavailable job cap."""
        raise RuntimeError("UnavailableJobCap should not execute.")


class FakeIEXResponse:
    """Response model for fake IEX payloads."""
    def __init__(self, payload, url: str, status_code: int = 200):
        """Initialize the fake IEX response."""
        self._payload = payload
        self.url = url
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        """Handle JSON for the fake IEX response."""
        return self._payload


class FakeTWSEResponse:
    """Response model for fake TWSE payloads."""
    def __init__(self, payload, url: str, status_code: int = 200):
        """Initialize the fake TWSE response."""
        self._payload = payload
        self.url = url
        self.status_code = status_code
        self.text = str(payload)

    def json(self):
        """Handle JSON for the fake TWSE response."""
        return self._payload


class FakeYFinanceHistory:
    """Represent a fake y finance history."""
    def __init__(self, rows):
        """Initialize the fake y finance history."""
        self._rows = list(rows)
        self.empty = not self._rows

    def iterrows(self):
        """Handle iterrows for the fake y finance history."""
        for index, row in self._rows:
            yield index, row


class FakeYFinanceTicker:
    """Represent a fake y finance ticker."""
    def __init__(self, symbol: str, payload_by_symbol, requested_history_calls):
        """Initialize the fake y finance ticker."""
        self.symbol = symbol
        self.payload_by_symbol = payload_by_symbol
        self.requested_history_calls = requested_history_calls

    def history(self, start=None, end=None, interval=None, auto_adjust=None, actions=None, raise_errors=None):
        """Return the history."""
        self.requested_history_calls.append(
            {
                "symbol": self.symbol,
                "start": start.isoformat() if hasattr(start, "isoformat") else str(start),
                "end": end.isoformat() if hasattr(end, "isoformat") else str(end),
                "interval": interval,
                "auto_adjust": auto_adjust,
                "actions": actions,
            }
        )
        rows = []
        for row in self.payload_by_symbol.get(self.symbol, []):
            trade_day = date.fromisoformat(row["Date"])
            if start is not None and trade_day < start:
                continue
            if end is not None and trade_day >= end:
                continue
            rows.append((trade_day, row))
        return FakeYFinanceHistory(rows)


class FakeTextResponse:
    """Response model for fake text payloads."""
    def __init__(self, text: str, url: str, status_code: int = 200):
        """Initialize the fake text response."""
        self.text = text
        self.url = url
        self.status_code = status_code


class RecordingSubmitWorker:
    """Represent a recording submit worker."""
    def __init__(self, pool: SQLitePool):
        """Initialize the recording submit worker."""
        self.pool = pool
        self.dispatcher_address = ""
        self.submissions: list[dict[str, object]] = []

    def submit_job(self, **kwargs):
        """Submit the job."""
        self.submissions.append(dict(kwargs))
        symbol = ""
        symbols = kwargs.get("symbols")
        if isinstance(symbols, list) and symbols:
            symbol = str(symbols[0] or "")
        return {
            "status": "success",
            "job": {
                "id": f"ads-job:queued:{symbol}",
                "required_capability": kwargs.get("required_capability"),
                "symbols": kwargs.get("symbols"),
                "payload": kwargs.get("payload"),
            },
        }

    def raise_if_stop_requested(self, job: JobDetail) -> None:
        """Handle raise if stop requested for the recording submit worker."""
        return None


def build_twse_daily_quotes_payload(date_key: str, rows):
    """Build the TWSE daily quotes payload."""
    return {
        "stat": "OK",
        "date": date_key,
        "tables": [
            {
                "title": f"{date_key[:4]}/{date_key[4:6]}/{date_key[6:]} Daily Quotes(All(no Warrant & CBBC & OCBBC))",
                "fields": [
                    "Security Code",
                    "Trade Volume",
                    "Transaction",
                    "Trade Value",
                    "Opening Price",
                    "Highest Price",
                    "Lowest Price",
                    "Closing Price",
                    "Dir(+/-)",
                    "Change",
                    "Last Best Bid Price",
                    "Last Best Bid Volume",
                    "Last Best Ask Price",
                    "Last Best Ask Volume",
                    "Price-Earning ratio",
                ],
                "data": rows,
                "notes": [
                    "Symbols for Direction:+/-/ X represent Up/Down/Not compared.",
                ],
            }
        ],
    }


def build_symbol_directory_text(headers, rows, file_creation_time: str) -> str:
    """Build the symbol directory text."""
    lines = ["|".join(headers)]
    lines.extend("|".join(str(value) for value in row) for row in rows)
    lines.append(f"File Creation Time: {file_creation_time}" + ("|" * (len(headers) - 1)))
    return "\n".join(lines)


def test_ads_agents_default_to_ads_party(tmp_path):
    """Exercise the test_ads_agents_default_to_ads_party regression scenario."""
    dispatcher_pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", str(tmp_path / "dispatch.sqlite"))
    worker_pool = SQLitePool("ads_worker", "ADS worker test pool", str(tmp_path / "worker.sqlite"))
    pulser_pool = SQLitePool("ads_pulser", "ADS pulser test pool", str(tmp_path / "pulser.sqlite"))

    dispatcher = ADSDispatcherAgent(pool=dispatcher_pool)
    worker = ADSWorkerAgent(pool=worker_pool, auto_register=False)
    pulser = ADSPulser(pool=pulser_pool, auto_register=False)

    assert dispatcher.agent_card["party"] == "ADS"
    assert dispatcher.agent_card["meta"]["party"] == "ADS"
    assert worker.agent_card["party"] == "ADS"
    assert worker.agent_card["meta"]["party"] == "ADS"
    assert pulser.agent_card["party"] == "ADS"
    assert pulser.agent_card["meta"]["party"] == "ADS"


def test_ads_dispatcher_claim_and_report_flow(tmp_path):
    """Exercise the test_ads_dispatcher_claim_and_report_flow regression scenario."""
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", str(tmp_path / "ads.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool)

    submit_result = dispatcher.submit_job(
        required_capability="news",
        payload={"symbol": "AAPL"},
        symbols=["AAPL"],
        source_url="https://example.com/news",
    )
    job = submit_result["job"]

    claim_result = dispatcher.claim_job(worker_id="worker-a", capabilities=["news"])
    claimed_job = JobDetail.model_validate(claim_result["job"])

    assert claimed_job.id == job["id"]
    assert claimed_job.status == "claimed"
    assert claimed_job.claimed_by == "worker-a"

    report_result = dispatcher.post_job_result(
        JobResult(
            job_id=job["id"],
            worker_id="worker-a",
            status="completed",
            collected_rows=[
                {
                    "symbol": "AAPL",
                    "headline": "Apple launches something new",
                    "summary": "Short summary",
                    "url": "https://example.com/news/1",
                    "source": "ExampleWire",
                    "published_at": "2026-03-28T09:00:00+00:00",
                }
            ],
            raw_payload={"headline": "Apple launches something new"},
            result_summary={"rows": 1},
        )
    )

    assert report_result["stored_rows"] == 1
    saved_news_rows = pool._GetTableData(TABLE_NEWS, {"symbol": "AAPL"})
    assert len(saved_news_rows) == 1
    assert saved_news_rows[0]["headline"] == "Apple launches something new"
    security_rows = pool._GetTableData(TABLE_SECURITY_MASTER, {"symbol": "AAPL"})
    assert len(security_rows) == 1
    assert security_rows[0]["metadata"]["auto_created"] is True

    raw_rows = pool._GetTableData(TABLE_RAW_DATA, {"job_id": job["id"]})
    assert len(raw_rows) == 1
    assert raw_rows[0]["payload"]["headline"] == "Apple launches something new"


def test_ads_dispatcher_requires_matching_job_capability_metadata_when_claiming(tmp_path):
    """
    Exercise the
    test_ads_dispatcher_requires_matching_job_capability_metadata_when_claiming
    regression scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", str(tmp_path / "ads.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool)

    submit_result = dispatcher.submit_job(
        required_capability="YFinance EOD",
        payload={"symbol": "MSFT"},
        symbols=["MSFT"],
    )

    no_cap_claim = dispatcher.claim_job(
        worker_id="worker-a",
        capabilities=["yfinance eod"],
        metadata={
            "job_capabilities": [
                {"name": "RSS News"},
            ]
        },
    )
    assert no_cap_claim["status"] == "success"
    assert no_cap_claim["job"] is None

    worker_rows = pool._GetTableData(TABLE_WORKERS, "worker-a")
    assert len(worker_rows) == 1
    assert worker_rows[0]["capabilities"] == []

    matching_cap_claim = dispatcher.claim_job(
        worker_id="worker-a",
        capabilities=["yfinance eod"],
        metadata={
            "job_capabilities": [
                {"name": "YFinance EOD"},
            ]
        },
    )
    assert matching_cap_claim["status"] == "success"
    assert matching_cap_claim["job"]["id"] == submit_result["job"]["id"]
    assert matching_cap_claim["job"]["required_capability"] == "yfinance eod"


def test_ads_dispatcher_preserves_error_history_across_retry_then_completion(tmp_path):
    """
    Exercise the
    test_ads_dispatcher_preserves_error_history_across_retry_then_completion
    regression scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", str(tmp_path / "ads.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool)

    submit_result = dispatcher.submit_job(
        required_capability="news",
        payload={"symbol": "AAPL"},
        symbols=["AAPL"],
        max_attempts=3,
    )
    job_id = submit_result["job"]["id"]

    claim_result = dispatcher.claim_job(worker_id="worker-a", capabilities=["news"])
    assert claim_result["job"]["id"] == job_id

    retry_result = dispatcher.post_job_result(
        JobResult(
            job_id=job_id,
            worker_id="worker-a",
            status="retry",
            error="Remote end closed connection without response",
            result_summary={
                "exception": "ConnectionError",
                "retryable": True,
            },
        )
    )
    assert retry_result["status"] == "success"

    reclaim_result = dispatcher.claim_job(worker_id="worker-a", capabilities=["news"])
    assert reclaim_result["job"]["id"] == job_id
    assert reclaim_result["job"]["attempts"] == 2

    complete_result = dispatcher.post_job_result(
        JobResult(
            job_id=job_id,
            worker_id="worker-a",
            status="completed",
            result_summary={"rows": 0},
        )
    )
    assert complete_result["status"] == "success"

    latest_rows = dispatcher._latest_job_rows(pool._GetTableData(TABLE_JOB_ARCHIVE, job_id) or [])
    assert len(latest_rows) == 1
    latest_job = latest_rows[0]
    assert latest_job["status"] == "completed"
    assert latest_job["error"] == ""
    assert latest_job["result_summary"]["rows"] == 0
    assert latest_job["result_summary"]["error_count"] == 1
    assert latest_job["result_summary"]["last_error"] == "Remote end closed connection without response"
    assert len(latest_job["result_summary"]["error_history"]) == 1
    assert latest_job["result_summary"]["error_history"][0]["status"] == "retry"
    assert latest_job["result_summary"]["error_history"][0]["exception"] == "ConnectionError"
    assert latest_job["result_summary"]["error_history"][0]["attempt"] == 1
    assert latest_job["result_summary"]["error_history"][0]["worker_id"] == "worker-a"
    assert pool._GetTableData(TABLE_JOBS, job_id) == []


def test_ads_dispatcher_get_job_ignores_stale_queued_snapshot_for_same_job_id(tmp_path):
    """
    Exercise the
    test_ads_dispatcher_get_job_ignores_stale_queued_snapshot_for_same_job_id
    regression scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", str(tmp_path / "ads.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool)

    with pool.lock:
        pool.conn.execute("DROP TABLE IF EXISTS ads_jobs")
        pool.conn.execute(
            """
            CREATE TABLE ads_jobs (
                id TEXT,
                job_type TEXT,
                status TEXT,
                required_capability TEXT,
                capability_tags TEXT,
                symbols TEXT,
                payload TEXT,
                target_table TEXT,
                source_url TEXT,
                parse_rules TEXT,
                priority INTEGER,
                premium INTEGER,
                metadata TEXT,
                scheduled_for TEXT,
                claimed_by TEXT,
                claimed_at TEXT,
                completed_at TEXT,
                result_summary TEXT,
                error TEXT,
                attempts INTEGER,
                max_attempts INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        pool.conn.commit()

    job_id = "ads-job:stale-1"
    created_at = "2026-03-28T10:00:00+00:00"
    dispatcher.pool._Insert(
        "ads_jobs",
        {
            "id": job_id,
            "job_type": "collect",
            "status": "queued",
            "required_capability": "yfinance eod",
            "capability_tags": [],
            "symbols": ["MSFT"],
            "payload": {"symbol": "MSFT"},
            "target_table": "",
            "source_url": "",
            "parse_rules": {},
            "priority": 100,
            "premium": False,
            "metadata": {},
            "scheduled_for": created_at,
            "claimed_by": "",
            "claimed_at": "",
            "completed_at": "",
            "result_summary": {},
            "error": "",
            "attempts": 0,
            "max_attempts": 3,
            "created_at": created_at,
            "updated_at": created_at,
        },
    )
    dispatcher.pool._Insert(
        "ads_jobs",
        {
            "id": job_id,
            "job_type": "collect",
            "status": "claimed",
            "required_capability": "yfinance eod",
            "capability_tags": [],
            "symbols": ["MSFT"],
            "payload": {"symbol": "MSFT"},
            "target_table": "",
            "source_url": "",
            "parse_rules": {},
            "priority": 100,
            "premium": False,
            "metadata": {},
            "scheduled_for": created_at,
            "claimed_by": "worker-a",
            "claimed_at": "2026-03-28T10:01:00+00:00",
            "completed_at": "",
            "result_summary": {},
            "error": "",
            "attempts": 1,
            "max_attempts": 3,
            "created_at": created_at,
            "updated_at": "2026-03-28T10:01:00+00:00",
        },
    )

    claim_result = dispatcher.claim_job(worker_id="worker-b", capabilities=["yfinance eod"])

    assert claim_result["status"] == "success"
    assert claim_result["job"] is None


def test_ads_dispatcher_submit_job_infers_symbols_from_payload():
    """
    Exercise the test_ads_dispatcher_submit_job_infers_symbols_from_payload
    regression scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", ":memory:")
    dispatcher = ADSDispatcherAgent(pool=pool)

    result = dispatcher.submit_job(
        required_capability="YFinance EOD",
        payload={"symbol": "msft"},
    )

    assert result["job"]["symbols"] == ["MSFT"]


def test_ads_dispatcher_submit_job_rejects_symbol_required_cap_without_symbols():
    """
    Exercise the
    test_ads_dispatcher_submit_job_rejects_symbol_required_cap_without_symbols
    regression scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", ":memory:")
    dispatcher = ADSDispatcherAgent(pool=pool)

    try:
        dispatcher.submit_job(required_capability="YFinance EOD", payload={})
        assert False, "Expected submit_job to reject a symbol-less YFinance EOD job."
    except ValueError as exc:
        assert "requires at least one symbol" in str(exc)


def test_ads_dispatcher_submit_job_reports_postgres_connection_details(monkeypatch):
    """
    Exercise the test_ads_dispatcher_submit_job_reports_postgres_connection_details
    regression scenario.
    """
    for env_name in (
        "POSTGRES_DSN",
        "DATABASE_URL",
        "SUPABASE_DB_URL",
        "PGHOST",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
    ):
        monkeypatch.delenv(env_name, raising=False)

    dispatcher = ADSDispatcherAgent(pool=SQLitePool("ads_dispatch", "ADS dispatch test pool", ":memory:"))

    class PostgresPool:
        """Represent a Postgres pool."""
        def __init__(self):
            """Initialize the Postgres pool."""
            self.name = "ads_dispatch_pool"
            self.is_connected = False
            self.last_error = 'Error connecting to PostgreSQL: connection to server at "127.0.0.1", port 5432 failed'
            self.dsn = ""

        def _Insert(self, table_name, data):
            """Internal helper for insert."""
            return False

    dispatcher.pool = PostgresPool()

    try:
        dispatcher.submit_job(required_capability="US Listed Sec to security master")
        assert False, "Expected submit_job to surface the PostgreSQL connection failure."
    except RuntimeError as exc:
        message = str(exc)
        assert "Failed to persist ADS job." in message
        assert "PostgreSQL pool 'ads_dispatch_pool' is not connected." in message
        assert "POSTGRES_DSN" in message
        assert "Last error:" in message


def test_ads_dispatcher_submit_job_persists_null_for_unset_timestamps():
    """
    Exercise the test_ads_dispatcher_submit_job_persists_null_for_unset_timestamps
    regression scenario.
    """
    dispatcher = ADSDispatcherAgent(pool=SQLitePool("ads_dispatch", "ADS dispatch test pool", ":memory:"))

    class RecordingPool:
        """Represent a recording pool."""
        def __init__(self):
            """Initialize the recording pool."""
            self.rows = []

        def _Insert(self, table_name, data):
            """Internal helper for insert."""
            self.rows.append((table_name, dict(data)))
            return True

    dispatcher.pool = RecordingPool()

    result = dispatcher.submit_job(required_capability="US Listed Sec to security master")

    assert result["status"] == "success"
    inserted = dispatcher.pool.rows[0][1]
    assert inserted["scheduled_for"]
    assert inserted["claimed_at"] is None
    assert inserted["completed_at"] is None


def test_job_detail_from_row_normalizes_postgres_datetime_values():
    """
    Exercise the test_job_detail_from_row_normalizes_postgres_datetime_values
    regression scenario.
    """
    row = {
        "id": "ads-job:1",
        "scheduled_for": datetime(2026, 3, 28, 14, 0, tzinfo=timezone.utc),
        "claimed_at": None,
        "completed_at": None,
        "created_at": datetime(2026, 3, 28, 13, 55, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 28, 13, 56, tzinfo=timezone.utc),
    }

    job = JobDetail.from_row(row)

    assert job.scheduled_for == "2026-03-28T14:00:00+00:00"
    assert job.claimed_at == ""
    assert job.completed_at == ""
    assert job.created_at == "2026-03-28T13:55:00+00:00"
    assert job.updated_at == "2026-03-28T13:56:00+00:00"


def test_ads_dispatcher_submit_job_allows_twse_market_job_without_symbols():
    """
    Exercise the
    test_ads_dispatcher_submit_job_allows_twse_market_job_without_symbols regression
    scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", ":memory:")
    dispatcher = ADSDispatcherAgent(pool=pool)

    result = dispatcher.submit_job(
        required_capability="TWSE Market EOD",
        payload={},
    )

    assert result["status"] == "success"
    assert result["job"]["symbols"] == []


def test_ads_dispatcher_control_job_can_pause_and_delete_job():
    """
    Exercise the test_ads_dispatcher_control_job_can_pause_and_delete_job regression
    scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", ":memory:")
    dispatcher = ADSDispatcherAgent(pool=pool)

    submission = dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})
    job_id = submission["job"]["id"]

    paused = dispatcher.control_job(job_id=job_id, action="pause", worker_id="boss-1")
    assert paused["job"]["status"] == "paused"
    assert paused["job"]["metadata"]["boss_control"]["action"] == "pause"
    assert dispatcher.claim_job(worker_id="worker-a", capabilities=["news"])["job"] is None

    deleted = dispatcher.control_job(job_id=job_id, action="delete", worker_id="boss-1")
    assert deleted["job"]["status"] == "deleted"
    assert deleted["job"]["metadata"]["boss_control"]["action"] == "delete"


def test_ads_dispatcher_control_job_rejects_claimed_job():
    """
    Exercise the test_ads_dispatcher_control_job_rejects_claimed_job regression
    scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", ":memory:")
    dispatcher = ADSDispatcherAgent(pool=pool)

    submission = dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})
    job_id = submission["job"]["id"]
    dispatcher.claim_job(worker_id="worker-a", capabilities=["news"])

    try:
        dispatcher.control_job(job_id=job_id, action="pause", worker_id="boss-1")
        assert False, "Expected claimed jobs to reject pause."
    except ValueError as exc:
        assert "cannot be paused" in str(exc)


def test_ads_dispatcher_control_job_can_stop_resume_and_cancel_claimed_job():
    """
    Exercise the
    test_ads_dispatcher_control_job_can_stop_resume_and_cancel_claimed_job
    regression scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", ":memory:")
    dispatcher = ADSDispatcherAgent(pool=pool)

    submission = dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})
    job_id = submission["job"]["id"]
    dispatcher.claim_job(worker_id="worker-a", capabilities=["news"])

    stopping = dispatcher.control_job(job_id=job_id, action="stop", worker_id="boss-1", reason="Operator stop")
    assert stopping["job"]["status"] == "stopping"
    assert stopping["job"]["metadata"]["boss_control"]["action"] == "stop"

    dispatcher.post_job_result(
        JobResult(
            job_id=job_id,
            worker_id="worker-a",
            status="stopped",
            result_summary={"stopped": True},
            error="ADS job was stopped by the boss.",
        )
    )
    stopped_rows = dispatcher.pool._GetTableData(TABLE_JOBS, job_id)
    stopped_rows.sort(key=lambda row: row["updated_at"], reverse=True)
    assert stopped_rows[0]["status"] == "stopped"

    resumed = dispatcher.control_job(job_id=job_id, action="resume", worker_id="boss-1")
    assert resumed["job"]["status"] == "queued"
    assert resumed["job"]["claimed_by"] == ""
    assert resumed["job"]["claimed_at"] == ""

    canceled = dispatcher.control_job(job_id=job_id, action="cancel", worker_id="boss-1")
    assert canceled["job"]["status"] == "cancelled"
    assert canceled["job"]["metadata"]["boss_control"]["action"] == "cancel"


def test_ads_dispatcher_register_worker_persists_worker_history_and_progress(tmp_path):
    """
    Exercise the
    test_ads_dispatcher_register_worker_persists_worker_history_and_progress
    regression scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", str(tmp_path / "dispatcher.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool)

    result = dispatcher.register_worker(
        worker_id="worker-a",
        name="Worker A",
        address="http://127.0.0.1:8061",
        capabilities=["news"],
        metadata={
            "environment": {"hostname": "worker-host"},
            "heartbeat": {
                "session_started_at": "2026-03-29T10:00:00+00:00",
                "active_job": {"id": "ads-job:1", "status": "working"},
                "progress": {"phase": "working", "percent": 50, "message": "Halfway there"},
            },
        },
        status="working",
        event_type="heartbeat",
    )

    assert result["status"] == "success"
    history_rows = dispatcher.pool._GetTableData(TABLE_WORKER_HISTORY, {"worker_id": "worker-a"})
    assert len(history_rows) == 1
    history_row = history_rows[0]
    assert history_row["event_type"] == "heartbeat"
    assert history_row["status"] == "working"
    assert history_row["active_job_id"] == "ads-job:1"
    assert history_row["progress"]["percent"] == 50
    assert history_row["environment"]["hostname"] == "worker-host"


def test_ads_dispatcher_marks_stale_claimed_job_unfinished_and_ignores_late_results(tmp_path):
    """
    Exercise the
    test_ads_dispatcher_marks_stale_claimed_job_unfinished_and_ignores_late_results
    regression scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", str(tmp_path / "dispatcher.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool)

    submission = dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})
    job_id = submission["job"]["id"]
    dispatcher.claim_job(worker_id="worker-a", capabilities=["news"])

    stale_at = (datetime.now(timezone.utc) - timedelta(seconds=181)).isoformat()
    assert dispatcher.pool._Insert(
        TABLE_WORKERS,
        {
            "id": "worker-a",
            "worker_id": "worker-a",
            "name": "Worker A",
            "address": "http://127.0.0.1:8061",
            "capabilities": ["news"],
            "metadata": {
                "environment": {"hostname": "worker-a-host"},
                "heartbeat": {
                    "session_started_at": "2026-03-29T10:00:00+00:00",
                    "active_job": {"id": job_id, "status": "working"},
                    "progress": {"phase": "working", "message": "Collecting rows"},
                },
            },
            "plaza_url": "",
            "status": "online",
            "last_seen_at": stale_at,
            "updated_at": stale_at,
        },
    )

    dispatcher.register_worker(
        worker_id="worker-b",
        name="Worker B",
        address="http://127.0.0.1:8062",
        capabilities=["news"],
        metadata={"environment": {"hostname": "worker-b-host"}},
        status="online",
        event_type="heartbeat",
    )

    unfinished_rows = dispatcher.pool._GetTableData(TABLE_JOBS, job_id)
    unfinished_rows.sort(key=lambda row: row["updated_at"], reverse=True)
    unfinished_job = unfinished_rows[0]
    assert unfinished_job["status"] == "unfinished"
    assert unfinished_job["claimed_by"] == ""
    assert "missed ADS heartbeats" in unfinished_job["error"]
    assert unfinished_job["result_summary"]["unfinished"] is True
    assert unfinished_job["result_summary"]["last_progress"]["phase"] == "working"

    ignored = dispatcher.post_job_result(
        JobResult(
            job_id=job_id,
            worker_id="worker-a",
            status="completed",
            result_summary={"rows": 1},
        )
    )
    assert ignored["ignored"] is True

    reclaim = dispatcher.claim_job(worker_id="worker-b", capabilities=["news"])
    reclaimed_job = JobDetail.model_validate(reclaim["job"])
    assert reclaimed_job.status == "claimed"
    assert reclaimed_job.claimed_by == "worker-b"


def test_ads_dispatcher_serializes_concurrent_claims_for_same_job(tmp_path):
    """
    Exercise the test_ads_dispatcher_serializes_concurrent_claims_for_same_job
    regression scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", str(tmp_path / "dispatcher.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool)

    submission = dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})
    job_id = submission["job"]["id"]
    original_query_ready_job_candidates = dispatcher._query_ready_job_candidates
    first_job_read_started = threading.Event()
    release_first_job_read = threading.Event()
    call_counter = {"candidate_queries": 0}

    def blocked_query_ready_job_candidates(capabilities, *, limit=None):
        """Handle blocked ready-job candidate query."""
        call_counter["candidate_queries"] += 1
        if call_counter["candidate_queries"] == 1:
            first_job_read_started.set()
            assert release_first_job_read.wait(timeout=2.0)
        return original_query_ready_job_candidates(capabilities, limit=limit)

    results: dict[str, dict[str, Any]] = {}
    errors: list[Exception] = []

    def claim(worker_id: str) -> None:
        """Claim the value."""
        try:
            results[worker_id] = dispatcher.claim_job(worker_id=worker_id, capabilities=["news"])
        except Exception as exc:  # pragma: no cover - regression visibility only
            errors.append(exc)

    with patch.object(dispatcher, "register_worker", return_value={"status": "success"}), patch.object(
        dispatcher,
        "_query_ready_job_candidates",
        side_effect=blocked_query_ready_job_candidates,
    ):
        thread_a = threading.Thread(target=claim, args=("worker-a",), daemon=True)
        thread_b = threading.Thread(target=claim, args=("worker-b",), daemon=True)
        thread_a.start()
        assert first_job_read_started.wait(timeout=1.0)
        thread_b.start()
        time.sleep(0.2)
        release_first_job_read.set()
        thread_a.join(timeout=2.0)
        thread_b.join(timeout=2.0)

    assert not errors
    claimed_jobs = [payload["job"] for payload in results.values() if payload.get("job")]
    assert len(claimed_jobs) == 1
    assert claimed_jobs[0]["id"] == job_id
    assert {payload.get("job") is None for payload in results.values()} == {False, True}


def test_ads_dispatcher_ignores_result_after_job_already_completed_by_other_worker(tmp_path):
    """
    Exercise the
    test_ads_dispatcher_ignores_result_after_job_already_completed_by_other_worker
    regression scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", str(tmp_path / "dispatcher.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool)

    submission = dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})
    job_id = submission["job"]["id"]
    claimed = dispatcher.claim_job(worker_id="worker-a", capabilities=["news"])
    claimed_job = JobDetail.model_validate(claimed["job"])
    completed_at = utcnow_iso()
    completed_job = claimed_job.model_copy(
        update={
            "status": "completed",
            "claimed_by": "worker-b",
            "updated_at": completed_at,
            "completed_at": completed_at,
            "result_summary": {"rows": 1, "completed_by": "worker-b"},
        }
    )
    assert dispatcher.pool._Insert(TABLE_JOBS, completed_job.to_row())

    ignored = dispatcher.post_job_result(
        JobResult(
            job_id=job_id,
            worker_id="worker-a",
            status="completed",
            result_summary={"rows": 99, "completed_by": "worker-a"},
        )
    )

    assert ignored["ignored"] is True
    latest_rows = dispatcher.pool._GetTableData(TABLE_JOBS, job_id)
    latest_rows.sort(key=lambda row: row["updated_at"], reverse=True)
    assert latest_rows[0]["status"] == "completed"
    assert latest_rows[0]["claimed_by"] == "worker-b"
    assert latest_rows[0]["result_summary"]["completed_by"] == "worker-b"


def test_ads_dispatcher_ignores_late_result_after_job_has_been_archived(tmp_path):
    """
    Exercise the test_ads_dispatcher_ignores_late_result_after_job_has_been_archived
    regression scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", str(tmp_path / "dispatcher.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool)

    submission = dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})
    job_id = submission["job"]["id"]
    claimed = dispatcher.claim_job(worker_id="worker-a", capabilities=["news"])
    claimed_job = JobDetail.model_validate(claimed["job"])
    completed_at = utcnow_iso()
    completed_job = claimed_job.model_copy(
        update={
            "status": "completed",
            "claimed_by": "worker-b",
            "updated_at": completed_at,
            "completed_at": completed_at,
            "result_summary": {"rows": 1, "completed_by": "worker-b"},
        }
    )
    archive_row = completed_job.to_row()
    archive_row["archived_at"] = completed_at
    assert dispatcher.pool._Insert(TABLE_JOB_ARCHIVE, archive_row)
    dispatcher._delete_job_row(TABLE_JOBS, job_id)

    ignored = dispatcher.post_job_result(
        JobResult(
            job_id=job_id,
            worker_id="worker-a",
            status="completed",
            result_summary={"rows": 99, "completed_by": "worker-a"},
        )
    )

    assert ignored["ignored"] is True
    latest_rows = dispatcher.pool._GetTableData(TABLE_JOB_ARCHIVE, job_id)
    latest_rows.sort(key=lambda row: row["updated_at"], reverse=True)
    assert latest_rows[0]["status"] == "completed"
    assert latest_rows[0]["claimed_by"] == "worker-b"
    assert latest_rows[0]["result_summary"]["completed_by"] == "worker-b"


def test_ads_dispatcher_db_viewer_lists_tables_and_runs_read_only_queries():
    """
    Exercise the
    test_ads_dispatcher_db_viewer_lists_tables_and_runs_read_only_queries regression
    scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", ":memory:")
    dispatcher = ADSDispatcherAgent(pool=pool)
    dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})

    tables = dispatcher.list_db_tables()
    assert any(table["name"] == TABLE_JOBS for table in tables["tables"])
    assert any(table["name"] == TABLE_JOB_ARCHIVE for table in tables["tables"])

    preview = dispatcher.preview_db_table(TABLE_JOBS, limit=10)
    assert preview["table_name"] == TABLE_JOBS
    assert preview["count"] == 1
    assert "id" in preview["columns"]

    query = dispatcher.query_db("SELECT id, status FROM ads_jobs ORDER BY created_at DESC", limit=10)
    assert query["count"] == 1
    assert query["columns"] == ["id", "status"]

    try:
        dispatcher.query_db("DELETE FROM ads_jobs")
        assert False, "Expected DB Viewer to reject write SQL."
    except ValueError as exc:
        assert "read-only SQL" in str(exc)


def test_ads_dispatcher_db_viewer_supports_postgres_pool():
    """
    Exercise the test_ads_dispatcher_db_viewer_supports_postgres_pool regression
    scenario.
    """
    class DummyLock:
        """Represent a dummy lock."""
        def __enter__(self):
            """Enter the context manager."""
            return self

        def __exit__(self, exc_type, exc, tb):
            """Exit the context manager."""
            return False

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
            if "FROM information_schema.tables" in normalized_query:
                self.description = [("table_name",)]
                self.rows = [(TABLE_JOBS,)]
            elif normalized_query.startswith('SELECT * FROM "market_data"."ads_jobs"'):
                self.description = [("id",), ("status",)]
                self.rows = [("job-1", "queued")]
            elif normalized_query.startswith('SELECT COUNT(*) FROM "market_data"."ads_jobs"'):
                self.description = [("count",)]
                self.rows = [(1,)]
            elif normalized_query.startswith("SHOW search_path"):
                self.description = [("search_path",)]
                self.rows = [('market_data, public',)]
            elif normalized_query == "SELECT 1":
                self.description = [("?column?",)]
                self.rows = [(1,)]
            else:
                raise AssertionError(f"Unexpected query: {normalized_query}")

        def fetchall(self):
            """Handle fetchall for the fake cursor."""
            return list(self.rows)

        def fetchone(self):
            """Handle fetchone for the fake cursor."""
            return self.rows[0] if self.rows else None

        def fetchmany(self, size):
            """Handle fetchmany for the fake cursor."""
            return list(self.rows[:size])

        def __enter__(self):
            """Enter the context manager."""
            return self

        def __exit__(self, exc_type, exc, tb):
            """Exit the context manager."""
            return False

    class FakeConnection:
        """Represent a fake connection."""
        def __init__(self, calls):
            """Initialize the fake connection."""
            self.calls = calls

        def cursor(self):
            """Return the cursor."""
            return FakeCursor(self.calls)

    class PostgresPool:
        """Represent a Postgres pool."""
        def __init__(self):
            """Initialize the Postgres pool."""
            self.lock = DummyLock()
            self.schema = "market_data"
            self.conn = FakeConnection([])

        def _ensure_connection(self):
            """Internal helper to ensure the connection exists."""
            return True

    dispatcher = ADSDispatcherAgent(pool=SQLitePool("ads_dispatch", "ADS dispatch test pool", ":memory:"))
    fake_pool = PostgresPool()
    dispatcher.pool = fake_pool

    tables = dispatcher.list_db_tables()
    assert tables["tables"] == [{"name": TABLE_JOBS, "description": ads_table_schema_map()[TABLE_JOBS].description}]

    preview = dispatcher.preview_db_table(TABLE_JOBS, limit=10)
    assert preview["table_name"] == TABLE_JOBS
    assert preview["rows"] == [{"id": "job-1", "status": "queued"}]

    query = dispatcher.query_db("SHOW search_path", limit=10)
    assert query["columns"] == ["search_path"]
    assert query["rows"] == [{"search_path": "market_data, public"}]

    assert any("FROM information_schema.tables" in sql for sql, _params in fake_pool.conn.calls)
    assert any(sql.startswith('SELECT * FROM "market_data"."ads_jobs"') for sql, _params in fake_pool.conn.calls)


def test_ensure_ads_tables_compacts_legacy_jobs_table(tmp_path):
    """
    Exercise the test_ensure_ads_tables_compacts_legacy_jobs_table regression
    scenario.
    """
    pool = SQLitePool("ads_dispatch", "ADS dispatch test pool", str(tmp_path / "ads.sqlite"))

    with pool.lock:
        pool.conn.execute("DROP TABLE IF EXISTS ads_jobs")
        pool.conn.execute(
            """
            CREATE TABLE ads_jobs (
                id TEXT,
                job_type TEXT,
                status TEXT,
                required_capability TEXT,
                capability_tags TEXT,
                symbols TEXT,
                payload TEXT,
                target_table TEXT,
                source_url TEXT,
                parse_rules TEXT,
                priority INTEGER,
                premium INTEGER,
                metadata TEXT,
                scheduled_for TEXT,
                claimed_by TEXT,
                claimed_at TEXT,
                completed_at TEXT,
                result_summary TEXT,
                error TEXT,
                attempts INTEGER,
                max_attempts INTEGER,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        pool.conn.commit()

    pool._Insert(
        TABLE_JOBS,
        {
            "id": "ads-job:legacy-1",
            "job_type": "collect",
            "status": "queued",
            "required_capability": "yfinance eod",
            "capability_tags": [],
            "symbols": ["MSFT"],
            "payload": {"symbol": "MSFT"},
            "target_table": "",
            "source_url": "",
            "parse_rules": {},
            "priority": 100,
            "premium": False,
            "metadata": {},
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "claimed_by": "",
            "claimed_at": "",
            "completed_at": "",
            "result_summary": {},
            "error": "",
            "attempts": 0,
            "max_attempts": 3,
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:00+00:00",
        },
    )
    pool._Insert(
        TABLE_JOBS,
        {
            "id": "ads-job:legacy-1",
            "job_type": "collect",
            "status": "completed",
            "required_capability": "yfinance eod",
            "capability_tags": [],
            "symbols": ["MSFT"],
            "payload": {"symbol": "MSFT"},
            "target_table": "",
            "source_url": "",
            "parse_rules": {},
            "priority": 100,
            "premium": False,
            "metadata": {},
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "claimed_by": "worker-a",
            "claimed_at": "2026-03-28T10:00:02+00:00",
            "completed_at": "2026-03-28T10:00:03+00:00",
            "result_summary": {"rows": 1},
            "error": "",
            "attempts": 1,
            "max_attempts": 3,
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:03+00:00",
        },
    )

    ensure_ads_tables(pool, [TABLE_JOBS])
    dispatcher = ADSDispatcherAgent(pool=pool)
    claim_result = dispatcher.claim_job(worker_id="worker-b", capabilities=["yfinance eod"])

    rows = pool._GetTableData(TABLE_JOBS, "ads-job:legacy-1")
    assert len(rows) == 1
    assert rows[0]["status"] == "completed"
    assert rows[0]["attempts"] == 1
    assert claim_result["job"] is None

    with pool.lock:
        cursor = pool.conn.cursor()
        cursor.execute("PRAGMA table_info('ads_jobs')")
        table_info = cursor.fetchall()
    assert any(column[1] == "id" and int(column[5] or 0) > 0 for column in table_info)


def test_ensure_ads_tables_skips_sqlite_integrity_migrations_for_postgres_pool():
    """
    Exercise the
    test_ensure_ads_tables_skips_sqlite_integrity_migrations_for_postgres_pool
    regression scenario.
    """
    class DummyLock:
        """Represent a dummy lock."""
        def __enter__(self):
            """Enter the context manager."""
            return self

        def __exit__(self, exc_type, exc, tb):
            """Exit the context manager."""
            return False

    class FakeCursor:
        """Represent a fake cursor."""
        def __init__(self, calls):
            """Initialize the fake cursor."""
            self.calls = calls

        def execute(self, query, params=None):
            """Handle execute for the fake cursor."""
            self.calls.append((str(query).strip(), params))
            raise AssertionError("SQLite PRAGMA-style integrity queries should not run for PostgresPool.")

    class FakeConnection:
        """Represent a fake connection."""
        def __init__(self):
            """Initialize the fake connection."""
            self.calls = []

        def cursor(self):
            """Return the cursor."""
            return FakeCursor(self.calls)

    class PostgresPool:
        """Represent a Postgres pool."""
        def __init__(self):
            """Initialize the Postgres pool."""
            self.lock = DummyLock()
            self.conn = FakeConnection()
            self.created_tables = []

        def _ensure_connection(self):
            """Internal helper to ensure the connection exists."""
            return True

        def _TableExists(self, table_name):
            """Return whether the table exists for value."""
            return True

        def _CreateTable(self, table_name, schema):
            """Internal helper to create the table."""
            self.created_tables.append((table_name, schema.name))
            return True

    pool = PostgresPool()

    ensure_ads_tables(pool, [TABLE_JOBS, TABLE_SECURITY_MASTER, TABLE_DAILY_PRICE])

    assert pool.conn.calls == []
    assert pool.created_tables == []


def test_ads_pulser_reads_shared_tables(tmp_path):
    """Exercise the test_ads_pulser_reads_shared_tables regression scenario."""
    pool = SQLitePool("ads_pulser", "ADS pulser test pool", str(tmp_path / "ads.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool)

    dispatcher.submit_job(required_capability="daily_price", symbols=["NVDA"])
    queued_job = JobDetail.model_validate(dispatcher.claim_job(worker_id="worker-a", capabilities=["daily_price"])["job"])
    dispatcher.post_job_result(
        JobResult(
            job_id=queued_job.id,
            worker_id="worker-a",
            status="completed",
            collected_rows=[
                {
                    "symbol": "NVDA",
                    "trade_date": "2026-03-27",
                    "open": 120.0,
                    "high": 125.0,
                    "low": 118.0,
                    "close": 124.0,
                    "adj_close": 124.0,
                    "volume": 1000,
                }
            ],
            raw_payload={"rows": 1},
        )
    )

    pulser = ADSPulser(pool=pool, auto_register=False)
    prices = pulser.get_pulse_data({"symbol": "NVDA"}, pulse_name="daily_price_history")

    assert prices["symbol"] == "NVDA"
    assert prices["count"] == 1
    assert prices["prices"][0]["close"] == 124.0


def test_ads_pulser_maps_company_profile_from_fundamentals_and_security_master(tmp_path):
    """
    Exercise the
    test_ads_pulser_maps_company_profile_from_fundamentals_and_security_master
    regression scenario.
    """
    pool = SQLitePool("ads_pulser", "ADS pulser test pool", str(tmp_path / "ads.sqlite"))
    ensure_ads_tables(pool)
    assert pool._Insert(
        TABLE_SECURITY_MASTER,
        {
            "id": "ads-security-master:AAPL",
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "exchange": "NASDAQ",
            "currency": "USD",
            "provider": "demo",
            "metadata": {"website": "https://fallback.example.com"},
        },
    )
    assert pool._Insert(
        TABLE_FUNDAMENTALS,
        {
            "id": "ads-fundamentals:AAPL:2026-03-28",
            "symbol": "AAPL",
            "as_of_date": "2026-03-28",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "provider": "demo",
            "data": {
                "website": "https://www.apple.com",
                "headquarters_country": "United States",
                "legal_name": "Apple Inc.",
            },
        },
    )

    pulser = ADSPulser(pool=pool, auto_register=False)

    company_profile = pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="company_profile")
    legacy_profile = pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="company_fundamentals")

    assert company_profile == legacy_profile
    assert company_profile == {
        "symbol": "AAPL",
        "company_name": "Apple Inc.",
        "legal_name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "headquarters_country": "United States",
        "website": "https://www.apple.com",
        "exchange": "NASDAQ",
        "currency": "USD",
        "source": "demo",
    }


def test_ads_pulser_maps_news_article_from_ads_news_rows(tmp_path):
    """
    Exercise the test_ads_pulser_maps_news_article_from_ads_news_rows regression
    scenario.
    """
    pool = SQLitePool("ads_pulser", "ADS pulser test pool", str(tmp_path / "ads.sqlite"))
    ensure_ads_tables(pool)
    seed_security_master_symbol(pool, "AAPL", provider="demo", name="Apple Inc.")
    assert pool._Insert(
        TABLE_NEWS,
        {
            "id": "ads-news:AAPL:1",
            "symbol": "AAPL",
            "headline": "Apple launches AI features",
            "summary": "Apple previewed a new on-device assistant.",
            "url": "https://example.com/apple-ai",
            "source": "ExampleWire",
            "published_at": "2026-03-28T09:30:00+00:00",
            "data": {"sentiment_label": "Bullish"},
        },
    )

    pulser = ADSPulser(pool=pool, auto_register=False)

    news_article = pulser.get_pulse_data(
        {"symbol": "AAPL", "number_of_articles": 1},
        pulse_name="news_article",
    )
    legacy_news = pulser.get_pulse_data(
        {"symbol": "AAPL", "number_of_articles": 1},
        pulse_name="company_news",
    )

    assert news_article == legacy_news
    assert news_article == {
        "symbol": "AAPL",
        "number_of_articles": 1,
        "articles": [
            {
                "headline": "Apple launches AI features",
                "published_at": "2026-03-28T09:30:00+00:00",
                "publisher": "ExampleWire",
                "summary": "Apple previewed a new on-device assistant.",
                "url": "https://example.com/apple-ai",
                "sentiment_label": "Bullish",
            }
        ],
        "source": "ads",
    }


def test_ads_pulser_maps_news_article_without_symbol_filter(tmp_path):
    """
    Exercise the test_ads_pulser_maps_news_article_without_symbol_filter regression
    scenario.
    """
    pool = SQLitePool("ads_pulser", "ADS pulser test pool", str(tmp_path / "ads.sqlite"))
    ensure_ads_tables(pool)
    assert pool._Insert(
        TABLE_NEWS,
        {
            "id": "ads-news:rss:1",
            "headline": "SEC updates disclosure guidance",
            "summary": "The SEC published a live regulatory update.",
            "url": "https://example.com/sec-guidance",
            "source": "SEC",
            "source_url": "https://www.sec.gov/news/pressreleases.rss",
            "published_at": "2026-03-28T09:30:00+00:00",
        },
    )

    pulser = ADSPulser(pool=pool, auto_register=False)

    news_article = pulser.get_pulse_data(
        {"number_of_articles": 1},
        pulse_name="news_article",
    )

    assert news_article == {
        "number_of_articles": 1,
        "articles": [
            {
                "headline": "SEC updates disclosure guidance",
                "published_at": "2026-03-28T09:30:00+00:00",
                "publisher": "SEC",
                "summary": "The SEC published a live regulatory update.",
                "url": "https://example.com/sec-guidance",
            }
        ],
        "source": "ads",
    }


def test_ads_pulser_maps_sec_companyfact_from_symbol_lookup(tmp_path):
    """
    Exercise the test_ads_pulser_maps_sec_companyfact_from_symbol_lookup regression
    scenario.
    """
    pool = SQLitePool("ads_pulser", "ADS pulser test pool", str(tmp_path / "ads.sqlite"))
    ensure_ads_tables(pool)
    assert pool._Insert(
        TABLE_SEC_COMPANYFACTS,
        {
            "id": "ads-sec-companyfacts:0000320193",
            "cik": "0000320193",
            "entity_name": "Apple Inc.",
            "file_name": "CIK0000320193.json",
            "fact_count": 14,
            "provider": "sec_edgar",
            "payload": {"facts": {"dei": {"EntityCommonStockSharesOutstanding": {}}}},
        },
    )
    assert pool._Insert(
        TABLE_SEC_SUBMISSIONS,
        {
            "id": "ads-sec-submissions:0000320193:CIK0000320193.json",
            "cik": "0000320193",
            "entity_name": "Apple Inc.",
            "symbol": "AAPL",
            "symbols": ["AAPL"],
            "exchanges": ["Nasdaq"],
            "file_name": "CIK0000320193.json",
            "is_primary": True,
            "filing_count": 2,
            "provider": "sec_edgar",
            "payload": {"tickers": ["AAPL"]},
        },
    )

    pulser = ADSPulser(pool=pool, auto_register=False)

    companyfact = pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="sec_companyfact")
    legacy_companyfacts = pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="sec_companyfacts")

    assert companyfact == legacy_companyfacts
    assert companyfact["cik"] == "0000320193"
    assert companyfact["symbol"] == "AAPL"
    assert companyfact["count"] == 1
    assert companyfact["companyfact"]["entity_name"] == "Apple Inc."
    assert companyfact["companyfact"]["payload"]["facts"]["dei"]["EntityCommonStockSharesOutstanding"] == {}


def test_ads_pulser_maps_sec_submission_rows(tmp_path):
    """Exercise the test_ads_pulser_maps_sec_submission_rows regression scenario."""
    pool = SQLitePool("ads_pulser", "ADS pulser test pool", str(tmp_path / "ads.sqlite"))
    ensure_ads_tables(pool)
    assert pool._Insert(
        TABLE_SEC_SUBMISSIONS,
        {
            "id": "ads-sec-submissions:0000320193:primary",
            "cik": "0000320193",
            "entity_name": "Apple Inc.",
            "symbol": "AAPL",
            "symbols": ["AAPL"],
            "exchanges": ["Nasdaq"],
            "file_name": "CIK0000320193.json",
            "is_primary": True,
            "filing_count": 5,
            "provider": "sec_edgar",
            "payload": {"tickers": ["AAPL"]},
        },
    )
    assert pool._Insert(
        TABLE_SEC_SUBMISSIONS,
        {
            "id": "ads-sec-submissions:0000320193:supplemental",
            "cik": "0000320193",
            "entity_name": "Apple Inc.",
            "symbol": "AAPL",
            "symbols": ["AAPL"],
            "exchanges": ["Nasdaq"],
            "file_name": "CIK0000320193-submissions-001.json",
            "is_primary": False,
            "filing_count": 1,
            "provider": "sec_edgar",
            "payload": {"tickers": ["AAPL"], "supplemental": True},
        },
    )

    pulser = ADSPulser(pool=pool, auto_register=False)

    submission = pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="sec_submission")
    legacy_submissions = pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="sec_submissions")

    assert submission == legacy_submissions
    assert submission["cik"] == "0000320193"
    assert submission["symbol"] == "AAPL"
    assert submission["count"] == 2
    assert bool(submission["items"][0]["is_primary"]) is True
    assert submission["items"][0]["file_name"] == "CIK0000320193.json"
    assert submission["items"][1]["payload"]["supplemental"] is True


def test_ads_pulser_defaults_include_stable_pulse_addresses():
    """
    Exercise the test_ads_pulser_defaults_include_stable_pulse_addresses regression
    scenario.
    """
    pool = SQLitePool("ads_pulser", "ADS pulser test pool", ":memory:")
    pulser = ADSPulser(pool=pool, auto_register=False)

    pulse_addresses = {pulse["name"]: pulse["pulse_address"] for pulse in pulser.supported_pulses}

    assert pulse_addresses == {
        "security_master_lookup": "plaza://pulse/security_master_lookup",
        "daily_price_history": "plaza://pulse/daily_price_history",
        "company_profile": "plaza://pulse/company_profile",
        "financial_statements": "plaza://pulse/financial_statements",
        "news_article": "plaza://pulse/news_article",
        "sec_companyfact": "plaza://pulse/sec_companyfact",
        "sec_submission": "plaza://pulse/sec_submission",
        "raw_collection_payload": "plaza://pulse/raw_collection_payload",
    }


def test_ads_pulser_agent_config_loads_via_shared_agent_factory(tmp_path):
    """
    Exercise the test_ads_pulser_agent_config_loads_via_shared_agent_factory
    regression scenario.
    """
    sample_config_path = Path(__file__).resolve().parents[2] / "ads" / "configs" / "pulser.agent"
    sample_config = json.loads(sample_config_path.read_text(encoding="utf-8"))
    sample_config["pools"][0]["type"] = "SQLitePool"
    sample_config["pools"][0]["db_path"] = str(tmp_path / "ads.sqlite")
    sample_config["pools"][0].pop("schema", None)
    sample_config["pools"][0].pop("sslmode", None)
    config_path = tmp_path / "ads_pulser.agent"
    config_path.write_text(json.dumps(sample_config), encoding="utf-8")
    sent_payloads = []

    def fake_post(url, json=None, timeout=5, **kwargs):
        """Handle fake post."""
        sent_payloads.append({"url": url, "payload": dict(json or {}), "timeout": timeout})
        return FakeIEXResponse(
            {
                "status": "registered",
                "token": "ads-pulser-token",
                "expires_in": 3600,
                "agent_id": "ads-pulser-id",
                "api_key": "ads-pulser-key",
            },
            url=url,
        )

    with patch("prompits.agents.base.requests.post", side_effect=fake_post), patch(
        "prompits.agents.base.requests.get",
        return_value=FakeIEXResponse([], url="http://127.0.0.1:8011/search", status_code=200),
    ):
        agent = build_agent_from_config(str(config_path))

    assert agent.name == "ADSPulser"
    assert agent.port == 8062
    assert agent.plaza_url == "http://127.0.0.1:8011"
    assert agent.agent_id == "ads-pulser-id"
    assert len(agent.supported_pulses) == 8

    register_calls = [entry for entry in sent_payloads if entry["url"] == "http://127.0.0.1:8011/register"]
    assert len(register_calls) == 1
    assert register_calls[0]["payload"]["pit_type"] == "Pulser"
    assert len(register_calls[0]["payload"]["pulse_pulser_pairs"]) == 8
    assert {
        pair["pulse_name"]: pair["pulse_address"]
        for pair in register_calls[0]["payload"]["pulse_pulser_pairs"]
    } == {
        "security_master_lookup": "plaza://pulse/security_master_lookup",
        "daily_price_history": "plaza://pulse/daily_price_history",
        "company_profile": "plaza://pulse/company_profile",
        "financial_statements": "plaza://pulse/financial_statements",
        "news_article": "plaza://pulse/news_article",
        "sec_companyfact": "plaza://pulse/sec_companyfact",
        "sec_submission": "plaza://pulse/sec_submission",
        "raw_collection_payload": "plaza://pulse/raw_collection_payload",
    }


def test_ads_pulser_uses_shared_editor_and_test_endpoint(tmp_path):
    """
    Exercise the test_ads_pulser_uses_shared_editor_and_test_endpoint regression
    scenario.
    """
    config_path = tmp_path / "demo_ads.pulser"
    config_path.write_text(
        json.dumps(
            {
                "name": "DemoADSPulser",
                "type": "ads.pulser.ADSPulser",
                "host": "127.0.0.1",
                "port": 8127,
                "description": "Demo ADS pulser",
                "tags": ["ads", "market-data"],
                "ads": {
                    "auto_register": False,
                },
                "supported_pulses": [
                    {
                        "name": "daily_price_history",
                        "description": "Return daily OHLCV history collected by ADS.",
                        "pulse_address": "plaza://pulse/daily_price_history",
                        "tags": ["ads", "prices", "ohlcv"],
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "limit": {"type": "integer"},
                            },
                            "required": ["symbol"],
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "prices": {"type": "array"},
                                "count": {"type": "integer"},
                            },
                        },
                        "test_data": {"symbol": "NVDA"},
                    }
                ],
                "pools": [
                    {
                        "type": "SQLitePool",
                        "name": "demo_ads_pool",
                        "description": "test pool",
                        "db_path": str(tmp_path / "ads.sqlite"),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))
    seed_security_master_symbol(agent.pool, "NVDA", provider="demo")
    agent.pool._Insert(
        TABLE_DAILY_PRICE,
        {
            "id": "ads-daily-price:NVDA:2026-03-28:demo",
            "symbol": "NVDA",
            "trade_date": "2026-03-28",
            "provider": "demo",
            "open": 118.0,
            "high": 121.0,
            "low": 117.5,
            "close": 120.5,
            "adj_close": 120.5,
            "volume": 1000,
        },
    )

    with TestClient(agent.app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "DemoADSPulser Config" in root.text
        assert "Search Supported Pulses" in root.text
        assert "APIsPulser Details" in root.text
        assert "Pulse Details" in root.text
        assert "Pulse Test Data JSON" in root.text
        assert "Test Runner" in root.text
        assert '<div id="config-preview" class="json-tree-shell"></div>' in root.text
        assert '<div id="test-runner-result" class="json-tree-shell result"></div>' in root.text

        current = client.get("/api/config")
        assert current.status_code == 200
        payload = current.json()["config"]
        assert payload["name"] == "DemoADSPulser"
        assert payload["supported_pulses"][0]["test_data"]["symbol"] == "NVDA"

        invalid_payload = json.loads(json.dumps(payload))
        invalid_payload["supported_pulses"][0]["test_data"] = {}
        invalid_save = client.post("/api/config", json={"config": invalid_payload})
        assert invalid_save.status_code == 400
        assert "at least one set of test parameters" in invalid_save.json()["detail"]

        payload["description"] = "Updated ADS pulser"
        payload["supported_pulses"][0]["test_data"] = {"symbol": "NVDA", "limit": 1}

        saved = client.post("/api/config", json={"config": payload})
        assert saved.status_code == 200
        saved_payload = saved.json()["config"]
        assert saved_payload["description"] == "Updated ADS pulser"
        assert saved_payload["supported_pulses"][0]["test_data"]["limit"] == 1

        tested = client.post(
            "/api/test-pulse",
            json={
                "config": payload,
                "pulse_name": "daily_price_history",
                "params": {"symbol": "NVDA", "limit": 1},
                "debug": True,
            },
        )
        assert tested.status_code == 200
        tested_payload = tested.json()
        assert tested_payload["status"] == "success"
        assert tested_payload["result"]["symbol"] == "NVDA"
        assert tested_payload["result"]["count"] == 1
        assert tested_payload["result"]["prices"][0]["close"] == 120.5
        assert tested_payload["debug"]["pulse_definition"]["name"] == "daily_price_history"
        assert tested_payload["debug"]["fetch"]["ads_table"] == TABLE_DAILY_PRICE
        assert tested_payload["debug"]["fetch"]["row_count"] == 1

    written = json.loads(config_path.read_text(encoding="utf-8"))
    assert written["description"] == "Updated ADS pulser"
    assert written["ads"]["auto_register"] is False
    assert written["supported_pulses"][0]["test_data"]["limit"] == 1


def test_ads_pulser_default_runtime_config_exposes_sample_test_data(tmp_path):
    """
    Exercise the test_ads_pulser_default_runtime_config_exposes_sample_test_data
    regression scenario.
    """
    pool = SQLitePool("ads_runtime_pool", "ADS runtime pool", str(tmp_path / "ads-runtime.sqlite"))
    ensure_ads_tables(pool)
    agent = ADSPulser(pool=pool, auto_register=False)

    with TestClient(agent.app) as client:
        response = client.get("/api/config")

    assert response.status_code == 200
    payload = response.json()["config"]
    company_profile = next(pulse for pulse in payload["supported_pulses"] if pulse["name"] == "company_profile")
    raw_collection = next(pulse for pulse in payload["supported_pulses"] if pulse["name"] == "raw_collection_payload")
    assert company_profile["test_data"]["symbol"] == "AAPL"
    assert raw_collection["test_data"]["job_id"] == "ads-job:demo"
    assert raw_collection["test_data"]["limit"] == 1


def test_ads_daily_price_is_unique_by_symbol_trade_date_and_provider(tmp_path):
    """
    Exercise the test_ads_daily_price_is_unique_by_symbol_trade_date_and_provider
    regression scenario.
    """
    pool = SQLitePool("ads_prices", "ADS daily price uniqueness pool", str(tmp_path / "ads.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool)

    dispatcher.submit_job(required_capability="daily_price", symbols=["AAPL"])
    first_job = JobDetail.model_validate(dispatcher.claim_job(worker_id="worker-a", capabilities=["daily_price"])["job"])
    dispatcher.post_job_result(
        JobResult(
            job_id=first_job.id,
            worker_id="worker-a",
            status="completed",
            collected_rows=[
                {
                    "symbol": "AAPL",
                    "trade_date": "2026-03-28",
                    "provider": "mock-feed",
                    "close": 100.0,
                }
            ],
        )
    )

    dispatcher.submit_job(required_capability="daily_price", symbols=["AAPL"])
    second_job = JobDetail.model_validate(dispatcher.claim_job(worker_id="worker-a", capabilities=["daily_price"])["job"])
    dispatcher.post_job_result(
        JobResult(
            job_id=second_job.id,
            worker_id="worker-a",
            status="completed",
            collected_rows=[
                {
                    "symbol": "AAPL",
                    "trade_date": "2026-03-28",
                    "provider": "mock-feed",
                    "close": 101.5,
                }
            ],
        )
    )

    rows = pool._GetTableData(TABLE_DAILY_PRICE, {"symbol": "AAPL"})
    assert len(rows) == 1
    assert rows[0]["provider"] == "mock-feed"
    assert rows[0]["close"] == 101.5


def test_ads_daily_price_schema_enforces_unique_symbol_trade_date_provider_in_sqlite(tmp_path):
    """
    Exercise the
    test_ads_daily_price_schema_enforces_unique_symbol_trade_date_provider_in_sqlite
    regression scenario.
    """
    pool = SQLitePool("ads_prices_schema", "ADS daily price schema uniqueness pool", str(tmp_path / "ads.sqlite"))
    assert pool._CreateTable(TABLE_SECURITY_MASTER, ads_table_schema_map()[TABLE_SECURITY_MASTER])
    schema = ads_table_schema_map()[TABLE_DAILY_PRICE]
    assert pool._CreateTable(TABLE_DAILY_PRICE, schema)
    seed_security_master_symbol(pool, "AAPL", provider="mock-feed", name="Apple Inc.")

    assert pool._Insert(
        TABLE_DAILY_PRICE,
        {
            "id": "row-1",
            "symbol": "AAPL",
            "trade_date": "2026-03-28",
            "provider": "mock-feed",
            "close": 100.0,
        },
    )
    assert pool._Insert(
        TABLE_DAILY_PRICE,
        {
            "id": "row-2",
            "symbol": "AAPL",
            "trade_date": "2026-03-28",
            "provider": "mock-feed",
            "close": 101.5,
        },
    )

    rows = pool._GetTableData(TABLE_DAILY_PRICE, {"symbol": "AAPL"})
    assert len(rows) == 1
    assert rows[0]["id"] == "row-2"
    assert rows[0]["close"] == 101.5


def test_ads_symbol_child_tables_enforce_symbol_foreign_key_to_security_master_in_sqlite(tmp_path):
    """
    Exercise the test_ads_symbol_child_tables_enforce_symbol_foreign_key_to_security
    _master_in_sqlite regression scenario.
    """
    pool = SQLitePool("ads_prices_fk", "ADS symbol child foreign key pool", str(tmp_path / "ads.sqlite"))
    schema_map = ads_table_schema_map()
    ensure_ads_tables(pool, SYMBOL_CHILD_TABLES)
    security_columns = {row[1]: row[2] for row in pool._Query(f"PRAGMA table_info('{TABLE_SECURITY_MASTER}')")}
    assert security_columns["symbol"].upper() == "VARCHAR(20)"
    assert schema_map[TABLE_SECURITY_MASTER].primary_key == ["symbol"]

    sample_rows = {
        TABLE_DAILY_PRICE: {
            "id": "daily-1",
            "symbol": "AAPL",
            "trade_date": "2026-03-28",
            "provider": "mock-feed",
            "close": 100.0,
        },
        TABLE_FUNDAMENTALS: {
            "id": "fundamentals-1",
            "symbol": "AAPL",
            "provider": "mock-feed",
            "market_cap": 123.0,
        },
        TABLE_FINANCIAL_STATEMENTS: {
            "id": "financial-statements-1",
            "symbol": "AAPL",
            "provider": "mock-feed",
            "statement_type": "income_statement",
        },
        TABLE_NEWS: {
            "id": "news-1",
            "symbol": "AAPL",
            "headline": "Sample headline",
        },
    }

    for table_name in SYMBOL_CHILD_TABLES:
        child_columns = {row[1]: row[2] for row in pool._Query(f"PRAGMA table_info('{table_name}')")}
        assert child_columns["symbol"].upper() == "VARCHAR(20)"
        foreign_keys = pool._Query(f"PRAGMA foreign_key_list('{table_name}')")
        assert any(
            str(row[2] or "").strip() == TABLE_SECURITY_MASTER
            and str(row[3] or "").strip() == "symbol"
            and str(row[4] or "").strip() == "symbol"
            for row in foreign_keys
        )
        assert not pool._Insert(table_name, dict(sample_rows[table_name]))

    assert pool._Insert(
        TABLE_SECURITY_MASTER,
        {
            "id": "sec-1",
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "provider": "mock-feed",
        },
    )
    for table_name in SYMBOL_CHILD_TABLES:
        assert pool._Insert(table_name, dict(sample_rows[table_name]))


def test_ads_daily_price_results_create_missing_security_master_parent_rows(tmp_path):
    """
    Exercise the
    test_ads_daily_price_results_create_missing_security_master_parent_rows
    regression scenario.
    """
    pool = SQLitePool("ads_prices_parent", "ADS daily price parent row pool", str(tmp_path / "ads.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool)

    dispatcher.submit_job(required_capability="daily_price", symbols=["AAPL"])
    claimed_job = JobDetail.model_validate(dispatcher.claim_job(worker_id="worker-a", capabilities=["daily_price"])["job"])
    dispatcher.post_job_result(
        JobResult(
            job_id=claimed_job.id,
            worker_id="worker-a",
            status="completed",
            collected_rows=[
                {
                    "symbol": "AAPL",
                    "trade_date": "2026-03-28",
                    "provider": "mock-feed",
                    "close": 101.5,
                }
            ],
        )
    )

    security_rows = pool._GetTableData(TABLE_SECURITY_MASTER, {"symbol": "AAPL"})
    daily_price_rows = pool._GetTableData(TABLE_DAILY_PRICE, {"symbol": "AAPL"})
    assert len(security_rows) == 1
    assert security_rows[0]["symbol"] == "AAPL"
    assert security_rows[0]["metadata"]["auto_created"] is True
    assert len(daily_price_rows) == 1
    assert daily_price_rows[0]["close"] == 101.5


def test_ads_worker_run_once_processes_remote_job(tmp_path):
    """
    Exercise the test_ads_worker_run_once_processes_remote_job regression scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    worker_config = tmp_path / "worker.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
    worker_db = tmp_path / "worker.sqlite"

    dispatcher_config.write_text(
        f"""
{{
  "name": "ADSDispatcher",
  "host": "127.0.0.1",
  "port": 9070,
  "type": "ads.agents.ADSDispatcherAgent",
  "pools": [
    {{
      "type": "SQLitePool",
      "name": "ads_dispatch_pool",
      "description": "dispatch",
      "db_path": "{dispatcher_db}"
    }}
  ]
}}
""".strip(),
        encoding="utf-8",
    )
    worker_config.write_text(
        f"""
{{
  "name": "ADSWorker",
  "host": "127.0.0.1",
  "port": 9071,
  "type": "ads.agents.ADSWorkerAgent",
  "pools": [
    {{
      "type": "SQLitePool",
      "name": "ads_worker_pool",
      "description": "worker",
      "db_path": "{worker_db}"
    }}
  ],
  "ads": {{
    "dispatcher_address": "http://127.0.0.1:9070",
    "capabilities": ["daily_price"],
    "job_capabilities": [
      {{
        "name": "daily_price",
        "callable": "ads.tests.test_ads:collect_daily_price_for_test"
      }}
    ]
  }}
}}
""".strip(),
        encoding="utf-8",
    )

    dispatcher, dispatcher_server, dispatcher_thread = start_agent_thread(str(dispatcher_config))
    worker = build_agent_from_config(str(worker_config))

    try:
        dispatcher.submit_job(
            required_capability="daily_price",
            symbols=["MSFT"],
            payload={"symbol": "MSFT"},
        )

        result = worker.run_once()

        assert result["status"] == "completed"
        assert isinstance(result["job"], JobDetail)
        assert isinstance(result["job_result"], JobResult)
        saved_rows = dispatcher.pool._GetTableData(TABLE_DAILY_PRICE, {"symbol": "MSFT"})
        assert len(saved_rows) == 1
        assert saved_rows[0]["close"] == 402.0
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_ads_worker_run_once_calls_job_cap_immediately_after_claim(caplog):
    """
    Exercise the test_ads_worker_run_once_calls_job_cap_immediately_after_claim
    regression scenario.
    """
    calls: list[str] = []
    worker = ADSWorkerAgent(
        dispatcher_address="http://127.0.0.1:9999",
        capabilities=["yfinance eod"],
        job_capabilities=[RecordingJobCap(calls, name="YFinance EOD")],
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:test-claimed",
            "job_type": "collect",
            "status": "claimed",
            "required_capability": "yfinance eod",
            "symbols": ["MSFT"],
            "payload": {"symbol": "MSFT"},
            "priority": 100,
            "premium": False,
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "attempts": 1,
            "max_attempts": 3,
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:01+00:00",
        }
    )
    reported_results: list[JobResult] = []

    with patch.object(worker, "register_capabilities", return_value={"status": "success"}), patch.object(
        worker,
        "request_job",
        return_value={"status": "success", "job": job},
    ), patch.object(
        worker,
        "post_job_result",
        side_effect=lambda result: reported_results.append(JobResult.from_value(result)) or {"status": "success"},
    ):
        with caplog.at_level("INFO"):
            result = worker.run_once()

    assert result["status"] == "completed"
    assert calls == [job.id]
    assert len(reported_results) == 1
    assert reported_results[0].job_id == job.id
    assert reported_results[0].status == "completed"
    assert f"Starting ADS job {job.id}" in caplog.text
    assert f"Completed ADS job {job.id}" in caplog.text


def test_ads_worker_run_once_retries_exception_before_max_attempts(caplog):
    """
    Exercise the test_ads_worker_run_once_retries_exception_before_max_attempts
    regression scenario.
    """
    worker = ADSWorkerAgent(
        dispatcher_address="http://127.0.0.1:9999",
        capabilities=["yfinance eod"],
        job_capabilities=[FailingJobCap()],
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:test-retry",
            "job_type": "collect",
            "status": "claimed",
            "required_capability": "yfinance eod",
            "symbols": ["MSFT"],
            "payload": {"symbol": "MSFT"},
            "priority": 100,
            "premium": False,
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "attempts": 1,
            "max_attempts": 3,
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:01+00:00",
        }
    )
    reported_results: list[JobResult] = []

    with patch.object(worker, "register_capabilities", return_value={"status": "success"}), patch.object(
        worker,
        "request_job",
        return_value={"status": "success", "job": job},
    ), patch.object(
        worker,
        "post_job_result",
        side_effect=lambda result: reported_results.append(JobResult.from_value(result)) or {"status": "success"},
    ):
        with caplog.at_level("INFO"):
            result = worker.run_once()

    assert result["status"] == "retry"
    assert len(reported_results) == 1
    assert reported_results[0].status == "retry"
    assert reported_results[0].result_summary["retryable"] is True
    assert "Reported ADS job ads-job:test-retry for retry" in caplog.text


def test_ads_worker_run_once_fails_value_error_without_retry(caplog):
    """
    Exercise the test_ads_worker_run_once_fails_value_error_without_retry regression
    scenario.
    """
    worker = ADSWorkerAgent(
        dispatcher_address="http://127.0.0.1:9999",
        capabilities=["yfinance eod"],
        job_capabilities=[FailingJobCap(message="missing symbol", error_type=ValueError)],
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:test-invalid-input",
            "job_type": "collect",
            "status": "claimed",
            "required_capability": "yfinance eod",
            "payload": {},
            "priority": 100,
            "premium": False,
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "attempts": 1,
            "max_attempts": 3,
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:01+00:00",
        }
    )
    reported_results: list[JobResult] = []

    with patch.object(worker, "register_capabilities", return_value={"status": "success"}), patch.object(
        worker,
        "request_job",
        return_value={"status": "success", "job": job},
    ), patch.object(
        worker,
        "post_job_result",
        side_effect=lambda result: reported_results.append(JobResult.from_value(result)) or {"status": "success"},
    ):
        with caplog.at_level("INFO"):
            result = worker.run_once()

    assert result["status"] == "failed"
    assert len(reported_results) == 1
    assert reported_results[0].status == "failed"
    assert reported_results[0].result_summary["retryable"] is False
    assert "Reported ADS job ads-job:test-invalid-input as failed" in caplog.text


def test_ads_worker_run_once_fails_generic_success_envelope_without_fake_completion(caplog):
    """
    Exercise the
    test_ads_worker_run_once_fails_generic_success_envelope_without_fake_completion
    regression scenario.
    """
    worker = ADSWorkerAgent(
        dispatcher_address="http://127.0.0.1:9999",
        capabilities=["news"],
        job_capabilities=[SuccessEnvelopeJobCap()],
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:test-success-envelope",
            "job_type": "collect",
            "status": "claimed",
            "required_capability": "news",
            "payload": {},
            "priority": 100,
            "premium": False,
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "attempts": 1,
            "max_attempts": 3,
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:01+00:00",
        }
    )
    reported_results: list[JobResult] = []

    with patch.object(worker, "register_capabilities", return_value={"status": "success"}), patch.object(
        worker,
        "request_job",
        return_value={"status": "success", "job": job},
    ), patch.object(
        worker,
        "post_job_result",
        side_effect=lambda result: reported_results.append(JobResult.from_value(result)) or {"status": "success"},
    ):
        with caplog.at_level("INFO"):
            result = worker.run_once()

    assert result["status"] == "failed"
    assert len(reported_results) == 1
    assert reported_results[0].status == "failed"
    assert "unsupported status 'success'" in reported_results[0].error.lower()
    assert "Reported ADS job ads-job:test-success-envelope as failed" in caplog.text


def test_ads_worker_run_once_fails_none_result_without_fake_completion(caplog):
    """
    Exercise the test_ads_worker_run_once_fails_none_result_without_fake_completion
    regression scenario.
    """
    worker = ADSWorkerAgent(
        dispatcher_address="http://127.0.0.1:9999",
        capabilities=["news"],
        job_capabilities=[NoneReturningJobCap()],
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:test-none-result",
            "job_type": "collect",
            "status": "claimed",
            "required_capability": "news",
            "payload": {},
            "priority": 100,
            "premium": False,
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "attempts": 1,
            "max_attempts": 3,
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:01+00:00",
        }
    )
    reported_results: list[JobResult] = []

    with patch.object(worker, "register_capabilities", return_value={"status": "success"}), patch.object(
        worker,
        "request_job",
        return_value={"status": "success", "job": job},
    ), patch.object(
        worker,
        "post_job_result",
        side_effect=lambda result: reported_results.append(JobResult.from_value(result)) or {"status": "success"},
    ):
        with caplog.at_level("INFO"):
            result = worker.run_once()

    assert result["status"] == "failed"
    assert len(reported_results) == 1
    assert reported_results[0].status == "failed"
    assert "returned none" in reported_results[0].error.lower()
    assert "Reported ADS job ads-job:test-none-result as failed" in caplog.text


def test_ads_worker_run_once_reports_stopped_when_boss_requests_stop(caplog):
    """
    Exercise the test_ads_worker_run_once_reports_stopped_when_boss_requests_stop
    regression scenario.
    """
    worker = ADSWorkerAgent(
        dispatcher_address="http://127.0.0.1:9999",
        capabilities=["news"],
        job_capabilities=[StopCheckingJobCap()],
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:test-stop",
            "job_type": "collect",
            "status": "claimed",
            "required_capability": "news",
            "symbols": ["AAPL"],
            "payload": {"symbol": "AAPL"},
            "priority": 100,
            "premium": False,
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "attempts": 1,
            "max_attempts": 3,
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:01+00:00",
        }
    )
    reported_results: list[JobResult] = []

    with patch.object(worker, "register_capabilities", return_value={"status": "success"}), patch.object(
        worker,
        "request_job",
        return_value={"status": "success", "job": job},
    ), patch.object(
        worker,
        "post_job_result",
        side_effect=lambda result: reported_results.append(JobResult.from_value(result)) or {"status": "success"},
    ), patch.object(
        worker,
        "_fetch_job_control_row",
        return_value={"id": job.id, "status": "stopping", "metadata": {"boss_control": {"action": "stop"}}},
    ):
        with caplog.at_level("INFO"):
            result = worker.run_once()

    assert result["status"] == "stopped"
    assert len(reported_results) == 1
    assert reported_results[0].status == "stopped"
    assert reported_results[0].result_summary["stopped"] is True
    assert "Reported ADS job ads-job:test-stop as stopped" in caplog.text


def test_ads_worker_run_once_fails_exception_after_max_attempts(caplog):
    """
    Exercise the test_ads_worker_run_once_fails_exception_after_max_attempts
    regression scenario.
    """
    worker = ADSWorkerAgent(
        dispatcher_address="http://127.0.0.1:9999",
        capabilities=["yfinance eod"],
        job_capabilities=[FailingJobCap()],
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:test-final-failure",
            "job_type": "collect",
            "status": "claimed",
            "required_capability": "yfinance eod",
            "symbols": ["MSFT"],
            "payload": {"symbol": "MSFT"},
            "priority": 100,
            "premium": False,
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "attempts": 3,
            "max_attempts": 3,
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:01+00:00",
        }
    )
    reported_results: list[JobResult] = []

    with patch.object(worker, "register_capabilities", return_value={"status": "success"}), patch.object(
        worker,
        "request_job",
        return_value={"status": "success", "job": job},
    ), patch.object(
        worker,
        "post_job_result",
        side_effect=lambda result: reported_results.append(JobResult.from_value(result)) or {"status": "success"},
    ):
        with caplog.at_level("INFO"):
            result = worker.run_once()

    assert result["status"] == "failed"
    assert len(reported_results) == 1
    assert reported_results[0].status == "failed"
    assert reported_results[0].result_summary["retryable"] is False
    assert "Reported ADS job ads-job:test-final-failure as failed" in caplog.text


def test_ads_worker_app_startup_polls_for_jobs_periodically():
    """
    Exercise the test_ads_worker_app_startup_polls_for_jobs_periodically regression
    scenario.
    """
    worker = ADSWorkerAgent(
        dispatcher_address="http://127.0.0.1:9999",
        poll_interval_sec=0.1,
        capabilities=["yfinance eod"],
        job_capabilities=[AutoPollingYFinanceJobCap(name="YFinance EOD")],
    )
    poll_counts = {"request_job": 0}

    with patch.object(worker, "register_capabilities", return_value={"status": "success"}), patch.object(
        worker,
        "request_job",
        side_effect=lambda: poll_counts.__setitem__("request_job", poll_counts["request_job"] + 1) or {"status": "success", "job": None},
    ):
        with TestClient(worker.app):
            time.sleep(0.35)

    assert poll_counts["request_job"] >= 2


def test_ads_worker_polling_can_start_before_dispatcher_is_discovered():
    """
    Exercise the test_ads_worker_polling_can_start_before_dispatcher_is_discovered
    regression scenario.
    """
    worker = ADSWorkerAgent(
        plaza_url="http://127.0.0.1:8011",
        poll_interval_sec=0.1,
        capabilities=["yfinance eod"],
        job_capabilities=[AutoPollingYFinanceJobCap(name="YFinance EOD")],
    )
    run_counts = {"run_once": 0}

    try:
        with patch.object(
            worker,
            "run_once",
            side_effect=lambda: run_counts.__setitem__("run_once", run_counts["run_once"] + 1) or {"status": "idle"},
        ):
            assert worker._start_polling_thread() is True
            time.sleep(0.35)
    finally:
        worker._stop_polling_thread(join_timeout=1.0)

    assert run_counts["run_once"] >= 2


def test_ads_worker_discovers_dispatcher_via_plaza_search():
    """
    Exercise the test_ads_worker_discovers_dispatcher_via_plaza_search regression
    scenario.
    """
    worker = ADSWorkerAgent(
        plaza_url="http://127.0.0.1:8011",
        capabilities=["yfinance eod"],
        job_capabilities=[AutoPollingYFinanceJobCap(name="YFinance EOD")],
        auto_register=False,
    )
    dispatcher_entry = {
        "agent_id": "ads-dispatcher-1",
        "name": "ADSDispatcher",
        "last_active": 1711650000.0,
        "card": {
            "address": "http://127.0.0.1:9070",
            "role": "dispatcher",
            "tags": ["ads", "dispatcher"],
            "practices": [
                {"id": "ads-get-job"},
                {"id": "ads-register-worker"},
                {"id": "ads-post-job-result"},
            ],
        },
    }
    practice_calls: list[tuple[str, str]] = []
    search_calls: list[dict[str, object]] = []

    def fake_search(**kwargs):
        """Handle fake search."""
        search_calls.append(dict(kwargs))
        return [dispatcher_entry]

    def fake_use_practice(practice_id, content=None, pit_address=None, **kwargs):
        """Handle fake use practice."""
        practice_calls.append((practice_id, pit_address))
        if practice_id == "ads-get-job":
            return {"status": "success", "job": None}
        return {"status": "success"}

    with patch.object(worker, "search", side_effect=fake_search), patch.object(
        worker,
        "UsePractice",
        side_effect=fake_use_practice,
    ):
        register_result = worker.register_capabilities()
        poll_result = worker.request_job()

    assert register_result["status"] == "success"
    assert poll_result["status"] == "success"
    assert poll_result["job"] is None
    assert worker.dispatcher_address == "http://127.0.0.1:9070"
    assert search_calls
    assert all(call.get("party") == "ADS" for call in search_calls)
    assert practice_calls == [
        ("ads-register-worker", "http://127.0.0.1:9070"),
        ("ads-get-job", "http://127.0.0.1:9070"),
    ]


def test_ads_worker_waits_for_dispatcher_discovery_without_raising():
    """
    Exercise the test_ads_worker_waits_for_dispatcher_discovery_without_raising
    regression scenario.
    """
    worker = ADSWorkerAgent(
        plaza_url="http://127.0.0.1:8011",
        capabilities=["yfinance eod"],
        job_capabilities=[AutoPollingYFinanceJobCap(name="YFinance EOD")],
        auto_register=False,
    )

    with patch.object(worker, "search", return_value=[]):
        register_result = worker.register_capabilities()
        poll_result = worker.request_job()

    assert register_result["status"] == "pending"
    assert register_result["worker_id"] == worker._worker_identity()
    assert poll_result == {
        "status": "pending",
        "job": None,
        "error": "ADS dispatcher is not available yet.",
    }


def test_ads_worker_uses_unique_runtime_identity_and_reports_progress_metadata():
    """
    Exercise the
    test_ads_worker_uses_unique_runtime_identity_and_reports_progress_metadata
    regression scenario.
    """
    worker_a = ADSWorkerAgent(
        dispatcher_address="http://127.0.0.1:9070",
        capabilities=["news"],
        auto_register=False,
    )
    worker_b = ADSWorkerAgent(
        dispatcher_address="http://127.0.0.1:9070",
        capabilities=["news"],
        auto_register=False,
    )
    practice_calls: list[tuple[str, dict[str, object], str]] = []

    def fake_use_practice(practice_id, content=None, pit_address=None, **kwargs):
        """Handle fake use practice."""
        practice_calls.append((practice_id, dict(content or {}), str(pit_address or "")))
        return {"status": "success", "worker_id": dict(content or {}).get("worker_id", "")}

    worker_a._set_active_job({"id": "ads-job:progress", "required_capability": "news", "symbols": ["AAPL"]})
    worker_a.update_progress(percent=40, message="Downloading payload", extra={"stage": "fetch"})
    with patch.object(worker_a, "UsePractice", side_effect=fake_use_practice):
        register_result = worker_a.register_capabilities()

    assert worker_a._worker_identity() != worker_b._worker_identity()
    assert worker_a.agent_card["meta"]["reuse_plaza_identity"] is False
    assert register_result["status"] == "success"
    assert practice_calls[0][0] == "ads-register-worker"
    payload = practice_calls[0][1]
    assert payload["worker_id"] == worker_a._worker_identity()
    assert payload["status"] == "working"
    assert payload["metadata"]["heartbeat"]["active_job"]["id"] == "ads-job:progress"
    assert payload["metadata"]["heartbeat"]["progress"]["message"] == "Downloading payload"
    assert payload["metadata"]["heartbeat"]["progress"]["extra"]["stage"] == "fetch"
    assert payload["metadata"]["environment"]["hostname"]


def test_ads_worker_reads_yfinance_request_cooldown_from_config_and_defaults_to_120():
    """
    Exercise the
    test_ads_worker_reads_yfinance_request_cooldown_from_config_and_defaults_to_120
    regression scenario.
    """
    default_worker = ADSWorkerAgent(
        config={
            "name": "ADSWorker",
            "ads": {
                "capabilities": ["yfinance eod"],
            },
        },
        auto_register=False,
    )
    custom_worker = ADSWorkerAgent(
        config={
            "name": "ADSWorker",
            "ads": {
                "capabilities": ["yfinance eod"],
                "yfinance_request_cooldown_sec": 45,
            },
        },
        auto_register=False,
    )

    assert default_worker.yfinance_request_cooldown_sec == 120.0
    assert custom_worker.yfinance_request_cooldown_sec == 45.0


def test_ads_worker_hides_yfinance_capabilities_during_cooldown():
    """
    Exercise the test_ads_worker_hides_yfinance_capabilities_during_cooldown
    regression scenario.
    """
    worker = ADSWorkerAgent(
        dispatcher_address="http://127.0.0.1:9999",
        capabilities=["yfinance eod", "yfinance us market eod", "twse market eod"],
        yfinance_request_cooldown_sec=120,
        auto_register=False,
    )
    practice_calls: list[tuple[str, dict[str, object], str]] = []

    def fake_use_practice(practice_id, content=None, pit_address=None, **kwargs):
        """Handle fake use practice."""
        practice_calls.append((practice_id, dict(content or {}), str(pit_address or "")))
        if practice_id == "ads-get-job":
            return {"status": "success", "job": None}
        return {"status": "success"}

    worker.trigger_yfinance_cooldown(reason="YFinance rate limit")
    with patch.object(worker, "UsePractice", side_effect=fake_use_practice):
        register_result = worker.register_capabilities()
        poll_result = worker.request_job()

    assert worker.yfinance_cooldown_active() is True
    assert register_result["status"] == "success"
    assert poll_result["status"] == "success"
    assert [call[1]["capabilities"] for call in practice_calls] == [
        ["twse market eod"],
        ["twse market eod"],
    ]


def test_ads_example_worker_config_covers_advertised_capabilities():
    """
    Exercise the test_ads_example_worker_config_covers_advertised_capabilities
    regression scenario.
    """
    config_path = Path(__file__).resolve().parents[1] / "configs" / "worker.agent"
    config = read_ads_config(config_path)
    ads_config = config.get("ads") or {}

    advertised_capabilities = set(normalize_capabilities(ads_config.get("capabilities") or []))
    job_capabilities = build_job_cap_map(ads_config.get("job_capabilities") or [])

    assert set(job_capabilities.keys()) == advertised_capabilities
    assert isinstance(job_capabilities["daily job archive"], DailyJobArchiveJobCap)
    assert isinstance(job_capabilities["us listed sec to security master"], USListedSecJobCap)
    assert isinstance(job_capabilities["us filing bulk"], USFilingBulkJobCap)
    assert isinstance(job_capabilities["us filing mapping"], USFilingMappingJobCap)
    assert isinstance(job_capabilities["yfinance eod"], YFinanceEODJobCap)
    assert isinstance(job_capabilities["yfinance us market eod"], YFinanceUSMarketEODJobCap)
    assert isinstance(job_capabilities["twse market eod"], TWSEMarketEODJobCap)
    assert isinstance(job_capabilities["rss news"], RSSNewsJobCap)
    assert ads_config.get("yfinance_request_cooldown_sec") == 600


def test_yfinance_rate_limit_starts_worker_cooldown():
    """
    Exercise the test_yfinance_rate_limit_starts_worker_cooldown regression
    scenario.
    """
    class RateLimitedTicker:
        """Represent a rate limited ticker."""
        def history(self, **kwargs):
            """Return the history."""
            raise RuntimeError("Too Many Requests. Rate limited. Try after a while.")

    capability = YFinanceEODJobCap(
        ticker_factory=lambda symbol: RateLimitedTicker(),
        today_fn=lambda: date(2026, 3, 28),
    )
    worker = ADSWorkerAgent(
        capabilities=["yfinance eod", "yfinance us market eod", "twse market eod"],
        job_capabilities=[capability],
        yfinance_request_cooldown_sec=120,
        auto_register=False,
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:yf-rate-limit",
            "required_capability": "yfinance eod",
            "symbols": ["MSFT"],
            "payload": {"symbol": "MSFT"},
            "attempts": 0,
            "max_attempts": 3,
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:00+00:00",
        }
    )
    reported_results: list[JobResult] = []

    with patch.object(worker, "register_capabilities", return_value={"status": "success"}), patch.object(
        worker,
        "request_job",
        return_value={"status": "success", "job": job},
    ), patch.object(
        worker,
        "post_job_result",
        side_effect=lambda result: reported_results.append(JobResult.from_value(result)) or {"status": "success"},
    ):
        result = worker.run_once()

    assert result["status"] == "retry"
    assert len(reported_results) == 1
    assert reported_results[0].status == "retry"
    assert "Too Many Requests" in reported_results[0].error
    assert worker.yfinance_cooldown_active() is True
    assert worker.advertised_capabilities() == ["twse market eod"]


def test_yfinance_timeout_starts_worker_cooldown():
    """Exercise the test_yfinance_timeout_starts_worker_cooldown regression scenario."""
    class TimeoutTicker:
        """Represent a timeout ticker."""
        def history(self, **kwargs):
            """Return the history."""
            raise RuntimeError(
                "Failed to perform, curl: (28) Operation timed out after 10002 milliseconds with 0 bytes received."
            )

    capability = YFinanceEODJobCap(
        ticker_factory=lambda symbol: TimeoutTicker(),
        today_fn=lambda: date(2026, 3, 30),
    )
    worker = ADSWorkerAgent(
        capabilities=["yfinance eod", "yfinance us market eod", "twse market eod"],
        job_capabilities=[capability],
        yfinance_request_cooldown_sec=120,
        auto_register=False,
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:yf-timeout",
            "required_capability": "yfinance eod",
            "symbols": ["HYFM"],
            "payload": {"symbol": "HYFM"},
            "attempts": 0,
            "max_attempts": 3,
            "scheduled_for": "2026-03-30T10:00:00+00:00",
            "created_at": "2026-03-30T10:00:00+00:00",
            "updated_at": "2026-03-30T10:00:00+00:00",
        }
    )
    reported_results: list[JobResult] = []

    with patch.object(worker, "register_capabilities", return_value={"status": "success"}), patch.object(
        worker,
        "request_job",
        return_value={"status": "success", "job": job},
    ), patch.object(
        worker,
        "post_job_result",
        side_effect=lambda result: reported_results.append(JobResult.from_value(result)) or {"status": "success"},
    ):
        result = worker.run_once()

    assert result["status"] == "retry"
    assert len(reported_results) == 1
    assert reported_results[0].status == "retry"
    assert "curl: (28)" in reported_results[0].error
    assert worker.yfinance_cooldown_active() is True
    assert worker.advertised_capabilities() == ["twse market eod"]


def test_ads_daily_job_archive_job_cap_moves_completed_jobs_to_archive(tmp_path):
    """
    Exercise the daily ADS archive-sweep job cap regression scenario.
    """
    pool = SQLitePool("ads_archive_pool", "ADS archive jobcap pool", str(tmp_path / "ads.sqlite"))
    ensure_ads_tables(pool)

    completed_job_id = "ads-job:completed-archive-me"
    assert pool._Insert(
        TABLE_JOBS,
        {
            "id": completed_job_id,
            "status": "completed",
            "required_capability": "rss news",
            "payload": {"feed": "sec"},
            "priority": 100,
            "completed_at": "2026-04-13T01:59:00+00:00",
            "created_at": "2026-04-13T01:55:00+00:00",
            "updated_at": "2026-04-13T01:59:00+00:00",
        },
    )

    cap = DailyJobArchiveJobCap()
    cap.bind_worker(type("WorkerStub", (), {"pool": pool})())

    result = cap.finish(
        JobDetail(
            id="ads-job:daily-archive-run",
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


def test_ads_example_worker_config_omits_dispatcher_address():
    """
    Exercise the test_ads_example_worker_config_omits_dispatcher_address regression
    scenario.
    """
    config_path = Path(__file__).resolve().parents[1] / "configs" / "worker.agent"
    config = read_ads_config(config_path)
    ads_config = config.get("ads") or {}

    assert "dispatcher_address" not in ads_config


def test_ads_example_configs_declare_ads_party():
    """Exercise the test_ads_example_configs_declare_ads_party regression scenario."""
    configs_dir = Path(__file__).resolve().parents[1] / "configs"
    for config_name in ("boss.agent", "dispatcher.agent", "worker.agent", "pulser.agent"):
        config = read_ads_config(configs_dir / config_name)
        assert config["party"] == "ADS"


def test_ads_example_configs_default_to_postgres_pool():
    """
    Exercise the test_ads_example_configs_default_to_postgres_pool regression
    scenario.
    """
    configs_dir = Path(__file__).resolve().parents[1] / "configs"
    for config_name in ("boss.agent", "dispatcher.agent", "worker.agent", "pulser.agent"):
        config = read_ads_config(configs_dir / config_name)
        pools = config.get("pools") or []
        assert pools
        assert pools[0]["type"] == "PostgresPool"


def test_ads_example_configs_keep_job_caps_in_sync():
    """
    Exercise the test_ads_example_configs_keep_job_caps_in_sync regression scenario.
    """
    configs_dir = Path(__file__).resolve().parents[1] / "configs"
    boss_config = read_ads_config(configs_dir / "boss.agent")
    dispatcher_config = read_ads_config(configs_dir / "dispatcher.agent")
    worker_config = read_ads_config(configs_dir / "worker.agent")

    boss_job_caps = {
        str(entry.get("name") or "").strip().lower()
        for entry in (boss_config.get("ads") or {}).get("job_capabilities") or []
        if isinstance(entry, dict) and str(entry.get("name") or "").strip()
    }
    dispatcher_job_caps = {
        str(entry.get("name") or "").strip().lower()
        for entry in (dispatcher_config.get("ads") or {}).get("job_capabilities") or []
        if isinstance(entry, dict) and str(entry.get("name") or "").strip()
    }
    worker_job_caps = set(
        build_job_cap_map((worker_config.get("ads") or {}).get("job_capabilities") or []).keys()
    )

    assert boss_job_caps == {
        "daily job archive",
        "us listed sec to security master",
        "us filing bulk",
        "us filing mapping",
        "yfinance eod",
        "yfinance us market eod",
        "twse market eod",
        "rss news",
    }
    assert dispatcher_job_caps == boss_job_caps
    assert worker_job_caps.issuperset(boss_job_caps)


def test_data_pipeline_demo_uses_live_job_caps():
    """
    Exercise the test_data_pipeline_demo_uses_live_job_caps regression scenario.
    """
    demo_dir = Path(__file__).resolve().parents[2] / "demos" / "data-pipeline"
    boss_config = read_ads_config(demo_dir / "boss.agent")
    dispatcher_config = read_ads_config(demo_dir / "dispatcher.agent")
    worker_config = read_ads_config(demo_dir / "worker.agent")

    demo_job_caps = {
        "security_master",
        "daily_price",
        "fundamentals",
        "financial_statements",
        "news",
    }
    boss_job_caps = {
        str(entry.get("name") or "").strip().lower()
        for entry in (boss_config.get("ads") or {}).get("job_capabilities") or []
        if isinstance(entry, dict) and str(entry.get("name") or "").strip()
    }
    dispatcher_job_caps = {
        str(entry.get("name") or "").strip().lower()
        for entry in (dispatcher_config.get("ads") or {}).get("job_capabilities") or []
        if isinstance(entry, dict) and str(entry.get("name") or "").strip()
    }
    worker_job_caps = build_job_cap_map((worker_config.get("ads") or {}).get("job_capabilities") or [])

    assert boss_job_caps == demo_job_caps
    assert dispatcher_job_caps == demo_job_caps
    assert worker_config["pools"][0]["db_path"] == "demos/data-pipeline/storage/ads_dispatcher.sqlite"
    assert isinstance(worker_job_caps["security_master"], USListedSecJobCap)
    assert isinstance(worker_job_caps["daily_price"], YFinanceEODJobCap)
    assert isinstance(worker_job_caps["fundamentals"], LiveSECFundamentalsJobCap)
    assert isinstance(worker_job_caps["financial_statements"], LiveSECFinancialStatementsJobCap)
    assert isinstance(worker_job_caps["news"], RSSNewsJobCap)


def test_live_sec_financial_statements_demo_job_cap_promotes_statement_rows():
    """
    Exercise the
    test_live_sec_financial_statements_demo_job_cap_promotes_statement_rows
    regression scenario.
    """
    bulk_cap = StaticJobCap(
        "bulk",
        JobResult(
            status="completed",
            raw_payload={"dataset": "sec_bulk"},
            result_summary={"cache": {"companyfacts": {"cache_status": "hit"}}},
        ),
    )
    mapping_cap = StaticJobCap(
        "mapping",
        JobResult(
            status="completed",
            target_table=TABLE_FUNDAMENTALS,
            collected_rows=[
                {
                    "symbol": "AAPL",
                    "as_of_date": "2026-03-28",
                    "provider": "sec_edgar",
                }
            ],
            additional_targets=[
                {
                    "table_name": TABLE_FINANCIAL_STATEMENTS,
                    "rows": [
                        {
                            "symbol": "AAPL",
                            "statement_type": "income_statement",
                            "period_end": "2025-12-31",
                            "provider": "sec_edgar",
                        }
                    ],
                }
            ],
            raw_payload={"dataset": "sec_mapping"},
            result_summary={"rows": 2},
        ),
    )
    capability = LiveSECFinancialStatementsJobCap(
        bulk_job_cap=bulk_cap,
        mapping_job_cap=mapping_cap,
    )

    result = capability.finish(
        JobDetail(
            id="ads-job:test-financial-statements",
            payload={"symbol": "AAPL"},
        )
    )

    assert bulk_cap.calls == 1
    assert mapping_cap.calls == 1
    assert result.target_table == TABLE_FINANCIAL_STATEMENTS
    assert result.collected_rows == [
        {
            "symbol": "AAPL",
            "statement_type": "income_statement",
            "period_end": "2025-12-31",
            "provider": "sec_edgar",
        }
    ]
    assert result.additional_targets == [
        {
            "table_name": TABLE_FUNDAMENTALS,
            "rows": [
                {
                    "symbol": "AAPL",
                    "as_of_date": "2026-03-28",
                    "provider": "sec_edgar",
                }
            ],
        }
    ]
    assert result.raw_payload == {
        "bulk_refresh": {"dataset": "sec_bulk"},
        "mapping": {"dataset": "sec_mapping"},
    }
    assert result.result_summary == {
        "rows": 2,
        "bulk_refresh": {"cache": {"companyfacts": {"cache_status": "hit"}}},
    }


def test_build_job_cap_can_instantiate_job_cap_type():
    """
    Exercise the test_build_job_cap_can_instantiate_job_cap_type regression
    scenario.
    """
    capability = build_job_cap(
        {
            "name": "IEX EOD",
            "type": "ads.iex:IEXEODJobCap",
            "token": "demo-token",
        }
    )

    assert isinstance(capability, IEXEODJobCap)
    assert capability.name == "iex eod"


def test_build_job_cap_map_skips_iex_job_cap_when_token_is_missing():
    """
    Exercise the test_build_job_cap_map_skips_iex_job_cap_when_token_is_missing
    regression scenario.
    """
    with patch.dict(os.environ, {}, clear=True), patch.object(
        IEXEODJobCap,
        "DEFAULT_TOKEN_ENV_CANDIDATES",
        ("ADS_TEST_MISSING_IEX_TOKEN",),
    ):
        capability_map = build_job_cap_map(
            [
                {
                    "name": "IEX EOD",
                    "type": "ads.iex:IEXEODJobCap",
                }
            ]
        )

    assert capability_map == {}


def test_build_job_cap_can_instantiate_yfinance_job_cap_type():
    """
    Exercise the test_build_job_cap_can_instantiate_yfinance_job_cap_type regression
    scenario.
    """
    capability = build_job_cap(
        {
            "name": "YFinance EOD",
            "type": "ads.yfinance:YFinanceEODJobCap",
        }
    )

    assert isinstance(capability, YFinanceEODJobCap)
    assert capability.name == "yfinance eod"


def test_build_job_cap_can_instantiate_live_demo_sec_job_cap_types():
    """
    Exercise the
    test_build_job_cap_can_instantiate_live_demo_sec_job_cap_types regression
    scenario.
    """
    fundamentals_cap = build_job_cap(
        {
            "name": "fundamentals",
            "type": "ads.examples.live_data_pipeline:LiveSECFundamentalsJobCap",
        }
    )
    statements_cap = build_job_cap(
        {
            "name": "financial_statements",
            "type": "ads.examples.live_data_pipeline:LiveSECFinancialStatementsJobCap",
        }
    )

    assert isinstance(fundamentals_cap, LiveSECFundamentalsJobCap)
    assert isinstance(statements_cap, LiveSECFinancialStatementsJobCap)
    assert fundamentals_cap.name == "fundamentals"
    assert statements_cap.name == "financial_statements"


def test_build_job_cap_map_skips_yfinance_job_cap_when_module_is_missing():
    """
    Exercise the
    test_build_job_cap_map_skips_yfinance_job_cap_when_module_is_missing regression
    scenario.
    """
    with patch("ads.jobcap.importlib_util.find_spec", return_value=None):
        capability_map = build_job_cap_map(
            [
                {
                    "name": "YFinance EOD",
                    "type": "ads.yfinance:YFinanceEODJobCap",
                }
            ]
        )

    assert capability_map == {}


def test_build_job_cap_map_skips_disabled_entries():
    """
    Exercise the test_build_job_cap_map_skips_disabled_entries regression scenario.
    """
    capability_map = build_job_cap_map(
        [
            {
                "name": "Disabled Mock Daily Price",
                "callable": "ads.examples.job_caps:mock_daily_price_cap",
                "disabled": True,
            },
            {
                "name": "RSS News",
                "type": "ads.rss_news:RSSNewsJobCap",
            },
        ]
    )

    assert set(capability_map.keys()) == {"rss news"}


def test_build_job_cap_can_instantiate_yfinance_us_market_job_cap_type():
    """
    Exercise the test_build_job_cap_can_instantiate_yfinance_us_market_job_cap_type
    regression scenario.
    """
    capability = build_job_cap(
        {
            "name": "YFinance US Market EOD",
            "type": "ads.yfinance:YFinanceUSMarketEODJobCap",
        }
    )

    assert isinstance(capability, YFinanceUSMarketEODJobCap)
    assert capability.name == "yfinance us market eod"


def test_build_job_cap_can_instantiate_twse_job_cap_type():
    """
    Exercise the test_build_job_cap_can_instantiate_twse_job_cap_type regression
    scenario.
    """
    capability = build_job_cap(
        {
            "name": "TWSE Market EOD",
            "type": "ads.twse:TWSEMarketEODJobCap",
        }
    )

    assert isinstance(capability, TWSEMarketEODJobCap)
    assert capability.name == "twse market eod"


def test_build_job_cap_can_instantiate_us_listed_job_cap_type():
    """
    Exercise the test_build_job_cap_can_instantiate_us_listed_job_cap_type
    regression scenario.
    """
    capability = build_job_cap(
        {
            "name": "US Listed Sec to security master",
            "type": "ads.us_listed:USListedSecJobCap",
        }
    )

    assert isinstance(capability, USListedSecJobCap)
    assert capability.name == "us listed sec to security master"


def test_build_job_cap_can_instantiate_us_filing_bulk_job_cap_type():
    """
    Exercise the test_build_job_cap_can_instantiate_us_filing_bulk_job_cap_type
    regression scenario.
    """
    capability = build_job_cap(
        {
            "name": "US Filing Bulk",
            "type": "ads.sec:USFilingBulkJobCap",
        }
    )

    assert isinstance(capability, USFilingBulkJobCap)
    assert capability.name == "us filing bulk"


def test_build_job_cap_can_instantiate_us_filing_mapping_job_cap_type():
    """
    Exercise the test_build_job_cap_can_instantiate_us_filing_mapping_job_cap_type
    regression scenario.
    """
    capability = build_job_cap(
        {
            "name": "US Filing Mapping",
            "type": "ads.sec:USFilingMappingJobCap",
        }
    )

    assert isinstance(capability, USFilingMappingJobCap)
    assert capability.name == "us filing mapping"


def test_build_job_cap_can_instantiate_rss_news_job_cap_type():
    """
    Exercise the test_build_job_cap_can_instantiate_rss_news_job_cap_type regression
    scenario.
    """
    capability = build_job_cap(
        {
            "name": "RSS News",
            "type": "ads.rss_news:RSSNewsJobCap",
        }
    )

    assert isinstance(capability, RSSNewsJobCap)
    assert capability.name == "rss news"


def test_worker_omits_unavailable_job_caps_from_advertisement():
    """
    Exercise the test_worker_omits_unavailable_job_caps_from_advertisement
    regression scenario.
    """
    available_capability = RecordingJobCap([], name="Available Cap")
    unavailable_capability = UnavailableJobCap(name="Unavailable Cap", reason="missing dependency")

    worker = ADSWorkerAgent(
        capabilities=["News", "Available Cap", "Unavailable Cap"],
        job_capabilities=[available_capability, unavailable_capability],
        auto_register=False,
    )

    assert worker.capabilities == ["news", "available cap"]
    assert set(worker.job_capabilities.keys()) == {"available cap"}
    assert worker.unavailable_job_capabilities == {"unavailable cap": "missing dependency"}
    assert worker.agent_card["meta"]["capabilities"] == ["news", "available cap"]
    assert worker.agent_card["meta"]["job_capabilities"] == [available_capability.to_metadata()]


def test_worker_omits_disabled_job_caps_from_advertisement():
    """
    Exercise the test_worker_omits_disabled_job_caps_from_advertisement regression
    scenario.
    """
    worker = ADSWorkerAgent(
        capabilities=["News", "Disabled Cap"],
        job_capabilities=[
            {
                "name": "Disabled Cap",
                "callable": "ads.examples.job_caps:mock_daily_price_cap",
                "disabled": "true",
            },
            {
                "name": "News",
                "callable": "ads.examples.job_caps:mock_news_cap",
            },
        ],
        auto_register=False,
    )

    assert worker.capabilities == ["news"]
    assert set(worker.job_capabilities.keys()) == {"news"}
    assert worker.unavailable_job_capabilities == {"disabled cap": "disabled by config."}
    assert worker.agent_card["meta"]["capabilities"] == ["news"]
    assert worker.agent_card["meta"]["job_capabilities"] == [worker.job_capabilities["news"].to_metadata()]


def test_resolve_daily_price_start_date_backfills_three_years_when_no_saved_rows_exist():
    """
    Exercise the test_resolve_daily_price_start_date_backfills_three_years_when_no_s
    aved_rows_exist regression scenario.
    """
    assert resolve_daily_price_start_date(None, None, date(2026, 3, 28)) == date(2023, 3, 28)


def test_subtract_years_clamps_leap_day_to_february_28():
    """
    Exercise the test_subtract_years_clamps_leap_day_to_february_28 regression
    scenario.
    """
    assert subtract_years(date(2024, 2, 29), 3) == date(2021, 2, 28)


def test_rss_news_job_cap_fetches_multiple_feeds_into_ads_news():
    """
    Exercise the test_rss_news_job_cap_fetches_multiple_feeds_into_ads_news
    regression scenario.
    """
    feed_payloads = {
        "https://www.sec.gov/news/pressreleases.rss": """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>SEC Press Releases</title>
    <item>
      <title>SEC Announces Rule Update</title>
      <description><![CDATA[SEC summary line.]]></description>
      <link>https://www.sec.gov/news/press-release/2026-1</link>
      <guid>sec-2026-1</guid>
      <pubDate>Fri, 27 Mar 2026 14:30:00 GMT</pubDate>
    </item>
  </channel>
</rss>""",
        "https://www.cftc.gov/RSS/RSSGP/rssgp.xml": """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>CFTC General Press Releases</title>
    <item>
      <title>CFTC Issues Market Notice</title>
      <description>CFTC summary line.</description>
      <link>https://www.cftc.gov/PressRoom/PressReleases/9000-26</link>
      <guid>cftc-9000-26</guid>
      <pubDate>Thu, 26 Mar 2026 13:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>""",
        "https://www.bls.gov/feed/bls_latest.rss": """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>BLS Latest Numbers</title>
    <item>
      <title>BLS Updates Employment Data</title>
      <description><![CDATA[<p>BLS summary line.</p>]]></description>
      <link>https://www.bls.gov/news.release/empsit.nr0.htm</link>
      <guid>bls-empsit-2026-03</guid>
      <pubDate>Wed, 25 Mar 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>""",
    }

    class FakeResponse:
        """Response model for fake payloads."""
        def __init__(self, text: str):
            """Initialize the fake response."""
            self.text = text

        def raise_for_status(self):
            """Return the raise for the status."""
            return None

    def fake_request_get(url, timeout=None, headers=None):
        """Handle fake request get."""
        assert timeout == 15.0
        assert headers["User-Agent"] == "FinMAS RSSNewsJobCap/1.0"
        return FakeResponse(feed_payloads[url])

    capability = RSSNewsJobCap(request_get=fake_request_get, timeout_sec=15.0)
    job = JobDetail(
        id="ads-job:rss-1",
        required_capability="RSS News",
        payload={},
    )

    result = capability.finish(job)

    assert result.target_table == TABLE_NEWS
    assert result.result_summary["rows"] == 3
    assert result.result_summary["successful_feeds"] == 3
    assert result.result_summary["failed_feeds"] == []
    assert [row["source"] for row in result.collected_rows] == ["SEC", "CFTC", "BLS"]
    assert result.collected_rows[0]["headline"] == "SEC Announces Rule Update"
    assert result.collected_rows[1]["url"] == "https://www.cftc.gov/PressRoom/PressReleases/9000-26"
    assert result.collected_rows[2]["summary"] == "BLS summary line."
    assert all(str(row["id"]).startswith("ads-news:") for row in result.collected_rows)
    assert result.raw_payload["feeds"][0]["feed_title"] == "SEC Press Releases"
    assert result.raw_payload["feeds"][2]["entries"][0]["guid"] == "bls-empsit-2026-03"


def test_iex_eod_job_cap_fetches_from_latest_stored_date_and_persists_results(tmp_path):
    """
    Exercise the
    test_iex_eod_job_cap_fetches_from_latest_stored_date_and_persists_results
    regression scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
    worker_db = tmp_path / "worker.sqlite"
    requested_dates = []

    dispatcher_config.write_text(
        f"""
{{
  "name": "ADSDispatcher",
  "host": "127.0.0.1",
  "port": 9072,
  "type": "ads.agents.ADSDispatcherAgent",
  "pools": [
    {{
      "type": "SQLitePool",
      "name": "ads_dispatch_pool",
      "description": "dispatch",
      "db_path": "{dispatcher_db}"
    }}
  ]
}}
""".strip(),
        encoding="utf-8",
    )

    def fake_request_get(url, params=None, timeout=None):
        """Handle fake request get."""
        requested_dates.append(url.rsplit("/", 1)[-1])
        payload_by_date = {
            "20260327": [
                {
                    "date": "2026-03-27",
                    "open": 400.0,
                    "high": 405.0,
                    "low": 398.0,
                    "close": 402.0,
                    "volume": 1000,
                    "label": "Mar 27, 26",
                }
            ],
            "20260328": [
                {
                    "date": "2026-03-28",
                    "open": 403.0,
                    "high": 407.0,
                    "low": 401.0,
                    "close": 406.0,
                    "volume": 1200,
                    "label": "Mar 28, 26",
                }
            ],
        }
        date_key = url.rsplit("/", 1)[-1]
        return FakeIEXResponse(
            payload_by_date.get(date_key, []),
            f"{url}?chartByDay=true",
        )

    dispatcher, dispatcher_server, dispatcher_thread = start_agent_thread(str(dispatcher_config))
    worker_pool = SQLitePool("ads_worker_pool", "ADS worker state", str(worker_db))
    capability = IEXEODJobCap(
        token="demo-token",
        request_get=fake_request_get,
        today_fn=lambda: date(2026, 3, 28),
    )
    worker = ADSWorkerAgent(
        pool=worker_pool,
        dispatcher_address="http://127.0.0.1:9072",
        capabilities=["daily_price"],
        job_capabilities=[capability],
    )

    try:
        seed_security_master_symbol(dispatcher.pool, "MSFT", provider="iex", name="Microsoft")
        dispatcher.pool._Insert(
            TABLE_DAILY_PRICE,
            {
                "id": build_daily_price_id("MSFT", "2026-03-27", "iex"),
                "symbol": "MSFT",
                "trade_date": "2026-03-27",
                "provider": "iex",
                "close": 399.0,
                "created_at": utcnow_iso(),
                "updated_at": utcnow_iso(),
            },
        )
        submit_result = dispatcher.submit_job(
            required_capability="daily_price",
            symbols=["MSFT"],
            payload={"symbol": "MSFT"},
        )

        result = worker.run_once()

        assert result["status"] == "completed"
        assert requested_dates == ["20260327", "20260328"]
        saved_rows = dispatcher.pool._GetTableData(TABLE_DAILY_PRICE, {"symbol": "MSFT", "provider": "iex"})
        assert len(saved_rows) == 2
        saved_rows_by_date = {row["trade_date"]: row for row in saved_rows}
        assert saved_rows_by_date["2026-03-27"]["close"] == 402.0
        assert saved_rows_by_date["2026-03-28"]["close"] == 406.0

        raw_rows = dispatcher.pool._GetTableData(TABLE_RAW_DATA, {"job_id": submit_result["job"]["id"]})
        assert len(raw_rows) == 1
        payload = raw_rows[0]["payload"]
        assert payload["provider"] == "iex"
        assert len(payload["requests"]) == 2
        assert payload["requests"][0]["trade_date"] == "2026-03-27"
        assert payload["requests"][1]["trade_date"] == "2026-03-28"
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_us_listed_security_master_job_cap_fetches_and_persists_results(tmp_path):
    """
    Exercise the test_us_listed_security_master_job_cap_fetches_and_persists_results
    regression scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
    worker_db = tmp_path / "worker.sqlite"
    requested_urls = []

    nasdaq_listed_text = build_symbol_directory_text(
        [
            "Symbol",
            "Security Name",
            "Market Category",
            "Test Issue",
            "Financial Status",
            "Round Lot Size",
            "ETF",
            "NextShares",
        ],
        [
            ["AAPL", "Apple Inc. - Common Stock", "Q", "N", "N", "100", "N", "N"],
            ["QQQ", "Invesco QQQ Trust, Series 1", "G", "N", "N", "100", "Y", "N"],
            ["ZVZZT", "NASDAQ TEST STOCK", "G", "Y", "N", "100", "N", "N"],
        ],
        "0328202610:15",
    )
    other_listed_text = build_symbol_directory_text(
        [
            "ACT Symbol",
            "Security Name",
            "Exchange",
            "CQS Symbol",
            "ETF",
            "Round Lot Size",
            "Test Issue",
            "NASDAQ Symbol",
        ],
        [
            ["ABBV", "AbbVie Inc. Common Stock", "N", "ABBV", "N", "100", "N", "ABBV"],
            ["SPY", "SPDR S&P 500 ETF Trust", "P", "SPY", "Y", "100", "N", "SPY"],
            ["TEST", "NYSE TEST STOCK", "N", "TEST", "N", "100", "Y", "TEST"],
        ],
        "0328202610:16",
    )

    dispatcher_config.write_text(
        f"""
{{
  "name": "ADSDispatcher",
  "host": "127.0.0.1",
  "port": 9076,
  "type": "ads.agents.ADSDispatcherAgent",
  "pools": [
    {{
      "type": "SQLitePool",
      "name": "ads_dispatch_pool",
      "description": "dispatch",
      "db_path": "{dispatcher_db}"
    }}
  ]
}}
""".strip(),
        encoding="utf-8",
    )

    def fake_request_get(url, timeout=None):
        """Handle fake request get."""
        requested_urls.append(url)
        if url.endswith("nasdaqlisted.txt"):
            return FakeTextResponse(nasdaq_listed_text, url)
        if url.endswith("otherlisted.txt"):
            return FakeTextResponse(other_listed_text, url)
        return FakeTextResponse("", url, status_code=404)

    dispatcher, dispatcher_server, dispatcher_thread = start_agent_thread(str(dispatcher_config))
    worker_pool = SQLitePool("ads_worker_pool", "ADS worker state", str(worker_db))
    capability = USListedSecJobCap(
        request_get=fake_request_get,
    )
    worker = ADSWorkerAgent(
        pool=worker_pool,
        dispatcher_address="http://127.0.0.1:9076",
        capabilities=["US Listed Sec to security master"],
        job_capabilities=[capability],
    )

    try:
        dispatcher.pool._Insert(
            TABLE_SECURITY_MASTER,
            {
                "id": "ads-security-master:OLD",
                "symbol": "OLD",
                "name": "Old Listing Common Stock",
                "instrument_type": "equity",
                "exchange": "NYSE",
                "currency": "USD",
                "is_active": True,
                "provider": "nasdaqtrader",
                "metadata": {"listing_source": "otherlisted"},
                "created_at": utcnow_iso(),
                "updated_at": utcnow_iso(),
            },
        )
        submit_result = dispatcher.submit_job(required_capability="US Listed Sec to security master")

        result = worker.run_once()

        assert result["status"] == "completed"
        assert requested_urls == [
            "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
            "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
        ]

        saved_rows = dispatcher.pool._GetTableData(TABLE_SECURITY_MASTER)
        saved_by_symbol = {row["symbol"]: row for row in saved_rows}
        assert set(saved_by_symbol.keys()) == {"AAPL", "ABBV", "OLD", "QQQ", "SPY"}

        assert saved_by_symbol["AAPL"]["exchange"] == "NASDAQ"
        assert saved_by_symbol["AAPL"]["instrument_type"] == "equity"
        assert bool(saved_by_symbol["AAPL"]["is_active"]) is True
        assert saved_by_symbol["AAPL"]["metadata"]["market_category"] == "Q"

        assert saved_by_symbol["QQQ"]["instrument_type"] == "etf"
        assert saved_by_symbol["QQQ"]["metadata"]["listing_source"] == "nasdaqlisted"

        assert saved_by_symbol["ABBV"]["exchange"] == "NYSE"
        assert saved_by_symbol["ABBV"]["metadata"]["act_symbol"] == "ABBV"
        assert saved_by_symbol["SPY"]["exchange"] == "NYSE ARCA"
        assert saved_by_symbol["SPY"]["instrument_type"] == "etf"

        assert bool(saved_by_symbol["OLD"]["is_active"]) is False
        assert saved_by_symbol["OLD"]["provider"] == "nasdaqtrader"
        assert saved_by_symbol["OLD"]["metadata"]["deactivated_reason"] == "missing_from_latest_us_listed_snapshot"

        raw_rows = dispatcher.pool._GetTableData(TABLE_RAW_DATA, {"job_id": submit_result["job"]["id"]})
        assert len(raw_rows) == 1
        payload = raw_rows[0]["payload"]
        assert payload["provider"] == "nasdaqtrader"
        assert len(payload["files"]) == 2
        assert payload["files"][0]["dataset"] == "nasdaqlisted"
        assert payload["files"][0]["row_count"] == 3
        assert payload["files"][1]["dataset"] == "otherlisted"
        assert payload["files"][1]["row_count"] == 3
        assert payload["deactivated_symbols"] == ["OLD"]
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_us_listed_security_master_job_cap_falls_back_to_ftp_when_https_fails():
    """
    Exercise the
    test_us_listed_security_master_job_cap_falls_back_to_ftp_when_https_fails
    regression scenario.
    """
    requested_urls = []
    nasdaq_listed_text = build_symbol_directory_text(
        [
            "Symbol",
            "Security Name",
            "Market Category",
            "Test Issue",
            "Financial Status",
            "Round Lot Size",
            "ETF",
            "NextShares",
        ],
        [
            ["AAPL", "Apple Inc. - Common Stock", "Q", "N", "N", "100", "N", "N"],
        ],
        "0328202610:15",
    )
    other_listed_text = build_symbol_directory_text(
        [
            "ACT Symbol",
            "Security Name",
            "Exchange",
            "CQS Symbol",
            "ETF",
            "Round Lot Size",
            "Test Issue",
            "NASDAQ Symbol",
        ],
        [
            ["ABBV", "AbbVie Inc. Common Stock", "N", "ABBV", "N", "100", "N", "ABBV"],
        ],
        "0328202610:16",
    )

    def fake_request_get(url, timeout=None):
        """Handle fake request get."""
        requested_urls.append(url)
        if url.startswith("https://www.nasdaqtrader.com/"):
            raise RuntimeError("timed out")
        if url.endswith("nasdaqlisted.txt"):
            return FakeTextResponse(nasdaq_listed_text, url)
        if url.endswith("otherlisted.txt"):
            return FakeTextResponse(other_listed_text, url)
        return FakeTextResponse("", url, status_code=404)

    capability = USListedSecJobCap(request_get=fake_request_get)

    result = capability.finish(JobDetail(id="ads-job:test", required_capability="us listed sec to security master"))

    assert result.status == "completed"
    assert requested_urls == [
        "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
        "ftp://ftp.nasdaqtrader.com/symboldirectory/nasdaqlisted.txt",
        "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
        "ftp://ftp.nasdaqtrader.com/symboldirectory/otherlisted.txt",
    ]
    assert len(result.collected_rows) == 2


def test_twse_market_eod_job_cap_fetches_from_latest_stored_date_and_persists_results(tmp_path):
    """
    Exercise the test_twse_market_eod_job_cap_fetches_from_latest_stored_date_and_pe
    rsists_results regression scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
    worker_db = tmp_path / "worker.sqlite"
    requested_dates = []
    payload_by_date = {
        "20260327": build_twse_daily_quotes_payload(
            "20260327",
            [
                [
                    "1101",
                    "1,234,567",
                    "1,111",
                    "52,995,000",
                    "43.00",
                    "43.10",
                    "42.70",
                    "42.90",
                    "<p style= color:green>-</p>",
                    "0.20",
                    "42.85",
                    "50",
                    "42.90",
                    "10",
                    "18.00",
                ],
                [
                    "2330",
                    "40,662,382",
                    "236,370",
                    "77,082,966,123",
                    "850.00",
                    "860.00",
                    "845.00",
                    "855.00",
                    "<p style= color:red>+</p>",
                    "5.00",
                    "854.00",
                    "20",
                    "855.00",
                    "10",
                    "20.00",
                ],
            ],
        ),
        "20260328": build_twse_daily_quotes_payload(
            "20260328",
            [
                [
                    "2330",
                    "42,000,000",
                    "240,000",
                    "79,000,000,000",
                    "856.00",
                    "862.00",
                    "853.00",
                    "857.00",
                    "<p style= color:red>+</p>",
                    "2.00",
                    "856.00",
                    "30",
                    "857.00",
                    "12",
                    "20.05",
                ]
            ],
        ),
    }

    dispatcher_config.write_text(
        f"""
{{
  "name": "ADSDispatcher",
  "host": "127.0.0.1",
  "port": 9073,
  "type": "ads.agents.ADSDispatcherAgent",
  "pools": [
    {{
      "type": "SQLitePool",
      "name": "ads_dispatch_pool",
      "description": "dispatch",
      "db_path": "{dispatcher_db}"
    }}
  ]
}}
""".strip(),
        encoding="utf-8",
    )

    def fake_request_get(url, params=None, timeout=None, headers=None):
        """Handle fake request get."""
        date_key = str((params or {}).get("date") or "")
        requested_dates.append(date_key)
        return FakeTWSEResponse(
            payload_by_date.get(date_key, {"stat": "No Data!", "tables": []}),
            f"{url}?response=json&date={date_key}&type=ALLBUT0999",
        )

    dispatcher, dispatcher_server, dispatcher_thread = start_agent_thread(str(dispatcher_config))
    worker_pool = SQLitePool("ads_worker_pool", "ADS worker state", str(worker_db))
    capability = TWSEMarketEODJobCap(
        request_get=fake_request_get,
        today_fn=lambda: date(2026, 3, 28),
    )
    worker = ADSWorkerAgent(
        pool=worker_pool,
        dispatcher_address="http://127.0.0.1:9073",
        capabilities=["twse market eod"],
        job_capabilities=[capability],
    )

    try:
        seed_security_master_symbol(dispatcher.pool, "1101", provider="twse")
        seed_security_master_symbol(dispatcher.pool, "2330", provider="twse")
        dispatcher.pool._Insert(
            TABLE_DAILY_PRICE,
            {
                "id": build_daily_price_id("2330", "2026-03-27", "twse"),
                "symbol": "2330",
                "trade_date": "2026-03-27",
                "provider": "twse",
                "close": 852.0,
                "created_at": utcnow_iso(),
                "updated_at": utcnow_iso(),
            },
        )
        submit_result = dispatcher.submit_job(
            required_capability="TWSE Market EOD",
            payload={},
        )

        result = worker.run_once()

        assert result["status"] == "completed"
        assert requested_dates == ["20260327", "20260328"]

        saved_rows = dispatcher.pool._GetTableData(TABLE_DAILY_PRICE, {"provider": "twse"})
        assert len(saved_rows) == 3
        saved_rows_by_key = {(row["symbol"], row["trade_date"]): row for row in saved_rows}
        assert saved_rows_by_key[("1101", "2026-03-27")]["close"] == 42.9
        assert saved_rows_by_key[("2330", "2026-03-27")]["close"] == 855.0
        assert saved_rows_by_key[("2330", "2026-03-27")]["volume"] == 40662382
        assert saved_rows_by_key[("2330", "2026-03-27")]["metadata"]["change"] == 5.0
        assert saved_rows_by_key[("2330", "2026-03-27")]["metadata"]["transactions"] == 236370
        assert saved_rows_by_key[("2330", "2026-03-28")]["close"] == 857.0
        assert saved_rows_by_key[("2330", "2026-03-28")]["metadata"]["price_earnings_ratio"] == 20.05

        raw_rows = dispatcher.pool._GetTableData(TABLE_RAW_DATA, {"job_id": submit_result["job"]["id"]})
        assert len(raw_rows) == 1
        payload = raw_rows[0]["payload"]
        assert payload["provider"] == "twse"
        assert payload["scope"] == "market"
        assert payload["latest_stored_trade_date"] == "2026-03-27"
        assert len(payload["requests"]) == 2
        assert payload["requests"][0]["scope"] == "market"
        assert payload["requests"][0]["row_count"] == 2
        assert payload["requests"][0]["table_row_count"] == 2
        assert payload["requests"][0]["payload"][0]["Security Code"] == "1101"
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_yfinance_eod_job_cap_fetches_from_latest_stored_date_and_persists_results(tmp_path):
    """
    Exercise the
    test_yfinance_eod_job_cap_fetches_from_latest_stored_date_and_persists_results
    regression scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
    worker_db = tmp_path / "worker.sqlite"
    requested_history_calls = []
    payload_by_symbol = {
        "MSFT": [
            {
                "Date": "2026-03-27",
                "Open": 400.0,
                "High": 405.0,
                "Low": 398.0,
                "Close": 402.0,
                "Adj Close": 401.5,
                "Volume": 1000,
            },
            {
                "Date": "2026-03-28",
                "Open": 403.0,
                "High": 407.0,
                "Low": 401.0,
                "Close": 406.0,
                "Adj Close": 405.5,
                "Volume": 1200,
            },
        ]
    }

    dispatcher_config.write_text(
        f"""
{{
  "name": "ADSDispatcher",
  "host": "127.0.0.1",
  "port": 9074,
  "type": "ads.agents.ADSDispatcherAgent",
  "pools": [
    {{
      "type": "SQLitePool",
      "name": "ads_dispatch_pool",
      "description": "dispatch",
      "db_path": "{dispatcher_db}"
    }}
  ]
}}
""".strip(),
        encoding="utf-8",
    )

    dispatcher, dispatcher_server, dispatcher_thread = start_agent_thread(str(dispatcher_config))
    worker_pool = SQLitePool("ads_worker_pool", "ADS worker state", str(worker_db))
    capability = YFinanceEODJobCap(
        ticker_factory=lambda symbol: FakeYFinanceTicker(symbol, payload_by_symbol, requested_history_calls),
        today_fn=lambda: date(2026, 3, 28),
    )
    worker = ADSWorkerAgent(
        pool=worker_pool,
        dispatcher_address="http://127.0.0.1:9074",
        capabilities=["yfinance eod"],
        job_capabilities=[capability],
    )

    try:
        seed_security_master_symbol(dispatcher.pool, "MSFT", provider="yfinance", name="Microsoft")
        dispatcher.pool._Insert(
            TABLE_DAILY_PRICE,
            {
                "id": build_daily_price_id("MSFT", "2026-03-27", "yfinance"),
                "symbol": "MSFT",
                "trade_date": "2026-03-27",
                "provider": "yfinance",
                "close": 399.0,
                "created_at": utcnow_iso(),
                "updated_at": utcnow_iso(),
            },
        )
        submit_result = dispatcher.submit_job(
            required_capability="YFinance EOD",
            symbols=["MSFT"],
            payload={"symbol": "MSFT"},
        )

        result = worker.run_once()

        assert result["status"] == "completed"
        assert len(requested_history_calls) == 1
        assert requested_history_calls[0]["start"] == "2026-03-27"
        assert requested_history_calls[0]["end"] == "2026-03-29"
        assert requested_history_calls[0]["interval"] == "1d"

        saved_rows = dispatcher.pool._GetTableData(TABLE_DAILY_PRICE, {"symbol": "MSFT", "provider": "yfinance"})
        assert len(saved_rows) == 2
        saved_rows_by_date = {row["trade_date"]: row for row in saved_rows}
        assert saved_rows_by_date["2026-03-27"]["close"] == 402.0
        assert saved_rows_by_date["2026-03-27"]["adj_close"] == 401.5
        assert saved_rows_by_date["2026-03-28"]["close"] == 406.0
        assert saved_rows_by_date["2026-03-28"]["adj_close"] == 405.5

        raw_rows = dispatcher.pool._GetTableData(TABLE_RAW_DATA, {"job_id": submit_result["job"]["id"]})
        assert len(raw_rows) == 1
        payload = raw_rows[0]["payload"]
        assert payload["provider"] == "yfinance"
        assert len(payload["requests"]) == 1
        assert payload["requests"][0]["start_date"] == "2026-03-27"
        assert payload["requests"][0]["end_date"] == "2026-03-28"
        assert payload["requests"][0]["row_count"] == 2
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_yfinance_eod_job_cap_backfills_three_years_when_daily_price_table_is_empty(tmp_path):
    """
    Exercise the
    test_yfinance_eod_job_cap_backfills_three_years_when_daily_price_table_is_empty
    regression scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
    worker_db = tmp_path / "worker.sqlite"
    requested_history_calls = []
    payload_by_symbol = {
        "MSFT": [
            {
                "Date": "2023-03-28",
                "Open": 300.0,
                "High": 305.0,
                "Low": 298.0,
                "Close": 302.0,
                "Adj Close": 301.5,
                "Volume": 900,
            },
            {
                "Date": "2026-03-28",
                "Open": 403.0,
                "High": 407.0,
                "Low": 401.0,
                "Close": 406.0,
                "Adj Close": 405.5,
                "Volume": 1200,
            },
        ]
    }

    dispatcher_config.write_text(
        f"""
{{
  "name": "ADSDispatcher",
  "host": "127.0.0.1",
  "port": 9075,
  "type": "ads.agents.ADSDispatcherAgent",
  "pools": [
    {{
      "type": "SQLitePool",
      "name": "ads_dispatch_pool",
      "description": "dispatch",
      "db_path": "{dispatcher_db}"
    }}
  ]
}}
""".strip(),
        encoding="utf-8",
    )

    dispatcher, dispatcher_server, dispatcher_thread = start_agent_thread(str(dispatcher_config))
    worker_pool = SQLitePool("ads_worker_pool", "ADS worker state", str(worker_db))
    capability = YFinanceEODJobCap(
        ticker_factory=lambda symbol: FakeYFinanceTicker(symbol, payload_by_symbol, requested_history_calls),
        today_fn=lambda: date(2026, 3, 28),
    )
    worker = ADSWorkerAgent(
        pool=worker_pool,
        dispatcher_address="http://127.0.0.1:9075",
        capabilities=["yfinance eod"],
        job_capabilities=[capability],
    )

    try:
        submit_result = dispatcher.submit_job(
            required_capability="YFinance EOD",
            symbols=["MSFT"],
            payload={"symbol": "MSFT"},
        )

        result = worker.run_once()

        assert result["status"] == "completed"
        assert len(requested_history_calls) == 1
        assert requested_history_calls[0]["start"] == "2023-03-28"
        assert requested_history_calls[0]["end"] == "2026-03-29"
        assert requested_history_calls[0]["interval"] == "1d"

        saved_rows = dispatcher.pool._GetTableData(TABLE_DAILY_PRICE, {"symbol": "MSFT", "provider": "yfinance"})
        assert len(saved_rows) == 2
        saved_rows_by_date = {row["trade_date"]: row for row in saved_rows}
        assert saved_rows_by_date["2023-03-28"]["close"] == 302.0
        assert saved_rows_by_date["2023-03-28"]["adj_close"] == 301.5
        assert saved_rows_by_date["2026-03-28"]["close"] == 406.0
        assert saved_rows_by_date["2026-03-28"]["adj_close"] == 405.5

        raw_rows = dispatcher.pool._GetTableData(TABLE_RAW_DATA, {"job_id": submit_result["job"]["id"]})
        assert len(raw_rows) == 1
        payload = raw_rows[0]["payload"]
        assert payload["provider"] == "yfinance"
        assert len(payload["requests"]) == 1
        assert payload["requests"][0]["start_date"] == "2023-03-28"
        assert payload["requests"][0]["end_date"] == "2026-03-28"
        assert payload["requests"][0]["row_count"] == 2
        assert payload["requests"][0]["payload"][0]["date"] == "2023-03-28"
        assert payload["requests"][0]["payload"][1]["date"] == "2026-03-28"
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_yfinance_eod_job_cap_treats_missing_ticker_history_as_empty_result():
    """
    Exercise the
    test_yfinance_eod_job_cap_treats_missing_ticker_history_as_empty_result
    regression scenario.
    """
    class MissingTicker:
        """Represent a missing ticker."""
        def history(self, **kwargs):
            """Return the history."""
            raise YFPricesMissingError("AAMI", "(1d 2023-03-28 -> 2026-03-29)")

    capability = YFinanceEODJobCap(
        ticker_factory=lambda symbol: MissingTicker(),
        today_fn=lambda: date(2026, 3, 28),
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:yf-missing",
            "required_capability": "yfinance eod",
            "symbols": ["AAMI"],
            "payload": {"symbol": "AAMI"},
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:00+00:00",
        }
    )

    result = capability.finish(job)

    assert result.status == "completed"
    assert result.collected_rows == []
    assert len(result.raw_payload["requests"]) == 1
    assert result.raw_payload["requests"][0]["symbol"] == "AAMI"
    assert result.raw_payload["requests"][0]["row_count"] == 0
    assert "possibly delisted" in result.raw_payload["requests"][0]["notes"][0]


def test_yfinance_eod_job_cap_wraps_history_errors():
    """
    Exercise the test_yfinance_eod_job_cap_wraps_history_errors regression scenario.
    """
    class RaisingTicker:
        """Represent a raising ticker."""
        def history(self, **kwargs):
            """Return the history."""
            raise TypeError("'NoneType' object is not subscriptable")

    capability = YFinanceEODJobCap(
        ticker_factory=lambda symbol: RaisingTicker(),
        today_fn=lambda: date(2026, 3, 28),
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:yf-error",
            "required_capability": "yfinance eod",
            "symbols": ["MSFT"],
            "payload": {"symbol": "MSFT"},
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:00+00:00",
        }
    )

    try:
        capability.finish(job)
        assert False, "Expected YFinanceEODJobCap.finish to raise."
    except RuntimeError as exc:
        message = str(exc)
        assert "YFinance history request failed for MSFT" in message
        assert "'NoneType' object is not subscriptable" in message


def test_yfinance_us_market_eod_job_cap_orders_oldest_usd_active_symbols_first(tmp_path):
    """
    Exercise the
    test_yfinance_us_market_eod_job_cap_orders_oldest_usd_active_symbols_first
    regression scenario.
    """
    pool = SQLitePool("ads_dispatch_pool", "dispatch", str(tmp_path / "dispatcher.sqlite"))
    ensure_ads_tables(pool, [TABLE_SECURITY_MASTER])
    now_values = iter(
        [
            "2026-03-28T10:00:00+00:00",
            "2026-03-28T10:00:01+00:00",
            "2026-03-28T10:00:02+00:00",
        ]
    )

    rows = [
        {
            "id": "ads-security-master:AAPL",
            "symbol": "AAPL",
            "name": "Apple",
            "currency": "USD",
            "is_active": True,
            "provider": "nasdaqtrader",
            "metadata": {"yfinance": {"eod_at": "2026-03-20T09:00:00+00:00"}, "sector": "Tech"},
            "created_at": "2026-03-01T00:00:00+00:00",
            "updated_at": "2026-03-20T09:00:00+00:00",
        },
        {
            "id": "ads-security-master:MSFT",
            "symbol": "MSFT",
            "name": "Microsoft",
            "currency": "USD",
            "is_active": 1,
            "provider": "nasdaqtrader",
            "metadata": {"yfinance": {"eod_at": "2026-03-10T09:00:00+00:00"}},
            "created_at": "2026-03-01T00:00:00+00:00",
            "updated_at": "2026-03-10T09:00:00+00:00",
        },
        {
            "id": "ads-security-master:NVDA",
            "symbol": "NVDA",
            "name": "NVIDIA",
            "currency": "USD",
            "is_active": True,
            "provider": "nasdaqtrader",
            "metadata": {"notes": "missing timestamp"},
            "created_at": "2026-03-01T00:00:00+00:00",
            "updated_at": "2026-03-01T00:00:00+00:00",
        },
        {
            "id": "ads-security-master:TEST$P",
            "symbol": "TEST$P",
            "name": "Unsupported Preferred",
            "currency": "USD",
            "is_active": True,
            "provider": "nasdaqtrader",
            "metadata": {"yfinance": {"eod_at": "2026-03-01T00:00:00+00:00"}},
            "created_at": "2026-03-01T00:00:00+00:00",
            "updated_at": "2026-03-01T00:00:00+00:00",
        },
        {
            "id": "ads-security-master:SHOP",
            "symbol": "SHOP",
            "name": "Shopify",
            "currency": "CAD",
            "is_active": True,
            "provider": "nasdaqtrader",
            "metadata": {},
            "created_at": "2026-03-01T00:00:00+00:00",
            "updated_at": "2026-03-01T00:00:00+00:00",
        },
        {
            "id": "ads-security-master:TSLA",
            "symbol": "TSLA",
            "name": "Tesla",
            "currency": "USD",
            "is_active": False,
            "provider": "nasdaqtrader",
            "metadata": {},
            "created_at": "2026-03-01T00:00:00+00:00",
            "updated_at": "2026-03-01T00:00:00+00:00",
        },
    ]
    assert pool._InsertMany(TABLE_SECURITY_MASTER, rows)

    worker = RecordingSubmitWorker(pool)
    capability = YFinanceUSMarketEODJobCap(timestamp_fn=lambda: next(now_values)).bind_worker(worker)
    job = JobDetail.model_validate(
        {
            "id": "ads-job:yf-us-market",
            "required_capability": "yfinance us market eod",
            "payload": {"end_date": "2026-03-28"},
            "priority": 42,
            "max_attempts": 5,
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:00+00:00",
        }
    )

    result = capability.finish(job)

    assert result.status == "completed"
    assert result.result_summary["queued_jobs"] == 3
    assert result.result_summary["symbols"] == ["NVDA", "MSFT", "AAPL"]
    assert [entry["symbols"] for entry in worker.submissions] == [["NVDA"], ["MSFT"], ["AAPL"]]
    assert [entry["priority"] for entry in worker.submissions] == [42, 42, 42]
    assert [entry["max_attempts"] for entry in worker.submissions] == [5, 5, 5]
    assert [entry["payload"] for entry in worker.submissions] == [
        {"end_date": "2026-03-28", "symbol": "NVDA"},
        {"end_date": "2026-03-28", "symbol": "MSFT"},
        {"end_date": "2026-03-28", "symbol": "AAPL"},
    ]

    saved_rows = {row["symbol"]: row for row in pool._GetTableData(TABLE_SECURITY_MASTER)}
    assert saved_rows["NVDA"]["metadata"]["yfinance"]["eod_at"] == "2026-03-28T10:00:00+00:00"
    assert saved_rows["MSFT"]["metadata"]["yfinance"]["eod_at"] == "2026-03-28T10:00:01+00:00"
    assert saved_rows["AAPL"]["metadata"]["yfinance"]["eod_at"] == "2026-03-28T10:00:02+00:00"
    assert saved_rows["AAPL"]["metadata"]["sector"] == "Tech"
    assert saved_rows["TEST$P"]["metadata"]["yfinance"]["eod_at"] == "2026-03-01T00:00:00+00:00"
    assert "yfinance" not in saved_rows["SHOP"]["metadata"]
    assert "yfinance" not in saved_rows["TSLA"]["metadata"]


def test_twse_market_eod_job_cap_handles_no_data_response():
    """
    Exercise the test_twse_market_eod_job_cap_handles_no_data_response regression
    scenario.
    """
    requested_dates = []
    today = date(2026, 3, 14)
    expected_start = date(2026, 3, 7)
    expected_request_count = (today - expected_start).days + 1

    def fake_request_get(url, params=None, timeout=None, headers=None):
        """Handle fake request get."""
        date_key = str((params or {}).get("date") or "")
        requested_dates.append(date_key)
        return FakeTWSEResponse(
            {
                "stat": "No Data!",
                "date": None,
                "tables": [],
            },
            f"{url}?response=json&date={date_key}&type=ALLBUT0999",
        )

    capability = TWSEMarketEODJobCap(
        request_get=fake_request_get,
        today_fn=lambda: today,
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:twse-no-data",
            "required_capability": "twse market eod",
            "symbols": [],
            "payload": {},
            "scheduled_for": "2026-03-14T10:00:00+00:00",
            "created_at": "2026-03-14T10:00:00+00:00",
            "updated_at": "2026-03-14T10:00:00+00:00",
        }
    )

    result = capability.finish(job)

    assert len(requested_dates) == expected_request_count
    assert requested_dates[0] == "20260307"
    assert requested_dates[-1] == "20260314"
    assert result.status == "completed"
    assert result.collected_rows == []
    assert result.result_summary["rows"] == 0
    assert result.result_summary["start_date"] == "2026-03-07"
    assert len(result.raw_payload["requests"]) == expected_request_count
    assert result.raw_payload["start_date"] == "2026-03-07"
    assert result.raw_payload["end_date"] == "2026-03-14"
    assert result.raw_payload["requests"][0]["stat"] == "No Data!"
    assert result.raw_payload["requests"][0]["row_count"] == 0
    assert result.raw_payload["requests"][-1]["trade_date"] == "2026-03-14"


def test_twse_market_eod_job_cap_uses_explicit_start_date_for_historical_backfill():
    """
    Exercise the
    test_twse_market_eod_job_cap_uses_explicit_start_date_for_historical_backfill
    regression scenario.
    """
    requested_dates = []

    def fake_request_get(url, params=None, timeout=None, headers=None):
        """Handle fake request get."""
        date_key = str((params or {}).get("date") or "")
        requested_dates.append(date_key)
        return FakeTWSEResponse(
            {
                "stat": "No Data!",
                "tables": [],
            },
            f"{url}?response=json&date={date_key}&type=ALLBUT0999",
        )

    capability = TWSEMarketEODJobCap(
        request_get=fake_request_get,
        today_fn=lambda: date(2026, 3, 28),
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:twse-explicit-start",
            "required_capability": "twse market eod",
            "payload": {"start_date": "2023-03-28"},
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:00+00:00",
        }
    )

    result = capability.finish(job)

    assert requested_dates[0] == "20230328"
    assert requested_dates[-1] == "20260328"
    assert result.raw_payload["start_date"] == "2023-03-28"
    assert result.result_summary["start_date"] == "2023-03-28"


def test_twse_market_eod_job_cap_retries_retryable_stat_for_valid_supported_dates():
    """
    Exercise the
    test_twse_market_eod_job_cap_retries_retryable_stat_for_valid_supported_dates
    regression scenario.
    """
    requested_dates = []
    received_headers = []
    sleep_calls = []

    def fake_request_get(url, params=None, timeout=None, headers=None):
        """Handle fake request get."""
        date_key = str((params or {}).get("date") or "")
        requested_dates.append(date_key)
        received_headers.append(dict(headers or {}))
        if len(requested_dates) == 1:
            return FakeTWSEResponse(
                {
                    "stat": "Search date less than 2004/02/11, please retry!",
                    "tables": [],
                },
                f"{url}?response=json&date={date_key}&type=ALLBUT0999",
            )
        return FakeTWSEResponse(
            build_twse_daily_quotes_payload(
                date_key,
                [
                    [
                        "2330",
                        "42,000,000",
                        "240,000",
                        "79,000,000,000",
                        "856.00",
                        "862.00",
                        "853.00",
                        "857.00",
                        "<p style= color:red>+</p>",
                        "2.00",
                        "856.00",
                        "30",
                        "857.00",
                        "12",
                        "20.05",
                    ]
                ],
            ),
            f"{url}?response=json&date={date_key}&type=ALLBUT0999",
        )

    capability = TWSEMarketEODJobCap(
        request_get=fake_request_get,
        today_fn=lambda: date(2026, 3, 28),
        bootstrap_days=0,
        request_retry_limit=1,
        retry_sleep_sec=0.5,
        sleep_fn=lambda seconds: sleep_calls.append(seconds),
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:twse-retryable-stat",
            "required_capability": "twse market eod",
            "payload": {"start_date": "2026-03-28"},
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:00+00:00",
        }
    )

    result = capability.finish(job)

    assert requested_dates == ["20260328", "20260328"]
    assert sleep_calls == [0.5]
    assert received_headers[0]["User-Agent"].startswith("Mozilla/5.0")
    assert result.status == "completed"
    assert len(result.collected_rows) == 1
    assert result.collected_rows[0]["symbol"] == "2330"


def test_twse_market_eod_job_cap_wraps_invalid_json_response():
    """
    Exercise the test_twse_market_eod_job_cap_wraps_invalid_json_response regression
    scenario.
    """
    class InvalidJsonResponse:
        """Response model for invalid JSON payloads."""
        def __init__(self, url: str):
            """Initialize the invalid JSON response."""
            self.url = url
            self.status_code = 200
            self.text = ""

        def json(self):
            """Handle JSON for the invalid JSON response."""
            raise JSONDecodeError("Expecting value", "", 0)

    def fake_request_get(url, params=None, timeout=None, headers=None):
        """Handle fake request get."""
        date_key = str((params or {}).get("date") or "")
        return InvalidJsonResponse(f"{url}?response=json&date={date_key}&type=ALLBUT0999")

    capability = TWSEMarketEODJobCap(
        request_get=fake_request_get,
        today_fn=lambda: date(2026, 3, 28),
        bootstrap_days=0,
        request_retry_limit=0,
    )
    job = JobDetail.model_validate(
        {
            "id": "ads-job:twse-invalid-json",
            "required_capability": "twse market eod",
            "payload": {"start_date": "2026-03-28"},
            "scheduled_for": "2026-03-28T10:00:00+00:00",
            "created_at": "2026-03-28T10:00:00+00:00",
            "updated_at": "2026-03-28T10:00:00+00:00",
        }
    )

    try:
        capability.finish(job)
        assert False, "Expected TWSEMarketEODJobCap.finish to raise for invalid JSON."
    except RuntimeError as exc:
        message = str(exc)
        assert "TWSE response was not valid JSON for 2026-03-28" in message
        assert "<empty response body>" in message
