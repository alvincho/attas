"""
Regression tests for eBay sold-stamp dispatcher job caps.

These tests cover the private collectibles pipeline that ingests sold eBay search
results in the Stamps category, stores rows in `sales_listings`, and downloads all
detail-page gallery images.
"""

import os
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from private.collectibles.jobcaps.ebay_sold_stamps import (
    TABLE_SALES_LISTINGS,
    EbaySoldStampImageJobCap,
    EbaySoldStampJobCap,
    EbaySoldStampListingJobCap,
    EbaySoldStampPageJobCap,
    sales_listings_table_schema,
)
from prompits.dispatcher.models import JobDetail
from prompits.dispatcher.runtime import utcnow_iso
from prompits.dispatcher.schema import TABLE_JOBS, ensure_dispatcher_tables
from prompits.pools.sqlite import SQLitePool


SOLD_SEARCH_HTML = """
<html><body>
  <div class="srp-controls__count-heading">
    <span class="BOLD">2 results</span>
  </div>
  <nav class="pagination">
    <a href="https://example.test/sch/i.html?_nkw=stamp&_sacat=260&LH_Sold=1&LH_Complete=1&_pgn=1">1</a>
    <a href="https://example.test/sch/i.html?_nkw=stamp&_sacat=260&LH_Sold=1&LH_Complete=1&_pgn=2">2</a>
    <a href="https://example.test/sch/i.html?_nkw=stamp&_sacat=260&LH_Sold=1&LH_Complete=1&_pgn=3">3</a>
  </nav>
  <ul class="srp-results srp-list clearfix">
    <li class="s-item s-item__pl-on-bottom">
      <div class="s-item__image">
        <a class="s-item__link" href="https://example.test/itm/123456789012">
          <img class="s-item__image-img" src="https://i.ebayimg.com/images/g/AAA/s-l1600.jpg" alt="1920 China Junk stamp lot" />
        </a>
      </div>
      <div class="s-item__info clearfix">
        <div class="s-item__title">1920 China Junk stamp lot</div>
        <div class="s-item__subtitle">Album page with cancellations</div>
        <span class="s-item__price">US $12.50</span>
        <span class="s-item__shipping">US $3.25 shipping</span>
        <span class="SECONDARY_INFO">Used</span>
        <span class="s-item__seller-info-text">paper-house</span>
        <span class="s-item__location">Taipei, Taiwan</span>
        <span class="POSITIVE">Sold Apr 07, 2026</span>
      </div>
    </li>
    <li class="s-item s-item__pl-on-bottom">
      <div class="s-item__image">
        <a class="s-item__link" href="https://example.test/itm/210987654321">
          <img class="s-item__image-img" src="https://i.ebayimg.com/images/g/BBB/s-l1600.jpg" alt="Japan cherry blossom commemorative stamp" />
        </a>
      </div>
      <div class="s-item__info clearfix">
        <div class="s-item__title">Japan cherry blossom commemorative stamp</div>
        <span class="s-item__price">US $8.00</span>
        <span class="s-item__shipping">Free shipping</span>
        <span class="SECONDARY_INFO">Mint Never Hinged/MNH</span>
        <span class="s-item__seller-info-text">mint-covers</span>
        <span class="s-item__location">Osaka, Japan</span>
        <span class="POSITIVE">Sold Apr 06, 2026</span>
      </div>
    </li>
  </ul>
</body></html>
"""

