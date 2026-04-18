"""
Regression tests for eBay active-stamp dispatcher job caps.

These tests cover the private collectibles pipeline that ingests active eBay Browse
API results in the Stamps category, stores rows in `sales_listings`, downloads all
detail-page gallery images, and refreshes rows whose stored end dates are already due.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from requests.exceptions import ReadTimeout

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from private.collectibles.jobcaps.colnect_stamps import (  # noqa: E402
    TABLE_COLNECT_RUNTIME,
    ColnectStampPageJobCap,
    colnect_runtime_table_schema,
)
from private.collectibles.jobcaps.ebay_active_stamps import (  # noqa: E402
    IMAGE_JOB_PRIORITY,
    LISTING_JOB_PRIORITY,
    PAGE_JOB_PRIORITY,
    RUNTIME_LISTING_ITEM_HOLD_ROW_ID,
    RUNTIME_RATE_LIMIT_ROW_ID,
    STATUS_JOB_PRIORITY,
    TABLE_EBAY_ACTIVE_DAILY_REPORTS,
    TABLE_EBAY_ACTIVE_RUNTIME,
    TABLE_EBAY_ACTIVE_SELLER_ACCOUNTS,
    TABLE_SALES_LISTINGS,
    EbayRateLimitError,
    _extract_listing_page_seller_account_name,
    _listing_dispatch_priority,
    _location_text,
    EbayDailyScheduleJobCap,
    EbayActiveStampImageJobCap,
    EbayActiveStampJobCap,
    EbayActiveStampListingJobCap,
    EbayActiveStampPageJobCap,
    EbayActiveStampStatusJobCap,
    ebay_active_runtime_table_schema,
    ebay_active_seller_accounts_table_schema,
    sales_listings_table_schema,
)
from private.collectibles.report_items import ebay_daily_schedule_report_item_id  # noqa: E402
from prompits.dispatcher.models import JobDetail, JobResult  # noqa: E402
from prompits.dispatcher.agents import DispatcherAgent, DispatcherWorkerAgent  # noqa: E402
from prompits.dispatcher.jobcap import build_job_cap  # noqa: E402
from prompits.dispatcher.report_feed import TABLE_DISPATCHER_REPORT_ITEMS  # noqa: E402
from prompits.dispatcher.runtime import build_dispatch_job, utcnow_iso  # noqa: E402
from prompits.dispatcher.schema import TABLE_JOB_ARCHIVE, TABLE_JOBS, ensure_dispatcher_tables  # noqa: E402
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
            "seller": {"username": "paper-house", "feedbackScore": 4200, "feedbackPercentage": "99.8"},
            "itemLocation": {"city": "Taipei", "country": "Taiwan"},
            "itemOriginDate": "2026-03-15T12:00:00Z",
            "itemEndDate": "2026-04-20T12:00:00Z",
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
            "seller": {"username": "mint-covers", "feedbackScore": 12000, "feedbackPercentage": "100.0"},
            "itemLocation": {"city": "Osaka", "country": "Japan"},
            "itemOriginDate": "2026-03-01T15:30:00Z",
            "itemEndDate": "2026-04-21T15:30:00Z",
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
    "seller": {"username": "paper-house", "feedbackScore": 4200, "feedbackPercentage": "99.8"},
    "itemLocation": {"city": "Taipei", "country": "Taiwan"},
    "itemOriginDate": "2026-03-15T12:00:00Z",
    "itemEndDate": "2026-04-20T12:00:00Z",
    "buyingOptions": ["FIXED_PRICE"],
    "image": {"imageUrl": "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg"},
    "additionalImages": [{"imageUrl": "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg"}],
}

ANUBIS_CHALLENGE_HTML = """
<html>
  <head><title>Making sure you&#39;re not a bot!</title></head>
  <body>
    <script id="anubis_version" type="application/json">"1.25.0"</script>
    <script id="anubis_challenge" type="application/json">{"rules":{"algorithm":"fast","difficulty":4},"challenge":{"id":"challenge-123","randomData":"abcdef1234567890","spent":false}}</script>
    <script id="anubis_base_prefix" type="application/json">""</script>
    <script id="anubis_public_url" type="application/json">""</script>
    <h1 id="title">Making sure you&#39;re not a bot!</h1>
  </body>
</html>
"""

ENDED_DETAIL_PAYLOAD = {
    **DETAIL_PAYLOAD,
    "itemEndDate": "2026-04-01T12:00:00Z",
}


def test_location_text_unescapes_html_entities():
    """eBay item locations should be normalized before persistence/display."""
    assert _location_text({"city": "&apos;s Gravenzande", "country": "NL"}) == "'s Gravenzande, NL"
    assert _location_text("&apos;s Gravenzande, NL") == "'s Gravenzande, NL"


def test_ebay_search_params_use_stamp_q_and_open_ended_end_time():
    """Browse search params should use q=stamp and the open-ended upper-bound itemEndDate form."""
    cap = EbayActiveStampPageJobCap(access_token="token-abc", page_size=200)

    params = cap._build_search_params(
        page_number=1,
        keywords="",
        category_id="260",
        page_size=200,
        buying_options=["AUCTION"],
        min_bid_count=1,
        item_end_date_from="2026-04-13T09:17:59.000Z",
        item_end_date_to="2026-04-13T09:27:59.000Z",
        sort="-price",
    )

    assert params["q"] == "stamp"
    assert params["filter"] == (
        "buyingOptions:{AUCTION},bidCount:[1],itemEndDate:[..2026-04-13T09:27:59.000Z]"
    )


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
        self.log_messages: list[str] = []
        self.progress_updates: list[dict[str, Any]] = []
        self.logger = self

    def info(self, message: str, *args: Any):
        """Capture log messages for assertions."""
        rendered = message % args if args else message
        self.log_messages.append(rendered)

    def update_progress(self, **kwargs: Any):
        """Capture structured worker progress snapshots for assertions."""
        snapshot = dict(kwargs)
        self.progress_updates.append(snapshot)
        return snapshot


def _job(
    *,
    required_capability: str,
    payload=None,
    priority: int | None = None,
    attempts: int | None = None,
    max_attempts: int | None = None,
    scheduled_for: str = "",
) -> JobDetail:
    """Build a claimed job detail for one test."""
    job_payload = {
        "id": f"dispatcher-job:{required_capability.lower().replace(' ', '-')}",
        "required_capability": required_capability,
        "payload": payload or {},
        "status": "claimed",
        "claimed_by": "worker-a",
        "attempts": 1,
        "max_attempts": 5,
    }
    if priority is not None:
        job_payload["priority"] = int(priority)
    if attempts is not None:
        job_payload["attempts"] = int(attempts)
    if max_attempts is not None:
        job_payload["max_attempts"] = int(max_attempts)
    if scheduled_for:
        job_payload["scheduled_for"] = str(scheduled_for)
    return JobDetail.model_validate(job_payload)


def _latest_job_row(pool: SQLitePool, job_id: str) -> dict[str, Any]:
    """Return the latest persisted row for one dispatcher job id."""
    rows = [dict(row) for row in (pool._GetTableData(TABLE_JOBS, job_id) or []) if isinstance(row, Mapping)]
    assert rows
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("updated_at") or row.get("created_at") or ""),
            str(row.get("id") or ""),
        ),
    )[-1]


def _lock_alert_rows(pool: SQLitePool, source_key: str) -> list[dict[str, Any]]:
    """Return dispatcher lock-status alert rows for one source."""
    return [
        dict(row)
        for row in (pool._GetTableData(TABLE_DISPATCHER_REPORT_ITEMS) or [])
        if str(row.get("kind") or "") == "alert"
        and str(row.get("source_key") or "") == source_key
        and str(row.get("category_key") or "") == "lock_status"
    ]


def test_extract_listing_page_seller_account_name_reads_feedback_link_username():
    """Rendered listing HTML should fall back to the feedback username when needed."""
    html = """
    <html>
      <body>
        <a href="https://www.ebay.com/fdbk/mweb_profile?item_id=366333117430&username=gsquared7#tab1&filter=feedback_page%3ARECEIVED_AS_SELLER">
          See all feedback
        </a>
      </body>
    </html>
    """

    assert _extract_listing_page_seller_account_name(html) == "gsquared7"


def test_extract_listing_page_seller_account_name_reads_storefront_sid_username():
    """Rendered listing HTML should read the seller account from storefront sid links."""
    html = """
    <html>
      <body>
        <a href="https://www.ebay.com/sch/i.html?sid=wrgstamp&_trksid=p4429486.m2548.l2792">
          Visit store
        </a>
      </body>
    </html>
    """

    assert _extract_listing_page_seller_account_name(html) == "wrgstamp"


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
    assert result.result_summary["ebay_response_keys"] == ["browse_search_page"]
    assert result.raw_payload["ebay_responses"]["browse_search_page"]["href"] == SEARCH_PAYLOAD["href"]
    assert len(oauth_calls) == 1

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 3
    assert [row["required_capability"] for row in queued_jobs] == [
        "ebay active stamps page",
        "ebay active stamps page",
        "ebay active stamps page",
    ]
    assert {row["priority"] for row in queued_jobs} == {PAGE_JOB_PRIORITY}
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
                "report_date": "2026-04-11T02:00:00+08:00",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 2
    assert result.result_summary["ebay_response_keys"] == ["browse_search_pages"]
    assert [entry["page_number"] for entry in result.raw_payload["ebay_responses"]["browse_search_pages"]] == [1]

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 2
    assert [row["required_capability"] for row in queued_jobs] == [
        "ebay active stamps listing",
        "ebay active stamps listing",
    ]
    priority_by_listing_id = {
        row["payload"]["source_listing_id"]: row["priority"]
        for row in queued_jobs
    }
    assert priority_by_listing_id == {
        "123456789012": LISTING_JOB_PRIORITY,
        "210987654321": LISTING_JOB_PRIORITY - 3,
    }
    assert PAGE_JOB_PRIORITY < LISTING_JOB_PRIORITY
    assert [row["payload"]["source_listing_id"] for row in queued_jobs] == ["123456789012", "210987654321"]
    assert queued_jobs[0]["payload"]["listing_status"] == "active"
    assert queued_jobs[0]["payload"]["item_end_date"] == "2026-04-20T12:00:00Z"
    assert queued_jobs[0]["payload"]["seller_feedback_score"] == 4200
    assert all(row["payload"]["report_date"] == "2026-04-11T02:00:00+08:00" for row in queued_jobs)
    assert any(
        update.get("extra", {}).get("browse_page_number") == 1 and "fetching browse page 1" in str(update.get("message") or "")
        for update in worker.progress_updates
    )
    assert any(
        "browse page 1 returned 2 items, queued 2 listing fan-out jobs, skipped 0 items" in message
        for message in worker.log_messages
    )
    assert any("queued 2 listing fan-out jobs after scanning 1 browse pages" in message for message in worker.log_messages)


def test_ebay_active_stamp_page_job_queues_follow_on_page_when_current_page_has_only_duplicates(tmp_path):
    """Page job should queue the next browse page when the current page has no new imports."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    for source_listing_id in ("123456789012", "210987654321"):
        pool._Insert(
            TABLE_SALES_LISTINGS,
            {
                "id": f"ebay:{source_listing_id}",
                "listing_uid": f"ebay:{source_listing_id}",
                "provider": "ebay",
                "source_listing_id": source_listing_id,
                "marketplace_site": "www.ebay.com",
                "source_category_id": "260",
                "source_query": "stamp",
                "listing_status": "active",
                "sale_type": "AUCTION",
                "title": f"Existing {source_listing_id}",
                "subtitle": "",
                "listing_url": f"https://www.ebay.com/itm/{source_listing_id}",
                "search_page": 1,
                "listing_position": 0,
                "sold_at": "",
                "price_amount": 10.0,
                "price_currency": "USD",
                "shipping_amount": 0.0,
                "shipping_currency": "USD",
                "total_amount": 10.0,
                "condition_text": "Used",
                "seller_name": "existing-seller",
                "location_text": "Taipei, Taiwan",
                "image_url": "",
                "image_urls": [],
                "image_local_paths": [],
                "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp",
                "payload": {"item_end_date": "2026-04-20T12:00:00Z"},
                "created_at": utcnow_iso(),
                "updated_at": utcnow_iso(),
            },
        )

    def fake_request_get(url, **kwargs):
        params = dict(kwargs.get("params") or {})
        assert kwargs["headers"]["Authorization"] == "Bearer token-abc"
        if params["offset"] == 0:
            return FakeResponse(
                url="https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp&category_ids=260&limit=2&offset=0",
                json_data={
                    **SEARCH_PAYLOAD,
                    "total": 4,
                    "limit": 2,
                    "next": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp&category_ids=260&limit=2&offset=2",
                },
            )
        raise AssertionError(f"Unexpected params: {params}")

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
                "target_new_items": 2,
                "report_date": "2026-04-11T02:00:00+08:00",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["scanned_pages_this_run"] == 1
    assert result.result_summary["last_scanned_page_number"] == 1
    assert result.result_summary["target_new_items"] == 2
    assert result.result_summary["queued_listings_this_run"] == 0
    assert result.result_summary["skipped_listings_this_run"] == 2
    assert result.result_summary["page_continuation_action"] == "queued_next_page"
    assert result.result_summary["page_continuation_next_page_number"] == 2
    assert result.result_summary["ebay_response_keys"] == ["browse_search_pages"]
    assert [entry["page_number"] for entry in result.raw_payload["ebay_responses"]["browse_search_pages"]] == [1]
    assert any(
        "browse page 1 returned 2 items, queued 0 listing fan-out jobs, skipped 2 items" in message
        for message in worker.log_messages
    )

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "ebay active stamps page"
    assert queued_jobs[0]["payload"]["page_number"] == 2
    assert queued_jobs[0]["payload"]["import_stop_after"] == 2


