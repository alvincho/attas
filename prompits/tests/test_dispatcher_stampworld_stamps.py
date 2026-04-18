"""
Regression tests for StampWorld stamp dispatcher job caps.

These tests cover the private collectibles pipeline that discovers StampWorld map and
country pages, fans out category/page jobs, stores normalized stamp rows, and
downloads StampWorld catalogue images into local media storage.
"""

import os
import sys
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from private.collectibles.jobcaps.stampworld_stamps import (
    TABLE_STAMPWORLD_STAMP_CATALOG,
    StampWorldStampCatalogJobCap,
    StampWorldStampCountryJobCap,
    StampWorldStampImageJobCap,
    StampWorldStampMapJobCap,
    StampWorldStampPageJobCap,
    _extract_category_options,
    _extract_map_links,
    stampworld_stamp_catalog_table_schema,
)
from private.collectibles.jobcaps.web_support import TABLE_WEB_PAGES, web_pages_table_schema
from prompits.dispatcher.models import JobDetail
from prompits.dispatcher.schema import TABLE_JOBS, ensure_dispatcher_tables
from prompits.pools.sqlite import SQLitePool


MAP_PAGE_HTML = """
<html><body>
  <div class="country-cell">
    <a href="/en/maps/United-States/" data-country-code="us" class="country-link">United States</a>
  </div>
  <div class="country-cell">
    <a href="/en/stamps/Aruba/" data-country-code="aw" class="country-link">Aruba</a>
  </div>
</body></html>
"""


COUNTRY_ROOT_HTML = """
<html>
  <head>
    <title>United States - Postage stamps (1900 - 1901) - Page 1</title>
  </head>
  <body>
    <h6>United States (page 1/2)</h6>
    <div class="info_row">
      <p>
        Now showing: United States -
        <a href="/en/stamps/United-States/Postage stamps/1900-1901">Postage stamps</a>
        (1900 - 1901) - 2 stamps.
      </p>
    </div>
    <form method="POST" name="searchForm" id="searchForm" action="/en/stamps/United-States/">
      <select class="dropDown_search" id="id_category_name" maxlength="64" name="category_name" onchange="category_changed()">
        <option value="Airmail stamps">Airmail stamps</option>
        <option value="Postage stamps" selected="selected">Postage stamps</option>
      </select>
    </form>
  </body>
</html>
"""


Airmail_CATEGORY_HTML = """
<html>
  <head>
    <title>United States - Airmail stamps (1918 - 1918) - Page 1</title>
  </head>
  <body>
    <h6>United States (page 1/1)</h6>
    <div class="info_row">
      <p>
        Now showing: United States -
        <a href="/en/stamps/United-States/Airmail stamps/1918-1918">Airmail stamps</a>
        (1918 - 1918) - 1 stamps.
      </p>
    </div>
    <form method="POST" name="searchForm" id="searchForm" action="/en/stamps/United-States/">
      <select class="dropDown_search" id="id_category_name" maxlength="64" name="category_name" onchange="category_changed()">
        <option value="Airmail stamps" selected="selected">Airmail stamps</option>
        <option value="Postage stamps">Postage stamps</option>
      </select>
    </form>
  </body>
</html>
"""


CATALOG_PAGE_HTML = """
<html>
  <head>
    <title>United States - Postage stamps (1900 - 1901) - Page 1</title>
  </head>
  <body>
    <h6>United States (page 1/2)</h6>
    <a href="/en/stamps/United-States/Postage stamps/1900-1901?page=2" class="next_page">Next</a>
    <div class="info_row">
      <p>
        Now showing: United States -
        <a href="/en/stamps/United-States/Postage stamps/1900-1901">Postage stamps</a>
        (1900 - 1901) - 2 stamps.
      </p>
    </div>
    <div class="container-fluid content_table" id="group_box_22579">
      <div class="row">
        <div class="col-12 table_header">
          <a href="https://www.stampworld.com/stamps/United-States/Postage-stamps/g0001//">
            1900 Sample Definitive Issue
          </a>
          <p>1. January WM: None Sheetsize: 100 Design: Sample Designer Engraving: Sample Engraver Perforation: 11</p>
        </div>
      </div>
      <div class="row">
        <div class="col-12 images_container">
          <span class="stamp_img stamp_img_js">
            <img class="img-fluid" src="https://www.stampworld.com/media/catalogue/United-States/Postage-stamps/A-s.jpg" alt="[Sample Definitive Issue, type A]">
          </span>
        </div>
      </div>
      <div class="row table-responsive">
        <table class="table table-striped table-sm table-hover data_table">
          <tbody>
            <tr class="stamp_tr " data-stamp-group-id="22579" data-stamp-type="A">
              <th scope="row"><a name="0001" id="a_s_0001">1</a></th>
              <td><a href="/en/stamps/United-States/Postage stamps?type=A&amp;view=">A</a></td>
              <td>5C</td>
              <td class="hidden-xs">&nbsp;</td>
              <td class="hidden-xs">blue</td>
              <td class="hidden-xs">&nbsp;</td>
              <td class="hidden-xs">Sample description</td>
              <td class="hidden-xs">(1,000)</td>
              <td class="hidden-xs">&nbsp;</td>
              <td>10</td>
              <td>8</td>
              <td>4</td>
              <td>12</td>
              <td>USD&nbsp;</td>
              <td class="hidden-xs omit_in_print">
                <div class="addthis_toolbox addthis_default_style">
                  <a class="addthis_button_compact"
                     addthis:url="https://www.stampworld.com/stamps/United-States/Postage-stamps/g0001/#0001"
                     addthis:title="Stampworld - United States 1900 - #1"
                     addthis:description="Stamp Sample Definitive Issue">
                    <img src="/static/layout/share-icon.png" alt="Share stamp" />
                  </a>
                </div>
              </td>
              <td class="omit_in_print">
                <a href="#" class='info_btn_js' data-stamp-id="61259">
                  <img src="/static/layout/info-icon.png" alt="Info">
                </a>
              </td>
              <td class="omit_in_print"><button class="btn btn-success buy_btn_js">Buy</button></td>
              <td class="omit_in_print"><button class="btn btn-warning">Sell</button></td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </body>
</html>
"""


