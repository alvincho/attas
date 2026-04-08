"""
Regression tests for eBay active-stamp dispatcher job caps.

These tests cover the private collectibles pipeline that ingests active eBay Browse
API results in the Stamps category, stores rows in `sales_listings`, downloads all
detail-page gallery images, and refreshes rows whose stored end dates are already due.
"""

import os
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from private.collectibles.jobcaps.ebay_active_stamps import (  # noqa: E402
    TABLE_SALES_LISTINGS,
    EbayActiveStampImageJobCap,
    EbayActiveStampJobCap,
    EbayActiveStampListingJobCap,
    EbayActiveStampPageJobCap,
    EbayActiveStampStatusJobCap,
    sales_listings_table_schema,
)
from prompits.dispatcher.models import JobDetail  # noqa: E402
from prompits.dispatcher.runtime import utcnow_iso  # noqa: E402
from prompits.dispatcher.schema import TABLE_JOBS, ensure_dispatcher_tables  # noqa: E402
from prompits.pools.sqlite import SQLitePool  # noqa: E402


SEARCH_PAYLOAD = {
    "href": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp&category_ids=260&limit=2&offset=0",
    "total": 5,
    "limit": 2,
    "itemSummaries": [
        {
            "itemId": "v1|123456789012|0",
            "legacyItemId": "123456789012",
            "title": "1920 China Junk stamp lot",
            "itemWebUrl": "https://www.ebay.com/itm/123456789012",
            "price": {"value": "12.50", "currency": "USD"},
            "shippingOptions": [
                {
                    "shippingCostType": "FIXED",
                    "shippingCost": {"value": "3.25", "currency": "USD"},
                }
            ],
            "condition": "Used",
            "seller": {"username": "paper-house"},
            "itemLocation": {"city": "Taipei", "country": "Taiwan"},
            "itemEndDate": "2026-04-10T12:00:00Z",
            "buyingOptions": ["FIXED_PRICE"],
            "image": {"imageUrl": "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg"},
            "additionalImages": [{"imageUrl": "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg"}],
        },
        {
            "itemId": "v1|210987654321|0",
            "legacyItemId": "210987654321",
            "title": "Japan cherry blossom commemorative stamp",
            "itemWebUrl": "https://www.ebay.com/itm/210987654321",
            "price": {"value": "8.00", "currency": "USD"},
            "shippingOptions": [{"shippingCostType": "FREE"}],
            "condition": "Mint Never Hinged/MNH",
            "seller": {"username": "mint-covers"},
            "itemLocation": {"city": "Osaka", "country": "Japan"},
            "itemEndDate": "2026-04-11T15:30:00Z",
            "buyingOptions": ["AUCTION"],
            "image": {"imageUrl": "https://i.ebayimg.com/images/g/BBB/s-l1600.jpg"},
        },
    ],
}

DETAIL_PAYLOAD = {
    "itemId": "v1|123456789012|0",
    "legacyItemId": "123456789012",
    "title": "1920 China Junk stamp lot",
    "itemWebUrl": "https://www.ebay.com/itm/123456789012",
    "price": {"value": "12.50", "currency": "USD"},
    "shippingOptions": [
        {
            "shippingCostType": "FIXED",
            "shippingCost": {"value": "3.25", "currency": "USD"},
        }
    ],
    "condition": "Used",
    "seller": {"username": "paper-house"},
    "itemLocation": {"city": "Taipei", "country": "Taiwan"},
    "itemEndDate": "2026-04-10T12:00:00Z",
    "buyingOptions": ["FIXED_PRICE"],
    "image": {"imageUrl": "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg"},
    "additionalImages": [{"imageUrl": "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg"}],
}

ENDED_DETAIL_PAYLOAD = {
    **DETAIL_PAYLOAD,
    "itemEndDate": "2026-04-01T12:00:00Z",
}


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
        json_data: Mapping[str, Any] | None = None,
    ):
        self.status_code = status_code
        self.url = url
        self.headers = dict(headers or {})
        self._json_data = dict(json_data or {})
        if json_data is not None and not text:
            text = __import__("json").dumps(json_data)
        self.text = text
        self.content = content if content is not None else text.encode("utf-8")

    def json(self):
        """Return the fake JSON payload."""
        return dict(self._json_data)

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