def test_ebay_active_stamp_page_job_trusts_browse_query_without_local_window_filter(tmp_path):
    """Page job should trust the Browse query and not locally drop returned items by end-date window."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    off_window_payload = {
        "href": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp&category_ids=260&limit=2&offset=0",
        "total": 1,
        "limit": 2,
        "itemSummaries": [
            {
                "itemId": "v1|168287511957|0",
                "legacyItemId": "168287511957",
                "title": "DR WHO 1930 ZEPPELIN FLIGHT NY TO GERMANY $2.60 R47081",
                "itemWebUrl": "https://www.ebay.com/itm/168287511957",
                "currentBidPrice": {"value": "192.50", "currency": "USD"},
                "shippingOptions": [{"shippingCostType": "FIXED", "shippingCost": {"value": "1.35", "currency": "USD"}}],
                "seller": {"username": "kEnNdKMwTFq", "feedbackScore": 191786, "feedbackPercentage": "100.0"},
                "itemLocation": {"country": "US", "postalCode": "986**"},
                "itemOriginDate": "2026-04-05T02:07:30.000Z",
                "itemEndDate": "2026-04-15T02:07:30.000Z",
                "buyingOptions": ["AUCTION"],
                "bidCount": 14,
                "image": {"imageUrl": "https://i.ebayimg.com/images/g/Un0AAeSwU5Vp0UzL/s-l225.jpg"},
            }
        ],
    }

    def fake_request_get(url, **kwargs):
        assert kwargs["headers"]["Authorization"] == "Bearer token-abc"
        return FakeResponse(url=url, json_data=off_window_payload)

    cap = EbayActiveStampPageJobCap(
        search_url="https://api.ebay.test/buy/browse/v1/item_summary/search",
        access_token="token-abc",
        page_size=2,
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Page",
            payload={
                "page_number": 1,
                "category_id": "260",
                "page_size": 2,
                "buying_options": ["AUCTION"],
                "min_bid_count": 1,
                "item_end_date_from": "2026-04-12T10:10:09.831627Z",
                "item_end_date_to": "2026-04-12T10:20:09.831627Z",
                "report_date": "2026-04-12T18:10:00+08:00",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 1
    assert result.result_summary["skipped_listings_this_run"] == 0
    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["payload"]["source_listing_id"] == "168287511957"


def test_ebay_manual_page_job_fans_out_all_remaining_pages_immediately(tmp_path):
    """Manual Browse crawls should queue every remaining page as soon as the Browse response reveals them."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        params = dict(kwargs.get("params") or {})
        assert kwargs["headers"]["Authorization"] == "Bearer token-abc"
        if params["offset"] == 2000:
            return FakeResponse(
                url="https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp&category_ids=260&limit=200&offset=2000",
                json_data={
                    **SEARCH_PAYLOAD,
                    "total": 2600,
                    "limit": 200,
                    "next": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp&category_ids=260&limit=200&offset=2200",
                },
            )
        raise AssertionError(f"Unexpected params: {params}")

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
                "search_run_id": "ebay-manual-auction-2026-04-14t00-43-35-08-00-18h",
                "search_key": "manual-auction-next-18h-price-desc-2026-04-14t00-43-35-08-00",
                "page_number": 11,
                "keywords": "stamp",
                "category_id": "260",
                "page_size": 200,
                "buying_options": ["AUCTION"],
                "min_bid_count": 1,
                "sort": "-price",
                "crawl_all_pages": True,
                "target_new_items": 100000,
                "import_stop_after": 100000,
                "report_date": "2026-04-14T00:43:35+08:00",
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 2
    assert result.result_summary["skipped_listings_this_run"] == 0
    assert result.result_summary["discovered_total_pages"] == 13
    assert result.result_summary["page_continuation_action"] == "queued_remaining_pages"
    assert result.result_summary["page_continuation_next_page_number"] == 12
    assert result.result_summary["page_continuation_last_page_number"] == 13
    assert result.result_summary["page_continuation_queued_page_jobs"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    next_page_jobs = [
        row for row in queued_jobs if str(row["required_capability"]).strip().lower() == "ebay active stamps page"
    ]
    listing_jobs = [
        row for row in queued_jobs if str(row["required_capability"]).strip().lower() == "ebay active stamps listing"
    ]

    assert len(next_page_jobs) == 2
    assert len(listing_jobs) == 2
    assert [row["payload"]["page_number"] for row in next_page_jobs] == [12, 13]
    assert all(row["payload"]["crawl_all_pages"] is True for row in next_page_jobs)
    assert all(job["payload"]["crawl_all_pages"] is True for job in listing_jobs)


def test_ebay_listing_job_completion_queues_next_page_after_current_page_finishes(tmp_path):
    """The last terminal listing result on a page should fan out the next Browse page when imports are still below threshold."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(pool, [TABLE_JOBS])

    first_listing = build_dispatch_job(
        required_capability="eBay Active Stamps Listing",
        payload={
            "source_listing_id": "111111111111",
            "search_run_id": "ebay-daily-auction-2026-04-13t17-00-00-08-00",
            "search_key": "260-stamp-200-auction-bid-1",
            "page_number": 1,
            "next_page_number": 2,
            "page_size": 200,
            "keywords": "stamp",
            "category_id": "260",
            "buying_options": ["AUCTION"],
            "min_bid_count": 1,
            "item_end_date_from": "2026-04-13T09:00:00.000Z",
            "item_end_date_to": "2026-04-13T09:10:00.000Z",
            "sort": "-price",
            "report_date": "2026-04-13T17:00:00+08:00",
            "import_stop_after": 60,
        },
        job_id="dispatcher-job:ebay-active-stamps-listing:111111111111",
        priority=LISTING_JOB_PRIORITY,
        max_attempts=5,
        metadata={"ebay_active_stamp": {"job_kind": "listing", "source_listing_id": "111111111111"}},
    ).to_row()
    first_listing["status"] = "completed"
    first_listing["result_summary"] = {"provider": "ebay", "job_kind": "listing", "source_listing_id": "111111111111"}
    first_listing["completed_at"] = utcnow_iso()
    pool._Insert(TABLE_JOBS, first_listing)

    second_listing = build_dispatch_job(
        required_capability="eBay Active Stamps Listing",
        payload={
            "source_listing_id": "222222222222",
            "search_run_id": "ebay-daily-auction-2026-04-13t17-00-00-08-00",
            "search_key": "260-stamp-200-auction-bid-1",
            "page_number": 1,
            "next_page_number": 2,
            "page_size": 200,
            "keywords": "stamp",
            "category_id": "260",
            "buying_options": ["AUCTION"],
            "min_bid_count": 1,
            "item_end_date_from": "2026-04-13T09:00:00.000Z",
            "item_end_date_to": "2026-04-13T09:10:00.000Z",
            "sort": "-price",
            "report_date": "2026-04-13T17:00:00+08:00",
            "import_stop_after": 60,
        },
        job_id="dispatcher-job:ebay-active-stamps-listing:222222222222",
        priority=LISTING_JOB_PRIORITY,
        max_attempts=5,
        metadata={"ebay_active_stamp": {"job_kind": "listing", "source_listing_id": "222222222222"}},
    ).to_row()
    second_listing["status"] = "claimed"
    second_listing["claimed_by"] = "worker-a"
    second_listing["claimed_at"] = utcnow_iso()
    pool._Insert(TABLE_JOBS, second_listing)

    cap = EbayActiveStampListingJobCap(access_token="token-abc", page_size=200).bind_worker(worker)
    job = JobDetail.from_row(second_listing)
    result = cap._maybe_continue_search_run_after_listing_result(
        job,
        JobResult(
            job_id=job.id,
            status="completed",
            result_summary={
                "provider": "ebay",
                "job_kind": "listing",
                "source_listing_id": "222222222222",
            },
        ),
    )

    assert result.result_summary["page_continuation_action"] == "queued_next_page"
    assert result.result_summary["page_continuation_next_page_number"] == 2
    assert result.result_summary["page_continuation_imported_total"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    next_page_jobs = [
        row
        for row in queued_jobs
        if str(row["required_capability"]).strip().lower() == "ebay active stamps page"
    ]
    assert len(next_page_jobs) == 1
    assert next_page_jobs[0]["payload"]["page_number"] == 2
    assert next_page_jobs[0]["payload"]["page_size"] == 200
    assert next_page_jobs[0]["payload"]["keywords"] == "stamp"
    assert next_page_jobs[0]["payload"]["import_stop_after"] == 60


def test_ebay_manual_listing_completion_does_not_wait_for_peer_listings_before_queueing_next_page(tmp_path):
    """Manual Browse crawls should advance to the next page even while same-page listings are still in flight."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(pool, [TABLE_JOBS])

    first_listing = build_dispatch_job(
        required_capability="eBay Active Stamps Listing",
        payload={
            "source_listing_id": "111111111111",
            "search_run_id": "ebay-manual-auction-2026-04-14t00-43-35-08-00-18h",
            "search_key": "260-stamp-200-auction-bid-1",
            "page_number": 1,
            "next_page_number": 2,
            "page_size": 200,
            "keywords": "stamp",
            "category_id": "260",
            "buying_options": ["AUCTION"],
            "min_bid_count": 1,
            "item_end_date_to": "2026-04-14T10:43:35.000Z",
            "sort": "-price",
            "report_date": "2026-04-14T00:43:35+08:00",
            "import_stop_after": 100000,
            "crawl_all_pages": True,
        },
        job_id="dispatcher-job:ebay-active-stamps-listing:111111111111",
        priority=LISTING_JOB_PRIORITY,
        max_attempts=5,
        metadata={"ebay_active_stamp": {"job_kind": "listing", "source_listing_id": "111111111111"}},
    ).to_row()
    first_listing["status"] = "claimed"
    first_listing["claimed_by"] = "worker-a"
    first_listing["claimed_at"] = utcnow_iso()
    pool._Insert(TABLE_JOBS, first_listing)

    second_listing = build_dispatch_job(
        required_capability="eBay Active Stamps Listing",
        payload={
            "source_listing_id": "222222222222",
            "search_run_id": "ebay-manual-auction-2026-04-14t00-43-35-08-00-18h",
            "search_key": "260-stamp-200-auction-bid-1",
            "page_number": 1,
            "next_page_number": 2,
            "page_size": 200,
            "keywords": "stamp",
            "category_id": "260",
            "buying_options": ["AUCTION"],
            "min_bid_count": 1,
            "item_end_date_to": "2026-04-14T10:43:35.000Z",
            "sort": "-price",
            "report_date": "2026-04-14T00:43:35+08:00",
            "import_stop_after": 100000,
            "crawl_all_pages": True,
        },
        job_id="dispatcher-job:ebay-active-stamps-listing:222222222222",
        priority=LISTING_JOB_PRIORITY,
        max_attempts=5,
        metadata={"ebay_active_stamp": {"job_kind": "listing", "source_listing_id": "222222222222"}},
    ).to_row()
    second_listing["status"] = "claimed"
    second_listing["claimed_by"] = "worker-b"
    second_listing["claimed_at"] = utcnow_iso()
    pool._Insert(TABLE_JOBS, second_listing)

    cap = EbayActiveStampListingJobCap(access_token="token-abc", page_size=200).bind_worker(worker)
    job = JobDetail.from_row(second_listing)
    result = cap._maybe_continue_search_run_after_listing_result(
        job,
        JobResult(
            job_id=job.id,
            status="completed",
            result_summary={
                "provider": "ebay",
                "job_kind": "listing",
                "source_listing_id": "222222222222",
            },
        ),
    )

    assert result.result_summary["page_continuation_action"] == "queued_next_page"
    assert result.result_summary["page_continuation_next_page_number"] == 2
    assert result.result_summary["page_continuation_imported_total"] == 1

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    next_page_jobs = [
        row
        for row in queued_jobs
        if str(row["required_capability"]).strip().lower() == "ebay active stamps page"
    ]
    assert len(next_page_jobs) == 1
    assert next_page_jobs[0]["payload"]["page_number"] == 2
    assert next_page_jobs[0]["payload"]["crawl_all_pages"] is True


def test_ebay_active_stamp_page_job_429_fails_without_cancelling_peers_or_reissuing(tmp_path):
    """A 429 should hold eBay work, keep queued jobs intact, and fail the current page job once."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    agent = DispatcherAgent(pool=pool)

    queued_job = agent.submit_job(
        required_capability="eBay Active Stamps Listing",
        payload={"source_listing_id": "queued-item"},
        priority=LISTING_JOB_PRIORITY,
        max_attempts=3,
    )["job"]

    def fake_request_get(url, **kwargs):
        return FakeResponse(url=url, status_code=429, json_data={"errors": [{"message": "Too Many Requests"}]})

    cap = EbayActiveStampPageJobCap(
        search_url="https://api.ebay.test/buy/browse/v1/item_summary/search",
        access_token="token-abc",
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Page",
            payload={
                "search_run_id": "ebay-active-run",
                "page_number": 10389,
                "keywords": "",
                "category_id": "260",
                "page_size": 200,
            },
            priority=PAGE_JOB_PRIORITY,
        )
    )

    assert result.status == "failed"
    assert "status 429" in result.error
    assert result.result_summary["rate_limited"] is True
    assert result.result_summary["suppress_failed_reissue"] is True

    hold_rows = pool._GetTableData(TABLE_EBAY_ACTIVE_RUNTIME, "api-rate-limit")
    assert len(hold_rows) == 1
    assert hold_rows[0]["scope"] == "browse-api-rate-limit"
    assert hold_rows[0]["metadata"]["active"] is True
    page_cap = EbayActiveStampPageJobCap(access_token="token-abc", page_size=200).bind_worker(worker)
    assert page_cap.advertised_capabilities() == []

    queued_rows = pool._GetTableData(TABLE_JOBS, queued_job["id"])
    assert len(queued_rows) == 1
    assert queued_rows[0]["status"] == "queued"
    assert queued_rows[0]["error"] == ""

    surviving_rows = [
        row for row in (pool._GetTableData(TABLE_JOBS) or [])
        if row["required_capability"] == "ebay active stamps page"
    ]
    assert surviving_rows == []

    report_rows = pool._GetTableData(TABLE_EBAY_ACTIVE_DAILY_REPORTS)
    assert len(report_rows) == 1
    assert report_rows[0]["status"] == "rate_limited"


def test_ebay_daily_schedule_keeps_shared_rate_limit_hold_when_probe_still_429(tmp_path):
    """Daily schedule should probe the sticky shared hold and skip fan-out while 429 persists."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        return FakeResponse(url=url, status_code=429, json_data={"errors": [{"message": "Too Many Requests"}]})

    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )

    cap = EbayDailyScheduleJobCap(access_token="token-abc", page_size=200, request_get=fake_request_get).bind_worker(worker)
    hold_until = cap._record_rate_limit_hold(EbayRateLimitError("shared hold", hold_sec=600))

    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={"report_date": "2026-04-13T09:40:00+08:00"},
            priority=90,
        )
    )

    assert result.status == "completed"
    assert result.result_summary["rate_limited"] is True
    assert result.result_summary["rate_limit_skipped"] is True
    assert result.result_summary["api_probe_status"] == "rate_limited"
    assert result.result_summary["cancelled_jobs"] == 0
    assert result.result_summary["stopping_jobs"] == 0
    report_row = pool._GetTableData(TABLE_EBAY_ACTIVE_DAILY_REPORTS, _report_row_id("2026-04-13T09:40:00+08:00"))[0]
    assert report_row["status"] == "rate_limited"
    assert hold_until == ""
    assert report_row["payload"]["hold_until"] == ""
    assert (pool._GetTableData(TABLE_JOBS) or []) == []