class FakeResponse:
    """Simple fake response used for StampWorld job-cap tests."""

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


def test_extract_map_links_only_returns_country_links():
    links = _extract_map_links(MAP_PAGE_HTML, "https://www.stampworld.com/en/maps/North-America/")
    assert links == [
        {
            "kind": "map",
            "url": "https://www.stampworld.com/en/maps/United-States/",
            "label": "United States",
        },
        {
            "kind": "country",
            "url": "https://www.stampworld.com/en/stamps/Aruba/",
            "label": "Aruba",
        },
    ]


def test_extract_category_options_returns_selected_category():
    categories, selected = _extract_category_options(COUNTRY_ROOT_HTML)
    assert categories == ["Airmail stamps", "Postage stamps"]
    assert selected == "Postage stamps"


def test_stampworld_catalog_job_queues_seed_map_jobs(tmp_path):
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    cap = StampWorldStampCatalogJobCap(
        start_map_urls=(
            "https://www.stampworld.com/en/maps/North-America/",
            "https://www.stampworld.com/en/maps/Europe/",
        )
    ).bind_worker(worker)

    result = cap.finish(_job(required_capability="StampWorld Stamp Catalog"))
    assert result.status == "completed"
    assert result.result_summary["queued_maps_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert [row["required_capability"] for row in queued_jobs] == [
        "stampworld stamp map",
        "stampworld stamp map",
    ]


def test_stampworld_map_job_queues_nested_map_and_country_jobs(tmp_path):
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        return FakeResponse(MAP_PAGE_HTML, url=str(url))

    cap = StampWorldStampMapJobCap(request_get=fake_request_get).bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="StampWorld Stamp Map",
            payload={"map_url": "https://www.stampworld.com/en/maps/North-America/"},
        )
    )

    assert result.status == "completed"
    assert result.result_summary["discovered_links"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["required_capability"])
    assert [row["required_capability"] for row in queued_jobs] == [
        "stampworld stamp country",
        "stampworld stamp map",
    ]
    cached_rows = pool._GetTableData(TABLE_WEB_PAGES, table_schema=web_pages_table_schema()) or []
    assert cached_rows[0]["provider"] == "stampworld_stamps"


def test_stampworld_country_job_posts_additional_categories_and_queues_page_jobs(tmp_path):
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    posted_categories: list[str] = []

    def fake_request_get(url, **kwargs):
        return FakeResponse(
            COUNTRY_ROOT_HTML,
            url="https://www.stampworld.com/en/stamps/United-States/",
        )

    def fake_request_post(url, data=None, **kwargs):
        posted_categories.append(str((data or {}).get("category_name") or ""))
        return FakeResponse(
            Airmail_CATEGORY_HTML,
            url="https://www.stampworld.com/en/stamps/United-States/Airmail%20stamps/1918-1918",
        )

    cap = StampWorldStampCountryJobCap(
        request_get=fake_request_get,
        request_post=fake_request_post,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="StampWorld Stamp Country",
            payload={"country_url": "https://www.stampworld.com/en/stamps/United-States/"},
        )
    )

    assert result.status == "completed"
    assert posted_categories == ["Airmail stamps"]
    assert result.result_summary["queued_page_jobs_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert [row["required_capability"] for row in queued_jobs] == [
        "stampworld stamp page",
        "stampworld stamp page",
    ]
    payloads = [row["payload"] for row in queued_jobs]
    assert {payload["category_name"] for payload in payloads} == {"Airmail stamps", "Postage stamps"}
    cached_urls = {
        str(row["source_url"])
        for row in (pool._GetTableData(TABLE_WEB_PAGES, table_schema=web_pages_table_schema()) or [])
    }
    assert "https://www.stampworld.com/en/stamps/United-States/Postage%20stamps/1900-1901" in cached_urls
    assert "https://www.stampworld.com/en/stamps/United-States/Airmail%20stamps/1918-1918" in cached_urls


