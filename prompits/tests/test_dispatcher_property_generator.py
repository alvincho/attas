"""
Regression tests for collectibles property-generator job caps.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from private.collectibles.jobcaps.ebay_sold_stamps import TABLE_SALES_LISTINGS, sales_listings_table_schema
from private.collectibles.jobcaps.property_generator import (
    ISSUER_PROPERTY_GENERATOR_CAPABILITY,
    PROPERTY_GENERATOR_CAPABILITY,
    CollectiblesIssuerPropertyGeneratorJobCap,
    CollectiblesPropertyGeneratorJobCap,
)
from private.collectibles.property_lists import TABLE_PROPERTY_LISTS, property_lists_table_schema
from prompits.dispatcher.models import JobDetail
from prompits.dispatcher.schema import TABLE_JOBS, ensure_dispatcher_tables
from prompits.pools.sqlite import SQLitePool


FIXTURE_PATH = (
    Path(__file__).resolve().parents[2]
    / "private"
    / "collectibles"
    / "examples"
    / "ebay_issuer_test_items.json"
)


class FakeResponse:
    """Simple fake response used for property-generator tests."""

    def __init__(self, *, status_code: int = 200, text: str = "", json_data: Mapping[str, Any] | None = None):
        self.status_code = status_code
        self.text = text
        self._json_data = dict(json_data or {})

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
        self.logger = self
        self.log_messages: list[str] = []

    def info(self, message: str, *args: Any):
        """Capture log messages for assertions."""
        rendered = message % args if args else message
        self.log_messages.append(rendered)


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


def _seed_tables(pool: SQLitePool) -> None:
    """Ensure the tables required by the property-generator tests exist."""
    ensure_dispatcher_tables(
        pool,
        [TABLE_JOBS, TABLE_SALES_LISTINGS, TABLE_PROPERTY_LISTS],
        extra_schemas={
            TABLE_SALES_LISTINGS: sales_listings_table_schema(),
            TABLE_PROPERTY_LISTS: property_lists_table_schema(),
        },
    )


def _fixture_sales_rows() -> list[dict[str, Any]]:
    """Return the generated synthetic sales rows."""
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [dict(item["sales_row"]) for item in payload["items"] if isinstance(item, Mapping)]


def test_property_generator_queues_issuer_jobs_for_100_ebay_rows(tmp_path):
    """The batch property generator should queue one issuer job per selected sales row."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    _seed_tables(pool)
    assert pool._InsertMany(TABLE_SALES_LISTINGS, _fixture_sales_rows())

    worker = FakeWorker(pool)
    cap = CollectiblesPropertyGeneratorJobCap().bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability=PROPERTY_GENERATOR_CAPABILITY,
            payload={
                "record_mode": "sales",
                "property_key": "issuer",
                "provider": "ebay",
                "limit": 100,
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["selected_records"] == 100
    assert result.result_summary["queued_jobs_this_run"] == 100
    queued_rows = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_rows) == 100
    assert {str(row["required_capability"]).lower() for row in queued_rows} == {
        ISSUER_PROPERTY_GENERATOR_CAPABILITY.lower()
    }

    second_result = cap.finish(
        _job(
            required_capability=PROPERTY_GENERATOR_CAPABILITY,
            payload={
                "record_mode": "sales",
                "property_key": "issuer",
                "provider": "ebay",
                "limit": 100,
            },
        )
    )
    assert second_result.result_summary["queued_jobs_this_run"] == 0
    assert second_result.result_summary["skipped_existing_jobs"] == 100