def test_ebay_active_stamp_catalog_job_queues_page_jobs_from_browse_api(tmp_path):
    """Catalog job should fan out Browse API pages after reading the first response."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    oauth_calls: list[dict[str, Any]] = []

    def fake_request_post(url, **kwargs):
        oauth_calls.append({"url": url, **kwargs})
        assert kwargs["data"]["grant_type"] == "client_credentials"
        assert kwargs["data"]["scope"] == "https://api.ebay.com/oauth/api_scope"
        assert kwargs["headers"]["Authorization"].startswith("Basic ")
        return FakeResponse(
            url=url,
            json_data={"access_token": "token-123", "expires_in": 7200},
        )

    def fake_request_get(url, **kwargs):
        params = dict(kwargs.get("params") or {})
        assert kwargs["headers"]["Authorization"] == "Bearer token-123"
        assert params["category_ids"] == "260"
        assert params["limit"] == 2
        assert params["offset"] == 0
        assert params["q"] == "stamp"
        return FakeResponse(
            url="https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp&category_ids=260&limit=2&offset=0",
            json_data=SEARCH_PAYLOAD,
        )

    cap = EbayActiveStampJobCap(
        search_url="https://api.ebay.test/buy/browse/v1/item_summary/search",
        oauth_url="https://api.ebay.test/identity/v1/oauth2/token",
        keywords="stamp",
        page_size=2,
        client_id="client-id",
        client_secret="client-secret",
        request_get=fake_request_get,
        request_post=fake_request_post,
    ).bind_worker(worker)

    result = cap.finish(_job(required_capability="eBay Active Stamps Catalog"))
    assert result.status == "completed"
    assert result.result_summary["queued_pages_this_run"] == 3
    assert len(oauth_calls) == 1

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 3
    assert [row["required_capability"] for row in queued_jobs] == [
        "ebay active stamps page",
        "ebay active stamps page",
        "ebay active stamps page",
    ]
    assert [row["payload"]["page_number"] for row in queued_jobs] == [1, 2, 3]


def test_ebay_active_stamp_page_job_parses_api_results_and_queues_listing_jobs(tmp_path):
    """Page job should parse Browse API item summaries and queue listing jobs."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        params = dict(kwargs.get("params") or {})
        assert params["offset"] == 0
        assert kwargs["headers"]["Authorization"] == "Bearer token-abc"
        return FakeResponse(url=url, json_data=SEARCH_PAYLOAD)

    cap = EbayActiveStampPageJobCap(
        search_url="https://api.ebay.test/buy/browse/v1/item_summary/search",
        access_token="token-abc",
        keywords="stamp",
        page_size=2,
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Page",
            payload={
                "page_number": 1,
                "keywords": "stamp",
                "category_id": "260",
                "page_size": 2,
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 2
    assert [row["required_capability"] for row in queued_jobs] == [
        "ebay active stamps listing",
        "ebay active stamps listing",
    ]
    assert [row["payload"]["source_listing_id"] for row in queued_jobs] == ["123456789012", "210987654321"]
    assert queued_jobs[0]["payload"]["listing_status"] == "active"
    assert queued_jobs[0]["payload"]["item_end_date"] == "2026-04-10T12:00:00Z"


def test_ebay_active_stamp_listing_job_persists_row_and_queues_image_job(tmp_path):
    """Listing job should persist an active sales-listing row and enqueue the image job."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    cap = EbayActiveStampListingJobCap(access_token="token").bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Listing",
            payload={
                "source_listing_id": "123456789012",
                "item_id": "v1|123456789012|0",
                "listing_url": "https://www.ebay.com/itm/123456789012",
                "title": "1920 China Junk stamp lot",
                "price_amount": 12.5,
                "price_currency": "USD",
                "shipping_amount": 3.25,
                "shipping_currency": "USD",
                "total_amount": 15.75,
                "condition_text": "Used",
                "seller_name": "paper-house",
                "location_text": "Taipei, Taiwan",
                "image_url": "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
                "image_urls": [
                    "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
                    "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
                ],
                "page_number": 1,
                "listing_position": 0,
                "keywords": "stamp",
                "category_id": "260",
                "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp",
                "item_end_date": "2026-04-10T12:00:00Z",
                "sale_type": "FIXED_PRICE",
                "listing_status": "active",
                "payload": {"item_summary": {"legacyItemId": "123456789012"}},
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_job_queued"] is True

    rows = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:123456789012")
    assert len(rows) == 1
    assert rows[0]["source_listing_id"] == "123456789012"
    assert rows[0]["title"] == "1920 China Junk stamp lot"
    assert rows[0]["listing_status"] == "active"
    assert float(rows[0]["price_amount"]) == 12.5
    assert float(rows[0]["shipping_amount"]) == 3.25
    assert float(rows[0]["total_amount"]) == 15.75
    assert rows[0]["payload"]["item_end_date"] == "2026-04-10T12:00:00Z"

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "ebay active stamps image"
    assert queued_jobs[0]["payload"]["source_listing_id"] == "123456789012"


def test_ebay_active_stamp_image_job_downloads_all_images_and_updates_listing(tmp_path):
    """Image job should fetch item detail, download gallery images, and update the row."""
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
            "marketplace_site": "www.ebay.com",
            "source_category_id": "260",
            "source_query": "stamp",
            "listing_status": "active",
            "sale_type": "FIXED_PRICE",
            "title": "1920 China Junk stamp lot",
            "subtitle": "",
            "listing_url": "https://www.ebay.com/itm/123456789012",
            "search_page": 1,
            "listing_position": 0,
            "sold_at": "",
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
            "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp",
            "payload": {"item_end_date": "2026-04-10T12:00:00Z"},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        params = dict(kwargs.get("params") or {})
        if url == "https://api.ebay.test/buy/browse/v1/item/get_item_by_legacy_id":
            assert params["legacy_item_id"] == "123456789012"
            return FakeResponse(url=url, json_data=DETAIL_PAYLOAD)
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
    cap = EbayActiveStampImageJobCap(
        item_url="https://api.ebay.test/buy/browse/v1/item/get_item_by_legacy_id",
        media_root=str(media_root),
        access_token="token",
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Image",
            payload={
                "source_listing_id": "123456789012",
                "listing_url": "https://www.ebay.com/itm/123456789012",
                "image_url": "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
            },
        )
    )
    assert result.status == "completed"
    assert len(result.result_summary["image_local_paths"]) == 2

    updated_rows = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:123456789012")
    assert len(updated_rows) == 1
    updated_row = updated_rows[0]
    assert updated_row["image_urls"] == [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
    ]
    assert len(updated_row["image_local_paths"]) == 2
    assert Path(updated_row["image_local_paths"][0]).exists()
    assert Path(updated_row["image_local_paths"][1]).exists()
    assert updated_row["payload"]["item_detail"]["legacyItemId"] == "123456789012"


def test_ebay_active_stamp_status_job_marks_due_active_listing_as_ended(tmp_path):
    """Status job should update due active rows to ended when the refreshed end date is past."""
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
            "marketplace_site": "www.ebay.com",
            "source_category_id": "260",
            "source_query": "stamp",
            "listing_status": "active",
            "sale_type": "FIXED_PRICE",
            "title": "1920 China Junk stamp lot",
            "subtitle": "",
            "listing_url": "https://www.ebay.com/itm/123456789012",
            "search_page": 1,
            "listing_position": 0,
            "sold_at": "",
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
            "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp",
            "payload": {"item_end_date": "2026-04-01T12:00:00Z"},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "ebay:210987654321",
            "listing_uid": "ebay:210987654321",
            "provider": "ebay",
            "source_listing_id": "210987654321",
            "marketplace_site": "www.ebay.com",
            "source_category_id": "260",
            "source_query": "stamp",
            "listing_status": "active",
            "sale_type": "AUCTION",
            "title": "Japan cherry blossom commemorative stamp",
            "subtitle": "",
            "listing_url": "https://www.ebay.com/itm/210987654321",
            "search_page": 1,
            "listing_position": 1,
            "sold_at": "",
            "price_amount": 8.0,
            "price_currency": "USD",
            "shipping_amount": 0.0,
            "shipping_currency": "USD",
            "total_amount": 8.0,
            "condition_text": "Mint Never Hinged/MNH",
            "seller_name": "mint-covers",
            "location_text": "Osaka, Japan",
            "image_url": "https://i.ebayimg.com/images/g/BBB/s-l1600.jpg",
            "image_urls": ["https://i.ebayimg.com/images/g/BBB/s-l1600.jpg"],
            "image_local_paths": [],
            "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp",
            "payload": {"item_end_date": "2026-04-11T15:30:00Z"},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        params = dict(kwargs.get("params") or {})
        assert url == "https://api.ebay.test/buy/browse/v1/item/get_item_by_legacy_id"
        assert params["legacy_item_id"] == "123456789012"
        return FakeResponse(url=url, json_data=ENDED_DETAIL_PAYLOAD)

    cap = EbayActiveStampStatusJobCap(
        item_url="https://api.ebay.test/buy/browse/v1/item/get_item_by_legacy_id",
        access_token="token",
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(_job(required_capability="eBay Active Stamps Status", payload={"batch_size": 10}))
    assert result.status == "completed"
    assert result.result_summary["processed_count"] == 1
    assert result.result_summary["ended_count"] == 1
    assert result.result_summary["updated_source_listing_ids"] == ["123456789012"]

    ended_row = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:123456789012")[0]
    future_row = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:210987654321")[0]
    assert ended_row["listing_status"] == "ended"
    assert ended_row["payload"]["status_refresh_reason"] == "detail_refresh"
    assert future_row["listing_status"] == "active"
