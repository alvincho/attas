"""
Regression tests for Dispatcher Boss.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_create_and_issue_schedule_uses_targets_and_tags_metadata`,
`test_normalize_submit_payload_maps_symbols_alias_to_targets`,
`test_query_db_via_dispatcher_calls_read_only_query_practice`, and
`test_normalize_job_options_preserves_default_priority`, helping guard against
regressions as the packages evolve.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.dispatcher.boss import (
    BossDbQueryRequest,
    BossScheduleJobRequest,
    BossSubmitJobRequest,
    DispatcherBossAgent,
    TABLE_JOB_ARCHIVE,
    TABLE_SCHEDULED_JOBS,
)
from prompits.dispatcher.runtime import parse_datetime_value
from prompits.pools.sqlite import SQLitePool


def test_normalize_job_options_preserves_default_priority():
    """
    Exercise the test_normalize_job_options_preserves_default_priority regression
    scenario.
    """
    agent = DispatcherBossAgent.__new__(DispatcherBossAgent)

    options = agent._normalize_job_option_entries(
        [
            {
                "name": "UPU WNS Catalog",
                "description": "Scan the UPU WNS catalog.",
                "default_priority": 100,
            },
            {
                "name": "UPU WNS Listing",
                "description": "Fetch one listing.",
                "default_priority": "110",
            },
        ]
    )

    assert options == [
        {
            "id": "UPU WNS Catalog",
            "label": "UPU WNS Catalog",
            "description": "Scan the UPU WNS catalog.",
            "default_priority": 100,
        },
        {
            "id": "UPU WNS Listing",
            "label": "UPU WNS Listing",
            "description": "Fetch one listing.",
            "default_priority": 110,
        },
    ]


def test_monitor_summary_classifies_worker_health_from_heartbeat_age():
    """
    Exercise the test_monitor_summary_classifies_worker_health_from_heartbeat_age
    regression scenario.
    """
    agent = DispatcherBossAgent.__new__(DispatcherBossAgent)
    now = datetime.now(timezone.utc)

    def snapshot(*, dispatcher_address: str):
        """Return the snapshot."""
        return {
            "tables": {
                "dispatcher_jobs": {
                    "rows": [
                        {"id": "job-1", "status": "queued", "claimed_by": ""},
                        {"id": "job-2", "status": "claimed", "claimed_by": "worker-online"},
                    ]
                },
                "dispatcher_worker_capabilities": {
                    "rows": [
                        {
                            "worker_id": "worker-online",
                            "name": "Online Worker",
                            "status": "working",
                            "last_seen_at": now.isoformat(),
                            "metadata": {"heartbeat": {"heartbeat_interval_sec": 15}},
                        },
                        {
                            "worker_id": "worker-stale",
                            "name": "Stale Worker",
                            "status": "online",
                            "last_seen_at": (now - timedelta(seconds=70)).isoformat(),
                            "metadata": {"heartbeat": {"heartbeat_interval_sec": 15}},
                        },
                        {
                            "worker_id": "worker-unknown",
                            "name": "Unknown Worker",
                            "status": "online",
                            "metadata": {"heartbeat": {"heartbeat_interval_sec": 15}},
                        },
                    ]
                },
                "dispatcher_worker_history": {"rows": []},
            }
        }

    agent._monitor_snapshot = snapshot

    result = agent._monitor_summary(dispatcher_address="http://127.0.0.1:8066")

    assert result["dispatcher"]["active_workers"] == 1
    assert result["dispatcher"]["worker_counts"] == {
        "online": 1,
        "stale": 1,
        "offline": 1,
        "total": 3,
    }

    workers = {row["worker_id"]: row for row in result["workers"]}
    assert workers["worker-online"]["health_status"] == "online"
    assert workers["worker-online"]["heartbeat_age_sec"] is not None
    assert workers["worker-stale"]["health_status"] == "stale"
    assert workers["worker-stale"]["heartbeat_age_sec"] is not None
    assert workers["worker-unknown"]["health_status"] == "offline"
    assert workers["worker-unknown"]["heartbeat_age_sec"] is None


def test_list_jobs_scans_beyond_first_preview_page_when_filters_are_active():
    """
    Exercise the
    test_list_jobs_scans_beyond_first_preview_page_when_filters_are_active
    regression scenario.
    """
    agent = DispatcherBossAgent.__new__(DispatcherBossAgent)
    first_page_rows = [
        {"id": f"job-page-{index}", "required_capability": "upu wns page", "status": "queued"}
        for index in range(500)
    ]

    def preview(dispatcher_address: str, table_name: str, *, limit: int = 20, offset: int = 0):
        """Preview the value."""
        if table_name == TABLE_JOB_ARCHIVE:
            return {"rows": [], "count": 0, "total_rows": 0}
        assert table_name == "dispatcher_jobs"
        if offset == 0:
            return {
                "rows": first_page_rows,
                "count": len(first_page_rows),
                "total_rows": 501,
            }
        if offset == 500:
            return {
                "rows": [
                    {"id": "job-catalog-latest", "required_capability": "upu wns catalog", "status": "claimed"},
                ],
                "count": 1,
                "total_rows": 501,
            }
        return {"rows": [], "count": 0, "total_rows": 501}

    agent._preview_dispatcher_table = preview

    result = agent._list_jobs(
        dispatcher_address="http://127.0.0.1:8066",
        capability="catalog",
    )

    assert [row["id"] for row in result["jobs"]] == ["job-catalog-latest"]


def test_list_jobs_includes_completed_archive_rows():
    """Completed archive rows should remain visible in the boss job list."""
    agent = DispatcherBossAgent.__new__(DispatcherBossAgent)

    def preview(dispatcher_address: str, table_name: str, *, limit: int = 20, offset: int = 0):
        """Preview dispatcher rows."""
        if table_name == "dispatcher_jobs":
            return {"rows": [], "count": 0, "total_rows": 0}
        if table_name == TABLE_JOB_ARCHIVE:
            return {
                "rows": [
                    {"id": "job-completed", "required_capability": "upu wns listing", "status": "completed"},
                ],
                "count": 1,
                "total_rows": 1,
            }
        return {"rows": [], "count": 0, "total_rows": 0}

    agent._preview_dispatcher_table = preview

    result = agent._list_jobs(dispatcher_address="http://127.0.0.1:8066", status="completed")

    assert [row["id"] for row in result["jobs"]] == ["job-completed"]


def test_job_detail_reads_completed_job_from_archive():
    """Job detail should still resolve jobs that have been archived out of the active queue."""
    agent = DispatcherBossAgent.__new__(DispatcherBossAgent)

    def preview(dispatcher_address: str, table_name: str, *, limit: int = 20, offset: int = 0):
        """Preview dispatcher rows."""
        if table_name == "dispatcher_jobs":
            return {"rows": [], "count": 0, "total_rows": 0}
        if table_name == TABLE_JOB_ARCHIVE:
            return {
                "rows": [
                    {"id": "job-completed", "required_capability": "upu wns listing", "status": "completed"},
                ],
                "count": 1,
                "total_rows": 1,
            }
        if table_name == "dispatcher_raw_payloads":
            return {"rows": [], "count": 0, "total_rows": 0}
        if table_name == "dispatcher_worker_history":
            return {"rows": [], "count": 0, "total_rows": 0}
        return {"rows": [], "count": 0, "total_rows": 0}

    agent._preview_dispatcher_table = preview

    result = agent._job_detail(dispatcher_address="http://127.0.0.1:8066", job_id="job-completed")

    assert result["job"]["id"] == "job-completed"
    assert result["job"]["status"] == "completed"


def test_plaza_directory_discovers_dispatchers_for_selected_party():
    """
    Exercise the test_plaza_directory_discovers_dispatchers_for_selected_party
    regression scenario.
    """
    agent = DispatcherBossAgent.__new__(DispatcherBossAgent)
    now = datetime.now(timezone.utc)
    agent.plaza_url = "http://127.0.0.1:8011"
    agent.plaza_token = "token"
    agent.dispatcher_address = ""
    agent.dispatcher_party = "Collectible"
    agent.name = "CollectiblesBoss"
    agent.agent_id = "boss-1"
    agent.agent_card = {"party": "Collectible", "meta": {}}
    agent.last_plaza_heartbeat_at = now.timestamp()
    agent._plaza_connection_error = ""

    dispatcher_rows = [
        {
            "agent_id": "dispatcher-collectible",
            "name": "CollectiblesDispatcher",
            "last_active": now.timestamp(),
            "card": {
                "address": "http://127.0.0.1:8066",
                "party": "Collectible",
                "role": "dispatcher",
                "tags": ["dispatcher"],
                "practices": [{"id": "dispatcher-get-job"}],
            },
        },
        {
            "agent_id": "dispatcher-prompits",
            "name": "GenericDispatcher",
            "last_active": now.timestamp() - 60,
            "card": {
                "address": "http://127.0.0.1:8060",
                "party": "Prompits",
                "role": "dispatcher",
                "tags": ["dispatcher"],
                "practices": [{"id": "dispatcher-get-job"}],
            },
        },
    ]

    agent.search = lambda **_kwargs: dispatcher_rows

    directory = agent._plaza_dispatcher_directory(dispatcher_party="Collectible")

    assert directory["dispatcher_party"] == "Collectible"
    assert directory["selected_dispatcher_address"] == "http://127.0.0.1:8066"
    assert directory["parties"] == ["Collectible", "Prompits"]
    assert [entry["address"] for entry in directory["dispatchers"]] == ["http://127.0.0.1:8066"]

    resolved = agent._resolve_dispatcher_address(dispatcher_party="Collectible")

    assert resolved == "http://127.0.0.1:8066"
    assert agent.dispatcher_address == "http://127.0.0.1:8066"


def test_normalize_submit_payload_maps_symbols_alias_to_targets():
    """
    Exercise the test_normalize_submit_payload_maps_symbols_alias_to_targets
    regression scenario.
    """
    agent = DispatcherBossAgent.__new__(DispatcherBossAgent)
    agent.dispatcher_address = "http://127.0.0.1:8066"
    agent._resolve_dispatcher_address = lambda override=None, dispatcher_party="": str(override or agent.dispatcher_address)

    payload = agent._normalize_submit_payload(
        BossSubmitJobRequest(
            required_capability="UPU WNS Listing",
            symbols=["AA001.2025"],
            payload={"refresh_item": False},
        )
    )

    assert payload["dispatcher_address"] == "http://127.0.0.1:8066"
    assert payload["targets"] == ["AA001.2025"]
    assert "symbols" not in payload


def test_create_and_issue_schedule_uses_targets_and_tags_metadata(tmp_path):
    """
    Exercise the test_create_and_issue_schedule_uses_targets_and_tags_metadata
    regression scenario.
    """
    pool = SQLitePool("dispatcher_boss_pool", "dispatcher boss pool", str(tmp_path / "boss.sqlite"))
    agent = DispatcherBossAgent(
        pool=pool,
        dispatcher_address="http://127.0.0.1:8066",
        auto_register=False,
    )

    practice_calls = []

    def fake_use_practice(practice_id, payload, pit_address=""):
        """Handle fake use practice."""
        practice_calls.append((practice_id, payload, pit_address))
        if practice_id == "dispatcher-submit-job":
            return {
                "status": "success",
                "job": {
                    "id": "job-1",
                    "required_capability": payload["required_capability"],
                    "targets": payload["targets"],
                    "status": "queued",
                },
            }
        raise AssertionError(f"Unexpected practice call: {practice_id}")

    agent.UsePractice = fake_use_practice

    created = agent.create_schedule(
        BossScheduleJobRequest(
            dispatcher_address="http://127.0.0.1:8066",
            required_capability="UPU WNS Listing",
            targets=["AA001.2025"],
            scheduled_for="2026-04-02T10:00:00+00:00",
        )
    )

    issued = agent.issue_scheduled_job(created["schedule"]["id"], force_now=True)

    assert practice_calls[0][0] == "dispatcher-submit-job"
    assert practice_calls[0][1]["targets"] == ["AA001.2025"]
    assert practice_calls[0][1]["metadata"]["boss_schedule_id"] == created["schedule"]["id"]
    assert practice_calls[0][2] == "http://127.0.0.1:8066"
    assert issued["schedule"]["status"] == "issued"
    assert issued["schedule"]["dispatcher_job_id"] == "job-1"


def test_interval_schedule_preserves_anchor_and_rounds_forward():
    """
    Exercise the interval-schedule normalization and next-occurrence regression.
    """
    next_due = DispatcherBossAgent._compute_next_occurrence(
        repeat_frequency="interval",
        timezone_name="Asia/Shanghai",
        schedule_times=[],
        weekdays=[],
        days_of_month=[],
        interval_minutes=10,
        start_at=datetime(2030, 4, 11, 18, 0, tzinfo=timezone.utc),
        after=datetime(2030, 4, 11, 18, 24, tzinfo=timezone.utc),
    )
    assert next_due == "2030-04-11T18:30:00+00:00"


def test_create_interval_schedule_records_interval_metadata(tmp_path):
    """
    Exercise the interval schedule creation regression scenario.
    """
    pool = SQLitePool("dispatcher_boss_pool", "dispatcher boss pool", str(tmp_path / "boss.sqlite"))
    agent = DispatcherBossAgent(
        pool=pool,
        dispatcher_address="http://127.0.0.1:8066",
        auto_register=False,
    )

    created = agent.create_schedule(
        BossScheduleJobRequest(
            dispatcher_address="http://127.0.0.1:8066",
            required_capability="10 Minutes Scheduled Job",
            repeat_frequency="interval",
            schedule_timezone="Asia/Shanghai",
            schedule_interval_minutes=10,
            scheduled_for="2030-04-12T02:00:00+08:00",
            priority=90,
            payload={"window_minutes": 10, "page_item_limit": 60},
        )
    )

    schedule = created["schedule"]
    assert schedule["repeat_frequency"] == "interval"
    assert schedule["schedule_interval_minutes"] == 10
    assert schedule["schedule_times"] == []
    assert schedule["metadata"]["interval_start_at"] == "2030-04-11T18:00:00+00:00"
    assert schedule["metadata"]["schedule_interval_minutes"] == 10
    assert schedule["scheduled_for"] == "2030-04-11T18:00:00+00:00"


def test_dispatcher_boss_seeds_configured_daily_archive_schedule_once(tmp_path):
    """
    Exercise the dispatcher config-seeded daily archive schedule regression scenario.
    """
    pool = SQLitePool("dispatcher_boss_pool", "dispatcher boss pool", str(tmp_path / "boss.sqlite"))
    config = {
        "dispatcher": {
            "scheduled_jobs": [
                {
                    "id": "dispatcher-boss-schedule:collectibles-daily-job-archive",
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

    agent = DispatcherBossAgent(
        pool=pool,
        dispatcher_address="http://127.0.0.1:8066",
        auto_register=False,
        config=config,
    )

    seeded = agent._get_schedule_row("dispatcher-boss-schedule:collectibles-daily-job-archive")
    assert seeded["name"] == "Daily Job Archive (3AM)"
    assert seeded["required_capability"] == "Daily Job Archive"
    assert seeded["repeat_frequency"] == "daily"
    assert seeded["schedule_timezone"] == "Asia/Shanghai"
    assert seeded["schedule_time"] == "03:00"
    assert seeded["schedule_times"] == ["03:00"]
    assert seeded["priority"] == 80
    assert seeded["payload"] == {"batch_size": 1000}
    assert seeded["metadata"]["seeded_from_config"] is True
    assert seeded["metadata"]["config_schedule_id"] == "dispatcher-boss-schedule:collectibles-daily-job-archive"
    assert parse_datetime_value(seeded["scheduled_for"]) > datetime.min.replace(tzinfo=timezone.utc)
    assert len(pool._GetTableData(TABLE_SCHEDULED_JOBS, "dispatcher-boss-schedule:collectibles-daily-job-archive")) == 1

    DispatcherBossAgent(
        pool=pool,
        dispatcher_address="http://127.0.0.1:8066",
        auto_register=False,
        config=config,
    )

    assert len(pool._GetTableData(TABLE_SCHEDULED_JOBS, "dispatcher-boss-schedule:collectibles-daily-job-archive")) == 1


def test_dispatcher_boss_seeds_configured_interval_schedule_once(tmp_path):
    """
    Exercise config-seeded interval schedules so recurring dashboard snapshots stay seeded.
    """
    pool = SQLitePool("dispatcher_boss_pool", "dispatcher boss pool", str(tmp_path / "boss.sqlite"))
    config = {
        "dispatcher": {
            "scheduled_jobs": [
                {
                    "id": "dispatcher-boss-schedule:collectibles-dashboard-snapshot",
                    "name": "Collectibles Dashboard Snapshot (Every Minute)",
                    "required_capability": "Collectibles Dashboard Snapshot",
                    "repeat_frequency": "interval",
                    "schedule_timezone": "Asia/Taipei",
                    "schedule_interval_minutes": 1,
                    "scheduled_for": "2026-01-01T00:00:00+08:00",
                    "priority": 95,
                    "payload": {},
                }
            ]
        }
    }

    agent = DispatcherBossAgent(
        pool=pool,
        dispatcher_address="http://127.0.0.1:8066",
        auto_register=False,
        config=config,
    )

    seeded = agent._get_schedule_row("dispatcher-boss-schedule:collectibles-dashboard-snapshot")
    assert seeded["name"] == "Collectibles Dashboard Snapshot (Every Minute)"
    assert seeded["required_capability"] == "Collectibles Dashboard Snapshot"
    assert seeded["repeat_frequency"] == "interval"
    assert seeded["schedule_timezone"] == "Asia/Taipei"
    assert seeded["schedule_interval_minutes"] == 1
    assert seeded["priority"] == 95
    assert seeded["payload"] == {}
    assert seeded["metadata"]["seeded_from_config"] is True
    assert seeded["metadata"]["config_schedule_id"] == "dispatcher-boss-schedule:collectibles-dashboard-snapshot"
    assert seeded["metadata"]["interval_start_at"] == "2025-12-31T16:00:00+00:00"
    assert seeded["scheduled_for"] >= seeded["metadata"]["interval_start_at"]
    assert len(pool._GetTableData(TABLE_SCHEDULED_JOBS, "dispatcher-boss-schedule:collectibles-dashboard-snapshot")) == 1

    DispatcherBossAgent(
        pool=pool,
        dispatcher_address="http://127.0.0.1:8066",
        auto_register=False,
        config=config,
    )

    assert len(pool._GetTableData(TABLE_SCHEDULED_JOBS, "dispatcher-boss-schedule:collectibles-dashboard-snapshot")) == 1


def test_issue_scheduled_job_recovers_legacy_interval_schedule_rows(tmp_path):
    """
    Legacy/custom rows that stored interval metadata without repeat_frequency
    should resume as recurring interval schedules instead of staying one-shot.
    """
    pool = SQLitePool("dispatcher_boss_pool", "dispatcher boss pool", str(tmp_path / "boss.sqlite"))
    agent = DispatcherBossAgent(
        pool=pool,
        dispatcher_address="http://127.0.0.1:8066",
        auto_register=False,
    )
    agent.ensure_schedule_tables()

    legacy_due = (datetime.now(timezone.utc) - timedelta(minutes=25)).replace(microsecond=0)
    pool._Insert(
        TABLE_SCHEDULED_JOBS,
        {
            "id": "dispatcher-boss-schedule:legacy-interval",
            "name": "eBay Daily Schedule (10m)",
            "status": "issued",
            "dispatcher_address": "http://127.0.0.1:8066",
            "repeat_frequency": "once",
            "schedule_timezone": "Asia/Shanghai",
            "schedule_time": "",
            "schedule_times": [],
            "schedule_weekdays": [],
            "schedule_day_of_month": None,
            "schedule_days_of_month": [],
            "required_capability": "eBay Daily Schedule",
            "targets": [],
            "payload": {"window_minutes": 10},
            "target_table": "",
            "source_url": "",
            "parse_rules": {},
            "capability_tags": [],
            "job_type": "run",
            "priority": 90,
            "premium": False,
            "metadata": {
                "interval_start_at": legacy_due.isoformat(),
                "schedule_interval_minutes": 10,
            },
            "scheduled_for": legacy_due.isoformat(),
            "max_attempts": 3,
            "dispatcher_job_id": "job-legacy-0",
            "issued_at": legacy_due.isoformat(),
            "last_attempted_at": legacy_due.isoformat(),
            "last_error": "",
            "issue_attempts": 1,
            "created_at": legacy_due.isoformat(),
            "updated_at": legacy_due.isoformat(),
        },
    )

    practice_calls = []

    def fake_use_practice(practice_id, payload, pit_address=""):
        """Handle fake use practice."""
        practice_calls.append((practice_id, payload, pit_address))
        if practice_id == "dispatcher-submit-job":
            return {
                "status": "success",
                "job": {
                    "id": "job-legacy-1",
                    "required_capability": payload["required_capability"],
                    "status": "queued",
                },
            }
        raise AssertionError(f"Unexpected practice call: {practice_id}")

    agent.UsePractice = fake_use_practice

    issued = agent.issue_scheduled_job("dispatcher-boss-schedule:legacy-interval")
    schedule = issued["schedule"]

    assert practice_calls[0][0] == "dispatcher-submit-job"
    assert schedule["repeat_frequency"] == "interval"
    assert schedule["status"] == "scheduled"
    assert schedule["schedule_interval_minutes"] == 10
    assert schedule["dispatcher_job_id"] == "job-legacy-1"
    assert parse_datetime_value(schedule["scheduled_for"]) > datetime.now(timezone.utc)

    stored = agent._get_schedule_row("dispatcher-boss-schedule:legacy-interval")
    assert stored["repeat_frequency"] == "interval"
    assert stored["status"] == "scheduled"


def test_query_db_via_dispatcher_calls_read_only_query_practice():
    """
    Exercise the test_query_db_via_dispatcher_calls_read_only_query_practice
    regression scenario.
    """
    agent = DispatcherBossAgent.__new__(DispatcherBossAgent)
    agent.dispatcher_address = "http://127.0.0.1:8066"
    captured = {}

    def fake_call_dispatcher(practice_id, payload, *, dispatcher_address=""):
        """Handle fake call dispatcher."""
        captured["practice_id"] = practice_id
        captured["payload"] = payload
        captured["dispatcher_address"] = dispatcher_address
        return {"status": "success", "rows": [{"count": 1}]}

    agent._call_dispatcher = fake_call_dispatcher
    agent._resolve_dispatcher_address = lambda override=None, dispatcher_party="": str(override or agent.dispatcher_address)

    response = agent.query_db_via_dispatcher(BossDbQueryRequest(sql="SELECT 1", limit=10))

    assert captured["practice_id"] == "dispatcher-db-query"
    assert captured["payload"] == {"sql": "SELECT 1", "params": None, "limit": 10}
    assert captured["dispatcher_address"] == "http://127.0.0.1:8066"
    assert response["dispatcher_address"] == "http://127.0.0.1:8066"
