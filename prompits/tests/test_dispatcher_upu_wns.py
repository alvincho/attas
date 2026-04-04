"""
Regression tests for Dispatcher UPU WNS.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_upu_wns_job_caps_build_from_dispatcher_config`, `test_upu_wns_catalog_job_uses_reg
istered_stamp_count_fallback_when_discovery_has_no_page_count`,
`test_upu_wns_catalog_job_queues_page_jobs_from_single_discovery_fetch`, and
`test_upu_wns_image_job_downloads_file_and_updates_catalog_metadata`, helping guard
against regressions as the packages evolve.
"""

import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.dispatcher.jobcap import build_job_cap
from prompits.dispatcher.models import JobDetail
from prompits.dispatcher.schema import TABLE_JOBS, ensure_dispatcher_tables
from private.collectibles.jobcaps.upu_wns import (
    TABLE_UPU_WNS_CATALOG,
    UPUWNSItemImageJobCap,
    UPUWNSJobCap,
    UPUWNSPageJobCap,
    UPUWNSListingJobCap,
    upu_wns_catalog_table_schema,
)
from prompits.pools.sqlite import SQLitePool


class FakeResponse:
    """Response model for fake payloads."""
    def __init__(self, text: str, *, status_code: int = 200, url: str = "", content: bytes | None = None, headers=None):
        """Initialize the fake response."""
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")
        self.headers = dict(headers or {})
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        """Return the raise for the status."""
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")
        return None


class FakeWorker:
    """Represent a fake worker."""
    def __init__(self, pool: SQLitePool):
        """Initialize the fake worker."""
        self.pool = pool
        self.progress_updates: list[dict[str, Any]] = []
        self.heartbeats = 0
        self.log_messages: list[tuple[str, tuple[Any, ...]]] = []
        self.logger = self

    def update_progress(self, **kwargs):
        """Update the progress."""
        self.progress_updates.append(dict(kwargs))
        return dict(kwargs)

    def info(self, message: str, *args: Any):
        """Handle info for the fake worker."""
        self.log_messages.append((message, args))

    def _send_worker_heartbeat(self, event_type: str = "job_progress"):
        """Internal helper to send the worker heartbeat."""
        self.heartbeats += 1
        return {"status": "success", "event_type": event_type}

    def raise_if_stop_requested(self, job):
        """Handle raise if stop requested for the fake worker."""
        return None


class RecordingSQLitePool(SQLitePool):
    """Represent a recording sq lite pool."""
    def __init__(self, name: str, description: str, db_path: str):
        """Initialize the recording sq lite pool."""
        super().__init__(name, description, db_path)
        self.query_calls: list[tuple[str, list[Any]]] = []

    def _Query(self, query: str, params: list[Any] = None):
        """Internal helper to query the value."""
        self.query_calls.append((query, list(params or [])))
        return super()._Query(query, params)


def _job(*, required_capability: str, payload=None, result_summary=None) -> JobDetail:
    """Internal helper for job."""
    return JobDetail.model_validate(
        {
            "id": f"dispatcher-job:{required_capability.lower().replace(' ', '-')}",
            "required_capability": required_capability,
            "payload": payload or {},
            "result_summary": result_summary or {},
            "status": "claimed",
            "claimed_by": "worker-a",
            "attempts": 1,
            "max_attempts": 5,
        }
    )