LISTING_DETAIL_HTML = """
<html><head>
  <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Product",
      "name": "1920 China Junk stamp lot",
      "image": [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg"
      ],
      "offers": {
        "@type": "Offer",
        "price": "12.50",
        "priceCurrency": "USD"
      }
    }
  </script>
  <meta property="og:image" content="https://i.ebayimg.com/images/g/AAA/s-l1600.jpg" />
</head><body>
  <h1 class="x-item-title__mainTitle">1920 China Junk stamp lot</h1>
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


def test_ebay_sold_stamp_catalog_job_queues_page_jobs_from_discovery_page(tmp_path):
    """Catalog job should fan out sold-search pages after discovering pagination."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        params = dict(kwargs.get("params") or {})
        assert params["LH_Sold"] == "1"
        assert params["LH_Complete"] == "1"
        assert params["_sacat"] == "260"
        assert params["_pgn"] == 1
        return FakeResponse(
            SOLD_SEARCH_HTML,
            url="https://example.test/sch/i.html?_nkw=stamp&_sacat=260&LH_Sold=1&LH_Complete=1&_pgn=1",
        )

    cap = EbaySoldStampJobCap(
        search_url="https://example.test/sch/i.html",
        keywords="stamp",
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(_job(required_capability="eBay Sold Stamps Catalog"))
    assert result.status == "completed"
    assert result.result_summary["queued_pages_this_run"] == 3

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 3
    assert [row["required_capability"] for row in queued_jobs] == [
        "ebay sold stamps page",
        "ebay sold stamps page",
        "ebay sold stamps page",
    ]
    assert [row["payload"]["page_number"] for row in queued_jobs] == [1, 2, 3]


def test_ebay_sold_stamp_page_job_parses_html_and_queues_listing_jobs(tmp_path):
    """Page job should parse sold-search cards and queue sold-listing jobs."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        params = dict(kwargs.get("params") or {})
        assert params["_pgn"] == 1
        return FakeResponse(
            SOLD_SEARCH_HTML,
            url="https://example.test/sch/i.html?_nkw=stamp&_sacat=260&LH_Sold=1&LH_Complete=1&_pgn=1",
        )

    cap = EbaySoldStampPageJobCap(
        search_url="https://example.test/sch/i.html",
        keywords="stamp",
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Sold Stamps Page",
            payload={
                "page_number": 1,
                "keywords": "stamp",
                "category_id": "260",
                "page_size": 240,
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 2
    assert [row["required_capability"] for row in queued_jobs] == [
        "ebay sold stamps listing",
        "ebay sold stamps listing",
    ]
    assert [row["payload"]["source_listing_id"] for row in queued_jobs] == ["123456789012", "210987654321"]
    assert [row["payload"]["listing_url"] for row in queued_jobs] == [
        "https://example.test/itm/123456789012",
        "https://example.test/itm/210987654321",
    ]


def test_ebay_sold_stamp_listing_job_persists_row_and_queues_image_job(tmp_path):
    """Listing job should persist a sales-listing row and enqueue the image job."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    cap = EbaySoldStampListingJobCap().bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="eBay Sold Stamps Listing",
            payload={
                "source_listing_id": "123456789012",
                "listing_url": "https://example.test/itm/123456789012",
                "title": "1920 China Junk stamp lot",
                "subtitle": "Album page with cancellations",
                "price_text": "US $12.50",
                "shipping_text": "US $3.25 shipping",
                "condition_text": "Used",
                "seller_name": "paper-house",
                "location_text": "Taipei, Taiwan",
                "sold_text": "Sold Apr 07, 2026",
                "image_url": "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
                "page_number": 1,
                "listing_position": 0,
                "keywords": "stamp",
                "category_id": "260",
                "source_url": "https://example.test/sch/i.html?_nkw=stamp",
                "payload": {"card_html": "<li>card</li>"},
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_job_queued"] is True

    rows = pool._GetTableData(
        TABLE_SALES_LISTINGS,
        "ebay:123456789012",
        table_schema=sales_listings_table_schema(),
    )
    assert len(rows) == 1
    assert rows[0]["source_listing_id"] == "123456789012"
    assert rows[0]["title"] == "1920 China Junk stamp lot"
    assert float(rows[0]["price_amount"]) == 12.5
    assert float(rows[0]["shipping_amount"]) == 3.25
    assert float(rows[0]["total_amount"]) == 15.75
    assert rows[0]["sold_at"] == "2026-04-07"

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "ebay sold stamps image"
    assert queued_jobs[0]["payload"]["source_listing_id"] == "123456789012"


def test_ebay_sold_stamp_image_job_downloads_all_images_and_updates_listing(tmp_path):
    """Image job should fetch the detail page, download all gallery images, and update the row."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "ebay:123456789012",
            "listing_uid": "ebay:123456789012",
            "provider": "ebay",
            "source_listing_id": "123456789012",
            "marketplace_site": "example.test",
            "source_category_id": "260",
            "source_query": "stamp",
            "listing_status": "sold",
            "sale_type": "",
            "title": "1920 China Junk stamp lot",
            "subtitle": "Album page with cancellations",
            "listing_url": "https://example.test/itm/123456789012",
            "search_page": 1,
            "listing_position": 0,
            "sold_at": "2026-04-07",
            "price_amount": 12.5,
            "price_currency": "USD",
            "shipping_amount": 3.25,
            "shipping_currency": "USD",
            "total_amount": 15.75,
            "condition_text": "Used",
            "seller_name": "paper-house",
            "location_text": "Taipei, Taiwan",
            "image_url": "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
            "image_urls": ["https://i.ebayimg.com/images/g/AAA/s-l1600.jpg"],
            "image_local_paths": [],
            "source_url": "https://example.test/sch/i.html?_nkw=stamp",
            "payload": {"price_text": "US $12.50"},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        if url == "https://example.test/itm/123456789012":
            return FakeResponse(LISTING_DETAIL_HTML, url=url)
        if url == "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg":
            return FakeResponse(
                status_code=200,
                url=url,
                content=b"\x89PNG\r\n\x1a\nfirst",
                headers={"Content-Type": "image/png"},
            )
        if url == "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg":
            return FakeResponse(
                status_code=200,
                url=url,
                content=b"\xff\xd8\xffsecond",
                headers={"Content-Type": "image/jpeg"},
            )
        raise AssertionError(f"Unexpected URL: {url}")

    media_root = tmp_path / "media"
    cap = EbaySoldStampImageJobCap(
        media_root=str(media_root),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Sold Stamps Image",
            payload={
                "source_listing_id": "123456789012",
                "listing_url": "https://example.test/itm/123456789012",
                "image_url": "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
            },
        )
    )
    assert result.status == "completed"
    assert len(result.result_summary["image_local_paths"]) == 2

    updated_rows = pool._GetTableData(
        TABLE_SALES_LISTINGS,
        "ebay:123456789012",
        table_schema=sales_listings_table_schema(),
    )
    assert len(updated_rows) == 1
    updated_row = updated_rows[0]
    assert updated_row["image_urls"] == [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
    ]
    assert len(updated_row["image_local_paths"]) == 2
    assert Path(updated_row["image_local_paths"][0]).exists()
    assert Path(updated_row["image_local_paths"][1]).exists()
    assert updated_row["payload"]["detail_json_ld"]