def test_ebay_daily_schedule_releases_shared_rate_limit_hold_after_successful_probe(tmp_path):
    """Daily schedule should be the controller that clears the shared Browse/API lock."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        return FakeResponse(url=url, json_data={"itemSummaries": [], "total": 0, "limit": 1, "offset": 0})

    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )

    cap = EbayDailyScheduleJobCap(access_token="token-abc", page_size=200, request_get=fake_request_get).bind_worker(worker)
    cap._record_rate_limit_hold(EbayRateLimitError("shared hold", hold_sec=600))

    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={"report_date": "2026-04-13T09:50:00+08:00"},
            priority=90,
        )
    )

    assert result.status == "completed"
    hold_row = pool._GetTableData(TABLE_EBAY_ACTIVE_RUNTIME, {"id": "api-rate-limit"})[0]
    assert hold_row["metadata"]["active"] is False
    assert hold_row["metadata"]["last_probe_status"] == "released"
    queued_jobs = pool._GetTableData(TABLE_JOBS) or []
    assert any(str(row.get("required_capability") or "") == "ebay active stamps page" for row in queued_jobs)


def test_record_rate_limit_hold_preserves_held_at_without_time_box(tmp_path):
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_EBAY_ACTIVE_RUNTIME],
        extra_schemas={TABLE_EBAY_ACTIVE_RUNTIME: ebay_active_runtime_table_schema()},
    )

    cap = EbayDailyScheduleJobCap(access_token="token-abc", page_size=200).bind_worker(worker)
    first_until = cap._record_rate_limit_hold(EbayRateLimitError("first hold", hold_sec=120))
    first_row = pool._GetTableData(TABLE_EBAY_ACTIVE_RUNTIME, {"id": "api-rate-limit"})[0]

    second_until = cap._record_rate_limit_hold(EbayRateLimitError("second hold", hold_sec=120))
    second_row = pool._GetTableData(TABLE_EBAY_ACTIVE_RUNTIME, {"id": "api-rate-limit"})[0]

    assert first_until == ""
    assert second_until == ""
    assert first_row["hold_until"] in ("", None)
    assert second_row["hold_until"] in ("", None)
    assert second_row["metadata"]["held_at"] == first_row["metadata"]["held_at"]
    assert second_row["metadata"]["last_probe_status"] == "locked"


def test_ebay_rate_limit_lock_writes_dispatcher_alert_on_status_change(tmp_path):
    """The dispatcher should get one alert only when the eBay lock active state flips."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    cap = EbayDailyScheduleJobCap(access_token="token-abc", page_size=200).bind_worker(worker)

    cap._record_rate_limit_hold(EbayRateLimitError("first hold", hold_sec=120))

    alerts = _lock_alert_rows(pool, "ebay")
    assert len(alerts) == 1
    assert alerts[0]["status"] == "active"
    assert alerts[0]["severity"] == "warning"
    assert alerts[0]["payload"]["lock_key"] == RUNTIME_RATE_LIMIT_ROW_ID
    assert alerts[0]["payload"]["active"] is True

    cap._record_rate_limit_hold(EbayRateLimitError("second hold", hold_sec=120))
    assert len(_lock_alert_rows(pool, "ebay")) == 1

    cap._release_rate_limit_hold(reason="manual release")

    alerts = _lock_alert_rows(pool, "ebay")
    assert len(alerts) == 2
    released_alert = next(row for row in alerts if row["status"] == "released")
    assert released_alert["severity"] == "success"
    assert released_alert["payload"]["previous_active"] is True
    assert "manual release" in released_alert["body"]


def test_expired_shared_rate_limit_hold_stays_locked_until_schedule_probe(tmp_path):
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    cap = EbayDailyScheduleJobCap(access_token="token-abc", page_size=200).bind_worker(worker)
    expired_until = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    cap._upsert_runtime_state(
        "api-rate-limit",
        scope="browse-api-rate-limit",
        hold_until=expired_until,
        hold_reason="previous 429",
        metadata={
            "provider": "ebay",
            "active": True,
            "channel": "browse-api",
            "hold_count": 3,
            "last_error": "previous 429",
            "held_at": expired_until,
        },
    )

    assert cap._active_rate_limit_hold() is not None
    hold_row = pool._GetTableData(TABLE_EBAY_ACTIVE_RUNTIME, {"id": "api-rate-limit"})[0]
    assert hold_row["hold_until"] == expired_until
    assert hold_row["metadata"]["active"] is True
    page_cap = EbayActiveStampPageJobCap(access_token="token-abc", page_size=200).bind_worker(worker)
    assert page_cap.advertised_capabilities() == []


def test_expired_listing_item_hold_stays_locked_until_schedule_probe(tmp_path):
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    cap = EbayActiveStampListingJobCap(access_token="token-abc", page_size=200).bind_worker(worker)
    expired_until = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    cap._upsert_runtime_state(
        RUNTIME_LISTING_ITEM_HOLD_ROW_ID,
        scope="browse-item",
        hold_until=expired_until,
        hold_reason="previous GetItem 429",
        metadata={
            "provider": "ebay",
            "active": True,
            "channel": "browse-item",
            "hold_count": 3,
            "last_error": "previous GetItem 429",
            "held_at": expired_until,
        },
    )

    assert cap._active_listing_item_hold() is not None
    hold_row = pool._GetTableData(TABLE_EBAY_ACTIVE_RUNTIME, {"id": RUNTIME_LISTING_ITEM_HOLD_ROW_ID})[0]
    assert hold_row["hold_until"] == expired_until
    assert hold_row["metadata"]["active"] is True
    assert cap.advertised_capabilities() == []


def test_upsert_dispatcher_report_item_writes_null_for_blank_response_timestamp(tmp_path):
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    cap = EbayDailyScheduleJobCap(access_token="token-abc", page_size=200).bind_worker(worker)
    captured: dict[str, Any] = {}
    original_insert = pool._Insert

    def capture_insert(table_name: str, item: Mapping[str, Any], *args: Any, **kwargs: Any) -> bool:
        if table_name == TABLE_DISPATCHER_REPORT_ITEMS:
            captured.update(dict(item))
        return original_insert(table_name, item, *args, **kwargs)

    pool._Insert = capture_insert  # type: ignore[method-assign]
    cap._upsert_dispatcher_report_item(
        {
            "id": "ebay-daily-report:test",
            "kind": "report",
            "source_key": "ebay",
            "source_label": "eBay",
            "category_key": "ebay_daily_schedule",
            "title": "eBay Daily Schedule",
            "summary": "Finished",
            "status": "finished",
            "created_at": "2026-04-16T18:30:00+08:00",
            "updated_at": "2026-04-16T18:30:00+08:00",
            "responded_at": "",
        }
    )

    assert captured["responded_at"] is None


def test_final_daily_report_status_marks_terminal_failures_completed_with_errors():
    """Terminal failed tracked jobs should produce a completed_with_errors report state."""
    assert EbayActiveStampPageJobCap._final_daily_report_status(
        "processing page",
        [{"status": "failed"}],
    ) == "completed_with_errors"


def test_ebay_active_stamp_listing_job_429_sets_listing_hold_and_hides_capability(tmp_path):
    """A listing 429 should fail once, persist the listing hold, and hide listing claims."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        return FakeResponse(url=url, status_code=429, json_data={"errors": [{"message": "Too Many Requests"}]})

    cap = EbayActiveStampListingJobCap(
        access_token="token-abc",
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Listing",
            payload={"source_listing_id": "327090177509"},
            priority=LISTING_JOB_PRIORITY,
        )
    )

    assert result.status == "failed"
    assert result.result_summary["listing_item_hold_active"] is True
    assert result.result_summary["listing_item_hold_id"] == RUNTIME_LISTING_ITEM_HOLD_ROW_ID
    hold_rows = pool._GetTableData(TABLE_EBAY_ACTIVE_RUNTIME, RUNTIME_LISTING_ITEM_HOLD_ROW_ID)
    assert len(hold_rows) == 1
    assert hold_rows[0]["scope"] == "browse-item"
    assert hold_rows[0]["metadata"]["active"] is True
    assert hold_rows[0]["metadata"]["last_probe_status"] == "locked"
    assert hold_rows[0]["metadata"]["probe_source_listing_id"] == "327090177509"
    assert cap.advertised_capabilities() == []


def test_ebay_daily_schedule_releases_listing_hold_after_successful_getitem_probe(tmp_path):
    """Daily schedule should probe GetItem and clear the listing hold once 429 stops."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        return FakeResponse(url=url, json_data=DETAIL_PAYLOAD)

    cap = EbayDailyScheduleJobCap(
        access_token="token-abc",
        page_size=200,
        request_get=fake_request_get,
    ).bind_worker(worker)
    cap._record_listing_item_hold(
        error="eBay item 123456789012 returned status 429.",
        source_listing_id="123456789012",
        trigger_capability="ebay active stamps listing",
    )

    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={"report_date": "2026-04-13T09:20:00+08:00"},
            priority=90,
        )
    )

    assert result.status == "completed"
    assert result.result_summary["listing_probe_status"] == "released"
    hold_rows = pool._GetTableData(TABLE_EBAY_ACTIVE_RUNTIME, RUNTIME_LISTING_ITEM_HOLD_ROW_ID)
    assert len(hold_rows) == 1
    assert hold_rows[0]["metadata"]["active"] is False
    queued_jobs = pool._GetTableData(TABLE_JOBS) or []
    assert any(str(row.get("required_capability") or "") == "ebay active stamps page" for row in queued_jobs)


def test_ebay_daily_schedule_keeps_listing_hold_when_getitem_probe_still_429(tmp_path):
    """Daily schedule should keep the listing hold when the GetItem probe still 429s."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        return FakeResponse(url=url, status_code=429, json_data={"errors": [{"message": "Too Many Requests"}]})

    cap = EbayDailyScheduleJobCap(
        access_token="token-abc",
        page_size=200,
        request_get=fake_request_get,
    ).bind_worker(worker)
    cap._record_listing_item_hold(
        error="eBay item 123456789012 returned status 429.",
        source_listing_id="123456789012",
        trigger_capability="ebay active stamps listing",
    )

    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={"report_date": "2026-04-13T09:30:00+08:00"},
            priority=90,
        )
    )

    assert result.status == "completed"
    assert result.result_summary["listing_probe_status"] == "rate_limited"
    hold_rows = pool._GetTableData(TABLE_EBAY_ACTIVE_RUNTIME, RUNTIME_LISTING_ITEM_HOLD_ROW_ID)
    assert len(hold_rows) == 1
    assert hold_rows[0]["metadata"]["active"] is True
    queued_jobs = pool._GetTableData(TABLE_JOBS) or []
    assert any(str(row.get("required_capability") or "") == "ebay active stamps page" for row in queued_jobs)


def test_ebay_daily_schedule_releases_colnect_hold_after_successful_probe(tmp_path):
    """Daily schedule should release the shared Colnect hold only after a clean Colnect probe."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        if "colnect.com" in str(url):
            return FakeResponse("<html><body>Colnect OK</body></html>", url=url)
        return FakeResponse(url=url, json_data=DETAIL_PAYLOAD)

    ensure_dispatcher_tables(
        pool,
        [TABLE_COLNECT_RUNTIME, TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={
            TABLE_COLNECT_RUNTIME: colnect_runtime_table_schema(),
            TABLE_SALES_LISTINGS: sales_listings_table_schema(),
        },
    )

    colnect_cap = ColnectStampPageJobCap(request_get=fake_request_get).bind_worker(worker)
    colnect_cap._record_global_rate_limit_hold(
        error="Colnect page returned status 429.",
        trigger_capability="Colnect Stamp Page",
    )

    cap = EbayDailyScheduleJobCap(
        access_token="token-abc",
        page_size=200,
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={"report_date": "2026-04-13T09:20:00+08:00"},
            priority=90,
        )
    )

    assert result.status == "completed"
    assert result.result_summary["colnect_probe_status"] == "released"
    assert result.result_summary["colnect_probe_url"] == "https://colnect.com/en/stamps/list"
    hold_rows = pool._GetTableData(TABLE_COLNECT_RUNTIME, {"id": "global-rate-limit"})
    assert len(hold_rows) == 1
    assert hold_rows[0]["metadata"]["active"] is False
    assert hold_rows[0]["metadata"]["release_reason"]


