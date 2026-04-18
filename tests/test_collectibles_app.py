from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from urllib.parse import quote_plus

from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from private.collectibles.app import (
    CollectiblesRepository,
    SALES_LISTING_REFRESH_PRIORITY,
    _serialize_sales_listing,
    _build_sales_listing_refresh_job,
    create_app,
    media_url_for_path,
    resolve_media_path,
)
import private.collectibles.app as collectibles_app


class FakeCollectiblesRepository:
    def __init__(self, image_path: Path, alt_image_path: Path):
        self.image_path = image_path
        self.alt_image_path = alt_image_path
        self.catalog_calls: list[dict[str, object]] = []
        self.sales_calls: list[dict[str, object]] = []
        self.refresh_calls: list[dict[str, object]] = []
        self.property_save_calls: list[dict[str, object]] = []
        self.report_calls: list[dict[str, object]] = []
        self.report_response_calls: list[dict[str, object]] = []
        self.report_bulk_response_calls: list[dict[str, object]] = []
        self.worker_log_calls: list[dict[str, object]] = []
        self.start_worker_calls: list[str] = []
        self.terminate_worker_calls: list[str] = []
        self.bulk_worker_calls: list[dict[str, str]] = []
        self.restore_worker_calls = 0
        self.save_current_worker_calls = 0

    def get_summary(self) -> dict[str, object]:
        return {
            "catalog": {
                "catalog_items": 10,
                "catalog_items_with_local_images": 3,
                "earliest_issue_year": 1990,
                "latest_issue_year": 2026,
            },
            "sales": {
                "sales_listings": 8,
                "sales_listings_with_local_images": 4,
            },
            "colnect_items": 12,
            "ebay_listings": 8,
            "san_listings": 5,
            "top_catalogs": [{"catalog_code": "UPU-WNS", "catalog_name": "UPU WNS", "item_count": 10}],
            "top_issuers": [{"issuer_name": "Japan", "item_count": 5}],
            "sales_facets": [{"provider": "ebay", "listing_status": "active", "listing_count": 8}],
            "sales_sale_types": [{"sale_type_key": "fixed_price", "sale_type_label": "Fixed price", "listing_count": 6}],
            "sales_subcategories": [{"subcategory_name": "United States", "listing_count": 4}],
        }

    def get_dashboard(self, *, history_limit: int = 72, live: bool = False) -> dict[str, object]:
        return {
            "snapshot_interval_minutes": 1,
            "current": {
                "captured_at": "2026-04-14T01:00:00+00:00",
                "sources": [
                    {
                        "key": "colnect",
                        "label": "Colnect",
                        "imported_records": 12,
                        "downloaded_images": 9,
                        "page_jobs": {"queued": 1, "working": 0, "pending": 1},
                        "listing_jobs": {"queued": 3, "working": 1, "pending": 4},
                        "image_jobs": {"queued": 2, "working": 0, "pending": 2},
                    },
                    {
                        "key": "ebay",
                        "label": "eBay",
                        "imported_records": 8,
                        "downloaded_images": 15,
                        "page_jobs": {"queued": 2, "working": 1, "pending": 3},
                        "listing_jobs": {"queued": 5, "working": 2, "pending": 7},
                        "image_jobs": {"queued": 1, "working": 1, "pending": 2},
                    },
                    {
                        "key": "san",
                        "label": "SAN",
                        "imported_records": 5,
                        "downloaded_images": 7,
                        "page_jobs": {"queued": 3, "working": 0, "pending": 3},
                        "listing_jobs": {"queued": 0, "working": 0, "pending": 0},
                        "image_jobs": {"queued": 4, "working": 1, "pending": 5},
                    },
                ],
                "workers": {
                    "current_count": 6,
                    "working_count": 4,
                    "idle_count": 2,
                    "active_job_count": 4,
                },
            },
            "ebay_daily_schedule": {
                "schedule_id": "dispatcher-boss-schedule:ebay-daily-20260412-0200-10m",
                "name": "eBay Daily Schedule (10m)",
                "status": "scheduled",
                "required_capability": "eBay Daily Schedule",
                "scheduled_for": "2026-04-14T09:10:00+08:00",
                "issued_at": "2026-04-14T09:00:02+08:00",
                "updated_at": "2026-04-14T09:00:02+08:00",
                "schedule_interval_minutes": 10,
                "dispatcher_job_id": "dispatcher-job:ebay-daily-1",
                "job_status": "claimed",
                "job_claimed_by": "dispatcher-worker:ebay-worker-1",
                "job_claimed_at": "2026-04-14T09:00:05+08:00",
                "job_completed_at": "",
                "job_updated_at": "2026-04-14T09:00:05+08:00",
                "job_error": "",
                "job_worker_name": "CollectiblesWorker eBay only",
            },
            "daily_archive_schedule": {
                "schedule_id": "dispatcher-boss-schedule:collectibles-daily-job-archive",
                "name": "Daily Job Archive (3AM)",
                "status": "scheduled",
                "required_capability": "Daily Job Archive",
                "scheduled_for": "2026-04-15T03:00:00+08:00",
                "issued_at": "2026-04-14T03:00:00+08:00",
                "updated_at": "2026-04-14T03:00:00+08:00",
                "schedule_interval_minutes": 0,
                "dispatcher_job_id": "dispatcher-job:archive-1",
                "job_status": "completed",
                "job_claimed_by": "dispatcher-worker:archive-worker-1",
                "job_claimed_at": "2026-04-14T03:00:05+08:00",
                "job_completed_at": "2026-04-14T03:02:00+08:00",
                "job_updated_at": "2026-04-14T03:02:00+08:00",
                "job_error": "",
                "job_worker_name": "CollectiblesWorker Dashboard",
            },
            "rate_limit_locks": [
                {
                    "source_key": "colnect",
                    "label": "Colnect",
                    "active": True,
                    "started_at": "2026-04-14T08:58:00+08:00",
                    "hold_until": "2026-04-14T09:18:00+08:00",
                    "updated_at": "2026-04-14T08:58:00+08:00",
                    "reason": "HTTP 429",
                },
                {
                    "source_key": "ebay",
                    "label": "eBay",
                    "active": False,
                    "started_at": "",
                    "hold_until": "",
                    "updated_at": "2026-04-14T08:40:00+08:00",
                    "reason": "",
                },
            ],
            "ebay_daily_reports": [
                {
                    "report_date": "2026-04-14T09:00:00+08:00",
                    "status": "finished",
                    "fan_out_pages": 1,
                    "queued_listing_jobs": 55,
                    "planned_status_jobs": 1,
                    "planned_page_jobs": 1,
                    "planned_retrieval_items": 60,
                    "updated_items": 18,
                    "retrieved_items": 55,
                    "error_count": 0,
                    "total_jobs": 2,
                    "completed_jobs": 2,
                    "failed_jobs": 0,
                    "active_jobs": 0,
                    "updated_at": "2026-04-14T09:05:00+08:00",
                }
            ],
            "unresolved_alerts": {
                "total_count": 2,
                "new_count": 1,
                "acknowledged_count": 1,
                "sources": [{"source_key": "ebay", "source_label": "eBay", "count": 2}],
                "latest": [
                    {
                        "id": "alert:ebay:rate-limit",
                        "kind": "alert",
                        "source_key": "ebay",
                        "source_label": "eBay",
                        "title": "eBay rate limit lock active",
                        "severity": "warning",
                        "response_status": "new",
                        "created_at": "2026-04-14T09:02:00+08:00",
                        "updated_at": "2026-04-14T09:02:00+08:00",
                    }
                ],
            },
            "latest_snapshot": {
                "captured_at": "2026-04-14T00:55:00+00:00",
                "sources": [
                    {
                        "key": "colnect",
                        "label": "Colnect",
                        "imported_records": 10,
                        "downloaded_images": 8,
                        "page_jobs": {"queued": 1, "working": 0, "pending": 1},
                        "listing_jobs": {"queued": 4, "working": 1, "pending": 5},
                        "image_jobs": {"queued": 2, "working": 0, "pending": 2},
                    }
                ],
                "workers": {
                    "current_count": 5,
                    "working_count": 3,
                    "idle_count": 2,
                    "active_job_count": 3,
                },
            },
            "history": [
                {
                    "captured_at": "2026-04-14T00:55:00+00:00",
                    "sources": [
                        {
                            "key": "colnect",
                            "label": "Colnect",
                            "imported_records": 10,
                            "downloaded_images": 8,
                            "page_jobs": {"queued": 1, "working": 0, "pending": 1},
                            "listing_jobs": {"queued": 4, "working": 1, "pending": 5},
                            "image_jobs": {"queued": 2, "working": 0, "pending": 2},
                        }
                    ],
                    "workers": {
                        "current_count": 5,
                        "working_count": 3,
                        "idle_count": 2,
                        "active_job_count": 3,
                    },
                }
            ],
            "workers": {
                "current_count": 6,
                "working_count": 4,
                "idle_count": 2,
                "active_job_count": 4,
                "items": [
                    {
                        "worker_id": "worker-1",
                        "name": "CollectiblesWorker eBay items",
                        "status": "working",
                        "source_key": "ebay",
                        "source_label": "eBay",
                        "last_seen_at": "2026-04-14T01:00:00+00:00",
                        "captured_at": "2026-04-14T01:00:00+00:00",
                        "active_job_id": "dispatcher-job:ebay-active-stamps-listing:123",
                        "active_job_status": "working",
                        "job_capability": "eBay Active Stamps Listing",
                        "job_status": "claimed",
                        "capabilities": ["eBay Active Stamps Listing"],
                    }
                ],
            },
        }

    def list_catalog_items(self, **kwargs) -> dict[str, object]:
        self.catalog_calls.append(kwargs)
        item = self.get_catalog_set("set:group-1") if kwargs.get("view") == "set" else self.get_catalog_item("item-1")
        return {
            "items": [item],
            "page": kwargs["page"],
            "page_size": kwargs["page_size"],
            "total": 1,
            "page_count": 1,
            "filters": kwargs,
        }

    def get_catalog_item(self, item_uid: str) -> dict[str, object] | None:
        if item_uid != "item-1":
            return None
        return {
            "item_id": 1,
            "item_uid": "item-1",
            "category": "stamp",
            "title": "Blue Bird",
            "subtitle": "",
            "series_name": "Migration Set",
            "issue_date": "2024-01-01",
            "issue_year": 2024,
            "description": "A commemorative issue.",
            "tags": ["bird", "blue"],
            "updated_at": "2026-04-10T12:00:00+00:00",
            "issuer_name": "Japan",
            "extra_attributes": {
                "image_local_path": str(self.image_path),
                "image_url": "https://example.com/bird.jpg",
                "source_url": "https://example.com/catalog/item-1",
            },
            "catalog_entries": [
                {
                    "catalog_code": "UPU-WNS",
                    "catalog_name": "UPU WNS",
                    "catalog_number": "JP001.2024",
                    "variant_label": "",
                    "market_value": None,
                    "market_value_currency": "",
                    "notes": "Imported from test fixture.",
                }
            ],
        }

    def get_catalog_set(self, set_uid: str) -> dict[str, object] | None:
        if set_uid != "set:group-1":
            return None
        return {
            "item_id": None,
            "item_uid": "set:group-1",
            "entry_type": "set",
            "category": "set",
            "title": "Migration",
            "subtitle": "",
            "series_name": "Birds",
            "issue_date": "2024-01-01",
            "issue_year": 2024,
            "description": "",
            "tags": [],
            "updated_at": "2026-04-10T12:00:00+00:00",
            "issuer_name": "Japan",
            "item_count": 3,
            "representative_item_uid": "item-1",
            "group_topic": "Birds",
            "extra_attributes": {
                "image_local_path": str(self.image_path),
                "image_url": "https://example.com/bird.jpg",
                "theme": "Birds",
            },
            "gallery_members": [
                {
                    "item_uid": "item-1",
                    "extra_attributes": {
                        "image_local_path": str(self.image_path),
                        "image_url": "https://example.com/bird.jpg",
                    },
                },
                {
                    "item_uid": "item-2",
                    "extra_attributes": {
                        "image_local_path": str(self.alt_image_path),
                        "image_url": "https://example.com/heron.jpg",
                    },
                },
                {
                    "item_uid": "item-3",
                    "extra_attributes": {
                        "image_url": "https://example.com/falcon.jpg",
                    },
                },
            ],
            "catalog_entries": [
                {
                    "catalog_code": "UPU-WNS",
                    "catalog_name": "UPU WNS",
                    "catalog_number": "JP001.2024",
                    "variant_label": "",
                    "market_value": None,
                    "market_value_currency": "",
                    "notes": "",
                }
            ],
        }

    def list_sales_listings(self, **kwargs) -> dict[str, object]:
        self.sales_calls.append(kwargs)
        return {
            "items": [self.get_sales_listing("sale-1")],
            "page": kwargs["page"],
            "page_size": kwargs["page_size"],
            "total": 1,
            "page_count": 1,
            "filters": kwargs,
        }

    def get_sales_listing(self, listing_uid: str) -> dict[str, object] | None:
        if listing_uid != "sale-1":
            return None
        return {
            "listing_uid": "sale-1",
            "provider": "ebay",
            "auctioneer_id": "",
            "auction_id": "auction-1",
            "auctioneer_name": "Bluebird House",
            "auction_title": "Bluebird Spring Sale",
            "source_listing_id": "123",
            "marketplace_site": "EBAY_US",
            "source_category_id": "260",
            "source_query": "blue bird stamp",
            "listing_status": "active",
            "sale_type": "FIXED_PRICE",
            "title": "Blue Bird Stamp Block",
            "subtitle": "",
            "listing_url": "https://example.com/sale-1",
            "search_page": 1,
            "listing_position": 4,
            "sold_at": "",
            "price_amount": "10",
            "price_currency": "USD",
            "shipping_amount": "",
            "shipping_currency": "",
            "total_amount": "10",
            "condition_text": "MNH",
            "seller_name": "seller-1",
            "location_text": "Tokyo",
            "image_url": "https://example.com/sale-1.jpg",
            "image_urls": ["https://example.com/sale-1.jpg"],
            "image_local_paths": [str(self.image_path)],
            "source_url": "https://example.com/source/sale-1",
            "payload": {
                "item_id": "v1|123|0",
                "api_mode": "browse",
                "grade": "VF",
                "item_summary": {
                    "seller": {"feedbackScore": 6837},
                    "categories": [
                        {"categoryId": "260", "categoryName": "Stamps"},
                        {"categoryId": "261", "categoryName": "United States"},
                    ],
                    "itemOriginDate": "2026-04-09T11:12:13.000Z",
                    "itemEndDate": "2026-04-12T17:45:00.000Z",
                    "shippingOptions": [
                        {
                            "shippingCost": {"value": "4.5", "currency": "USD"},
                            "shippingCostType": "FIXED",
                            "minEstimatedDeliveryDate": "2026-04-12T07:00:00.000Z",
                            "maxEstimatedDeliveryDate": "2026-04-14T07:00:00.000Z",
                        }
                    ],
                },
                "item_detail": {
                    "description": "<p>Fresh gum and sharp centering.</p>",
                },
            },
            "created_at": "2026-04-10T11:00:00+00:00",
            "updated_at": "2026-04-10T12:00:00+00:00",
        }

    def queue_sales_listing_refresh(self, listing_uid: str, *, priority: int = SALES_LISTING_REFRESH_PRIORITY) -> dict[str, object]:
        self.refresh_calls.append({
            "listing_uid": listing_uid,
            "priority": priority,
        })
        if listing_uid != "sale-1":
            raise LookupError(f"Sales listing '{listing_uid}' was not found.")
        return {
            "queued": True,
            "job_id": "dispatcher-job:ebay-active-stamps-listing:123",
            "existing_status": "",
            "listing_uid": listing_uid,
            "priority": priority,
            "capability": "ebay active stamps listing",
        }

    def save_property_list_values(self, records, *, property_key: str, property_value: object) -> dict[str, object]:
        normalized_records = list(records)
        self.property_save_calls.append({
            "records": normalized_records,
            "property_key": property_key,
            "property_value": property_value,
        })
        return {
            "updated_count": len(normalized_records),
            "property_key": property_key,
            "property_value": property_value,
        }

    def get_workers(self) -> dict[str, object]:
        return {
            "summary": {
                "current_count": 2,
                "working_count": 1,
                "idle_count": 1,
                "active_job_count": 1,
            },
            "items": [
                {
                    "worker_id": "worker-1",
                    "name": "CollectiblesWorker eBay items",
                    "worker_template_name": "CollectiblesWorker eBay items",
                    "status": "working",
                    "source_key": "ebay",
                    "source_label": "eBay",
                    "last_seen_at": "2026-04-14T01:00:00+00:00",
                    "captured_at": "2026-04-14T01:00:00+00:00",
                    "active_job_id": "dispatcher-job:ebay-active-stamps-listing:123",
                    "active_job_status": "working",
                    "job_capability": "eBay Active Stamps Listing",
                    "job_status": "claimed",
                    "capabilities": ["eBay Active Stamps Listing"],
                    "pid": 12345,
                    "config_path": "/tmp/worker_ebay_item.agent",
                    "launch_key": "worker_ebay_item",
                    "progress_message": "Importing active pages",
                },
                {
                    "worker_id": "worker-2",
                    "name": "CollectiblesWorker eBay items",
                    "worker_template_name": "CollectiblesWorker eBay items",
                    "status": "online",
                    "source_key": "ebay",
                    "source_label": "eBay",
                    "last_seen_at": "2026-04-14T00:59:00+00:00",
                    "captured_at": "2026-04-14T00:59:00+00:00",
                    "active_job_id": "",
                    "active_job_status": "",
                    "job_capability": "",
                    "job_status": "",
                    "capabilities": ["eBay Active Stamps Listing"],
                    "pid": 12346,
                    "config_path": "/tmp/worker_ebay_item.agent",
                    "launch_key": "worker_ebay_item",
                    "progress_message": "Waiting for work",
                },
            ],
            "launch_options": [
                {
                    "key": "worker_ebay_item",
                    "label": "eBay items",
                    "config_path": "/tmp/worker_ebay_item.agent",
                    "source_key": "ebay",
                    "source_label": "eBay",
                },
                {
                    "key": "worker_san",
                    "label": "SAN",
                    "config_path": "/tmp/worker_san.agent",
                    "source_key": "san",
                    "source_label": "SAN",
                },
            ],
            "saved_state": {
                "state_key": "latest",
                "updated_at": "2026-04-14T01:02:00+00:00",
                "items": [
                    {
                        "launch_key": "worker_ebay_item",
                        "label": "eBay items",
                        "source_key": "ebay",
                        "source_label": "eBay",
                        "count": 3,
                    }
                ],
                "total_count": 3,
            },
            "restore_plan": {
                "needs_restore": True,
                "saved_updated_at": "2026-04-14T01:02:00+00:00",
                "saved_total_count": 3,
                "current_total_count": 2,
                "missing": [
                    {
                        "launch_key": "worker_ebay_item",
                        "label": "eBay items",
                        "source_key": "ebay",
                        "source_label": "eBay",
                        "desired_count": 3,
                        "current_count": 2,
                        "count": 1,
                    }
                ],
                "extra": [],
            },
        }

    def get_reports(
        self,
        *,
        limit: int = 80,
        kind: str = "",
        source_key: str = "",
        include_acknowledged_reports: bool = False,
        include_resolved_alerts: bool = False,
    ) -> dict[str, object]:
        self.report_calls.append({
            "limit": limit,
            "kind": kind,
            "source_key": source_key,
            "include_acknowledged_reports": include_acknowledged_reports,
            "include_resolved_alerts": include_resolved_alerts,
        })
        items = [
            {
                "id": "derived:ebay-daily:2026-04-14T09:00:00+08:00",
                "kind": "report",
                "source_key": "ebay",
                "source_label": "eBay",
                "category_key": "ebay_daily_schedule",
                "title": "eBay Daily Schedule 2026-04-14T09:00:00+08:00",
                "summary": "Finished · 55 listings · 1 page",
                "body": "Run: 2026-04-14T09:00:00+08:00\nStatus: Finished\nListings queued: 55",
                "status": "finished",
                "severity": "success",
                "metrics": {
                    "pages": 1,
                    "listings": 55,
                    "retrieved": 55,
                    "updated": 18,
                    "errors": 0,
                },
                "payload": {
                    "report_date": "2026-04-14T09:00:00+08:00",
                    "status": "finished",
                    "queued_listing_jobs": 55,
                    "fan_out_pages": 1,
                },
                "response_status": "new",
                "response_note": "",
                "response_payload": {},
                "responded_by": "",
                "responded_at": "",
                "created_at": "2026-04-14T09:00:00+08:00",
                "updated_at": "2026-04-14T09:05:00+08:00",
                "derived": True,
            },
            {
                "id": "alert:watchlist:1",
                "kind": "alert",
                "source_key": "ebay",
                "source_label": "eBay",
                "category_key": "watchlist",
                "title": "Watched listing ended",
                "summary": "One watched eBay listing has ended.",
                "body": "seller-1 · Blue Bird Stamp Block",
                "status": "ended",
                "severity": "warning",
                "metrics": {},
                "payload": {"listing_uid": "sale-1"},
                "response_status": "new",
                "response_note": "",
                "response_payload": {},
                "responded_by": "",
                "responded_at": "",
                "created_at": "2026-04-14T10:00:00+08:00",
                "updated_at": "2026-04-14T10:00:00+08:00",
                "derived": False,
            },
        ]
        if kind:
            items = [item for item in items if item["kind"] == kind]
        if source_key:
            items = [item for item in items if item["source_key"] == source_key]
        items = items[:limit]
        return {
            "items": items,
            "summary": {
                "total_count": len(items),
                "report_count": sum(1 for item in items if item["kind"] == "report"),
                "alert_count": sum(1 for item in items if item["kind"] == "alert"),
                "source_counts": [
                    {
                        "source_key": "ebay",
                        "source_label": "eBay",
                        "count": len(items),
                    }
                ] if items else [],
            },
            "filters": {
                "kind": kind,
                "source_key": source_key,
                "limit": limit,
                "include_acknowledged_reports": include_acknowledged_reports,
                "include_resolved_alerts": include_resolved_alerts,
            },
        }

    def respond_report_item(
        self,
        report_id: str,
        *,
        response_status: str,
        response_note: str = "",
        response_payload=None,
        responded_by: str = "console",
    ) -> dict[str, object]:
        normalized = {
            "report_id": report_id,
            "response_status": response_status,
            "response_note": response_note,
            "response_payload": response_payload or {},
            "responded_by": responded_by,
        }
        self.report_response_calls.append(normalized)
        return {
            "id": str(report_id or "report-item:test"),
            "kind": "alert",
            "source_key": "ebay",
            "source_label": "eBay",
            "category_key": "watchlist",
            "title": "Watchlist update",
            "summary": "A watched listing has changed.",
            "body": "",
            "status": "active",
            "severity": "warning",
            "metrics": {},
            "payload": {"listing_uid": "sale-1"},
            "response_status": str(response_status or "new"),
            "response_note": str(response_note or ""),
            "response_payload": response_payload or {},
            "responded_by": str(responded_by or "console"),
            "responded_at": "2026-04-14T10:05:00+08:00",
            "created_at": "2026-04-14T10:00:00+08:00",
            "updated_at": "2026-04-14T10:05:00+08:00",
            "derived": False,
        }

    def bulk_respond_report_alerts(
        self,
        *,
        response_status: str,
        source_key: str = "",
        include_resolved_alerts: bool = False,
        response_note: str = "",
        response_payload=None,
        responded_by: str = "console",
    ) -> dict[str, object]:
        normalized = {
            "response_status": response_status,
            "source_key": source_key,
            "include_resolved_alerts": include_resolved_alerts,
            "response_note": response_note,
            "response_payload": response_payload or {},
            "responded_by": responded_by,
        }
        self.report_bulk_response_calls.append(normalized)
        return {
            "response_status": str(response_status or "new"),
            "source_key": str(source_key or ""),
            "include_resolved_alerts": bool(include_resolved_alerts),
            "updated_count": 3,
            "updated_ids": ["alert:watchlist:1", "alert:watchlist:2", "alert:watchlist:3"],
            "responded_by": str(responded_by or "console"),
            "responded_at": "2026-04-14T10:08:00+08:00",
        }

    def get_worker_log(self, worker_id: str, *, limit: int = 60) -> dict[str, object]:
        self.worker_log_calls.append({
            "worker_id": worker_id,
            "limit": limit,
        })
        return {
            "worker_id": worker_id,
            "name": "CollectiblesWorker eBay items",
            "lines": [
                {
                    "captured_at": "2026-04-14T01:00:00+00:00",
                    "event_type": "heartbeat",
                    "status": "working",
                    "phase": "import",
                    "message": "Importing active pages",
                    "active_job_id": "dispatcher-job:ebay-active-stamps-listing:123",
                    "active_job_status": "working",
                }
            ],
        }

    def start_worker(self, launch_key: str) -> dict[str, object]:
        self.start_worker_calls.append(str(launch_key))
        return {
            "started": True,
            "launch_key": launch_key,
            "label": "eBay items",
            "config_path": "/tmp/worker_ebay_item.agent",
            "pid": 22345,
            "log_path": "/tmp/collectibles-worker-logs/worker_ebay_item.log",
            "started_at": "2026-04-14T01:05:00+00:00",
        }

    def terminate_worker(self, worker_id: str) -> dict[str, object]:
        self.terminate_worker_calls.append(str(worker_id))
        return {
            "terminated": True,
            "worker_id": worker_id,
            "pid": 12345,
            "status": "terminating",
        }

    def bulk_worker_action(self, action: str, *, launch_key: str = "") -> dict[str, object]:
        self.bulk_worker_calls.append({
            "action": str(action),
            "launch_key": str(launch_key),
        })
        return {
            "completed": True,
            "in_progress": False,
            "action": str(action),
            "launch_key": str(launch_key),
            "saved_state": {
                "state_key": "latest",
                "items": [
                    {
                        "launch_key": "worker_ebay_item",
                        "label": "eBay items",
                        "source_key": "ebay",
                        "source_label": "eBay",
                        "count": 2,
                    }
                ],
                "total_count": 2,
            },
            "started": [{"launch_key": "worker_ebay_item", "pid": 22345}],
            "terminated": [{"worker_id": "worker-1", "pid": 12345, "terminated": True}],
            "errors": [],
        }

    def restore_worker_state(self) -> dict[str, object]:
        self.restore_worker_calls += 1
        return {
            "restored": True,
            "saved_state": {
                "state_key": "latest",
                "updated_at": "2026-04-14T01:02:00+00:00",
                "items": [
                    {
                        "launch_key": "worker_ebay_item",
                        "label": "CollectiblesWorker eBay items",
                        "source_key": "ebay",
                        "source_label": "eBay",
                        "count": 2,
                    }
                ],
                "total_count": 2,
            },
            "restore_plan": {
                "needs_restore": True,
                "saved_updated_at": "2026-04-14T01:02:00+00:00",
                "saved_total_count": 2,
                "current_total_count": 1,
                "missing": [
                    {
                        "launch_key": "worker_ebay_item",
                        "label": "CollectiblesWorker eBay items",
                        "source_key": "ebay",
                        "source_label": "eBay",
                        "desired_count": 2,
                        "current_count": 1,
                        "count": 1,
                    }
                ],
                "extra": [],
            },
            "started": [{"launch_key": "worker_ebay_item", "pid": 22345}],
            "terminated": [],
            "errors": [],
        }

    def save_current_worker_state(self) -> dict[str, object]:
        self.save_current_worker_calls += 1
        return {
            "saved": True,
            "saved_state": {
                "state_key": "latest",
                "updated_at": "2026-04-14T01:03:00+00:00",
                "items": [
                    {
                        "launch_key": "worker_ebay_item",
                        "label": "CollectiblesWorker eBay items",
                        "source_key": "ebay",
                        "source_label": "eBay",
                        "count": 1,
                    }
                ],
                "total_count": 1,
            },
            "restore_plan": {
                "needs_restore": False,
                "saved_updated_at": "2026-04-14T01:03:00+00:00",
                "saved_total_count": 1,
                "current_total_count": 1,
                "missing": [],
                "extra": [],
            },
        }


