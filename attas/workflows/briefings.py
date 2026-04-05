"""
Finance briefing workflow pack for `attas.workflows.briefings`.

Attas owns finance-specific workflow packaging on top of the shared Prompits and
Phemacast runtimes. This module turns normalized MCP search/fetch payloads into a
stable finance briefing payload, Notion-ready Markdown, and NotebookLM-compatible
export artifacts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import re
from typing import Any

from phemacast.personal_agent.file_save import (
    save_bytes_file,
    save_json_file,
    save_markdown_file,
    save_text_file,
)

try:
    from fpdf import FPDF
except ImportError:  # pragma: no cover - optional dependency
    FPDF = None


BRIEFING_PAYLOAD_TYPE = "attas.finance_briefing"
BRIEFING_PAYLOAD_VERSION = 1
NOTEBOOKLM_IMPORT_MODE = "beta_export_only"
DEFAULT_OWNER = "attas.workflows.briefings"
TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "briefings"
_TEMPLATE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_POSITIVE_TERMS = (
    "accelerat",
    "approval",
    "backlog",
    "beat",
    "constructive",
    "demand",
    "expand",
    "growth",
    "launch",
    "margin",
    "outperform",
    "pipeline",
    "project",
    "resilient",
    "strong",
    "upgrade",
    "win",
)
_NEGATIVE_TERMS = (
    "antitrust",
    "cut",
    "caution",
    "decline",
    "delay",
    "downgrade",
    "export control",
    "headwind",
    "investigation",
    "lawsuit",
    "miss",
    "pressure",
    "probe",
    "regulation",
    "risk",
    "sanction",
    "slow",
    "warning",
    "weaker",
)
_HIGH_RISK_TERMS = (
    "export control",
    "fraud",
    "guidance cut",
    "lawsuit",
    "probe",
    "sanction",
    "warning",
)
_CATALYST_RULES = (
    {"name": "earnings", "direction": "mixed", "timing": "upcoming", "keywords": ("earnings", "results", "guidance", "call")},
    {"name": "product", "direction": "positive", "timing": "reported", "keywords": ("launch", "rollout", "shipment", "project", "design win")},
    {"name": "policy", "direction": "negative", "timing": "monitor", "keywords": ("policy", "export control", "regulation", "tariff", "hearing")},
    {"name": "capital", "direction": "positive", "timing": "reported", "keywords": ("buyback", "dividend", "capex", "investment")},
)
_WORKFLOW_CONFIG = {
    "morning_desk_briefing": {
        "label": "Morning Desk Briefing",
        "template": "morning_desk_briefing.md.tmpl",
    },
    "watchlist_check": {
        "label": "Watchlist Check",
        "template": "watchlist_check.md.tmpl",
    },
    "research_roundup": {
        "label": "Research Roundup",
        "template": "research_roundup.md.tmpl",
    },
}


def _utcnow_iso() -> str:
    """Return a stable UTC timestamp string."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _collapse_whitespace(value: Any) -> str:
    """Return a trimmed single-line string."""
    return _WHITESPACE_PATTERN.sub(" ", str(value or "")).strip()


def _truncate(value: Any, limit: int = 260) -> str:
    """Return a clipped string for user-facing summaries."""
    text = _collapse_whitespace(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3].rstrip()}..."


def _slugify(value: Any) -> str:
    """Return a filesystem-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug[:72] or "briefing"


def _unique_strings(values: Sequence[Any]) -> list[str]:
    """Return unique non-empty strings in order."""
    unique: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _collapse_whitespace(value)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return unique


def _stable_id(*parts: Any) -> str:
    """Return a deterministic short identifier."""
    basis = "|".join(_collapse_whitespace(part) for part in parts if _collapse_whitespace(part))
    digest = hashlib.sha1((basis or "briefing").encode("utf-8")).hexdigest()[:12]
    return digest


def _normalize_payload_timestamp(value: Any) -> str:
    """Return an ISO-ish timestamp string."""
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    normalized = str(value or "").strip()
    return normalized or _utcnow_iso()


def _workflow_settings(workflow_name: str) -> dict[str, str]:
    """Return the workflow settings."""
    if workflow_name not in _WORKFLOW_CONFIG:
        raise ValueError(f"Unsupported finance workflow '{workflow_name}'.")
    return dict(_WORKFLOW_CONFIG[workflow_name])


def _coerce_mapping_list(value: Any) -> list[dict[str, Any]]:
    """Return a list of mapping entries."""
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [dict(value)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [dict(entry) for entry in value if isinstance(entry, Mapping)]
    return []


def _extract_source_items(value: Any) -> list[dict[str, Any]]:
    """Extract stable source items from search/fetch payloads."""
    if value is None:
        return []
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        items: list[dict[str, Any]] = []
        for entry in value:
            items.extend(_extract_source_items(entry))
        return items
    if not isinstance(value, Mapping):
        return []

    for key in ("sources", "results", "items"):
        nested = value.get(key)
        if isinstance(nested, list):
            return [dict(entry) for entry in nested if isinstance(entry, Mapping)]
    return [dict(value)]


def _normalize_citation(source: Mapping[str, Any]) -> dict[str, Any]:
    """Return the normalized citation record for a source."""
    raw_citation = source.get("citation")
    citation = dict(raw_citation) if isinstance(raw_citation, Mapping) else {}
    title = _collapse_whitespace(citation.get("title") or source.get("title"))
    url = _collapse_whitespace(citation.get("url") or source.get("url"))
    source_domain = _collapse_whitespace(citation.get("source_domain") or source.get("source_domain"))
    published_at = _collapse_whitespace(citation.get("published_at") or source.get("published_at"))
    citation_id = _collapse_whitespace(citation.get("id") or source.get("id")) or _stable_id(url, title, source_domain)
    normalized = {
        "id": citation_id,
        "title": title,
        "url": url,
        "source_domain": source_domain,
        "published_at": published_at,
    }
    locator = citation.get("locator")
    if locator not in (None, "", [], {}):
        normalized["locator"] = locator
    return normalized


def _normalize_source_item(item: Mapping[str, Any], *, source_kind: str) -> dict[str, Any]:
    """Return a normalized finance research source."""
    normalized = dict(item)
    citation = _normalize_citation(normalized)
    source_id = _collapse_whitespace(normalized.get("id")) or citation["id"]
    title = _collapse_whitespace(normalized.get("title") or citation.get("title"))
    url = _collapse_whitespace(normalized.get("url") or citation.get("url"))
    source_domain = _collapse_whitespace(normalized.get("source_domain") or citation.get("source_domain"))
    published_at = _collapse_whitespace(normalized.get("published_at") or citation.get("published_at"))
    snippet = _truncate(normalized.get("snippet"))
    text = _collapse_whitespace(normalized.get("text"))
    return {
        "id": source_id or _stable_id(url, title, source_kind),
        "title": title,
        "url": url,
        "source_domain": source_domain,
        "published_at": published_at,
        "snippet": snippet,
        "text": text,
        "citation": citation,
        "source_kind": source_kind,
    }


def _merge_source_records(
    *,
    search_results: Any = None,
    fetched_documents: Any = None,
) -> list[dict[str, Any]]:
    """Merge normalized search and fetch records into one source list."""
    ordered_keys: list[str] = []
    merged: dict[str, dict[str, Any]] = {}

    def upsert(item: Mapping[str, Any], *, source_kind: str) -> None:
        """Merge an individual item."""
        normalized = _normalize_source_item(item, source_kind=source_kind)
        key = _collapse_whitespace(normalized.get("id") or normalized.get("url") or normalized.get("title"))
        if not key:
            key = _stable_id(normalized.get("url"), normalized.get("title"), source_kind)
        if key not in merged:
            merged[key] = normalized
            merged[key]["source_kinds"] = [source_kind]
            ordered_keys.append(key)
            return

        current = merged[key]
        for field_name in ("id", "title", "url", "source_domain", "published_at"):
            if not current.get(field_name) and normalized.get(field_name):
                current[field_name] = normalized[field_name]

        current_snippet = str(current.get("snippet") or "")
        next_snippet = str(normalized.get("snippet") or "")
        if len(next_snippet) > len(current_snippet):
            current["snippet"] = next_snippet

        current_text = str(current.get("text") or "")
        next_text = str(normalized.get("text") or "")
        if len(next_text) > len(current_text):
            current["text"] = next_text

        current["citation"] = _normalize_citation({**current, **normalized})
        current["source_kinds"] = _unique_strings(list(current.get("source_kinds") or []) + [source_kind])

    for entry in _extract_source_items(search_results):
        upsert(entry, source_kind="search")
    for entry in _extract_source_items(fetched_documents):
        upsert(entry, source_kind="document")

    sources: list[dict[str, Any]] = []
    for key in ordered_keys:
        source = dict(merged[key])
        blob = _collapse_whitespace(" ".join([source.get("title") or "", source.get("snippet") or "", source.get("text") or ""]))
        positive_hits = sum(1 for term in _POSITIVE_TERMS if term in blob.lower())
        negative_hits = sum(1 for term in _NEGATIVE_TERMS if term in blob.lower())
        if positive_hits and negative_hits:
            tone = "mixed"
        elif negative_hits > positive_hits:
            tone = "negative"
        elif positive_hits > negative_hits:
            tone = "positive"
        else:
            tone = "neutral"

        risk_flags = [term for term in _NEGATIVE_TERMS if term in blob.lower()]
        catalyst_flags = [rule["name"] for rule in _CATALYST_RULES if any(keyword in blob.lower() for keyword in rule["keywords"])]
        source["classification"] = {
            "tone": tone,
            "risk_flags": _unique_strings(risk_flags),
            "catalyst_flags": _unique_strings(catalyst_flags),
        }
        source["citation_id"] = source["citation"]["id"]
        sources.append(source)
    return sources


def _normalize_watchlist(watchlist: Any) -> list[dict[str, Any]]:
    """Return normalized watchlist entries."""
    items: list[dict[str, Any]] = []
    for raw in _coerce_mapping_list(watchlist):
        symbol = _collapse_whitespace(raw.get("symbol") or raw.get("ticker"))
        name = _collapse_whitespace(raw.get("name"))
        thesis = _collapse_whitespace(raw.get("thesis") or raw.get("view") or raw.get("note"))
        position = _collapse_whitespace(raw.get("position"))
        if not any((symbol, name, thesis, position)):
            continue
        items.append(
            {
                "symbol": symbol,
                "name": name,
                "position": position,
                "thesis": thesis,
            }
        )
    return items


def _normalize_subject(
    subject: Any,
    *,
    workflow_name: str,
    watchlist: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return the normalized briefing subject."""
    label = ""
    symbols: list[str] = []
    if isinstance(subject, Mapping):
        label = _collapse_whitespace(subject.get("label") or subject.get("name") or subject.get("topic"))
        symbols = _unique_strings(
            list(subject.get("symbols") or [])
            + ([subject.get("symbol")] if subject.get("symbol") else [])
        )
    else:
        label = _collapse_whitespace(subject)

    if not symbols:
        symbols = _unique_strings(entry.get("symbol") for entry in watchlist)

    if not label:
        if symbols:
            label = ", ".join(symbols)
        else:
            label = _workflow_settings(workflow_name)["label"]

    return {
        "label": label,
        "symbols": symbols,
    }