def test_ebay_daily_schedule_solves_colnect_anubis_probe_before_release(tmp_path):
    """The 10-minute schedule probe should solve Colnect's Anubis challenge before deciding the lock is still blocked."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    target_url = "https://colnect.com/en/stamps/list"
    pass_url = "https://colnect.com/.within.website/x/cmd/anubis/api/pass-challenge"
    target_hits = 0

    def fake_request_get(url, **kwargs):
        nonlocal target_hits
        if url == target_url:
            target_hits += 1
            if target_hits == 1:
                return FakeResponse(ANUBIS_CHALLENGE_HTML, url=url)
            return FakeResponse("<html><body>Colnect OK after challenge</body></html>", url=url)
        if url == pass_url:
            params = dict(kwargs.get("params") or {})
            assert params["id"] == "challenge-123"
            assert params["redir"] == target_url
            headers = dict(kwargs.get("headers") or {})
            assert headers["Referer"] == target_url
            assert headers["Sec-Fetch-Site"] == "same-origin"
            return FakeResponse("<html><body>Colnect OK after proof</body></html>", url=target_url)
        return FakeResponse(url=url, json_data=DETAIL_PAYLOAD)

    ensure_dispatcher_tables(
        pool,
        [TABLE_COLNECT_RUNTIME, TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={
            TABLE_COLNECT_RUNTIME: colnect_runtime_table_schema(),
            TABLE_SALES_LISTINGS: sales_listings_table_schema(),
        },
    )

    colnect_cap = ColnectStampPageJobCap(request_get=fake_request_get).bind_worker(worker)
    colnect_cap._record_global_rate_limit_hold(
        error="Colnect page returned status 429.",
        trigger_capability="Colnect Stamp Page",
    )

    cap = EbayDailyScheduleJobCap(
        access_token="token-abc",
        page_size=200,
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="10 Minutes Scheduled Job",
            payload={"report_date": "2026-04-13T09:20:00+08:00"},
            priority=90,
        )
    )

    assert result.status == "completed"
    assert result.result_summary["colnect_probe_status"] == "released"
    assert target_hits == 1
    hold_rows = pool._GetTableData(TABLE_COLNECT_RUNTIME, {"id": "global-rate-limit"})
    assert len(hold_rows) == 1
    assert hold_rows[0]["metadata"]["active"] is False
    assert hold_rows[0]["metadata"]["last_probe_status"] == "released"


def test_ebay_daily_schedule_records_colnect_lock_check_when_hold_is_not_active(tmp_path):
    """Every 10-minute schedule run should update Colnect lock-check metadata even when no hold is active."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    colnect_request_hits = 0

    def fake_request_get(url, **kwargs):
        nonlocal colnect_request_hits
        if "colnect.com" in str(url):
            colnect_request_hits += 1
            raise AssertionError("Colnect should not be fetched when there is no active hold.")
        return FakeResponse(url=url, json_data=DETAIL_PAYLOAD)

    ensure_dispatcher_tables(
        pool,
        [TABLE_COLNECT_RUNTIME, TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={
            TABLE_COLNECT_RUNTIME: colnect_runtime_table_schema(),
            TABLE_SALES_LISTINGS: sales_listings_table_schema(),
        },
    )

    cap = EbayDailyScheduleJobCap(
        access_token="token-abc",
        page_size=200,
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="10 Minutes Scheduled Job",
            payload={"report_date": "2026-04-13T09:10:00+08:00"},
            priority=90,
        )
    )

    assert result.status == "completed"
    assert result.result_summary["colnect_probe_status"] == "not_active"
    assert result.result_summary["colnect_probe_url"] == "https://colnect.com/en/stamps/list"
    assert colnect_request_hits == 0
    hold_rows = pool._GetTableData(TABLE_COLNECT_RUNTIME, {"id": "global-rate-limit"})
    assert len(hold_rows) == 1
    assert hold_rows[0]["metadata"]["active"] is False
    assert hold_rows[0]["metadata"]["release_pending"] is False
    assert hold_rows[0]["metadata"]["last_probe_status"] == "not_active"
    assert hold_rows[0]["metadata"]["last_probe_url"] == "https://colnect.com/en/stamps/list"
    assert hold_rows[0]["metadata"]["last_probe_at"]


def test_ebay_daily_schedule_keeps_colnect_hold_when_probe_still_blocked(tmp_path):
    """Daily schedule should keep the shared Colnect hold active when the probe is still blocked."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        if "colnect.com" in str(url):
            return FakeResponse("too many requests", status_code=429, url=url)
        return FakeResponse(url=url, json_data=DETAIL_PAYLOAD)

    ensure_dispatcher_tables(
        pool,
        [TABLE_COLNECT_RUNTIME, TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={
            TABLE_COLNECT_RUNTIME: colnect_runtime_table_schema(),
            TABLE_SALES_LISTINGS: sales_listings_table_schema(),
        },
    )

    colnect_cap = ColnectStampPageJobCap(request_get=fake_request_get).bind_worker(worker)
    colnect_cap._record_global_rate_limit_hold(
        error="Colnect page returned status 429.",
        trigger_capability="Colnect Stamp Page",
    )

    cap = EbayDailyScheduleJobCap(
        access_token="token-abc",
        page_size=200,
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={"report_date": "2026-04-13T09:30:00+08:00"},
            priority=90,
        )
    )

    assert result.status == "completed"
    assert result.result_summary["colnect_probe_status"] == "rate_limited"
    hold_rows = pool._GetTableData(TABLE_COLNECT_RUNTIME, {"id": "global-rate-limit"})
    assert len(hold_rows) == 1
    assert hold_rows[0]["metadata"]["active"] is True
    assert hold_rows[0]["metadata"]["last_probe_status"] == "rate_limited"
    assert hold_rows[0]["metadata"]["last_probe_url"] == "https://colnect.com/en/stamps/list"
    assert hold_rows[0]["metadata"]["last_probe_http_status"] == 429
    assert hold_rows[0]["metadata"]["last_probe_at"]


def test_ebay_active_stamp_page_job_retries_and_can_be_claimed_again(tmp_path):
    """A non-connection eBay page failure should stay claimable while attempts remain."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool, [TABLE_JOBS])
    agent = DispatcherAgent(pool=pool)
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        raise RuntimeError("unexpected parse failure")

    cap = EbayActiveStampPageJobCap(
        search_url="https://api.ebay.test/buy/browse/v1/item_summary/search",
        access_token="token-abc",
        request_get=fake_request_get,
    ).bind_worker(worker)

    submitted = agent.submit_job(
        required_capability="eBay Active Stamps Page",
        payload={
            "search_run_id": "ebay-active-run",
            "page_number": 1,
            "keywords": "",
            "category_id": "260",
            "page_size": 200,
        },
        priority=PAGE_JOB_PRIORITY,
        max_attempts=3,
    )["job"]

    claimed = agent.claim_job(worker_id="worker-a", capabilities=["ebay active stamps page"])["job"]
    assert claimed["id"] == submitted["id"]
    assert claimed["attempts"] == 1

    result = cap.finish(JobDetail.model_validate(claimed))
    assert result.status == "retry"
    assert result.result_summary["retryable"] is True

    report = agent.report_job_result(
        job_id=claimed["id"],
        worker_id="worker-a",
        status=result.status,
        error=result.error,
        result_summary=result.result_summary,
        raw_payload=result.raw_payload,
    )

    assert report["job"]["status"] == "retry"
    reclaimed = agent.claim_job(worker_id="worker-b", capabilities=["ebay active stamps page"])["job"]
    assert reclaimed["id"] == claimed["id"]
    assert reclaimed["attempts"] == 2


def test_ebay_active_stamp_page_job_last_attempt_stays_failed(tmp_path):
    """The last allowed non-connection failure should stay failed for dispatcher reissue."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        raise RuntimeError("unexpected parse failure")

    cap = EbayActiveStampPageJobCap(
        search_url="https://api.ebay.test/buy/browse/v1/item_summary/search",
        access_token="token-abc",
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Page",
            payload={
                "search_run_id": "ebay-active-run",
                "page_number": 1,
                "keywords": "",
                "category_id": "260",
                "page_size": 200,
            },
            priority=PAGE_JOB_PRIORITY,
            attempts=3,
            max_attempts=3,
        )
    )

    assert result.status == "failed"
    assert result.result_summary["retryable"] is False


def test_ebay_active_stamp_page_job_logs_reissued_job_after_connection_timeout(tmp_path):
    """A connection timeout should log the replacement job id and queue the reissued page job."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        raise ReadTimeout("HTTPSConnectionPool(host='api.ebay.com', port=443): Read timed out.")

    cap = EbayActiveStampPageJobCap(
        search_url="https://api.ebay.test/buy/browse/v1/item_summary/search",
        access_token="token-abc",
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Page",
            payload={
                "job_kind": "page",
                "search_run_id": "ebay-active-run",
                "page_number": 1,
                "keywords": "stamp",
                "category_id": "260",
                "page_size": 200,
            },
            priority=PAGE_JOB_PRIORITY,
            max_attempts=5,
        )
    )

    assert result.status == "failed"
    assert result.result_summary["connection_issue"] is True
    assert result.result_summary["reissued_priority"] == PAGE_JOB_PRIORITY + 1
    reissued_job_id = result.result_summary["reissued_job_id"]
    assert reissued_job_id

    queued_jobs = [dict(row) for row in (pool._GetTableData(TABLE_JOBS) or [])]
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["id"] == reissued_job_id
    assert queued_jobs[0]["status"] == "queued"
    assert queued_jobs[0]["priority"] == PAGE_JOB_PRIORITY + 1

    assert any(
        f"eBay page job 1: connection issue; queued replacement job {reissued_job_id} after failure (retry 1, priority {PAGE_JOB_PRIORITY + 1})."
        in message
        for message in worker.log_messages
    )


