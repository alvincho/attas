"""
Regression tests for Colnect stamp dispatcher job caps.

These tests cover the private collectibles pipeline that ingests public Colnect stamp
listing pages, stores normalized stamp rows, and downloads stamp images into local
media storage.
"""

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from private.collectibles.jobcaps.colnect_stamps import (
    TABLE_COLNECT_RUNTIME,
    DEFAULT_COUNTRIES_URL,
    TABLE_COLNECT_STAMP_CATALOG,
    ColnectStampCountryJobCap,
    ColnectStampImageJobCap,
    ColnectStampJobCap,
    ColnectStampListingJobCap,
    ColnectStampPageJobCap,
    ColnectStampYearJobCap,
    _build_colnect_item_description,
    _catalog_code_filename_component,
    _coerce_catalog_codes,
    _coerce_iso_date,
    _extract_title,
    _image_country_component,
    _normalize_colnect_description,
    _normalize_colnect_image_url,
    _parse_stamp_detail,
    colnect_runtime_table_schema,
    colnect_stamp_catalog_table_schema,
)
from private.collectibles.report_items import build_lock_status_alert_item
from private.collectibles.jobcaps.web_support import TABLE_WEB_PAGES, web_pages_table_schema
from prompits.dispatcher.models import JobDetail
from prompits.dispatcher.report_feed import TABLE_DISPATCHER_REPORT_ITEMS
from prompits.dispatcher.runtime import build_dispatch_job, utcnow_iso
from prompits.dispatcher.schema import TABLE_JOB_ARCHIVE, TABLE_JOBS, ensure_dispatcher_tables
from prompits.pools.sqlite import SQLitePool


CATALOG_PAGE_HTML = """
<html><body>
  <nav class="countries">
    <a href="https://colnect.com/en/stamps/list/country/225-United_States_of_America">United States of America</a>
    <a href="https://colnect.com/en/stamps/list/country/211-Taiwan_China">Taiwan, China</a>
  </nav>
</body></html>
"""


COUNTRIES_PAGE_HTML = """
<html><body>
  <nav class="countries">
    <a href="https://colnect.com/en/stamps/years/country/225-United_States_of_America">Stamps: United States of America</a>
    <a href="https://colnect.com/en/stamps/years/country/211-Taiwan_China">Stamps: Taiwan, China</a>
  </nav>
</body></html>
"""


COUNTRY_PAGE_HTML = """
<html><body>
  <div class="cookie-consent-modal" role="dialog" aria-modal="true">
    <a href="https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/1999">1999 (popup)</a>
  </div>
  <nav class="years">
    <a href="https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2026">2026 (45)</a>
    <a href="https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2025">2025 (224)</a>
  </nav>
</body></html>
"""


EMPTY_COUNTRY_PAGE_HTML = """
<html><body>
  <p>No years were listed.</p>
</body></html>
"""


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
    <a href="https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006?page=2">2</a>
    <a rel="next" href="https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006?page=2">Next</a>
  </nav>
</body></html>
"""


LIST_PAGE_WITH_FILTER_LINK_HTML = """
<html><body>
  <div class="stamp-grid">
    <article class="stamp-card">
      <a class="title" href="https://colnect.com/en/stamps/stamp/1574778-Republic_of_China_13th_JCC_Asia_International_Postage_Stamp_Exhibition-Taiwan_China_2023">
        Republic of China 13th JCC Asia International Postage Stamp Exhibition
      </a>
    </article>
  </div>
  <nav class="pagination">
    <a href="https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006/page/2">2</a>
    <a rel="next" href="https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006/page/2">Next</a>
  </nav>
  <aside class="filters">
    <a href="https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006/perforation/356-i11i">12</a>
  </aside>
</body></html>
"""


LIST_PAGE_DEEPER_PAGINATION_HTML = """
<html><body>
  <div class="stamp-grid">
    <article class="stamp-card">
      <a class="title" href="https://colnect.com/en/stamps/stamp/1574780-Deep_Page_Item-Taiwan_China_2023">
        Deep Page Item
      </a>
    </article>
  </div>
  <nav class="pagination">
    <a href="https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006/page/3">3</a>
    <a rel="next" href="https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006/page/3">Next</a>
  </nav>
</body></html>
"""


LIST_PAGE_WITH_CATALOG_CODES_HTML = """
<html><body>
  <div class="pl-it">
    <h2 class="item_header">
      <a href="/en/stamps/stamp/719726-Dr_Sun_Yat-sen_and_Plum_Blossoms-China">Dr. Sun Yat-sen and Plum Blossoms</a>
    </h2>
    <div class="item_thumb">
      <a href="/en/stamps/stamp/719726-Dr_Sun_Yat-sen_and_Plum_Blossoms-China">
        <img data-src="//i.colnect.net/t/7322/893/Dr-Sun-Yat-sen-and-Plum-Blossoms.jpg" alt="Dr. Sun Yat-sen and Plum Blossoms" />
      </a>
    </div>
    <div class="i_d">
      <dl>
        <dt>Catalog codes:</dt>
        <dd><strong>Mi:</strong>CN-IM 804, <strong>Sn:</strong>CN-IM 761, <strong>Yt:</strong>CN-IM 583, <strong>Sg:</strong>CN-IM 971, <strong>Chi:</strong>CN-IM 1155</dd>
        <dt>Face value:</dt><dd>300,000 Chinese dollar</dd>
      </dl>
    </div>
  </div>
  <div class="pl-it">
    <h2 class="item_header">
      <a href="/en/stamps/stamp/999694-Dr_Sun_Yat-sen_and_Plum_Blossoms-China">Dr. Sun Yat-sen and Plum Blossoms</a>
    </h2>
    <div class="i_d">
      <dl>
        <dt>Catalog codes:</dt><dd>ColnectIsBest</dd>
      </dl>
    </div>
  </div>
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
      <tr><th>Series</th><td><a href="https://colnect.com/en/stamps/list/country/211-Taiwan_China/series/473001-13th_JCC_Asia_International_Postage_Stamp_Exhibition/year/2023">13th JCC Asia International Postage Stamp Exhibition</a></td></tr>
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
      <tr><th>Related items</th><td>Companion stamp: <a href="https://colnect.com/en/stamps/stamp/1300-Companion_Item-Taiwan_China_2023">Companion Item</a></td></tr>
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


def _render_logs(worker: FakeWorker) -> list[str]:
    """Return the captured worker log lines with %-formatting applied."""
    rendered: list[str] = []
    for message, args in worker.log_messages:
        rendered.append(message % args if args else message)
    return rendered


def _web_page_rows_by_source_url(pool: SQLitePool) -> dict[str, dict[str, Any]]:
    """Return cached shared web pages keyed by source URL."""
    rows = pool._GetTableData(TABLE_WEB_PAGES, table_schema=web_pages_table_schema()) or []
    return {
        str(row["source_url"]): row
        for row in rows
        if isinstance(row, Mapping) and str(row.get("source_url") or "").strip()
    }


def _lock_alert_rows(pool: SQLitePool, source_key: str) -> list[dict[str, Any]]:
    """Return dispatcher lock-status alert rows for one source."""
    return [
        dict(row)
        for row in (pool._GetTableData(TABLE_DISPATCHER_REPORT_ITEMS) or [])
        if str(row.get("kind") or "") == "alert"
        and str(row.get("source_key") or "") == source_key
        and str(row.get("category_key") or "") == "lock_status"
    ]


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