def test_stampworld_page_job_persists_rows_and_queues_image_and_next_page(tmp_path):
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        return FakeResponse(CATALOG_PAGE_HTML, url=str(url))

    cap = StampWorldStampPageJobCap(request_get=fake_request_get).bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="StampWorld Stamp Page",
            payload={
                "page_url": "https://www.stampworld.com/en/stamps/United-States/Postage%20stamps/1900-1901",
                "country_slug": "United-States",
                "country_name": "United States",
                "category_name": "Postage stamps",
                "page_number": 1,
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["rows_persisted"] == 1
    assert result.result_summary["queued_image_jobs_this_run"] == 1
    assert result.result_summary["queued_next_page"] is True

    catalog_rows = pool._GetTableData(
        TABLE_STAMPWORLD_STAMP_CATALOG,
        table_schema=stampworld_stamp_catalog_table_schema(),
    ) or []
    assert len(catalog_rows) == 1
    row = catalog_rows[0]
    assert row["country_name"] == "United States"
    assert row["category_name"] == "Postage stamps"
    assert row["stampworld_item_id"] == "61259"
    assert row["stamp_number"] == "1"
    assert row["stamp_type"] == "A"
    assert row["image_url"] == "https://www.stampworld.com/media/catalogue/United-States/Postage-stamps/A-s.jpg"

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["required_capability"])
    assert [row["required_capability"] for row in queued_jobs] == [
        "stampworld stamp image",
        "stampworld stamp page",
    ]


def test_stampworld_image_job_downloads_file_and_updates_catalog_row(tmp_path):
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    ensure_dispatcher_tables(
        pool,
        [TABLE_STAMPWORLD_STAMP_CATALOG],
        extra_schemas={TABLE_STAMPWORLD_STAMP_CATALOG: stampworld_stamp_catalog_table_schema()},
    )
    row = {
        "id": "stampworld:stamp:61259",
        "provider": "stampworld_stamps",
        "stampworld_item_id": "61259",
        "country_slug": "United-States",
        "country_name": "United States",
        "category_name": "Postage stamps",
        "catalog_year": 1900,
        "year_range": "1900 - 1901",
        "page_number": 1,
        "page_url": "https://www.stampworld.com/en/stamps/United-States/Postage%20stamps/1900-1901",
        "group_id": "22579",
        "group_url": "https://www.stampworld.com/stamps/United-States/Postage-stamps/g0001//",
        "group_title": "Sample Definitive Issue",
        "group_issue_date": "1. January",
        "watermark": "None",
        "sheet_size": "100",
        "design": "Sample Designer",
        "engraving": "Sample Engraver",
        "perforation": "11",
        "stamp_number": "1",
        "stamp_anchor": "0001",
        "stamp_type": "A",
        "denomination": "5C",
        "color": "blue",
        "description": "Sample description",
        "issued_quantity": "(1,000)",
        "mint_price": "10",
        "unused_price": "8",
        "used_price": "4",
        "cover_price": "12",
        "price_currency": "USD",
        "item_url": "https://www.stampworld.com/stamps/United-States/Postage-stamps/g0001/#0001",
        "image_url": "https://www.stampworld.com/media/catalogue/United-States/Postage-stamps/A-s.jpg",
        "image_local_path": "",
        "source_page_url": "https://www.stampworld.com/en/stamps/United-States/Postage%20stamps/1900-1901",
        "payload": {},
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }
    assert pool._Insert(TABLE_STAMPWORLD_STAMP_CATALOG, row)

    def fake_request_get(url, **kwargs):
        return FakeResponse(
            "",
            url=str(url),
            content=b"fake-image-bytes",
            headers={"Content-Type": "image/jpeg"},
        )

    media_root = tmp_path / "media"
    cap = StampWorldStampImageJobCap(request_get=fake_request_get, media_root=str(media_root)).bind_worker(worker)
    result = cap.finish(
        _job(
            required_capability="StampWorld Stamp Image",
            payload={
                "row_id": "stampworld:stamp:61259",
                "image_url": "https://www.stampworld.com/media/catalogue/United-States/Postage-stamps/A-s.jpg",
                "country_slug": "United-States",
                "category_name": "Postage stamps",
                "catalog_year": 1900,
                "stamp_number": "1",
                "stamp_type": "A",
            },
        )
    )

    assert result.status == "completed"
    image_local_path = Path(result.result_summary["image_local_path"])
    assert image_local_path.exists()
    updated_rows = pool._GetTableData(
        TABLE_STAMPWORLD_STAMP_CATALOG,
        "stampworld:stamp:61259",
        table_schema=stampworld_stamp_catalog_table_schema(),
    ) or []
    assert updated_rows[0]["image_local_path"] == str(image_local_path)