def build_client(tmp_path: Path) -> tuple[TestClient, FakeCollectiblesRepository, Path]:
    image_path = tmp_path / "allowed" / "bird.jpg"
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"bird-image")
    alt_image_path = tmp_path / "allowed" / "heron.jpg"
    alt_image_path.write_bytes(b"heron-image")
    repo = FakeCollectiblesRepository(image_path=image_path, alt_image_path=alt_image_path)
    app = create_app(repository=repo, media_roots=[tmp_path / "allowed"])
    return TestClient(app), repo, image_path


def test_root_renders_collectibles_shell(tmp_path: Path):
    client, _, _ = build_client(tmp_path)
    response = client.get("/")
    assert response.status_code == 200
    assert "Collectibles Atlas" in response.text
    assert "Catalog" in response.text
    assert "Reports" in response.text
    assert "Dashboard" in response.text
    assert "Workers" in response.text
    assert "Edit" in response.text
    assert "Refresh" in response.text


def test_summary_api_includes_san_listing_count(tmp_path: Path):
    client, _, _ = build_client(tmp_path)

    response = client.get("/api/summary")

    assert response.status_code == 200
    assert response.json()["san_listings"] == 5


def test_dashboard_api_returns_live_metrics_and_workers(tmp_path: Path):
    client, _, _ = build_client(tmp_path)

    response = client.get("/api/dashboard", params={"history_limit": 12})

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot_interval_minutes"] == 1
    assert payload["current"]["sources"][0]["label"] == "Colnect"
    assert payload["current"]["sources"][1]["page_jobs"]["queued"] == 2
    assert payload["ebay_daily_schedule"]["status"] == "scheduled"
    assert payload["ebay_daily_schedule"]["job_status"] == "claimed"
    assert payload["rate_limit_locks"][0]["active"] is True
    assert payload["ebay_daily_reports"][0]["status"] == "finished"
    assert payload["ebay_daily_reports"][0]["fan_out_pages"] == 1
    assert payload["unresolved_alerts"]["total_count"] == 2
    assert payload["unresolved_alerts"]["latest"][0]["title"] == "eBay rate limit lock active"
    assert payload["workers"]["items"][0]["job_capability"] == "eBay Active Stamps Listing"


def test_dashboard_worker_summary_does_not_fall_back_to_stale_heartbeat_rows():
    class _Repo(CollectiblesRepository):
        def _current_workers(self, *, only_working: bool = False):
            return []

        def _fetchone(self, sql: str, params=None):
            raise AssertionError("dashboard worker summary should use the live worker list only")

    repo = _Repo(dsn="postgresql://localhost/collectibles?sslmode=disable")

    assert repo._dashboard_worker_summary() == {
        "current_count": 0,
        "working_count": 0,
        "idle_count": 0,
        "active_job_count": 0,
    }