def test_ebay_daily_schedule_job_queues_auction_status_and_page_jobs(tmp_path):
    """The daily schedule should queue auction status refreshes and one 10-minute auction page job."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "ebay:auction-ended",
            "listing_uid": "ebay:auction-ended",
            "provider": "ebay",
            "source_listing_id": "auction-ended",
            "marketplace_site": "www.ebay.com",
            "source_category_id": "260",
            "source_query": "stamp",
            "listing_status": "active",
            "sale_type": "AUCTION",
            "title": "Auction listing",
            "subtitle": "",
            "listing_url": "https://www.ebay.com/itm/auction-ended",
            "search_page": 1,
            "listing_position": 0,
            "sold_at": "",
            "price_amount": 10.0,
            "price_currency": "USD",
            "shipping_amount": 0.0,
            "shipping_currency": "USD",
            "total_amount": 10.0,
            "condition_text": "Used",
            "seller_name": "big-seller",
            "location_text": "Osaka, Japan",
            "image_url": "",
            "image_urls": [],
            "image_local_paths": [],
            "source_url": "https://api.ebay.test/browse",
            "payload": {
                "item_end_date": "2026-04-01T00:00:00Z",
                "item_origin_date": "2026-03-01T00:00:00Z",
                "seller_feedback_score": 12000,
            },
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "ebay:fixed-ended",
            "listing_uid": "ebay:fixed-ended",
            "provider": "ebay",
            "source_listing_id": "fixed-ended",
            "marketplace_site": "www.ebay.com",
            "source_category_id": "260",
            "source_query": "stamp",
            "listing_status": "active",
            "sale_type": "FIXED_PRICE",
            "title": "Fixed listing",
            "subtitle": "",
            "listing_url": "https://www.ebay.com/itm/fixed-ended",
            "search_page": 1,
            "listing_position": 0,
            "sold_at": "",
            "price_amount": 10.0,
            "price_currency": "USD",
            "shipping_amount": 0.0,
            "shipping_currency": "USD",
            "total_amount": 10.0,
            "condition_text": "Used",
            "seller_name": "small-seller",
            "location_text": "Taipei, Taiwan",
            "image_url": "",
            "image_urls": [],
            "image_local_paths": [],
            "source_url": "https://api.ebay.test/browse",
            "payload": {
                "item_end_date": "2026-04-01T00:00:00Z",
                "item_origin_date": "2026-03-15T00:00:00Z",
                "seller_feedback_score": 100,
            },
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    cap = EbayDailyScheduleJobCap(
        access_token="token-abc",
        page_size=200,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={
                "report_date": "2026-04-11",
                "sort": "-price",
            },
            priority=90,
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_status_jobs"] == 1
    assert result.result_summary["queued_page_jobs"] == 1
    assert result.result_summary["planned_retrieval_items"] == 200
    assert result.result_summary["import_stop_after"] == 60
    assert result.result_summary["window_minutes"] == 15
    assert result.result_summary["page_size"] == 200
    fan_out_updates = [
        update
        for update in worker.progress_updates
        if update.get("extra", {}).get("fan_out_kind") == "status_and_page"
        and "preparing fan-out" in str(update.get("message") or "")
    ]
    assert fan_out_updates
    assert "itemEndDate:[.." in str(fan_out_updates[0].get("message") or "")
    assert fan_out_updates[0].get("extra", {}).get("browse_item_end_filter", "").startswith("itemEndDate:[..")
    assert any("queued 1 status fan-out jobs and 1 page fan-out jobs" in message for message in worker.log_messages)

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: (row["priority"], row["id"]))
    assert len(queued_jobs) == 2
    assert queued_jobs[0]["required_capability"] == "ebay active stamps status"
    assert queued_jobs[0]["priority"] == STATUS_JOB_PRIORITY
    assert queued_jobs[0]["payload"]["source_listing_ids"] == ["auction-ended"]
    assert queued_jobs[0]["payload"]["auction_only"] is True
    assert [row["required_capability"] for row in queued_jobs[1:]] == ["ebay active stamps page"]
    assert all(row["payload"]["buying_options"] == ["AUCTION"] for row in queued_jobs[1:])
    assert all(row["payload"]["min_bid_count"] == 1 for row in queued_jobs[1:])
    assert all(row["payload"]["page_size"] == 200 for row in queued_jobs[1:])
    assert all(row["payload"]["target_new_items"] == 60 for row in queued_jobs[1:])
    assert all(row["payload"]["import_stop_after"] == 60 for row in queued_jobs[1:])
    assert all(row["payload"]["keywords"] == "stamp" for row in queued_jobs[1:])
    assert all(row["payload"]["sort"] == "-price" for row in queued_jobs[1:])
    page_window_starts = [datetime.fromisoformat(row["payload"]["item_end_date_from"].replace("Z", "+00:00")) for row in queued_jobs[1:]]
    page_window_ends = [datetime.fromisoformat(row["payload"]["item_end_date_to"].replace("Z", "+00:00")) for row in queued_jobs[1:]]
    assert all(end > start for start, end in zip(page_window_starts, page_window_ends))
    assert all(int((end - start).total_seconds()) == 15 * 60 for start, end in zip(page_window_starts, page_window_ends))

    report_rows = pool._GetTableData(TABLE_EBAY_ACTIVE_DAILY_REPORTS)
    assert len(report_rows) == 1
    assert report_rows[0]["planned_status_jobs"] == 1
    assert report_rows[0]["planned_page_jobs"] == 1
    assert report_rows[0]["planned_retrieval_items"] == 200
    assert all(row["payload"]["report_date"] == "2026-04-11" for row in queued_jobs)


def test_ebay_daily_schedule_job_ignores_older_claimed_daily_page_work_and_keeps_queueing(tmp_path):
    """Daily schedule should ignore older claimed page work and still queue its own page job."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "ebay:auction-ended",
            "listing_uid": "ebay:auction-ended",
            "provider": "ebay",
            "source_listing_id": "auction-ended",
            "marketplace_site": "www.ebay.com",
            "source_category_id": "260",
            "source_query": "stamp",
            "listing_status": "active",
            "sale_type": "AUCTION",
            "title": "Auction listing",
            "subtitle": "",
            "listing_url": "https://www.ebay.com/itm/auction-ended",
            "search_page": 1,
            "listing_position": 0,
            "sold_at": "",
            "price_amount": 10.0,
            "price_currency": "USD",
            "shipping_amount": 0.0,
            "shipping_currency": "USD",
            "total_amount": 10.0,
            "condition_text": "Used",
            "seller_name": "big-seller",
            "location_text": "Osaka, Japan",
            "image_url": "",
            "image_urls": [],
            "image_local_paths": [],
            "source_url": "https://api.ebay.test/browse",
            "payload": {
                "item_end_date": "2026-04-01T00:00:00Z",
                "item_origin_date": "2026-03-01T00:00:00Z",
                "seller_feedback_score": 12000,
            },
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )
    existing_page_row = build_dispatch_job(
        required_capability="eBay Active Stamps Page",
        payload={
            "page_number": 1,
            "report_date": "2026-04-11",
            "search_run_id": "ebay-daily-auction-2026-04-11t16-30-00-08-00",
        },
        priority=PAGE_JOB_PRIORITY,
        max_attempts=5,
        scheduled_for="2026-04-11T16:30:00+08:00",
    ).to_row()
    existing_page_row["status"] = "claimed"
    existing_page_row["claimed_by"] = "worker-a"
    existing_page_row["claimed_at"] = utcnow_iso()
    existing_page_row["updated_at"] = utcnow_iso()
    pool._Insert(TABLE_JOBS, existing_page_row)

    cap = EbayDailyScheduleJobCap(
        access_token="token-abc",
        page_size=200,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={
                "report_date": "2026-04-11",
                "sort": "-price",
            },
            priority=90,
            scheduled_for="2026-04-11T16:40:00+08:00",
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_status_jobs"] == 1
    assert result.result_summary["queued_page_jobs"] == 1
    assert result.result_summary["page_queue_blocked"] is False
    assert result.result_summary["active_page_job_id"] == ""
    assert result.result_summary["page_queue_block_reason"] == ""
    assert result.result_summary["superseded_daily_search_jobs"] == 0
    assert result.result_summary["cancelled_daily_search_jobs"] == 0
    assert result.result_summary["force_terminated_daily_search_jobs"] == 0
    assert result.result_summary["daily_search_supersede_reason"] == ""

    latest_old = _latest_job_row(pool, str(existing_page_row["id"]))
    assert latest_old["status"] == "claimed"
    assert latest_old["claimed_by"] == "worker-a"
    assert "control" not in (latest_old.get("metadata") or {})

    queued_status_jobs = [
        row
        for row in (pool._GetTableData(TABLE_JOBS) or [])
        if row["required_capability"] == "ebay active stamps status"
    ]
    queued_page_jobs = [
        row
        for row in (pool._GetTableData(TABLE_JOBS) or [])
        if row["required_capability"] == "ebay active stamps page"
        and str((row.get("payload") or {}).get("search_run_id") or "") == "ebay-daily-auction-2026-04-11"
    ]
    assert len(queued_status_jobs) == 1
    assert len(queued_page_jobs) == 1
    assert not any("daily page/listing jobs before page fan-out" in message for message in worker.log_messages)

    report_rows = pool._GetTableData(TABLE_EBAY_ACTIVE_DAILY_REPORTS)
    assert len(report_rows) == 1
    assert report_rows[0]["planned_page_jobs"] == 1


def test_ebay_daily_schedule_job_ignores_older_queued_daily_listing_work_and_keeps_queueing(tmp_path):
    """Daily schedule should ignore older queued listing work and still queue its own page job."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )

    older_listing_row = build_dispatch_job(
        required_capability="eBay Active Stamps Listing",
        payload={
            "page_number": 1,
            "report_date": "2026-04-11T16:30:00+08:00",
            "search_run_id": "ebay-daily-auction-2026-04-11t16-30-00-08-00",
            "source_listing_id": "older-listing",
        },
        priority=LISTING_JOB_PRIORITY,
        max_attempts=5,
        job_id="dispatcher-job:ebay-daily-old-listing-queued",
        scheduled_for="2026-04-11T16:30:00+08:00",
    ).to_row()
    older_listing_row["status"] = "queued"
    pool._Insert(TABLE_JOBS, older_listing_row)

    cap = EbayDailyScheduleJobCap(
        access_token="token-abc",
        page_size=200,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={
                "report_date": "2026-04-11T16:40:00+08:00",
                "sort": "-price",
                "status_item_limit": 1,
            },
            priority=90,
            scheduled_for="2026-04-11T16:40:00+08:00",
        )
    )

    latest_old = _latest_job_row(pool, "dispatcher-job:ebay-daily-old-listing-queued")

    assert result.status == "completed"
    assert result.result_summary["queued_page_jobs"] == 1
    assert result.result_summary["page_queue_blocked"] is False
    assert result.result_summary["active_page_job_id"] == ""
    assert result.result_summary["page_queue_block_reason"] == ""
    assert result.result_summary["superseded_daily_search_jobs"] == 0
    assert result.result_summary["cancelled_daily_search_jobs"] == 0
    assert result.result_summary["force_terminated_daily_search_jobs"] == 0
    assert result.result_summary["daily_search_supersede_reason"] == ""
    assert latest_old["status"] == "queued"
    assert "control" not in (latest_old.get("metadata") or {})

    queued_page_jobs = [
        row
        for row in (pool._GetTableData(TABLE_JOBS) or [])
        if row["required_capability"] == "ebay active stamps page"
        and row["id"] != "dispatcher-job:ebay-daily-old-listing-queued"
    ]
    assert len(queued_page_jobs) == 1
    assert not any("daily page/listing jobs before page fan-out" in message for message in worker.log_messages)


def test_ebay_daily_schedule_job_cancels_older_queued_schedule_jobs(tmp_path):
    """Newer daily schedules should cancel older queued schedules before fan-out."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )

    older_schedule_row = build_dispatch_job(
        required_capability="eBay Daily Schedule",
        payload={"sort": "-price"},
        priority=90,
        max_attempts=5,
        scheduled_for="2026-04-13T16:30:00+08:00",
        job_id="dispatcher-job:ebay-daily-old-queued",
    ).to_row()
    older_schedule_row["status"] = "queued"
    pool._Insert(TABLE_JOBS, older_schedule_row)

    cap = EbayDailyScheduleJobCap(
        access_token="token-abc",
        page_size=200,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={"sort": "-price"},
            priority=90,
            scheduled_for="2026-04-13T16:40:00+08:00",
        )
    )

    latest_old = _latest_job_row(pool, "dispatcher-job:ebay-daily-old-queued")

    assert result.status == "completed"
    assert result.result_summary["queued_page_jobs"] == 1
    assert result.result_summary["superseded_daily_schedule_jobs"] == 1
    assert result.result_summary["cancelled_daily_schedule_jobs"] == 1
    assert result.result_summary["force_terminated_daily_schedule_jobs"] == 0
    assert latest_old["status"] == "cancelled"
    assert latest_old["metadata"]["control"]["effective_action"] == "cancel"


def test_ebay_daily_schedule_job_force_terminates_older_claimed_schedule_jobs(tmp_path):
    """Newer daily schedules should force terminate older claimed schedules before fan-out."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )

    older_schedule_row = build_dispatch_job(
        required_capability="eBay Daily Schedule",
        payload={"sort": "-price"},
        priority=90,
        max_attempts=5,
        scheduled_for="2026-04-13T16:30:00+08:00",
        job_id="dispatcher-job:ebay-daily-old-claimed",
    ).to_row()
    older_schedule_row["status"] = "claimed"
    older_schedule_row["claimed_by"] = "worker-old"
    older_schedule_row["claimed_at"] = utcnow_iso()
    older_schedule_row["updated_at"] = utcnow_iso()
    pool._Insert(TABLE_JOBS, older_schedule_row)

    cap = EbayDailyScheduleJobCap(
        access_token="token-abc",
        page_size=200,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={"sort": "-price"},
            priority=90,
            scheduled_for="2026-04-13T16:40:00+08:00",
        )
    )

    latest_old = _latest_job_row(pool, "dispatcher-job:ebay-daily-old-claimed")

    assert result.status == "completed"
    assert result.result_summary["superseded_daily_schedule_jobs"] == 1
    assert result.result_summary["cancelled_daily_schedule_jobs"] == 0
    assert result.result_summary["force_terminated_daily_schedule_jobs"] == 1
    assert latest_old["status"] == "failed"
    assert latest_old["result_summary"]["force_terminated"] is True
    assert latest_old["metadata"]["control"]["effective_action"] == "force_terminate"


def _report_row_id(report_date: str) -> str:
    """Return the persisted report-row id used by the jobcap."""
    return f"ebay-active-daily:{report_date}"


def test_build_job_cap_resolves_env_backed_ebay_report_settings(monkeypatch):
    """Worker job-cap config should resolve env references before instantiation."""
    monkeypatch.setenv("EBAY_DAILY_REPORT_EMAIL_TO", "reports@example.com")
    monkeypatch.setenv("SES_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("SES_REGION", "us-west-2")

    config_path = Path(__file__).resolve().parents[2] / "private" / "collectibles" / "configs" / "worker_dashboard.agent"
    entries = json.loads(config_path.read_text(encoding="utf-8"))["dispatcher"]["job_capabilities"]
    entry = next(item for item in entries if item.get("name") == "10 Minutes Scheduled Job")
    cap = build_job_cap(entry)

    assert cap.daily_report_email_to == "reports@example.com"
    assert cap.daily_report_email_from == "noreply@example.com"
    assert cap.daily_report_ses_region == "us-west-2"


def test_ebay_daily_schedule_uses_scheduled_for_as_report_key_when_missing(tmp_path):
    """Recurring schedules should derive a unique report key from scheduled_for when payload.report_date is omitted."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )

    cap = EbayDailyScheduleJobCap(access_token="token-abc", page_size=200).bind_worker(worker)
    scheduled_for = "2026-04-12T02:10:00+08:00"
    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={"sort": "-price"},
            priority=90,
            scheduled_for=scheduled_for,
        )
    )

    assert result.status == "completed"
    assert result.result_summary["report_date"] == scheduled_for
    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "ebay active stamps page"
    assert queued_jobs[0]["payload"]["report_date"] == scheduled_for
    assert queued_jobs[0]["payload"]["target_new_items"] == 60
    assert queued_jobs[0]["payload"]["import_stop_after"] == 60
    assert queued_jobs[0]["payload"]["keywords"] == "stamp"
    assert result.result_summary["daily_report_id"] == _report_row_id(scheduled_for)


def test_ebay_daily_reports_can_be_disabled_for_live_workers(tmp_path):
    """When disabled, eBay jobs should not create or finalize daily report rows."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={TABLE_SALES_LISTINGS: sales_listings_table_schema()},
    )

    cap = EbayDailyScheduleJobCap(
        access_token="token-abc",
        page_size=200,
        daily_reports_enabled=False,
    ).bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={"report_date": "2026-04-13T10:40:00+08:00"},
            priority=90,
        )
    )

    assert result.status == "completed"
    assert result.result_summary.get("daily_report_id", "") == ""
    assert (pool._GetTableData(TABLE_EBAY_ACTIVE_DAILY_REPORTS) or []) == []
    queued_jobs = pool._GetTableData(TABLE_JOBS) or []
    assert any(str(row.get("required_capability") or "") == "ebay active stamps page" for row in queued_jobs)


def test_ebay_daily_schedule_ignores_legacy_hold_rows(tmp_path):
    """Legacy runtime hold rows should not block daily schedule processing."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_SALES_LISTINGS],
        extra_schemas={
            TABLE_SALES_LISTINGS: sales_listings_table_schema(),
        },
    )

    cap = EbayDailyScheduleJobCap(access_token="token-abc", page_size=200).bind_worker(worker)
    cap._ensure_runtime_tables(pool)
    pool._Insert(
        TABLE_EBAY_ACTIVE_RUNTIME,
        {
            "id": "api-rate-limit",
            "scope": "browse-api",
            "hold_until": "2099-01-01T00:00:00+00:00",
            "hold_reason": "legacy",
            "updated_at": utcnow_iso(),
            "metadata": {"provider": "ebay"},
        },
    )
    result = cap.finish(
        _job(
            required_capability="eBay Daily Schedule",
            payload={"report_date": "2026-04-12T00:10:00+08:00"},
            priority=90,
        )
    )

    assert result.status == "completed"
    queued_jobs = pool._GetTableData(TABLE_JOBS) or []
    assert queued_jobs
    assert any(str(row.get("required_capability") or "") == "ebay active stamps page" for row in queued_jobs)


def test_ebay_active_stamp_jobcap_ignores_legacy_hold_rows_for_capabilities(tmp_path):
    """Legacy runtime hold rows should not hide eBay capabilities from worker advertisement."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    cap = EbayActiveStampPageJobCap(access_token="token-abc")
    worker = DispatcherWorkerAgent(
        name="test-worker",
        host="127.0.0.1",
        port=0,
        plaza_url="",
        pool=pool,
        dispatcher_address="http://127.0.0.1:9999",
        capabilities=["eBay Active Stamps Page"],
        job_capabilities=[cap],
        auto_register=False,
    )
    cap.bind_worker(worker)
    cap._ensure_runtime_tables(pool)
    pool._Insert(
        TABLE_EBAY_ACTIVE_RUNTIME,
        {
            "id": "api-rate-limit",
            "scope": "browse-api",
            "hold_until": "2099-01-01T00:00:00+00:00",
            "hold_reason": "legacy",
            "updated_at": utcnow_iso(),
            "metadata": {"provider": "ebay"},
        },
    )

    assert cap.advertised_capabilities() == ["ebay active stamps page"]
    assert worker.advertised_capabilities() == ["ebay active stamps page"]


def test_ebay_active_stamp_page_job_ignores_legacy_hold_rows(tmp_path):
    """Legacy runtime hold rows should not stop page-job processing."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        return FakeResponse(url=url, json_data=SEARCH_PAYLOAD)

    cap = EbayActiveStampPageJobCap(
        search_url="https://api.ebay.test/buy/browse/v1/item_summary/search",
        access_token="token-abc",
        request_get=fake_request_get,
        page_size=2,
    ).bind_worker(worker)
    cap._ensure_runtime_tables(pool)
    pool._Insert(
        TABLE_EBAY_ACTIVE_RUNTIME,
        {
            "id": "api-rate-limit",
            "scope": "browse-api",
            "hold_until": "2099-01-01T00:00:00+00:00",
            "hold_reason": "legacy",
            "updated_at": utcnow_iso(),
            "metadata": {"provider": "ebay"},
        },
    )

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Page",
            payload={
                "search_run_id": "ebay-active-run",
                "page_number": 1,
                "keywords": "stamp",
                "category_id": "260",
                "page_size": 2,
            },
            priority=PAGE_JOB_PRIORITY,
        )
    )

    assert result.status == "completed"
    queued_jobs = pool._GetTableData(TABLE_JOBS) or []
    assert len(queued_jobs) == 2


