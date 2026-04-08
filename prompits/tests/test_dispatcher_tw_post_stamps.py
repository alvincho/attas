"""
Regression tests for Taiwan Post stamp dispatcher job caps.

These tests cover the private collectibles pipeline that ingests Chunghwa Post
issuing-information pages, stores Taiwan stamp issue rows, and renders local preview
images from the official issue PDFs.
"""

import os
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from private.collectibles.jobcaps.tw_post_stamps import (
    TABLE_TW_POST_STAMP_CATALOG,
    TWPostStampImageJobCap,
    TWPostStampJobCap,
    TWPostStampListingJobCap,
    TWPostStampPageJobCap,
    tw_post_stamp_catalog_table_schema,
)
from prompits.dispatcher.models import JobDetail
from prompits.dispatcher.runtime import utcnow_iso
from prompits.dispatcher.schema import TABLE_JOBS, ensure_dispatcher_tables
from prompits.pools.sqlite import SQLitePool


ISSUING_PAGE_HTML = """
<html><body>
  <table>
    <tbody>
      <tr>
        <th class="hd">File name</th>
        <th class="hd">File type</th>
        <th class="hd">File size</th>
        <th class="hd">Update time</th>
      </tr>
      <tr>
        <td data-th='File name'>2026 ( No. 1 ) - Alpine Plants Postage Stamps (III)</td>
        <td class='format' data-th='File type'>
          <span class="ListContainer hidden_S">
            <a href="https://example.test/download/alpine.pdf"
               onclick="javascript:window.open('ap5_dt_hit.jsp?download_sn=3327');"
               title='2026 ( No. 1 ) - Alpine Plants Postage Stamps (III).pdf(pdf File download )'>
               <img src='images/FileType_PDF.png' alt='' /> pdf
            </a>
          </span>
        </td>
        <td class='size' data-th='File size'>201.1KB</td>
        <td data-th='Update time'>2025-12-01</td>
      </tr>
      <tr class='odd'>
        <td data-th='File name'>2026 ( No. 2 ) - Taiwan Trains Postage Stamps (II)</td>
        <td class='format' data-th='File type'>
          <span class="ListContainer hidden_S">
            <a href="https://example.test/download/trains.pdf"
               onclick="javascript:window.open('ap5_dt_hit.jsp?download_sn=3351');"
               title='2026 ( No. 2 ) - Taiwan Trains Postage Stamps (II).pdf(pdf File download )'>
               <img src='images/FileType_PDF.png' alt='' /> pdf
            </a>
          </span>
        </td>
        <td class='size' data-th='File size'>198.4KB</td>
        <td data-th='Update time'>2026-01-26</td>
      </tr>
    </tbody>
  </table>
</body></html>
"""


class FakeResponse:
    """Simple fake response used for job-cap tests."""

    def __init__(
        self,
        text: str = "",
        *,
        status_code: int = 200,
        url: str = "",
        content: bytes | None = None,
        headers: Mapping[str, Any] | None = None,
    ):
        self.text = text
        self.status_code = status_code
        self.url = url
        self.content = content if content is not None else text.encode("utf-8")
        self.headers = dict(headers or {})

    def raise_for_status(self):
        """Raise on HTTP failures."""
        if self.status_code >= 400:
            raise RuntimeError(f"status {self.status_code}")
        return None


class FakeWorker:
    """Minimal worker stub with a pool and logger."""

    def __init__(self, pool: SQLitePool):
        self.pool = pool
        self.log_messages: list[tuple[str, tuple[Any, ...]]] = []
        self.logger = self

    def info(self, message: str, *args: Any):
        """Capture log messages for assertions."""
        self.log_messages.append((message, args))


def _job(*, required_capability: str, payload=None) -> JobDetail:
    """Build a claimed job detail for one test."""
    return JobDetail.model_validate(
        {
            "id": f"dispatcher-job:{required_capability.lower().replace(' ', '-')}",
            "required_capability": required_capability,
            "payload": payload or {},
            "status": "claimed",
            "claimed_by": "worker-a",
            "attempts": 1,
            "max_attempts": 5,
        }
    )