def test_dashboard_job_counts_only_treats_live_claimants_as_working():
    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.last_sql = ""
            self.last_params = []

        def _fetchall(self, sql: str, params=None):
            self.last_sql = " ".join(str(sql).split()).lower()
            self.last_params = list(params or [])
            return [{"capability": "ebay active stamps listing", "queued": 2, "working": 0}]

    repo = _Repo()

    assert repo._dashboard_job_counts("eBay Active Stamps Listing", []) == {"queued": 2, "working": 0, "pending": 2}
    assert "filter (where false)" in repo.last_sql
    assert repo.last_params == ["ebay active stamps listing"]

    repo._dashboard_job_counts("eBay Active Stamps Listing", ["dispatcher-worker:live"])
    assert "claimed_by" in repo.last_sql
    assert repo.last_params == ["dispatcher-worker:live", "ebay active stamps listing"]


def test_dashboard_ebay_schedule_status_accepts_renamed_ten_minute_schedule():
    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.last_sql = ""
            self.last_params = []

        def _fetchone(self, sql: str, params=None):
            self.last_sql = " ".join(str(sql).split()).lower()
            self.last_params = list(params or [])
            return {
                "id": "dispatcher-boss-schedule:ebay-daily-20260412-0200-10m",
                "name": "10 Minutes Scheduled Job (10m)",
                "status": "scheduled",
                "required_capability": "10 Minutes Scheduled Job",
                "scheduled_for": "2026-04-16T20:00:00+08:00",
                "issued_at": "2026-04-16T19:50:03+08:00",
                "updated_at": "2026-04-16T19:50:03+08:00",
                "dispatcher_job_id": "dispatcher-job:ten-minute",
                "metadata": {"schedule_interval_minutes": 10},
                "job_status": "queued",
                "job_claimed_by": "",
                "job_claimed_at": "",
                "job_completed_at": "",
                "job_updated_at": "2026-04-16T19:50:03+08:00",
                "job_error": "",
                "job_worker_name": "",
            }

    repo = _Repo()

    payload = repo._dashboard_ebay_schedule_status()

    assert payload["name"] == "10 Minutes Scheduled Job (10m)"
    assert payload["required_capability"] == "10 Minutes Scheduled Job"
    assert payload["schedule_interval_minutes"] == 10
    assert payload["job_status"] == "queued"
    assert "required_capability" in repo.last_sql
    assert repo.last_params == [
        "",
        "10 Minutes Scheduled Job",
        "10 Minutes Scheduled Job",
        "eBay Daily Schedule",
    ]


def test_dashboard_archive_schedule_status_returns_daily_archive_job():
    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.last_sql = ""
            self.last_params = []

        def _fetchone(self, sql: str, params=None):
            self.last_sql = " ".join(str(sql).split()).lower()
            self.last_params = list(params or [])
            return {
                "id": "dispatcher-boss-schedule:collectibles-daily-job-archive",
                "name": "Daily Job Archive (3AM)",
                "status": "scheduled",
                "required_capability": "Daily Job Archive",
                "scheduled_for": "2026-04-17T03:00:00+08:00",
                "issued_at": "2026-04-16T03:00:04+08:00",
                "updated_at": "2026-04-16T03:00:04+08:00",
                "dispatcher_job_id": "dispatcher-job:archive",
                "metadata": {},
                "job_status": "completed",
                "job_claimed_by": "dispatcher-worker:dashboard",
                "job_claimed_at": "2026-04-16T03:00:10+08:00",
                "job_completed_at": "2026-04-16T03:01:20+08:00",
                "job_updated_at": "2026-04-16T03:01:20+08:00",
                "job_error": "",
                "job_worker_name": "CollectiblesWorker Dashboard",
            }

    repo = _Repo()

    payload = repo._dashboard_archive_schedule_status()

    assert payload["name"] == "Daily Job Archive (3AM)"
    assert payload["required_capability"] == "Daily Job Archive"
    assert payload["job_status"] == "completed"
    assert "required_capability" in repo.last_sql
    assert "schedule_rank" in repo.last_sql
    assert repo.last_params == [
        "dispatcher-boss-schedule:collectibles-daily-job-archive",
        "Daily Job Archive",
        "Daily Job Archive",
    ]


def test_dashboard_monthly_archive_schedule_status_returns_monthly_cleanup_job():
    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.last_sql = ""
            self.last_params = []

        def _fetchone(self, sql: str, params=None):
            self.last_sql = " ".join(str(sql).split()).lower()
            self.last_params = list(params or [])
            return {
                "id": "dispatcher-boss-schedule:collectibles-monthly-archive-cleanup",
                "name": "Monthly Archive Cleanup (4AM)",
                "status": "scheduled",
                "required_capability": "Daily Job Archive",
                "scheduled_for": "2026-05-01T04:00:00+08:00",
                "issued_at": "",
                "updated_at": "2026-04-16T23:25:23+08:00",
                "dispatcher_job_id": "",
                "metadata": {},
                "job_status": "",
                "job_claimed_by": "",
                "job_claimed_at": "",
                "job_completed_at": "",
                "job_updated_at": "",
                "job_error": "",
                "job_worker_name": "",
            }

    repo = _Repo()

    payload = repo._dashboard_monthly_archive_schedule_status()

    assert payload["name"] == "Monthly Archive Cleanup (4AM)"
    assert payload["required_capability"] == "Daily Job Archive"
    assert payload["scheduled_for"] == "2026-05-01T04:00:00+08:00"
    assert "schedule_rank" in repo.last_sql
    assert repo.last_params == [
        "dispatcher-boss-schedule:collectibles-monthly-archive-cleanup",
        "Daily Job Archive",
        "Daily Job Archive",
    ]


def test_dashboard_monthly_archive_history_returns_recent_cleanup_jobs():
    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.last_sql = ""
            self.last_params = []

        def _fetchall(self, sql: str, params=None):
            self.last_sql = " ".join(str(sql).split()).lower()
            self.last_params = list(params or [])
            return [
                {
                    "id": "dispatcher-job:monthly-cleanup-1",
                    "status": "completed",
                    "required_capability": "Daily Job Archive",
                    "claimed_by": "dispatcher-worker:dashboard",
                    "claimed_at": "2026-05-01T04:00:10+08:00",
                    "completed_at": "2026-05-01T04:02:10+08:00",
                    "created_at": "2026-05-01T04:00:00+08:00",
                    "updated_at": "2026-05-01T04:02:10+08:00",
                    "archived_at": "2026-05-01T04:03:00+08:00",
                    "result_summary": {
                        "archived_jobs": 3,
                        "purged_rows": 40,
                        "related_table_archives": [
                            {"table": "dispatcher_worker_history", "archived_rows": 10},
                            {"table": "dispatcher_raw_payloads", "archived_rows": 2},
                        ],
                    },
                    "error": "",
                    "worker_name": "CollectiblesWorker Dashboard",
                }
            ]

    repo = _Repo()

    payload = repo._dashboard_monthly_archive_history(limit=5)

    assert payload == [
        {
            "job_id": "dispatcher-job:monthly-cleanup-1",
            "status": "completed",
            "required_capability": "Daily Job Archive",
            "claimed_by": "dispatcher-worker:dashboard",
            "worker_name": "CollectiblesWorker Dashboard",
            "claimed_at": "2026-05-01T04:00:10+08:00",
            "completed_at": "2026-05-01T04:02:10+08:00",
            "created_at": "2026-05-01T04:00:00+08:00",
            "updated_at": "2026-05-01T04:02:10+08:00",
            "archived_at": "2026-05-01T04:03:00+08:00",
            "archived_jobs": 3,
            "archived_rows": 15,
            "purged_rows": 40,
            "error": "",
        }
    ]
    assert "boss_schedule_id" in repo.last_sql
    assert repo.last_params == [
        "dispatcher-boss-schedule:collectibles-monthly-archive-cleanup",
        "dispatcher-boss-schedule:collectibles-monthly-archive-cleanup",
        5,
    ]


def test_dashboard_ebay_daily_reports_marks_completed_page_runs_finished():
    class _Repo(CollectiblesRepository):
        def _fetchall(self, sql: str, params=None):
            normalized_sql = " ".join(str(sql).split()).lower()
            if f"from public.{collectibles_app.TABLE_EBAY_ACTIVE_DAILY_REPORTS}".lower() in normalized_sql:
                return [
                    {
                        "report_date": "2026-04-15T04:00:00+08:00",
                        "status": "processing page",
                        "planned_status_jobs": 1,
                        "planned_page_jobs": 1,
                        "planned_retrieval_items": 200,
                        "updated_items": 1,
                        "retrieved_items": 0,
                        "error_count": 0,
                        "payload": {
                            "queued_listing_jobs": 62,
                            "job_counts": {
                                "total_jobs": 1,
                                "completed_jobs": 0,
                                "failed_jobs": 0,
                                "active_jobs": 1,
                            },
                        },
                        "updated_at": "2026-04-15T04:02:22.272525+08:00",
                    }
                ]
            if (
                f"from public.{collectibles_app.TABLE_JOBS}".lower() in normalized_sql
                and f"from public.{collectibles_app.TABLE_JOB_ARCHIVE}".lower() in normalized_sql
            ):
                return [
                    {
                        "report_date": "2026-04-15T04:00:00+08:00",
                        "status": "completed",
                    }
                ]
            return []

    repo = _Repo(dsn="postgresql://localhost/collectibles?sslmode=disable")

    payload = repo._dashboard_ebay_daily_reports(3)

    assert payload[0]["status"] == "finished"
    assert payload[0]["queued_listing_jobs"] == 62


def test_workers_api_returns_items_and_launch_options(tmp_path: Path):
    client, _, _ = build_client(tmp_path)

    response = client.get("/api/workers")

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["current_count"] == 2
    assert payload["items"][0]["worker_id"] == "worker-1"
    assert payload["launch_options"][0]["key"] == "worker_ebay_item"
    assert payload["saved_state"]["total_count"] == 3
    assert payload["restore_plan"]["needs_restore"] is True
    assert payload["restore_plan"]["missing"][0]["count"] == 1