def test_listing_dispatch_priority_prefers_auctions_and_high_feedback():
    """Listing priority should favor auctions and stronger seller feedback tiers."""
    fixed_low = _listing_dispatch_priority({"sale_type": "FIXED_PRICE", "seller_feedback_score": 4200})
    fixed_5k = _listing_dispatch_priority({"sale_type": "FIXED_PRICE", "seller_feedback_score": 5000})
    fixed_10k = _listing_dispatch_priority({"sale_type": "FIXED_PRICE", "seller_feedback_score": 10000})
    fixed_50k = _listing_dispatch_priority({"sale_type": "FIXED_PRICE", "seller_feedback_score": 50000})
    fixed_100k = _listing_dispatch_priority({"sale_type": "FIXED_PRICE", "seller_feedback_score": 100000})
    auction_100k = _listing_dispatch_priority({"sale_type": "AUCTION", "seller_feedback_score": 100000})

    assert PAGE_JOB_PRIORITY < auction_100k
    assert fixed_low == LISTING_JOB_PRIORITY
    assert fixed_5k == LISTING_JOB_PRIORITY - 1
    assert fixed_10k == LISTING_JOB_PRIORITY - 2
    assert fixed_50k == LISTING_JOB_PRIORITY - 3
    assert fixed_100k == LISTING_JOB_PRIORITY - 4
    assert auction_100k == PAGE_JOB_PRIORITY + 1


def test_ebay_active_stamp_listing_job_persists_row_and_queues_image_job(tmp_path):
    """Listing job should fetch detail, persist the row, and enqueue the image job."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        if url == "https://api.ebay.com/buy/browse/v1/item/get_item_by_legacy_id":
            params = dict(kwargs.get("params") or {})
            assert params["legacy_item_id"] == "123456789012"
            return FakeResponse(url=url, json_data=DETAIL_PAYLOAD)
        raise AssertionError(f"Unexpected URL: {url}")

    cap = EbayActiveStampListingJobCap(access_token="token", request_get=fake_request_get).bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Listing",
            priority=LISTING_JOB_PRIORITY,
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
                "item_end_date": "2026-04-20T12:00:00Z",
                "sale_type": "FIXED_PRICE",
                "listing_status": "active",
                "report_date": "2026-04-11T02:00:00+08:00",
                "payload": {"item_summary": {"legacyItemId": "123456789012"}},
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_job_queued"] is True
    assert result.result_summary["ebay_response_keys"] == ["browse_item_detail", "browse_item_summary"]
    assert result.raw_payload["ebay_responses"]["browse_item_summary"] == {"legacyItemId": "123456789012"}
    assert result.raw_payload["ebay_responses"]["browse_item_detail"]["legacyItemId"] == "123456789012"

    rows = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:123456789012")
    assert len(rows) == 1
    assert rows[0]["source_listing_id"] == "123456789012"
    assert rows[0]["title"] == "1920 China Junk stamp lot"
    assert rows[0]["listing_status"] == "active"
    assert float(rows[0]["price_amount"]) == 12.5
    assert float(rows[0]["shipping_amount"]) == 3.25
    assert float(rows[0]["total_amount"]) == 15.75
    assert rows[0]["payload"]["item_end_date"] == "2026-04-20T12:00:00Z"
    assert rows[0]["payload"]["item_detail"]["legacyItemId"] == "123456789012"

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "ebay active stamps image"
    assert queued_jobs[0]["payload"]["source_listing_id"] == "123456789012"
    assert queued_jobs[0]["priority"] == IMAGE_JOB_PRIORITY
    assert queued_jobs[0]["payload"]["report_date"] == "2026-04-11T02:00:00+08:00"


def test_ebay_active_stamp_listing_job_uses_cached_seller_account_name(tmp_path):
    """Listing job should reuse a cached seller account name instead of the Browse API token."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_EBAY_ACTIVE_SELLER_ACCOUNTS],
        extra_schemas={TABLE_EBAY_ACTIVE_SELLER_ACCOUNTS: ebay_active_seller_accounts_table_schema()},
    )
    pool._Insert(
        TABLE_EBAY_ACTIVE_SELLER_ACCOUNTS,
        {
            "id": "ebay:seller-account:p1QEhNdAQZW",
            "provider": "ebay",
            "seller_key": "p1QEhNdAQZW",
            "account_name": "gsquared7",
            "source_listing_id": "366333117430",
            "listing_url": "https://www.ebay.com/itm/366333117430",
            "payload": {"lookup_source": "listing_page"},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    cap = EbayActiveStampListingJobCap().bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Listing",
            priority=LISTING_JOB_PRIORITY,
            payload={
                "source_listing_id": "366333117430",
                "item_id": "v1|366333117430|0",
                "listing_url": "https://www.ebay.com/itm/366333117430",
                "title": "U.S. Mint Postage Lot - $238 face",
                "price_amount": 86.0,
                "price_currency": "USD",
                "shipping_amount": 7.0,
                "shipping_currency": "USD",
                "total_amount": 93.0,
                "condition_text": "",
                "seller_name": "p1QEhNdAQZW",
                "location_text": "US",
                "image_url": "https://i.ebayimg.com/images/g/kqwAAeSwpRJp1VDT/s-l1600.jpg",
                "image_urls": ["https://i.ebayimg.com/images/g/kqwAAeSwpRJp1VDT/s-l1600.jpg"],
                "page_number": 9,
                "listing_position": 45,
                "keywords": "",
                "category_id": "260",
                "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?offset=480",
                "item_end_date": "2026-04-12T18:46:11.000Z",
                "sale_type": "AUCTION",
                "listing_status": "active",
                "payload": {
                    "item_summary": {
                        "legacyItemId": "366333117430",
                        "seller": {"username": "p1QEhNdAQZW", "feedbackScore": 109144},
                    }
                },
            },
        )
    )

    assert result.status == "completed"
    rows = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:366333117430")
    assert len(rows) == 1
    assert rows[0]["seller_name"] == "gsquared7"
    assert rows[0]["payload"]["page_seller_name"] == "gsquared7"
    assert rows[0]["payload"]["seller_lookup_key"] == "p1QEhNdAQZW"


