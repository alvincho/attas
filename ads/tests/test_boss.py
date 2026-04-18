"""
Regression tests for Boss.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace. These tests protect the ADS data-service
behaviors, scheduling rules, and provider integrations.

The pytest cases in this file document expected behavior through checks such as
`test_ads_boss_can_create_and_list_scheduled_jobs`,
`test_ads_boss_can_create_monthly_schedule_with_multiple_days`,
`test_ads_boss_can_create_weekly_recurring_schedule`, and
`test_ads_boss_compute_next_occurrence_supports_multiple_run_times`, helping guard
against regressions as the packages evolve.
"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ads.boss import ADSBossAgent, BossDbQueryRequest, BossDbTableRequest, BossScheduleJobRequest, TABLE_SCHEDULED_JOBS
from ads.models import JobResult
from ads.runtime import parse_datetime_value, read_ads_config
from ads.schema import (
    TABLE_DAILY_PRICE,
    TABLE_JOB_ARCHIVE,
    TABLE_JOBS,
    TABLE_NEWS,
    TABLE_RAW_DATA,
    TABLE_SEC_COMPANYFACTS,
    TABLE_SEC_SUBMISSIONS,
    TABLE_SECURITY_MASTER,
    TABLE_WORKER_HISTORY,
    TABLE_WORKERS,
)
from prompits.pools.sqlite import SQLitePool
from prompits.tests.test_support import start_agent_thread, stop_servers


def build_client(tmp_path, *, dispatcher_address: str = "http://127.0.0.1:8060"):
    """Build the client."""
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    agent = ADSBossAgent(pool=pool, dispatcher_address=dispatcher_address)
    return agent, TestClient(agent.app)


class FakePopen:
    """Minimal subprocess double for ADS boss worker-launch tests."""

    def __init__(self, pid: int = 4242):
        self.pid = pid
        self._returncode = None

    def poll(self):
        """Return the current fake process exit code."""
        return self._returncode

    def terminate(self):
        """Simulate a graceful terminate."""
        self._returncode = 0

    def wait(self, timeout=None):
        """Return the final exit code."""
        return self._returncode

    def kill(self):
        """Simulate a forced kill."""
        self._returncode = -9


def build_client_with_worker_template(tmp_path):
    """Build one ADS boss test client with a local worker template config."""
    worker_config_path = tmp_path / "worker.agent"
    worker_config_path.write_text(
        json.dumps(
            {
                "name": "ADSWorker",
                "host": "127.0.0.1",
                "plaza_url": "http://127.0.0.1:8011",
                "ads": {
                    "job_capabilities": [
                        {"name": "RSS News", "type": "ads.rss_news:RSSNewsJobCap"},
                        {"name": "TWSE Market EOD", "type": "ads.twse:TWSEMarketEODJobCap"},
                    ],
                    "capabilities": ["rss news", "twse market eod"],
                    "auto_register": True,
                },
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    boss_config_path = tmp_path / "boss.agent"
    boss_config_path.write_text(
        json.dumps(
            {
                "name": "ADSBoss",
                "host": "127.0.0.1",
                "ads": {
                    "dispatcher_address": "http://127.0.0.1:8060",
                    "worker_config_path": "worker.agent",
                },
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    agent = ADSBossAgent(pool=pool, config_path=boss_config_path)
    return agent, TestClient(agent.app)


def test_ads_boss_root_renders_dispatch_console(tmp_path):
    """Exercise the test_ads_boss_root_renders_dispatch_console regression scenario."""
    _agent, client = build_client(tmp_path)

    response = client.get("/")

    assert response.status_code == 200
    assert "ADS Boss Agent" in response.text
    assert "Issue Job" in response.text
    assert "Settings" in response.text
    assert "Job Name" in response.text
    assert "Priority" in response.text
    assert "Lower numbers dispatch sooner; 100 is normal, smaller is urgent, larger is background." in response.text
    assert "job-parameters-toggle" in response.text
    assert "Expand parameters" in response.text
    assert "Collapse" in response.text
    assert "ADS Boss Deck" in response.text
    assert "ADS Metrics" in response.text
    assert "Security Master" in response.text
    assert "Daily Price" in response.text
    assert "News" in response.text
    assert "SEC Companyfacts" in response.text
    assert "SEC Submissions" in response.text
    assert "Queued Jobs" in response.text
    assert "Workers Online" in response.text
    assert "Refresh Metrics" in response.text
    assert "/boss-static/boss.js?v=" in response.text


def test_ads_boss_defaults_to_ads_party(tmp_path):
    """Exercise the test_ads_boss_defaults_to_ads_party regression scenario."""
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    agent = ADSBossAgent(pool=pool)

    assert agent.agent_card["party"] == "ADS"
    assert agent.agent_card["meta"]["party"] == "ADS"


def test_ads_boss_monitor_page_renders_dispatcher_and_worker_status(tmp_path):
    """
    Exercise the test_ads_boss_monitor_page_renders_dispatcher_and_worker_status
    regression scenario.
    """
    _agent, client = build_client(tmp_path)

    response = client.get("/monitor")

    assert response.status_code == 200
    assert "Monitor" in response.text
    assert "Plaza" in response.text
    assert "Operations Monitor" in response.text
    assert "Expand" in response.text
    assert "Jobs" in response.text
    assert "Dispatcher" in response.text
    assert "Workers" in response.text
    assert "Dispatcher Status" in response.text
    assert "Worker Roster" in response.text
    assert "Worker Status" in response.text
    assert "Online Only" in response.text
    assert "Refresh Monitor" in response.text
    assert "Queue Drilldown" in response.text
    assert "Sort By" in response.text
    assert "Latest Time" in response.text
    assert "Current Job Detail" in response.text
    assert "Work History" in response.text


def test_ads_boss_monitor_page_renders_management_console_sections(tmp_path):
    """Exercise the ADS management console monitor layout."""
    _agent, client = build_client(tmp_path)

    response = client.get("/monitor")

    assert response.status_code == 200
    assert "Dashboard" in response.text
    assert "Crawler Coverage" in response.text
    assert "Start New Workers" in response.text
    assert "Managed Runtime" in response.text
    assert "Worker Roster By Type" in response.text
    assert "Worker Logs" in response.text


def test_ads_boss_local_worker_endpoints_launch_and_list_sessions(tmp_path):
    """Exercise boss-managed local worker launch and listing."""
    _agent, client = build_client_with_worker_template(tmp_path)
    fake_process = FakePopen(pid=7331)

    with patch("ads.boss.subprocess.Popen", return_value=fake_process):
        response = client.post("/api/workers/local", json={"worker_type": "rss-news", "count": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 1
    worker = payload["workers"][0]
    assert worker["worker_type"] == "rss-news"
    assert worker["worker_type_label"] == "RSS News"
    assert worker["status"] == "running"
    generated_config = json.loads(Path(worker["config_path"]).read_text(encoding="utf-8"))
    assert generated_config["name"].startswith("ADSWorker-rss-news-")
    assert generated_config["ads"]["dispatcher_address"] == "http://127.0.0.1:8060"
    assert [entry["name"] for entry in generated_config["ads"]["job_capabilities"]] == ["RSS News"]
    assert generated_config["agent_card"]["meta"]["local_manager_session_id"] == worker["id"]

    list_response = client.get("/api/workers/local")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert listed["count"] == 1
    assert listed["workers"][0]["id"] == worker["id"]
    catalog_ids = {entry["id"] for entry in listed["catalog"]}
    assert "all-capabilities" in catalog_ids
    assert "rss-news" in catalog_ids
    assert "twse-market-eod" in catalog_ids


def test_ads_boss_local_worker_logs_and_terminate(tmp_path):
    """Exercise log tailing and terminate for boss-managed local workers."""
    _agent, client = build_client_with_worker_template(tmp_path)
    fake_process = FakePopen(pid=8448)

    with patch("ads.boss.subprocess.Popen", return_value=fake_process):
        launch_response = client.post("/api/workers/local", json={"worker_type": "rss-news", "count": 1})

    assert launch_response.status_code == 200
    worker = launch_response.json()["workers"][0]
    with open(worker["log_path"], "a", encoding="utf-8") as fh:
        fh.write("line-one\nline-two\n")

    logs_response = client.get(f"/api/workers/local/{worker['id']}/logs?limit=1")
    assert logs_response.status_code == 200
    logs_payload = logs_response.json()
    assert logs_payload["lines"] == ["line-two"]

    terminate_response = client.post(
        f"/api/workers/local/{worker['id']}/control",
        json={"action": "terminate"},
    )
    assert terminate_response.status_code == 200
    terminated = terminate_response.json()["worker"]
    assert terminated["status"] == "terminated"
    assert terminated["exit_code"] == 0


def test_ads_boss_monitor_summary_reports_not_configured_without_dispatcher(tmp_path):
    """
    Exercise the
    test_ads_boss_monitor_summary_reports_not_configured_without_dispatcher
    regression scenario.
    """
    _agent, client = build_client(tmp_path, dispatcher_address="")

    response = client.get("/api/monitor/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dispatcher"]["connection_status"] == "not_configured"
    assert payload["dispatcher"]["queue_state"] == "not_configured"
    assert payload["workers"] == []


def test_ads_boss_metrics_summary_reports_not_configured_without_dispatcher(tmp_path):
    """
    Exercise the
    test_ads_boss_metrics_summary_reports_not_configured_without_dispatcher
    regression scenario.
    """
    _agent, client = build_client(tmp_path, dispatcher_address="")

    response = client.get("/api/metrics/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "not_configured"
    assert payload["error"] == "Set a dispatcher address to load ADS metrics."
    assert [metric["label"] for metric in payload["metrics"]] == [
        "Security Master",
        "Daily Price",
        "News",
        "SEC Companyfacts",
        "SEC Submissions",
    ]
    assert all(metric["count"] == 0 for metric in payload["metrics"])
    assert all(metric["available"] is False for metric in payload["metrics"])


def test_ads_boss_metrics_summary_counts_ads_tables(tmp_path):
    """
    Exercise the test_ads_boss_metrics_summary_counts_ads_tables regression
    scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")

    with (
        patch.object(
            agent,
            "list_db_tables_via_dispatcher",
            return_value={
                "tables": [
                    {"name": TABLE_SECURITY_MASTER},
                    {"name": TABLE_DAILY_PRICE},
                    {"name": TABLE_NEWS},
                    {"name": TABLE_SEC_COMPANYFACTS},
                    {"name": TABLE_SEC_SUBMISSIONS},
                ]
            },
        ),
        patch.object(
            agent,
            "query_db_via_dispatcher",
            side_effect=[
                {"rows": [{"row_count": 1250}]},
                {"rows": [{"row_count": 98234}]},
                {"rows": [{"row_count": 441}]},
                {"rows": [{"row_count": 2876}]},
                {"rows": [{"row_count": 2941}]},
            ],
        ),
    ):
        response = client.get("/api/metrics/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["dispatcher_address"] == "http://127.0.0.1:9070"
    assert {metric["id"]: metric["count"] for metric in payload["metrics"]} == {
        "security_master": 1250,
        "daily_price": 98234,
        "news": 441,
        "sec_companyfacts": 2876,
        "sec_submissions": 2941,
    }
    assert all(metric["available"] is True for metric in payload["metrics"])


def test_ads_boss_monitor_summary_reports_worker_and_queue_status(tmp_path):
    """
    Exercise the test_ads_boss_monitor_summary_reports_worker_and_queue_status
    regression scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")
    now = datetime.now(timezone.utc)

    def fake_fetch_dispatcher_rows(*, table_name, table_schema, dispatcher_address="", id_or_where=None):
        """Return the fake fetch dispatcher rows."""
        assert dispatcher_address == "http://127.0.0.1:9070"
        assert id_or_where is None
        if table_name == TABLE_JOBS:
            return [
                {
                    "id": "ads-job:queued",
                    "required_capability": "YFinance EOD",
                    "status": "queued",
                    "symbols": ["MSFT"],
                    "updated_at": (now - timedelta(seconds=15)).isoformat(),
                    "created_at": (now - timedelta(minutes=2)).isoformat(),
                },
                {
                    "id": "ads-job:claimed",
                    "required_capability": "IEX EOD",
                    "status": "claimed",
                    "claimed_by": "worker-a",
                    "symbols": ["AAPL"],
                    "updated_at": (now - timedelta(seconds=8)).isoformat(),
                    "created_at": (now - timedelta(minutes=3)).isoformat(),
                },
                {
                    "id": "ads-job:failed",
                    "required_capability": "TWSE Market EOD",
                    "status": "failed",
                    "claimed_by": "worker-b",
                    "symbols": ["2330"],
                    "updated_at": (now - timedelta(minutes=5)).isoformat(),
                    "created_at": (now - timedelta(minutes=6)).isoformat(),
                },
            ]
        if table_name == TABLE_WORKERS:
            return [
                {
                    "id": "worker-a",
                    "worker_id": "worker-a",
                    "name": "Worker A",
                    "status": "online",
                    "address": "http://127.0.0.1:8061",
                    "capabilities": ["IEX EOD"],
                    "last_seen_at": (now - timedelta(seconds=6)).isoformat(),
                    "updated_at": (now - timedelta(seconds=6)).isoformat(),
                },
                {
                    "id": "worker-b",
                    "worker_id": "worker-b",
                    "name": "Worker B",
                    "status": "online",
                    "address": "http://127.0.0.1:8062",
                    "capabilities": ["TWSE Market EOD"],
                    "last_seen_at": (now - timedelta(seconds=90)).isoformat(),
                    "updated_at": (now - timedelta(seconds=90)).isoformat(),
                },
            ]
        raise AssertionError(f"Unexpected table request: {table_name}")

    with patch.object(agent, "_fetch_dispatcher_rows", side_effect=fake_fetch_dispatcher_rows):
        response = client.get("/api/monitor/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dispatcher"]["connection_status"] == "connected"
    assert payload["dispatcher"]["queue_state"] == "working"
    assert payload["dispatcher"]["ready_jobs"] == 1
    assert payload["dispatcher"]["inflight_jobs"] == 1
    assert payload["dispatcher"]["failed_jobs"] == 1
    assert payload["dispatcher"]["active_workers"] == 1
    assert payload["dispatcher"]["stale_workers"] == 1
    assert payload["dispatcher"]["total_workers"] == 2
    assert payload["workers"][0]["worker_id"] == "worker-a"
    assert payload["workers"][0]["health_status"] == "online"
    assert payload["workers"][0]["active_job_ids"] == ["ads-job:claimed"]
    assert payload["workers"][0]["active_jobs"][0]["required_capability"] == "IEX EOD"
    assert payload["workers"][0]["active_jobs"][0]["symbols"] == ["AAPL"]
    assert payload["workers"][1]["worker_id"] == "worker-b"
    assert payload["workers"][1]["health_status"] == "stale"


def test_ads_boss_monitor_summary_falls_back_to_worker_heartbeat_active_job(tmp_path):
    """
    Exercise the
    test_ads_boss_monitor_summary_falls_back_to_worker_heartbeat_active_job
    regression scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")
    now = datetime.now(timezone.utc)

    def fake_fetch_dispatcher_rows(*, table_name, table_schema, dispatcher_address="", id_or_where=None):
        """Return the fake fetch dispatcher rows."""
        assert dispatcher_address == "http://127.0.0.1:9070"
        assert id_or_where is None
        if table_name == TABLE_JOBS:
            return [
                {
                    "id": "ads-job:queued",
                    "required_capability": "YFinance EOD",
                    "status": "queued",
                    "symbols": ["AAPL"],
                    "updated_at": (now - timedelta(seconds=8)).isoformat(),
                    "created_at": (now - timedelta(minutes=1)).isoformat(),
                }
            ]
        if table_name == TABLE_WORKERS:
            return [
                {
                    "id": "worker-a",
                    "worker_id": "worker-a",
                    "name": "Worker A",
                    "status": "working",
                    "address": "http://127.0.0.1:8061",
                    "capabilities": ["YFinance EOD"],
                    "metadata": {
                        "heartbeat": {
                            "active_job": {
                                "id": "ads-job:heartbeat",
                                "status": "working",
                            },
                            "progress": {
                                "phase": "working",
                                "message": "Processing yfinance eod.",
                                "extra": {
                                    "required_capability": "yfinance eod",
                                    "symbols": ["MSFT"],
                                },
                            },
                        }
                    },
                    "last_seen_at": (now - timedelta(seconds=5)).isoformat(),
                    "updated_at": (now - timedelta(seconds=5)).isoformat(),
                }
            ]
        raise AssertionError(f"Unexpected table request: {table_name}")

    with patch.object(agent, "_fetch_dispatcher_rows", side_effect=fake_fetch_dispatcher_rows):
        response = client.get("/api/monitor/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["dispatcher"]["inflight_jobs"] == 0
    assert payload["workers"][0]["worker_id"] == "worker-a"
    assert payload["workers"][0]["health_status"] == "online"
    assert payload["workers"][0]["active_job_count"] == 1
    assert payload["workers"][0]["active_job_ids"] == ["ads-job:heartbeat"]
    assert payload["workers"][0]["active_jobs"] == [
        {
            "id": "ads-job:heartbeat",
            "required_capability": "yfinance eod",
            "symbols": ["MSFT"],
            "target_table": "",
            "source_url": "",
            "payload": {},
            "priority": None,
            "scheduled_for": "",
            "status": "working",
        }
    ]


def test_ads_boss_monitor_summary_ignores_heartbeat_active_job_for_offline_worker(tmp_path):
    """
    Exercise the
    test_ads_boss_monitor_summary_ignores_heartbeat_active_job_for_offline_worker
    regression scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")
    now = datetime.now(timezone.utc)

    def fake_fetch_dispatcher_rows(*, table_name, table_schema, dispatcher_address="", id_or_where=None):
        """Return the fake fetch dispatcher rows."""
        assert dispatcher_address == "http://127.0.0.1:9070"
        assert id_or_where is None
        if table_name == TABLE_JOBS:
            return []
        if table_name == TABLE_WORKERS:
            return [
                {
                    "id": "worker-a",
                    "worker_id": "worker-a",
                    "name": "Worker A",
                    "status": "working",
                    "address": "http://127.0.0.1:8061",
                    "capabilities": ["YFinance EOD"],
                    "metadata": {
                        "heartbeat": {
                            "active_job": {
                                "id": "ads-job:heartbeat",
                                "status": "working",
                            },
                            "progress": {
                                "phase": "working",
                                "message": "Processing yfinance eod.",
                                "extra": {
                                    "required_capability": "yfinance eod",
                                    "symbols": ["MSFT"],
                                },
                            },
                        }
                    },
                    "last_seen_at": (now - timedelta(minutes=10)).isoformat(),
                    "updated_at": (now - timedelta(minutes=10)).isoformat(),
                }
            ]
        raise AssertionError(f"Unexpected table request: {table_name}")

    with patch.object(agent, "_fetch_dispatcher_rows", side_effect=fake_fetch_dispatcher_rows):
        response = client.get("/api/monitor/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workers"][0]["worker_id"] == "worker-a"
    assert payload["workers"][0]["health_status"] == "offline"
    assert payload["workers"][0]["active_job_count"] == 0
    assert payload["workers"][0]["active_job_ids"] == []
    assert payload["workers"][0]["active_jobs"] == []


def test_ads_boss_worker_history_lists_recent_jobs_for_worker(tmp_path):
    """
    Exercise the test_ads_boss_worker_history_lists_recent_jobs_for_worker
    regression scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")
    now = datetime.now(timezone.utc)

    def fake_fetch_dispatcher_rows(*, table_name, table_schema, dispatcher_address="", id_or_where=None):
        """Return the fake fetch dispatcher rows."""
        assert dispatcher_address == "http://127.0.0.1:9070"
        assert id_or_where is None
        if table_name == TABLE_JOBS:
            rows = []
            for index in range(12):
                rows.append(
                    {
                        "id": f"ads-job:{index}",
                        "required_capability": f"Job {index}",
                        "status": "claimed" if index == 0 else "completed",
                        "claimed_by": "worker-a",
                        "symbols": [f"SYM{index}"],
                        "created_at": (now - timedelta(minutes=index + 5)).isoformat(),
                        "updated_at": (now - timedelta(minutes=index)).isoformat(),
                        "claimed_at": (now - timedelta(minutes=index)).isoformat(),
                    }
                )
            rows.append(
                {
                    "id": "ads-job:other",
                    "required_capability": "Other Worker Job",
                    "status": "completed",
                    "claimed_by": "worker-b",
                    "symbols": ["MSFT"],
                    "created_at": (now - timedelta(minutes=2)).isoformat(),
                    "updated_at": (now - timedelta(minutes=2)).isoformat(),
                }
            )
            return rows
        if table_name == TABLE_JOB_ARCHIVE:
            return []
        if table_name == TABLE_WORKERS:
            return [
                {
                    "id": "worker-a",
                    "worker_id": "worker-a",
                    "name": "Worker A",
                    "status": "online",
                    "last_seen_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            ]
        raise AssertionError(f"Unexpected table request: {table_name}")

    with patch.object(agent, "_fetch_dispatcher_rows", side_effect=fake_fetch_dispatcher_rows):
        response = client.get("/api/workers/worker-a/history?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["worker"]["name"] == "Worker A"
    assert payload["count"] == 12
    assert payload["limit"] == 10
    assert len(payload["jobs"]) == 10
    assert payload["jobs"][0]["id"] == "ads-job:0"
    assert payload["jobs"][0]["status"] == "claimed"
    assert payload["jobs"][-1]["id"] == "ads-job:9"


def test_ads_boss_worker_history_returns_worker_heartbeat_history(tmp_path):
    """
    Exercise the test_ads_boss_worker_history_returns_worker_heartbeat_history
    regression scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")
    now = datetime.now(timezone.utc)

    def fake_fetch_dispatcher_rows(*, table_name, table_schema, dispatcher_address="", id_or_where=None):
        """Return the fake fetch dispatcher rows."""
        assert dispatcher_address == "http://127.0.0.1:9070"
        if table_name == TABLE_JOBS:
            return []
        if table_name == TABLE_JOB_ARCHIVE:
            return []
        if table_name == TABLE_WORKERS:
            return [
                {
                    "id": "worker-a",
                    "worker_id": "worker-a",
                    "name": "Worker A",
                    "status": "working",
                    "last_seen_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "metadata": {
                        "environment": {"hostname": "worker-a-host"},
                        "heartbeat": {
                            "progress": {"phase": "working", "message": "Collecting news"},
                            "active_job": {"id": "ads-job:1", "status": "working"},
                        },
                    },
                }
            ]
        if table_name == TABLE_WORKER_HISTORY:
            return [
                {
                    "id": "history-1",
                    "worker_id": "worker-a",
                    "name": "Worker A",
                    "status": "working",
                    "event_type": "heartbeat",
                    "progress": {"phase": "working", "message": "Collecting news"},
                    "environment": {"hostname": "worker-a-host"},
                    "captured_at": now.isoformat(),
                }
            ]
        raise AssertionError(f"Unexpected table request: {table_name}")

    with patch.object(agent, "_fetch_dispatcher_rows", side_effect=fake_fetch_dispatcher_rows):
        response = client.get("/api/workers/worker-a/history?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["history"]) == 1
    assert payload["history"][0]["event_type"] == "heartbeat"
    assert payload["history"][0]["progress"]["phase"] == "working"
    assert payload["history"][0]["environment"]["hostname"] == "worker-a-host"


def test_ads_boss_job_detail_includes_latest_heartbeat_message(tmp_path):
    """
    Exercise the test_ads_boss_job_detail_includes_latest_heartbeat_message
    regression scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")
    now = datetime.now(timezone.utc)

    def fake_fetch_dispatcher_rows(*, table_name, table_schema, dispatcher_address="", id_or_where=None):
        """Return the fake fetch dispatcher rows."""
        assert dispatcher_address == "http://127.0.0.1:9070"
        if table_name == TABLE_JOBS:
            assert id_or_where == {"id": "ads-job:1"}
            return [
                {
                    "id": "ads-job:1",
                    "required_capability": "RSS News",
                    "status": "claimed",
                    "claimed_by": "worker-a",
                    "symbols": ["AAPL"],
                    "created_at": (now - timedelta(minutes=2)).isoformat(),
                    "updated_at": now.isoformat(),
                }
            ]
        if table_name == TABLE_JOB_ARCHIVE:
            assert id_or_where == {"id": "ads-job:1"}
            return []
        if table_name == TABLE_RAW_DATA:
            assert id_or_where == {"job_id": "ads-job:1"}
            return []
        if table_name == TABLE_WORKER_HISTORY:
            assert id_or_where == {"active_job_id": "ads-job:1"}
            return [
                {
                    "id": "history-1",
                    "worker_id": "worker-a",
                    "name": "Worker A",
                    "status": "working",
                    "event_type": "heartbeat",
                    "active_job_id": "ads-job:1",
                    "active_job_status": "working",
                    "progress": {"phase": "working", "message": "Collecting latest headlines"},
                    "captured_at": now.isoformat(),
                }
            ]
        raise AssertionError(f"Unexpected table request: {table_name}")

    with patch.object(agent, "_fetch_dispatcher_rows", side_effect=fake_fetch_dispatcher_rows):
        response = client.get("/api/jobs/ads-job:1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["job"]["id"] == "ads-job:1"
    assert payload["latest_heartbeat"]["message"] == "Collecting latest headlines"
    assert payload["latest_heartbeat"]["phase"] == "working"
    assert payload["latest_heartbeat"]["worker_name"] == "Worker A"


def test_ads_boss_schedule_history_lists_related_jobs(tmp_path):
    """
    Exercise the test_ads_boss_schedule_history_lists_related_jobs regression
    scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")
    now = datetime.now(timezone.utc)

    create_response = client.post(
        "/api/schedules",
        json={
            "required_capability": "news",
            "symbols": ["AAPL"],
            "payload": {"symbol": "AAPL"},
            "scheduled_for": "2099-03-28T10:00:00+00:00",
        },
    )
    assert create_response.status_code == 200
    schedule = create_response.json()["schedule"]
    schedule_id = schedule["id"]

    def fake_fetch_dispatcher_rows(*, table_name, table_schema, dispatcher_address="", id_or_where=None):
        """Return the fake fetch dispatcher rows."""
        assert dispatcher_address == "http://127.0.0.1:9070"
        assert id_or_where is None
        if table_name == TABLE_JOBS:
            return []
        if table_name == TABLE_JOB_ARCHIVE:
            return [
                {
                    "id": "ads-job:recent",
                    "required_capability": "news",
                    "status": "completed",
                    "claimed_by": "worker-a",
                    "symbols": ["AAPL"],
                    "metadata": {"boss_schedule_id": schedule_id},
                    "created_at": (now - timedelta(minutes=5)).isoformat(),
                    "updated_at": (now - timedelta(minutes=1)).isoformat(),
                    "completed_at": now.isoformat(),
                },
                {
                    "id": "ads-job:older",
                    "required_capability": "news",
                    "status": "completed",
                    "claimed_by": "worker-b",
                    "symbols": ["AAPL"],
                    "metadata": {"boss_schedule_id": schedule_id},
                    "created_at": (now - timedelta(minutes=15)).isoformat(),
                    "updated_at": (now - timedelta(minutes=9)).isoformat(),
                    "completed_at": (now - timedelta(minutes=9)).isoformat(),
                },
                {
                    "id": "ads-job:other",
                    "required_capability": "news",
                    "status": "completed",
                    "claimed_by": "worker-z",
                    "symbols": ["MSFT"],
                    "metadata": {"boss_schedule_id": "ads-boss-schedule:other"},
                    "created_at": (now - timedelta(minutes=3)).isoformat(),
                    "updated_at": (now - timedelta(minutes=2)).isoformat(),
                },
            ]
        raise AssertionError(f"Unexpected table request: {table_name}")

    with patch.object(agent, "_fetch_dispatcher_rows", side_effect=fake_fetch_dispatcher_rows):
        response = client.get(f"/api/schedules/{schedule_id}/history?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["schedule"]["id"] == schedule_id
    assert payload["count"] == 2
    assert payload["limit"] == 10
    assert [job["id"] for job in payload["jobs"]] == ["ads-job:recent", "ads-job:older"]


def test_ads_boss_schedule_page_renders_schedule_console(tmp_path):
    """
    Exercise the test_ads_boss_schedule_page_renders_schedule_console regression
    scenario.
    """
    _agent, client = build_client(tmp_path)

    response = client.get("/schedule")

    assert response.status_code == 200
    assert "Schedule Console" in response.text
    assert "Scheduled Jobs" in response.text
    assert "Schedule Job History" in response.text
    assert "Repeat Frequency" in response.text
    assert "Run Times" in response.text
    assert "Days Of Month" in response.text


def test_ads_boss_settings_page_renders_console_defaults(tmp_path):
    """
    Exercise the test_ads_boss_settings_page_renders_console_defaults regression
    scenario.
    """
    _agent, client = build_client(tmp_path)

    response = client.get("/settings")

    assert response.status_code == 200
    assert "Console Profile" in response.text
    assert "Default Dispatcher Address" in response.text
    assert "Monitor Auto Refresh" in response.text
    assert "Plaza URL" in response.text
    assert "Connect Plaza" in response.text
    assert "Save Local" in response.text
    assert "Load Local" in response.text


def test_ads_boss_db_page_renders_viewer_console(tmp_path):
    """Exercise the test_ads_boss_db_page_renders_viewer_console regression scenario."""
    _agent, client = build_client(tmp_path)

    response = client.get("/db")

    assert response.status_code == 200
    assert "DB Viewer" in response.text
    assert "SQL Console" in response.text
    assert "Run SQL" in response.text
    assert "Result Grid" in response.text
    assert 'data-db-tab="viewer"' in response.text
    assert 'data-db-tab="sql"' in response.text


def test_ads_boss_uses_job_cap_name_for_job_options(tmp_path):
    """
    Exercise the test_ads_boss_uses_job_cap_name_for_job_options regression
    scenario.
    """
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    agent = ADSBossAgent(
        pool=pool,
        config={
            "ads": {
                "job_capabilities": [
                    {"name": "IEX EOD", "type": "ads.iex:IEXEODJobCap", "token": "demo-token"}
                ]
            }
        },
    )

    assert agent.job_options[0]["id"] == "IEX EOD"
    assert agent.job_options[0]["label"] == "IEX EOD"


def test_ads_boss_omits_disabled_job_capabilities_from_options(tmp_path):
    """
    Exercise the test_ads_boss_omits_disabled_job_capabilities_from_options
    regression scenario.
    """
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    agent = ADSBossAgent(
        pool=pool,
        config={
            "ads": {
                "job_capabilities": [
                    {"name": "YFinance EOD", "disabled": True},
                    {"name": "RSS News"},
                ]
            }
        },
    )

    assert [option["id"] for option in agent.job_options] == ["RSS News"]


def test_ads_boss_preserves_job_option_parameter_metadata(tmp_path):
    """
    Exercise the test_ads_boss_preserves_job_option_parameter_metadata regression
    scenario.
    """
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    agent = ADSBossAgent(
        pool=pool,
        config={
            "ads": {
                "job_capabilities": [
                    {
                        "name": "RSS News",
                        "description": "Fetch RSS feeds.",
                        "payload_template": {
                            "feeds": [
                                {
                                    "source": "SEC",
                                    "url": "https://www.sec.gov/news/pressreleases.rss",
                                }
                            ]
                        },
                        "parameters": [
                            {
                                "key": "feeds",
                                "label": "RSS Feed URLs",
                                "type": "feed_list",
                            }
                        ],
                    }
                ]
            }
        },
    )

    assert agent.job_options[0]["payload_template"]["feeds"][0]["source"] == "SEC"
    assert agent.job_options[0]["parameters"][0]["key"] == "feeds"
    assert agent.job_options[0]["parameters"][0]["type"] == "feed_list"
    assert agent.job_options[0]["requires_symbols"] is False


def test_ads_boss_job_option_symbol_requirement_matches_submit_rule(tmp_path):
    """
    Exercise the test_ads_boss_job_option_symbol_requirement_matches_submit_rule
    regression scenario.
    """
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "configs", "boss.agent"))
    config = read_ads_config(config_path)
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    agent = ADSBossAgent(pool=pool, config=config, config_path=config_path)

    options_by_id = {option["id"]: option for option in agent.job_options}

    assert options_by_id["YFinance EOD"]["requires_symbols"] is True
    assert options_by_id["YFinance US Market EOD"]["requires_symbols"] is False
    assert options_by_id["TWSE Market EOD"]["requires_symbols"] is False
    assert options_by_id["RSS News"]["requires_symbols"] is False


def test_ads_boss_config_exposes_only_configured_job_caps(tmp_path):
    """
    Exercise the test_ads_boss_config_exposes_only_configured_job_caps regression
    scenario.
    """
    config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "configs", "boss.agent"))
    config = read_ads_config(config_path)
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    agent = ADSBossAgent(pool=pool, config=config, config_path=config_path)

    assert [option["id"] for option in agent.job_options] == [
        "US Listed Sec to security master",
        "US Filing Bulk",
        "US Filing Mapping",
        "YFinance EOD",
        "YFinance US Market EOD",
        "TWSE Market EOD",
        "RSS News",
    ]


def test_ads_boss_plaza_status_reports_not_configured_when_missing(tmp_path):
    """
    Exercise the test_ads_boss_plaza_status_reports_not_configured_when_missing
    regression scenario.
    """
    _agent, client = build_client(tmp_path)

    response = client.get("/api/plaza/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["connection_status"] == "not_configured"
    assert payload["plaza_url"] == ""


def test_ads_boss_plaza_connect_updates_runtime_state(tmp_path):
    """
    Exercise the test_ads_boss_plaza_connect_updates_runtime_state regression
    scenario.
    """
    agent, client = build_client(tmp_path)

    class FakeResponse:
        """Response model for fake payloads."""
        status_code = 200
        text = "ok"

    def fake_register(*_args, **_kwargs):
        """Handle fake register."""
        agent.plaza_token = "demo-token"
        agent.last_plaza_heartbeat_at = time.time()
        agent.agent_id = "boss-1"
        return FakeResponse()

    with patch.object(agent, "register", side_effect=fake_register):
        response = client.post(
            "/api/plaza/connect",
            json={"plaza_url": "http://127.0.0.1:8211"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["plaza_url"] == "http://127.0.0.1:8211"
    assert payload["plaza_status"]["connection_status"] == "connected"
    assert agent.plaza_url == "http://127.0.0.1:8211"
    assert agent.agent_id == "boss-1"


def test_ads_boss_submit_uses_default_dispatcher_address(tmp_path):
    """
    Exercise the test_ads_boss_submit_uses_default_dispatcher_address regression
    scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")

    with patch.object(agent, "UsePractice", return_value={"status": "success", "job": {"id": "job-1"}}) as mocked:
        response = client.post(
            "/api/jobs/submit",
            json={
                "required_capability": "IEX EOD",
                "symbols": ["MSFT"],
                "priority": 25,
                "payload": {"symbol": "MSFT"},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    mocked.assert_called_once()
    args, kwargs = mocked.call_args
    assert args[0] == "ads-submit-job"
    assert args[1]["required_capability"] == "IEX EOD"
    assert args[1]["priority"] == 25
    assert kwargs["pit_address"] == "http://127.0.0.1:9070"


def test_ads_boss_can_create_and_list_scheduled_jobs(tmp_path):
    """
    Exercise the test_ads_boss_can_create_and_list_scheduled_jobs regression
    scenario.
    """
    _agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")

    create_response = client.post(
        "/api/schedules",
        json={
            "required_capability": "YFinance EOD",
            "symbols": ["MSFT"],
            "payload": {"symbol": "MSFT"},
            "scheduled_for": "2026-03-28T10:00:00+00:00",
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["schedule"]
    assert created["status"] == "scheduled"
    assert created["required_capability"] == "YFinance EOD"

    list_response = client.get("/api/schedules")

    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["count"] == 1
    assert payload["schedules"][0]["id"] == created["id"]
    assert payload["schedules"][0]["symbols"] == ["MSFT"]


def test_ads_boss_persists_null_for_unset_schedule_timestamps(tmp_path):
    """
    Exercise the test_ads_boss_persists_null_for_unset_schedule_timestamps
    regression scenario.
    """
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    agent = ADSBossAgent(pool=pool, dispatcher_address="http://127.0.0.1:9070")

    class RecordingPool:
        """Represent a recording pool."""
        def __init__(self):
            """Initialize the recording pool."""
            self.rows = []

        def _Insert(self, table_name, data):
            """Internal helper for insert."""
            self.rows.append((table_name, dict(data)))
            return True

    agent.pool = RecordingPool()

    result = agent.create_schedule(
        BossScheduleJobRequest(
            required_capability="YFinance EOD",
            symbols=["MSFT"],
            payload={"symbol": "MSFT"},
            scheduled_for="2026-03-28T10:00:00+00:00",
        )
    )

    assert result["status"] == "success"
    assert result["schedule"]["issued_at"] == ""
    inserted = agent.pool.rows[0][1]
    assert inserted["scheduled_for"] == "2026-03-28T10:00:00+00:00"
    assert inserted["issued_at"] is None
    assert inserted["last_attempted_at"] is None


def test_ads_boss_normalizes_datetime_schedule_timestamps(tmp_path):
    """
    Exercise the test_ads_boss_normalizes_datetime_schedule_timestamps regression
    scenario.
    """
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    agent = ADSBossAgent(pool=pool, dispatcher_address="http://127.0.0.1:9070")
    row = {
        "id": "ads-boss-schedule:1",
        "required_capability": "YFinance EOD",
        "symbols": ["MSFT"],
        "scheduled_for": datetime(2026, 3, 28, 10, 0, tzinfo=timezone.utc),
        "issued_at": datetime(2026, 3, 28, 10, 5, tzinfo=timezone.utc),
        "last_attempted_at": None,
        "created_at": datetime(2026, 3, 28, 9, 59, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 28, 10, 6, tzinfo=timezone.utc),
    }

    normalized = agent._normalize_schedule_row(row)

    assert normalized["scheduled_for"] == "2026-03-28T10:00:00+00:00"
    assert normalized["issued_at"] == "2026-03-28T10:05:00+00:00"
    assert normalized["last_attempted_at"] == ""
    assert normalized["created_at"] == "2026-03-28T09:59:00+00:00"
    assert normalized["updated_at"] == "2026-03-28T10:06:00+00:00"


def test_ads_boss_can_create_weekly_recurring_schedule(tmp_path):
    """
    Exercise the test_ads_boss_can_create_weekly_recurring_schedule regression
    scenario.
    """
    _agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")

    create_response = client.post(
        "/api/schedules",
        json={
            "required_capability": "news",
            "symbols": ["AAPL"],
            "payload": {"symbol": "AAPL"},
            "repeat_frequency": "weekly",
            "schedule_timezone": "Asia/Shanghai",
            "schedule_times": ["09:30", "15:45"],
            "schedule_weekdays": ["mon", "wed", "fri"],
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["schedule"]
    assert created["repeat_frequency"] == "weekly"
    assert created["schedule_timezone"] == "Asia/Shanghai"
    assert created["schedule_time"] == "09:30"
    assert created["schedule_times"] == ["09:30", "15:45"]
    assert created["schedule_weekdays"] == ["mon", "wed", "fri"]
    assert created["status"] == "scheduled"
    assert created["scheduled_for"]


def test_ads_boss_can_create_monthly_schedule_with_multiple_days(tmp_path):
    """
    Exercise the test_ads_boss_can_create_monthly_schedule_with_multiple_days
    regression scenario.
    """
    _agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")

    create_response = client.post(
        "/api/schedules",
        json={
            "required_capability": "news",
            "symbols": ["NVDA"],
            "payload": {"symbol": "NVDA"},
            "repeat_frequency": "monthly",
            "schedule_timezone": "UTC",
            "schedule_times": ["08:00", "18:30"],
            "schedule_days_of_month": [1, 15, 31],
        },
    )

    assert create_response.status_code == 200
    created = create_response.json()["schedule"]
    assert created["repeat_frequency"] == "monthly"
    assert created["schedule_time"] == "08:00"
    assert created["schedule_times"] == ["08:00", "18:30"]
    assert created["schedule_day_of_month"] == 1
    assert created["schedule_days_of_month"] == [1, 15, 31]
    assert created["status"] == "scheduled"
    assert created["scheduled_for"]


def test_ads_boss_compute_next_occurrence_supports_multiple_run_times(tmp_path):
    """
    Exercise the test_ads_boss_compute_next_occurrence_supports_multiple_run_times
    regression scenario.
    """
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    agent = ADSBossAgent(pool=pool, dispatcher_address="http://127.0.0.1:9070")

    next_occurrence = agent._compute_next_occurrence(
        repeat_frequency="daily",
        timezone_name="UTC",
        schedule_times=["09:00", "15:00"],
        weekdays=[],
        days_of_month=[],
        after=datetime(2026, 3, 29, 9, 30, tzinfo=timezone.utc),
    )

    assert next_occurrence == "2026-03-29T15:00:00+00:00"


def test_ads_boss_compute_next_occurrence_supports_multiple_month_days(tmp_path):
    """
    Exercise the test_ads_boss_compute_next_occurrence_supports_multiple_month_days
    regression scenario.
    """
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    agent = ADSBossAgent(pool=pool, dispatcher_address="http://127.0.0.1:9070")

    next_occurrence = agent._compute_next_occurrence(
        repeat_frequency="monthly",
        timezone_name="UTC",
        schedule_times=["08:00", "18:00"],
        weekdays=[],
        days_of_month=[1, 15, 31],
        after=datetime(2026, 2, 28, 8, 30, tzinfo=timezone.utc),
    )

    assert next_occurrence == "2026-02-28T18:00:00+00:00"


def test_ads_boss_schedule_control_can_issue_and_delete_schedule(tmp_path):
    """
    Exercise the test_ads_boss_schedule_control_can_issue_and_delete_schedule
    regression scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")

    create_response = client.post(
        "/api/schedules",
        json={
            "required_capability": "YFinance EOD",
            "symbols": ["MSFT"],
            "payload": {"symbol": "MSFT"},
            "scheduled_for": "2099-03-28T10:00:00+00:00",
        },
    )
    schedule_id = create_response.json()["schedule"]["id"]

    with patch.object(agent, "UsePractice", return_value={"status": "success", "job": {"id": "job-123"}}) as mocked:
        issue_response = client.post(
            f"/api/schedules/{schedule_id}/control",
            json={"action": "issue"},
        )

    assert issue_response.status_code == 200
    issue_payload = issue_response.json()
    assert issue_payload["control"]["schedule"]["status"] == "issued"
    assert issue_payload["control"]["schedule"]["dispatcher_job_id"] == "job-123"
    mocked.assert_called_once()
    args, kwargs = mocked.call_args
    assert args[0] == "ads-submit-job"
    assert kwargs["pit_address"] == "http://127.0.0.1:9070"

    delete_response = client.post(
        f"/api/schedules/{schedule_id}/control",
        json={"action": "delete"},
    )

    assert delete_response.status_code == 200
    deleted_response = client.get("/api/schedules?status=deleted")
    assert deleted_response.status_code == 200
    assert deleted_response.json()["count"] == 1
    assert deleted_response.json()["schedules"][0]["status"] == "deleted"


def test_ads_boss_submit_requires_dispatcher_address(tmp_path):
    """
    Exercise the test_ads_boss_submit_requires_dispatcher_address regression
    scenario.
    """
    _agent, client = build_client(tmp_path, dispatcher_address="")

    response = client.post(
        "/api/jobs/submit",
        json={
            "required_capability": "news",
            "symbols": ["AAPL"],
        },
    )

    assert response.status_code == 400
    assert "dispatcher_address is required" in response.json()["detail"]


def test_ads_boss_submit_rejects_symbol_required_cap_without_symbols(tmp_path):
    """
    Exercise the test_ads_boss_submit_rejects_symbol_required_cap_without_symbols
    regression scenario.
    """
    _agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")

    response = client.post(
        "/api/jobs/submit",
        json={
            "required_capability": "YFinance EOD",
            "payload": {},
        },
    )

    assert response.status_code == 400
    assert "requires at least one symbol" in response.json()["detail"]


def test_ads_boss_submit_allows_twse_market_job_without_symbols(tmp_path):
    """
    Exercise the test_ads_boss_submit_allows_twse_market_job_without_symbols
    regression scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")

    with patch.object(agent, "UsePractice", return_value={"status": "success", "job": {"id": "job-1"}}) as mocked:
        response = client.post(
            "/api/jobs/submit",
            json={
                "required_capability": "TWSE Market EOD",
                "payload": {},
            },
        )

    assert response.status_code == 200
    args, kwargs = mocked.call_args
    assert args[1]["symbols"] == []
    assert kwargs["pit_address"] == "http://127.0.0.1:9070"


def test_ads_boss_submit_infers_symbols_from_payload(tmp_path):
    """
    Exercise the test_ads_boss_submit_infers_symbols_from_payload regression
    scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")

    with patch.object(agent, "UsePractice", return_value={"status": "success", "job": {"id": "job-1"}}) as mocked:
        response = client.post(
            "/api/jobs/submit",
            json={
                "required_capability": "YFinance EOD",
                "payload": {"symbol": "msft"},
            },
        )

    assert response.status_code == 200
    args, kwargs = mocked.call_args
    assert args[1]["symbols"] == ["MSFT"]
    assert kwargs["pit_address"] == "http://127.0.0.1:9070"


def test_ads_boss_job_control_uses_default_dispatcher_address(tmp_path):
    """
    Exercise the test_ads_boss_job_control_uses_default_dispatcher_address
    regression scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")

    with patch.object(
        agent,
        "UsePractice",
        return_value={"status": "success", "action": "pause", "job": {"id": "job-1", "status": "paused"}},
    ) as mocked:
        response = client.post(
            "/api/jobs/job-1/control",
            json={"action": "pause"},
        )

    assert response.status_code == 200
    args, kwargs = mocked.call_args
    assert args[0] == "ads-control-job"
    assert args[1]["job_id"] == "job-1"
    assert args[1]["action"] == "pause"
    assert kwargs["pit_address"] == "http://127.0.0.1:9070"


def test_ads_boss_job_control_accepts_force_terminate(tmp_path):
    """
    Exercise the test_ads_boss_job_control_accepts_force_terminate regression
    scenario.
    """
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")

    with patch.object(
        agent,
        "UsePractice",
        return_value={"status": "success", "action": "force_terminate", "job": {"id": "job-1", "status": "failed"}},
    ) as mocked:
        response = client.post(
            "/api/jobs/job-1/control",
            json={"action": "force_terminate", "reason": "Boss requested hard stop"},
        )

    assert response.status_code == 200
    args, kwargs = mocked.call_args
    assert args[0] == "ads-control-job"
    assert args[1]["job_id"] == "job-1"
    assert args[1]["action"] == "force_terminate"
    assert args[1]["reason"] == "Boss requested hard stop"
    assert kwargs["pit_address"] == "http://127.0.0.1:9070"


def test_ads_boss_db_viewer_falls_back_to_pool_practices_when_custom_practices_are_missing(tmp_path):
    """
    Exercise the test_ads_boss_db_viewer_falls_back_to_pool_practices_when_custom_pr
    actices_are_missing regression scenario.
    """
    agent, _client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9070")

    def fake_use_practice(practice_id, payload=None, pit_address=None, **_kwargs):
        """Handle fake use practice."""
        if practice_id == "ads-db-list-tables":
            raise HTTPException(status_code=404, detail="Practice 'ads-db-list-tables' not found")
        if practice_id == "ads-db-preview-table":
            raise HTTPException(status_code=404, detail="Practice 'ads-db-preview-table' not found")
        if practice_id == "ads-db-query":
            raise HTTPException(status_code=404, detail="Practice 'ads-db-query' not found")
        if practice_id == "pool-query":
            query = str((payload or {}).get("query") or "")
            if "sqlite_master" in query:
                return [("ads_jobs",), ("ads_daily_price",)]
            if query.startswith("PRAGMA table_info(ads_jobs)"):
                return [
                    (0, "id", "TEXT", 0, None, 1),
                    (1, "status", "TEXT", 0, None, 0),
                ]
            if query.startswith("SELECT * FROM ads_jobs"):
                return [("job-1", "queued")]
            if query.startswith("SELECT COUNT(*) FROM ads_jobs"):
                return [(1,)]
            if query.startswith("SELECT id, status FROM ads_jobs"):
                return [("job-1", "queued")]
        raise AssertionError(f"Unexpected practice call: {practice_id}")

    with patch.object(agent, "UsePractice", side_effect=fake_use_practice):
        tables = agent.list_db_tables_via_dispatcher()
        preview = agent.preview_db_table_via_dispatcher(
            BossDbTableRequest(
                dispatcher_address="http://127.0.0.1:9070",
                table_name="ads_jobs",
                limit=10,
                offset=0,
            )
        )
        query = agent.query_db_via_dispatcher(
            BossDbQueryRequest(
                dispatcher_address="http://127.0.0.1:9070",
                sql="SELECT id, status FROM ads_jobs",
                limit=10,
            )
        )

    assert any(table["name"] == "ads_jobs" for table in tables["tables"])
    assert preview["columns"] == ["id", "status"]
    assert preview["rows"][0]["id"] == "job-1"
    assert query["columns"] == ["column_1", "column_2"]
    assert query["rows"][0]["column_1"] == "job-1"


def test_ads_boss_submit_issues_job_to_live_dispatcher(tmp_path):
    """
    Exercise the test_ads_boss_submit_issues_job_to_live_dispatcher regression
    scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
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

    dispatcher, dispatcher_server, dispatcher_thread = start_agent_thread(str(dispatcher_config))
    _agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9073")

    try:
        response = client.post(
            "/api/jobs/submit",
            json={
                "required_capability": "news",
                "symbols": ["AAPL"],
                "payload": {"symbol": "AAPL"},
                "source_url": "https://example.com/feed",
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "success"
        jobs = dispatcher.pool._GetTableData(TABLE_JOBS)
        assert len(jobs) == 1
        assert jobs[0]["required_capability"] == "news"
        assert jobs[0]["symbols"] == ["AAPL"]
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_ads_boss_jobs_api_reads_claimed_job_from_live_dispatcher(tmp_path):
    """
    Exercise the test_ads_boss_jobs_api_reads_claimed_job_from_live_dispatcher
    regression scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
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
    _agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9074")

    try:
        submission = dispatcher.submit_job(
            required_capability="news",
            symbols=["AAPL"],
            payload={"symbol": "AAPL"},
        )
        job_id = submission["job"]["id"]

        claim = dispatcher.claim_job(worker_id="worker-a", capabilities=["news"])
        assert claim["job"]["id"] == job_id
        assert claim["job"]["status"] == "claimed"

        jobs_response = client.get("/api/jobs")
        assert jobs_response.status_code == 200
        jobs_payload = jobs_response.json()
        assert jobs_payload["count"] == 1
        assert jobs_payload["jobs"][0]["id"] == job_id
        assert jobs_payload["jobs"][0]["status"] == "claimed"
        assert jobs_payload["jobs"][0]["claimed_by"] == "worker-a"

        claimed_response = client.get("/api/jobs?status=claimed")
        assert claimed_response.status_code == 200
        claimed_payload = claimed_response.json()
        assert claimed_payload["count"] == 1
        assert claimed_payload["jobs"][0]["id"] == job_id

        detail_response = client.get(f"/api/jobs/{job_id}")
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["job"]["id"] == job_id
        assert detail_payload["job"]["status"] == "claimed"
        assert detail_payload["job"]["claimed_by"] == "worker-a"
        assert detail_payload["job"]["claimed_at"]
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_ads_boss_can_pause_and_delete_job_via_live_dispatcher(tmp_path):
    """
    Exercise the test_ads_boss_can_pause_and_delete_job_via_live_dispatcher
    regression scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
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

    dispatcher, dispatcher_server, dispatcher_thread = start_agent_thread(str(dispatcher_config))
    _agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9076")

    try:
        submission = dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})
        job_id = submission["job"]["id"]

        pause_response = client.post(
            f"/api/jobs/{job_id}/control",
            json={"action": "pause"},
        )
        assert pause_response.status_code == 200
        paused_rows = dispatcher.pool._GetTableData(TABLE_JOBS, job_id)
        paused_rows.sort(key=lambda row: row["updated_at"], reverse=True)
        assert paused_rows[0]["status"] == "paused"

        delete_response = client.post(
            f"/api/jobs/{job_id}/control",
            json={"action": "delete"},
        )
        assert delete_response.status_code == 200
        deleted_rows = dispatcher.pool._GetTableData(TABLE_JOBS, job_id)
        deleted_rows.sort(key=lambda row: row["updated_at"], reverse=True)
        assert deleted_rows[0]["status"] == "deleted"

        jobs_response = client.get("/api/jobs")
        assert jobs_response.status_code == 200
        assert jobs_response.json()["count"] == 0

        deleted_response = client.get("/api/jobs?status=deleted")
        assert deleted_response.status_code == 200
        assert deleted_response.json()["count"] == 1
        assert deleted_response.json()["jobs"][0]["id"] == job_id
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_ads_boss_can_stop_resume_and_cancel_claimed_job_via_live_dispatcher(tmp_path):
    """
    Exercise the
    test_ads_boss_can_stop_resume_and_cancel_claimed_job_via_live_dispatcher
    regression scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
    dispatcher_config.write_text(
        f"""
{{
  "name": "ADSDispatcher",
  "host": "127.0.0.1",
  "port": 9078,
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
    _agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9078")

    try:
        submission = dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})
        job_id = submission["job"]["id"]
        dispatcher.claim_job(worker_id="worker-a", capabilities=["news"])

        stop_response = client.post(
            f"/api/jobs/{job_id}/control",
            json={"action": "stop", "reason": "Operator requested stop"},
        )
        assert stop_response.status_code == 200
        stopping_rows = dispatcher.pool._GetTableData(TABLE_JOBS, job_id)
        stopping_rows.sort(key=lambda row: row["updated_at"], reverse=True)
        assert stopping_rows[0]["status"] == "stopping"

        dispatcher.post_job_result(
            JobResult(
                job_id=job_id,
                worker_id="worker-a",
                status="stopped",
                result_summary={"stopped": True},
                error="ADS job was stopped by the boss.",
            )
        )

        resume_response = client.post(
            f"/api/jobs/{job_id}/control",
            json={"action": "resume"},
        )
        assert resume_response.status_code == 200
        resumed_rows = dispatcher.pool._GetTableData(TABLE_JOBS, job_id)
        resumed_rows.sort(key=lambda row: row["updated_at"], reverse=True)
        assert resumed_rows[0]["status"] == "queued"

        cancel_response = client.post(
            f"/api/jobs/{job_id}/control",
            json={"action": "cancel"},
        )
        assert cancel_response.status_code == 200
        cancelled_rows = dispatcher.pool._GetTableData(TABLE_JOBS, job_id)
        cancelled_rows.sort(key=lambda row: row["updated_at"], reverse=True)
        assert cancelled_rows[0]["status"] == "cancelled"

        jobs_response = client.get("/api/jobs")
        assert jobs_response.status_code == 200
        assert jobs_response.json()["count"] == 1
        assert jobs_response.json()["jobs"][0]["id"] == job_id
        assert jobs_response.json()["jobs"][0]["status"] == "cancelled"

        cancelled_response = client.get("/api/jobs?status=cancelled")
        assert cancelled_response.status_code == 200
        assert cancelled_response.json()["count"] == 1
        assert cancelled_response.json()["jobs"][0]["id"] == job_id
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_ads_boss_can_force_terminate_claimed_job_and_ignore_late_result(tmp_path):
    """
    Exercise the
    test_ads_boss_can_force_terminate_claimed_job_and_ignore_late_result regression
    scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
    dispatcher_config.write_text(
        f"""
{{
  "name": "ADSDispatcher",
  "host": "127.0.0.1",
  "port": 9088,
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
    _agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9088")

    try:
        submission = dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})
        job_id = submission["job"]["id"]
        dispatcher.claim_job(worker_id="worker-a", capabilities=["news"])

        terminate_response = client.post(
            f"/api/jobs/{job_id}/control",
            json={"action": "force_terminate", "reason": "Boss requested hard stop"},
        )
        assert terminate_response.status_code == 200
        terminated_rows = dispatcher.pool._GetTableData(TABLE_JOBS, job_id)
        terminated_rows.sort(key=lambda row: row["updated_at"], reverse=True)
        assert terminated_rows[0]["status"] == "failed"
        assert terminated_rows[0]["error"] == "Boss requested hard stop"
        assert terminated_rows[0]["result_summary"]["force_terminated"] is True
        assert terminated_rows[0]["metadata"]["boss_control"]["effective_action"] == "force_terminate"

        late_result = dispatcher.post_job_result(
            JobResult(
                job_id=job_id,
                worker_id="worker-a",
                status="completed",
                result_summary={"rows": 25},
            )
        )
        assert late_result["ignored"] is True

        rows_after_result = dispatcher.pool._GetTableData(TABLE_JOBS, job_id)
        rows_after_result.sort(key=lambda row: row["updated_at"], reverse=True)
        assert rows_after_result[0]["status"] == "failed"
        assert rows_after_result[0]["result_summary"]["force_terminated"] is True
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_ads_boss_rejects_force_terminate_for_queued_job(tmp_path):
    """
    Exercise the test_ads_boss_rejects_force_terminate_for_queued_job regression
    scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
    dispatcher_config.write_text(
        f"""
{{
  "name": "ADSDispatcher",
  "host": "127.0.0.1",
  "port": 9089,
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
    _agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9089")

    try:
        submission = dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})
        job_id = submission["job"]["id"]

        terminate_response = client.post(
            f"/api/jobs/{job_id}/control",
            json={"action": "force_terminate", "reason": "Boss requested hard stop"},
        )
        assert terminate_response.status_code == 400
        assert terminate_response.json()["detail"] == "Only claimed or working jobs can be force terminated."

        queued_rows = dispatcher.pool._GetTableData(TABLE_JOBS, job_id)
        queued_rows.sort(key=lambda row: row["updated_at"], reverse=True)
        assert queued_rows[0]["status"] == "queued"
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_ads_boss_db_viewer_reads_tables_and_queries_live_dispatcher(tmp_path):
    """
    Exercise the test_ads_boss_db_viewer_reads_tables_and_queries_live_dispatcher
    regression scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
    dispatcher_config.write_text(
        f"""
{{
  "name": "ADSDispatcher",
  "host": "127.0.0.1",
  "port": 9077,
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
    _agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9077")

    try:
        dispatcher.submit_job(required_capability="news", symbols=["AAPL"], payload={"symbol": "AAPL"})

        tables_response = client.get("/api/db/tables")
        assert tables_response.status_code == 200
        tables_payload = tables_response.json()
        assert any(table["name"] == TABLE_JOBS for table in tables_payload["tables"])

        preview_response = client.get(f"/api/db/table?table_name={TABLE_JOBS}&limit=10")
        assert preview_response.status_code == 200
        preview_payload = preview_response.json()
        assert preview_payload["table_name"] == TABLE_JOBS
        assert preview_payload["count"] == 1

        query_response = client.post(
            "/api/db/query",
            json={"sql": "SELECT id, status FROM ads_jobs ORDER BY created_at DESC", "limit": 10},
        )
        assert query_response.status_code == 200
        query_payload = query_response.json()
        assert query_payload["columns"] == ["id", "status"]
        assert query_payload["count"] == 1
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_ads_boss_jobs_api_reads_list_and_detail_from_live_dispatcher(tmp_path):
    """
    Exercise the test_ads_boss_jobs_api_reads_list_and_detail_from_live_dispatcher
    regression scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
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
    _agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9075")

    try:
        submission = dispatcher.submit_job(
            required_capability="YFinance EOD",
            symbols=["MSFT"],
            payload={"symbol": "MSFT"},
            source_url="https://finance.yahoo.com/quote/MSFT/history",
        )
        job_id = submission["job"]["id"]
        dispatcher.post_job_result(
            JobResult(
                job_id=job_id,
                worker_id="worker-a",
                status="completed",
                raw_payload={"provider": "yfinance", "requests": [{"symbol": "MSFT"}]},
                result_summary={"rows": 0},
            )
        )
        assert dispatcher.pool._GetTableData(TABLE_JOBS, job_id) == []
        archived_rows = dispatcher.pool._GetTableData(TABLE_JOB_ARCHIVE, job_id)
        assert len(archived_rows) == 1
        assert archived_rows[0]["status"] == "completed"

        jobs_response = client.get("/api/jobs")
        assert jobs_response.status_code == 200
        jobs_payload = jobs_response.json()
        assert jobs_payload["count"] == 1
        assert jobs_payload["jobs"][0]["id"] == job_id
        assert jobs_payload["jobs"][0]["status"] == "completed"

        detail_response = client.get(f"/api/jobs/{job_id}")
        assert detail_response.status_code == 200
        detail_payload = detail_response.json()
        assert detail_payload["job"]["id"] == job_id
        assert detail_payload["job"]["required_capability"] == "yfinance eod"
        assert len(detail_payload["raw_records"]) == 1
        assert detail_payload["raw_records"][0]["payload"]["provider"] == "yfinance"
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_ads_boss_process_due_schedules_issues_job_to_live_dispatcher(tmp_path):
    """
    Exercise the test_ads_boss_process_due_schedules_issues_job_to_live_dispatcher
    regression scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
    dispatcher_config.write_text(
        f"""
{{
  "name": "ADSDispatcher",
  "host": "127.0.0.1",
  "port": 9078,
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
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9078")

    try:
        scheduled_for = (datetime.now(timezone.utc) + timedelta(seconds=1.0)).isoformat()
        create_response = client.post(
            "/api/schedules",
            json={
                "required_capability": "news",
                "symbols": ["AAPL"],
                "payload": {"symbol": "AAPL"},
                "scheduled_for": scheduled_for,
            },
        )
        assert create_response.status_code == 200
        schedule_id = create_response.json()["schedule"]["id"]

        before_due = agent.process_due_schedules()
        assert before_due["issued_count"] == 0
        assert dispatcher.pool._GetTableData(TABLE_JOBS) == []

        time.sleep(1.2)

        after_due = agent.process_due_schedules()
        assert after_due["issued_count"] == 1

        dispatcher_jobs = dispatcher.pool._GetTableData(TABLE_JOBS)
        assert len(dispatcher_jobs) == 1
        assert dispatcher_jobs[0]["required_capability"] == "news"
        assert dispatcher_jobs[0]["symbols"] == ["AAPL"]

        schedules_response = client.get("/api/schedules")
        assert schedules_response.status_code == 200
        schedule_rows = schedules_response.json()["schedules"]
        assert schedule_rows[0]["id"] == schedule_id
        assert schedule_rows[0]["status"] == "issued"
        assert schedule_rows[0]["dispatcher_job_id"]
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])


def test_ads_boss_seeds_configured_daily_archive_schedule_once(tmp_path):
    """
    Exercise the ADS config-seeded daily archive schedule regression scenario.
    """
    pool = SQLitePool("ads_boss_pool", "ADS boss test pool", str(tmp_path / "boss.sqlite"))
    config = {
        "ads": {
            "scheduled_jobs": [
                {
                    "id": "ads-boss-schedule:daily-job-archive",
                    "name": "Daily Job Archive (3AM)",
                    "required_capability": "Daily Job Archive",
                    "repeat_frequency": "daily",
                    "schedule_timezone": "Asia/Shanghai",
                    "schedule_times": ["03:00"],
                    "priority": 80,
                    "payload": {"batch_size": 1000},
                }
            ]
        }
    }

    agent = ADSBossAgent(
        pool=pool,
        dispatcher_address="http://127.0.0.1:9070",
        config=config,
    )

    seeded = agent._get_schedule_row("ads-boss-schedule:daily-job-archive")
    assert seeded["name"] == "Daily Job Archive (3AM)"
    assert seeded["required_capability"] == "Daily Job Archive"
    assert seeded["repeat_frequency"] == "daily"
    assert seeded["schedule_timezone"] == "Asia/Shanghai"
    assert seeded["schedule_time"] == "03:00"
    assert seeded["schedule_times"] == ["03:00"]
    assert seeded["priority"] == 80
    assert seeded["payload"] == {"batch_size": 1000}
    assert seeded["metadata"]["seeded_from_config"] is True
    assert seeded["metadata"]["config_schedule_id"] == "ads-boss-schedule:daily-job-archive"
    assert parse_datetime_value(seeded["scheduled_for"]) > datetime.min.replace(tzinfo=timezone.utc)
    assert len(pool._GetTableData(TABLE_SCHEDULED_JOBS, "ads-boss-schedule:daily-job-archive")) == 1

    ADSBossAgent(
        pool=pool,
        dispatcher_address="http://127.0.0.1:9070",
        config=config,
    )

    assert len(pool._GetTableData(TABLE_SCHEDULED_JOBS, "ads-boss-schedule:daily-job-archive")) == 1


def test_ads_boss_recurring_schedule_advances_after_issue(tmp_path):
    """
    Exercise the test_ads_boss_recurring_schedule_advances_after_issue regression
    scenario.
    """
    dispatcher_config = tmp_path / "dispatcher.agent"
    dispatcher_db = tmp_path / "dispatcher.sqlite"
    dispatcher_config.write_text(
        f"""
{{
  "name": "ADSDispatcher",
  "host": "127.0.0.1",
  "port": 9079,
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
    agent, client = build_client(tmp_path, dispatcher_address="http://127.0.0.1:9079")

    try:
        create_response = client.post(
            "/api/schedules",
            json={
                "required_capability": "news",
                "symbols": ["AAPL"],
                "payload": {"symbol": "AAPL"},
                "repeat_frequency": "daily",
                "schedule_timezone": "UTC",
                "schedule_times": ["00:00", "12:00"],
            },
        )
        assert create_response.status_code == 200
        schedule = create_response.json()["schedule"]
        schedule_id = schedule["id"]

        forced_due = dict(agent._get_schedule_row(schedule_id))
        forced_due["scheduled_for"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        saved_due = agent._save_schedule_row(forced_due)

        result = agent.process_due_schedules()
        assert result["issued_count"] == 1

        updated = agent._get_schedule_row(schedule_id)
        assert updated["status"] == "scheduled"
        assert updated["repeat_frequency"] == "daily"
        assert updated["schedule_times"] == ["00:00", "12:00"]
        assert updated["issued_at"]
        assert updated["dispatcher_job_id"]
        assert parse_datetime_value(updated["scheduled_for"]) > parse_datetime_value(saved_due["scheduled_for"])

        dispatcher_jobs = dispatcher.pool._GetTableData(TABLE_JOBS)
        assert len(dispatcher_jobs) == 1
        assert dispatcher_jobs[0]["required_capability"] == "news"
    finally:
        stop_servers([(dispatcher_server, dispatcher_thread)])