def test_reports_api_returns_feed_items(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.get(
        "/api/reports",
        params={
            "limit": 25,
            "kind": "alert",
            "source_key": "ebay",
            "include_resolved_alerts": "true",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["summary"]["total_count"] == 1
    assert payload["summary"]["alert_count"] == 1
    assert payload["items"][0]["category_key"] == "watchlist"
    assert payload["filters"] == {
        "kind": "alert",
        "source_key": "ebay",
        "limit": 25,
        "include_acknowledged_reports": False,
        "include_resolved_alerts": True,
    }
    assert repo.report_calls[-1] == {
        "limit": 25,
        "kind": "alert",
        "source_key": "ebay",
        "include_acknowledged_reports": False,
        "include_resolved_alerts": True,
    }


def test_report_feed_filters_acknowledged_reports_and_resolved_alerts_by_default():
    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.last_sql = ""
            self.last_params = []

        def _ensure_report_items_table(self) -> None:
            pass

        def _sync_ebay_daily_reports_to_report_feed(self, *, limit: int = 20) -> None:
            del limit

        def _fetchall(self, sql: str, params=None):
            self.last_sql = " ".join(str(sql).split()).lower()
            self.last_params = list(params or [])
            return []

    repo = _Repo()

    payload = repo.get_reports(limit=25)

    assert payload["filters"]["include_acknowledged_reports"] is False
    assert payload["filters"]["include_resolved_alerts"] is False
    assert "(kind <> 'report' or coalesce(nullif(response_status, ''), 'new') <> 'acknowledged')" in repo.last_sql
    assert "(kind <> 'alert' or coalesce(nullif(response_status, ''), 'new') <> 'resolved')" in repo.last_sql
    assert repo.last_params == [25]

    repo.get_reports(limit=25, kind="report", include_acknowledged_reports=True)

    assert "kind = %s" in repo.last_sql
    assert "acknowledged" not in repo.last_sql
    assert repo.last_params == ["report", 25]

    repo.get_reports(limit=25, kind="alert", include_resolved_alerts=True)

    assert "kind = %s" in repo.last_sql
    assert "resolved" not in repo.last_sql
    assert repo.last_params == ["alert", 25]


def test_dashboard_unresolved_alerts_summarizes_open_report_feed_items():
    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.ensured_report_table = False
            self.last_sql = ""
            self.last_params = []

        def _ensure_report_items_table(self) -> None:
            self.ensured_report_table = True

        def _fetchall(self, sql: str, params=None):
            self.last_sql = " ".join(str(sql).split()).lower()
            self.last_params = list(params or [])
            return [
                {
                    "counts": {"total_count": 2, "new_count": 1, "acknowledged_count": 1},
                    "sources": [{"source_key": "ebay", "source_label": "eBay", "count": 2}],
                    "latest": [
                        {
                            "id": "alert:ebay:rate-limit",
                            "source_key": "ebay",
                            "source_label": "eBay",
                            "title": "eBay rate limit lock active",
                            "severity": "warning",
                            "response_status": "new",
                            "created_at": "2026-04-14T09:02:00+08:00",
                            "updated_at": "2026-04-14T09:02:00+08:00",
                        }
                    ],
                }
            ]

    repo = _Repo()

    payload = repo._dashboard_unresolved_alerts(limit=4)

    assert repo.ensured_report_table is True
    assert "where kind = 'alert'" in repo.last_sql
    assert "response_status, ''), 'new') <> 'resolved'" in repo.last_sql
    assert repo.last_params == [4]
    assert payload["total_count"] == 2
    assert payload["new_count"] == 1
    assert payload["acknowledged_count"] == 1
    assert payload["sources"][0]["source_label"] == "eBay"
    assert payload["latest"][0]["kind"] == "alert"
    assert payload["latest"][0]["response_status"] == "new"


def test_respond_report_api_updates_item_state(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.post(
        "/api/reports/alert:watchlist:1/respond",
        json={
            "response_status": "resolved",
            "response_note": "Handled in console.",
            "response_payload": {"listing_uid": "sale-1"},
            "responded_by": "console-main",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "alert:watchlist:1"
    assert payload["kind"] == "alert"
    assert payload["response_status"] == "resolved"
    assert payload["responded_by"] == "console-main"
    assert repo.report_response_calls[-1] == {
        "report_id": "alert:watchlist:1",
        "response_status": "resolved",
        "response_note": "Handled in console.",
        "response_payload": {"listing_uid": "sale-1"},
        "responded_by": "console-main",
    }


def test_bulk_respond_reports_api_updates_matching_alerts(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.post(
        "/api/reports/bulk/respond",
        json={
            "response_status": "acknowledged",
            "source_key": "ebay",
            "include_resolved_alerts": True,
            "responded_by": "console-main",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["response_status"] == "acknowledged"
    assert payload["updated_count"] == 3
    assert repo.report_bulk_response_calls[-1] == {
        "response_status": "acknowledged",
        "source_key": "ebay",
        "include_resolved_alerts": True,
        "response_note": "",
        "response_payload": {},
        "responded_by": "console-main",
    }


def test_bulk_respond_report_alerts_updates_unresolved_alert_rows_only():
    class _Cursor:
        def __init__(self):
            self.sql = ""
            self.params = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def execute(self, sql: str, params=None):
            self.sql = " ".join(str(sql).split()).lower()
            self.params = list(params or [])

        def fetchall(self):
            return [{"id": "alert:1"}, {"id": "alert:2"}]

    class _Connection:
        def __init__(self, cursor):
            self.cursor_instance = cursor

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def cursor(self):
            return self.cursor_instance

    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.cursor_instance = _Cursor()
            self.ensured_report_table = False

        def _ensure_report_items_table(self) -> None:
            self.ensured_report_table = True

        def _connect(self):
            return _Connection(self.cursor_instance)

    repo = _Repo()

    payload = repo.bulk_respond_report_alerts(response_status="resolved", source_key="ebay", responded_by="console-main")

    assert repo.ensured_report_table is True
    assert payload["updated_count"] == 2
    assert payload["updated_ids"] == ["alert:1", "alert:2"]
    assert "kind = 'alert'" in repo.cursor_instance.sql
    assert "response_status, ''), 'new') <> 'resolved'" in repo.cursor_instance.sql
    assert "source_key = %s" in repo.cursor_instance.sql
    assert repo.cursor_instance.sql.count("%s") == len(repo.cursor_instance.params)
    assert repo.cursor_instance.params[0] == "resolved"
    assert repo.cursor_instance.params[-2] == "resolved"
    assert repo.cursor_instance.params[-1] == "ebay"


def test_current_workers_filters_dead_local_worker_processes():
    class _Repo(CollectiblesRepository):
        def _fetchall(self, sql: str, params=None):
            del params
            normalized_sql = " ".join(str(sql).split()).lower()
            if "from public.dispatcher_worker_capabilities wc" not in normalized_sql:
                return []
            return [
                {
                    "worker_id": "worker-live",
                    "name": "CollectiblesWorker eBay items",
                    "status": "working",
                    "capabilities": ["eBay Active Stamps Listing"],
                    "metadata": {
                        "environment": {
                            "pid": 111,
                            "config_path": "/tmp/worker_ebay_item.agent",
                        },
                        "heartbeat": {
                            "session_started_at": "2026-04-14T18:51:59+00:00",
                            "progress": {"message": "Processing", "phase": "working"},
                        },
                    },
                    "last_seen_at": "2026-04-15T01:00:00+00:00",
                    "active_job_id": "dispatcher-job:one",
                    "active_job_status": "working",
                    "captured_at": "2026-04-15T01:00:00+00:00",
                    "required_capability": "eBay Active Stamps Listing",
                    "job_status": "claimed",
                    "job_payload": {
                        "title": "US stamp lot",
                        "page_number": 2,
                    },
                    "job_metadata": {
                        "ebay_active_stamp": {
                            "job_kind": "listing",
                            "source_listing_id": "12345",
                        },
                    },
                    "job_source_url": "https://www.ebay.com/itm/12345",
                },
                {
                    "worker_id": "worker-dead",
                    "name": "CollectiblesWorker Colnect only",
                    "status": "online",
                    "capabilities": ["Colnect Stamp Listing"],
                    "metadata": {
                        "environment": {
                            "pid": 222,
                            "config_path": "/tmp/worker_colnect_item.agent",
                        },
                        "heartbeat": {
                            "session_started_at": "2026-04-14T18:52:00+00:00",
                            "progress": {"message": "Waiting", "phase": "idle"},
                        },
                    },
                    "last_seen_at": "2026-04-15T01:00:00+00:00",
                    "active_job_id": "",
                    "active_job_status": "",
                    "captured_at": "2026-04-15T01:00:00+00:00",
                    "required_capability": "",
                    "job_status": "",
                },
            ]

        def _worker_process_is_live(self, pid: int, config_path: str = "", command: str = "") -> bool:
            del config_path, command
            return pid == 111

    repo = _Repo(dsn="postgresql://localhost/collectibles?sslmode=disable")

    payload = repo._current_workers()

    assert [item["worker_id"] for item in payload] == ["worker-live"]
    assert payload[0]["pid"] == 111
    assert payload[0]["job_payload"]["title"] == "US stamp lot"
    assert payload[0]["job_metadata"]["ebay_active_stamp"]["source_listing_id"] == "12345"
    assert payload[0]["job_source_url"] == "https://www.ebay.com/itm/12345"


def test_worker_launch_options_reloads_config_files_on_each_call(tmp_path: Path):
    original_base_dir = collectibles_app.BASE_DIR
    configs_dir = tmp_path / "configs"
    configs_dir.mkdir(parents=True, exist_ok=True)
    config_path = configs_dir / "worker_demo.agent"
    config_path.write_text('{"name":"Demo Worker A"}', encoding="utf-8")

    collectibles_app.BASE_DIR = tmp_path
    try:
        first = collectibles_app._worker_launch_options()
        config_path.write_text('{"name":"Demo Worker B"}', encoding="utf-8")
        second = collectibles_app._worker_launch_options()
    finally:
        collectibles_app.BASE_DIR = original_base_dir

    assert first[0]["label"] == "Demo Worker A"
    assert second[0]["label"] == "Demo Worker B"


def test_worker_log_api_returns_recent_lines(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.get("/api/workers/worker-1/log", params={"limit": 25})

    assert response.status_code == 200
    payload = response.json()
    assert payload["worker_id"] == "worker-1"
    assert payload["lines"][0]["message"] == "Importing active pages"
    assert repo.worker_log_calls[-1] == {"worker_id": "worker-1", "limit": 25}


def test_get_worker_log_prefers_launch_info_lines(tmp_path: Path):
    original_log_dir = collectibles_app.WORKER_LAUNCH_LOG_DIR
    log_dir = tmp_path / "worker-logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "worker_ebay_item-20260415-025157.log"
    log_path.write_text(
        "\n".join(
            [
                "[CollectiblesWorker eBay items] 2026-04-15 02:51:58,100 - prompits.agents.base - INFO - Polling dispatcher for matching jobs...",
                "[CollectiblesWorker eBay items] 2026-04-15 02:51:59,200 - prompits.agents.base - INFO - Claimed dispatcher job dispatcher-job:ebay-active-stamps-listing:123 for capability 'ebay active stamps listing'.",
                "[CollectiblesWorker eBay items] 2026-04-15 02:52:00,300 - prompits.agents.base - INFO - eBay listing job 123: fetched full listing metadata.",
            ]
        ),
        encoding="utf-8",
    )

    class _Repo(CollectiblesRepository):
        def _current_workers(self, *, only_working: bool = False):
            del only_working
            return [
                {
                    "worker_id": "worker-1",
                    "name": "CollectiblesWorker eBay items",
                    "launch_key": "worker_ebay_item",
                    "session_started_at": "2026-04-14T18:51:59+00:00",
                }
            ]

        def _fetchall(self, sql: str, params=None):
            del sql, params
            return []

    collectibles_app.WORKER_LAUNCH_LOG_DIR = log_dir
    try:
        repo = _Repo(dsn="postgresql://localhost/collectibles?sslmode=disable")
        payload = repo.get_worker_log("worker-1", limit=2)
    finally:
        collectibles_app.WORKER_LAUNCH_LOG_DIR = original_log_dir

    assert payload["source"] == "launch_log"
    assert payload["log_path"] == str(log_path)
    assert payload["name"] == "CollectiblesWorker eBay items"
    assert [line["message"] for line in payload["lines"]] == [
        "eBay listing job 123: fetched full listing metadata.",
        "Claimed dispatcher job dispatcher-job:ebay-active-stamps-listing:123 for capability 'ebay active stamps listing'.",
    ]
    assert payload["lines"][0]["raw_line"].startswith("[CollectiblesWorker eBay items] 2026-04-15 02:52:00,300")
    assert payload["lines"][0]["level"] == "info"
    assert payload["lines"][0]["logger_name"] == "prompits.agents.base"
    assert payload["lines"][0]["source"] == "launch_log"


def test_get_worker_log_falls_back_to_worker_history_when_launch_log_missing(tmp_path: Path):
    original_log_dir = collectibles_app.WORKER_LAUNCH_LOG_DIR
    log_dir = tmp_path / "empty-worker-logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    class _Repo(CollectiblesRepository):
        def _current_workers(self, *, only_working: bool = False):
            del only_working
            return [
                {
                    "worker_id": "worker-1",
                    "name": "CollectiblesWorker eBay items",
                    "launch_key": "worker_ebay_item",
                    "session_started_at": "2026-04-14T18:51:59+00:00",
                }
            ]

        def _fetchall(self, sql: str, params=None):
            del sql, params
            return [
                {
                    "worker_id": "worker-1",
                    "name": "CollectiblesWorker eBay items",
                    "status": "working",
                    "event_type": "heartbeat",
                    "active_job_id": "dispatcher-job:ebay-active-stamps-listing:123",
                    "active_job_status": "working",
                    "captured_at": "2026-04-14T01:00:00+00:00",
                    "metadata": {
                        "heartbeat": {
                            "progress": {
                                "message": "Importing active pages",
                                "phase": "import",
                            }
                        }
                    },
                }
            ]

    collectibles_app.WORKER_LAUNCH_LOG_DIR = log_dir
    try:
        repo = _Repo(dsn="postgresql://localhost/collectibles?sslmode=disable")
        payload = repo.get_worker_log("worker-1", limit=10)
    finally:
        collectibles_app.WORKER_LAUNCH_LOG_DIR = original_log_dir

    assert payload["source"] == "worker_history"
    assert payload["log_path"] == ""
    assert payload["lines"][0]["message"] == "Importing active pages"
    assert payload["lines"][0]["source"] == "worker_history"
    assert payload["lines"][0]["phase"] == "import"


def test_start_worker_api_uses_launch_key(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.post("/api/workers/start", json={"launch_key": "worker_ebay_item"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["started"] is True
    assert payload["pid"] == 22345
    assert repo.start_worker_calls[-1] == "worker_ebay_item"


def test_start_worker_persists_from_saved_state_without_live_worker_scan(tmp_path: Path, monkeypatch):
    original_log_dir = collectibles_app.WORKER_LAUNCH_LOG_DIR
    collectibles_app.WORKER_LAUNCH_LOG_DIR = tmp_path / "worker-logs"

    class _Process:
        pid = 4242

    def _fake_popen(*_args, **_kwargs):
        return _Process()

    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.persisted_items = []

        def _current_workers(self, *, only_working: bool = False):
            raise AssertionError("start_worker should not scan live workers before returning")

        def _ensure_worker_state_table(self):
            return

        def _fetchone(self, sql: str, params=None):
            normalized_sql = " ".join(str(sql).split()).lower()
            if f"from public.{collectibles_app.TABLE_WORKER_STATES}".lower() in normalized_sql:
                return {
                    "state_key": "latest",
                    "updated_at": "2026-04-16T12:00:00+00:00",
                    "payload": {
                        "items": [
                            {
                                "launch_key": "worker_ebay_item",
                                "label": "eBay items",
                                "source_key": "ebay",
                                "source_label": "eBay",
                                "count": 2,
                            }
                        ],
                    },
                }
            raise AssertionError(f"unexpected sql: {sql}")

        def _persist_worker_state_items(self, items):
            self.persisted_items = [dict(item) for item in items]
            return self._worker_state_from_row(
                {
                    "state_key": "latest",
                    "updated_at": "2026-04-16T12:01:00+00:00",
                    "payload": self._worker_state_payload_from_items(self.persisted_items),
                }
            )

    monkeypatch.setattr(collectibles_app.subprocess, "Popen", _fake_popen)
    try:
        repo = _Repo()
        payload = repo.start_worker("worker_ebay_item")
    finally:
        collectibles_app.WORKER_LAUNCH_LOG_DIR = original_log_dir

    assert payload["started"] is True
    assert payload["pid"] == 4242
    assert repo.persisted_items[0]["launch_key"] == "worker_ebay_item"
    assert repo.persisted_items[0]["count"] == 3


def test_terminate_worker_api_targets_worker(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.post("/api/workers/worker-1/terminate")

    assert response.status_code == 200
    payload = response.json()
    assert payload["terminated"] is True
    assert repo.terminate_worker_calls[-1] == "worker-1"


def test_bulk_workers_api_scopes_to_launch_key(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.post("/api/workers/bulk", json={"action": "restart_all", "launch_key": "worker_ebay_item"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["completed"] is True
    assert payload["started"][0]["launch_key"] == "worker_ebay_item"
    assert repo.bulk_worker_calls[-1] == {"action": "restart_all", "launch_key": "worker_ebay_item"}


def test_bulk_worker_restart_relaunches_group_and_preserves_desired_counts():
    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.started: list[str] = []
            self.terminated: list[str] = []
            self.persisted_items: list[dict[str, object]] = []
            self.current_workers = [
                {
                    "worker_id": "worker-1",
                    "name": "eBay Item",
                    "worker_template_name": "eBay Item",
                    "launch_key": "worker_ebay_item",
                    "source_key": "ebay",
                    "source_label": "eBay",
                    "pid": 101,
                },
                {
                    "worker_id": "worker-2",
                    "name": "eBay Item",
                    "worker_template_name": "eBay Item",
                    "launch_key": "worker_ebay_item",
                    "source_key": "ebay",
                    "source_label": "eBay",
                    "pid": 102,
                },
                {
                    "worker_id": "worker-3",
                    "name": "SAN",
                    "worker_template_name": "SAN",
                    "launch_key": "worker_san",
                    "source_key": "san",
                    "source_label": "SAN",
                    "pid": 103,
                },
            ]

        def _current_workers(self, *, only_working: bool = False):
            return list(self.current_workers)

        def _saved_worker_state(self, current_workers=None):
            return self._worker_state_from_row(
                {
                    "state_key": "latest",
                    "updated_at": "2026-04-16T12:00:00+00:00",
                    "payload": self._worker_state_payload_from_items(
                        self._worker_state_items_from_workers(current_workers or self.current_workers)
                    ),
                }
            )

        def terminate_worker(self, worker_id: str, *, persist_state: bool = True):
            self.terminated.append(worker_id)
            return {"terminated": True, "worker_id": worker_id, "status": "terminating"}

        def start_worker(self, launch_key: str, *, persist_state: bool = True):
            self.started.append(launch_key)
            return {"started": True, "launch_key": launch_key, "pid": 9000 + len(self.started)}

        def _persist_worker_state_items(self, items):
            self.persisted_items = [dict(item) for item in items]
            return self._worker_state_from_row(
                {
                    "state_key": "latest",
                    "updated_at": "2026-04-16T12:01:00+00:00",
                    "payload": self._worker_state_payload_from_items(self.persisted_items),
                }
            )

    repo = _Repo()

    payload = repo.bulk_worker_action("restart_all", launch_key="worker_ebay_item")

    assert payload["completed"] is True
    assert repo.terminated == ["worker-1", "worker-2"]
    assert repo.started == ["worker_ebay_item", "worker_ebay_item"]
    assert {item["launch_key"]: item["count"] for item in repo.persisted_items} == {
        "worker_ebay_item": 2,
        "worker_san": 1,
    }


def test_bulk_worker_scoped_restart_preserves_unrelated_saved_counts_during_registration_gap():
    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.started: list[str] = []
            self.terminated: list[str] = []
            self.persisted_items: list[dict[str, object]] = []
            self.saved_items = [
                {
                    "launch_key": "worker_ebay_item",
                    "label": "eBay items",
                    "source_key": "ebay",
                    "source_label": "eBay",
                    "count": 2,
                },
                {
                    "launch_key": "worker_ebay_no_image",
                    "label": "eBay no image",
                    "source_key": "ebay",
                    "source_label": "eBay",
                    "count": 3,
                },
                {
                    "launch_key": "worker_san_page",
                    "label": "SAN Page only",
                    "source_key": "san",
                    "source_label": "SAN",
                    "count": 7,
                },
            ]
            self.current_workers = [
                {
                    "worker_id": "worker-1",
                    "name": "eBay items",
                    "worker_template_name": "eBay items",
                    "launch_key": "worker_ebay_item",
                    "source_key": "ebay",
                    "source_label": "eBay",
                    "pid": 101,
                },
                {
                    "worker_id": "worker-2",
                    "name": "eBay no image",
                    "worker_template_name": "eBay no image",
                    "launch_key": "worker_ebay_no_image",
                    "source_key": "ebay",
                    "source_label": "eBay",
                    "pid": 102,
                },
                {
                    "worker_id": "worker-3",
                    "name": "eBay no image",
                    "worker_template_name": "eBay no image",
                    "launch_key": "worker_ebay_no_image",
                    "source_key": "ebay",
                    "source_label": "eBay",
                    "pid": 103,
                },
                {
                    "worker_id": "worker-4",
                    "name": "eBay no image",
                    "worker_template_name": "eBay no image",
                    "launch_key": "worker_ebay_no_image",
                    "source_key": "ebay",
                    "source_label": "eBay",
                    "pid": 104,
                },
            ]

        def _current_workers(self, *, only_working: bool = False):
            return list(self.current_workers)

        def _saved_worker_state(self, current_workers=None):
            return self._worker_state_from_row(
                {
                    "state_key": "latest",
                    "updated_at": "2026-04-16T12:01:00+00:00",
                    "payload": self._worker_state_payload_from_items(self.saved_items),
                }
            )

        def terminate_worker(self, worker_id: str, *, persist_state: bool = True):
            self.terminated.append(worker_id)
            return {"terminated": True, "worker_id": worker_id, "status": "terminating"}

        def start_worker(self, launch_key: str, *, persist_state: bool = True):
            self.started.append(launch_key)
            return {"started": True, "launch_key": launch_key, "pid": 9000 + len(self.started)}

        def _persist_worker_state_items(self, items):
            self.persisted_items = [dict(item) for item in items]
            return self._worker_state_from_row(
                {
                    "state_key": "latest",
                    "updated_at": "2026-04-16T12:02:00+00:00",
                    "payload": self._worker_state_payload_from_items(self.persisted_items),
                }
            )

    repo = _Repo()

    payload = repo.bulk_worker_action("restart_all", launch_key="worker_ebay_no_image")

    assert payload["completed"] is True
    assert repo.terminated == ["worker-2", "worker-3", "worker-4"]
    assert repo.started == ["worker_ebay_no_image", "worker_ebay_no_image", "worker_ebay_no_image"]
    assert {item["launch_key"]: item["count"] for item in repo.persisted_items} == {
        "worker_ebay_item": 2,
        "worker_ebay_no_image": 3,
        "worker_san_page": 7,
    }


def test_bulk_worker_stop_group_removes_group_from_desired_state():
    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.terminated: list[str] = []
            self.persisted_items: list[dict[str, object]] = []
            self.current_workers = [
                {
                    "worker_id": "worker-1",
                    "name": "eBay Item",
                    "worker_template_name": "eBay Item",
                    "launch_key": "worker_ebay_item",
                    "source_key": "ebay",
                    "source_label": "eBay",
                    "pid": 101,
                },
                {
                    "worker_id": "worker-2",
                    "name": "SAN",
                    "worker_template_name": "SAN",
                    "launch_key": "worker_san",
                    "source_key": "san",
                    "source_label": "SAN",
                    "pid": 102,
                },
            ]

        def _current_workers(self, *, only_working: bool = False):
            return list(self.current_workers)

        def _saved_worker_state(self, current_workers=None):
            return self._worker_state_from_row(
                {
                    "state_key": "latest",
                    "updated_at": "2026-04-16T12:00:00+00:00",
                    "payload": self._worker_state_payload_from_items(
                        self._worker_state_items_from_workers(current_workers or self.current_workers)
                    ),
                }
            )

        def terminate_worker(self, worker_id: str, *, persist_state: bool = True):
            self.terminated.append(worker_id)
            return {"terminated": True, "worker_id": worker_id, "status": "terminating"}

        def _persist_worker_state_items(self, items):
            self.persisted_items = [dict(item) for item in items]
            return self._worker_state_from_row(
                {
                    "state_key": "latest",
                    "updated_at": "2026-04-16T12:01:00+00:00",
                    "payload": self._worker_state_payload_from_items(self.persisted_items),
                }
            )

    repo = _Repo()

    payload = repo.bulk_worker_action("stop_all", launch_key="worker_ebay_item")

    assert payload["completed"] is True
    assert repo.terminated == ["worker-1"]
    assert {item["launch_key"]: item["count"] for item in repo.persisted_items} == {"worker_san": 1}


def test_restore_workers_api_uses_saved_state(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.post("/api/workers/restore")

    assert response.status_code == 200
    payload = response.json()
    assert payload["restored"] is True
    assert payload["started"][0]["launch_key"] == "worker_ebay_item"
    assert repo.restore_worker_calls == 1


def test_save_current_workers_api_updates_saved_state(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.post("/api/workers/save-current")

    assert response.status_code == 200
    payload = response.json()
    assert payload["saved"] is True
    assert payload["restore_plan"]["needs_restore"] is False
    assert payload["saved_state"]["total_count"] == 1
    assert repo.save_current_worker_calls == 1


def test_catalog_api_serializes_local_media_and_detail(tmp_path: Path):
    client, repo, image_path = build_client(tmp_path)

    response = client.get(
        "/api/catalog/items",
        params={
            "q": "bird",
            "issuer": "Japan",
            "catalog_code": "UPU-WNS",
            "year_from": 2020,
            "year_to": 2026,
            "property_in_catalog": "yes",
            "property_issuer": "Bird Archive",
            "property_watchlist": "watched",
            "sort": "issuer_asc",
            "view": "set",
            "local_only": "true",
            "page": 2,
            "page_size": 12,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["preview_image"] == f"/api/media?path={quote_plus(str(image_path))}"
    assert payload["items"][0]["has_local_image"] is True
    assert payload["items"][0]["entry_type"] == "set"
    assert payload["items"][0]["issue_date"] == "2024-01-01"
    assert payload["items"][0]["property_list"] == {"in_catalog": "unknown", "issuer": "", "watchlist": False}
    assert repo.catalog_calls[-1] == {
        "q": "bird",
        "issuer": "Japan",
        "catalog_code": "UPU-WNS",
        "year_from": 2020,
        "year_to": 2026,
        "property_in_catalog": "yes",
        "property_issuer": "Bird Archive",
        "property_watchlist": "watched",
        "sort": "issuer_asc",
        "view": "set",
        "local_only": True,
        "page": 2,
        "page_size": 12,
    }

    detail_response = client.get("/api/catalog/items/item-1")
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["catalog_entries"][0]["catalog_number"] == "JP001.2024"
    assert detail_payload["image_sources"][0]["kind"] == "local"

    set_detail_response = client.get("/api/catalog/sets/set:group-1")
    assert set_detail_response.status_code == 200
    set_payload = set_detail_response.json()
    assert set_payload["item_count"] == 3
    assert [source["kind"] for source in set_payload["image_sources"]] == ["local", "local", "remote"]
    assert [source["url"] for source in set_payload["image_sources"]] == [
        f"/api/media?path={quote_plus(str(repo.image_path))}",
        f"/api/media?path={quote_plus(str(repo.alt_image_path))}",
        "https://example.com/falcon.jpg",
    ]
    assert [source.get("item_uid") for source in set_payload["image_sources"]] == ["item-1", "item-2", "item-3"]


def test_catalog_colnect_missing_placeholder_is_not_local_image(tmp_path: Path):
    """Colnect no-image placeholders should not count as real gallery images."""
    media_root = tmp_path / "media"
    missing_path = media_root / "_shared" / "colnect-missing-image.jpg"
    missing_path.parent.mkdir(parents=True)
    missing_path.write_bytes(b"placeholder")

    payload = collectibles_app._serialize_catalog_item(
        {
            "item_id": 1,
            "item_uid": "colnect-stamp:123",
            "title": "No image stamp",
            "extra_attributes": {
                "image_url": "https://i.colnect.net/items/thumb/none-stamps.jpg",
                "image_local_path": str(missing_path),
            },
        },
        [media_root],
    )

    assert payload["image_sources"] == []
    assert payload["preview_image"] == ""
    assert payload["has_local_image"] is False


def test_catalog_colnect_number_kind_distinguishes_stamp_numbers_from_ids():
    """Colnect rows should display stamp numbers bare and source ids with a Colnect label."""
    assert (
        collectibles_app._catalog_number_kind(
            "COLNECT-STAMPS",
            "88",
            item_uid="colnect-stamp:424242",
            extra_attributes={"stamp_id": "424242"},
        )
        == "stamp-number"
    )
    assert (
        collectibles_app._catalog_number_kind(
            "COLNECT-STAMPS",
            "424242",
            item_uid="colnect-stamp:424242",
            extra_attributes={"stamp_id": "424242"},
        )
        == "colnect-id"
    )
    assert (
        collectibles_app._catalog_number_kind(
            "COLNECT-STAMPS",
            "Mi.PR267A",
            item_uid="colnect-stamp:867845",
            extra_attributes={"stamp_id": "867845"},
        )
        == ""
    )


def test_gallery_search_terms_support_partial_and_loose_matching():
    """Gallery search should split multi-word queries and allow broad typo tolerance."""
    assert collectibles_app._gallery_search_terms("United States 1868") == ["united", "states", "1868"]
    assert collectibles_app._gallery_loose_like_pattern("roosevlt") == "%r%o%o%s%e%v%l%t%"
    assert collectibles_app._gallery_loose_like_pattern("1868") == ""


def test_catalog_minor_variant_display_title_uses_original_name_and_traits():
    """Minor variant placeholders should render as the original name plus variant traits."""
    row = {
        "title": "Minor variant of #94864",
        "description": "Columbus Welcomed at Barcelona (United States of America (Columbian Exposition Issue))",
        "extra_attributes": {
            "colors": "Purple",
            "perforation": "line 12",
            "format": "Stamp",
            "stamp_id": "94864",
        },
    }

    assert collectibles_app._catalog_original_title(row) == "Columbus Welcomed at Barcelona"
    assert collectibles_app._catalog_variant_label(row) == "Purple, line 12"
    assert collectibles_app._catalog_display_title(row) == "Columbus Welcomed at Barcelona - Purple, line 12"


def test_catalog_query_uses_term_search_for_gallery_queries():
    """Catalog search should match separate terms across different searchable fields."""
    repo = CollectiblesRepository(dsn="postgresql://example.invalid/collectibles")

    _base_from, where_sql, params, _query = repo._catalog_query_parts(q="United 1868")

    assert "concat_ws" in where_sql
    assert "catalog_listings" in where_sql
    assert "%united 1868%" in params
    assert "%united%" in params
    assert "%1868%" in params
    assert "%u%n%i%t%e%d%" not in params

    _base_from, _where_sql, fuzzy_params, _query = repo._catalog_query_parts(q="roosevlt")
    assert "%r%o%o%s%e%v%l%t%" in fuzzy_params


def test_catalog_local_only_sql_excludes_colnect_missing_placeholder():
    """The local-only catalog filter should require a real local image."""
    repo = CollectiblesRepository(dsn="postgresql://example.invalid/collectibles")

    _base_from, where_sql, _params, _query = repo._catalog_query_parts(local_only=True)

    assert "image_local_path" in where_sql
    assert "no_image" in where_sql
    assert "colnect-missing-image.jpg" in where_sql
    assert "https://i.colnect.net/items/full/none-stamps.jpg" in where_sql
    assert "https://i.colnect.net/items/thumb/none-stamps.jpg" in where_sql
    assert "https://i.colnect.net/colnect_sm.png" in where_sql


def test_catalog_api_defaults_to_updated_sort(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.get("/api/catalog/items")

    assert response.status_code == 200
    assert repo.catalog_calls[-1]["sort"] == "updated_desc"
    assert response.json()["filters"]["sort"] == "updated_desc"


def test_sales_api_forwards_filters_and_404s_missing_detail(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.get(
        "/api/sales/listings",
        params={
            "q": "blue",
            "provider": "ebay",
            "auction_id": "auction-1",
            "listing_status": "active",
            "sale_type": "fixed_price",
            "subcategory": "United States",
            "property_in_catalog": "unknown",
            "property_issuer": "Bird House",
            "property_watchlist": "watched",
            "sort": "price_desc",
            "local_only": "true",
            "page_size": 8,
        },
    )
    assert response.status_code == 200
    assert response.json()["items"][0]["price_label"] == "$ 10.00"
    assert response.json()["items"][0]["subcategory_names"] == ["United States"]
    assert response.json()["items"][0]["seller_label"] == "seller-1(6,837)"
    assert response.json()["items"][0]["auction_title"] == "Bluebird Spring Sale"
    assert response.json()["items"][0]["end_at"] == "2026-04-12T17:45:00"
    assert response.json()["items"][0]["property_list"] == {"in_catalog": "unknown", "issuer": "", "watchlist": False}
    assert response.json()["items"][0]["payload"] == {
        "item_summary": {
            "categories": [
                {"categoryId": "260", "categoryName": "Stamps"},
                {"categoryId": "261", "categoryName": "United States"},
            ],
            "itemOriginDate": "2026-04-09T11:12:13.000Z",
            "shippingOptions": [
                {
                    "shippingCost": {"value": "4.5", "currency": "USD"},
                    "shippingCostType": "FIXED",
                    "minEstimatedDeliveryDate": "2026-04-12T07:00:00.000Z",
                    "maxEstimatedDeliveryDate": "2026-04-14T07:00:00.000Z",
                }
            ],
        },
        "item_detail": {
            "description": "<p>Fresh gum and sharp centering.</p>",
        },
    }
    assert repo.sales_calls[-1] == {
        "q": "blue",
        "provider": "ebay",
        "auction_id": "auction-1",
        "listing_status": "active",
        "sale_type": "fixed_price",
        "subcategory": "United States",
        "property_in_catalog": "unknown",
        "property_issuer": "Bird House",
        "property_watchlist": "watched",
        "sort": "price_desc",
        "local_only": True,
        "page": 1,
        "page_size": 8,
    }

    missing = client.get("/api/sales/listings/missing")
    assert missing.status_code == 404


def test_sales_refresh_api_queues_high_priority_listing_job(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.post("/api/sales/listings/sale-1/refresh")

    assert response.status_code == 200
    assert response.json() == {
        "queued": True,
        "job_id": "dispatcher-job:ebay-active-stamps-listing:123",
        "existing_status": "",
        "listing_uid": "sale-1",
        "priority": SALES_LISTING_REFRESH_PRIORITY,
        "capability": "ebay active stamps listing",
    }
    assert repo.refresh_calls[-1] == {
        "listing_uid": "sale-1",
        "priority": SALES_LISTING_REFRESH_PRIORITY,
    }

    missing = client.post("/api/sales/listings/missing/refresh")
    assert missing.status_code == 404


def test_property_bulk_save_api_forwards_checked_records(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.post(
        "/api/property-lists/bulk",
        json={
            "records": [
                {"mode": "sales", "id": "sale-1"},
                {"mode": "catalog", "id": "item-1"},
            ],
            "property_key": "issuer",
            "property_value": "Bird Archive",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "updated_count": 2,
        "property_key": "issuer",
        "property_value": "Bird Archive",
    }
    assert repo.property_save_calls[-1] == {
        "records": [
            {"mode": "sales", "id": "sale-1"},
            {"mode": "catalog", "id": "item-1"},
        ],
        "property_key": "issuer",
        "property_value": "Bird Archive",
    }


def test_property_bulk_save_api_accepts_watchlist_boolean(tmp_path: Path):
    client, repo, _ = build_client(tmp_path)

    response = client.post(
        "/api/property-lists/bulk",
        json={
            "records": [{"mode": "sales", "id": "sale-1"}],
            "property_key": "watchlist",
            "property_value": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "updated_count": 1,
        "property_key": "watchlist",
        "property_value": True,
    }
    assert repo.property_save_calls[-1] == {
        "records": [{"mode": "sales", "id": "sale-1"}],
        "property_key": "watchlist",
        "property_value": True,
    }


def test_catalog_query_parts_partial_matches_issuer():
    repo = CollectiblesRepository(dsn="postgresql://localhost/collectibles?sslmode=disable")
    _, where_sql, params, _ = repo._catalog_query_parts(issuer="Chi")
    assert "regexp_split_to_array(lower(coalesce(iss.issuer_name, '')), '[^a-z0-9]+')" in where_sql
    assert "chi%" in params


def test_dashboard_snapshot_due_check_accepts_recent_iso_string_without_inserting(monkeypatch):
    fixed_now = datetime(2026, 4, 14, 1, 0, 30, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(collectibles_app, "datetime", _FixedDateTime)

    class _Repo(CollectiblesRepository):
        def _ensure_dashboard_snapshot_table(self) -> None:
            return

        def _fetchone(self, sql: str, params=None):
            return {
                "captured_at": datetime(2026, 4, 14, 1, 0, 10, tzinfo=timezone.utc).isoformat(),
                "payload": {
                    "sources": [{"key": "colnect", "label": "Colnect", "imported_records": 12}],
                    "workers": {"current_count": 3},
                },
            }

        def _connect(self):
            raise AssertionError("snapshot insert should not run when the latest row is still within the interval")

    repo = _Repo(dsn="postgresql://localhost/collectibles?sslmode=disable")

    snapshot = repo._capture_dashboard_snapshot_if_due({"sources": [], "workers": {}})

    assert snapshot["sources"][0]["key"] == "colnect"
    assert snapshot["workers"]["current_count"] == 3


def test_dashboard_snapshot_due_check_captures_new_minute_bucket():
    class _Repo(CollectiblesRepository):
        def _ensure_dashboard_snapshot_table(self) -> None:
            return

        def _fetchone(self, sql: str, params=None):
            return {
                "captured_at": "2026-04-14T01:13:04.955533+08:00",
                "payload": {
                    "sources": [{"key": "colnect", "label": "Colnect", "imported_records": 12}],
                    "workers": {"current_count": 3},
                },
            }

        def _insert_dashboard_snapshot(self, payload):
            self.inserted_payload = payload
            return {
                "captured_at": "2026-04-14T01:14:04.689173+08:00",
                "sources": payload["sources"],
                "workers": payload["workers"],
            }

    repo = _Repo(dsn="postgresql://localhost/collectibles?sslmode=disable")
    snapshot = repo._capture_dashboard_snapshot_if_due(
        {
            "sources": [{"key": "colnect", "label": "Colnect", "page_jobs": {"queued": 1900, "working": 0, "pending": 1900}}],
            "workers": {"current_count": 4},
        }
    )

    assert repo.inserted_payload["sources"][0]["page_jobs"] == {"queued": 1900, "working": 0, "pending": 1900}
    assert snapshot["sources"][0]["page_jobs"] == {"queued": 1900, "working": 0, "pending": 1900}


def test_capture_dashboard_snapshot_uses_live_payload_and_due_check():
    class _Repo(CollectiblesRepository):
        def __init__(self):
            super().__init__(dsn="postgresql://localhost/collectibles?sslmode=disable")
            self.seen_payload = None

        def _dashboard_snapshot_payload(self) -> dict[str, object]:
            return {
                "sources": [{
                    "key": "colnect",
                    "label": "Colnect",
                    "imported_records": 12,
                    "page_jobs": {"queued": 1900, "working": 0, "pending": 1900},
                }],
                "workers": {"current_count": 3},
            }

        def _capture_dashboard_snapshot_if_due(self, current_payload):
            self.seen_payload = current_payload
            return {
                "captured_at": "2026-04-14T01:00:00+00:00",
                "sources": current_payload["sources"],
                "workers": current_payload["workers"],
            }

    repo = _Repo()

    snapshot = repo.capture_dashboard_snapshot()

    assert repo.seen_payload == {
        "sources": [{
            "key": "colnect",
            "label": "Colnect",
            "imported_records": 12,
            "page_jobs": {"queued": 1900, "working": 0, "pending": 1900},
        }],
        "workers": {"current_count": 3},
    }
    assert snapshot["captured_at"] == "2026-04-14T01:00:00+00:00"


def test_get_dashboard_uses_latest_snapshot_as_current_and_previous_snapshot_for_delta_base():
    class _Repo(CollectiblesRepository):
        def _ensure_dashboard_snapshot_table(self) -> None:
            return

        def _current_workers(self, *, only_working: bool = False):
            return [{"worker_id": "worker-1", "status": "working"}]

        def _dashboard_snapshot_payload(self, current_workers=None) -> dict[str, object]:
            return {
                "sources": [{"key": "colnect", "label": "Colnect", "imported_records": 99}],
                "workers": {"current_count": 9, "working_count": 7, "idle_count": 2, "active_job_count": 7},
            }

        def _capture_dashboard_snapshot_if_due(self, current_payload):
            return {
                "captured_at": "2026-04-14T01:01:00+00:00",
                "sources": current_payload.get("sources", []),
                "workers": current_payload.get("workers", {}),
            }

        def _dashboard_snapshot_rows(self, limit: int):
            return [
                {
                    "captured_at": "2026-04-14T01:00:00+00:00",
                    "payload": {
                        "sources": [{"key": "colnect", "label": "Colnect", "imported_records": 12}],
                        "workers": {"current_count": 6, "working_count": 4, "idle_count": 2, "active_job_count": 4},
                    },
                },
                {
                    "captured_at": "2026-04-14T00:59:00+00:00",
                    "payload": {
                        "sources": [{"key": "colnect", "label": "Colnect", "imported_records": 10}],
                        "workers": {"current_count": 5, "working_count": 3, "idle_count": 2, "active_job_count": 3},
                    },
                },
            ][:limit]

        def _dashboard_working_workers(self):
            return [{"worker_id": "worker-1"}]

        def _dashboard_ebay_schedule_status(self):
            return {
                "schedule_id": "dispatcher-boss-schedule:ebay-daily",
                "status": "scheduled",
                "scheduled_for": "2026-04-14T01:08:00+00:00",
                "issued_at": "2026-04-14T00:58:00+00:00",
                "schedule_interval_minutes": 10,
                "dispatcher_job_id": "dispatcher-job:ebay-daily-1",
                "job_status": "claimed",
                "job_claimed_by": "dispatcher-worker:ebay-1",
                "job_claimed_at": "2026-04-14T00:58:02+00:00",
                "job_worker_name": "CollectiblesWorker eBay only",
            }

        def _dashboard_archive_schedule_status(self):
            return {
                "schedule_id": "dispatcher-boss-schedule:collectibles-daily-job-archive",
                "status": "scheduled",
                "scheduled_for": "2026-04-15T03:00:00+00:00",
                "issued_at": "2026-04-14T03:00:00+00:00",
                "dispatcher_job_id": "dispatcher-job:archive-1",
                "job_status": "completed",
            }

        def _dashboard_monthly_archive_schedule_status(self):
            return {
                "schedule_id": "dispatcher-boss-schedule:collectibles-monthly-archive-cleanup",
                "status": "scheduled",
                "scheduled_for": "2026-05-01T04:00:00+08:00",
                "dispatcher_job_id": "",
                "job_status": "",
            }

        def _dashboard_monthly_archive_history(self, *, limit: int = 5):
            return [
                {
                    "job_id": "dispatcher-job:monthly-cleanup-1",
                    "status": "completed",
                    "archived_rows": 12,
                    "purged_rows": 9,
                }
            ][:limit]

        def _dashboard_ebay_daily_reports(self, limit: int = 3):
            return [
                {
                    "report_date": "2026-04-14T00:58:00+00:00",
                    "status": "completed_with_errors",
                    "fan_out_pages": 1,
                    "queued_listing_jobs": 41,
                    "planned_status_jobs": 1,
                    "planned_page_jobs": 1,
                    "planned_retrieval_items": 60,
                    "updated_items": 12,
                    "retrieved_items": 41,
                    "error_count": 2,
                    "total_jobs": 2,
                    "completed_jobs": 1,
                    "failed_jobs": 1,
                    "active_jobs": 0,
                    "updated_at": "2026-04-14T00:59:00+00:00",
                }
            ][:limit]

        def _dashboard_rate_limit_locks(self):
            return [
                {
                    "source_key": "colnect",
                    "label": "Colnect",
                    "active": True,
                    "started_at": "2026-04-14T00:57:00+00:00",
                    "hold_until": "2026-04-14T01:12:00+00:00",
                    "updated_at": "2026-04-14T00:57:00+00:00",
                    "reason": "HTTP 429",
                }
            ]

    repo = _Repo(dsn="postgresql://localhost/collectibles?sslmode=disable")

    payload = repo.get_dashboard(history_limit=12, live=True)

    assert payload["snapshot_interval_minutes"] == 1
    assert payload["current"]["captured_at"]
    assert payload["current"]["sources"][0]["imported_records"] == 99
    assert payload["latest_snapshot"]["captured_at"] == "2026-04-14T01:01:00+00:00"
    assert payload["latest_snapshot"]["sources"][0]["imported_records"] == 99
    assert payload["delta_base_snapshot"]["captured_at"] == "2026-04-14T01:00:00+00:00"
    assert payload["delta_base_snapshot"]["sources"][0]["imported_records"] == 12
    assert payload["history"][1]["captured_at"] == "2026-04-14T00:59:00+00:00"
    assert payload["history"][1]["sources"][0]["imported_records"] == 10
    assert payload["ebay_daily_schedule"]["job_status"] == "claimed"
    assert payload["daily_archive_schedule"]["job_status"] == "completed"
    assert payload["monthly_archive_schedule"]["status"] == "scheduled"
    assert payload["monthly_archive_history"][0]["purged_rows"] == 9
    assert payload["rate_limit_locks"][0]["source_key"] == "colnect"
    assert payload["ebay_daily_reports"][0]["queued_listing_jobs"] == 41
    assert payload["ebay_daily_reports"][0]["error_count"] == 2
    assert payload["workers"]["current_count"] == 9
    assert payload["workers"]["items"] == [{"worker_id": "worker-1", "status": "working"}]


def test_get_dashboard_reads_existing_snapshots_with_live_schedule_payloads():
    class _Repo(CollectiblesRepository):
        def _current_workers(self, *, only_working: bool = False):
            return [{"worker_id": "worker-1", "status": "working"}]

        def _dashboard_snapshot_payload(self, current_workers=None) -> dict[str, object]:
            return {
                "sources": [{"key": "colnect", "label": "Colnect", "imported_records": 14}],
                "workers": {"current_count": 7, "working_count": 5, "idle_count": 2, "active_job_count": 5},
            }

        def _dashboard_snapshot_rows(self, limit: int):
            return [
                {
                    "captured_at": "2026-04-14T01:00:00+00:00",
                    "payload": {
                        "sources": [{"key": "colnect", "label": "Colnect", "imported_records": 12}],
                        "workers": {"current_count": 6, "working_count": 4, "idle_count": 2, "active_job_count": 4},
                    },
                }
            ][:limit]

        def _capture_dashboard_snapshot_if_due(self, current_payload):
            return {
                "captured_at": "2026-04-14T01:01:00+00:00",
                "sources": current_payload.get("sources", []),
                "workers": current_payload.get("workers", {}),
            }

        def _dashboard_working_workers(self):
            return [{"worker_id": "worker-1"}]

        def _dashboard_ebay_schedule_status(self):
            return {
                "schedule_id": "dispatcher-boss-schedule:ebay-daily",
                "status": "scheduled",
                "scheduled_for": "2026-04-14T01:10:00+00:00",
                "issued_at": "2026-04-14T01:00:00+00:00",
                "schedule_interval_minutes": 10,
                "dispatcher_job_id": "dispatcher-job:ebay-daily-1",
                "job_status": "completed",
                "job_worker_name": "CollectiblesWorker eBay only",
            }

        def _dashboard_archive_schedule_status(self):
            return {
                "schedule_id": "dispatcher-boss-schedule:collectibles-daily-job-archive",
                "status": "scheduled",
                "scheduled_for": "2026-04-15T03:00:00+00:00",
                "issued_at": "2026-04-14T03:00:00+00:00",
                "dispatcher_job_id": "dispatcher-job:archive-1",
                "job_status": "completed",
            }

        def _dashboard_monthly_archive_schedule_status(self):
            return {
                "schedule_id": "dispatcher-boss-schedule:collectibles-monthly-archive-cleanup",
                "status": "scheduled",
                "scheduled_for": "2026-05-01T04:00:00+08:00",
                "dispatcher_job_id": "",
                "job_status": "",
            }

        def _dashboard_monthly_archive_history(self, *, limit: int = 5):
            return []

        def _dashboard_ebay_daily_reports(self, limit: int = 3):
            return [
                {
                    "report_date": "2026-04-14T01:00:00+00:00",
                    "status": "finished",
                    "fan_out_pages": 0,
                    "queued_listing_jobs": 0,
                    "planned_status_jobs": 0,
                    "planned_page_jobs": 0,
                    "planned_retrieval_items": 0,
                    "updated_items": 0,
                    "retrieved_items": 0,
                    "error_count": 0,
                    "total_jobs": 0,
                    "completed_jobs": 0,
                    "failed_jobs": 0,
                    "active_jobs": 0,
                    "updated_at": "2026-04-14T01:00:00+00:00",
                }
            ][:limit]

        def _dashboard_rate_limit_locks(self):
            return [
                {
                    "source_key": "ebay",
                    "label": "eBay",
                    "active": False,
                    "started_at": "",
                    "hold_until": "",
                    "updated_at": "2026-04-14T00:58:00+00:00",
                    "reason": "",
                }
            ]

    repo = _Repo(dsn="postgresql://localhost/collectibles?sslmode=disable")

    payload = repo.get_dashboard(history_limit=12, live=True)

    assert payload["current"]["captured_at"]
    assert payload["current"]["sources"][0]["imported_records"] == 14
    assert payload["latest_snapshot"]["captured_at"] == "2026-04-14T01:01:00+00:00"
    assert payload["delta_base_snapshot"]["captured_at"] == "2026-04-14T01:00:00+00:00"
    assert payload["delta_base_snapshot"]["sources"][0]["imported_records"] == 12
    assert payload["ebay_daily_schedule"]["status"] == "scheduled"
    assert payload["daily_archive_schedule"]["status"] == "scheduled"
    assert payload["monthly_archive_schedule"]["status"] == "scheduled"
    assert payload["monthly_archive_history"] == []
    assert payload["rate_limit_locks"][0]["active"] is False
    assert payload["ebay_daily_reports"][0]["status"] == "finished"
    assert payload["workers"]["items"] == [{"worker_id": "worker-1", "status": "working"}]


def test_dashboard_rate_limit_locks_keep_runtime_active_rows_on_even_if_hold_until_has_passed():
    class _Repo(CollectiblesRepository):
        def _fetchone(self, sql: str, params=None):
            normalized_sql = " ".join(str(sql).split()).lower()
            if f"from public.{collectibles_app.TABLE_COLNECT_RUNTIME}".lower() in normalized_sql:
                return {
                    "id": "global-rate-limit",
                    "scope": "global-rate-limit",
                    "hold_until": "2026-04-14T01:10:00+00:00",
                    "updated_at": "2026-04-14T01:11:00+00:00",
                    "metadata": {
                        "active": True,
                        "held_at": "2026-04-14T01:00:00+00:00",
                        "last_error": "status 429",
                    },
                }
            if f"from public.{collectibles_app.TABLE_EBAY_ACTIVE_RUNTIME}".lower() in normalized_sql:
                return {
                    "id": "api-rate-limit",
                    "scope": "browse-api-rate-limit",
                    "hold_until": "2026-04-14T01:12:00+00:00",
                    "updated_at": "2026-04-14T01:12:30+00:00",
                    "metadata": {
                        "active": True,
                        "held_at": "2026-04-14T01:02:00+00:00",
                        "last_error": "status 429",
                    },
                    }
                return {}

        def _fetchall(self, sql: str, params=None):
            normalized_sql = " ".join(str(sql).split()).lower()
            if f"from public.{collectibles_app.TABLE_EBAY_ACTIVE_DAILY_REPORTS}".lower() in normalized_sql:
                return []
            return []

    repo = _Repo(dsn="postgresql://localhost/collectibles?sslmode=disable")

    locks = repo._dashboard_rate_limit_locks()

    assert locks[0]["source_key"] == "colnect"
    assert locks[0]["active"] is True
    assert locks[0]["started_at"] == "2026-04-14T01:00:00+00:00"
    assert locks[0]["hold_until"] == ""
    assert locks[1]["source_key"] == "ebay"
    assert locks[1]["active"] is True
    assert locks[1]["started_at"] == "2026-04-14T01:02:00+00:00"
    assert locks[1]["hold_until"] == ""


def test_dashboard_rate_limit_locks_use_oldest_consecutive_ebay_rate_limited_report_as_start():
    class _Repo(CollectiblesRepository):
        def _fetchone(self, sql: str, params=None):
            normalized_sql = " ".join(str(sql).split()).lower()
            if f"from public.{collectibles_app.TABLE_EBAY_ACTIVE_RUNTIME}".lower() in normalized_sql:
                return {
                    "id": "api-rate-limit",
                    "scope": "browse-api-rate-limit",
                    "hold_until": "2026-04-14T02:20:00+00:00",
                    "updated_at": "2026-04-14T02:18:00+00:00",
                    "metadata": {
                        "active": True,
                        "held_at": "2026-04-14T02:18:00+00:00",
                        "last_error": "status 429",
                    },
                }
            if f"from public.{collectibles_app.TABLE_COLNECT_RUNTIME}".lower() in normalized_sql:
                return {}
            return {}

        def _fetchall(self, sql: str, params=None):
            normalized_sql = " ".join(str(sql).split()).lower()
            if f"from public.{collectibles_app.TABLE_EBAY_ACTIVE_DAILY_REPORTS}".lower() in normalized_sql:
                return [
                    {"report_date": "2026-04-14T02:10:00+00:00", "status": "rate_limited"},
                    {"report_date": "2026-04-14T02:00:00+00:00", "status": "rate_limited"},
                    {"report_date": "2026-04-14T01:50:00+00:00", "status": "finished"},
                ]
            return []

    repo = _Repo(dsn="postgresql://localhost/collectibles?sslmode=disable")

    locks = repo._dashboard_rate_limit_locks()

    assert locks[1]["source_key"] == "ebay"
    assert locks[1]["active"] is True
    assert locks[1]["started_at"] == "2026-04-14T02:00:00+00:00"


def test_dashboard_sources_snapshot_counts_colnect_country_and_year_as_page():
    class _Repo(CollectiblesRepository):
        def _fetchone(self, sql: str, params=None):
            normalized_sql = " ".join(str(sql).split())
            if "from catalog_listings cl" in normalized_sql:
                return {
                    "imported_records": 12,
                    "downloaded_images": 9,
                }
            if "from public.sales_listings" in normalized_sql:
                return {
                    "ebay_imported_records": 8,
                    "ebay_downloaded_images": 15,
                    "san_imported_records": 5,
                    "san_downloaded_images": 7,
                }
            raise AssertionError(f"unexpected sql: {sql}")

        def _dashboard_job_count_map(self, capability_groups, live_worker_ids=None):
            counts = {
                ("Colnect Stamp Country", "Colnect Stamp Year", "Colnect Stamp Page"): {"queued": 6, "working": 2, "pending": 8},
                ("Colnect Stamp Listing",): {"queued": 3, "working": 1, "pending": 4},
                ("Colnect Stamp Image",): {"queued": 2, "working": 0, "pending": 2},
                ("eBay Active Stamps Page",): {"queued": 2, "working": 1, "pending": 3},
                ("eBay Active Stamps Listing",): {"queued": 5, "working": 2, "pending": 7},
                ("eBay Active Stamps Image",): {"queued": 1, "working": 1, "pending": 2},
                ("StampAuctionNetwork Page",): {"queued": 3, "working": 0, "pending": 3},
                ("StampAuctionNetwork Listing",): {"queued": 0, "working": 0, "pending": 0},
                ("StampAuctionNetwork Image",): {"queued": 4, "working": 1, "pending": 5},
            }
            return {key: counts[tuple(capabilities)] for key, capabilities in capability_groups.items()}

    repo = _Repo(dsn="postgresql://localhost/collectibles?sslmode=disable")

    payload = repo._dashboard_sources_snapshot()

    assert payload[0]["key"] == "colnect"
    assert payload[0]["page_jobs"] == {"queued": 6, "working": 2, "pending": 8}
    assert payload[1]["page_jobs"] == {"queued": 2, "working": 1, "pending": 3}


def test_catalog_group_identity_expr_prefers_series_id():
    expr = CollectiblesRepository._catalog_group_identity_expr("i")
    assert "'series:' || nullif(i.extra_attributes ->> 'series_id', '')" in expr
    assert "'topic:'" in expr
    assert "issue_date::text" not in expr


def test_sales_sort_clause_supports_recent_update():
    newest = CollectiblesRepository._sales_sort_clause("newest")
    oldest = CollectiblesRepository._sales_sort_clause("oldest")
    recent_update = CollectiblesRepository._sales_sort_clause("recent_update")

    assert newest.startswith("created_at desc nulls last")
    assert oldest.startswith("created_at asc nulls last")
    assert recent_update.startswith("updated_at desc nulls last")


def test_sales_order_clauses_skip_local_image_boost_for_recent_update():
    newest = CollectiblesRepository._sales_order_clauses("newest")
    recent_update = CollectiblesRepository._sales_order_clauses("recent_update")

    assert "jsonb_typeof(sl.image_local_paths) = 'array'" in newest[0]
    assert newest[1].startswith("created_at desc nulls last")
    assert recent_update == [CollectiblesRepository._sales_sort_clause("recent_update")]


def test_catalog_effective_series_id_expr_infers_from_matching_rows():
    expr = CollectiblesRepository._catalog_effective_series_id_expr("fb")
    assert "max(fb.series_id) filter (where fb.series_id is not null)" in expr
    assert "partition by fb.issuer_name, fb.issue_year, fb.group_topic" in expr


def test_catalog_set_member_order_clause_prioritizes_format_then_catalog_number():
    clause = CollectiblesRepository._catalog_set_member_order_clause("f", "f.sort_catalog_number")
    assert "strpos(lower(coalesce(f.extra_attributes ->> 'format', '')), 'se-tenant') > 0" in clause
    assert "strpos(lower(coalesce(f.extra_attributes ->> 'format', '')), 'stamp') > 0" in clause
    assert "strpos(lower(coalesce(f.extra_attributes ->> 'format', '')), 'booklet') > 0" in clause
    assert "regexp_replace(coalesce(f.sort_catalog_number, ''), '[^0-9]+', '', 'g')" in clause


def test_serialize_sales_listing_prefers_payload_seller_display_name(tmp_path: Path):
    row = {
        "listing_uid": "sale-display-name",
        "provider": "ebay",
        "marketplace_site": "EBAY_US",
        "source_category_id": "260",
        "source_query": "horse stamp",
        "listing_status": "active",
        "sale_type": "FIXED_PRICE",
        "title": "Horse Stamp",
        "subtitle": "",
        "listing_url": "https://example.com/horse",
        "search_page": 1,
        "listing_position": 1,
        "sold_at": "",
        "price_amount": "7.5",
        "price_currency": "USD",
        "shipping_amount": "",
        "shipping_currency": "",
        "total_amount": "7.5",
        "condition_text": "MNH",
        "seller_name": "3BCJqe8MRE2",
        "location_text": "Tokyo",
        "image_url": "",
        "image_urls": [],
        "image_local_paths": [],
        "source_url": "https://example.com/source/horse",
        "payload": {
            "item_summary": {
                "seller": {
                    "displayName": "Bluebird Stamps",
                    "username": "3BCJqe8MRE2",
                    "feedbackScore": 17728,
                }
            }
        },
        "created_at": "2026-04-10T11:00:00+00:00",
        "updated_at": "2026-04-10T12:00:00+00:00",
    }

    payload = _serialize_sales_listing(row, media_roots=[tmp_path])

    assert payload["seller_name"] == "Bluebird Stamps"
    assert payload["seller_label"] == "Bluebird Stamps(17,728)"


def test_serialize_sales_listing_prefers_page_seller_name(tmp_path: Path):
    row = {
        "listing_uid": "sale-page-seller-name",
        "provider": "ebay",
        "marketplace_site": "EBAY_US",
        "source_category_id": "260",
        "source_query": "horse stamp",
        "listing_status": "active",
        "sale_type": "FIXED_PRICE",
        "title": "Horse Stamp",
        "subtitle": "",
        "listing_url": "https://example.com/horse",
        "search_page": 1,
        "listing_position": 1,
        "sold_at": "",
        "price_amount": "7.5",
        "price_currency": "USD",
        "shipping_amount": "",
        "shipping_currency": "",
        "total_amount": "7.5",
        "condition_text": "MNH",
        "seller_name": "p1QEhNdAQZW",
        "location_text": "Tokyo",
        "image_url": "",
        "image_urls": [],
        "image_local_paths": [],
        "source_url": "https://example.com/source/horse",
        "payload": {
            "page_seller_name": "gsquared7",
            "item_summary": {
                "seller": {
                    "username": "p1QEhNdAQZW",
                    "feedbackScore": 17728,
                }
            }
        },
        "created_at": "2026-04-10T11:00:00+00:00",
        "updated_at": "2026-04-10T12:00:00+00:00",
    }

    payload = _serialize_sales_listing(row, media_roots=[tmp_path])

    assert payload["seller_name"] == "gsquared7"
    assert payload["seller_label"] == "gsquared7(17,728)"


def test_serialize_sales_listing_includes_ebay_bid_count_for_auction(tmp_path: Path):
    row = {
        "listing_uid": "sale-auction-bids",
        "provider": "ebay",
        "marketplace_site": "EBAY_US",
        "source_category_id": "260",
        "source_query": "auction stamp",
        "listing_status": "active",
        "sale_type": "AUCTION",
        "title": "Auction Stamp",
        "subtitle": "",
        "listing_url": "https://example.com/auction-stamp",
        "search_page": 1,
        "listing_position": 1,
        "sold_at": "",
        "price_amount": "42.5",
        "price_currency": "USD",
        "shipping_amount": "",
        "shipping_currency": "",
        "total_amount": "42.5",
        "condition_text": "MNH",
        "seller_name": "seller-1",
        "location_text": "Tokyo",
        "image_url": "",
        "image_urls": [],
        "image_local_paths": [],
        "source_url": "https://example.com/source/auction-stamp",
        "payload": {
            "item_summary": {
                "bidCount": 14,
                "seller": {
                    "feedbackScore": 17728,
                },
            }
        },
        "created_at": "2026-04-10T11:00:00+00:00",
        "updated_at": "2026-04-10T12:00:00+00:00",
    }

    payload = _serialize_sales_listing(row, media_roots=[tmp_path])

    assert payload["bid_count"] == 14
    assert payload["payload"]["item_summary"]["bidCount"] == 14


def test_build_sales_listing_refresh_job_prefers_ebay_active_listing_worker():
    row = {
        "listing_uid": "sale-1",
        "provider": "ebay",
        "source_listing_id": "123",
        "source_query": "blue bird stamp",
        "source_category_id": "260",
        "listing_status": "active",
        "sale_type": "FIXED_PRICE",
        "title": "Blue Bird Stamp Block",
        "subtitle": "",
        "listing_url": "https://example.com/sale-1",
        "search_page": 1,
        "listing_position": 4,
        "price_amount": "10",
        "price_currency": "USD",
        "shipping_amount": "",
        "shipping_currency": "",
        "total_amount": "10",
        "condition_text": "MNH",
        "seller_name": "seller-1",
        "location_text": "Tokyo",
        "image_url": "https://example.com/sale-1.jpg",
        "image_urls": ["https://example.com/sale-1.jpg"],
        "source_url": "https://example.com/source/sale-1",
        "payload": {
            "item_id": "v1|123|0",
            "api_mode": "browse",
            "item_summary": {
                "itemOriginDate": "2026-04-09T11:12:13.000Z",
                "itemEndDate": "2026-04-12T17:45:00.000Z",
                "seller": {
                    "feedbackScore": 6837,
                    "feedbackPercentage": 99.8,
                },
            },
        },
    }

    spec = _build_sales_listing_refresh_job(row)
    job = spec["job"]

    assert spec["metadata_key"] == "ebay_active_stamp"
    assert spec["logical_job_key"] == "listing:123"
    assert job.required_capability == "ebay active stamps listing"
    assert job.priority == SALES_LISTING_REFRESH_PRIORITY
    assert job.payload["refresh_item"] is True
    assert job.payload["item_id"] == "v1|123|0"
    assert job.payload["seller_feedback_score"] == 6837


def test_build_sales_listing_refresh_job_supports_stamp_auction_network():
    row = {
        "listing_uid": "stampauctionnetwork:za-420-2442",
        "provider": "stampauctionnetwork",
        "source_listing_id": "ZA-420-2442",
        "auctioneer_id": "stampauctionnetwork:auctioneer:za",
        "auction_id": "stampauctionnetwork:auction:za-420",
        "auction_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
        "lot_number": "2442",
        "source_query": "Auction",
        "listing_status": "active",
        "sale_type": "AUCTION",
        "title": "Sweden lot",
        "subtitle": "",
        "listing_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm#25",
        "search_page": 25,
        "listing_position": 1,
        "price_amount": "42",
        "price_currency": "USD",
        "estimate_amount": "65",
        "estimate_currency": "USD",
        "hammer_price_amount": "",
        "hammer_price_currency": "",
        "seller_name": "AB Philea",
        "image_url": "https://stampauctionnetwork.com/assets/za420/2442-1.jpg",
        "image_urls": ["https://stampauctionnetwork.com/assets/za420/2442-1.jpg"],
        "source_url": "https://stampauctionnetwork.com/ZA/za42024.cfm",
        "payload": {
            "firm_code": "ZA",
            "sale_number": "420",
            "source_auction_id": "ZA-420",
            "auction_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm",
            "detail_url": "https://stampauctionnetwork.com/ZA/za42024.cfm",
            "catalog_text": "Sweden lot",
            "page_title": "Sweden",
            "page_label": "Unused collections",
            "raw_block_text": "Lot 2442",
            "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
        },
    }

    spec = _build_sales_listing_refresh_job(row)
    job = spec["job"]

    assert spec["metadata_key"] == "stamp_auction_network"
    assert spec["logical_job_key"] == "listing:za-420-2442"
    assert job.required_capability == "stampauctionnetwork listing"
    assert job.priority == SALES_LISTING_REFRESH_PRIORITY
    assert job.payload["refresh_item"] is True
    assert job.payload["sale_number"] == "420"
    assert job.payload["auction_url"] == "https://stampauctionnetwork.com/ZA/ZA420.cfm"


def test_serialize_sales_listing_keeps_ebay_username_when_no_better_seller_name_exists(tmp_path: Path):
    row = {
        "listing_uid": "sale-hidden-seller",
        "provider": "ebay",
        "marketplace_site": "EBAY_US",
        "source_category_id": "260",
        "source_query": "horse stamp",
        "listing_status": "active",
        "sale_type": "FIXED_PRICE",
        "title": "Horse Stamp",
        "subtitle": "",
        "listing_url": "https://example.com/horse",
        "search_page": 1,
        "listing_position": 1,
        "sold_at": "",
        "price_amount": "7.5",
        "price_currency": "USD",
        "shipping_amount": "",
        "shipping_currency": "",
        "total_amount": "7.5",
        "condition_text": "MNH",
        "seller_name": "3BCJqe8MRE2",
        "location_text": "Tokyo",
        "image_url": "",
        "image_urls": [],
        "image_local_paths": [],
        "source_url": "https://example.com/source/horse",
        "payload": {
            "item_summary": {
                "seller": {
                    "username": "3BCJqe8MRE2",
                    "feedbackScore": 17728,
                }
            }
        },
        "created_at": "2026-04-10T11:00:00+00:00",
        "updated_at": "2026-04-10T12:00:00+00:00",
    }

    payload = _serialize_sales_listing(row, media_roots=[tmp_path])

    assert payload["seller_name"] == "3BCJqe8MRE2"
    assert payload["seller_label"] == "3BCJqe8MRE2(17,728)"


def test_serialize_sales_listing_cleans_san_presentation_fields(tmp_path: Path):
    row = {
        "listing_uid": "stampauctionnetwork:za-420-2442",
        "provider": "stampauctionnetwork",
        "auctioneer_id": "stampauctionnetwork:auctioneer:za",
        "auction_id": "stampauctionnetwork:auction:za-420",
        "lot_number": "2442",
        "marketplace_site": "stampauctionnetwork.com",
        "source_category_id": "sweden",
        "source_query": "AB Philea Online Stamp Auction - April 15-16, 2026",
        "listing_status": "closed",
        "sale_type": "AUCTION",
        "title": "4 öre light grey. EXCELLENT cancellation MARIEFRED 29.3.1890. (Image1)",
        "subtitle": "SWEDEN continued...",
        "listing_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm#25",
        "search_page": 25,
        "listing_position": 1,
        "sold_at": "",
        "price_amount": "42",
        "price_currency": "USD",
        "shipping_amount": "",
        "shipping_currency": "",
        "total_amount": "42",
        "condition_text": "",
        "seller_name": "AB Philea Online Stamp Auction - April 15-16, 2026",
        "location_text": "",
        "image_url": "https://stampauctionnetwork.com/assets/za420/2442-1.jpg",
        "image_urls": ["https://stampauctionnetwork.com/assets/za420/2442-1.jpg"],
        "image_local_paths": [],
        "source_url": "https://stampauctionnetwork.com/ZA/za42024.cfm",
        "payload": {
            "auctioneer_name": "AB Philea",
            "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
            "closed_at": "2026-04-15T03:00:00Z",
            "item_summary": {
                "itemEndDate": "2026-04-15T03:00:00Z",
            },
        },
        "created_at": "2026-04-12T00:59:04+00:00",
        "updated_at": "2026-04-12T00:59:04+00:00",
    }

    payload = _serialize_sales_listing(row, media_roots=[tmp_path])

    assert payload["title"] == "4 öre light grey. EXCELLENT cancellation MARIEFRED 29.3.1890"
    assert payload["auctioneer_name"] == "AB Philea"
    assert payload["auction_title"] == "AB Philea Online Stamp Auction - April 15-16, 2026"
    assert payload["seller_name"] == "AB Philea"
    assert payload["seller_label"] == "AB Philea"
    assert payload["source_query"] == "Auction"
    assert payload["listing_status"] == "closed"
    assert payload["end_at"] == "2026-04-15T03:00:00"
    assert payload["jump_query"] == payload["title"]
    assert "(Image1)" not in payload["title"]


def test_serialize_sales_listing_repairs_san_fallbacks_from_row_context(tmp_path: Path):
    row = {
        "listing_uid": "stampauctionnetwork:za-420-2880",
        "provider": "stampauctionnetwork",
        "auctioneer_id": "stampauctionnetwork:auctioneer:za",
        "auctioneer_name": "AB Philea",
        "auction_id": "stampauctionnetwork:auction:za-420",
        "auction_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
        "lot_number": "2880",
        "marketplace_site": "stampauctionnetwork.com",
        "source_category_id": "sweden",
        "source_query": "AB Philea Online Stamp Auction - April 15-16, 2026",
        "listing_status": "closed",
        "sale_type": "AUCTION",
        "title": "SWEDEN continued...",
        "subtitle": "SWEDEN continued...",
        "listing_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm#45",
        "search_page": 45,
        "listing_position": 19,
        "sold_at": "Closing..Apr-15, 03:00 AM",
        "price_amount": "83",
        "price_currency": "USD",
        "shipping_amount": "",
        "shipping_currency": "",
        "total_amount": "83",
        "condition_text": "",
        "seller_name": "AB Philea Online Stamp Auction - April 15-16, 2026",
        "location_text": "",
        "image_url": "https://www.philea.se/objects/1860/orig/105102.jpg",
        "image_urls": ["https://www.philea.se/objects/1860/orig/105102.jpg"],
        "image_local_paths": [],
        "source_url": "https://stampauctionnetwork.com/ZA/za42044.cfm",
        "payload": {
            "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
            "page_title": "SWEDEN continued...",
            "page_label": "Unused collections Lots (2862-2881)",
            "catalog_text": "Sweden, **/* lot. Four stamps, 7, 7N1, 14B and 15a, nice/mixed quality. (Image1)",
            "closed_text": "Closing..Apr-15, 03:00 AM",
        },
        "created_at": "2026-04-12T02:09:00+00:00",
        "updated_at": "2026-04-12T02:09:00+00:00",
    }

    payload = _serialize_sales_listing(row, media_roots=[tmp_path])

    assert payload["title"] == "Sweden, **/* lot. Four stamps, 7, 7N1, 14B and 15a, nice/mixed quality"
    assert payload["seller_name"] == "AB Philea"
    assert payload["seller_label"] == "AB Philea"
    assert payload["source_query"] == "Auction"
    assert payload["end_at"] == "2026-04-15T03:00:00"
    assert payload["listing_status"] == "closed"


def test_serialize_sales_listing_replaces_generic_san_sale_title_with_catalog_text(tmp_path: Path):
    row = {
        "listing_uid": "stampauctionnetwork:za-420-2013",
        "provider": "stampauctionnetwork",
        "auctioneer_id": "stampauctionnetwork:auctioneer:za",
        "auctioneer_name": "AB Philea",
        "auction_id": "stampauctionnetwork:auction:za-420",
        "auction_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
        "lot_number": "2013",
        "marketplace_site": "stampauctionnetwork.com",
        "source_category_id": "sweden",
        "source_query": "Auction",
        "listing_status": "active",
        "sale_type": "AUCTION",
        "title": "AB Philea Sale - 420",
        "subtitle": "",
        "listing_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm#2",
        "search_page": 2,
        "listing_position": 12,
        "sold_at": "2026-04-15T03:00:00",
        "price_amount": "32",
        "price_currency": "USD",
        "shipping_amount": "",
        "shipping_currency": "",
        "total_amount": "32",
        "condition_text": "",
        "seller_name": "AB Philea",
        "location_text": "",
        "image_url": "https://www.philea.se/objects/1688/orig/54720.jpg",
        "image_urls": ["https://www.philea.se/objects/1688/orig/54720.jpg"],
        "image_local_paths": [],
        "source_url": "https://stampauctionnetwork.com/ZA/za4201.cfm",
        "payload": {
            "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
            "catalog_text": "Sweden, A-county. STOCKHOLM, ribbon postmarks Type 1 on cover dated '1724' by pen, sent to Hedemora. Superb. Postal: 2500 SEK",
            "detail_url": "https://stampauctionnetwork.com/ZA/za4201.cfm",
        },
        "created_at": "2026-04-12T19:40:00+00:00",
        "updated_at": "2026-04-12T19:40:00+00:00",
    }

    payload = _serialize_sales_listing(row, media_roots=[tmp_path])

    assert payload["title"] == "Sweden, A-county. STOCKHOLM, ribbon postmarks Type 1 on cover dated '1724' by pen, sent to Hedemora. Superb. Postal: 2500 SEK"
    assert payload["auction_title"] == "AB Philea Online Stamp Auction - April 15-16, 2026"
    assert payload["seller_name"] == "AB Philea"


def test_serialize_sales_listing_sanitizes_dirty_san_closing_footer_text(tmp_path: Path):
    row = {
        "listing_uid": "stampauctionnetwork:za-420-2201",
        "provider": "stampauctionnetwork",
        "auctioneer_id": "stampauctionnetwork:auctioneer:za",
        "auctioneer_name": "AB Philea",
        "auction_id": "stampauctionnetwork:auction:za-420",
        "auction_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
        "lot_number": "2201",
        "marketplace_site": "stampauctionnetwork.com",
        "source_category_id": "sweden",
        "source_query": "Auction",
        "listing_status": "active",
        "sale_type": "AUCTION",
        "title": "Sweden, Facit 21 or Scott 22 *, 12 öre blue. Two short perfs.",
        "subtitle": "SWEDEN continued...",
        "listing_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm#11",
        "search_page": 11,
        "listing_position": 2,
        "sold_at": "Apr-15, 03:00 AM Previous Page , Next Page or Return to Table of Contents StampAuctionNetwork® is a registered trademark of Droege Computing Services, Inc",
        "price_amount": "32",
        "price_currency": "USD",
        "shipping_amount": "",
        "shipping_currency": "",
        "total_amount": "32",
        "condition_text": "",
        "seller_name": "AB Philea",
        "location_text": "",
        "image_url": "https://www.philea.se/objects/1688/orig/24564-2.jpg",
        "image_urls": ["https://www.philea.se/objects/1688/orig/24564-2.jpg"],
        "image_local_paths": [],
        "source_url": "https://stampauctionnetwork.com/ZA/za42010.cfm",
        "payload": {
            "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
            "auctioneer_name": "AB Philea",
            "catalog_text": "Sweden, Facit 21 or Scott 22 *, 12 öre blue. Two short perfs.",
            "closed_text": "Closing..Apr-15, 03:00 AM Previous Page , Next Page or Return to Table of Contents StampAuctionNetwork® is a registered trademark of Droege Computing Services, Inc",
        },
        "created_at": "2026-04-12T02:09:00+00:00",
        "updated_at": "2026-04-12T02:09:00+00:00",
    }

    payload = _serialize_sales_listing(row, media_roots=[tmp_path])

    assert payload["end_at"] == "2026-04-15T03:00:00"
    assert payload["listing_status"] == "active"


def test_serialize_sales_listing_uses_san_catalog_text_for_description(tmp_path: Path):
    row = {
        "listing_uid": "stampauctionnetwork:za-420-2338",
        "provider": "stampauctionnetwork",
        "auctioneer_id": "stampauctionnetwork:auctioneer:za",
        "auctioneer_name": "AB Philea",
        "auction_id": "stampauctionnetwork:auction:za-420",
        "auction_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
        "lot_number": "2338",
        "marketplace_site": "stampauctionnetwork.com",
        "source_category_id": "sweden",
        "source_query": "Auction",
        "listing_status": "active",
        "sale_type": "AUCTION",
        "title": "5 öre pale bluish green. EXCELLENT cancellation LUND 6.11.1882. Slightly short perf.",
        "subtitle": "SWEDEN continued... / Circle type, perf 13 (F 28-38) Lots (2322-2341)",
        "listing_url": "https://stampauctionnetwork.com/ZA/ZA420.cfm#18",
        "search_page": 18,
        "listing_position": 16,
        "sold_at": "2026-04-15T03:00:00",
        "price_amount": "32",
        "price_currency": "USD",
        "shipping_amount": "",
        "shipping_currency": "",
        "total_amount": "32",
        "condition_text": "o",
        "seller_name": "AB Philea",
        "location_text": "",
        "image_url": "https://www.philea.se/objects/1688/orig/24008.jpg",
        "image_urls": ["https://www.philea.se/objects/1688/orig/24008.jpg"],
        "image_local_paths": [],
        "source_url": "https://stampauctionnetwork.com/ZA/za42017.cfm",
        "payload": {
            "sale_title": "AB Philea Online Stamp Auction - April 15-16, 2026",
            "catalog_text": "Sweden, Facit 30e or Scott 30 used, 5 öre pale bluish green. EXCELLENT cancellation LUND 6.11.1882. Slightly short perf.",
            "major_group": "SWEDEN continued...",
            "sub_group": "Circle type, perf 13 (F 28-38) Lots (2322-2341)",
            "closed_text": "Closing..Apr-15, 03:00 AM",
        },
        "created_at": "2026-04-12T22:37:00+00:00",
        "updated_at": "2026-04-12T22:37:00+00:00",
    }

    payload = _serialize_sales_listing(row, media_roots=[tmp_path])

    assert payload["payload"]["item_detail"]["description"] == (
        "Sweden, Facit 30e or Scott 30 used, 5 öre pale bluish green. EXCELLENT cancellation LUND 6.11.1882. Slightly short perf"
    )


def test_media_route_requires_allowed_root(tmp_path: Path):
    client, _, image_path = build_client(tmp_path)
    response = client.get("/api/media", params={"path": str(image_path)})
    assert response.status_code == 200
    assert response.content == b"bird-image"

    resized_response = client.get("/api/media", params={"path": str(image_path), "w": 64, "h": 64, "fit": "cover"})
    assert resized_response.status_code == 200
    assert resized_response.headers["content-type"] == "image/jpeg"
    assert resized_response.content

    blocked_path = tmp_path / "blocked" / "outside.jpg"
    blocked_path.parent.mkdir(parents=True, exist_ok=True)
    blocked_path.write_bytes(b"outside")
    blocked_response = client.get("/api/media", params={"path": str(blocked_path)})
    assert blocked_response.status_code == 404


def test_media_resolution_falls_back_to_matching_allowed_root(tmp_path: Path):
    primary_root = tmp_path / "primary"
    backup_root = tmp_path / "backup"
    backup_image = backup_root / "wns" / "MT" / "2025" / "MT029.2025.jpg"
    backup_image.parent.mkdir(parents=True, exist_ok=True)
    backup_image.write_bytes(b"malta")

    stale_path = primary_root / "wns" / "MT" / "2025" / "MT029.2025.jpg"
    resolved = resolve_media_path(str(stale_path), [primary_root, backup_root])

    assert resolved == backup_image
    assert media_url_for_path(str(stale_path), [primary_root, backup_root]) == f"/api/media?path={quote_plus(str(backup_image))}"
