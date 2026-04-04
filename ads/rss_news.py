"""
RSS News module for `ads.rss_news`.

ADS supplies collection agents, job capabilities, and normalized market and filing
datasets for the wider FinMAS workspace.

Core types exposed here include `RSSNewsJobCap`, which carry the main behavior or state
managed by this module.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any, Callable, Dict, Iterable, List, Mapping
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests

from ads.jobcap import JobCap
from ads.models import JobDetail, JobResult
from ads.schema import TABLE_NEWS


RequestGetter = Callable[..., Any]

_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _local_name(tag: Any) -> str:
    """Internal helper to return the local name."""
    text = str(tag or "")
    return text.split("}", 1)[-1].strip().lower()


def _element_text(element: ET.Element | None) -> str:
    """Internal helper for element text."""
    if element is None:
        return ""
    return "".join(part for part in element.itertext() if part).strip()


def _find_child_text(element: ET.Element, names: Iterable[str]) -> str:
    """Internal helper to find the child text."""
    wanted = {str(name or "").strip().lower() for name in names if str(name or "").strip()}
    if not wanted:
        return ""
    for child in list(element):
        if _local_name(child.tag) in wanted:
            text = _element_text(child)
            if text:
                return text
    return ""


def _find_link(element: ET.Element) -> str:
    """Internal helper to find the link."""
    for child in list(element):
        if _local_name(child.tag) != "link":
            continue
        href = str(child.attrib.get("href") or "").strip()
        rel = str(child.attrib.get("rel") or "").strip().lower()
        if href and rel in {"", "alternate"}:
            return href
        text = _element_text(child)
        if text:
            return text
    return ""


def _clean_text(value: Any) -> str:
    """Internal helper for clean text."""
    text = unescape(str(value or "").strip())
    if not text:
        return ""
    text = _TAG_PATTERN.sub(" ", text)
    return _WHITESPACE_PATTERN.sub(" ", text).strip()


def _parse_timestamp(value: Any) -> str | None:
    """Internal helper to parse the timestamp."""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _infer_feed_source(url: Any) -> str:
    """Internal helper to return the infer feed source."""
    text = str(url or "").strip().lower()
    if "sec.gov" in text:
        return "SEC"
    if "cftc.gov" in text:
        return "CFTC"
    if "bls.gov" in text:
        return "BLS"
    hostname = urlparse(text).netloc.split(":")[0].strip()
    return hostname or "RSS"


def _normalize_feed_entries(value: Any) -> List[Dict[str, str]]:
    """Internal helper to normalize the feed entries."""
    if value is None:
        return []
    if isinstance(value, Mapping):
        entries = [value]
    elif isinstance(value, (list, tuple)):
        entries = list(value)
    else:
        entries = [value]

    normalized: List[Dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in entries:
        if isinstance(entry, Mapping):
            source = str(entry.get("source") or entry.get("name") or entry.get("label") or "").strip()
            url = str(entry.get("url") or entry.get("feed_url") or "").strip()
        else:
            source = ""
            url = str(entry or "").strip()
        if not url:
            continue
        source = source or _infer_feed_source(url)
        key = (source.lower(), url)
        if key in seen:
            continue
        seen.add(key)
        normalized.append({"source": source, "url": url})
    return normalized


def _news_row_id(*, source: str, feed_url: str, guid: str, link: str, published_at: str | None, headline: str) -> str:
    """Internal helper for news row ID."""
    digest_input = "||".join(
        [
            str(source or "").strip(),
            str(feed_url or "").strip(),
            str(guid or "").strip(),
            str(link or "").strip(),
            str(published_at or "").strip(),
            str(headline or "").strip(),
        ]
    )
    digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
    return f"ads-news:{digest}"


class RSSNewsJobCap(JobCap):
    """Job capability implementation for RSS news workflows."""
    DEFAULT_NAME = "RSS News"
    DEFAULT_USER_AGENT = "FinMAS RSSNewsJobCap/1.0"
    DEFAULT_FEEDS = (
        {"source": "SEC", "url": "https://www.sec.gov/news/pressreleases.rss"},
        {"source": "CFTC", "url": "https://www.cftc.gov/RSS/RSSGP/rssgp.xml"},
        {"source": "BLS", "url": "https://www.bls.gov/feed/bls_latest.rss"},
    )

    def __init__(
        self,
        name: str = DEFAULT_NAME,
        *,
        feeds: Any = None,
        timeout_sec: float = 20.0,
        user_agent: str = DEFAULT_USER_AGENT,
        request_get: RequestGetter | None = None,
        source: str = "",
    ):
        """Initialize the RSS news job cap."""
        super().__init__(
            name=name,
            source=source or f"{self.__class__.__module__}:{self.__class__.__name__}",
        )
        configured_feeds = _normalize_feed_entries(feeds)
        self.feeds = configured_feeds or _normalize_feed_entries(self.DEFAULT_FEEDS)
        self.timeout_sec = max(float(timeout_sec or 20.0), 1.0)
        self.user_agent = str(user_agent or self.DEFAULT_USER_AGENT).strip() or self.DEFAULT_USER_AGENT
        self.request_get = request_get or requests.get

    def check_environment(self) -> tuple[bool, str]:
        """Handle check environment for the RSS news job cap."""
        if not self.feeds:
            return False, "at least one RSS feed URL is required."
        if not callable(self.request_get):
            return False, "RSS request client is not callable."
        for feed in self.feeds:
            feed_url_ready, feed_url_reason = self.check_url_configured(
                feed.get("url"),
                label=f"RSS feed URL for {feed.get('source') or 'feed'}",
            )
            if not feed_url_ready:
                return False, feed_url_reason
        return True, ""

    def finish(self, job: JobDetail) -> JobResult:
        """Handle finish for the RSS news job cap."""
        payload = job.payload if isinstance(job.payload, Mapping) else {}
        configured_feeds = _normalize_feed_entries(payload.get("feeds"))
        if not configured_feeds:
            configured_feeds = _normalize_feed_entries(payload.get("feed_urls"))
        feeds = configured_feeds or list(self.feeds)
        if not feeds:
            raise ValueError("RSSNewsJobCap requires at least one RSS feed URL.")

        collected_rows: List[Dict[str, Any]] = []
        raw_feeds: List[Dict[str, Any]] = []
        failed_feeds: List[Dict[str, str]] = []

        for feed in feeds:
            source_name = str(feed.get("source") or "").strip() or _infer_feed_source(feed.get("url"))
            feed_url = str(feed.get("url") or "").strip()
            try:
                feed_title, entries = self._fetch_feed(feed_url)
                raw_entries: List[Dict[str, Any]] = []
                for entry in entries:
                    normalized_row, raw_entry = self._normalize_feed_entry(
                        entry,
                        source_name=source_name,
                        feed_url=feed_url,
                        feed_title=feed_title,
                    )
                    if normalized_row is None:
                        continue
                    collected_rows.append(normalized_row)
                    raw_entries.append(raw_entry)
                raw_feeds.append(
                    {
                        "source": source_name,
                        "url": feed_url,
                        "feed_title": feed_title,
                        "entry_count": len(raw_entries),
                        "entries": raw_entries,
                    }
                )
            except Exception as exc:
                failed_feeds.append(
                    {
                        "source": source_name,
                        "url": feed_url,
                        "error": str(exc),
                    }
                )
                raw_feeds.append(
                    {
                        "source": source_name,
                        "url": feed_url,
                        "error": str(exc),
                        "entry_count": 0,
                        "entries": [],
                    }
                )

        if not collected_rows and failed_feeds:
            failed_labels = ", ".join(
                f"{entry['source']} ({entry['error']})"
                for entry in failed_feeds
            )
            raise RuntimeError(f"RSSNewsJobCap failed for all feeds: {failed_labels}")

        result_summary = {
            "rows": len(collected_rows),
            "feeds": len(feeds),
            "successful_feeds": len(feeds) - len(failed_feeds),
            "failed_feeds": failed_feeds,
            "sources": [str(feed.get("source") or "") for feed in feeds],
        }
        raw_payload = {
            "provider": "rss",
            "feeds": raw_feeds,
        }
        return JobResult(
            job_id=job.id,
            status="completed",
            target_table=TABLE_NEWS,
            collected_rows=collected_rows,
            raw_payload=raw_payload,
            result_summary=result_summary,
        )

    def _fetch_feed(self, feed_url: str) -> tuple[str, List[ET.Element]]:
        """Internal helper to fetch the feed."""
        response = self.request_get(
            feed_url,
            timeout=self.timeout_sec,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
            },
        )
        raise_for_status = getattr(response, "raise_for_status", None)
        if callable(raise_for_status):
            raise_for_status()
        payload_text = str(getattr(response, "text", "") or "")
        if not payload_text.strip():
            raise ValueError(f"Feed {feed_url} returned an empty body.")

        root = ET.fromstring(payload_text)
        root_name = _local_name(root.tag)

        if root_name == "rss":
            channel = next((child for child in list(root) if _local_name(child.tag) == "channel"), root)
            feed_title = _clean_text(_find_child_text(channel, ("title",))) or _infer_feed_source(feed_url)
            entries = [child for child in list(channel) if _local_name(child.tag) == "item"]
            return feed_title, entries

        if root_name == "feed":
            feed_title = _clean_text(_find_child_text(root, ("title",))) or _infer_feed_source(feed_url)
            entries = [child for child in list(root) if _local_name(child.tag) == "entry"]
            return feed_title, entries

        feed_title = _clean_text(_find_child_text(root, ("title",))) or _infer_feed_source(feed_url)
        entries = [element for element in root.iter() if _local_name(element.tag) in {"item", "entry"}]
        return feed_title, entries

    def _normalize_feed_entry(
        self,
        entry: ET.Element,
        *,
        source_name: str,
        feed_url: str,
        feed_title: str,
    ) -> tuple[Dict[str, Any] | None, Dict[str, Any]]:
        """Internal helper to normalize the feed entry."""
        headline = _clean_text(_find_child_text(entry, ("title",)))
        summary_raw = _find_child_text(entry, ("description", "summary", "content", "subtitle"))
        summary = _clean_text(summary_raw)
        link = str(_find_link(entry) or _find_child_text(entry, ("guid", "id"))).strip()
        guid = str(_find_child_text(entry, ("guid", "id"))).strip()
        published_raw = _find_child_text(entry, ("pubDate", "published", "updated", "issued", "date"))
        published_at = _parse_timestamp(published_raw)
        categories = [
            _clean_text(_element_text(child))
            for child in list(entry)
            if _local_name(child.tag) == "category" and _clean_text(_element_text(child))
        ]

        raw_entry = {
            "headline": headline,
            "summary": summary,
            "url": link,
            "guid": guid,
            "published_at": published_at,
            "published_raw": published_raw,
            "categories": categories,
        }

        if not headline and not link and not guid:
            return None, raw_entry

        headline = headline or link or guid or "RSS item"
        row = {
            "id": _news_row_id(
                source=source_name,
                feed_url=feed_url,
                guid=guid,
                link=link,
                published_at=published_at,
                headline=headline,
            ),
            "headline": headline,
            "summary": summary,
            "url": link,
            "source": source_name,
            "source_url": feed_url,
            "published_at": published_at,
            "data": {
                "provider": "rss",
                "feed_source": source_name,
                "feed_title": feed_title,
                "feed_url": feed_url,
                "guid": guid,
                "published_raw": published_raw,
                "categories": categories,
            },
        }
        return row, raw_entry