def test_tw_post_catalog_job_queues_page_jobs_from_config(tmp_path):
    """Catalog job should fan out configured Chunghwa Post source pages."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    cap = TWPostStampJobCap(
        source_pages=[
            {"page_id": "1669769911221", "catalog_year": 2025, "label": "2025 Postage Stamps Issuing Information"},
            {"page_id": "1761870306320", "catalog_year": 2026, "label": "2026 Postage Stamps Issuing Information"},
        ]
    ).bind_worker(worker)

    result = cap.finish(_job(required_capability="Taiwan Post Issues Catalog"))
    assert result.status == "completed"
    assert result.result_summary["queued_pages_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 2
    assert [row["required_capability"] for row in queued_jobs] == [
        "taiwan post issue page",
        "taiwan post issue page",
    ]
    assert [row["payload"]["page_id"] for row in queued_jobs] == ["1669769911221", "1761870306320"]
    assert [row["payload"]["catalog_year"] for row in queued_jobs] == [2025, 2026]


def test_tw_post_page_job_parses_html_and_queues_listing_jobs(tmp_path):
    """Page job should parse the issuing-information table and queue listing jobs."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        params = dict(kwargs.get("params") or {})
        assert params["ID"] == "1761870306320"
        return FakeResponse(
            ISSUING_PAGE_HTML,
            url="https://example.test/index.jsp?ID=1761870306320",
        )

    cap = TWPostStampPageJobCap(
        index_url="https://example.test/index.jsp",
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Taiwan Post Issue Page",
            payload={
                "page_id": "1761870306320",
                "catalog_year": 2026,
                "source_page_label": "2026 Postage Stamps Issuing Information",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 2
    assert [row["required_capability"] for row in queued_jobs] == [
        "taiwan post issue listing",
        "taiwan post issue listing",
    ]
    assert [row["payload"]["issue_key"] for row in queued_jobs] == ["2026-001", "2026-002"]
    assert [row["payload"]["pdf_url"] for row in queued_jobs] == [
        "https://example.test/download/alpine.pdf",
        "https://example.test/download/trains.pdf",
    ]


def test_tw_post_listing_job_persists_row_and_queues_image_job(tmp_path):
    """Listing job should persist a Taiwan Post row and enqueue the preview job."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    cap = TWPostStampListingJobCap().bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="Taiwan Post Issue Listing",
            payload={
                "issue_key": "2026-001",
                "issue_number": 1,
                "catalog_year": 2026,
                "title": "Alpine Plants Postage Stamps (III)",
                "update_date": "2025-12-01",
                "pdf_url": "https://example.test/download/alpine.pdf",
                "source_page_id": "1761870306320",
                "source_page_label": "2026 Postage Stamps Issuing Information",
                "listing_position": 0,
                "file_size_text": "201.1KB",
                "source_url": "https://example.test/index.jsp?ID=1761870306320",
                "payload": {"download_sn": "3327"},
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_job_queued"] is True

    catalog_rows = pool._GetTableData(TABLE_TW_POST_STAMP_CATALOG)
    assert len(catalog_rows) == 1
    assert catalog_rows[0]["issue_key"] == "2026-001"
    assert catalog_rows[0]["title"] == "Alpine Plants Postage Stamps (III)"
    assert catalog_rows[0]["pdf_url"] == "https://example.test/download/alpine.pdf"

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "taiwan post issue image"
    assert queued_jobs[0]["payload"]["issue_key"] == "2026-001"


def test_tw_post_image_job_downloads_pdf_renders_preview_and_updates_catalog(tmp_path):
    """Image job should cache the official PDF and write a preview image path back."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_TW_POST_STAMP_CATALOG],
        extra_schemas={TABLE_TW_POST_STAMP_CATALOG: tw_post_stamp_catalog_table_schema()},
    )
    pool._Insert(
        TABLE_TW_POST_STAMP_CATALOG,
        {
            "id": "tw-post:2026-001",
            "issue_key": "2026-001",
            "issue_number": 1,
            "catalog_year": 2026,
            "title": "Alpine Plants Postage Stamps (III)",
            "issue_date": "",
            "update_date": "2025-12-01",
            "pdf_url": "https://example.test/download/alpine.pdf",
            "pdf_local_path": "",
            "image_local_path": "",
            "source_page_id": "1761870306320",
            "source_page_label": "2026 Postage Stamps Issuing Information",
            "listing_position": 0,
            "file_size_text": "201.1KB",
            "source_url": "https://example.test/index.jsp?ID=1761870306320",
            "provider": "tw_post_stamp_issues",
            "payload": {"download_sn": "3327"},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        assert url == "https://example.test/download/alpine.pdf"
        return FakeResponse(
            status_code=200,
            url=url,
            content=b"%PDF-1.7 test issue pdf",
            headers={"Content-Type": "application/pdf"},
        )

    def fake_preview_renderer(pdf_path: Path, target_path: Path, issue_key: str) -> str:
        assert issue_key == "2026-001"
        assert pdf_path.exists()
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"\x89PNG\r\n\x1a\npreview")
        return str(target_path)

    media_root = tmp_path / "media"
    cap = TWPostStampImageJobCap(
        media_root=str(media_root),
        request_get=fake_request_get,
        preview_renderer=fake_preview_renderer,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Taiwan Post Issue Image",
            payload={
                "issue_key": "2026-001",
                "catalog_year": 2026,
                "pdf_url": "https://example.test/download/alpine.pdf",
            },
        )
    )
    assert result.status == "completed"

    updated_row = pool._GetTableData(TABLE_TW_POST_STAMP_CATALOG, {"issue_key": "2026-001"})[0]
    assert updated_row["pdf_local_path"]
    assert updated_row["image_local_path"]
    assert Path(updated_row["pdf_local_path"]).exists()
    assert Path(updated_row["image_local_path"]).exists()
    assert Path(updated_row["image_local_path"]).suffix == ".png"
