"""
Regression tests for Colnect stamp dispatcher job caps.

These tests cover the private collectibles pipeline that ingests public Colnect stamp
listing pages, stores normalized stamp rows, and downloads stamp images into local
media storage.
"""

import os
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from private.collectibles.jobcaps.colnect_stamps import (
    TABLE_COLNECT_STAMP_CATALOG,
    ColnectStampImageJobCap,
    ColnectStampJobCap,
    ColnectStampListingJobCap,
    ColnectStampPageJobCap,
    colnect_stamp_catalog_table_schema,
)
from prompits.dispatcher.models import JobDetail
from prompits.dispatcher.runtime import utcnow_iso
from prompits.dispatcher.schema import TABLE_JOBS, ensure_dispatcher_tables
from prompits.pools.sqlite import SQLitePool


LIST_PAGE_HTML = """
<html><body>
  <div class="stamp-grid">
    <article class="stamp-card">
      <a class="thumb" href="https://colnect.com/en/stamps/stamp/1574778-Republic_of_China_13th_JCC_Asia_International_Postage_Stamp_Exhibition-Taiwan_China_2023">
        <img src="https://img.colnect.net/items/1574778.jpg" alt="Republic of China 13th JCC Asia International Postage Stamp Exhibition" />
      </a>
      <a class="title" href="https://colnect.com/en/stamps/stamp/1574778-Republic_of_China_13th_JCC_Asia_International_Postage_Stamp_Exhibition-Taiwan_China_2023">
        Republic of China 13th JCC Asia International Postage Stamp Exhibition
      </a>
    </article>
    <article class="stamp-card">
      <a class="thumb" href="https://colnect.com/en/stamps/stamp/1574779-Taiwan_Craft_Design-Taiwan_China_2023">
        <img src="https://img.colnect.net/items/1574779.jpg" alt="Taiwan Craft Design" />
      </a>
      <a class="title" href="https://colnect.com/en/stamps/stamp/1574779-Taiwan_Craft_Design-Taiwan_China_2023">
        Taiwan Craft Design
      </a>
    </article>
  </div>
  <nav class="pagination">
    <a href="https://colnect.com/en/stamps/list?page=2">2</a>
    <a rel="next" href="https://colnect.com/en/stamps/list?page=2">Next</a>
  </nav>
</body></html>
"""