def _normalize_statement_entries(
    value: Any,
    *,
    field_name: str = "statement",
    extra_fields: Sequence[str] = (),
) -> list[dict[str, Any]]:
    """Normalize lists of strings or objects into structured entries."""
    entries: list[dict[str, Any]] = []
    if value is None:
        return entries

    raw_items: list[Any]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        raw_items = list(value)
    else:
        raw_items = [value]

    for raw in raw_items:
        if isinstance(raw, str):
            text = _collapse_whitespace(raw)
            if not text:
                continue
            entries.append({field_name: text, "citation_ids": []})
            continue
        if not isinstance(raw, Mapping):
            continue
        primary = _collapse_whitespace(raw.get(field_name) or raw.get("statement") or raw.get("text"))
        if not primary:
            continue
        normalized = {field_name: primary}
        normalized["citation_ids"] = _unique_strings(raw.get("citation_ids") or raw.get("citations") or [])
        for extra_field in extra_fields:
            normalized[extra_field] = _collapse_whitespace(raw.get(extra_field))
        entries.append(normalized)
    return entries


def _source_fact_statement(source: Mapping[str, Any]) -> str:
    """Build a concise fact statement from a source."""
    title = _collapse_whitespace(source.get("title"))
    snippet = _collapse_whitespace(source.get("snippet"))
    if title and snippet and snippet.lower() not in title.lower():
        return _truncate(f"{title}: {snippet}")
    if snippet:
        return _truncate(snippet)
    if title:
        return _truncate(title)
    return _truncate(source.get("text"))


def _dedupe_entries(entries: Sequence[Mapping[str, Any]], field_name: str) -> list[dict[str, Any]]:
    """Deduplicate entries by a primary text field."""
    deduped: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        primary = _collapse_whitespace(entry.get(field_name))
        if not primary:
            continue
        key = primary.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(entry))
    return deduped