def test_ebay_active_stamp_image_job_uses_image_priority_for_external_description_urls(tmp_path):
    """Image jobs with external description URLs should not outrank page or listing jobs."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool, [TABLE_JOBS])
    worker = FakeWorker(pool)
    cap = EbayActiveStampListingJobCap().bind_worker(worker)

    queued = cap._queue_image_job(
        source_listing_id="123456789012",
        listing_url="https://www.ebay.com/itm/123456789012",
        image_url="https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        image_urls=["https://i.ebayimg.com/images/g/AAA/s-l1600.jpg"],
        description_image_urls=["https://example.com/suspicious-image.jpg"],
        priority=LISTING_JOB_PRIORITY,
        report_date="2026-04-11T02:00:00+08:00",
    )

    assert queued["queued"] is True
    queued_jobs = pool._GetTableData(TABLE_JOBS) or []
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "ebay active stamps image"
    assert queued_jobs[0]["priority"] == IMAGE_JOB_PRIORITY


def test_ebay_active_stamp_page_job_finalizes_report_after_listing_fanout(tmp_path):
    """Daily reports should stop once page fan-out has created the listing jobs."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    report_date = "2026-04-12T16:40:00+08:00"

    search_payload = dict(SEARCH_PAYLOAD)
    search_payload["total"] = 2

    def fake_request_get(url, **kwargs):
        return FakeResponse(url=url, json_data=search_payload)

    cap = EbayActiveStampPageJobCap(
        search_url="https://api.ebay.test/buy/browse/v1/item_summary/search",
        access_token="token-abc",
        page_size=2,
        request_get=fake_request_get,
    ).bind_worker(worker)
    cap._upsert_daily_report(
        report_date,
        status="processing page",
        planned_page_jobs=1,
        planned_retrieval_items=60,
    )

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Page",
            priority=PAGE_JOB_PRIORITY,
            payload={
                "page_number": 1,
                "search_run_id": "ebay-daily-auction-2026-04-12t16-40-00-08-00",
                "search_key": "auction:stamp",
                "keywords": "stamp",
                "category_id": "260",
                "page_size": 2,
                "report_date": report_date,
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["daily_report_status"] == "finished"
    report_row = pool._GetTableData(TABLE_EBAY_ACTIVE_DAILY_REPORTS, _report_row_id(report_date))[0]
    assert report_row["status"] == "finished"
    assert report_row["retrieved_items"] == 0
    assert report_row["planned_page_jobs"] == 1
    assert report_row["planned_retrieval_items"] == 60
    assert report_row["payload"]["job_counts"]["active_jobs"] == 0
    assert report_row["payload"]["job_counts"]["completed_jobs"] == 1
    assert report_row["payload"]["queued_listing_jobs"] == 2
    shared_report = pool._GetTableData(TABLE_DISPATCHER_REPORT_ITEMS, ebay_daily_schedule_report_item_id(report_date))[0]
    assert shared_report["category_key"] == "ebay_daily_schedule"
    assert shared_report["status"] == "finished"
    assert shared_report["response_status"] == "new"
    assert shared_report["metrics"]["listings"] == 2
    assert any(
        update.get("extra", {}).get("fan_out_kind") == "listing"
        and "queued 2 listing fan-out jobs" in str(update.get("message") or "")
        for update in worker.progress_updates
    )


def test_ebay_active_stamp_listing_job_keeps_completed_report_frozen(tmp_path):
    """Completed daily reports should not reopen while listing/image jobs finish later."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    report_date = "2026-04-12T16:40:00+08:00"

    cap = EbayActiveStampListingJobCap().bind_worker(worker)
    report_row = cap._upsert_daily_report(
        report_date,
        status="finished",
        planned_page_jobs=1,
        planned_retrieval_items=60,
    )
    stored_before = pool._GetTableData(TABLE_EBAY_ACTIVE_DAILY_REPORTS, _report_row_id(report_date))[0]

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Listing",
            priority=LISTING_JOB_PRIORITY,
            payload={
                "source_listing_id": "377090566764",
                "item_id": "v1|377090566764|0",
                "listing_url": "https://www.ebay.com/itm/377090566764",
                "title": "Germany Reich 1933 Nothilfe very fine sheet TOP!",
                "price_amount": 348.0,
                "price_currency": "USD",
                "shipping_amount": 0.0,
                "shipping_currency": "USD",
                "total_amount": 348.0,
                "condition_text": "Used",
                "seller_name": "amsterdam-stamps",
                "location_text": "Gravenzande, NL",
                "image_url": "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
                "image_urls": ["https://i.ebayimg.com/images/g/AAA/s-l1600.jpg"],
                "page_number": 1,
                "listing_position": 0,
                "keywords": "stamp",
                "category_id": "260",
                "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp",
                "item_end_date": "2026-04-12T16:49:00Z",
                "sale_type": "AUCTION",
                "listing_status": "active",
                "report_date": report_date,
                "payload": {"item_summary": {"legacyItemId": "377090566764"}},
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["daily_report_status"] == "finished"
    frozen_row = pool._GetTableData(TABLE_EBAY_ACTIVE_DAILY_REPORTS, _report_row_id(report_date))[0]
    assert frozen_row["status"] == "finished"
    assert frozen_row["updated_at"] == stored_before["updated_at"]
    assert frozen_row["retrieved_items"] == stored_before["retrieved_items"]


def test_ebay_daily_report_feed_preserves_console_response_state(tmp_path):
    """Worker report updates should not wipe console response state from the shared feed."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    report_date = "2026-04-12T16:40:00+08:00"

    cap = EbayActiveStampListingJobCap().bind_worker(worker)
    cap._upsert_daily_report(
        report_date,
        status="processing page",
        planned_page_jobs=1,
        planned_retrieval_items=60,
    )
    shared_id = ebay_daily_schedule_report_item_id(report_date)
    shared_row = dict(pool._GetTableData(TABLE_DISPATCHER_REPORT_ITEMS, shared_id)[0])
    shared_row["response_status"] = "acknowledged"
    shared_row["response_note"] = "Watching this run."
    shared_row["responded_by"] = "console-a"
    shared_row["responded_at"] = utcnow_iso()
    assert pool._Insert(TABLE_DISPATCHER_REPORT_ITEMS, shared_row)

    cap._upsert_daily_report(
        report_date,
        status="finished",
        planned_page_jobs=1,
        planned_retrieval_items=60,
    )

    refreshed_row = pool._GetTableData(TABLE_DISPATCHER_REPORT_ITEMS, shared_id)[0]
    assert refreshed_row["status"] == "finished"
    assert refreshed_row["response_status"] == "acknowledged"
    assert refreshed_row["response_note"] == "Watching this run."
    assert refreshed_row["responded_by"] == "console-a"


def test_ebay_active_daily_report_counts_archived_completed_jobs(tmp_path):
    """Daily report synthesis should include completed jobs that already moved to the archive."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    report_date = "2026-04-12T16:40:00+08:00"

    ensure_dispatcher_tables(pool, [TABLE_JOBS])
    archived_job = build_dispatch_job(
        required_capability="eBay Active Stamps Listing",
        payload={
            "source_listing_id": "377090566764",
            "report_date": report_date,
        },
        job_id="dispatcher-job:ebay-active-stamps-listing:377090566764",
        target_table=TABLE_SALES_LISTINGS,
    ).to_row()
    archived_job["status"] = "completed"
    archived_job["completed_at"] = utcnow_iso()
    archived_job["updated_at"] = utcnow_iso()
    archived_job["archived_at"] = utcnow_iso()
    assert pool._Insert(TABLE_JOB_ARCHIVE, archived_job)

    cap = EbayActiveStampListingJobCap().bind_worker(worker)

    report_row = cap._build_daily_report_payload(report_date, status="processing page")

    assert report_row["retrieved_items"] == 1
    assert report_row["payload"]["job_counts"]["completed_jobs"] == 1
    assert report_row["payload"]["queued_listing_jobs"] == 1


def test_ebay_active_stamp_image_job_downloads_only_first_large_image_and_queues_follow_up_jobs(tmp_path):
    """Image job should upgrade thumbnail URLs, download one image, and queue the rest."""
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
            "image_url": "https://i.ebayimg.com/images/g/AAA/s-l225.jpg",
            "image_urls": [
                "https://i.ebayimg.com/images/g/AAA/s-l225.jpg",
                "https://i.ebayimg.com/images/g/CCC/s-l225.jpg",
            ],
            "image_local_paths": [],
            "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp",
            "payload": {"item_end_date": "2026-04-20T12:00:00Z"},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
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
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Image",
            payload={
                "source_listing_id": "123456789012",
                "listing_url": "https://www.ebay.com/itm/123456789012",
                "image_url": "https://i.ebayimg.com/images/g/AAA/s-l225.jpg",
                "image_urls": [
                    "https://i.ebayimg.com/images/g/AAA/s-l225.jpg",
                    "https://i.ebayimg.com/images/g/CCC/s-l225.jpg",
                ],
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_urls"] == ["https://i.ebayimg.com/images/g/AAA/s-l1600.jpg"]
    assert len(result.result_summary["image_local_paths"]) == 1
    assert result.result_summary["known_image_urls"] == [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
    ]
    assert result.result_summary["queued_follow_up_image_jobs"] == 1

    updated_rows = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:123456789012")
    assert len(updated_rows) == 1
    updated_row = updated_rows[0]
    assert updated_row["image_urls"] == [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
    ]
    assert len(updated_row["image_local_paths"]) == 2
    assert Path(updated_row["image_local_paths"][0]).exists()
    assert updated_row["image_local_paths"][1] == ""
    first_relative_path = Path(updated_row["image_local_paths"][0]).relative_to(media_root)
    assert first_relative_path.parts[:-1] == ("12", "34", "56", "78", "90", "12")
    assert first_relative_path.name == "ebay-123456789012-01.jpg"
    assert updated_row["payload"]["item_end_date"] == "2026-04-20T12:00:00Z"
    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "ebay active stamps image"
    assert queued_jobs[0]["payload"]["image_urls"] == ["https://i.ebayimg.com/images/g/CCC/s-l1600.jpg"]
    assert queued_jobs[0]["payload"]["gallery_image_urls"] == [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
    ]


def test_ebay_active_stamp_image_job_fans_out_extra_payload_image_urls_without_detail_lookup(tmp_path):
    """Image job should fan out extra payload image URLs while keeping stable file slots."""
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
            "image_url": "https://i.ebayimg.com/images/g/AAA/s-l225.jpg",
            "image_urls": ["https://i.ebayimg.com/images/g/AAA/s-l225.jpg"],
            "image_local_paths": [],
            "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp",
            "payload": {"item_end_date": "2026-04-20T12:00:00Z"},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        if url == "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg":
            return FakeResponse(status_code=200, url=url, content=b"first", headers={"Content-Type": "image/jpeg"})
        if url == "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg":
            return FakeResponse(status_code=200, url=url, content=b"second", headers={"Content-Type": "image/jpeg"})
        if url == "https://i.ebayimg.com/images/g/DDD/s-l1600.jpg":
            return FakeResponse(status_code=200, url=url, content=b"third", headers={"Content-Type": "image/jpeg"})
        raise AssertionError(f"Unexpected URL: {url}")

    media_root = tmp_path / "media"
    cap = EbayActiveStampImageJobCap(
        media_root=str(media_root),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Image",
            payload={
                "source_listing_id": "123456789012",
                "listing_url": "https://www.ebay.com/itm/123456789012",
                "image_url": "https://i.ebayimg.com/images/g/AAA/s-l225.jpg",
                "image_urls": [
                    "https://i.ebayimg.com/images/g/AAA/s-l225.jpg",
                    "https://i.ebayimg.com/images/g/CCC/s-l225.jpg",
                    "https://i.ebayimg.com/images/g/DDD/s-l225.jpg",
                ],
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["image_urls"] == ["https://i.ebayimg.com/images/g/AAA/s-l1600.jpg"]
    assert len(result.result_summary["image_local_paths"]) == 1
    assert result.result_summary["known_image_urls"] == [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/DDD/s-l1600.jpg",
    ]
    assert result.result_summary["queued_follow_up_image_jobs"] == 2
    assert result.result_summary["ebay_response_keys"] == []

    queued_jobs = sorted(
        [dict(row) for row in (pool._GetTableData(TABLE_JOBS) or [])],
        key=lambda row: str((row.get("payload") or {}).get("image_url") or ""),
    )
    assert len(queued_jobs) == 2
    assert [row["payload"]["image_urls"] for row in queued_jobs] == [
        ["https://i.ebayimg.com/images/g/CCC/s-l1600.jpg"],
        ["https://i.ebayimg.com/images/g/DDD/s-l1600.jpg"],
    ]

    first_updated_row = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:123456789012")[0]
    assert first_updated_row["image_urls"] == [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/DDD/s-l1600.jpg",
    ]
    assert len(first_updated_row["image_local_paths"]) == 3
    assert Path(first_updated_row["image_local_paths"][0]).exists()
    assert first_updated_row["image_local_paths"][1:] == ["", ""]

    for queued_job in queued_jobs:
        follow_up_result = cap.finish(
            _job(
                required_capability="eBay Active Stamps Image",
                payload=queued_job["payload"],
            )
        )
        assert follow_up_result.status == "completed"
        assert len(follow_up_result.result_summary["image_urls"]) == 1
        assert len(follow_up_result.result_summary["image_local_paths"]) == 1
        assert follow_up_result.result_summary["queued_follow_up_image_jobs"] == 0

    updated_row = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:123456789012")[0]
    assert updated_row["image_urls"] == [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/DDD/s-l1600.jpg",
    ]
    assert len(updated_row["image_local_paths"]) == 3
    assert all(Path(local_path).exists() for local_path in updated_row["image_local_paths"])
    first_relative_path = Path(updated_row["image_local_paths"][0]).relative_to(media_root)
    second_relative_path = Path(updated_row["image_local_paths"][1]).relative_to(media_root)
    third_relative_path = Path(updated_row["image_local_paths"][2]).relative_to(media_root)
    assert first_relative_path.name == "ebay-123456789012-01.jpg"
    assert second_relative_path.name == "ebay-123456789012-02.jpg"
    assert third_relative_path.parts[:-1] == ("12", "34", "56", "78", "90", "12")
    assert third_relative_path.name == "ebay-123456789012-03.jpg"


def test_ebay_active_stamp_listing_job_fetches_description_images_from_trading_api(tmp_path):
    """Listing job should fetch seller-description metadata and queue image download URLs."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    trading_calls: list[dict[str, Any]] = []
    trading_xml = """<?xml version="1.0" encoding="utf-8"?>
<GetItemResponse xmlns="urn:ebay:apis:eBLBaseComponents">
  <Ack>Success</Ack>
  <Item>
    <ItemID>123456789012</ItemID>
    <ListingDetails>
      <ViewItemURL>https://www.ebay.com/itm/123456789012</ViewItemURL>
    </ListingDetails>
    <PictureDetails>
      <PictureURL>https://i.ebayimg.com/images/g/AAA/s-l225.jpg</PictureURL>
      <PictureURL>https://i.ebayimg.com/images/g/CCC/s-l225.jpg</PictureURL>
    </PictureDetails>
    <Description><![CDATA[
      <div>
        <img src="https://i.ebayimg.com/images/g/EEE/s-l225.jpg" />
        <img data-src="//cdn.example.com/images/stamp-back.jpg" />
      </div>
    ]]></Description>
  </Item>
</GetItemResponse>
"""

    def fake_request_post(url, **kwargs):
        trading_calls.append({"url": url, **kwargs})
        assert url == "https://api.ebay.test/ws/api.dll"
        assert kwargs["headers"]["X-EBAY-API-CALL-NAME"] == "GetItem"
        assert kwargs["headers"]["X-EBAY-API-IAF-TOKEN"] == "user-token"
        assert "<ItemID>123456789012</ItemID>" in kwargs["data"]
        assert "<eBayAuthToken>" not in kwargs["data"]
        return FakeResponse(text=trading_xml, url=url, headers={"Content-Type": "text/xml"})

    detail_payload = {
        **DETAIL_PAYLOAD,
        "image": {"imageUrl": "https://i.ebayimg.com/images/g/AAA/s-l225.jpg"},
        "additionalImages": [{"imageUrl": "https://i.ebayimg.com/images/g/CCC/s-l225.jpg"}],
    }

    def fake_request_get(url, **kwargs):
        if url == "https://api.ebay.test/buy/browse/v1/item/get_item_by_legacy_id":
            params = dict(kwargs.get("params") or {})
            assert params["legacy_item_id"] == "123456789012"
            return FakeResponse(url=url, json_data=detail_payload)
        raise AssertionError(f"Unexpected URL: {url}")

    cap = EbayActiveStampListingJobCap(
        item_url="https://api.ebay.test/buy/browse/v1/item/get_item_by_legacy_id",
        trading_url="https://api.ebay.test/ws/api.dll",
        access_token="token",
        trading_oauth_user_token="user-token",
        request_get=fake_request_get,
        request_post=fake_request_post,
    ).bind_worker(worker)

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
                "image_url": "https://i.ebayimg.com/images/g/AAA/s-l225.jpg",
                "image_urls": ["https://i.ebayimg.com/images/g/AAA/s-l225.jpg"],
                "page_number": 1,
                "listing_position": 0,
                "keywords": "stamp",
                "category_id": "260",
                "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp",
                "item_end_date": "2026-04-20T12:00:00Z",
                "sale_type": "AUCTION",
                "listing_status": "active",
                "payload": {"item_summary": {"legacyItemId": "123456789012"}},
            },
        )
    )

    assert result.status == "completed"
    assert len(trading_calls) == 1
    assert result.result_summary["image_urls"] == [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/EEE/s-l1600.jpg",
        "https://cdn.example.com/images/stamp-back.jpg",
    ]
    assert result.result_summary["description_image_urls"] == [
        "https://i.ebayimg.com/images/g/EEE/s-l1600.jpg",
        "https://cdn.example.com/images/stamp-back.jpg",
    ]
    assert result.result_summary["ebay_response_keys"] == ["browse_item_detail", "browse_item_summary", "trading_get_item"]
    assert result.raw_payload["ebay_responses"]["trading_get_item"]["raw_xml"].startswith('<?xml version="1.0" encoding="utf-8"?>')

    updated_row = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:123456789012")[0]
    assert updated_row["image_urls"] == [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/EEE/s-l1600.jpg",
        "https://cdn.example.com/images/stamp-back.jpg",
    ]
    assert updated_row["payload"]["gallery_image_urls"] == [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
    ]
    assert "<img src=\"https://i.ebayimg.com/images/g/EEE/s-l225.jpg\" />" in updated_row["payload"]["item_detail"]["description"]
    assert updated_row["payload"]["description_html"] == updated_row["payload"]["item_detail"]["description"]
    assert updated_row["payload"]["description_html_present"] is True
    assert updated_row["payload"]["description_image_urls"] == [
        "https://i.ebayimg.com/images/g/EEE/s-l1600.jpg",
        "https://cdn.example.com/images/stamp-back.jpg",
    ]
    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "ebay active stamps image"
    assert queued_jobs[0]["payload"]["image_urls"] == [
        "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/CCC/s-l1600.jpg",
        "https://i.ebayimg.com/images/g/EEE/s-l1600.jpg",
        "https://cdn.example.com/images/stamp-back.jpg",
    ]
    assert queued_jobs[0]["payload"]["description_image_urls"] == [
        "https://i.ebayimg.com/images/g/EEE/s-l1600.jpg",
        "https://cdn.example.com/images/stamp-back.jpg",
    ]