DETAIL_PAGE_HTML = """
<html>
  <head>
    <title>Republic of China 13th JCC Asia International Postage Stamp Exhibition</title>
    <meta property="og:title" content="Republic of China 13th JCC Asia International Postage Stamp Exhibition" />
    <meta property="og:image" content="https://img.colnect.net/items/1574778-large.jpg" />
    <meta name="description" content="Commemorative stamp issued in Taiwan, China." />
  </head>
  <body>
    <h1>Republic of China 13th JCC Asia International Postage Stamp Exhibition</h1>
    <table class="details">
      <tr><th>Country</th><td>Taiwan, China</td></tr>
      <tr><th>Series</th><td>13th JCC Asia International Postage Stamp Exhibition</td></tr>
      <tr><th>Issued on</th><td>2023-11-30</td></tr>
      <tr><th>Face value</th><td>8.00</td></tr>
      <tr><th>Currency</th><td>New Taiwan dollar</td></tr>
      <tr><th>Catalog codes</th><td>Colnect 1574778</td></tr>
      <tr><th>Colors</th><td>Multicolor</td></tr>
      <tr><th>Themes</th><td>Stamp exhibition; Emblems</td></tr>
      <tr><th>Perforation</th><td>13 x 13 1/2</td></tr>
      <tr><th>Format</th><td>Stamp</td></tr>
      <tr><th>Designer</th><td>Designer Name</td></tr>
      <tr><th>Printer</th><td>Central Engraving and Printing Plant</td></tr>
    </table>
  </body>
</html>
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


def test_colnect_catalog_job_queues_seed_pages(tmp_path):
    """Catalog job should queue the configured Colnect source pages."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    cap = ColnectStampJobCap(
        source_pages=[
            {"page_url": "https://colnect.com/en/stamps/list?country=Taiwan_China", "label": "Taiwan stamps"},
            {"page_url": "https://colnect.com/en/stamps/list?country=Japan", "label": "Japan stamps"},
        ]
    ).bind_worker(worker)

    result = cap.finish(_job(required_capability="Colnect Stamp Catalog"))
    assert result.status == "completed"
    assert result.result_summary["queued_pages_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 2
    assert [row["required_capability"] for row in queued_jobs] == [
        "colnect stamp page",
        "colnect stamp page",
    ]
    assert [row["payload"]["page_url"] for row in queued_jobs] == [
        "https://colnect.com/en/stamps/list?country=Japan",
        "https://colnect.com/en/stamps/list?country=Taiwan_China",
    ]


def test_colnect_page_job_parses_html_and_queues_listing_jobs(tmp_path):
    """Page job should parse stamp cards and queue detail jobs plus pagination."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://colnect.com/en/stamps/list?country=Taiwan_China"
        return FakeResponse(
            LIST_PAGE_HTML,
            url=url,
        )

    cap = ColnectStampPageJobCap(
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Page",
            payload={
                "page_url": "https://colnect.com/en/stamps/list?country=Taiwan_China",
                "source_page_label": "Taiwan stamps",
                "follow_pagination": True,
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 2
    assert result.result_summary["queued_pages_this_run"] == 1

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: (row["required_capability"], row["id"]))
    assert len(queued_jobs) == 3
    assert [row["required_capability"] for row in queued_jobs] == [
        "colnect stamp listing",
        "colnect stamp listing",
        "colnect stamp page",
    ]
    assert [row["payload"]["stamp_id"] for row in queued_jobs[:2]] == ["1574778", "1574779"]
    assert queued_jobs[2]["payload"]["page_url"] == "https://colnect.com/en/stamps/list?page=2"


def test_colnect_listing_job_persists_row_and_queues_image_job(tmp_path):
    """Listing job should persist a normalized row and enqueue the image job."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://colnect.com/en/stamps/stamp/1574778-Republic_of_China_13th_JCC_Asia_International_Postage_Stamp_Exhibition-Taiwan_China_2023"
        return FakeResponse(
            DETAIL_PAGE_HTML,
            url=url,
        )

    cap = ColnectStampListingJobCap(
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Listing",
            payload={
                "stamp_id": "1574778",
                "item_url": "https://colnect.com/en/stamps/stamp/1574778-Republic_of_China_13th_JCC_Asia_International_Postage_Stamp_Exhibition-Taiwan_China_2023",
                "title": "Republic of China 13th JCC Asia International Postage Stamp Exhibition",
                "image_url": "https://img.colnect.net/items/1574778.jpg",
                "source_page_url": "https://colnect.com/en/stamps/list?country=Taiwan_China",
                "source_page_label": "Taiwan stamps",
                "listing_position": 0,
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_job_queued"] is True

    catalog_rows = pool._GetTableData(TABLE_COLNECT_STAMP_CATALOG)
    assert len(catalog_rows) == 1
    assert catalog_rows[0]["stamp_id"] == "1574778"
    assert catalog_rows[0]["country_name"] == "Taiwan, China"
    assert catalog_rows[0]["catalog_year"] == 2023
    assert catalog_rows[0]["image_url"] == "https://img.colnect.net/items/1574778-large.jpg"

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "colnect stamp image"
    assert queued_jobs[0]["payload"]["stamp_id"] == "1574778"


def test_colnect_image_job_downloads_image_and_updates_catalog(tmp_path):
    """Image job should cache the image and write the saved path back to the catalog row."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_COLNECT_STAMP_CATALOG],
        extra_schemas={TABLE_COLNECT_STAMP_CATALOG: colnect_stamp_catalog_table_schema()},
    )
    pool._Insert(
        TABLE_COLNECT_STAMP_CATALOG,
        {
            "id": "colnect:1574778",
            "stamp_id": "1574778",
            "title": "Republic of China 13th JCC Asia International Postage Stamp Exhibition",
            "country_name": "Taiwan, China",
            "country_code": "TAIWAN-CHINA",
            "series_name": "13th JCC Asia International Postage Stamp Exhibition",
            "issue_date": "2023-11-30",
            "catalog_year": 2023,
            "face_value": "8.00",
            "currency": "New Taiwan dollar",
            "catalog_codes": "Colnect 1574778",
            "colors": "Multicolor",
            "themes": "Stamp exhibition; Emblems",
            "perforation": "13 x 13 1/2",
            "format": "Stamp",
            "designer": "Designer Name",
            "printer": "Central Engraving and Printing Plant",
            "description": "Commemorative stamp issued in Taiwan, China.",
            "item_url": "https://colnect.com/en/stamps/stamp/1574778-Republic_of_China_13th_JCC_Asia_International_Postage_Stamp_Exhibition-Taiwan_China_2023",
            "image_url": "https://img.colnect.net/items/1574778-large.jpg",
            "image_local_path": "",
            "source_page_url": "https://colnect.com/en/stamps/list?country=Taiwan_China",
            "source_page_label": "Taiwan stamps",
            "listing_position": 0,
            "provider": "colnect_stamps",
            "payload": {},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        assert url == "https://img.colnect.net/items/1574778-large.jpg"
        return FakeResponse(
            status_code=200,
            url=url,
            content=b"\x89PNG\r\n\x1a\ncolnect",
            headers={"Content-Type": "image/png"},
        )

    media_root = tmp_path / "media"
    cap = ColnectStampImageJobCap(
        media_root=str(media_root),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Image",
            payload={
                "stamp_id": "1574778",
                "catalog_year": 2023,
                "image_url": "https://img.colnect.net/items/1574778-large.jpg",
            },
        )
    )
    assert result.status == "completed"

    updated_row = pool._GetTableData(TABLE_COLNECT_STAMP_CATALOG, {"stamp_id": "1574778"})[0]
    assert updated_row["image_local_path"]
    assert Path(updated_row["image_local_path"]).exists()
    assert Path(updated_row["image_local_path"]).suffix == ".png"