def test_colnect_catalog_job_queues_country_jobs(tmp_path):
    """Catalog job should discover countries and queue country jobs."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://colnect.com/en/stamps/list"
        return FakeResponse(
            CATALOG_PAGE_HTML,
            url=url,
        )

    cap = ColnectStampJobCap(
        source_pages=[
            {"page_url": "https://colnect.com/en/stamps/list", "label": "Colnect stamps"},
        ],
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(_job(required_capability="Colnect Stamp Catalog"))
    assert result.status == "completed"
    assert result.result_summary["queued_countries_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["payload"]["country_key"])
    assert len(queued_jobs) == 2
    assert [row["required_capability"] for row in queued_jobs] == [
        "colnect stamp country",
        "colnect stamp country",
    ]
    assert [row["payload"]["country_key"] for row in queued_jobs] == [
        "211-Taiwan_China",
        "225-United_States_of_America",
    ]
    assert [row["payload"]["country_url"] for row in queued_jobs] == [
        "https://colnect.com/en/stamps/list/country/211-Taiwan_China",
        "https://colnect.com/en/stamps/list/country/225-United_States_of_America",
    ]
    assert [row["priority"] for row in queued_jobs] == [
        ColnectStampJobCap.COUNTRY_PRIORITY - 1,
        ColnectStampJobCap.COUNTRY_PRIORITY - 2,
    ]


def test_colnect_catalog_job_default_seed_uses_countries_page(tmp_path):
    """Catalog job should use the countries seed page by default."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == DEFAULT_COUNTRIES_URL
        return FakeResponse(
            COUNTRIES_PAGE_HTML,
            url=url,
        )

    cap = ColnectStampJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(_job(required_capability="Colnect Stamp Catalog"))
    assert result.status == "completed"
    assert result.result_summary["queued_countries_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["payload"]["country_key"])
    assert [row["payload"]["country_name"] for row in queued_jobs] == [
        "Taiwan, China",
        "United States of America",
    ]
    assert [row["payload"]["country_url"] for row in queued_jobs] == [
        "https://colnect.com/en/stamps/years/country/211-Taiwan_China",
        "https://colnect.com/en/stamps/years/country/225-United_States_of_America",
    ]

    logs = _render_logs(worker)
    assert any("event=job-start" in line and "job_kind=catalog" in line for line in logs)
    assert any("event=fetch-start" in line and f"url={DEFAULT_COUNTRIES_URL}" in line for line in logs)
    assert any(
        "event=job-posted" in line and 'capability="Colnect Stamp Country"' in line
        for line in logs
    )


def test_colnect_catalog_job_jitters_country_schedule_over_requested_day(tmp_path):
    """Catalog fan-out can spread country jobs pseudo-randomly across one local day."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == DEFAULT_COUNTRIES_URL
        return FakeResponse(COUNTRIES_PAGE_HTML, url=url)

    cap = ColnectStampJobCap(request_get=fake_request_get).bind_worker(worker)
    jitter_date = "2020-04-18"

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Catalog",
            payload={"country_schedule_jitter_date": jitter_date},
        )
    )
    assert result.status == "completed"

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["payload"]["country_key"])
    scheduled_values = [row["scheduled_for"] for row in queued_jobs]
    scheduled_times = [datetime.fromisoformat(value) for value in scheduled_values]
    assert [scheduled_time.date().isoformat() for scheduled_time in scheduled_times] == [
        jitter_date,
        jitter_date,
    ]
    assert all(scheduled_time.utcoffset() == timezone(timedelta(hours=8)).utcoffset(None) for scheduled_time in scheduled_times)
    assert len(set(scheduled_values)) == len(scheduled_values)

    logs = _render_logs(worker)
    assert any("event=catalog-source" in line and f"country_schedule_jitter_date={jitter_date}" in line for line in logs)
    assert any("event=job-posted" in line and f"scheduled_for={jitter_date}" in line for line in logs)


def test_colnect_page_job_skip_log_includes_processed_item_counts(tmp_path):
    """Duplicate page skips should report how many items the completed page already processed."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    cap = ColnectStampJobCap().bind_worker(worker)

    page_url = "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/1991/page/6"
    job = build_dispatch_job(
        required_capability="Colnect Stamp Page",
        payload={
            "page_url": page_url,
            "country_key": "225-United_States_of_America",
            "country_name": "United States of America",
            "catalog_year": 1991,
        },
        job_id=cap._page_job_id(page_url),
        source_url=page_url,
        priority=106,
    )
    row = job.to_row()
    row["status"] = "completed"
    row["result_summary"] = {
        "provider": "colnect_stamps",
        "job_kind": "page",
        "queued_listings_this_run": 8,
        "skipped_listings_this_run": 2,
        "queued_pages_this_run": 1,
        "skipped_pages_this_run": 0,
    }
    row["updated_at"] = utcnow_iso()
    ensure_dispatcher_tables(pool, [TABLE_JOBS])
    row["archived_at"] = utcnow_iso()
    assert pool._Insert(TABLE_JOB_ARCHIVE, row)

    result = cap._queue_page_job(
        page_url=page_url,
        source_page_label="United States of America 1991",
        country_key="225-United_States_of_America",
        country_name="United States of America",
        catalog_year=1991,
        year_label="1991",
        follow_pagination=True,
    )
    assert result["queued"] is False
    assert result["existing_status"] == "completed"

    logs = _render_logs(worker)
    assert any(
        "event=job-post-skip" in line
        and 'capability="Colnect Stamp Page"' in line
        and "processed_items=10" in line
        and "queued_items=8" in line
        and "skipped_items=2" in line
        for line in logs
    )


def test_colnect_country_job_priority_elevates_selected_countries(tmp_path):
    """Selected countries should queue after the United States but before normal country jobs."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    cap = ColnectStampJobCap().bind_worker(worker)

    cap._queue_country_job(
        country_url="https://colnect.com/en/stamps/years/country/86-China",
        country_key="86-China",
        country_name="China",
        source_page_url=DEFAULT_COUNTRIES_URL,
        source_page_label="Colnect stamps countries",
    )
    cap._queue_country_job(
        country_url="https://colnect.com/en/stamps/years/country/211-Taiwan_China",
        country_key="211-Taiwan_China",
        country_name="Taiwan, China",
        source_page_url=DEFAULT_COUNTRIES_URL,
        source_page_label="Colnect stamps countries",
    )
    cap._queue_country_job(
        country_url="https://colnect.com/en/stamps/years/country/74-France",
        country_key="74-France",
        country_name="France",
        source_page_url=DEFAULT_COUNTRIES_URL,
        source_page_label="Colnect stamps countries",
    )
    cap._queue_country_job(
        country_url="https://colnect.com/en/stamps/years/country/224-United_Kingdom_of_Great_Britain_Northern_Ireland",
        country_key="224-United_Kingdom_of_Great_Britain_Northern_Ireland",
        country_name="United Kingdom of Great Britain & Northern Ireland",
        source_page_url=DEFAULT_COUNTRIES_URL,
        source_page_label="Colnect stamps countries",
    )
    cap._queue_country_job(
        country_url="https://colnect.com/en/stamps/years/country/225-United_States_of_America",
        country_key="225-United_States_of_America",
        country_name="United States of America",
        source_page_url=DEFAULT_COUNTRIES_URL,
        source_page_label="Colnect stamps countries",
    )

    queued_jobs = {
        row["payload"]["country_key"]: row["priority"]
        for row in pool._GetTableData(TABLE_JOBS)
    }
    assert queued_jobs == {
        "86-China": ColnectStampJobCap.COUNTRY_PRIORITY - 1,
        "74-France": ColnectStampJobCap.COUNTRY_PRIORITY - 1,
        "211-Taiwan_China": ColnectStampJobCap.COUNTRY_PRIORITY - 1,
        "224-United_Kingdom_of_Great_Britain_Northern_Ireland": ColnectStampJobCap.COUNTRY_PRIORITY - 1,
        "225-United_States_of_America": ColnectStampJobCap.COUNTRY_PRIORITY - 2,
    }
    assert (
        ColnectStampJobCap.YEAR_PRIORITY
        < queued_jobs["225-United_States_of_America"]
        < queued_jobs["86-China"]
        < ColnectStampJobCap.COUNTRY_PRIORITY
    )


def test_colnect_request_headers_look_like_safari():
    """Colnect requests should look like a normal Safari navigation."""
    cap = ColnectStampJobCap()
    headers = cap._request_headers()
    assert headers["User-Agent"].startswith("Mozilla/5.0")
    assert "Version/" in headers["User-Agent"]
    assert "Safari/605.1.15" in headers["User-Agent"]
    assert "Chrome/" not in headers["User-Agent"]
    assert headers["Upgrade-Insecure-Requests"] == "1"
    assert headers["Sec-Fetch-Mode"] == "navigate"
    assert "sec-ch-ua" not in headers


def test_colnect_image_url_normalization_prefers_original_image_path():
    """Colnect page thumbnails should map to the matching original image URL."""
    assert (
        _normalize_colnect_image_url("https://i.colnect.net/t/22058/049/George-Washington.jpg")
        == "https://i.colnect.net/f/22058/049/George-Washington.jpg"
    )
    assert (
        _normalize_colnect_image_url("https://i.colnect.net/f/22058/049/George-Washington.jpg")
        == "https://i.colnect.net/f/22058/049/George-Washington.jpg"
    )
    assert _normalize_colnect_image_url("https://i.colnect.net/items/thumb/none_logged_image.jpg") == ""


def test_colnect_coerce_iso_date_normalizes_spaced_and_unicode_dashes():
    """Date parsing should normalize Colnect's oddly spaced ISO-ish dates."""
    assert _coerce_iso_date("2026 -01-09") == "2026-01-09"
    assert _coerce_iso_date("2026 - 01 - 09") == "2026-01-09"
    assert _coerce_iso_date("2026–01–09") == "2026-01-09"
    assert _coerce_iso_date("from colnect.com") == ""
    assert _coerce_iso_date("ColnectIsBest") == ""


def test_colnect_parse_stamp_detail_ignores_non_date_issue_label():
    """Detail parsing should drop bogus issue-date text from live Colnect pages."""
    detail = _parse_stamp_detail(
        """
        <html>
          <head><title>Stamp catalog : Stamp › Love Birds</title></head>
          <body>
            <table>
              <tr><th>Issued on</th><td>from colnect.com</td></tr>
              <tr><th>Country</th><td>United States of America</td></tr>
            </table>
          </body>
        </html>
        """,
        source_url="https://colnect.com/en/stamps/stamp/1651924-Love_Birds-Love_Birds_2026-United_States_of_America",
    )
    assert detail["issue_date"] == ""


def test_colnect_coerce_catalog_codes_drops_colnect_noise():
    """Catalog code parsing should ignore anti-bot text and preserve real codes."""
    assert _coerce_catalog_codes("VisitColnectCom") == ""
    assert _coerce_catalog_codes("from colnect.com") == ""
    assert _coerce_catalog_codes("ColnectScrp") == ""
    assert _coerce_catalog_codes("iInfringe") == ""
    assert _coerce_catalog_codes("Login to see complete item details") == ""
    assert _coerce_catalog_codes("Mi:US 4018BDI, Sn:US 3976") == "3976, Mi.4018BDI"
    assert (
        _coerce_catalog_codes(
            "Stamp Number US 5987 Yvert et Tellier US 5914 Stanley Gibbons US 6611 Colnect codes US 2025.04.26-02f"
        )
        == "5987, Sg.6611, Yt.5914, Col.2025.04.26-02f"
    )
    assert _coerce_catalog_codes("Colnect codes US 2026.02.18-01a Michel Unlisted") == "Mi.Unlisted, Col.2026.02.18-01a"
    assert _coerce_catalog_codes("Michel US 6275BA Stamp Number US 5960i Yvert et Tellier US 5873") == "5960i, Mi.6275BA, Yt.5873"
    assert _coerce_catalog_codes("Colnect codes US 2026.01.15-01") == "Col.2026.01.15-01"


def test_colnect_parse_stamp_detail_ignores_non_catalog_code_label():
    """Detail parsing should allow row building to drop bogus catalog code text."""
    detail = _parse_stamp_detail(
        """
        <html>
          <body>
            <table>
              <tr><th>Catalog codes</th><td>VisitColnectCom</td></tr>
              <tr><th>Issued on</th><td>2026 -01-29</td></tr>
            </table>
          </body>
        </html>
        """,
        source_url="https://colnect.com/en/stamps/stamp/1655167-Phyllis_Wheatley_Poet-United_States_of_America",
    )
    assert _coerce_catalog_codes(detail["catalog_codes"]) == ""
    assert detail["issue_date"] == "2026-01-29"


def test_colnect_parse_stamp_detail_sanitizes_noisy_labels():
    """Detail parsing should blank noisy labels and preserve external catalog numbers."""
    detail = _parse_stamp_detail(
        """
        <html>
          <body>
            <table>
              <tr><th>Face value</th><td>ColnectIsBest</td></tr>
              <tr><th>Perforation</th><td>VisitColnectCom</td></tr>
              <tr><th>Catalog codes</th><td>Stamp Number US 6051 Colnect codes US 2026.01.15-01b</td></tr>
              <tr><th>Issued on</th><td>2026-01-15</td></tr>
            </table>
          </body>
        </html>
        """,
        source_url="https://colnect.com/en/stamps/stamp/1651931-Muhammad_Ali_Boxer-United_States_of_America",
    )
    assert detail["face_value"] == ""
    assert detail["perforation"] == ""
    assert detail["catalog_codes"] == "6051, Col.2026.01.15-01b"
    assert detail["issue_date"] == "2026-01-15"


def test_colnect_parse_stamp_detail_reads_separate_stamp_number_label():
    """Detail parsing should keep stamp numbers even when Colnect splits catalog labels."""
    detail = _parse_stamp_detail(
        """
        <html>
          <body>
            <table>
              <tr><th>Country</th><td>China</td></tr>
              <tr><th>Stamp Number</th><td>CN 1060</td></tr>
              <tr><th>Michel</th><td>CN 1127</td></tr>
              <tr><th>Colnect codes</th><td>CN 1948.02.01</td></tr>
              <tr><th>Issued on</th><td>1948</td></tr>
            </table>
          </body>
        </html>
        """,
        source_url="https://colnect.com/en/stamps/stamp/999694-Dr_Sun_Yat-sen_and_Plum_Blossoms-China",
    )
    assert detail["catalog_codes"] == "1060, Mi.1127, Col.1948.02.01"


def test_colnect_parse_stamp_detail_extracts_related_item_links():
    """Detail parsing should preserve related Colnect ids and URLs."""
    detail = _parse_stamp_detail(
        """
        <html>
          <body>
            <table>
              <tr>
                <th>Related items</th>
                <td>
                  Philatelic Product (Related):
                  <a href="https://colnect.com/en/stamps/stamp/3628-Ludwig_Wittgenstein_Philosopher-Austria_2022">Ludwig Wittgenstein, Philosopher</a>
                </td>
              </tr>
            </table>
          </body>
        </html>
        """,
        source_url="https://colnect.com/en/stamps/stamp/3627-Ludwig_Wittgenstein_Philosopher-Austria_2022",
    )
    assert detail["payload"]["related_items"] == [
        {
            "title": "Ludwig Wittgenstein, Philosopher",
            "item_url": "https://colnect.com/en/stamps/stamp/3628-Ludwig_Wittgenstein_Philosopher-Austria_2022",
            "relation_label": "Philatelic Product (Related)",
            "colnect_section": "stamps",
            "colnect_kind": "stamp",
            "colnect_id": "3628",
            "item_uid": "colnect-stamp:3628",
        }
    ]


def test_colnect_item_description_uses_page_level_distinguishers():
    """Page-level rows should get useful item descriptions without detail-page text."""
    description = _build_colnect_item_description(
        {
            "item_url": "https://colnect.com/en/stamps/stamp/1563609-George_Washington_1732-1799_First_President_of_the_USA-1902-1908_Regular_Issue-United_States_of_America",
            "catalog_year": 1908,
            "payload": {"detail_fetch_pending": True},
        },
        title="George Washington (1732-1799), First President of the U.S.A.",
        country_name="United States of America",
        stamp_id="1563609",
        issue_year=1908,
    )
    assert description == (
        "George Washington (1732-1799), First President of the U.S.A.; "
        "1902-1908 Regular Issue; United States of America 1908; Colnect ID 1563609"
    )


def test_colnect_item_description_includes_related_item_context():
    """Related items should make otherwise similar rows easier to distinguish."""
    description = _build_colnect_item_description(
        {
            "description": "",
            "catalog_codes": "Mi:AT 123",
            "item_url": "https://colnect.com/en/stamps/stamp/3627-Ludwig_Wittgenstein_Philosopher-Austria_2022",
            "payload": {
                "related_items": [
                    {
                        "title": "Ludwig Wittgenstein, Philosopher",
                        "relation_label": "Philatelic Product (Related)",
                        "colnect_id": "3628",
                    }
                ]
            },
        },
        title="Ludwig Wittgenstein, Philosopher",
        country_name="Austria",
        stamp_id="3627",
        issue_year=2022,
    )
    assert description == (
        "Ludwig Wittgenstein, Philosopher; Austria 2022; catalog Mi.123. "
        "Related items: Philatelic Product (Related): Ludwig Wittgenstein, Philosopher (Colnect 3628)."
    )


def test_colnect_parse_stamp_detail_extracts_series_id_from_link():
    """Detail parsing should preserve the numeric Colnect series id from the series link."""
    detail = _parse_stamp_detail(
        """
        <html>
          <body>
            <table>
              <tr>
                <th>Series</th>
                <td>
                  <a href="https://colnect.com/en/stamps/list/country/14-Austria/series/373987-Musical_Country_Austria/year/2022/catalog/137-ANK">
                    Musical Country Austria
                  </a>
                </td>
              </tr>
            </table>
          </body>
        </html>
        """,
        source_url="https://colnect.com/en/stamps/stamp/999999-Trombone-Musical_Country_Austria-Austria",
    )
    assert detail["series_name"] == "Musical Country Austria"
    assert detail["payload"]["series_id"] == "373987"
    assert detail["payload"]["series_url"] == (
        "https://colnect.com/en/stamps/list/country/14-Austria/series/373987-Musical_Country_Austria/year/2022/catalog/137-ANK"
    )


def test_colnect_parse_stamp_detail_marks_stub_image_as_missing():
    """Detail parsing should flag Colnect's shared no-image stub instead of keeping it as a real image."""
    detail = _parse_stamp_detail(
        """
        <html>
          <head>
            <meta property="og:image" content="https://i.colnect.net/items/full/none-stamps.jpg" />
          </head>
          <body>
            <table>
              <tr><th>Country</th><td>United States of America</td></tr>
            </table>
          </body>
        </html>
        """,
        source_url="https://colnect.com/en/stamps/stamp/1574083-Cherry_Trees_-_Intl_Eco_Parcel-Personal_Computer_Postage_-_Cherry_Blossoms-United_States_of_America",
    )
    assert detail["image_url"] == ""
    assert detail["payload"]["no_image"] is True


def test_colnect_parse_stamp_detail_marks_data_image_as_missing():
    """Detail parsing should treat inline data-image placeholders as no-image."""
    detail = _parse_stamp_detail(
        """
        <html>
          <head>
            <meta property="og:image" content="data:image/gif;base64,R0lGODlhAQABAAAAACw=" />
          </head>
          <body>
            <table>
              <tr><th>Country</th><td>United States of America</td></tr>
            </table>
          </body>
        </html>
        """,
        source_url="https://colnect.com/en/stamps/stamp/1568315-Placeholder-United_States_of_America",
    )
    assert detail["image_url"] == ""
    assert detail["payload"]["no_image"] is True


def test_colnect_parse_stamp_detail_prefers_real_body_image_over_data_placeholder():
    """Detail parsing should keep scanning past inline placeholders and capture a real Colnect image."""
    detail = _parse_stamp_detail(
        """
        <html>
          <head>
            <meta property="og:image" content="data:image/gif;base64,R0lGODlhAQABAAAAACw=" />
          </head>
          <body>
            <table>
              <tr><th>Country</th><td>United States of America</td></tr>
            </table>
            <div class="stamp-photo">
              <img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" />
              <img data-src="https://img.colnect.net/items/1568315-large.jpg" />
            </div>
          </body>
        </html>
        """,
        source_url="https://colnect.com/en/stamps/stamp/1568315-Placeholder-United_States_of_America",
    )
    assert detail["image_url"] == "https://img.colnect.net/items/1568315-large.jpg"
    assert detail["payload"]["no_image"] is False


def test_colnect_parse_stamp_detail_skips_colnect_logo_and_keeps_real_image():
    """Detail parsing should ignore Colnect's site logo and keep scanning for the stamp image."""
    detail = _parse_stamp_detail(
        """
        <html>
          <head>
            <meta property="og:image" content="https://i.colnect.net/items/full/none-stamps.jpg" />
          </head>
          <body>
            <img src="https://i.colnect.net/colnect_sm.png" />
            <div class="stamp-photo">
              <img data-src="https://i.colnect.net/f/23375/548/Quilt_Design_by_Harriet_Powers.jpg" />
            </div>
            <table>
              <tr><th>Country</th><td>United States of America</td></tr>
            </table>
          </body>
        </html>
        """,
        source_url="https://colnect.com/en/stamps/stamp/1662103-Quilt_Design_by_Harriet_Powers-Harriet_Powers_Quilt_Artist_2026-United_States_of_America",
    )
    assert detail["image_url"] == "https://i.colnect.net/f/23375/548/Quilt_Design_by_Harriet_Powers.jpg"
    assert detail["payload"]["no_image"] is False


def test_colnect_catalog_code_filename_component_uses_priority():
    """Image filenames should use the preferred catalog code token."""
    assert _catalog_code_filename_component("Stamp Number US 6051") == "6051"
    assert _catalog_code_filename_component("Michel Unlisted") == "Mi.Unlisted"
    assert _catalog_code_filename_component("Colnect codes US 2026.01.15-01") == "Col.2026.01.15-01"


def test_colnect_extract_title_strips_site_prefix():
    """Title extraction should drop the Colnect page prefix."""
    assert (
        _extract_title(
            "<html><head><title>Stamp catalog : Stamp › Quilt Design by Harriet Powers</title></head></html>",
            {},
        )
        == "Quilt Design by Harriet Powers"
    )


def test_colnect_normalize_description_strips_prefix_and_colnect_tail():
    """Description parsing should remove Colnect chrome from meta descriptions."""
    assert (
        _normalize_colnect_description(
            "Stamp: Quilt Design by Harriet Powers (United States of America(Harriet Powers, Quilt Artist (2026)) Col:US 2026.02.28-01a 📮. Buy, sell, trade and exchange collectibles easily with Colnect collectors community."
        )
        == "Quilt Design by Harriet Powers (United States of America (Harriet Powers, Quilt Artist (2026)))"
    )
    assert (
        _normalize_colnect_description(
            "Stamp: Love by Keith Haring (United States of AmericaMi:US 6260BA,Sn:US 5953,Sg:US 6577,Col:US 2025.01.17-01 📮. Buy, sell, trade and exchange collectibles easily with Colnect collectors community."
        )
        == "Love by Keith Haring (United States of America)"
    )


def test_colnect_image_country_component_removes_spaces():
    """Country names should not keep spaces in image filenames."""
    assert _image_country_component("United States of America") == "UnitedStatesOfAmerica"


def test_colnect_country_job_queues_year_jobs(tmp_path):
    """Country job should discover years and queue country/year jobs."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://colnect.com/en/stamps/years/country/225-United_States_of_America"
        return FakeResponse(
            COUNTRY_PAGE_HTML,
            url=url,
        )

    cap = ColnectStampCountryJobCap(
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Country",
            payload={
                "country_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_years_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["payload"]["catalog_year"])
    assert len(queued_jobs) == 2
    assert [row["required_capability"] for row in queued_jobs] == [
        "colnect stamp year",
        "colnect stamp year",
    ]
    assert [row["payload"]["catalog_year"] for row in queued_jobs] == [2025, 2026]
    assert [row["payload"]["year_url"] for row in queued_jobs] == [
        "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2025",
        "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2026",
    ]
    assert [row["payload"]["expected_item_count"] for row in queued_jobs] == [224, 45]
    assert [row["payload"]["expected_page_count"] for row in queued_jobs] == [23, 5]
    assert [row["priority"] for row in queued_jobs] == [
        ColnectStampJobCap.YEAR_PRIORITY,
        ColnectStampJobCap.YEAR_PRIORITY,
    ]


def test_colnect_country_job_without_year_links_queues_nothing(tmp_path):
    """Country job should not synthesize a null-year branch when the years page is empty."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://colnect.com/en/stamps/years/country/225-United_States_of_America"
        return FakeResponse(
            EMPTY_COUNTRY_PAGE_HTML,
            url=url,
        )

    cap = ColnectStampCountryJobCap(
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Country",
            payload={
                "country_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_years_this_run"] == 0
    assert pool._GetTableData(TABLE_JOBS) == []


def test_colnect_country_job_solves_anubis_challenge_and_queues_years(tmp_path):
    """Country job should solve Anubis proof-of-work before parsing year links."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    target_url = "https://colnect.com/en/stamps/years/country/225-United_States_of_America"
    pass_url = "https://colnect.com/.within.website/x/cmd/anubis/api/pass-challenge"
    target_hits = 0

    def fake_request_get(url, **kwargs):
        nonlocal target_hits
        if url == target_url:
            target_hits += 1
            if target_hits == 1:
                return FakeResponse(ANUBIS_CHALLENGE_HTML, url=url)
            return FakeResponse(COUNTRY_PAGE_HTML, url=url)
        if url == pass_url:
            params = dict(kwargs.get("params") or {})
            assert params["id"] == "challenge-123"
            assert params["redir"] == target_url
            nonce = int(params["nonce"])
            expected_hash = hashlib.sha256(f"abcdef1234567890{nonce}".encode("utf-8")).hexdigest()
            assert params["response"] == expected_hash
            assert int(params["elapsedTime"]) >= 0
            headers = dict(kwargs.get("headers") or {})
            assert headers["Referer"] == target_url
            assert headers["Sec-Fetch-Site"] == "same-origin"
            return FakeResponse("", url=target_url)
        raise AssertionError(f"Unexpected URL {url}")

    cap = ColnectStampCountryJobCap(
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Country",
            payload={
                "country_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_years_this_run"] == 2


def test_colnect_country_job_reissues_when_anubis_challenge_persists(tmp_path):
    """Country job should reissue itself when Anubis still blocks the years page."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    target_url = "https://colnect.com/en/stamps/years/country/225-United_States_of_America"
    pass_url = "https://colnect.com/.within.website/x/cmd/anubis/api/pass-challenge"

    def fake_request_get(url, **kwargs):
        if url == target_url:
            return FakeResponse(ANUBIS_CHALLENGE_HTML, url=url)
        if url == pass_url:
            params = dict(kwargs.get("params") or {})
            assert params["redir"] == target_url
            return FakeResponse("", url=target_url)
        raise AssertionError(f"Unexpected URL {url}")

    cap = ColnectStampCountryJobCap(
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Country",
            payload={
                "country_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
            },
        )
    )
    assert result.status == "failed"
    assert result.result_summary["connection_issue"] is True
    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "colnect stamp country"
    assert queued_jobs[0]["priority"] == 101


def test_colnect_year_job_queues_all_page_jobs(tmp_path):
    """Year job should queue every page directly from the exact item count."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        raise AssertionError(f"Year jobs should not fetch HTML anymore: {url}")

    cap = ColnectStampYearJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Year",
            payload={
                "country_url": "https://colnect.com/en/stamps/years/country/225-United_States_of_America",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
                "catalog_year": 2024,
                "year_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2024",
                "year_label": "2024 (15)",
                "expected_item_count": 15,
                "expected_page_count": 2,
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["page_job_queued"] is True
    assert result.result_summary["page_count"] == 2
    assert result.result_summary["queued_pages_this_run"] == 2

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["payload"]["page_url"])
    assert len(queued_jobs) == 2
    assert [row["required_capability"] for row in queued_jobs] == [
        "colnect stamp page",
        "colnect stamp page",
    ]
    assert [row["payload"]["page_url"] for row in queued_jobs] == [
        "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2024",
        "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2024/page/2",
    ]
    assert [row["priority"] for row in queued_jobs] == [106, 106]
    assert [row["payload"]["follow_pagination"] for row in queued_jobs] == [False, False]


def test_colnect_year_job_ignores_filter_links_when_queueing_pages(tmp_path):
    """Year job should trust the exact item count and queue every canonical page."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        raise AssertionError(f"Year jobs should not fetch HTML anymore: {url}")

    cap = ColnectStampYearJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Year",
            payload={
                "country_url": "https://colnect.com/en/stamps/years/country/225-United_States_of_America",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
                "catalog_year": 2006,
                "year_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006",
                "year_label": "2006 (45)",
                "expected_item_count": 45,
                "expected_page_count": 5,
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["page_count"] == 5

    queued_page_urls = sorted(
        row["payload"]["page_url"]
        for row in pool._GetTableData(TABLE_JOBS)
        if row["required_capability"] == "colnect stamp page"
    )
    assert queued_page_urls == [
        "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006",
        "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006/page/2",
        "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006/page/3",
        "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006/page/4",
        "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006/page/5",
    ]


def test_colnect_page_job_persists_page_rows_and_queues_image_jobs(tmp_path):
    """Page job should persist page-level rows and not fan out detail jobs."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006"
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
                "page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006",
                "source_page_label": "United States of America 2006",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
                "catalog_year": 2006,
                "year_label": "2006",
                "follow_pagination": False,
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["returned_items_this_run"] == 2
    assert result.result_summary["saved_page_items_this_run"] == 2
    assert result.result_summary["detail_fetch_pending_this_run"] == 2
    assert result.result_summary["queued_image_jobs_this_run"] == 2
    assert result.result_summary["queued_listings_this_run"] == 0
    assert result.result_summary["queued_pages_this_run"] == 0

    queued_jobs = sorted(pool._GetTableData(TABLE_JOBS), key=lambda row: row["id"])
    assert len(queued_jobs) == 2
    assert {row["required_capability"] for row in queued_jobs} == {"colnect stamp image"}
    assert [row["payload"]["stamp_id"] for row in queued_jobs] == ["1574778", "1574779"]
    assert [row["priority"] for row in queued_jobs] == [
        ColnectStampJobCap.IMAGE_PRIORITY,
        ColnectStampJobCap.IMAGE_PRIORITY,
    ]
    assert [row["payload"]["catalog_year"] for row in queued_jobs] == [2006, 2006]

    catalog_rows = sorted(
        pool._GetTableData(
            TABLE_COLNECT_STAMP_CATALOG,
            table_schema=colnect_stamp_catalog_table_schema(),
        ),
        key=lambda row: row["stamp_id"],
    )
    assert [row["stamp_id"] for row in catalog_rows] == ["1574778", "1574779"]
    assert [row["image_url"] for row in catalog_rows] == [
        "https://img.colnect.net/items/1574778.jpg",
        "https://img.colnect.net/items/1574779.jpg",
    ]
    assert all(row["payload"]["detail_fetch_pending"] is True for row in catalog_rows)
    assert all(row["payload"]["detail_fetch_status"] == "pending" for row in catalog_rows)


def test_colnect_page_job_reads_catalog_codes_from_listing_cards(tmp_path):
    """Page job should persist catalog codes available in Colnect list-page cards."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://colnect.com/en/stamps/list/country/442-China/year/1948"
        return FakeResponse(
            LIST_PAGE_WITH_CATALOG_CODES_HTML,
            url=url,
        )

    cap = ColnectStampPageJobCap(
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Page",
            payload={
                "page_url": "https://colnect.com/en/stamps/list/country/442-China/year/1948",
                "source_page_label": "China 1948",
                "country_key": "442-China",
                "country_name": "China",
                "catalog_year": 1948,
                "year_label": "1948",
                "follow_pagination": False,
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["queued_listings_this_run"] == 0

    catalog_rows = {
        row["stamp_id"]: row
        for row in pool._GetTableData(
            TABLE_COLNECT_STAMP_CATALOG,
            table_schema=colnect_stamp_catalog_table_schema(),
        )
    }
    assert catalog_rows["719726"]["catalog_codes"] == "CN-IM761, Mi.CN-IM804, Sg.CN-IM971, Yt.CN-IM583, Chi.CN-IM1155"
    assert catalog_rows["999694"]["catalog_codes"] == ""


def test_colnect_page_job_uses_cached_html_until_refreshed(tmp_path):
    """Page jobs should reuse cached raw HTML unless the run is forced to refresh."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    request_urls: list[str] = []
    responses = [LIST_PAGE_HTML, LIST_PAGE_DEEPER_PAGINATION_HTML]

    def fake_request_get(url, **kwargs):
        request_urls.append(url)
        assert url == "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006"
        return FakeResponse(responses[len(request_urls) - 1], url=url, headers={"Content-Type": "text/html; charset=utf-8"})

    cap = ColnectStampPageJobCap(
        request_get=fake_request_get,
    ).bind_worker(worker)

    first_result = cap.finish(
        _job(
            required_capability="Colnect Stamp Page",
            payload={
                "page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006",
                "source_page_label": "United States of America 2006",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
                "catalog_year": 2006,
                "year_label": "2006",
                "follow_pagination": True,
            },
        )
    )
    assert first_result.status == "completed"
    assert first_result.result_summary["page_cache_hit"] is False
    assert first_result.result_summary["page_fetch_source"] == "network"

    second_result = cap.finish(
        _job(
            required_capability="Colnect Stamp Page",
            payload={
                "page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006",
                "source_page_label": "United States of America 2006",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
                "catalog_year": 2006,
                "year_label": "2006",
                "follow_pagination": True,
            },
        )
    )
    assert second_result.status == "completed"
    assert second_result.result_summary["page_cache_hit"] is True
    assert second_result.result_summary["page_fetch_source"] == "cache"

    third_result = cap.finish(
        _job(
            required_capability="Colnect Stamp Page",
            payload={
                "page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006",
                "source_page_label": "United States of America 2006",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
                "catalog_year": 2006,
                "year_label": "2006",
                "follow_pagination": True,
                "refresh_item": True,
            },
        )
    )
    assert third_result.status == "completed"
    assert third_result.result_summary["page_cache_hit"] is False
    assert third_result.result_summary["page_fetch_source"] == "network"

    assert request_urls == [
        "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006",
        "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006",
    ]
    cached_rows = _web_page_rows_by_source_url(pool)
    cached_row = cached_rows["https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006"]
    assert cached_row["provider"] == "colnect_stamps"
    assert cached_row["page_kind"] == "year_page"
    assert cached_row["content_type"] == "text/html; charset=utf-8"
    assert "Deep Page Item" in cached_row["html_text"]


def test_colnect_page_job_does_not_follow_pagination_links(tmp_path):
    """Page jobs should only parse listings even if pagination links are present."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006/page/2"
        return FakeResponse(LIST_PAGE_DEEPER_PAGINATION_HTML, url=url)

    cap = ColnectStampPageJobCap(request_get=fake_request_get).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Page",
            payload={
                "page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006/page/2",
                "source_page_label": "United States of America 2006",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
                "catalog_year": 2006,
                "year_label": "2006",
                "follow_pagination": True,
            },
        )
    )

    assert result.status == "completed"
    assert result.result_summary["queued_pages_this_run"] == 0
    queued_page_urls = [
        row["payload"]["page_url"]
        for row in pool._GetTableData(TABLE_JOBS)
        if row["required_capability"] == "colnect stamp page"
    ]
    assert queued_page_urls == []


def test_colnect_page_job_sets_global_rate_limit_hold_on_429(tmp_path):
    """A 429 should suspend Colnect work globally until an explicit release check clears it."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        return FakeResponse("too many requests", status_code=429, url=url)

    cap = ColnectStampPageJobCap(
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Page",
            payload={
                "page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006",
                "source_page_label": "United States of America 2006",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
                "catalog_year": 2006,
                "year_label": "2006",
            },
        )
    )

    assert result.status == "failed"
    assert result.result_summary["rate_limited"] is True
    hold_rows = pool._GetTableData(TABLE_COLNECT_RUNTIME)
    assert len(hold_rows) == 1
    assert hold_rows[0]["id"] == "global-rate-limit"
    assert hold_rows[0]["hold_until"] in ("", None)
    assert hold_rows[0]["metadata"]["release_controller"] == "10 Minutes Scheduled Job"
    assert hold_rows[0]["metadata"]["release_pending"] is True
    assert (
        hold_rows[0]["metadata"]["last_blocked_url"]
        == "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006"
    )
    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "colnect stamp page"
    assert queued_jobs[0]["priority"] == 101


def _timeout_page_job(page_url: str) -> JobDetail:
    """Return a claimed Colnect page job for timeout-lock tests."""
    return JobDetail.model_validate(
        {
            "id": "dispatcher-job:colnect-page:test-timeout",
            "required_capability": "Colnect Stamp Page",
            "payload": {
                "page_url": page_url,
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
                "catalog_year": 1869,
            },
            "status": "claimed",
            "claimed_by": "worker-a",
            "attempts": 1,
            "max_attempts": 5,
            "priority": 106,
            "source_url": page_url,
            "metadata": {
                "colnect": {
                    "connection_retry_count": 0,
                },
            },
        }
    )


def _timeout_error(page_url: str) -> str:
    """Return the long Colnect timeout error text recognized by the lock code."""
    return (
        "Failed to process Colnect page "
        f"{page_url}: HTTPSConnectionPool(host='colnect.com', port=443): Max retries exceeded "
        f"with url: /en/stamps/list/country/225-United_States_of_America/year/1869/page/11 "
        "(Caused by ConnectTimeoutError(<urllib3.connection.HTTPSConnection object at 0x1>, "
        "'Connection to colnect.com timed out. (connect timeout=300.0)'))"
    )


def _seed_colnect_timeout_counter(cap: ColnectStampJobCap) -> None:
    """Seed the runtime row one timeout short of the global lock threshold."""
    cap._upsert_runtime_state(
        "global-rate-limit",
        scope="global-rate-limit",
        metadata={
            "provider": "colnect_stamps",
            "active": False,
            "release_pending": False,
            "release_controller": "10 Minutes Scheduled Job",
            "consecutive_120s_timeout_count": 2,
        },
    )


def test_colnect_third_configured_timeout_sets_global_rate_limit_hold_after_confirmed_block(tmp_path):
    """The third shared configured timeout should pause Colnect only after a confirming block probe."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    page_url = "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/1869/page/11"
    probe_urls: list[str] = []

    def fake_request_get(url, **kwargs):
        probe_urls.append(str(url))
        return FakeResponse("too many requests", status_code=429, url=url)

    cap = ColnectStampPageJobCap(request_get=fake_request_get).bind_worker(worker)
    _seed_colnect_timeout_counter(cap)
    job = _timeout_page_job(page_url)
    error = _timeout_error(page_url)
    result = cap._fail_for_connection_issue(job, error=error)

    assert result.status == "failed"
    assert result.result_summary["rate_limited"] is True
    assert probe_urls == [page_url]
    hold_rows = pool._GetTableData(TABLE_COLNECT_RUNTIME)
    assert len(hold_rows) == 1
    assert hold_rows[0]["hold_until"] in ("", None)
    assert hold_rows[0]["metadata"]["active"] is True
    assert hold_rows[0]["metadata"]["release_pending"] is True
    assert hold_rows[0]["metadata"]["consecutive_120s_timeout_count"] == 3
    assert hold_rows[0]["metadata"]["last_blocked_url"] == page_url
    assert hold_rows[0]["metadata"]["last_timeout_lock_probe_status"] == "rate_limited"
    assert hold_rows[0]["metadata"]["last_timeout_lock_confirmed"] is True
    assert hold_rows[0]["metadata"]["timeout_lock_confirmed"] is True
    assert "confirmation probe reported rate_limited" in hold_rows[0]["metadata"]["last_error"]

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["status"] == "queued"
    assert queued_jobs[0]["required_capability"] == "colnect stamp page"
    assert queued_jobs[0]["metadata"]["colnect"]["connection_retry_count"] == 1
    assert cap.advertised_capabilities() == []


def test_colnect_third_configured_timeout_does_not_set_hold_when_confirmation_probe_succeeds(tmp_path):
    """A reachable Colnect probe should prove the timeout streak was local instability, not a global block."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    page_url = "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/1869/page/11"
    probe_urls: list[str] = []

    def fake_request_get(url, **kwargs):
        probe_urls.append(str(url))
        return FakeResponse("<html><body>Colnect OK</body></html>", status_code=200, url=url)

    cap = ColnectStampPageJobCap(request_get=fake_request_get).bind_worker(worker)
    _seed_colnect_timeout_counter(cap)
    result = cap._fail_for_connection_issue(_timeout_page_job(page_url), error=_timeout_error(page_url))

    assert result.status == "failed"
    assert result.result_summary["connection_issue"] is True
    assert result.result_summary.get("rate_limited") is None
    assert probe_urls == [page_url]
    hold_rows = pool._GetTableData(TABLE_COLNECT_RUNTIME)
    assert len(hold_rows) == 1
    assert hold_rows[0]["hold_until"] in ("", None)
    assert hold_rows[0]["hold_reason"] in ("", None)
    assert hold_rows[0]["metadata"]["active"] is False
    assert hold_rows[0]["metadata"]["release_pending"] is False
    assert hold_rows[0]["metadata"]["consecutive_120s_timeout_count"] == 0
    assert hold_rows[0]["metadata"]["last_timeout_lock_probe_status"] == "accessible"
    assert hold_rows[0]["metadata"]["last_timeout_lock_confirmed"] is False
    assert hold_rows[0]["metadata"]["last_120s_timeout_reset_reason"] == "timeout lock confirmation succeeded"

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["status"] == "queued"
    assert queued_jobs[0]["required_capability"] == "colnect stamp page"
    assert cap.advertised_capabilities()


def test_colnect_third_configured_timeout_does_not_set_hold_when_confirmation_probe_fails(tmp_path):
    """Probe network errors should not be upgraded into a global Colnect lock."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    page_url = "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/1869/page/11"
    probe_urls: list[str] = []

    def fake_request_get(url, **kwargs):
        probe_urls.append(str(url))
        raise RuntimeError("temporary network outage during confirmation")

    cap = ColnectStampPageJobCap(request_get=fake_request_get).bind_worker(worker)
    _seed_colnect_timeout_counter(cap)
    result = cap._fail_for_connection_issue(_timeout_page_job(page_url), error=_timeout_error(page_url))

    assert result.status == "failed"
    assert result.result_summary["connection_issue"] is True
    assert result.result_summary.get("rate_limited") is None
    assert probe_urls == [page_url]
    hold_rows = pool._GetTableData(TABLE_COLNECT_RUNTIME)
    assert len(hold_rows) == 1
    assert hold_rows[0]["metadata"]["active"] is False
    assert hold_rows[0]["metadata"]["release_pending"] is False
    assert hold_rows[0]["metadata"]["consecutive_120s_timeout_count"] == 3
    assert hold_rows[0]["metadata"]["last_timeout_lock_probe_status"] == "probe_failed"
    assert hold_rows[0]["metadata"]["last_timeout_lock_confirmed"] is False

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["status"] == "queued"
    assert queued_jobs[0]["required_capability"] == "colnect stamp page"
    assert cap.advertised_capabilities()


def test_colnect_hold_hides_capabilities_and_short_circuits_claimed_jobs(tmp_path):
    """An active shared hold should hide Colnect capabilities until the eBay schedule releases it."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    request_hits = 0

    def fake_request_get(url, **kwargs):
        nonlocal request_hits
        request_hits += 1
        raise AssertionError("Request should not run while the shared hold is active.")

    cap = ColnectStampPageJobCap(
        request_get=fake_request_get,
    ).bind_worker(worker)
    hold_row = cap._record_global_rate_limit_hold(
        error="status 429",
        trigger_capability="Colnect Stamp Page",
    )

    assert cap.advertised_capabilities() == []
    rendered_logs = _render_logs(worker)
    assert any("Checked Colnect global rate-limit hold for capability" in line for line in rendered_logs)
    assert any("worker will not claim Colnect jobs" in line for line in rendered_logs)
    assert any("Reason: status 429" in line for line in rendered_logs)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Page",
            payload={
                "page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2006",
                "source_page_label": "United States of America 2006",
                "country_key": "225-United_States_of_America",
                "country_name": "United States of America",
                "catalog_year": 2006,
                "year_label": "2006",
            },
        )
    )

    assert request_hits == 0
    assert result.status == "failed"
    assert result.result_summary["rate_limited"] is True
    assert result.result_summary["rate_limit_hold_until"] == str(hold_row["hold_until"] or "")
    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    rendered_logs = _render_logs(worker)
    assert any(
        "Colnect page job skipped because Colnect global rate-limit hold is active until released by 10 Minutes Scheduled Job."
        in line
        for line in rendered_logs
    )
    assert any("Requeueing claimed job dispatcher-job:colnect-stamp-page" in line for line in rendered_logs)


def test_colnect_record_global_rate_limit_hold_preserves_held_at_for_explicit_release(tmp_path):
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_COLNECT_RUNTIME],
        extra_schemas={TABLE_COLNECT_RUNTIME: colnect_runtime_table_schema()},
    )

    cap = ColnectStampPageJobCap().bind_worker(worker)
    first_row = cap._record_global_rate_limit_hold(
        error="first 429",
        trigger_capability="Colnect Stamp Page",
        hold_sec=120,
    )
    second_row = cap._record_global_rate_limit_hold(
        error="second 429",
        trigger_capability="Colnect Stamp Page",
        hold_sec=120,
    )

    assert second_row["metadata"]["held_at"] == first_row["metadata"]["held_at"]
    assert first_row["hold_until"] in ("", None)
    assert second_row["hold_until"] in ("", None)
    assert second_row["metadata"]["hold_count"] == first_row["metadata"]["hold_count"] + 1


def test_colnect_global_hold_probe_uses_blocked_url_before_generic_probe(tmp_path):
    """The release check must probe the URL that actually triggered the 429."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    cap = ColnectStampPageJobCap().bind_worker(worker)
    blocked_url = "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/1869/page/11"
    generic_url = "https://colnect.com/en/stamps/list"
    seen_urls: list[str] = []

    cap._record_global_rate_limit_hold(
        error="status 429",
        trigger_capability="Colnect Stamp Page",
        blocked_url=blocked_url,
    )

    def fake_request_get(url, **kwargs):
        seen_urls.append(url)
        return FakeResponse("<html><body>ok</body></html>", status_code=200, url=url)

    result = cap._probe_global_rate_limit_hold(
        context="10 Minutes Scheduled Job",
        probe_url=generic_url,
        request_get=fake_request_get,
    )

    assert result["status"] == "released"
    assert seen_urls == [generic_url]

    cap._record_global_rate_limit_hold(
        error="status 429 again",
        trigger_capability="Colnect Stamp Page",
        blocked_url=blocked_url,
    )
    seen_urls.clear()

    result = cap._probe_global_rate_limit_hold(
        context="10 Minutes Scheduled Job",
        request_get=fake_request_get,
    )

    assert result["status"] == "released"
    assert seen_urls == [blocked_url]


def test_colnect_lock_status_alert_payload_is_json_safe():
    """Postgres can return datetimes in runtime rows, so alert payloads must serialize cleanly."""
    changed_at = datetime(2026, 4, 16, 12, 0, tzinfo=timezone.utc)

    item = build_lock_status_alert_item(
        source_key="colnect",
        source_label="Colnect",
        lock_key="global-rate-limit",
        current_row={
            "id": "global-rate-limit",
            "scope": "global-rate-limit",
            "hold_until": None,
            "hold_reason": "status 429",
            "updated_at": changed_at,
            "metadata": {"active": True, "last_seen": changed_at},
        },
        previous_row={
            "id": "global-rate-limit",
            "updated_at": changed_at,
            "metadata": {"active": False, "released_at": changed_at},
        },
        current_active=True,
        previous_active=False,
        changed_at=changed_at,
    )

    json.dumps(item["payload"])


def test_colnect_global_lock_writes_dispatcher_alert_on_status_change(tmp_path):
    """The dispatcher should get one alert only when the Colnect lock active state flips."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    cap = ColnectStampPageJobCap().bind_worker(worker)

    cap._record_global_rate_limit_hold(
        error="status 429",
        trigger_capability="Colnect Stamp Page",
    )

    alerts = _lock_alert_rows(pool, "colnect")
    assert len(alerts) == 1
    assert alerts[0]["status"] == "active"
    assert alerts[0]["severity"] == "warning"
    assert alerts[0]["payload"]["lock_key"] == "global-rate-limit"
    assert alerts[0]["payload"]["active"] is True

    cap._record_global_rate_limit_hold(
        error="still 429",
        trigger_capability="Colnect Stamp Page",
    )
    assert len(_lock_alert_rows(pool, "colnect")) == 1

    cap._release_global_rate_limit_hold(reason="manual release")

    alerts = _lock_alert_rows(pool, "colnect")
    assert len(alerts) == 2
    released_alert = next(row for row in alerts if row["status"] == "released")
    assert released_alert["severity"] == "success"
    assert released_alert["payload"]["previous_active"] is True
    assert "manual release" in released_alert["body"]


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
    assert catalog_rows[0]["payload"]["series_id"] == "473001"
    assert catalog_rows[0]["payload"]["series_url"] == (
        "https://colnect.com/en/stamps/list/country/211-Taiwan_China/series/473001-13th_JCC_Asia_International_Postage_Stamp_Exhibition/year/2023"
    )
    assert catalog_rows[0]["payload"]["related_items"] == [
        {
            "title": "Companion Item",
            "item_url": "https://colnect.com/en/stamps/stamp/1300-Companion_Item-Taiwan_China_2023",
            "relation_label": "Companion stamp",
            "colnect_section": "stamps",
            "colnect_kind": "stamp",
            "colnect_id": "1300",
            "item_uid": "colnect-stamp:1300",
        }
    ]

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "colnect stamp image"
    assert queued_jobs[0]["payload"]["stamp_id"] == "1574778"
    assert queued_jobs[0]["priority"] == ColnectStampJobCap.IMAGE_PRIORITY

    logs = _render_logs(worker)
    assert any("event=job-start" in line and "job_kind=listing" in line for line in logs)
    assert any("event=listing-detail-parsed" in line and "stamp_id=1574778" in line for line in logs)
    assert any("event=db-save-catalog-rows" in line and "stamp_ids=1574778" in line for line in logs)
    assert any("event=listing-saved" in line and "stamp_id=1574778" in line for line in logs)
    assert any(
        "event=job-posted" in line and 'capability="Colnect Stamp Image"' in line and "job_id=dispatcher-job:colnect-image:1574778" in line
        for line in logs
    )

def test_colnect_listing_job_uses_cached_html_until_refreshed(tmp_path):
    """Listing jobs should reuse cached detail HTML unless refresh is requested."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    request_urls: list[str] = []
    item_url = "https://colnect.com/en/stamps/stamp/1574778-Republic_of_China_13th_JCC_Asia_International_Postage_Stamp_Exhibition-Taiwan_China_2023"

    def fake_request_get(url, **kwargs):
        request_urls.append(url)
        assert url == item_url
        return FakeResponse(DETAIL_PAGE_HTML, url=url, headers={"Content-Type": "text/html; charset=utf-8"})

    cap = ColnectStampListingJobCap(request_get=fake_request_get).bind_worker(worker)
    payload = {
        "stamp_id": "1574778",
        "item_url": item_url,
        "title": "Republic of China 13th JCC Asia International Postage Stamp Exhibition",
        "image_url": "https://img.colnect.net/items/1574778.jpg",
        "source_page_url": "https://colnect.com/en/stamps/list?country=Taiwan_China",
        "source_page_label": "Taiwan stamps",
        "listing_position": 0,
    }

    first = cap.finish(_job(required_capability="Colnect Stamp Listing", payload=payload))
    assert first.status == "completed"
    assert first.result_summary["item_cache_hit"] is False
    assert first.result_summary["item_fetch_source"] == "network"

    with pool.lock:
        pool._ensure_connection()
        pool.conn.execute(f'DELETE FROM "{TABLE_COLNECT_STAMP_CATALOG}"')
        pool.conn.commit()

    second = cap.finish(_job(required_capability="Colnect Stamp Listing", payload=payload))
    assert second.status == "completed"
    assert second.result_summary["item_cache_hit"] is True
    assert second.result_summary["item_fetch_source"] == "cache"

    with pool.lock:
        pool._ensure_connection()
        pool.conn.execute(f'DELETE FROM "{TABLE_COLNECT_STAMP_CATALOG}"')
        pool.conn.commit()

    third = cap.finish(
        _job(
            required_capability="Colnect Stamp Listing",
            payload={**payload, "refresh_item": True},
        )
    )
    assert third.status == "completed"
    assert third.result_summary["item_cache_hit"] is False
    assert third.result_summary["item_fetch_source"] == "network"

    assert request_urls == [item_url, item_url]
    cached_rows = _web_page_rows_by_source_url(pool)
    cached_row = cached_rows[item_url]
    assert cached_row["provider"] == "colnect_stamps"
    assert cached_row["page_kind"] == "stamp_detail"
    assert cached_row["content_type"] == "text/html; charset=utf-8"
    assert "Republic of China 13th JCC Asia International Postage Stamp Exhibition" in cached_row["html_text"]


def test_colnect_listing_job_marks_stub_image_as_no_image_and_skips_image_job(tmp_path):
    """Listing job should mark shared stub artwork as no-image and not enqueue an image download."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    def fake_request_get(url, **kwargs):
        assert url == "https://colnect.com/en/stamps/stamp/1574083-Cherry_Trees_-_Intl_Eco_Parcel-Personal_Computer_Postage_-_Cherry_Blossoms-United_States_of_America"
        return FakeResponse(
            """
            <html>
              <head>
                <title>Cherry Trees - Intl Eco Parcel</title>
                <meta property="og:image" content="https://i.colnect.net/items/full/none-stamps.jpg" />
              </head>
              <body>
                <table>
                  <tr><th>Country</th><td>United States of America</td></tr>
                  <tr><th>Issued on</th><td>2022</td></tr>
                </table>
              </body>
            </html>
            """,
            url=url,
        )

    cap = ColnectStampListingJobCap(
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Listing",
            payload={
                "stamp_id": "1574083",
                "item_url": "https://colnect.com/en/stamps/stamp/1574083-Cherry_Trees_-_Intl_Eco_Parcel-Personal_Computer_Postage_-_Cherry_Blossoms-United_States_of_America",
                "title": "Cherry Trees - Intl Eco Parcel",
                "image_url": "https://i.colnect.net/items/full/none-stamps.jpg",
                "source_page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2022/page/27",
                "source_page_label": "United States of America 2022",
                "listing_position": 0,
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_job_queued"] is False
    assert result.result_summary["image_job_status"] == "no_image"

    catalog_rows = pool._GetTableData(TABLE_COLNECT_STAMP_CATALOG)
    assert len(catalog_rows) == 1
    assert catalog_rows[0]["image_url"] == ""
    assert catalog_rows[0]["image_local_path"] == ""
    assert catalog_rows[0]["payload"]["no_image"] is True

    queued_jobs = pool._GetTableData(TABLE_JOBS)
    assert queued_jobs == []


def test_colnect_queue_image_job_keeps_default_priority_for_external_host(tmp_path):
    """Direct image jobs with off-host URLs should keep the default image priority."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    ensure_dispatcher_tables(pool, [TABLE_JOBS])
    worker = FakeWorker(pool)
    cap = ColnectStampListingJobCap().bind_worker(worker)

    queued = cap._queue_image_job(
        stamp_id="1574778",
        image_url="https://example.com/colnect-like-image.jpg",
        catalog_year=2023,
        country_name="Taiwan, China",
        issue_date="2023-11-30",
    )

    assert queued["queued"] is True
    queued_jobs = pool._GetTableData(TABLE_JOBS) or []
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["required_capability"] == "colnect stamp image"
    assert queued_jobs[0]["priority"] == ColnectStampJobCap.IMAGE_PRIORITY


def test_colnect_image_jobs_run_after_page_and_listing_jobs():
    """Colnect image jobs should wait behind page and listing work in the dispatcher."""
    assert ColnectStampJobCap.YEAR_PRIORITY < ColnectStampJobCap.PAGE_PRIORITY
    assert ColnectStampJobCap.PAGE_PRIORITY < ColnectStampJobCap.LISTING_PRIORITY < ColnectStampJobCap.IMAGE_PRIORITY


def test_colnect_build_row_sanitizes_noisy_fields():
    """Persisted rows should not keep Colnect noise strings in plain text fields."""
    row = ColnectStampListingJobCap()._build_row(
        {
            "stamp_id": "1586106",
            "title": "Dahlias",
            "country_name": "United States of America",
            "issue_date": "2025-04-26",
            "catalog_year": 2025,
            "face_value": "ColnectIsBest",
            "catalog_codes": "Stamp Number US 5995 Stanley Gibbons US 6619 Colnect codes US 2025.04.26-01d Yvert et Tellier Unlisted",
            "perforation": "VisitColnectCom",
        }
    )
    assert row["face_value"] == ""
    assert row["perforation"] == ""
    assert row["catalog_codes"] == "5995, Sg.6619, Yt.Unlisted, Col.2025.04.26-01d"


def test_colnect_build_row_repairs_country_identity_from_source_context():
    """Persisted rows should recover country identity from source context when noisy fields leak through."""
    row = ColnectStampListingJobCap()._build_row(
        {
            "stamp_id": "1664227",
            "title": "Stamp catalog : Stamp › Lowrider Automobiles",
            "country_name": "CopyWrong",
            "country_code": "COPYWRONG",
            "series_name": "from colnect.com",
            "source_page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2026/page/4",
            "source_page_label": "United States of America 2026",
            "issue_date": "2026-03-12",
            "catalog_year": 2026,
        }
    )
    assert row["title"] == "Lowrider Automobiles"
    assert row["country_name"] == "United States of America"
    assert row["country_code"] == "UNITED-STATES-OF-AMERICA"
    assert row["series_name"] == ""


def test_colnect_build_row_marks_stub_image_as_no_image():
    """Persisted rows should turn Colnect's shared no-image artwork into a no-image flag."""
    row = ColnectStampListingJobCap()._build_row(
        {
            "stamp_id": "1574083",
            "title": "Cherry Trees - Intl Eco Parcel",
            "image_url": "https://i.colnect.net/items/full/none-stamps.jpg",
            "image_local_path": "/tmp/fake-stub.jpg",
            "payload": {"no_image": True},
        }
    )
    assert row["image_url"] == ""
    assert row["image_local_path"] == ""
    assert row["payload"]["no_image"] is True


def test_colnect_build_row_reuses_shared_placeholder_local_path(tmp_path):
    """Placeholder rows should point at one shared local image instead of creating per-stamp copies."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)
    ensure_dispatcher_tables(
        pool,
        [TABLE_COLNECT_STAMP_CATALOG],
        extra_schemas={TABLE_COLNECT_STAMP_CATALOG: colnect_stamp_catalog_table_schema()},
    )
    legacy_placeholder = tmp_path / "legacy-placeholder.jpg"
    legacy_placeholder.write_bytes(b"colnect-placeholder")
    pool._Insert(
        TABLE_COLNECT_STAMP_CATALOG,
        {
            "id": "colnect:seed-placeholder",
            "stamp_id": "seed-placeholder",
            "title": "Seed Placeholder",
            "country_name": "United States of America",
            "country_code": "UNITED-STATES-OF-AMERICA",
            "series_name": "",
            "issue_date": "",
            "catalog_year": 1900,
            "face_value": "",
            "currency": "",
            "catalog_codes": "",
            "colors": "",
            "themes": "",
            "perforation": "",
            "format": "Stamp",
            "designer": "",
            "printer": "",
            "description": "",
            "item_url": "https://colnect.com/en/stamps/stamp/seed-placeholder",
            "image_url": "https://i.colnect.net/colnect_sm.png",
            "image_local_path": str(legacy_placeholder),
            "source_page_url": "",
            "source_page_label": "",
            "listing_position": 0,
            "provider": "colnect_stamps",
            "payload": {"no_image": True},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    cap = ColnectStampListingJobCap(media_root=str(tmp_path / "media")).bind_worker(worker)
    row = cap._build_row(
        {
            "stamp_id": "1574083",
            "title": "Cherry Trees - Intl Eco Parcel",
            "image_url": "https://i.colnect.net/colnect_sm.png",
            "payload": {},
        }
    )

    shared_placeholder = (tmp_path / "media" / "_shared" / "colnect-missing-image.jpg").resolve()
    assert row["image_url"] == ""
    assert row["image_local_path"] == str(shared_placeholder)
    assert row["payload"]["no_image"] is True
    assert row["payload"]["image_local_path"] == str(shared_placeholder)
    assert shared_placeholder.exists()
    assert shared_placeholder.read_bytes() == b"colnect-placeholder"


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
            "catalog_codes": "Mi:TW 1574778, Sn:TW 1300",
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
            content=b"\xff\xd8\xffcolnect",
            headers={"Content-Type": "image/jpeg"},
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
    assert Path(updated_row["image_local_path"]).suffix == ".jpg"
    assert updated_row["image_local_path"].endswith(
        "/TaiwanChina/2023/TaiwanChina-1300.jpg"
    )


def test_colnect_image_job_marks_stub_image_as_no_image(tmp_path):
    """Image job should skip Colnect's shared no-image artwork and mark the row accordingly."""
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
            "id": "colnect:1574083",
            "stamp_id": "1574083",
            "title": "Cherry Trees - Intl Eco Parcel",
            "country_name": "United States of America",
            "country_code": "UNITED-STATES-OF-AMERICA",
            "series_name": "",
            "issue_date": "",
            "catalog_year": 2022,
            "face_value": "",
            "currency": "",
            "catalog_codes": "",
            "colors": "",
            "themes": "",
            "perforation": "",
            "format": "Stamp",
            "designer": "",
            "printer": "",
            "description": "",
            "item_url": "https://colnect.com/en/stamps/stamp/1574083-Cherry_Trees_-_Intl_Eco_Parcel-Personal_Computer_Postage_-_Cherry_Blossoms-United_States_of_America",
            "image_url": "https://i.colnect.net/items/full/none-stamps.jpg",
            "image_local_path": str(tmp_path / "old-stub.jpg"),
            "source_page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2022/page/27",
            "source_page_label": "United States of America 2022",
            "listing_position": 0,
            "provider": "colnect_stamps",
            "payload": {},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        raise AssertionError("stub image should not be downloaded")

    cap = ColnectStampImageJobCap(
        media_root=str(tmp_path / "media"),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Image",
            payload={
                "stamp_id": "1574083",
                "catalog_year": 2022,
                "image_url": "https://i.colnect.net/items/full/none-stamps.jpg",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["no_image"] is True

    updated_row = pool._GetTableData(TABLE_COLNECT_STAMP_CATALOG, {"stamp_id": "1574083"})[0]
    assert updated_row["image_url"] == ""
    assert updated_row["image_local_path"] == ""
    assert updated_row["payload"]["no_image"] is True


def test_colnect_image_job_marks_stub_image_as_no_image_reuses_shared_placeholder(tmp_path):
    """Placeholder image jobs should reuse one shared local image path when an existing copy is available."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_COLNECT_STAMP_CATALOG],
        extra_schemas={TABLE_COLNECT_STAMP_CATALOG: colnect_stamp_catalog_table_schema()},
    )
    legacy_placeholder = tmp_path / "legacy-placeholder.jpg"
    legacy_placeholder.write_bytes(b"colnect-placeholder")
    pool._Insert(
        TABLE_COLNECT_STAMP_CATALOG,
        {
            "id": "colnect:seed-placeholder",
            "stamp_id": "seed-placeholder",
            "title": "Seed Placeholder",
            "country_name": "United States of America",
            "country_code": "UNITED-STATES-OF-AMERICA",
            "series_name": "",
            "issue_date": "",
            "catalog_year": 1900,
            "face_value": "",
            "currency": "",
            "catalog_codes": "",
            "colors": "",
            "themes": "",
            "perforation": "",
            "format": "Stamp",
            "designer": "",
            "printer": "",
            "description": "",
            "item_url": "https://colnect.com/en/stamps/stamp/seed-placeholder",
            "image_url": "https://i.colnect.net/colnect_sm.png",
            "image_local_path": str(legacy_placeholder),
            "source_page_url": "",
            "source_page_label": "",
            "listing_position": 0,
            "provider": "colnect_stamps",
            "payload": {"no_image": True},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )
    pool._Insert(
        TABLE_COLNECT_STAMP_CATALOG,
        {
            "id": "colnect:1574083",
            "stamp_id": "1574083",
            "title": "Cherry Trees - Intl Eco Parcel",
            "country_name": "United States of America",
            "country_code": "UNITED-STATES-OF-AMERICA",
            "series_name": "",
            "issue_date": "",
            "catalog_year": 2022,
            "face_value": "",
            "currency": "",
            "catalog_codes": "",
            "colors": "",
            "themes": "",
            "perforation": "",
            "format": "Stamp",
            "designer": "",
            "printer": "",
            "description": "",
            "item_url": "https://colnect.com/en/stamps/stamp/1574083-Cherry_Trees_-_Intl_Eco_Parcel-Personal_Computer_Postage_-_Cherry_Blossoms-United_States_of_America",
            "image_url": "https://i.colnect.net/items/full/none-stamps.jpg",
            "image_local_path": "",
            "source_page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2022/page/27",
            "source_page_label": "United States of America 2022",
            "listing_position": 0,
            "provider": "colnect_stamps",
            "payload": {},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        raise AssertionError("stub image should not be downloaded")

    cap = ColnectStampImageJobCap(
        media_root=str(tmp_path / "media"),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Image",
            payload={
                "stamp_id": "1574083",
                "catalog_year": 2022,
                "image_url": "https://i.colnect.net/items/full/none-stamps.jpg",
            },
        )
    )
    assert result.status == "completed"
    shared_placeholder = (tmp_path / "media" / "_shared" / "colnect-missing-image.jpg").resolve()
    assert result.result_summary["no_image"] is True
    assert result.result_summary["image_local_path"] == str(shared_placeholder)

    updated_row = pool._GetTableData(TABLE_COLNECT_STAMP_CATALOG, {"stamp_id": "1574083"})[0]
    assert updated_row["image_url"] == ""
    assert updated_row["image_local_path"] == str(shared_placeholder)
    assert updated_row["payload"]["no_image"] is True
    assert updated_row["payload"]["image_local_path"] == str(shared_placeholder)
    assert shared_placeholder.exists()
    assert shared_placeholder.read_bytes() == b"colnect-placeholder"


def test_colnect_image_job_marks_data_image_as_no_image(tmp_path):
    """Image job should skip inline data-image placeholders and mark the row accordingly."""
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
            "id": "colnect:1568315",
            "stamp_id": "1568315",
            "title": "Placeholder",
            "country_name": "United States of America",
            "country_code": "UNITED-STATES-OF-AMERICA",
            "series_name": "",
            "issue_date": "",
            "catalog_year": 2025,
            "face_value": "",
            "currency": "",
            "catalog_codes": "",
            "colors": "",
            "themes": "",
            "perforation": "",
            "format": "Stamp",
            "designer": "",
            "printer": "",
            "description": "",
            "item_url": "https://colnect.com/en/stamps/stamp/1568315-Placeholder-United_States_of_America",
            "image_url": "data:image/gif;base64,R0lGODlhAQABAAAAACw=",
            "image_local_path": str(tmp_path / "old-inline-stub.jpg"),
            "source_page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2025",
            "source_page_label": "United States of America 2025",
            "listing_position": 0,
            "provider": "colnect_stamps",
            "payload": {},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        raise AssertionError("inline data-image placeholder should not be downloaded")

    cap = ColnectStampImageJobCap(
        media_root=str(tmp_path / "media"),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Image",
            payload={
                "stamp_id": "1568315",
                "catalog_year": 2025,
                "image_url": "data:image/gif;base64,R0lGODlhAQABAAAAACw=",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["no_image"] is True

    updated_row = pool._GetTableData(TABLE_COLNECT_STAMP_CATALOG, {"stamp_id": "1568315"})[0]
    assert updated_row["image_url"] == ""
    assert updated_row["image_local_path"] == ""
    assert updated_row["payload"]["no_image"] is True


def test_colnect_image_job_prefers_catalog_http_image_over_placeholder_payload(tmp_path):
    """A stale placeholder payload should not blank a refreshed catalog row with a real image URL."""
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
            "id": "colnect:1568315",
            "stamp_id": "1568315",
            "title": "Placeholder",
            "country_name": "United States of America",
            "country_code": "UNITED-STATES-OF-AMERICA",
            "series_name": "",
            "issue_date": "",
            "catalog_year": 2025,
            "face_value": "",
            "currency": "",
            "catalog_codes": "Col.1568315",
            "colors": "",
            "themes": "",
            "perforation": "",
            "format": "Stamp",
            "designer": "",
            "printer": "",
            "description": "",
            "item_url": "https://colnect.com/en/stamps/stamp/1568315-Placeholder-United_States_of_America",
            "image_url": "https://img.colnect.net/items/1568315-large.jpg",
            "image_local_path": "",
            "source_page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2025",
            "source_page_label": "United States of America 2025",
            "listing_position": 0,
            "provider": "colnect_stamps",
            "payload": {},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        assert url == "https://img.colnect.net/items/1568315-large.jpg"
        return FakeResponse(
            status_code=200,
            url=url,
            content=b"\xff\xd8\xffcolnect",
            headers={"Content-Type": "image/jpeg"},
        )

    cap = ColnectStampImageJobCap(
        media_root=str(tmp_path / "media"),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Image",
            payload={
                "stamp_id": "1568315",
                "catalog_year": 2025,
                "image_url": "data:image/gif;base64,R0lGODlhAQABAAAAACw=",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_url"] == "https://img.colnect.net/items/1568315-large.jpg"
    assert result.result_summary["image_local_path"]

    updated_row = pool._GetTableData(TABLE_COLNECT_STAMP_CATALOG, {"stamp_id": "1568315"})[0]
    assert updated_row["image_url"] == "https://img.colnect.net/items/1568315-large.jpg"
    assert updated_row["image_local_path"]
    assert Path(updated_row["image_local_path"]).exists()


def test_colnect_image_job_overwrites_existing_colnect_logo_file(tmp_path):
    """A refresh should replace an existing tiny Colnect logo file with the real stamp image."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_COLNECT_STAMP_CATALOG],
        extra_schemas={TABLE_COLNECT_STAMP_CATALOG: colnect_stamp_catalog_table_schema()},
    )
    media_root = tmp_path / "media"
    target_path = media_root / "UnitedStatesOfAmerica" / "1851" / "UnitedStatesOfAmerica-Col.1538515.jpg"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        b"\x00\x00\x00\rIHDR"
        b"\x00\x00\x00Z"
        b"\x00\x00\x00\x1f"
        b"\x08\x03\x00\x00\x00"
        b"placeholder"
    )

    pool._Insert(
        TABLE_COLNECT_STAMP_CATALOG,
        {
            "id": "colnect:1538515",
            "stamp_id": "1538515",
            "title": "George Washington",
            "country_name": "United States of America",
            "country_code": "UNITED-STATES-OF-AMERICA",
            "series_name": "",
            "issue_date": "1851-07-01",
            "catalog_year": 1851,
            "face_value": "",
            "currency": "",
            "catalog_codes": "Col.1538515",
            "colors": "",
            "themes": "",
            "perforation": "",
            "format": "Stamp",
            "designer": "",
            "printer": "",
            "description": "",
            "item_url": "https://colnect.com/en/stamps/stamp/1538515-George_Washington_1732-1799_First_President_of_the_USA-1851-1856_Franklin_Jefferson_Washington_imperforate-United_States_of_America",
            "image_url": "https://i.colnect.net/f/23375/548/George_Washington.jpg",
            "image_local_path": str(target_path),
            "source_page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/1851/page/6",
            "source_page_label": "United States of America 1851",
            "listing_position": 0,
            "provider": "colnect_stamps",
            "payload": {},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        assert url == "https://i.colnect.net/f/23375/548/George_Washington.jpg"
        return FakeResponse(
            status_code=200,
            url=url,
            content=b"\xff\xd8\xffreal-stamp",
            headers={"Content-Type": "image/jpeg"},
        )

    cap = ColnectStampImageJobCap(
        media_root=str(media_root),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Image",
            payload={
                "stamp_id": "1538515",
                "catalog_year": 1851,
                "image_url": "https://i.colnect.net/f/23375/548/George_Washington.jpg",
            },
        )
    )
    assert result.status == "completed"
    assert target_path.read_bytes() == b"\xff\xd8\xffreal-stamp"


def test_colnect_image_job_replaces_thumbnail_file_with_original(tmp_path):
    """A stored thumbnail image should be overwritten by the original Colnect file."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_COLNECT_STAMP_CATALOG],
        extra_schemas={TABLE_COLNECT_STAMP_CATALOG: colnect_stamp_catalog_table_schema()},
    )
    media_root = tmp_path / "media"
    target_path = media_root / "UnitedStatesOfAmerica" / "1857" / "UnitedStatesOfAmerica-Col.1109245.jpg"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(b"thumbnail-bytes")

    pool._Insert(
        TABLE_COLNECT_STAMP_CATALOG,
        {
            "id": "colnect:1109245",
            "stamp_id": "1109245",
            "title": "George Washington",
            "country_name": "United States of America",
            "country_code": "UNITED-STATES-OF-AMERICA",
            "series_name": "",
            "issue_date": "",
            "catalog_year": 1857,
            "face_value": "",
            "currency": "",
            "catalog_codes": "Col.1109245",
            "colors": "",
            "themes": "",
            "perforation": "",
            "format": "Stamp",
            "designer": "",
            "printer": "",
            "description": "",
            "item_url": "https://colnect.com/en/stamps/stamp/1109245-George_Washington-United_States_of_America",
            "image_url": "https://i.colnect.net/t/22058/049/George-Washington.jpg",
            "image_local_path": str(target_path),
            "source_page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/1857",
            "source_page_label": "United States of America 1857",
            "listing_position": 0,
            "provider": "colnect_stamps",
            "payload": {},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        assert url == "https://i.colnect.net/f/22058/049/George-Washington.jpg"
        return FakeResponse(
            status_code=200,
            url=url,
            content=b"\xff\xd8\xfforiginal-stamp",
            headers={"Content-Type": "image/jpeg"},
        )

    cap = ColnectStampImageJobCap(
        media_root=str(media_root),
        request_get=fake_request_get,
    ).bind_worker(worker)

    result = cap.finish(
        _job(
            required_capability="Colnect Stamp Image",
            payload={
                "stamp_id": "1109245",
                "catalog_year": 1857,
                "image_url": "https://i.colnect.net/t/22058/049/George-Washington.jpg",
            },
        )
    )
    assert result.status == "completed"
    assert result.result_summary["image_url"] == "https://i.colnect.net/f/22058/049/George-Washington.jpg"
    assert target_path.read_bytes() == b"\xff\xd8\xfforiginal-stamp"

    updated_row = pool._GetTableData(TABLE_COLNECT_STAMP_CATALOG, {"stamp_id": "1109245"})[0]
    assert updated_row["image_url"] == "https://i.colnect.net/f/22058/049/George-Washington.jpg"
    assert updated_row["image_local_path"] == str(target_path)


def test_colnect_image_job_resolves_blank_country_name(tmp_path):
    """Image job should recover the country folder from Colnect page metadata when blank."""
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
            "id": "colnect:1651931",
            "stamp_id": "1651931",
            "title": "Muhammad Ali, Boxer",
            "country_name": "",
            "country_code": "",
            "series_name": "Muhammad Ali, Boxer",
            "issue_date": "2026-01-15",
            "catalog_year": 2026,
            "face_value": "",
            "currency": "",
            "catalog_codes": "6051, Col.2026.01.15-01b",
            "colors": "",
            "themes": "",
            "perforation": "",
            "format": "Stamp",
            "designer": "",
            "printer": "",
            "description": "",
            "item_url": "https://colnect.com/en/stamps/stamp/1651931-Muhammad_Ali_Boxer-Muhammad_Ali_Boxer_2026-United_States_of_America",
            "image_url": "https://img.colnect.net/items/1651931-large.jpg",
            "image_local_path": "",
            "source_page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2026",
            "source_page_label": "United States of America 2026",
            "listing_position": 0,
            "provider": "colnect_stamps",
            "payload": {},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        assert url == "https://img.colnect.net/items/1651931-large.jpg"
        return FakeResponse(
            status_code=200,
            url=url,
            content=b"\xff\xd8\xffcolnect",
            headers={"Content-Type": "image/jpeg"},
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
                "stamp_id": "1651931",
                "catalog_year": 2026,
                "image_url": "https://img.colnect.net/items/1651931-large.jpg",
            },
        )
    )
    assert result.status == "completed"

    updated_row = pool._GetTableData(TABLE_COLNECT_STAMP_CATALOG, {"stamp_id": "1651931"})[0]
    assert updated_row["image_local_path"].endswith(
        "/UnitedStatesOfAmerica/2026/UnitedStatesOfAmerica-6051.jpg"
    )


def test_colnect_image_job_uses_colnect_id_when_catalog_codes_missing(tmp_path):
    """Image job should fall back to the Colnect stamp id when no catalog code is available."""
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
            "id": "colnect:1575724",
            "stamp_id": "1575724",
            "title": "The Appalachian Trail",
            "country_name": "United States of America",
            "country_code": "UNITED-STATES-OF-AMERICA",
            "series_name": "The Appalachian Trail 2025",
            "issue_date": "2025-02-28",
            "catalog_year": 2025,
            "face_value": "",
            "currency": "",
            "catalog_codes": "",
            "colors": "",
            "themes": "",
            "perforation": "",
            "format": "Stamp",
            "designer": "",
            "printer": "",
            "description": "",
            "item_url": "https://colnect.com/en/stamps/stamp/1575724-The_Appalachian_Trail-The_Appalachian_Trail_2025-United_States_of_America",
            "image_url": "https://img.colnect.net/items/1575724-large.jpg",
            "image_local_path": "",
            "source_page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2025/page/2",
            "source_page_label": "United States of America 2025",
            "listing_position": 0,
            "provider": "colnect_stamps",
            "payload": {},
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
        },
    )

    def fake_request_get(url, **kwargs):
        assert url == "https://img.colnect.net/items/1575724-large.jpg"
        return FakeResponse(
            status_code=200,
            url=url,
            content=b"\xff\xd8\xffcolnect",
            headers={"Content-Type": "image/jpeg"},
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
                "stamp_id": "1575724",
                "catalog_year": 2025,
                "image_url": "https://img.colnect.net/items/1575724-large.jpg",
            },
        )
    )
    assert result.status == "completed"

    updated_row = pool._GetTableData(TABLE_COLNECT_STAMP_CATALOG, {"stamp_id": "1575724"})[0]
    assert updated_row["image_local_path"].endswith(
        "/UnitedStatesOfAmerica/2025/UnitedStatesOfAmerica-Col.1575724.jpg"
    )


def test_colnect_image_job_appends_stamp_id_for_filename_collisions(tmp_path):
    """Image job should avoid overwriting different stamps that share the same preferred code."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_COLNECT_STAMP_CATALOG],
        extra_schemas={TABLE_COLNECT_STAMP_CATALOG: colnect_stamp_catalog_table_schema()},
    )
    common = {
        "country_name": "United States of America",
        "country_code": "UNITED-STATES-OF-AMERICA",
        "catalog_year": 2026,
        "face_value": "",
        "currency": "",
        "colors": "",
        "themes": "",
        "perforation": "",
        "format": "Stamp",
        "designer": "",
        "printer": "",
        "description": "",
        "source_page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2026",
        "source_page_label": "United States of America 2026",
        "listing_position": 0,
        "provider": "colnect_stamps",
        "payload": {},
        "created_at": utcnow_iso(),
        "updated_at": utcnow_iso(),
    }
    pool._Insert(
        TABLE_COLNECT_STAMP_CATALOG,
        {
            **common,
            "id": "colnect:1651923",
            "stamp_id": "1651923",
            "title": "Love Birds",
            "series_name": "Love Birds",
            "issue_date": "2026-01-13",
            "catalog_codes": "Mi.Unlisted, Col.2026.01.13-01e",
            "item_url": "https://colnect.com/en/stamps/stamp/1651923-Love_Birds-Love_Birds_2026-United_States_of_America",
            "image_url": "https://img.colnect.net/items/1651923-large.jpg",
            "image_local_path": "",
        },
    )
    pool._Insert(
        TABLE_COLNECT_STAMP_CATALOG,
        {
            **common,
            "id": "colnect:1651929",
            "stamp_id": "1651929",
            "title": "Muhammad Ali, Boxer",
            "series_name": "Muhammad Ali, Boxer",
            "issue_date": "2026-01-15",
            "catalog_codes": "Mi.Unlisted, Col.2026.01.15-01c",
            "item_url": "https://colnect.com/en/stamps/stamp/1651929-Muhammad_Ali_Boxer-Muhammad_Ali_Boxer_2026-United_States_of_America",
            "image_url": "https://img.colnect.net/items/1651929-large.jpg",
            "image_local_path": "",
        },
    )

    def fake_request_get(url, **kwargs):
        assert url == "https://img.colnect.net/items/1651929-large.jpg"
        return FakeResponse(
            status_code=200,
            url=url,
            content=b"\xff\xd8\xffcolnect",
            headers={"Content-Type": "image/jpeg"},
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
                "stamp_id": "1651929",
                "catalog_year": 2026,
                "image_url": "https://img.colnect.net/items/1651929-large.jpg",
            },
        )
    )
    assert result.status == "completed"

    updated_row = pool._GetTableData(TABLE_COLNECT_STAMP_CATALOG, {"stamp_id": "1651929"})[0]
    assert updated_row["image_local_path"].endswith(
        "/UnitedStatesOfAmerica/2026/UnitedStatesOfAmerica-Mi.Unlisted-1651929.jpg"
    )


