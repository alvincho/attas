"""
Regression tests for SEC Job Caps.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace. These tests protect the ADS data-service
behaviors, scheduling rules, and provider integrations.

The pytest cases in this file document expected behavior through checks such as
`test_us_filing_bulk_job_cap_downloads_sec_archives_into_ads_tables`,
`test_us_filing_bulk_job_cap_reuses_recent_cached_archives`,
`test_us_filing_mapping_job_cap_maps_sec_rows_into_ads_tables`, and
`test_us_filing_mapping_job_cap_skips_company_without_symbol`, helping guard against
regressions as the packages evolve.
"""

import io
import json
import os
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from ads.agents import ADSDispatcherAgent
from ads.models import JobDetail
from ads.sec import USFilingBulkJobCap, USFilingMappingJobCap
from ads.schema import (
    TABLE_FINANCIAL_STATEMENTS,
    TABLE_FUNDAMENTALS,
    TABLE_RAW_DATA,
    TABLE_SEC_COMPANYFACTS,
    TABLE_SEC_SUBMISSIONS,
    TABLE_SECURITY_MASTER,
    ads_table_schema_map,
    ensure_ads_tables,
)
from prompits.pools.sqlite import SQLitePool


class _DummyWorker:
    """Represent a dummy worker."""
    def __init__(self, pool):
        """Initialize the dummy worker."""
        self.pool = pool
        self.dispatcher_address = ""
        self.logger = _DummyLogger()
        self.progress_updates: list[dict] = []
        self.heartbeat_events: list[dict] = []
        self._progress: dict = {}

    def update_progress(self, **kwargs):
        """Update the progress."""
        updated = dict(self._progress)
        phase = str(kwargs.get("phase") or "").strip()
        message = str(kwargs.get("message") or "").strip()
        if phase:
            updated["phase"] = phase
        if message:
            updated["message"] = message
        if kwargs.get("percent") is not None:
            updated["percent"] = kwargs["percent"]
        if kwargs.get("current") is not None:
            updated["current"] = kwargs["current"]
        if kwargs.get("total") is not None:
            updated["total"] = kwargs["total"]
        extra = kwargs.get("extra")
        if isinstance(extra, dict):
            merged_extra = dict(updated.get("extra") or {})
            merged_extra.update(extra)
            updated["extra"] = merged_extra
        self._progress = updated
        snapshot = dict(updated)
        self.progress_updates.append(snapshot)
        return snapshot

    def _send_worker_heartbeat(self, *, event_type="heartbeat"):
        """Internal helper to send the worker heartbeat."""
        heartbeat = {"event_type": event_type, **dict(self._progress)}
        self.heartbeat_events.append(heartbeat)
        return heartbeat

    def raise_if_stop_requested(self, job):
        """Handle raise if stop requested for the dummy worker."""
        return None


class _DummyLogger:
    """Represent a dummy logger."""
    def __init__(self):
        """Initialize the dummy logger."""
        self.debug_messages: list[str] = []

    def debug(self, message, *args):
        """Handle debug for the dummy logger."""
        rendered = message % args if args else str(message)
        self.debug_messages.append(rendered)


class _FakeBinaryResponse:
    """Response model for fake binary payloads."""
    def __init__(self, payload: bytes, *, url: str):
        """Initialize the fake binary response."""
        self._payload = payload
        self.url = url
        self.headers = {"Content-Length": str(len(payload))}

    def raise_for_status(self):
        """Return the raise for the status."""
        return None

    def iter_content(self, chunk_size=65536):
        """Handle iter content for the fake binary response."""
        for index in range(0, len(self._payload), chunk_size):
            yield self._payload[index:index + chunk_size]

    def close(self):
        """Handle close for the fake binary response."""
        return None