def test_upu_wns_catalog_job_queues_page_jobs_from_single_discovery_fetch(tmp_path):
    """
    Exercise the
    test_upu_wns_catalog_job_queues_page_jobs_from_single_discovery_fetch regression
    scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    search_page_zero = """
    <html><body>
      <a href="/Home/GetStamp?lang=en&amp;wnsNumber=AA001.2025">First Stamp</a>
      <a href="/Home/GetStamp?lang=en&amp;wnsNumber=AA002.2025">Second Stamp</a>
      <nav class="pagination">
        <a href="/Home/autoStampSearch?pageIndex=0">1</a>
        <a href="/Home/autoStampSearch?pageIndex=1">2</a>
        <a href="/Home/autoStampSearch?pageIndex=2">3</a>
      </nav>
    </body></html>
    """
    requested_pages: list[int] = []

    def fake_request_get(url, **kwargs):
        """Handle fake request get."""
        params = dict(kwargs.get("params") or {})
        if "pageIndex" not in params:
            return FakeResponse("<html></html>", url="https://example.test/search")
        page_index = int(params.get("pageIndex", 0) or 0)
        requested_pages.append(page_index)
        if page_index == 0:
            return FakeResponse(search_page_zero, url="https://example.test/search?pageIndex=0")
        raise AssertionError(f"catalog discovery should not fetch page {page_index}")

    cap = UPUWNSJobCap(
        search_url="https://example.test/search",
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(_job(required_capability="UPU WNS Catalog"))
    assert result.status == "completed"
    assert result.result_summary["total_pages"] == 3
    assert requested_pages == [0]

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 3
    assert [row["required_capability"] for row in queued_jobs] == ["upu wns page", "upu wns page", "upu wns page"]
    assert [row["payload"]["page_index"] for row in queued_jobs] == [0, 1, 2]
    assert all(row["payload"]["refresh_item"] is False for row in queued_jobs)
    assert all(row["priority"] == 105 for row in queued_jobs)
    assert worker.heartbeats > 0
    rendered_logs = [msg % args if args else msg for msg, args in worker.log_messages]
    assert "Working on WNS catalog run dispatcher-job:upu-wns-catalog from page 0 (refresh_item=false)." in rendered_logs
    assert "Determining WNS catalog page range from discovery page 0." in rendered_logs
    assert "Catalog queued WNS page 0." in rendered_logs
    assert "Catalog queued WNS page 1." in rendered_logs
    assert "Catalog queued WNS page 2." in rendered_logs
    assert all("Scanning WNS catalog page" not in line for line in rendered_logs)


def test_upu_wns_catalog_job_reissues_after_connection_error_while_queueing_page_jobs(tmp_path):
    """
    Exercise the test_upu_wns_catalog_job_reissues_after_connection_error_while_queu
    eing_page_jobs regression scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    search_page_zero = """
    <html><body>
      <a href="/Home/GetStamp?lang=en&amp;wnsNumber=AA001.2025">First Stamp</a>
      <nav class="pagination">
        <a href="/Home/autoStampSearch?pageIndex=0">1</a>
        <a href="/Home/autoStampSearch?pageIndex=1">2</a>
      </nav>
    </body></html>
    """

    def fake_request_get(url, **kwargs):
        """Handle fake request get."""
        params = dict(kwargs.get("params") or {})
        if "pageIndex" not in params:
            return FakeResponse("<html></html>", url="https://example.test/search")
        page_index = int(params.get("pageIndex", 0) or 0)
        if page_index == 0:
            return FakeResponse(search_page_zero, url="https://example.test/search?pageIndex=0")
        raise AssertionError(f"catalog discovery should not fetch page {page_index}")

    class QueueFailCatalogCap(UPUWNSJobCap):
        """Represent a queue fail catalog cap."""
        def _submit_dispatcher_job(self, **kwargs):
            """Internal helper to submit the dispatcher job."""
            payload = dict(kwargs.get("payload") or {})
            if (
                str(kwargs.get("required_capability") or "").strip().lower() == self.PAGE_CAPABILITY.lower()
                and int(payload.get("page_index") or 0) == 1
            ):
                raise RuntimeError("connection reset by peer")
            return super()._submit_dispatcher_job(**kwargs)

    cap = QueueFailCatalogCap(
        search_url="https://example.test/search",
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(_job(required_capability="UPU WNS Catalog"))
    assert result.status == "failed"
    assert result.result_summary["connection_issue"] is True
    assert result.result_summary["reissued_priority"] == 101

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 2
    assert [row["required_capability"] for row in queued_jobs] == ["upu wns catalog", "upu wns page"]
    assert queued_jobs[0]["payload"]["catalog_run_id"] == "dispatcher-job:upu-wns-catalog"
    assert queued_jobs[0]["payload"]["page_index"] == 1
    assert queued_jobs[0]["payload"]["total_pages"] == 2
    assert queued_jobs[0]["priority"] == 101
    assert queued_jobs[1]["payload"]["catalog_run_id"] == "dispatcher-job:upu-wns-catalog"
    assert queued_jobs[1]["payload"]["page_index"] == 0
    assert queued_jobs[1]["priority"] == 105


def test_upu_wns_catalog_job_uses_registered_stamp_count_fallback_when_discovery_has_no_page_count(tmp_path):
    """
    Exercise the test_upu_wns_catalog_job_uses_registered_stamp_count_fallback_when_
    discovery_has_no_page_count regression scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    search_home = """
    <html><body>
      <div>5 postage stamps registered</div>
    </body></html>
    """
    search_page_zero = """
    <html><body>
      <a href="/Home/GetStamp?lang=en&amp;wnsNumber=AA001.2025">First Stamp</a>
      <a href="/Home/GetStamp?lang=en&amp;wnsNumber=AA002.2025">Second Stamp</a>
    </body></html>
    """

    def fake_request_get(url, **kwargs):
        """Handle fake request get."""
        params = dict(kwargs.get("params") or {})
        if "pageIndex" not in params:
            return FakeResponse(search_home, url="https://example.test/search")
        page_index = int(params.get("pageIndex", 0) or 0)
        if page_index == 0:
            return FakeResponse(search_page_zero, url="https://example.test/search?pageIndex=0")
        raise AssertionError(f"catalog discovery should not fetch page {page_index}")

    cap = UPUWNSJobCap(
        search_url="https://example.test/search",
        request_get=fake_request_get,
        page_size=2,
    ).bind_worker(worker)

    result = cap.finish(_job(required_capability="UPU WNS Catalog"))
    assert result.status == "completed"
    assert result.result_summary["total_pages"] == 3

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 3
    assert [row["payload"]["page_index"] for row in queued_jobs] == [0, 1, 2]
    rendered_logs = [msg % args if args else msg for msg, args in worker.log_messages]
    assert "Derived WNS catalog page count from registered stamp count 5: 3 pages." in rendered_logs


def test_upu_wns_page_job_queues_listing_jobs(tmp_path):
    """Exercise the test_upu_wns_page_job_queues_listing_jobs regression scenario."""
    pool = RecordingSQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    search_page_zero = """
    <html><body>
      <a href="/Home/GetStamp?lang=en&amp;wnsNumber=AA001.2025">First Stamp</a>
      <a href="/Home/GetStamp?lang=en&amp;wnsNumber=AA002.2025">Second Stamp</a>
      <a href="/Home/GetStamp?lang=en&amp;wnsNumber=AA003.2025">Third Stamp</a>
    </body></html>
    """

    def fake_request_get(url, **kwargs):
        """Handle fake request get."""
        params = dict(kwargs.get("params") or {})
        page_index = int(params.get("pageIndex", 0) or 0)
        if page_index == 0:
            return FakeResponse(search_page_zero, url="https://example.test/search?pageIndex=0")
        return FakeResponse("<html><body>No results</body></html>", url=f"https://example.test/search?pageIndex={page_index}")

    cap = UPUWNSPageJobCap(
        search_url="https://example.test/search",
        request_get=fake_request_get,
    ).bind_worker(worker)

    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_UPU_WNS_CATALOG],
        extra_schemas={TABLE_UPU_WNS_CATALOG: upu_wns_catalog_table_schema()},
    )
    pool._Insert(
        TABLE_UPU_WNS_CATALOG,
        {
            "wns_number": "AA001.2025",
            "issuer_code": "AA",
            "issuer_name": "Issuer A",
            "title": "First Stamp",
            "issue_date": "2025-01-01",
            "catalog_year": 2025,
            "face_value": "1.00",
            "item_url": "https://example.test/stamp?wnsNumber=AA001.2025",
            "image_url": "",
            "listing_page": 0,
            "listing_position": 0,
            "source_url": "https://example.test/search?pageIndex=0",
            "provider": "upu_wns",
            "payload": {},
        },
    )
    pool._Insert(
        TABLE_UPU_WNS_CATALOG,
        {
            "wns_number": "AA002.2025",
            "issuer_code": "AA",
            "issuer_name": "Issuer A",
            "title": "Second Stamp",
            "issue_date": "2025-01-02",
            "catalog_year": 2025,
            "face_value": "2.00",
            "item_url": "https://example.test/stamp?wnsNumber=AA002.2025",
            "image_url": "",
            "listing_page": 0,
            "listing_position": 1,
            "source_url": "https://example.test/search?pageIndex=0",
            "provider": "upu_wns",
            "payload": {},
        },
    )

    result = cap.finish(
        _job(
            required_capability="UPU WNS Page",
            payload={
                "catalog_run_id": "catalog-run-1",
                "page_index": 0,
                "page_url": "https://example.test/search?pageIndex=0",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 1
    assert result.result_summary["skipped_listings_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 1
    assert [row["required_capability"] for row in queued_jobs] == ["upu wns listing"]
    assert [row["payload"]["wns_number"] for row in queued_jobs] == ["AA003.2025"]
    assert queued_jobs[0]["payload"]["refresh_item"] is False

    catalog_queries = [
        (query, params)
        for query, params in pool.query_calls
        if f'from "{TABLE_UPU_WNS_CATALOG}"' in query.lower()
    ]
    assert len(catalog_queries) == 1
    assert sorted(catalog_queries[0][1]) == ["AA001.2025", "AA002.2025", "AA003.2025"]
    job_queries = [
        (query, params)
        for query, params in pool.query_calls
        if f'from "{TABLE_JOBS}"' in query.lower()
    ]
    assert len(job_queries) == 1
    assert sorted(job_queries[0][1][:1]) == ["dispatcher-job:upu-wns-listing:aa003.2025"]

    rendered_logs = [msg % args if args else msg for msg, args in worker.log_messages]
    assert "Working on WNS page 0 (refresh_item=false)." in rendered_logs
    assert "Page 0 skipped 2 existing WNS listings: AA001.2025, AA002.2025" in rendered_logs
    assert "Page 0 queued 1 WNS listing job: AA003.2025" in rendered_logs
    assert all("Page 0 skipped existing WNS listing" not in line for line in rendered_logs)


def test_upu_wns_page_job_refresh_item_requeues_completed_listing_job(tmp_path):
    """
    Exercise the test_upu_wns_page_job_refresh_item_requeues_completed_listing_job
    regression scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    search_page_zero = """
    <html><body>
      <a href="/Home/GetStamp?lang=en&amp;wnsNumber=AA001.2025">First Stamp</a>
    </body></html>
    """

    def fake_request_get(url, **kwargs):
        """Handle fake request get."""
        params = dict(kwargs.get("params") or {})
        page_index = int(params.get("pageIndex", 0) or 0)
        if page_index == 0:
            return FakeResponse(search_page_zero, url="https://example.test/search?pageIndex=0")
        return FakeResponse("<html><body>No results</body></html>", url=f"https://example.test/search?pageIndex={page_index}")

    cap = UPUWNSPageJobCap(
        search_url="https://example.test/search",
        request_get=fake_request_get,
    ).bind_worker(worker)

    ensure_dispatcher_tables(pool, [TABLE_JOBS, TABLE_UPU_WNS_CATALOG], extra_schemas={TABLE_UPU_WNS_CATALOG: upu_wns_catalog_table_schema()})
    pool._Insert(
        TABLE_UPU_WNS_CATALOG,
        {
            "wns_number": "AA001.2025",
            "issuer_code": "AA",
            "issuer_name": "Issuer A",
            "title": "Old Title",
            "issue_date": "2025-01-01",
            "catalog_year": 2025,
            "face_value": "1.00",
            "item_url": "https://example.test/stamp?wnsNumber=AA001.2025",
            "image_url": "",
            "listing_page": 0,
            "listing_position": 0,
            "source_url": "https://example.test/search?pageIndex=0",
            "provider": "upu_wns",
            "payload": {},
        },
    )
    pool._Insert(
        TABLE_JOBS,
        {
            "id": "dispatcher-job:upu-wns-listing:aa001.2025",
            "required_capability": "upu wns listing",
            "status": "completed",
            "payload": {"wns_number": "AA001.2025"},
            "priority": 110,
            "max_attempts": 5,
            "attempts": 1,
            "metadata": {"upu_wns": {"logical_job_key": "listing:aa001.2025"}},
        },
    )

    result = cap.finish(
        _job(
            required_capability="UPU WNS Page",
            payload={
                "catalog_run_id": "catalog-run-1",
                "page_index": 0,
                "page_url": "https://example.test/search?pageIndex=0",
                "refresh_item": True,
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 1
    queued_jobs = pool._GetTableData(TABLE_JOBS, "dispatcher-job:upu-wns-listing:aa001.2025")
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["status"] == "queued"
    assert queued_jobs[0]["payload"]["refresh_item"] is True
    rendered_logs = [msg % args if args else msg for msg, args in worker.log_messages]
    assert "Page 0 queued 1 WNS listing job: AA001.2025" in rendered_logs


def test_upu_wns_listing_job_persists_row_and_queues_image_job(tmp_path):
    """
    Exercise the test_upu_wns_listing_job_persists_row_and_queues_image_job
    regression scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    detail_html = """
    <html><body>
      <img src="/Stamps Search_files/logo-blue.png" alt="">
      <a id="imageLink" href="javascript:openImageInNewTab('/images/O/MO014.2026.jpg')">
        <img class="card-img-top" src="/images/T600/MO014.2026.jpg" alt="MO014.2026">
      </a>
      <dl>
        <dt>WNS Member</dt><dd>Macao, China</dd>
        <dt>Issuing date</dt><dd>23 January 2026</dd>
        <dt>Subject</dt><dd>450th Anniversary</dd>
        <dt>Denomination</dt><dd>14.00 MOP</dd>
      </dl>
    </body></html>
    """

    def fake_request_get(url, **kwargs):
        """Handle fake request get."""
        params = dict(kwargs.get("params") or {})
        wns_number = str(params.get("wnsNumber") or "")
        if wns_number == "MO014.2026":
            return FakeResponse(detail_html, url=f"https://example.test/stamp?wnsNumber={wns_number}")
        return FakeResponse("<html></html>", url="https://example.test/")

    cap = UPUWNSListingJobCap(
        search_url="https://example.test/search",
        stamp_path="/stamp",
        media_root=str(tmp_path / "media" / "wns"),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="UPU WNS Listing",
            payload={
                "wns_number": "MO014.2026",
                "item_url": "https://example.test/stamp?wnsNumber=MO014.2026",
                "listing_page": 0,
                "listing_position": 0,
                "source_url": "https://example.test/search?pageIndex=0",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_job_queued"] is True

    rows = pool._GetTableData(TABLE_UPU_WNS_CATALOG)
    assert len(rows) == 1
    row = rows[0]
    assert row["wns_number"] == "MO014.2026"
    assert row["title"] == "450th Anniversary"
    assert row["image_url"] == "https://example.test/images/O/MO014.2026.jpg"
    assert row["payload"]["image_local_path"] == ""

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "upu wns item image"
    assert queued_jobs[0]["payload"]["wns_number"] == "MO014.2026"
    assert queued_jobs[0]["payload"]["image_url"] == "https://example.test/images/O/MO014.2026.jpg"
    rendered_logs = [msg % args if args else msg for msg, args in worker.log_messages]
    assert "Working on WNS listing MO014.2026 (refresh_item=false)." in rendered_logs
    assert "Stored WNS listing MO014.2026 and queued its image job." in rendered_logs


def test_upu_wns_listing_job_skips_existing_row_without_refresh(tmp_path):
    """
    Exercise the test_upu_wns_listing_job_skips_existing_row_without_refresh
    regression scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_UPU_WNS_CATALOG],
        extra_schemas={TABLE_UPU_WNS_CATALOG: upu_wns_catalog_table_schema()},
    )
    pool._Insert(
        TABLE_UPU_WNS_CATALOG,
        {
            "wns_number": "MO014.2026",
            "issuer_code": "MO",
            "issuer_name": "Macao, China",
            "title": "Existing Stamp",
            "issue_date": "23 January 2026",
            "catalog_year": 2026,
            "face_value": "14.00 MOP",
            "item_url": "https://example.test/stamp?wnsNumber=MO014.2026",
            "image_url": "https://example.test/images/O/MO014.2026.jpg",
            "listing_page": 0,
            "listing_position": 0,
            "source_url": "https://example.test/search?pageIndex=0",
            "provider": "upu_wns",
            "payload": {},
        },
    )

    def fail_request_get(url, **kwargs):
        """Handle fail request get."""
        raise AssertionError("existing listing should skip detail fetch when refresh_item is false")

    cap = UPUWNSListingJobCap(
        search_url="https://example.test/search",
        stamp_path="/stamp",
        media_root=str(tmp_path / "media" / "wns"),
        request_get=fail_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="UPU WNS Listing",
            payload={
                "wns_number": "MO014.2026",
                "item_url": "https://example.test/stamp?wnsNumber=MO014.2026",
                "listing_page": 0,
                "listing_position": 0,
                "source_url": "https://example.test/search?pageIndex=0",
                "refresh_item": False,
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["skipped_existing"] is True
    assert pool._GetTableData(TABLE_JOBS) == []
    rendered_logs = [msg % args if args else msg for msg, args in worker.log_messages]
    assert "Working on WNS listing MO014.2026 (refresh_item=false)." in rendered_logs
    assert "Skipped WNS listing MO014.2026 because it already exists." in rendered_logs


def test_upu_wns_listing_job_refresh_item_updates_existing_row(tmp_path):
    """
    Exercise the test_upu_wns_listing_job_refresh_item_updates_existing_row
    regression scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_UPU_WNS_CATALOG],
        extra_schemas={TABLE_UPU_WNS_CATALOG: upu_wns_catalog_table_schema()},
    )
    pool._Insert(
        TABLE_UPU_WNS_CATALOG,
        {
            "wns_number": "MO014.2026",
            "issuer_code": "MO",
            "issuer_name": "Macao, China",
            "title": "Old Title",
            "issue_date": "23 January 2026",
            "catalog_year": 2026,
            "face_value": "14.00 MOP",
            "item_url": "https://example.test/stamp?wnsNumber=MO014.2026",
            "image_url": "https://example.test/images/O/MO014.2026.jpg",
            "listing_page": 0,
            "listing_position": 0,
            "source_url": "https://example.test/search?pageIndex=0",
            "provider": "upu_wns",
            "payload": {},
        },
    )

    detail_html = """
    <html><body>
      <a id="imageLink" href="javascript:openImageInNewTab('/images/O/MO014.2026.jpg')">
        <img class="card-img-top" src="/images/T600/MO014.2026.jpg" alt="MO014.2026">
      </a>
      <dl>
        <dt>WNS Member</dt><dd>Macao, China</dd>
        <dt>Issuing date</dt><dd>23 January 2026</dd>
        <dt>Subject</dt><dd>New Title</dd>
        <dt>Denomination</dt><dd>14.00 MOP</dd>
      </dl>
    </body></html>
    """

    def fake_request_get(url, **kwargs):
        """Handle fake request get."""
        params = dict(kwargs.get("params") or {})
        wns_number = str(params.get("wnsNumber") or "")
        if wns_number == "MO014.2026":
            return FakeResponse(detail_html, url=f"https://example.test/stamp?wnsNumber={wns_number}")
        return FakeResponse("<html></html>", url="https://example.test/")

    cap = UPUWNSListingJobCap(
        search_url="https://example.test/search",
        stamp_path="/stamp",
        media_root=str(tmp_path / "media" / "wns"),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="UPU WNS Listing",
            payload={
                "wns_number": "MO014.2026",
                "item_url": "https://example.test/stamp?wnsNumber=MO014.2026",
                "listing_page": 0,
                "listing_position": 0,
                "source_url": "https://example.test/search?pageIndex=0",
                "refresh_item": True,
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["refresh_item"] is True
    rows = pool._GetTableData(TABLE_UPU_WNS_CATALOG)
    assert len(rows) == 1
    assert rows[0]["title"] == "New Title"


def test_upu_wns_listing_job_parses_bootstrap_div_detail_rows(tmp_path):
    """
    Exercise the test_upu_wns_listing_job_parses_bootstrap_div_detail_rows
    regression scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    detail_html = """
    <html><body>
      <a id="imageLink" href="javascript:openImageInNewTab('/images/O/MT002.2026.jpg')">
        <img class="card-img-top" src="/images/T600/MT002.2026.jpg" alt="MT002.2026">
      </a>
      <div class="row">
        <div class="col-4 pl-xs-1 pr-xs-1 text-right wrap-nowrap font-weight-bold">WNS Member</div>
        <div class="col-8 pl-xs-1 pr-xs-1">Malta</div>
      </div>
      <div class="row">
        <div class="col-4 pl-xs-1 pr-xs-1 text-right wrap-nowrap font-weight-bold">Issuing date</div>
        <div class="col-8 pl-xs-1 pr-xs-1">09 February 2026</div>
      </div>
      <div class="row">
        <div class="col-4 pl-xs-1 pr-xs-1 text-right wrap-nowrap font-weight-bold">Theme</div>
        <div class="col-8 pl-xs-1">Fauna (Horses) Holy Days &amp; Celebrations (Chinese New Year)</div>
      </div>
      <div class="row">
        <div class="col-4 pl-xs-1 pr-xs-1 text-right wrap-nowrap font-weight-bold">Subject</div>
        <div class="col-8 pl-xs-1 pr-xs-1">The Year of the Horse 2026</div>
      </div>
      <div class="row">
        <div class="col-4 pl-xs-1 pr-xs-1 text-right wrap-nowrap font-weight-bold">Denomination</div>
        <div class="col-8 pl-xs-1 pr-xs-1">1.91 EUR</div>
      </div>
      <div class="row">
        <div class="col-4 pl-xs-1 pr-xs-1 text-right wrap-nowrap font-weight-bold">Width</div>
        <div class="col-8 pl-xs-1 pr-xs-1">35.00 mm</div>
      </div>
      <div class="row">
        <div class="col-4 pl-xs-1 pr-xs-1 text-right wrap-nowrap font-weight-bold">Issuing authority</div>
        <div class="col-8 pl-xs-1 pr-xs-1">MaltaPost p.l.c.</div>
      </div>
    </body></html>
    """

    def fake_request_get(url, **kwargs):
        """Handle fake request get."""
        params = dict(kwargs.get("params") or {})
        wns_number = str(params.get("wnsNumber") or "")
        if wns_number == "MT002.2026":
            return FakeResponse(detail_html, url=f"https://example.test/stamp?wnsNumber={wns_number}")
        return FakeResponse("<html></html>", url="https://example.test/")

    cap = UPUWNSListingJobCap(
        search_url="https://example.test/search",
        stamp_path="/stamp",
        media_root=str(tmp_path / "media" / "wns"),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="UPU WNS Listing",
            payload={
                "wns_number": "MT002.2026",
                "item_url": "https://example.test/stamp?wnsNumber=MT002.2026",
                "listing_page": 0,
                "listing_position": 0,
                "source_url": "https://example.test/search?pageIndex=0",
            },
        )
    )

    assert result.status == "completed"
    row = pool._GetTableData(TABLE_UPU_WNS_CATALOG)[0]
    assert row["issuer_name"] == "Malta"
    assert row["title"] == "The Year of the Horse 2026"
    assert row["issue_date"] == "09 February 2026"
    assert row["face_value"] == "1.91 EUR"
    assert row["payload"]["theme"] == "Fauna (Horses) Holy Days & Celebrations (Chinese New Year)"
    assert row["payload"]["width"] == "35.00 mm"
    assert row["payload"]["issuing_authority"] == "MaltaPost p.l.c."


def test_upu_wns_image_job_downloads_file_and_updates_catalog_metadata(tmp_path):
    """
    Exercise the test_upu_wns_image_job_downloads_file_and_updates_catalog_metadata
    regression scenario.
    """
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    media_root = tmp_path / "media" / "wns"
    stale_logo_path = media_root / "MO" / "2026" / "MO014.2026.png"
    stale_logo_path.parent.mkdir(parents=True, exist_ok=True)
    stale_logo_path.write_bytes(b"upu-logo")

    ensure_dispatcher_tables(
        pool,
        [TABLE_UPU_WNS_CATALOG],
        extra_schemas={TABLE_UPU_WNS_CATALOG: upu_wns_catalog_table_schema()},
    )
    pool._Insert(
        TABLE_UPU_WNS_CATALOG,
        {
            "wns_number": "MO014.2026",
            "issuer_code": "MO",
            "issuer_name": "Macao, China",
            "title": "450th Anniversary",
            "issue_date": "2026-01-23",
            "catalog_year": 2026,
            "face_value": "14.00 MOP",
            "item_url": "https://example.test/stamp?wnsNumber=MO014.2026",
            "image_url": "https://example.test/images/O/MO014.2026.jpg",
            "listing_page": 0,
            "listing_position": 0,
            "source_url": "https://example.test/search?pageIndex=0",
            "provider": "upu_wns",
            "payload": {
                "image_urls": ["https://example.test/images/O/MO014.2026.jpg"],
                "image_local_path": "",
            },
        },
    )

    def fake_request_get(url, **kwargs):
        """Handle fake request get."""
        if str(url).endswith("/images/O/MO014.2026.jpg"):
            return FakeResponse(
                "",
                url="https://example.test/images/O/MO014.2026.jpg",
                content=b"stamp-image",
                headers={"Content-Type": "image/jpeg"},
            )
        return FakeResponse("<html></html>", url="https://example.test/")

    cap = UPUWNSItemImageJobCap(
        search_url="https://example.test/search",
        media_root=str(media_root),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="UPU WNS Item Image",
            payload={
                "wns_number": "MO014.2026",
                "image_url": "https://example.test/images/O/MO014.2026.jpg",
            },
        )
    )
    assert result.status == "completed"

    image_path = Path(result.result_summary["image_local_path"])
    assert image_path.exists()
    assert image_path.parts[-3:] == ("MO", "2026", "MO014.2026.jpg")
    assert image_path.read_bytes() == b"stamp-image"
    assert not stale_logo_path.exists()

    rows = pool._GetTableData(TABLE_UPU_WNS_CATALOG)
    assert len(rows) == 1
    assert rows[0]["payload"]["image_local_path"] == str(image_path)
    rendered_logs = [msg % args if args else msg for msg, args in worker.log_messages]
    assert any("Working on WNS image MO014.2026." == line for line in rendered_logs)
    assert any(f"Stored WNS image MO014.2026 at {image_path}." == line for line in rendered_logs)


def test_upu_wns_image_job_updates_item_metadata_without_reinserting_identity_row(tmp_path):
    """
    Exercise the
    test_upu_wns_image_job_updates_item_metadata_without_reinserting_identity_row
    regression scenario.
    """
    class FakeIdentityPool:
        """Represent a fake identity pool."""
        def __init__(self):
            """Initialize the fake identity pool."""
            self.last_error = ""
            self.items_row = {
                "item_uid": "upu-wns:MT002.2026",
                "item_id": 123,
                "extra_attributes": {
                    "image_url": "https://example.test/images/O/MT002.2026.jpg",
                    "image_local_path": "",
                },
            }
            self.updated_params = None

        def _TableExists(self, table_name):
            """Return whether the table exists for value."""
            return table_name == "items"

        def _GetTableData(self, table_name, id_or_where=None):
            """Internal helper to return the table data."""
            if table_name == "items" and isinstance(id_or_where, dict) and id_or_where.get("item_uid") == self.items_row["item_uid"]:
                return [dict(self.items_row)]
            return []

        def _Query(self, query, params=None):
            """Internal helper to query the value."""
            self.updated_params = (query, params)
            self.items_row["extra_attributes"] = dict(params[0])
            return []

        def _Insert(self, table_name, data):
            """Internal helper for insert."""
            raise AssertionError("image metadata update should not call _Insert on items")

    class FakeIdentityWorker:
        """Represent a fake identity worker."""
        def __init__(self, pool):
            """Initialize the fake identity worker."""
            self.pool = pool

    pool = FakeIdentityPool()
    worker = FakeIdentityWorker(pool)
    cap = UPUWNSItemImageJobCap(search_url="https://example.test/search", request_get=lambda *args, **kwargs: None).bind_worker(worker)

    cap._update_management_item_image_metadata(
        wns_number="MT002.2026",
        image_url="https://example.test/images/O/MT002.2026.jpg",
        image_local_path="/tmp/MT/2026/MT002.2026.jpg",
    )

    assert pool.updated_params is not None
    query, params = pool.updated_params
    assert 'update "items" set extra_attributes = %s, updated_at = %s where item_uid = %s' == query
    assert params[2] == "upu-wns:MT002.2026"
    assert params[0]["image_local_path"] == "/tmp/MT/2026/MT002.2026.jpg"


def test_upu_wns_job_caps_build_from_dispatcher_config():
    """
    Exercise the test_upu_wns_job_caps_build_from_dispatcher_config regression
    scenario.
    """
    catalog_cap = build_job_cap({"name": "UPU WNS Catalog", "type": "private.collectibles.jobcaps.upu_wns:UPUWNSJobCap"})
    page_cap = build_job_cap({"name": "UPU WNS Page", "type": "private.collectibles.jobcaps.upu_wns:UPUWNSPageJobCap"})
    listing_cap = build_job_cap({"name": "UPU WNS Listing", "type": "private.collectibles.jobcaps.upu_wns:UPUWNSListingJobCap"})
    image_cap = build_job_cap({"name": "UPU WNS Item Image", "type": "private.collectibles.jobcaps.upu_wns:UPUWNSItemImageJobCap"})

    assert isinstance(catalog_cap, UPUWNSJobCap)
    assert isinstance(page_cap, UPUWNSPageJobCap)
    assert isinstance(listing_cap, UPUWNSListingJobCap)
    assert isinstance(image_cap, UPUWNSItemImageJobCap)