def _build_fact_entries(
    *,
    sources: Sequence[Mapping[str, Any]],
    analysis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build fact entries from explicit analysis and normalized sources."""
    entries = _normalize_statement_entries(analysis.get("facts"), field_name="statement")
    for source in sources:
        statement = _source_fact_statement(source)
        if not statement:
            continue
        entries.append(
            {
                "statement": statement,
                "citation_ids": [str(source.get("citation_id") or "")] if source.get("citation_id") else [],
                "source_ids": [str(source.get("id") or "")] if source.get("id") else [],
                "kind": "reported",
            }
        )
    return _dedupe_entries(entries, "statement")


def _build_risk_entries(
    *,
    sources: Sequence[Mapping[str, Any]],
    analysis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build risk entries from explicit analysis and source classification."""
    entries = _normalize_statement_entries(analysis.get("risks"), field_name="statement", extra_fields=("severity",))
    for source in sources:
        flags = list((source.get("classification") or {}).get("risk_flags") or [])
        if not flags and (source.get("classification") or {}).get("tone") != "negative":
            continue
        blob = _collapse_whitespace(source.get("snippet") or source.get("text") or source.get("title"))
        severity = "high" if any(flag in blob.lower() for flag in _HIGH_RISK_TERMS) else "medium"
        entries.append(
            {
                "statement": _truncate(blob),
                "severity": severity,
                "citation_ids": [str(source.get("citation_id") or "")] if source.get("citation_id") else [],
            }
        )
    normalized = _dedupe_entries(entries, "statement")
    for entry in normalized:
        entry["severity"] = _collapse_whitespace(entry.get("severity")) or "medium"
    return normalized


def _build_catalyst_entries(
    *,
    sources: Sequence[Mapping[str, Any]],
    analysis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build catalyst entries from explicit analysis and source classification."""
    entries = _normalize_statement_entries(
        analysis.get("catalysts"),
        field_name="statement",
        extra_fields=("direction", "timing"),
    )
    for source in sources:
        blob = _collapse_whitespace(source.get("title") or source.get("snippet") or source.get("text"))
        blob_lower = blob.lower()
        for rule in _CATALYST_RULES:
            if not any(keyword in blob_lower for keyword in rule["keywords"]):
                continue
            entries.append(
                {
                    "statement": _truncate(blob),
                    "direction": rule["direction"],
                    "timing": rule["timing"],
                    "citation_ids": [str(source.get("citation_id") or "")] if source.get("citation_id") else [],
                }
            )
            break
    normalized = _dedupe_entries(entries, "statement")
    for entry in normalized:
        entry["direction"] = _collapse_whitespace(entry.get("direction")) or "mixed"
        entry["timing"] = _collapse_whitespace(entry.get("timing")) or "monitor"
    return normalized


def _determine_stance(
    *,
    sources: Sequence[Mapping[str, Any]],
    risks: Sequence[Mapping[str, Any]],
    catalysts: Sequence[Mapping[str, Any]],
) -> str:
    """Return the top-line stance label for the briefing."""
    positive_sources = sum(1 for source in sources if (source.get("classification") or {}).get("tone") == "positive")
    negative_sources = sum(1 for source in sources if (source.get("classification") or {}).get("tone") == "negative")
    high_risks = sum(1 for risk in risks if _collapse_whitespace(risk.get("severity")) == "high")
    positive_catalysts = sum(1 for catalyst in catalysts if _collapse_whitespace(catalyst.get("direction")) == "positive")

    if negative_sources and positive_sources:
        return "mixed"
    if negative_sources or high_risks:
        return "cautious"
    if positive_sources or positive_catalysts:
        return "constructive"
    return "balanced"


def _build_takeaway_entries(
    *,
    workflow_name: str,
    subject: Mapping[str, Any],
    sources: Sequence[Mapping[str, Any]],
    risks: Sequence[Mapping[str, Any]],
    catalysts: Sequence[Mapping[str, Any]],
    analysis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build inferred takeaway entries."""
    entries = _normalize_statement_entries(
        analysis.get("inferred_takeaways") or analysis.get("takeaways"),
        field_name="statement",
        extra_fields=("basis",),
    )
    positive_sources = [source for source in sources if (source.get("classification") or {}).get("tone") == "positive"]
    negative_sources = [source for source in sources if (source.get("classification") or {}).get("tone") == "negative"]
    subject_label = _collapse_whitespace(subject.get("label"))

    if positive_sources and negative_sources:
        entries.append(
            {
                "statement": f"{subject_label or 'The setup'} is mixed: supportive demand evidence is offset by active risk headlines.",
                "basis": "Cross-source tone split across constructive and negative research inputs.",
                "citation_ids": _unique_strings(
                    [positive_sources[0].get("citation_id"), negative_sources[0].get("citation_id")]
                ),
            }
        )
    elif positive_sources:
        entries.append(
            {
                "statement": f"{subject_label or 'The setup'} screens constructive on the current research tape.",
                "basis": "Most sourced items skew positive or event-supportive.",
                "citation_ids": _unique_strings(source.get("citation_id") for source in positive_sources[:2]),
            }
        )
    elif negative_sources:
        entries.append(
            {
                "statement": f"{subject_label or 'The setup'} carries a cautious near-term signal.",
                "basis": "The sourced flow is dominated by risk-heavy headlines or documents.",
                "citation_ids": _unique_strings(source.get("citation_id") for source in negative_sources[:2]),
            }
        )

    if catalysts:
        entries.append(
            {
                "statement": f"Near-term catalysts remain actionable for {subject_label or 'the desk'} monitoring list.",
                "basis": "Event-heavy items are present in the normalized research feed.",
                "citation_ids": _unique_strings(catalyst.get("citation_ids", [None])[0] for catalyst in catalysts[:2]),
            }
        )

    if workflow_name == "watchlist_check":
        entries.append(
            {
                "statement": "Watchlist names should be ranked by confirmation speed rather than headline volume alone.",
                "basis": "The workflow is focused on fast decision support for monitored names.",
                "citation_ids": [],
            }
        )

    normalized = _dedupe_entries(entries, "statement")
    for entry in normalized:
        entry["basis"] = _collapse_whitespace(entry.get("basis")) or "Derived from the normalized finance research set."
    return normalized


def _build_conflicting_evidence_entries(
    *,
    sources: Sequence[Mapping[str, Any]],
    analysis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build conflicting evidence entries."""
    entries: list[dict[str, Any]] = []
    raw_items = analysis.get("conflicting_evidence")
    for raw in _coerce_mapping_list(raw_items):
        bullish = _collapse_whitespace(raw.get("bullish") or raw.get("pro") or raw.get("positive"))
        bearish = _collapse_whitespace(raw.get("bearish") or raw.get("con") or raw.get("negative"))
        why_it_matters = _collapse_whitespace(raw.get("why_it_matters") or raw.get("context"))
        if not any((bullish, bearish, why_it_matters)):
            continue
        entries.append(
            {
                "bullish": bullish,
                "bearish": bearish,
                "why_it_matters": why_it_matters,
                "citation_ids": _unique_strings(raw.get("citation_ids") or raw.get("citations") or []),
            }
        )

    positive_sources = [source for source in sources if (source.get("classification") or {}).get("tone") == "positive"]
    negative_sources = [source for source in sources if (source.get("classification") or {}).get("tone") == "negative"]
    if positive_sources and negative_sources:
        entries.append(
            {
                "bullish": _source_fact_statement(positive_sources[0]),
                "bearish": _source_fact_statement(negative_sources[0]),
                "why_it_matters": "Positioning depends on whether supportive demand signals or the active risk headline set proves more durable.",
                "citation_ids": _unique_strings(
                    [positive_sources[0].get("citation_id"), negative_sources[0].get("citation_id")]
                ),
            }
        )
    return _dedupe_entries(entries, "why_it_matters")


def _build_open_question_entries(
    *,
    subject: Mapping[str, Any],
    risks: Sequence[Mapping[str, Any]],
    catalysts: Sequence[Mapping[str, Any]],
    conflicting_evidence: Sequence[Mapping[str, Any]],
    analysis: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build open question entries."""
    entries = _normalize_statement_entries(
        analysis.get("open_questions"),
        field_name="question",
        extra_fields=("why_it_matters",),
    )
    subject_label = _collapse_whitespace(subject.get("label")) or "the name"

    if conflicting_evidence:
        evidence = conflicting_evidence[0]
        entries.append(
            {
                "question": f"What evidence will resolve the current split view for {subject_label}?",
                "why_it_matters": _collapse_whitespace(evidence.get("why_it_matters")) or "The desk needs a cleaner read on which side of the debate should drive sizing.",
                "citation_ids": list(evidence.get("citation_ids") or []),
            }
        )
    elif risks:
        risk = risks[0]
        entries.append(
            {
                "question": f"What would confirm or disprove the lead risk on {subject_label}?",
                "why_it_matters": "Risk management is more useful when the invalidation signal is explicit.",
                "citation_ids": list(risk.get("citation_ids") or []),
            }
        )

    if catalysts:
        catalyst = catalysts[0]
        entries.append(
            {
                "question": f"Which upcoming catalyst is most likely to reset the tape for {subject_label}?",
                "why_it_matters": "Catalyst ranking helps decide whether to wait, scale, or publish now.",
                "citation_ids": list(catalyst.get("citation_ids") or []),
            }
        )

    normalized = _dedupe_entries(entries, "question")
    for entry in normalized:
        entry["why_it_matters"] = _collapse_whitespace(entry.get("why_it_matters")) or "It affects the next finance workflow decision."
    return normalized


def _dedupe_citations(sources: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return unique citations in source order."""
    citations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        citation = source.get("citation")
        if not isinstance(citation, Mapping):
            continue
        citation_id = _collapse_whitespace(citation.get("id"))
        if not citation_id or citation_id in seen:
            continue
        seen.add(citation_id)
        citations.append(dict(citation))
    return citations


def _citation_label_map(citations: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Return citation ids mapped to compact labels."""
    labels: dict[str, str] = {}
    for index, citation in enumerate(citations, start=1):
        citation_id = _collapse_whitespace(citation.get("id"))
        if citation_id:
            labels[citation_id] = f"S{index}"
    return labels


def _citation_marker_text(citation_ids: Sequence[Any], labels: Mapping[str, str]) -> str:
    """Return compact citation markers for Markdown and PDF views."""
    markers = [f"[{labels[citation_id]}]" for citation_id in _unique_strings(citation_ids) if citation_id in labels]
    return f" {' '.join(markers)}" if markers else ""


def _render_markdown_bullets(lines: Sequence[str]) -> str:
    """Return a Markdown bullet list."""
    usable = [_collapse_whitespace(line) for line in lines if _collapse_whitespace(line)]
    if not usable:
        return "- None identified."
    return "\n".join(f"- {line}" for line in usable)


def _render_fact_lines(items: Sequence[Mapping[str, Any]], labels: Mapping[str, str]) -> str:
    """Render fact items to Markdown."""
    return _render_markdown_bullets(
        f"{_collapse_whitespace(item.get('statement'))}{_citation_marker_text(item.get('citation_ids') or [], labels)}"
        for item in items
    )


def _render_takeaway_lines(items: Sequence[Mapping[str, Any]], labels: Mapping[str, str]) -> str:
    """Render takeaway items to Markdown."""
    lines: list[str] = []
    for item in items:
        statement = _collapse_whitespace(item.get("statement"))
        basis = _collapse_whitespace(item.get("basis"))
        if not statement:
            continue
        suffix = f" Basis: {basis}." if basis else ""
        lines.append(f"{statement}.{suffix}{_citation_marker_text(item.get('citation_ids') or [], labels)}".replace("..", "."))
    return _render_markdown_bullets(lines)


def _render_risk_lines(items: Sequence[Mapping[str, Any]], labels: Mapping[str, str]) -> str:
    """Render risk items to Markdown."""
    lines: list[str] = []
    for item in items:
        statement = _collapse_whitespace(item.get("statement"))
        if not statement:
            continue
        severity = _collapse_whitespace(item.get("severity")) or "medium"
        lines.append(f"{severity.title()}: {statement}{_citation_marker_text(item.get('citation_ids') or [], labels)}")
    return _render_markdown_bullets(lines)


def _render_catalyst_lines(items: Sequence[Mapping[str, Any]], labels: Mapping[str, str]) -> str:
    """Render catalyst items to Markdown."""
    lines: list[str] = []
    for item in items:
        statement = _collapse_whitespace(item.get("statement"))
        if not statement:
            continue
        direction = _collapse_whitespace(item.get("direction")) or "mixed"
        timing = _collapse_whitespace(item.get("timing")) or "monitor"
        lines.append(f"{direction.title()} / {timing}: {statement}{_citation_marker_text(item.get('citation_ids') or [], labels)}")
    return _render_markdown_bullets(lines)


def _render_conflict_lines(items: Sequence[Mapping[str, Any]], labels: Mapping[str, str]) -> str:
    """Render conflicting evidence items to Markdown."""
    lines: list[str] = []
    for item in items:
        bullish = _collapse_whitespace(item.get("bullish"))
        bearish = _collapse_whitespace(item.get("bearish"))
        why_it_matters = _collapse_whitespace(item.get("why_it_matters"))
        parts = []
        if bullish:
            parts.append(f"Bullish: {bullish}")
        if bearish:
            parts.append(f"Bearish: {bearish}")
        if why_it_matters:
            parts.append(f"Why it matters: {why_it_matters}")
        if parts:
            lines.append(f"{' '.join(parts)}{_citation_marker_text(item.get('citation_ids') or [], labels)}")
    return _render_markdown_bullets(lines)


def _render_question_lines(items: Sequence[Mapping[str, Any]], labels: Mapping[str, str]) -> str:
    """Render open questions to Markdown."""
    lines: list[str] = []
    for item in items:
        question = _collapse_whitespace(item.get("question"))
        if not question:
            continue
        why_it_matters = _collapse_whitespace(item.get("why_it_matters"))
        suffix = f" Why it matters: {why_it_matters}" if why_it_matters else ""
        lines.append(f"{question}{suffix}{_citation_marker_text(item.get('citation_ids') or [], labels)}")
    return _render_markdown_bullets(lines)


def _render_citation_lines(citations: Sequence[Mapping[str, Any]], labels: Mapping[str, str]) -> str:
    """Render citations to Markdown."""
    lines: list[str] = []
    for citation in citations:
        citation_id = _collapse_whitespace(citation.get("id"))
        label = labels.get(citation_id, citation_id or "S?")
        title = _collapse_whitespace(citation.get("title")) or "Untitled source"
        url = _collapse_whitespace(citation.get("url"))
        source_domain = _collapse_whitespace(citation.get("source_domain"))
        published_at = _collapse_whitespace(citation.get("published_at"))
        meta_parts = [part for part in (source_domain, published_at) if part]
        meta_text = f" | {' | '.join(meta_parts)}" if meta_parts else ""
        if url:
            lines.append(f"[{label}] [{title}]({url}){meta_text}")
        else:
            lines.append(f"[{label}] {title}{meta_text}")
    return _render_markdown_bullets(lines)


def _render_pdf_citation_lines(citations: Sequence[Mapping[str, Any]], labels: Mapping[str, str]) -> str:
    """Render citations into PDF-friendly text without long unbreakable URLs."""
    lines: list[str] = []
    for citation in citations:
        citation_id = _collapse_whitespace(citation.get("id"))
        label = labels.get(citation_id, citation_id or "S?")
        title = _collapse_whitespace(citation.get("title")) or "Untitled source"
        source_domain = _collapse_whitespace(citation.get("source_domain"))
        published_at = _collapse_whitespace(citation.get("published_at"))
        meta_parts = [part for part in (source_domain, published_at) if part]
        meta_text = f" | {' | '.join(meta_parts)}" if meta_parts else ""
        lines.append(f"[{label}] {title}{meta_text}")
    return _render_markdown_bullets(lines)


def _render_watchlist_lines(watchlist: Sequence[Mapping[str, Any]]) -> str:
    """Render watchlist entries to Markdown."""
    lines: list[str] = []
    for entry in watchlist:
        label = _collapse_whitespace(entry.get("symbol") or entry.get("name"))
        thesis = _collapse_whitespace(entry.get("thesis"))
        position = _collapse_whitespace(entry.get("position"))
        parts = [label] if label else []
        if position:
            parts.append(f"position: {position}")
        if thesis:
            parts.append(f"view: {thesis}")
        if parts:
            lines.append(" | ".join(parts))
    return _render_markdown_bullets(lines)


def _load_template(template_name: str) -> str:
    """Return the template text for a workflow."""
    path = TEMPLATE_DIR / template_name
    return path.read_text(encoding="utf-8")


def _render_template(template_text: str, bindings: Mapping[str, Any]) -> str:
    """Render a lightweight text template."""
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(bindings.get(key, ""))

    return _TEMPLATE_PATTERN.sub(replace, template_text)


def _summary_headline(
    *,
    workflow_name: str,
    subject: Mapping[str, Any],
    stance: str,
    watchlist: Sequence[Mapping[str, Any]],
    risks: Sequence[Mapping[str, Any]],
) -> str:
    """Return the workflow headline."""
    label = _collapse_whitespace(subject.get("label")) or _workflow_settings(workflow_name)["label"]
    risk_hint = _collapse_whitespace(risks[0].get("statement")) if risks else ""
    if workflow_name == "watchlist_check":
        count = len(watchlist)
        suffix = f"; lead risk is {_truncate(risk_hint, 80)}" if risk_hint else ""
        return f"Watchlist check on {count} names: {stance} read{suffix}"
    if workflow_name == "research_roundup":
        suffix = f"; lead risk is {_truncate(risk_hint, 80)}" if risk_hint else ""
        return f"{label} research roundup: {stance} tone{suffix}"
    suffix = f"; keep {_truncate(risk_hint, 80)} on the tape" if risk_hint else ""
    return f"{label} morning desk briefing: {stance} setup{suffix}"


def _channel_text(
    *,
    headline: str,
    takeaways: Sequence[Mapping[str, Any]],
    catalysts: Sequence[Mapping[str, Any]],
) -> str:
    """Return a channel-ready text block."""
    takeaway = _collapse_whitespace(takeaways[0].get("statement")) if takeaways else ""
    catalyst = _collapse_whitespace(catalysts[0].get("statement")) if catalysts else ""
    pieces = [headline]
    if takeaway:
        pieces.append(f"Takeaway: {takeaway}")
    if catalyst:
        pieces.append(f"Next catalyst: {_truncate(catalyst, 120)}")
    return " ".join(piece for piece in pieces if piece)


def build_source_url_bundle(payload: Mapping[str, Any]) -> str:
    """Return the raw URL bundle for NotebookLM import."""
    citations = payload.get("citations") if isinstance(payload.get("citations"), list) else []
    urls = _unique_strings(citation.get("url") for citation in citations if isinstance(citation, Mapping))
    return "\n".join(urls)


def render_briefing_markdown(payload: Mapping[str, Any]) -> str:
    """Render a workflow payload into publication-ready Markdown."""
    workflow_name = _collapse_whitespace(payload.get("workflow"))
    settings = _workflow_settings(workflow_name)
    citations = payload.get("citations") if isinstance(payload.get("citations"), list) else []
    labels = _citation_label_map(citations)
    watchlist = payload.get("watchlist") if isinstance(payload.get("watchlist"), list) else []
    template_text = _load_template(settings["template"])
    bindings = {
        "title": _collapse_whitespace(payload.get("title")) or settings["label"],
        "workflow_label": settings["label"],
        "as_of": _collapse_whitespace(payload.get("as_of")) or _utcnow_iso(),
        "subject_label": _collapse_whitespace((payload.get("subject") or {}).get("label") if isinstance(payload.get("subject"), Mapping) else ""),
        "headline": _collapse_whitespace((payload.get("summary") or {}).get("headline") if isinstance(payload.get("summary"), Mapping) else ""),
        "channel_text": _collapse_whitespace((payload.get("summary") or {}).get("channel_text") if isinstance(payload.get("summary"), Mapping) else ""),
        "watchlist_section": "" if not watchlist else f"## Watchlist\n{_render_watchlist_lines(watchlist)}\n",
        "facts": _render_fact_lines(payload.get("facts") or [], labels),
        "takeaways": _render_takeaway_lines(payload.get("inferred_takeaways") or [], labels),
        "risks": _render_risk_lines(payload.get("risks") or [], labels),
        "catalysts": _render_catalyst_lines(payload.get("catalysts") or [], labels),
        "conflicting_evidence": _render_conflict_lines(payload.get("conflicting_evidence") or [], labels),
        "open_questions": _render_question_lines(payload.get("open_questions") or [], labels),
        "citations": _render_citation_lines(citations, labels),
    }
    rendered = _render_template(template_text, bindings)
    return f"{rendered.strip()}\n"


def _default_pack_directory(payload: Mapping[str, Any], output_dir: Path) -> Path:
    """Return the export pack directory path."""
    stamp = _slugify((_collapse_whitespace(payload.get("as_of")) or _utcnow_iso()).replace(":", "-"))
    workflow = _slugify(payload.get("workflow"))
    subject = _slugify((payload.get("subject") or {}).get("label") if isinstance(payload.get("subject"), Mapping) else payload.get("title"))
    return output_dir / f"{stamp}-{workflow}-{subject}"


def _pdf_safe_text(value: Any) -> str:
    """Return text that the default FPDF renderer can handle."""
    return str(value or "").encode("latin-1", "replace").decode("latin-1")


def _build_pdf_bytes(payload: Mapping[str, Any]) -> bytes | None:
    """Return PDF bytes for the briefing when FPDF is available."""
    if FPDF is None:
        return None

    citations = payload.get("citations") if isinstance(payload.get("citations"), list) else []
    labels = _citation_label_map(citations)
    sections = [
        ("Headline", _collapse_whitespace((payload.get("summary") or {}).get("headline") if isinstance(payload.get("summary"), Mapping) else "")),
        ("Facts", _render_fact_lines(payload.get("facts") or [], labels)),
        ("Takeaways", _render_takeaway_lines(payload.get("inferred_takeaways") or [], labels)),
        ("Risks", _render_risk_lines(payload.get("risks") or [], labels)),
        ("Catalysts", _render_catalyst_lines(payload.get("catalysts") or [], labels)),
        ("Conflicting Evidence", _render_conflict_lines(payload.get("conflicting_evidence") or [], labels)),
        ("Open Questions", _render_question_lines(payload.get("open_questions") or [], labels)),
        ("Citations", _render_pdf_citation_lines(citations, labels)),
    ]

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, _pdf_safe_text(_collapse_whitespace(payload.get("title"))))
    pdf.ln(2)
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(0, 6, _pdf_safe_text(f"As of {_collapse_whitespace(payload.get('as_of'))}"))

    for section_title, section_body in sections:
        if not _collapse_whitespace(section_body):
            continue
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 7, _pdf_safe_text(section_title))
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 5, _pdf_safe_text(section_body))

    rendered = pdf.output(dest="S")
    if isinstance(rendered, str):
        return rendered.encode("latin-1")
    return bytes(rendered)


def generate_notebooklm_pack(
    payload: Mapping[str, Any],
    *,
    output_dir: str | Path | None = None,
    include_pdf: bool = False,
) -> dict[str, Any]:
    """Generate NotebookLM-compatible exports from a finance briefing payload."""
    markdown = render_briefing_markdown(payload)
    source_url_bundle = build_source_url_bundle(payload)
    result: dict[str, Any] = {
        "status": "ready",
        "mode": NOTEBOOKLM_IMPORT_MODE,
        "markdown": markdown,
        "source_url_bundle": source_url_bundle,
        "urls": source_url_bundle.splitlines() if source_url_bundle else [],
        "beta_note": "No direct NotebookLM write path is configured. Use this pack for manual import compatibility.",
        "artifacts": {},
    }

    if output_dir is None:
        if include_pdf and FPDF is None:
            result["artifacts"]["pdf"] = {
                "status": "skipped",
                "reason": "fpdf not installed",
            }
        return result

    resolved_output = Path(output_dir).expanduser().resolve()
    pack_dir = _default_pack_directory(payload, resolved_output)
    pack_dir.mkdir(parents=True, exist_ok=True)

    result["directory"] = str(pack_dir)
    result["artifacts"]["json"] = save_json_file(
        dict(payload),
        directory=str(pack_dir),
        file_name="briefing.json",
        title=_collapse_whitespace(payload.get("title")) or "briefing",
    )
    result["artifacts"]["markdown"] = save_markdown_file(
        markdown,
        directory=str(pack_dir),
        file_name="briefing.md",
        title=_collapse_whitespace(payload.get("title")) or "briefing",
    )
    result["artifacts"]["source_urls"] = save_text_file(
        source_url_bundle,
        directory=str(pack_dir),
        file_name="source-urls.txt",
        title=_collapse_whitespace(payload.get("title")) or "briefing",
        suffix=".txt",
    )

    if include_pdf:
        pdf_bytes: bytes | None = None
        pdf_error = ""
        try:
            pdf_bytes = _build_pdf_bytes(payload)
        except Exception as exc:  # pragma: no cover - defensive fallback for renderer edge cases
            pdf_error = str(exc)
        if pdf_bytes is None:
            result["artifacts"]["pdf"] = {
                "status": "skipped",
                "reason": "fpdf not installed" if not pdf_error else f"pdf render failed: {pdf_error}",
            }
        else:
            result["artifacts"]["pdf"] = save_bytes_file(
                pdf_bytes,
                directory=str(pack_dir),
                file_name="briefing.pdf",
                title=_collapse_whitespace(payload.get("title")) or "briefing",
                suffix=".pdf",
            )

    return result


def prepare_finance_briefing_context(
    *,
    workflow_name: str,
    subject: Any = None,
    search_results: Any = None,
    fetched_documents: Any = None,
    watchlist: Any = None,
    analysis: Mapping[str, Any] | None = None,
    as_of: Any = None,
    title: str | None = None,
    owner: str = DEFAULT_OWNER,
    output_dir: str | Path | None = None,
    include_pdf: bool = False,
) -> dict[str, Any]:
    """Normalize workflow-scoped inputs into a pulse-friendly context bundle."""
    settings = _workflow_settings(workflow_name)
    normalized_watchlist = _normalize_watchlist(watchlist)
    normalized_subject = _normalize_subject(
        subject,
        workflow_name=workflow_name,
        watchlist=normalized_watchlist,
    )
    return {
        "workflow": workflow_name,
        "workflow_label": settings["label"],
        "subject": normalized_subject,
        "watchlist": normalized_watchlist,
        "analysis": dict(analysis or {}),
        "as_of": _normalize_payload_timestamp(as_of),
        "title": _collapse_whitespace(title),
        "owner": _collapse_whitespace(owner) or DEFAULT_OWNER,
        "search_results": search_results,
        "fetched_documents": fetched_documents,
        "output_dir": str(output_dir) if output_dir not in (None, "") else "",
        "include_pdf": bool(include_pdf),
    }


def prepare_morning_desk_briefing_context(
    *,
    subject: Any = None,
    search_results: Any = None,
    fetched_documents: Any = None,
    watchlist: Any = None,
    analysis: Mapping[str, Any] | None = None,
    as_of: Any = None,
    title: str | None = None,
    owner: str = DEFAULT_OWNER,
    output_dir: str | Path | None = None,
    include_pdf: bool = False,
) -> dict[str, Any]:
    """Prepare the normalized context for the morning desk briefing workflow."""
    return prepare_finance_briefing_context(
        workflow_name="morning_desk_briefing",
        subject=subject,
        search_results=search_results,
        fetched_documents=fetched_documents,
        watchlist=watchlist,
        analysis=analysis,
        as_of=as_of,
        title=title,
        owner=owner,
        output_dir=output_dir,
        include_pdf=include_pdf,
    )


def prepare_watchlist_check_context(
    *,
    subject: Any = None,
    search_results: Any = None,
    fetched_documents: Any = None,
    watchlist: Any = None,
    analysis: Mapping[str, Any] | None = None,
    as_of: Any = None,
    title: str | None = None,
    owner: str = DEFAULT_OWNER,
    output_dir: str | Path | None = None,
    include_pdf: bool = False,
) -> dict[str, Any]:
    """Prepare the normalized context for the watchlist check workflow."""
    return prepare_finance_briefing_context(
        workflow_name="watchlist_check",
        subject=subject,
        search_results=search_results,
        fetched_documents=fetched_documents,
        watchlist=watchlist,
        analysis=analysis,
        as_of=as_of,
        title=title,
        owner=owner,
        output_dir=output_dir,
        include_pdf=include_pdf,
    )


def prepare_research_roundup_context(
    *,
    subject: Any = None,
    search_results: Any = None,
    fetched_documents: Any = None,
    watchlist: Any = None,
    analysis: Mapping[str, Any] | None = None,
    as_of: Any = None,
    title: str | None = None,
    owner: str = DEFAULT_OWNER,
    output_dir: str | Path | None = None,
    include_pdf: bool = False,
) -> dict[str, Any]:
    """Prepare the normalized context for the research roundup workflow."""
    return prepare_finance_briefing_context(
        workflow_name="research_roundup",
        subject=subject,
        search_results=search_results,
        fetched_documents=fetched_documents,
        watchlist=watchlist,
        analysis=analysis,
        as_of=as_of,
        title=title,
        owner=owner,
        output_dir=output_dir,
        include_pdf=include_pdf,
    )


def build_finance_source_bundle(
    *,
    search_results: Any = None,
    fetched_documents: Any = None,
    **_: Any,
) -> dict[str, Any]:
    """Return normalized finance research sources for downstream pulses."""
    return {
        "sources": _merge_source_records(
            search_results=search_results,
            fetched_documents=fetched_documents,
        )
    }


def build_finance_citations(
    *,
    sources: Sequence[Mapping[str, Any]] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Return normalized citations extracted from the source bundle."""
    return {
        "citations": _dedupe_citations(sources or [])
    }


def build_finance_facts(
    *,
    sources: Sequence[Mapping[str, Any]] | None = None,
    analysis: Mapping[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Return fact entries for the finance briefing workflow."""
    return {
        "facts": _build_fact_entries(
            sources=sources or [],
            analysis=dict(analysis or {}),
        )
    }


def build_finance_risks(
    *,
    sources: Sequence[Mapping[str, Any]] | None = None,
    analysis: Mapping[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Return risk entries for the finance briefing workflow."""
    return {
        "risks": _build_risk_entries(
            sources=sources or [],
            analysis=dict(analysis or {}),
        )
    }


def build_finance_catalysts(
    *,
    sources: Sequence[Mapping[str, Any]] | None = None,
    analysis: Mapping[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Return catalyst entries for the finance briefing workflow."""
    return {
        "catalysts": _build_catalyst_entries(
            sources=sources or [],
            analysis=dict(analysis or {}),
        )
    }


def build_finance_conflicting_evidence(
    *,
    sources: Sequence[Mapping[str, Any]] | None = None,
    analysis: Mapping[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Return conflicting evidence entries for the finance briefing workflow."""
    return {
        "conflicting_evidence": _build_conflicting_evidence_entries(
            sources=sources or [],
            analysis=dict(analysis or {}),
        )
    }


def build_finance_takeaways(
    *,
    workflow: str,
    subject: Mapping[str, Any] | None = None,
    sources: Sequence[Mapping[str, Any]] | None = None,
    risks: Sequence[Mapping[str, Any]] | None = None,
    catalysts: Sequence[Mapping[str, Any]] | None = None,
    analysis: Mapping[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Return inferred takeaway entries for the finance briefing workflow."""
    return {
        "inferred_takeaways": _build_takeaway_entries(
            workflow_name=workflow,
            subject=dict(subject or {}),
            sources=sources or [],
            risks=risks or [],
            catalysts=catalysts or [],
            analysis=dict(analysis or {}),
        )
    }


def build_finance_open_questions(
    *,
    subject: Mapping[str, Any] | None = None,
    risks: Sequence[Mapping[str, Any]] | None = None,
    catalysts: Sequence[Mapping[str, Any]] | None = None,
    conflicting_evidence: Sequence[Mapping[str, Any]] | None = None,
    analysis: Mapping[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Return open-question entries for the finance briefing workflow."""
    return {
        "open_questions": _build_open_question_entries(
            subject=dict(subject or {}),
            risks=risks or [],
            catalysts=catalysts or [],
            conflicting_evidence=conflicting_evidence or [],
            analysis=dict(analysis or {}),
        )
    }


def build_finance_summary(
    *,
    workflow: str,
    subject: Mapping[str, Any] | None = None,
    watchlist: Sequence[Mapping[str, Any]] | None = None,
    sources: Sequence[Mapping[str, Any]] | None = None,
    risks: Sequence[Mapping[str, Any]] | None = None,
    catalysts: Sequence[Mapping[str, Any]] | None = None,
    inferred_takeaways: Sequence[Mapping[str, Any]] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Return the briefing summary block for downstream publication pulses."""
    normalized_subject = dict(subject or {})
    normalized_watchlist = list(watchlist or [])
    normalized_sources = list(sources or [])
    normalized_risks = list(risks or [])
    normalized_catalysts = list(catalysts or [])
    normalized_takeaways = list(inferred_takeaways or [])
    stance = _determine_stance(
        sources=normalized_sources,
        risks=normalized_risks,
        catalysts=normalized_catalysts,
    )
    headline = _summary_headline(
        workflow_name=workflow,
        subject=normalized_subject,
        stance=stance,
        watchlist=normalized_watchlist,
        risks=normalized_risks,
    )
    return {
        "summary": {
            "stance": stance,
            "headline": headline,
            "channel_text": _channel_text(
                headline=headline,
                takeaways=normalized_takeaways,
                catalysts=normalized_catalysts,
            ),
        }
    }


def assemble_finance_briefing_payload(
    *,
    workflow: str,
    workflow_label: str | None = None,
    subject: Mapping[str, Any] | None = None,
    watchlist: Sequence[Mapping[str, Any]] | None = None,
    as_of: Any = None,
    title: str | None = None,
    owner: str = DEFAULT_OWNER,
    sources: Sequence[Mapping[str, Any]] | None = None,
    citations: Sequence[Mapping[str, Any]] | None = None,
    facts: Sequence[Mapping[str, Any]] | None = None,
    risks: Sequence[Mapping[str, Any]] | None = None,
    catalysts: Sequence[Mapping[str, Any]] | None = None,
    inferred_takeaways: Sequence[Mapping[str, Any]] | None = None,
    conflicting_evidence: Sequence[Mapping[str, Any]] | None = None,
    open_questions: Sequence[Mapping[str, Any]] | None = None,
    summary: Mapping[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    """Assemble the final stable finance briefing payload from step outputs."""
    settings = _workflow_settings(workflow)
    normalized_subject = dict(subject or {})
    normalized_watchlist = [dict(entry) for entry in (watchlist or []) if isinstance(entry, Mapping)]
    normalized_sources = [dict(entry) for entry in (sources or []) if isinstance(entry, Mapping)]
    normalized_citations = [dict(entry) for entry in (citations or []) if isinstance(entry, Mapping)]
    normalized_facts = [dict(entry) for entry in (facts or []) if isinstance(entry, Mapping)]
    normalized_risks = [dict(entry) for entry in (risks or []) if isinstance(entry, Mapping)]
    normalized_catalysts = [dict(entry) for entry in (catalysts or []) if isinstance(entry, Mapping)]
    normalized_takeaways = [dict(entry) for entry in (inferred_takeaways or []) if isinstance(entry, Mapping)]
    normalized_conflicts = [dict(entry) for entry in (conflicting_evidence or []) if isinstance(entry, Mapping)]
    normalized_questions = [dict(entry) for entry in (open_questions or []) if isinstance(entry, Mapping)]
    normalized_summary = dict(summary or {})

    normalized_title = _collapse_whitespace(title)
    if not normalized_title:
        subject_label = _collapse_whitespace(normalized_subject.get("label"))
        if workflow == "watchlist_check":
            normalized_title = f"{settings['label']}: {subject_label}"
        else:
            normalized_title = f"{settings['label']} | {subject_label}"

    payload: dict[str, Any] = {
        "payload_type": BRIEFING_PAYLOAD_TYPE,
        "payload_version": BRIEFING_PAYLOAD_VERSION,
        "workflow": workflow,
        "workflow_label": _collapse_whitespace(workflow_label) or settings["label"],
        "title": normalized_title,
        "owner": _collapse_whitespace(owner) or DEFAULT_OWNER,
        "as_of": _normalize_payload_timestamp(as_of),
        "subject": normalized_subject,
        "watchlist": normalized_watchlist,
        "summary": {
            "stance": _collapse_whitespace(normalized_summary.get("stance")),
            "headline": _collapse_whitespace(normalized_summary.get("headline")),
            "channel_text": _collapse_whitespace(normalized_summary.get("channel_text")),
        },
        "facts": normalized_facts,
        "inferred_takeaways": normalized_takeaways,
        "risks": normalized_risks,
        "catalysts": normalized_catalysts,
        "conflicting_evidence": normalized_conflicts,
        "open_questions": normalized_questions,
        "citations": normalized_citations,
        "sources": normalized_sources,
        "meta": {
            "generated_at": _utcnow_iso(),
            "source_count": len(normalized_sources),
            "citation_count": len(normalized_citations),
            "watchlist_count": len(normalized_watchlist),
            "notebooklm_import_mode": NOTEBOOKLM_IMPORT_MODE,
        },
    }
    markdown = render_briefing_markdown(payload)
    payload["publication"] = {
        "notion_title": normalized_title,
        "notion_markdown": markdown,
        "channel_text": _collapse_whitespace(payload["summary"].get("channel_text")),
    }
    return {
        "briefing_payload": payload
    }


def build_finance_briefing_payload(
    *,
    workflow_name: str,
    subject: Any = None,
    search_results: Any = None,
    fetched_documents: Any = None,
    watchlist: Any = None,
    analysis: Mapping[str, Any] | None = None,
    as_of: Any = None,
    title: str | None = None,
    owner: str = DEFAULT_OWNER,
) -> dict[str, Any]:
    """Build the stable finance briefing payload consumed by downstream lanes."""
    context = prepare_finance_briefing_context(
        workflow_name=workflow_name,
        subject=subject,
        search_results=search_results,
        fetched_documents=fetched_documents,
        watchlist=watchlist,
        analysis=analysis,
        as_of=as_of,
        title=title,
        owner=owner,
    )
    source_bundle = build_finance_source_bundle(
        search_results=context.get("search_results"),
        fetched_documents=context.get("fetched_documents"),
    )
    citation_bundle = build_finance_citations(
        sources=source_bundle.get("sources") or [],
    )
    fact_bundle = build_finance_facts(
        sources=source_bundle.get("sources") or [],
        analysis=context.get("analysis"),
    )
    risk_bundle = build_finance_risks(
        sources=source_bundle.get("sources") or [],
        analysis=context.get("analysis"),
    )
    catalyst_bundle = build_finance_catalysts(
        sources=source_bundle.get("sources") or [],
        analysis=context.get("analysis"),
    )
    conflict_bundle = build_finance_conflicting_evidence(
        sources=source_bundle.get("sources") or [],
        analysis=context.get("analysis"),
    )
    takeaway_bundle = build_finance_takeaways(
        workflow=str(context.get("workflow") or workflow_name),
        subject=context.get("subject"),
        sources=source_bundle.get("sources") or [],
        risks=risk_bundle.get("risks") or [],
        catalysts=catalyst_bundle.get("catalysts") or [],
        analysis=context.get("analysis"),
    )
    question_bundle = build_finance_open_questions(
        subject=context.get("subject"),
        risks=risk_bundle.get("risks") or [],
        catalysts=catalyst_bundle.get("catalysts") or [],
        conflicting_evidence=conflict_bundle.get("conflicting_evidence") or [],
        analysis=context.get("analysis"),
    )
    summary_bundle = build_finance_summary(
        workflow=str(context.get("workflow") or workflow_name),
        subject=context.get("subject"),
        watchlist=context.get("watchlist") or [],
        sources=source_bundle.get("sources") or [],
        risks=risk_bundle.get("risks") or [],
        catalysts=catalyst_bundle.get("catalysts") or [],
        inferred_takeaways=takeaway_bundle.get("inferred_takeaways") or [],
    )
    assembled = assemble_finance_briefing_payload(
        workflow=str(context.get("workflow") or workflow_name),
        workflow_label=str(context.get("workflow_label") or ""),
        subject=context.get("subject"),
        watchlist=context.get("watchlist") or [],
        as_of=context.get("as_of"),
        title=context.get("title"),
        owner=str(context.get("owner") or owner),
        sources=source_bundle.get("sources") or [],
        citations=citation_bundle.get("citations") or [],
        facts=fact_bundle.get("facts") or [],
        risks=risk_bundle.get("risks") or [],
        catalysts=catalyst_bundle.get("catalysts") or [],
        inferred_takeaways=takeaway_bundle.get("inferred_takeaways") or [],
        conflicting_evidence=conflict_bundle.get("conflicting_evidence") or [],
        open_questions=question_bundle.get("open_questions") or [],
        summary=summary_bundle.get("summary") or {},
    )
    return dict(assembled.get("briefing_payload") or {})


def morning_desk_briefing(
    *,
    subject: Any = None,
    search_results: Any = None,
    fetched_documents: Any = None,
    watchlist: Any = None,
    analysis: Mapping[str, Any] | None = None,
    as_of: Any = None,
    title: str | None = None,
    owner: str = DEFAULT_OWNER,
) -> dict[str, Any]:
    """Build a morning desk briefing payload."""
    return build_finance_briefing_payload(
        workflow_name="morning_desk_briefing",
        subject=subject,
        search_results=search_results,
        fetched_documents=fetched_documents,
        watchlist=watchlist,
        analysis=analysis,
        as_of=as_of,
        title=title,
        owner=owner,
    )


def watchlist_check(
    *,
    subject: Any = None,
    search_results: Any = None,
    fetched_documents: Any = None,
    watchlist: Any = None,
    analysis: Mapping[str, Any] | None = None,
    as_of: Any = None,
    title: str | None = None,
    owner: str = DEFAULT_OWNER,
) -> dict[str, Any]:
    """Build a watchlist check payload."""
    return build_finance_briefing_payload(
        workflow_name="watchlist_check",
        subject=subject,
        search_results=search_results,
        fetched_documents=fetched_documents,
        watchlist=watchlist,
        analysis=analysis,
        as_of=as_of,
        title=title,
        owner=owner,
    )


def research_roundup(
    *,
    subject: Any = None,
    search_results: Any = None,
    fetched_documents: Any = None,
    watchlist: Any = None,
    analysis: Mapping[str, Any] | None = None,
    as_of: Any = None,
    title: str | None = None,
    owner: str = DEFAULT_OWNER,
) -> dict[str, Any]:
    """Build a research roundup payload."""
    return build_finance_briefing_payload(
        workflow_name="research_roundup",
        subject=subject,
        search_results=search_results,
        fetched_documents=fetched_documents,
        watchlist=watchlist,
        analysis=analysis,
        as_of=as_of,
        title=title,
        owner=owner,
    )


def briefing_to_report_document(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a finance briefing payload into a report-style document."""
    if _collapse_whitespace(payload.get("payload_type")) != BRIEFING_PAYLOAD_TYPE:
        raise ValueError("Expected an attas.finance_briefing payload.")

    citations = payload.get("citations") if isinstance(payload.get("citations"), list) else []
    labels = _citation_label_map(citations)
    subject = payload.get("subject") if isinstance(payload.get("subject"), Mapping) else {}
    tags = _unique_strings(
        [
            "finance",
            "briefing",
            payload.get("workflow"),
            *(subject.get("symbols") or [] if isinstance(subject, Mapping) else []),
        ]
    )
    sections = [
        {
            "name": "Summary",
            "description": "Top-line finance workflow summary.",
            "content": [
                _collapse_whitespace((payload.get("summary") or {}).get("headline") if isinstance(payload.get("summary"), Mapping) else ""),
                _collapse_whitespace((payload.get("summary") or {}).get("channel_text") if isinstance(payload.get("summary"), Mapping) else ""),
            ],
        },
        {
            "name": "Facts",
            "description": "Reported facts grounded in the normalized source set.",
            "content": [_render_fact_lines(payload.get("facts") or [], labels)],
        },
        {
            "name": "Takeaways",
            "description": "Finance-specific inferred takeaways derived from the evidence set.",
            "content": [_render_takeaway_lines(payload.get("inferred_takeaways") or [], labels)],
        },
        {
            "name": "Risks",
            "description": "Risks worth carrying into publication and desk routing.",
            "content": [_render_risk_lines(payload.get("risks") or [], labels)],
        },
        {
            "name": "Catalysts",
            "description": "Catalysts to monitor after publication.",
            "content": [_render_catalyst_lines(payload.get("catalysts") or [], labels)],
        },
        {
            "name": "Conflicting Evidence",
            "description": "Cross-currents that keep conviction from becoming one-way.",
            "content": [_render_conflict_lines(payload.get("conflicting_evidence") or [], labels)],
        },
        {
            "name": "Open Questions",
            "description": "Questions the next workflow pass should answer.",
            "content": [_render_question_lines(payload.get("open_questions") or [], labels)],
        },
        {
            "name": "Citations",
            "description": "Normalized citations attached to the briefing payload.",
            "content": [_render_citation_lines(citations, labels)],
        },
    ]
    return {
        "name": _collapse_whitespace(payload.get("title")) or "Finance Briefing",
        "description": _collapse_whitespace((payload.get("summary") or {}).get("headline") if isinstance(payload.get("summary"), Mapping) else ""),
        "owner": _collapse_whitespace(payload.get("owner")) or DEFAULT_OWNER,
        "tags": tags,
        "sections": sections,
        "meta": {
            "briefing_payload_type": BRIEFING_PAYLOAD_TYPE,
            "briefing_payload_version": BRIEFING_PAYLOAD_VERSION,
            "workflow": _collapse_whitespace(payload.get("workflow")),
            "as_of": _collapse_whitespace(payload.get("as_of")),
            "subject": dict(subject) if isinstance(subject, Mapping) else {},
            "citations": citations,
            "notebooklm_import_mode": NOTEBOOKLM_IMPORT_MODE,
            "generated_by": "attas.workflows.briefings",
        },
    }


__all__ = [
    "BRIEFING_PAYLOAD_TYPE",
    "BRIEFING_PAYLOAD_VERSION",
    "NOTEBOOKLM_IMPORT_MODE",
    "assemble_finance_briefing_payload",
    "briefing_to_report_document",
    "build_finance_catalysts",
    "build_finance_briefing_payload",
    "build_finance_citations",
    "build_finance_conflicting_evidence",
    "build_finance_facts",
    "build_finance_open_questions",
    "build_finance_risks",
    "build_finance_source_bundle",
    "build_finance_summary",
    "build_finance_takeaways",
    "build_source_url_bundle",
    "generate_notebooklm_pack",
    "morning_desk_briefing",
    "prepare_finance_briefing_context",
    "prepare_morning_desk_briefing_context",
    "prepare_research_roundup_context",
    "prepare_watchlist_check_context",
    "render_briefing_markdown",
    "research_roundup",
    "watchlist_check",
]