def _archive_bytes(file_payloads: dict[str, dict]) -> bytes:
    """Internal helper for archive bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_name, payload in file_payloads.items():
            archive.writestr(file_name, json.dumps(payload))
    return buffer.getvalue()


def _sample_companyfacts_payload() -> dict:
    """Internal helper to return the sample companyfacts payload."""
    return {
        "cik": 320193,
        "entityName": "Apple Inc.",
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            {
                                "end": "2026-03-31",
                                "val": 1000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "EntityPublicFloat": {
                    "units": {
                        "USD": [
                            {
                                "end": "2026-03-31",
                                "val": 2500000000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
            },
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "units": {
                        "USD": [
                            {
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "val": 1000000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "GrossProfit": {
                    "units": {
                        "USD": [
                            {
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "val": 400000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "OperatingIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "val": 250000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "NetIncomeLoss": {
                    "units": {
                        "USD": [
                            {
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "val": 200000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "Assets": {
                    "units": {
                        "USD": [
                            {
                                "end": "2026-03-31",
                                "val": 5000000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "AssetsCurrent": {
                    "units": {
                        "USD": [
                            {
                                "end": "2026-03-31",
                                "val": 1800000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "Liabilities": {
                    "units": {
                        "USD": [
                            {
                                "end": "2026-03-31",
                                "val": 2100000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "LiabilitiesCurrent": {
                    "units": {
                        "USD": [
                            {
                                "end": "2026-03-31",
                                "val": 900000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "StockholdersEquity": {
                    "units": {
                        "USD": [
                            {
                                "end": "2026-03-31",
                                "val": 2900000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "CashAndCashEquivalentsAtCarryingValue": {
                    "units": {
                        "USD": [
                            {
                                "end": "2026-03-31",
                                "val": 700000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "NetCashProvidedByUsedInOperatingActivities": {
                    "units": {
                        "USD": [
                            {
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "val": 300000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "NetCashProvidedByUsedInInvestingActivities": {
                    "units": {
                        "USD": [
                            {
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "val": -120000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "NetCashProvidedByUsedInFinancingActivities": {
                    "units": {
                        "USD": [
                            {
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "val": -80000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "PaymentsToAcquirePropertyPlantAndEquipment": {
                    "units": {
                        "USD": [
                            {
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "val": 60000,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "EarningsPerShareBasic": {
                    "units": {
                        "USD/shares": [
                            {
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "val": 2.0,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
                "EarningsPerShareDiluted": {
                    "units": {
                        "USD/shares": [
                            {
                                "start": "2026-01-01",
                                "end": "2026-03-31",
                                "val": 1.9,
                                "accn": "0000320193-26-000010",
                                "fy": 2026,
                                "fp": "Q2",
                                "form": "10-Q",
                                "filed": "2026-04-30",
                            }
                        ]
                    }
                },
            },
        },
    }


def _sample_submissions_payload(*, with_symbol: bool = True) -> dict:
    """Internal helper to return the sample submissions payload."""
    return {
        "cik": "0000320193",
        "name": "Apple Inc.",
        "entityType": "operating",
        "sic": "3571",
        "sicDescription": "Electronic Computers",
        "ownerOrg": "06 Technology",
        "category": "Large accelerated filer",
        "fiscalYearEnd": "0926",
        "stateOfIncorporation": "CA",
        "website": "https://www.apple.com",
        "investorWebsite": "https://investor.apple.com",
        "phone": "(408) 996-1010",
        "tickers": ["AAPL"] if with_symbol else [],
        "exchanges": ["Nasdaq"] if with_symbol else [],
        "formerNames": [{"name": "APPLE INC", "from": "2007-01-10T05:00:00.000Z", "to": "2019-08-05T04:00:00.000Z"}],
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-26-000010", "0000320193-25-000099"],
                "filingDate": ["2026-04-30", "2025-10-31"],
                "reportDate": ["2026-03-31", "2025-09-27"],
                "acceptanceDateTime": ["2026-04-30T20:00:00.000Z", "2025-10-31T20:00:00.000Z"],
                "act": ["34", "34"],
                "form": ["10-Q", "10-K"],
                "fileNumber": ["001-36743", "001-36743"],
                "filmNumber": ["26800001", "26100001"],
                "items": ["", ""],
                "core_type": ["10-Q", "10-K"],
                "size": [12345, 23456],
                "isXBRL": [1, 1],
                "isInlineXBRL": [1, 1],
                "primaryDocument": ["a10-q20260331.htm", "a10-k20250927.htm"],
                "primaryDocDescription": ["10-Q", "10-K"],
            }
        },
    }


def test_us_filing_bulk_job_cap_downloads_sec_archives_into_ads_tables(tmp_path):
    """
    Exercise the test_us_filing_bulk_job_cap_downloads_sec_archives_into_ads_tables
    regression scenario.
    """
    pool = SQLitePool("ads_sec_bulk", "ADS SEC bulk pool", str(tmp_path / "ads.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool, auto_register=False)
    worker = _DummyWorker(pool)
    captured_headers = []
    cache_dir = tmp_path / "sec_cache"

    companyfacts_zip = _archive_bytes(
        {
            "CIK0000320193.json": _sample_companyfacts_payload(),
        }
    )
    submissions_zip = _archive_bytes(
        {
            "CIK0000320193.json": _sample_submissions_payload(),
            "CIK0000320193-submissions-001.json": {
                "cik": "0000320193",
                "accessionNumber": ["0000320193-24-000001"],
                "filingCount": 1,
            },
        }
    )

    def fake_request_get(url, **kwargs):
        """Handle fake request get."""
        captured_headers.append(dict(kwargs.get("headers") or {}))
        if "companyfacts.zip" in url:
            return _FakeBinaryResponse(companyfacts_zip, url=url)
        if "submissions.zip" in url:
            return _FakeBinaryResponse(submissions_zip, url=url)
        raise AssertionError(f"Unexpected URL: {url}")

    capability = USFilingBulkJobCap(
        request_get=fake_request_get,
        user_agent="FinMAS Tests qa@example.com",
        cache_dir=cache_dir,
    ).bind_worker(worker)
    submitted = dispatcher.submit_job(required_capability="us filing bulk")
    job = JobDetail.from_row(submitted["job"])
    result = capability.finish(job).model_copy(update={"worker_id": "worker-sec"})
    post_result = dispatcher.post_job_result(result)

    companyfacts_rows = pool._GetTableData(TABLE_SEC_COMPANYFACTS, table_schema=ads_table_schema_map()[TABLE_SEC_COMPANYFACTS])
    submissions_rows = pool._GetTableData(TABLE_SEC_SUBMISSIONS, table_schema=ads_table_schema_map()[TABLE_SEC_SUBMISSIONS])
    raw_rows = pool._GetTableData(TABLE_RAW_DATA, {"job_id": job.id}, table_schema=ads_table_schema_map()[TABLE_RAW_DATA])

    assert captured_headers
    assert all("User-Agent" in headers for headers in captured_headers)
    assert captured_headers[0]["User-Agent"] == "FinMAS Tests qa@example.com"
    assert result.result_summary["direct_persist"] is True
    assert result.result_summary["rows_by_table"][TABLE_SEC_COMPANYFACTS] == 1
    assert result.result_summary["rows_by_table"][TABLE_SEC_SUBMISSIONS] == 2
    assert result.result_summary["cache"]["companyfacts"]["cache_status"] == "miss"
    assert result.result_summary["cache"]["submissions"]["cache_status"] == "miss"
    assert post_result["target_table"] == TABLE_SEC_COMPANYFACTS
    assert any(
        event.get("message") == f"Downloading companyfacts.zip {len(companyfacts_zip)}/{len(companyfacts_zip)} bytes."
        for event in worker.heartbeat_events
    )
    assert any(
        event.get("message") == "Extracting companyfacts.zip."
        for event in worker.heartbeat_events
    )
    assert any(
        event.get("message") == "Extracting companyfacts.zip: CIK0000320193.json (1/1)."
        for event in worker.heartbeat_events
    )
    assert any(
        event.get("message") == "1/1 inserting companyfacts."
        for event in worker.heartbeat_events
    )
    assert any(
        event.get("message") == f"Downloading submissions.zip {len(submissions_zip)}/{len(submissions_zip)} bytes."
        for event in worker.heartbeat_events
    )
    assert any(
        event.get("message") == "Extracting submissions.zip."
        for event in worker.heartbeat_events
    )
    assert any(
        event.get("message") == "Extracting submissions.zip: CIK0000320193-submissions-001.json (2/2)."
        for event in worker.heartbeat_events
    )
    assert any(
        event.get("message") == "2/2 inserting submissions."
        for event in worker.heartbeat_events
    )
    assert all("SEC EDGAR" not in str(event.get("message") or "") for event in worker.heartbeat_events)
    assert worker.progress_updates[-1]["message"] == "Prepared SEC bulk ingest results: 1 companyfacts rows and 2 submissions rows."
    assert worker.progress_updates[-1]["extra"]["step"] == "finalize_bulk_ingest"
    assert "1/1 Apple Inc." in worker.logger.debug_messages
    assert (cache_dir / "companyfacts.zip").exists()
    assert (cache_dir / "submissions.zip").exists()
    assert len(companyfacts_rows) == 1
    assert companyfacts_rows[0]["cik"] == "0000320193"
    assert companyfacts_rows[0]["entity_name"] == "Apple Inc."
    assert len(submissions_rows) == 2
    assert any(bool(row["is_primary"]) for row in submissions_rows)
    assert len(raw_rows) == 1
    assert raw_rows[0]["payload"]["archives"][0]["dataset"] == "companyfacts"
    assert raw_rows[0]["payload"]["direct_persist"] is True
    assert raw_rows[0]["payload"]["archives"][0]["local_path"].endswith("companyfacts.zip")


def test_us_filing_bulk_job_cap_reuses_recent_cached_archives(tmp_path):
    """
    Exercise the test_us_filing_bulk_job_cap_reuses_recent_cached_archives
    regression scenario.
    """
    pool = SQLitePool("ads_sec_bulk_cache_hit", "ADS SEC bulk cache hit pool", str(tmp_path / "ads.sqlite"))
    dispatcher = ADSDispatcherAgent(pool=pool, auto_register=False)
    worker = _DummyWorker(pool)
    cache_dir = tmp_path / "sec_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    companyfacts_zip = _archive_bytes(
        {
            "CIK0000320193.json": _sample_companyfacts_payload(),
        }
    )
    submissions_zip = _archive_bytes(
        {
            "CIK0000320193.json": _sample_submissions_payload(),
            "CIK0000320193-submissions-001.json": {
                "cik": "0000320193",
                "accessionNumber": ["0000320193-24-000001"],
                "filingCount": 1,
            },
        }
    )
    companyfacts_path = cache_dir / "companyfacts.zip"
    submissions_path = cache_dir / "submissions.zip"
    companyfacts_path.write_bytes(companyfacts_zip)
    submissions_path.write_bytes(submissions_zip)
    now = datetime.now(timezone.utc).timestamp()
    os.utime(companyfacts_path, (now, now))
    os.utime(submissions_path, (now, now))

    request_calls = []

    def fake_request_get(url, **kwargs):
        """Handle fake request get."""
        request_calls.append(url)
        raise AssertionError(f"Network should not be used when cache is fresh: {url}")

    capability = USFilingBulkJobCap(
        request_get=fake_request_get,
        user_agent="FinMAS Tests qa@example.com",
        cache_dir=cache_dir,
    ).bind_worker(worker)
    submitted = dispatcher.submit_job(required_capability="us filing bulk")
    job = JobDetail.from_row(submitted["job"])
    result = capability.finish(job).model_copy(update={"worker_id": "worker-sec"})
    dispatcher.post_job_result(result)

    companyfacts_rows = pool._GetTableData(TABLE_SEC_COMPANYFACTS, table_schema=ads_table_schema_map()[TABLE_SEC_COMPANYFACTS])
    submissions_rows = pool._GetTableData(TABLE_SEC_SUBMISSIONS, table_schema=ads_table_schema_map()[TABLE_SEC_SUBMISSIONS])

    assert request_calls == []
    assert len(companyfacts_rows) == 1
    assert len(submissions_rows) == 2
    assert result.result_summary["cache"]["companyfacts"]["cache_status"] == "hit"
    assert result.result_summary["cache"]["submissions"]["cache_status"] == "hit"
    assert any(
        "Using cached companyfacts.zip from local SEC cache" in event.get("message", "")
        for event in worker.heartbeat_events
    )
    assert any(
        "Using cached submissions.zip from local SEC cache" in event.get("message", "")
        for event in worker.heartbeat_events
    )


def test_us_filing_mapping_job_cap_maps_sec_rows_into_ads_tables(tmp_path):
    """
    Exercise the test_us_filing_mapping_job_cap_maps_sec_rows_into_ads_tables
    regression scenario.
    """
    pool = SQLitePool("ads_sec_mapping", "ADS SEC mapping pool", str(tmp_path / "ads.sqlite"))
    ensure_ads_tables(pool, [TABLE_SEC_COMPANYFACTS, TABLE_SEC_SUBMISSIONS])
    dispatcher = ADSDispatcherAgent(pool=pool, auto_register=False)
    worker = _DummyWorker(pool)

    assert pool._Insert(
        TABLE_SEC_COMPANYFACTS,
        {
            "id": "ads-sec-companyfacts:0000320193",
            "cik": "0000320193",
            "entity_name": "Apple Inc.",
            "file_name": "CIK0000320193.json",
            "fact_count": 14,
            "provider": "sec_edgar",
            "payload": _sample_companyfacts_payload(),
        }
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
            "payload": _sample_submissions_payload(),
        }
    )

    capability = USFilingMappingJobCap().bind_worker(worker)
    submitted = dispatcher.submit_job(required_capability="us filing mapping", payload={"cik": "0000320193"})
    job = JobDetail.from_row(submitted["job"])
    result = capability.finish(job).model_copy(update={"worker_id": "worker-sec"})
    post_result = dispatcher.post_job_result(result)

    fundamentals_rows = pool._GetTableData(TABLE_FUNDAMENTALS, {"symbol": "AAPL"}, table_schema=ads_table_schema_map()[TABLE_FUNDAMENTALS])
    statement_rows = pool._GetTableData(
        TABLE_FINANCIAL_STATEMENTS,
        {"symbol": "AAPL"},
        table_schema=ads_table_schema_map()[TABLE_FINANCIAL_STATEMENTS],
    )
    security_rows = pool._GetTableData(TABLE_SECURITY_MASTER, {"symbol": "AAPL"}, table_schema=ads_table_schema_map()[TABLE_SECURITY_MASTER])

    assert post_result["stored_rows_by_table"][TABLE_FUNDAMENTALS] == 1
    assert post_result["stored_rows_by_table"][TABLE_FINANCIAL_STATEMENTS] >= 3
    assert [event["message"] for event in worker.heartbeat_events] == [
        "Loading SEC raw rows for CIK 0000320193.",
        "Mapping fundamentals for AAPL (CIK 0000320193).",
        "Mapping financial statements for AAPL (CIK 0000320193).",
        "Prepared SEC mappings for AAPL (CIK 0000320193): 1 fundamentals row and 3 financial statement rows.",
    ]
    assert len(fundamentals_rows) == 1
    assert fundamentals_rows[0]["industry"] == "Electronic Computers"
    assert fundamentals_rows[0]["provider"] == "sec_edgar"
    assert fundamentals_rows[0]["data"]["latest_facts"]["revenue"]["value"] == 1000000
    assert fundamentals_rows[0]["data"]["latest_quarterly_report"]["form"] == "10-Q"
    assert len(statement_rows) >= 3
    statement_types = {row["statement_type"] for row in statement_rows}
    assert {"income_statement", "balance_sheet", "cash_flow"}.issubset(statement_types)
    income_row = next(row for row in statement_rows if row["statement_type"] == "income_statement")
    assert income_row["data"]["revenue"] == 1000000
    assert income_row["data"]["net_income"] == 200000
    assert income_row["data"]["recent_filing"]["primaryDocument"] == "a10-q20260331.htm"
    assert income_row["data"]["filing_url"].endswith("/000032019326000010/a10-q20260331.htm")
    balance_row = next(row for row in statement_rows if row["statement_type"] == "balance_sheet")
    assert balance_row["data"]["assets"] == 5000000
    assert balance_row["data"]["shares_outstanding"] == 1000
    cash_flow_row = next(row for row in statement_rows if row["statement_type"] == "cash_flow")
    assert cash_flow_row["data"]["operating_cash_flow"] == 300000
    assert len(security_rows) == 1
    assert security_rows[0]["symbol"] == "AAPL"


def test_us_filing_mapping_job_cap_skips_company_without_symbol(tmp_path):
    """
    Exercise the test_us_filing_mapping_job_cap_skips_company_without_symbol
    regression scenario.
    """
    pool = SQLitePool("ads_sec_mapping_skip", "ADS SEC mapping skip pool", str(tmp_path / "ads.sqlite"))
    ensure_ads_tables(pool, [TABLE_SEC_COMPANYFACTS, TABLE_SEC_SUBMISSIONS])
    worker = _DummyWorker(pool)

    assert pool._Insert(
        TABLE_SEC_COMPANYFACTS,
        {
            "id": "ads-sec-companyfacts:0000320193",
            "cik": "0000320193",
            "entity_name": "Apple Inc.",
            "file_name": "CIK0000320193.json",
            "fact_count": 14,
            "provider": "sec_edgar",
            "payload": _sample_companyfacts_payload(),
        }
    )
    assert pool._Insert(
        TABLE_SEC_SUBMISSIONS,
        {
            "id": "ads-sec-submissions:0000320193:CIK0000320193.json",
            "cik": "0000320193",
            "entity_name": "Apple Inc.",
            "symbol": "",
            "symbols": [],
            "exchanges": [],
            "file_name": "CIK0000320193.json",
            "is_primary": True,
            "filing_count": 2,
            "provider": "sec_edgar",
            "payload": _sample_submissions_payload(with_symbol=False),
        }
    )

    capability = USFilingMappingJobCap().bind_worker(worker)
    job = JobDetail.model_validate(
        {
            "id": "ads-job:us-filing-mapping-skip",
            "required_capability": "us filing mapping",
            "payload": {"cik": "0000320193"},
            "symbols": [],
            "created_at": "2026-03-29T00:00:00+00:00",
            "updated_at": "2026-03-29T00:00:00+00:00",
            "scheduled_for": "2026-03-29T00:00:00+00:00",
        }
    )

    result = capability.finish(job)

    assert result.collected_rows == []
    assert result.result_summary["skipped"] is True
    assert result.result_summary["reason"] == "missing_symbol"
    assert worker.heartbeat_events[-1]["message"] == (
        "Skipping SEC mapping for CIK 0000320193 because no symbol is present in SEC submissions."
    )
    assert worker.heartbeat_events[-1]["extra"]["skip_reason"] == "missing_symbol"