def test_colnect_image_job_uses_colnect_id_for_blank_code_rows(tmp_path):
    """Blank-code image filenames should use the Colnect stamp id instead of a title token."""
    pool = SQLitePool("dispatcher_pool", "dispatcher pool", str(tmp_path / "dispatcher.sqlite"))
    worker = FakeWorker(pool)

    ensure_dispatcher_tables(
        pool,
        [TABLE_COLNECT_STAMP_CATALOG],
        extra_schemas={TABLE_COLNECT_STAMP_CATALOG: colnect_stamp_catalog_table_schema()},
    )
    common = {
        "country_name": "United States of America",
        "country_code": "UNITED-STATES-OF-AMERICA",
        "catalog_year": 2025,
        "face_value": "",
        "currency": "",
        "catalog_codes": "",
        "colors": "",
        "themes": "",
        "perforation": "",
        "format": "Stamp",
        "designer": "",
        "printer": "",
        "description": "",
        "source_page_url": "https://colnect.com/en/stamps/list/country/225-United_States_of_America/year/2025/page/4",
        "source_page_label": "United States of America 2025",
        "listing_position": 0,
        "provider": "colnect_stamps",
        "payload": {},
        "created_at": utcnow_iso(),
        "updated_at": utcnow_iso(),
    }
    pool._Insert(
        TABLE_COLNECT_STAMP_CATALOG,
        {
            **common,
            "id": "colnect:1577815",
            "stamp_id": "1577815",
            "title": "Sassafras Leaf",
            "series_name": "Vibrant Leaves 2025",
            "issue_date": "2025-03-14",
            "item_url": "https://colnect.com/en/stamps/stamp/1577815-Sassafras_Leaf-Vibrant_Leaves_2025-United_States_of_America",
            "image_url": "https://img.colnect.net/items/1577815-large.jpg",
            "image_local_path": "",
        },
    )
    pool._Insert(
        TABLE_COLNECT_STAMP_CATALOG,
        {
            **common,
            "id": "colnect:1577821",
            "stamp_id": "1577821",
            "title": "Sassafras Leaf",
            "series_name": "Vibrant Leaves 2025",
            "issue_date": "2025-03-14",
            "item_url": "https://colnect.com/en/stamps/stamp/1577821-Sasafras_Leaf-Vibrant_Leaves_2025-United_States_of_America",
            "image_url": "https://img.colnect.net/items/1577821-large.jpg",
            "image_local_path": "",
        },
    )

    def fake_request_get(url, **kwargs):
        assert url == "https://img.colnect.net/items/1577821-large.jpg"
        return FakeResponse(
            status_code=200,
            url=url,
            content=b"\xff\xd8\xffcolnect",
            headers={"Content-Type": "image/jpeg"},
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
                "stamp_id": "1577821",
                "catalog_year": 2025,
                "image_url": "https://img.colnect.net/items/1577821-large.jpg",
            },
        )
    )
    assert result.status == "completed"

    updated_row = pool._GetTableData(TABLE_COLNECT_STAMP_CATALOG, {"stamp_id": "1577821"})[0]
    assert updated_row["image_local_path"].endswith(
        "/UnitedStatesOfAmerica/2025/UnitedStatesOfAmerica-Col.1577821.jpg"
    )