def test_issuer_property_generator_persists_tbc_from_ollama_response(tmp_path):
    """Issuer item generation should persist a TBC issuer suggestion from Ollama JSON."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    _seed_tables(pool)
    sales_row = {
        "id": "ebay:test:model",
        "listing_uid": "ebay:test:model",
        "provider": "ebay",
        "source_listing_id": "100000000001",
        "auctioneer_id": "",
        "auction_id": "",
        "lot_number": "",
        "marketplace_site": "EBAY_US",
        "source_category_id": "260",
        "source_query": "stamp lot",
        "listing_status": "active",
        "sale_type": "AUCTION",
        "title": "Bluebird anniversary stamp lot",
        "subtitle": "Collector album page",
        "listing_url": "https://www.ebay.com/itm/100000000001",
        "search_page": 1,
        "listing_position": 0,
        "sold_at": "",
        "price_amount": 12.5,
        "price_currency": "USD",
        "estimate_amount": None,
        "estimate_currency": "",
        "hammer_price_amount": None,
        "hammer_price_currency": "",
        "shipping_amount": 2.5,
        "shipping_currency": "USD",
        "total_amount": 15.0,
        "condition_text": "Used",
        "seller_name": "paper-house",
        "location_text": "Taipei, Taiwan",
        "image_url": "https://i.ebayimg.com/images/g/AAA/s-l1600.jpg",
        "image_urls": ["https://i.ebayimg.com/images/g/AAA/s-l1600.jpg"],
        "image_local_paths": [],
        "source_url": "https://www.ebay.com/sch/i.html?_nkw=stamp&_sacat=260&_pgn=1",
        "payload": {
            "auction_title": "Sakura Weekend Auction",
            "item_summary": {
                "categories": [
                    {"categoryId": "260", "categoryName": "Stamps"},
                    {"categoryId": "999", "categoryName": "Asia"},
                ]
            },
        },
        "created_at": "2026-04-16T10:00:00+00:00",
        "updated_at": "2026-04-16T12:00:00+00:00",
    }
    assert pool._Insert(TABLE_SALES_LISTINGS, sales_row)

    def fake_request_post(url, **kwargs):
        assert "11434" in url
        body = kwargs.get("json") or {}
        assert body["model"] == "gemma4:26b"
        return FakeResponse(
            json_data={
                "response": json.dumps(
                    {
                        "issuer": "Japan",
                        "confidence": 0.83,
                        "needs_confirmation": True,
                        "reason": "Sakura hints point to Japan.",
                    }
                )
            }
        )

    worker = FakeWorker(pool)
    cap = CollectiblesIssuerPropertyGeneratorJobCap(request_post=fake_request_post).bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability=ISSUER_PROPERTY_GENERATOR_CAPABILITY,
            payload={"record_mode": "sales", "record_uid": "ebay:test:model"},
        )
    )

    assert result.status == "completed"
    assert result.result_summary["updated"] is True
    assert result.result_summary["issuer"] == "Japan"
    assert result.result_summary["issuer_status"] == "tbc"
    assert result.result_summary["used_model"] is True

    persisted_rows = pool._GetTableData(
        TABLE_PROPERTY_LISTS,
        {"record_mode": "sales", "record_uid": "ebay:test:model"},
        table_schema=property_lists_table_schema(),
    )
    assert len(persisted_rows) == 1
    persisted = persisted_rows[0]
    assert persisted["issuer"] == "Japan"
    assert persisted["issuer_status"] == "tbc"
    assert persisted["issuer_source"] == "ollama:gemma4:26b"
    assert round(float(persisted["issuer_confidence"]), 2) == 0.83


def test_issuer_property_generator_falls_back_to_heuristics(tmp_path):
    """Issuer generation should still persist TBC when Ollama is unavailable but title/category hints are strong."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    _seed_tables(pool)
    sales_row = {
        "id": "ebay:test:heuristic",
        "listing_uid": "ebay:test:heuristic",
        "provider": "ebay",
        "source_listing_id": "100000000002",
        "auctioneer_id": "",
        "auction_id": "",
        "lot_number": "",
        "marketplace_site": "EBAY_US",
        "source_category_id": "260",
        "source_query": "stamp lot",
        "listing_status": "active",
        "sale_type": "FIXED_PRICE",
        "title": "Taiwan scenic definitive stamp lot",
        "subtitle": "Album page and singles",
        "listing_url": "https://www.ebay.com/itm/100000000002",
        "search_page": 1,
        "listing_position": 0,
        "sold_at": "",
        "price_amount": 18.0,
        "price_currency": "USD",
        "estimate_amount": None,
        "estimate_currency": "",
        "hammer_price_amount": None,
        "hammer_price_currency": "",
        "shipping_amount": 2.0,
        "shipping_currency": "USD",
        "total_amount": 20.0,
        "condition_text": "Used",
        "seller_name": "paper-house",
        "location_text": "Taipei, Taiwan",
        "image_url": "https://i.ebayimg.com/images/g/BBB/s-l1600.jpg",
        "image_urls": ["https://i.ebayimg.com/images/g/BBB/s-l1600.jpg"],
        "image_local_paths": [],
        "source_url": "https://www.ebay.com/sch/i.html?_nkw=stamp&_sacat=260&_pgn=1",
        "payload": {
            "auction_title": "Global Collector Weekend",
            "item_summary": {
                "categories": [
                    {"categoryId": "260", "categoryName": "Stamps"},
                    {"categoryId": "262", "categoryName": "Taiwan"},
                ]
            },
        },
        "created_at": "2026-04-16T10:00:00+00:00",
        "updated_at": "2026-04-16T12:00:00+00:00",
    }
    assert pool._Insert(TABLE_SALES_LISTINGS, sales_row)

    def fake_request_post(url, **kwargs):
        raise RuntimeError("ollama unavailable")

    worker = FakeWorker(pool)
    cap = CollectiblesIssuerPropertyGeneratorJobCap(request_post=fake_request_post).bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability=ISSUER_PROPERTY_GENERATOR_CAPABILITY,
            payload={"record_mode": "sales", "record_uid": "ebay:test:heuristic"},
        )
    )

    assert result.status == "completed"
    assert result.result_summary["updated"] is True
    assert result.result_summary["issuer"] == "Taiwan"
    assert result.result_summary["used_model"] is False
    assert result.result_summary["source"] == "heuristic"

    persisted_rows = pool._GetTableData(
        TABLE_PROPERTY_LISTS,
        {"record_mode": "sales", "record_uid": "ebay:test:heuristic"},
        table_schema=property_lists_table_schema(),
    )
    assert len(persisted_rows) == 1
    persisted = persisted_rows[0]
    assert persisted["issuer"] == "Taiwan"
    assert persisted["issuer_status"] == "tbc"
    assert persisted["issuer_source"] == "heuristic"