def test_ebay_active_stamp_listing_job_prefers_listing_page_seller_account_name(tmp_path):
    """Listing job should replace opaque Browse seller ids with the listing-page account name."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    listing_page_html = """
    <script>
      window.__TEST__ = {
        "seller":{"__typename":"User","id":"p1QEhNdAQZW","userAccountName":"gsquared7"}
      };
    </script>
    """

    def fake_request_get(url, **kwargs):
        if url == "https://www.ebay.com/itm/123456789012":
            assert kwargs["headers"]["User-Agent"]
            return FakeResponse(url=url, text=listing_page_html, headers={"Content-Type": "text/html"})
        raise AssertionError(f"Unexpected URL: {url}")

    cap = EbayActiveStampListingJobCap(request_get=fake_request_get).bind_worker(worker)

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
                "seller_name": "p1QEhNdAQZW",
                "location_text": "Taipei, Taiwan",
                "image_url": "https://i.ebayimg.com/images/g/AAA/s-l225.jpg",
                "image_urls": ["https://i.ebayimg.com/images/g/AAA/s-l225.jpg"],
                "page_number": 1,
                "listing_position": 0,
                "keywords": "stamp",
                "category_id": "260",
                "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp",
                "item_end_date": "2026-04-20T12:00:00Z",
                "sale_type": "AUCTION",
                "listing_status": "active",
                "payload": {
                    "item_summary": {
                        "legacyItemId": "123456789012",
                        "seller": {"username": "p1QEhNdAQZW"},
                    }
                },
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["seller_name"] == "gsquared7"
    assert result.raw_payload["ebay_responses"]["listing_page_seller"]["seller_name"] == "gsquared7"

    updated_row = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:123456789012")[0]
    assert updated_row["seller_name"] == "gsquared7"
    assert updated_row["payload"]["page_seller_name"] == "gsquared7"


def test_ebay_active_stamp_listing_job_uses_shell_fallback_for_page_seller_name(tmp_path):
    """Listing import should fall back to curl-style page fetches before keeping an opaque seller id."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    shell_calls: list[list[str]] = []

    def fake_request_get(url, **kwargs):
        if url == "https://www.ebay.com/itm/123456789012":
            return FakeResponse(url=url, text="<html><body>No seller markers here.</body></html>", headers={"Content-Type": "text/html"})
        raise AssertionError(f"Unexpected URL: {url}")

    def fake_shell_run(cmd, **kwargs):
        shell_calls.append(list(cmd))
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout=(
                '<a href="https://www.ebay.com/sch/i.html?sid=gsquared7&_trksid='
                'p4429486.m2548.l2792">Visit store</a>'
            ),
            stderr="",
        )

    cap = EbayActiveStampListingJobCap(
        request_get=fake_request_get,
        shell_run=fake_shell_run,
    ).bind_worker(worker)

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
                "seller_name": "p1QEhNdAQZW",
                "location_text": "Taipei, Taiwan",
                "image_url": "https://i.ebayimg.com/images/g/AAA/s-l225.jpg",
                "image_urls": ["https://i.ebayimg.com/images/g/AAA/s-l225.jpg"],
                "page_number": 1,
                "listing_position": 0,
                "keywords": "stamp",
                "category_id": "260",
                "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp",
                "item_end_date": "2026-04-20T12:00:00Z",
                "sale_type": "AUCTION",
                "listing_status": "active",
                "payload": {
                    "item_summary": {
                        "legacyItemId": "123456789012",
                        "seller": {"username": "p1QEhNdAQZW"},
                    }
                },
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["seller_name"] == "gsquared7"
    updated_row = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:123456789012")[0]
    assert updated_row["seller_name"] == "gsquared7"
    assert updated_row["payload"]["page_seller_name"] == "gsquared7"
    assert updated_row["payload"]["seller_lookup_key"] == "p1QEhNdAQZW"
    assert shell_calls == [["curl", "-L", "--max-time", "120", "https://www.ebay.com/itm/123456789012"]]


def test_ebay_active_stamp_listing_job_persists_seller_lookup_key_when_page_lookup_fails(tmp_path):
    """Listing import should keep the seller lookup key even when the account name is still unresolved."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        if url == "https://www.ebay.com/itm/123456789012":
            return FakeResponse(url=url, text="<html><body>No seller markers here.</body></html>", headers={"Content-Type": "text/html"})
        raise AssertionError(f"Unexpected URL: {url}")

    def fake_shell_run(cmd, **kwargs):
        return subprocess.CompletedProcess(args=cmd, returncode=6, stdout="", stderr="dns failed")

    cap = EbayActiveStampListingJobCap(
        request_get=fake_request_get,
        shell_run=fake_shell_run,
    ).bind_worker(worker)

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
                "seller_name": "p1QEhNdAQZW",
                "location_text": "Taipei, Taiwan",
                "image_url": "https://i.ebayimg.com/images/g/AAA/s-l225.jpg",
                "image_urls": ["https://i.ebayimg.com/images/g/AAA/s-l225.jpg"],
                "page_number": 1,
                "listing_position": 0,
                "keywords": "stamp",
                "category_id": "260",
                "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?q=stamp",
                "item_end_date": "2026-04-20T12:00:00Z",
                "sale_type": "AUCTION",
                "listing_status": "active",
                "payload": {
                    "item_summary": {
                        "legacyItemId": "123456789012",
                        "seller": {"username": "p1QEhNdAQZW"},
                    }
                },
            },
        )
    )

    assert result.status == "completed"
    updated_row = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:123456789012")[0]
    assert updated_row["seller_name"] == "p1QEhNdAQZW"
    assert updated_row["payload"]["seller_lookup_key"] == "p1QEhNdAQZW"
    assert updated_row["payload"].get("page_seller_name", "") == ""


def test_ebay_active_stamp_image_job_uses_cached_seller_account_name_without_fetching_listing_page(tmp_path):
    """Image job should stay download-only and skip listing-page seller lookups."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS, TABLE_EBAY_ACTIVE_SELLER_ACCOUNTS],
        extra_schemas={
            TABLE_SALES_LISTINGS: sales_listings_table_schema(),
            TABLE_EBAY_ACTIVE_SELLER_ACCOUNTS: ebay_active_seller_accounts_table_schema(),
        },
    )
    pool._Insert(
        TABLE_EBAY_ACTIVE_SELLER_ACCOUNTS,
        {
            "id": "ebay:seller-account:p1QEhNdAQZW",
            "provider": "ebay",
            "seller_key": "p1QEhNdAQZW",
            "account_name": "gsquared7",
            "source_listing_id": "366333117430",
            "listing_url": "https://www.ebay.com/itm/366333117430",
            "payload": {"lookup_source": "listing_page"},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )
    pool._Insert(
        TABLE_SALES_LISTINGS,
        {
            "id": "ebay:366333117430",
            "listing_uid": "ebay:366333117430",
            "provider": "ebay",
            "source_listing_id": "366333117430",
            "marketplace_site": "www.ebay.com",
            "source_category_id": "260",
            "source_query": "",
            "listing_status": "active",
            "sale_type": "AUCTION",
            "title": "U.S. Mint Postage Lot - $238 face",
            "subtitle": "",
            "listing_url": "https://www.ebay.com/itm/366333117430",
            "search_page": 9,
            "listing_position": 45,
            "sold_at": "",
            "price_amount": 86.0,
            "price_currency": "USD",
            "shipping_amount": 7.0,
            "shipping_currency": "USD",
            "total_amount": 93.0,
            "condition_text": "",
            "seller_name": "p1QEhNdAQZW",
            "location_text": "US",
            "image_url": "https://i.ebayimg.com/images/g/kqwAAeSwpRJp1VDT/s-l225.jpg",
            "image_urls": ["https://i.ebayimg.com/images/g/kqwAAeSwpRJp1VDT/s-l225.jpg"],
            "image_local_paths": [],
            "source_url": "https://api.ebay.test/buy/browse/v1/item_summary/search?offset=480",
            "payload": {
                "item_summary": {
                    "seller": {"username": "p1QEhNdAQZW", "feedbackScore": 109144},
                    "itemEndDate": "2026-04-12T18:46:11.000Z",
                }
            },
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        if url == "https://i.ebayimg.com/images/g/kqwAAeSwpRJp1VDT/s-l1600.jpg":
            return FakeResponse(status_code=200, url=url, content=b"first", headers={"Content-Type": "image/jpeg"})
        if url == "https://www.ebay.com/itm/366333117430":
            raise AssertionError("listing page should not be fetched when seller cache exists")
        raise AssertionError(f"Unexpected URL: {url}")

    media_root = tmp_path / "media"
    cap = EbayActiveStampImageJobCap(
        item_url="https://api.ebay.test/buy/browse/v1/item/get_item_by_legacy_id",
        media_root=str(media_root),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Image",
            payload={
                "source_listing_id": "366333117430",
                "listing_url": "https://www.ebay.com/itm/366333117430",
                "image_url": "https://i.ebayimg.com/images/g/kqwAAeSwpRJp1VDT/s-l225.jpg",
                "image_urls": ["https://i.ebayimg.com/images/g/kqwAAeSwpRJp1VDT/s-l225.jpg"],
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["seller_name"] == "p1QEhNdAQZW"
    updated_row = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:366333117430")[0]
    assert updated_row["seller_name"] == "p1QEhNdAQZW"


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
            "payload": {"item_end_date": "2026-04-21T15:30:00Z"},
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
    assert result.result_summary["ebay_response_keys"] == ["browse_item_details"]
    assert result.raw_payload["ebay_responses"]["browse_item_details"][0]["response"]["legacyItemId"] == "123456789012"

    ended_row = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:123456789012")[0]
    future_row = pool._GetTableData(TABLE_SALES_LISTINGS, "ebay:210987654321")[0]
    assert ended_row["listing_status"] == "ended"
    assert ended_row["payload"]["status_refresh_reason"] == "detail_refresh"
    assert future_row["listing_status"] == "active"
    assert any(
        update.get("extra", {}).get("source_listing_id") == "123456789012"
        and "refreshing item 123456789012 (1/1)" in str(update.get("message") or "")
        for update in worker.progress_updates
    )
    assert any("refreshed 1 items; 1 ended, 0 still active, 0 not found" in message for message in worker.log_messages)


def test_ebay_active_stamp_status_job_finalizes_report_and_sends_email(tmp_path):
    """The last terminal report job should finalize the report and send one email."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    report_date = "2026-04-11T02:10:00+08:00"

    ensure_dispatcher_tables(
        pool,
        [TABLE_SALES_LISTINGS, TABLE_EBAY_ACTIVE_DAILY_REPORTS],
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
            "sale_type": "AUCTION",
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

    sent_messages = []

    class FakeSESClient:
        def send_email(self, **kwargs):
            sent_messages.append(kwargs)
            return {"MessageId": "ses-message-123"}

    def fake_request_get(url, **kwargs):
        params = dict(kwargs.get("params") or {})
        assert url == "https://api.ebay.test/buy/browse/v1/item/get_item_by_legacy_id"
        assert params["legacy_item_id"] == "123456789012"
        return FakeResponse(url=url, json_data=ENDED_DETAIL_PAYLOAD)

    cap = EbayActiveStampStatusJobCap(
        item_url="https://api.ebay.test/buy/browse/v1/item/get_item_by_legacy_id",
        access_token="token",
        request_get=fake_request_get,
        daily_report_email_to="alvincho@jumbosoft.com",
        daily_report_email_from="noreply@example.com",
        daily_report_email_reply_to="replies@example.com",
        daily_report_ses_region="us-west-2",
        daily_report_ses_configuration_set="collectibles-daily",
        daily_report_ses_source_arn="arn:aws:ses:us-west-2:123456789012:identity/example.com",
        daily_report_ses_client=FakeSESClient(),
    ).bind_worker(worker)
    cap._upsert_daily_report(report_date, status="processing page", planned_status_jobs=1)

    result = cap.finish(
        _job(
            required_capability="eBay Active Stamps Status",
            payload={
                "source_listing_ids": ["123456789012"],
                "batch_size": 10,
                "auction_only": True,
                "report_date": report_date,
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["daily_report_status"] == "finished"
    assert result.result_summary["daily_report_email_status"] == "sent"
    assert len(sent_messages) == 1
    assert sent_messages[0]["FromEmailAddress"] == "noreply@example.com"
    assert sent_messages[0]["Destination"]["ToAddresses"] == ["alvincho@jumbosoft.com"]
    assert sent_messages[0]["ReplyToAddresses"] == ["replies@example.com"]
    assert sent_messages[0]["ConfigurationSetName"] == "collectibles-daily"
    assert sent_messages[0]["FromEmailAddressIdentityArn"] == "arn:aws:ses:us-west-2:123456789012:identity/example.com"
    assert report_date in sent_messages[0]["Content"]["Simple"]["Subject"]["Data"]
    assert "Updated items: 1" in sent_messages[0]["Content"]["Simple"]["Body"]["Text"]["Data"]

    report_row = pool._GetTableData(TABLE_EBAY_ACTIVE_DAILY_REPORTS, _report_row_id(report_date))[0]
    assert report_row["status"] == "finished"
    assert report_row["updated_items"] == 1
    assert report_row["payload"]["email_notification"]["status"] == "sent"
    assert report_row["payload"]["email_notification"]["message_id"] == "ses-message-123"


def test_ebay_daily_report_email_uses_retis_ses_env_fallbacks(monkeypatch):
    """Daily report email should reuse the shared SES env names from retis-web."""
    monkeypatch.setenv("CONTACT_NOTIFICATION_EMAIL", "ops@example.com")
    monkeypatch.setenv("SES_FROM_EMAIL", "noreply@example.com")
    monkeypatch.setenv("SES_REGION", "us-east-1")
    monkeypatch.setenv("SES_CONFIGURATION_SET_NAME", "retis-shared")
    monkeypatch.setenv("SES_FROM_EMAIL_IDENTITY_ARN", "arn:aws:ses:us-east-1:123456789012:identity/retis.ai")
    monkeypatch.delenv("EBAY_DAILY_REPORT_EMAIL_TO", raising=False)
    monkeypatch.delenv("EBAY_DAILY_REPORT_EMAIL_FROM", raising=False)
    monkeypatch.delenv("EBAY_DAILY_REPORT_SES_REGION", raising=False)
    monkeypatch.delenv("EBAY_DAILY_REPORT_SES_CONFIGURATION_SET", raising=False)
    monkeypatch.delenv("EBAY_DAILY_REPORT_SES_SOURCE_ARN", raising=False)

    sent_messages = []

    class FakeSESClient:
        def send_email(self, **kwargs):
            sent_messages.append(kwargs)
            return {"MessageId": "ses-message-456"}

    cap = EbayActiveStampJobCap(daily_report_ses_client=FakeSESClient())
    notification = cap._send_daily_report_email(
        {
            "report_date": "2026-04-11",
            "status": "completed",
            "planned_status_jobs": 1,
            "planned_page_jobs": 1,
            "planned_retrieval_items": 60,
            "updated_items": 2,
            "retrieved_items": 3,
            "cancelled_jobs": 0,
            "stopping_jobs": 0,
            "payload": {"job_counts": {"total_jobs": 2, "completed_jobs": 2, "failed_jobs": 0, "active_jobs": 0}},
        }
    )

    assert cap.daily_report_email_to == "ops@example.com"
    assert cap.daily_report_email_from == "noreply@example.com"
    assert cap.daily_report_ses_region == "us-east-1"
    assert notification["status"] == "sent"
    assert notification["message_id"] == "ses-message-456"
    assert sent_messages[0]["FromEmailAddress"] == "noreply@example.com"
    assert sent_messages[0]["Destination"]["ToAddresses"] == ["ops@example.com"]
    assert sent_messages[0]["ConfigurationSetName"] == "retis-shared"
    assert sent_messages[0]["FromEmailAddressIdentityArn"] == "arn:aws:ses:us-east-1:123456789012:identity/retis.ai"
