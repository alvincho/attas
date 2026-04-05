"""
Generic channel and destination helpers for `prompits.channels.runtime`.

Prompits is the base framework layer for FinMAS. This module keeps the first B2B
delivery lane contract generic so higher layers can describe channel delivery and
destination publishing state without coupling to product-specific workflow code.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Iterable, Mapping, Sequence


B2B_CHANNEL_KINDS = ("slack", "teams", "email")


def _coerce_object(value: Any) -> dict[str, Any]:
    """Return a mutable mapping when the input looks like one."""
    return dict(value) if isinstance(value, Mapping) else {}


def _coerce_list(value: Any) -> list[Any]:
    """Return a list when the input looks like one."""
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray, Mapping)):
        return list(value)
    return []


def _first_text(*values: Any) -> str:
    """Return the first non-empty text value."""
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _status_text(value: Any, *, default: str = "available") -> str:
    """Normalize delivery-style status labels."""
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    aliases = {
        "ok": "ready",
        "success": "delivered",
        "sent": "delivered",
        "done": "delivered",
        "published": "published",
        "complete": "delivered",
        "completed": "delivered",
        "draft": "ready",
        "prepared": "ready",
        "queued": "queued",
        "running": "queued",
        "processing": "queued",
        "warning": "attention",
        "error": "failed",
        "failed": "failed",
        "skipped": "skipped",
        "disabled": "disabled",
        "not_configured": "not_configured",
        "unavailable": "not_configured",
    }
    return aliases.get(raw, raw)


def _channel_kind(value: Any, *, fallback: str = "") -> str:
    """Infer the lane kind from a generic delivery descriptor."""
    raw = str(value or "").strip().lower()
    if not raw:
        return str(fallback or "").strip().lower()
    if "slack" in raw:
        return "slack"
    if "teams" in raw or "microsoft" in raw:
        return "teams"
    if "email" in raw or "mail" in raw:
        return "email"
    return str(fallback or raw).strip().lower()


def default_b2b_channels() -> list[dict[str, Any]]:
    """Return the starter B2B delivery lanes exposed by the framework."""
    return [
        {
            "kind": "slack",
            "label": "Slack",
            "status": "available",
            "detail": "Desk channel delivery lane.",
            "recipient": "",
            "destination": "",
            "actions": ["inspect_payload", "deliver"],
            "metadata": {},
        },
        {
            "kind": "teams",
            "label": "Teams",
            "status": "available",
            "detail": "Microsoft Teams delivery lane.",
            "recipient": "",
            "destination": "",
            "actions": ["inspect_payload", "deliver"],
            "metadata": {},
        },
        {
            "kind": "email",
            "label": "Email",
            "status": "available",
            "detail": "Direct email delivery lane.",
            "recipient": "",
            "destination": "",
            "actions": ["inspect_payload", "deliver"],
            "metadata": {},
        },
    ]


def _channel_actions(kind: str, normalized: Mapping[str, Any]) -> list[str]:
    """Return the generic operator actions for a delivery lane."""
    actions = ["inspect_payload"]
    if str(normalized.get("status") or "") == "delivered":
        actions.append("review_delivery")
    else:
        actions.append("deliver")
    if str(normalized.get("url") or "").strip():
        actions.append("open")
    if kind == "email" and str(normalized.get("recipient") or "").strip():
        actions.append("copy_recipient")
    return actions


def normalize_channel_lane(entry: Any, *, fallback_kind: str = "") -> dict[str, Any]:
    """Normalize a generic channel lane payload."""
    normalized = _coerce_object(entry)
    kind = _channel_kind(
        normalized.get("kind")
        or normalized.get("channel")
        or normalized.get("type")
        or normalized.get("provider")
        or normalized.get("lane")
        or fallback_kind,
        fallback=fallback_kind,
    )
    label = _first_text(normalized.get("label"), normalized.get("name"), kind.title())
    recipient = _first_text(
        normalized.get("recipient"),
        normalized.get("channel_name"),
        normalized.get("channel"),
        normalized.get("email"),
        normalized.get("team"),
        normalized.get("destination"),
    )
    destination = _first_text(
        normalized.get("destination"),
        normalized.get("webhook_url"),
        normalized.get("address"),
        normalized.get("url"),
        recipient,
    )
    detail = _first_text(
        normalized.get("detail"),
        normalized.get("message"),
        normalized.get("summary"),
        normalized.get("note"),
    )
    status = _status_text(
        normalized.get("status")
        or normalized.get("delivery_status")
        or normalized.get("state"),
        default="available",
    )
    payload = {
        "kind": kind or str(fallback_kind or "").strip().lower(),
        "label": label or "Channel",
        "status": status,
        "detail": detail,
        "recipient": recipient,
        "destination": destination,
        "url": _first_text(normalized.get("url"), normalized.get("message_url")),
        "actions": _channel_actions(kind or fallback_kind, normalized),
        "metadata": deepcopy(normalized),
    }
    return payload


def _lane_entries(summary: Mapping[str, Any], metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Collect explicit lane descriptors from summary and metadata blocks."""
    entries: list[dict[str, Any]] = []
    for source in (summary, metadata):
        for key in (
            "channel_deliveries",
            "deliveries",
            "channels",
            "destinations",
            "delivery_lanes",
        ):
            entries.extend(
                normalize_channel_lane(entry)
                for entry in _coerce_list(source.get(key))
            )
        for key in ("channel_status", "delivery_status", "destination_status"):
            mapping = _coerce_object(source.get(key))
            for lane_kind, lane_value in mapping.items():
                if isinstance(lane_value, Mapping):
                    entries.append(normalize_channel_lane(lane_value, fallback_kind=str(lane_kind)))
                elif lane_value is not None:
                    entries.append(
                        normalize_channel_lane(
                            {"status": lane_value, "kind": lane_kind},
                            fallback_kind=str(lane_kind),
                        )
                    )
    return [entry for entry in entries if entry.get("kind") in B2B_CHANNEL_KINDS]


def _merge_channel_catalog(
    *,
    explicit_entries: Iterable[Mapping[str, Any]],
    payload_preview: str = "",
) -> list[dict[str, Any]]:
    """Overlay explicit channel state onto the default lane catalog."""
    catalog = {entry["kind"]: deepcopy(entry) for entry in default_b2b_channels()}
    if payload_preview:
        for lane in catalog.values():
            lane["status"] = "ready"
            lane["detail"] = lane.get("detail") or "Delivery copy is ready."
            lane["payload_preview"] = payload_preview
    for entry in explicit_entries:
        kind = str(entry.get("kind") or "").strip().lower()
        if kind not in catalog:
            continue
        current = catalog[kind]
        current.update({key: value for key, value in dict(entry).items() if value not in (None, "")})
        current["kind"] = kind
        current["label"] = current.get("label") or kind.title()
        current["status"] = _status_text(current.get("status"), default=current.get("status") or "available")
        current["actions"] = _channel_actions(kind, current)
        if payload_preview and not current.get("payload_preview"):
            current["payload_preview"] = payload_preview
    return list(catalog.values())


def _normalize_notion_destination(summary: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize the Notion destination status."""
    publication = _coerce_object(summary.get("publication") or metadata.get("publication"))
    notion = _coerce_object(summary.get("notion") or publication.get("notion") or metadata.get("notion"))
    title = _first_text(
        notion.get("title"),
        notion.get("notion_title"),
        publication.get("notion_title"),
        summary.get("notion_title"),
    )
    markdown = _first_text(
        notion.get("markdown"),
        notion.get("notion_markdown"),
        publication.get("notion_markdown"),
        summary.get("notion_markdown"),
    )
    url = _first_text(
        notion.get("url"),
        notion.get("page_url"),
        summary.get("notion_page_url"),
        summary.get("notion_url"),
    )
    status = _status_text(
        notion.get("status")
        or summary.get("notion_status")
        or ("published" if url else "ready" if title or markdown else "not_configured"),
        default="not_configured",
    )
    detail = _first_text(
        notion.get("detail"),
        notion.get("message"),
        "Markdown ready for publication." if markdown else "",
    )
    actions = ["inspect_markdown"]
    if url:
        actions.append("open")
    return {
        "kind": "notion",
        "label": "Notion",
        "status": status,
        "title": title,
        "detail": detail,
        "url": url,
        "available": bool(title or markdown or url or notion),
        "actions": actions,
        "metadata": {
            "publication": deepcopy(publication),
            "notion": deepcopy(notion),
        },
    }


def _normalize_notebooklm_destination(summary: Mapping[str, Any], metadata: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize the NotebookLM export status."""
    notebooklm = _coerce_object(
        summary.get("notebooklm")
        or summary.get("notebooklm_pack")
        or summary.get("exports")
        or metadata.get("notebooklm")
    )
    directory = _first_text(
        notebooklm.get("directory"),
        summary.get("notebooklm_directory"),
        summary.get("export_directory"),
    )
    source_url_bundle = _first_text(
        notebooklm.get("source_url_bundle"),
        summary.get("source_url_bundle"),
    )
    mode = _first_text(
        notebooklm.get("mode"),
        notebooklm.get("import_mode"),
        summary.get("notebooklm_import_mode"),
        _coerce_object(metadata.get("meta")).get("notebooklm_import_mode"),
    )
    status = _status_text(
        notebooklm.get("status")
        or summary.get("notebooklm_status")
        or ("exported" if directory or source_url_bundle else "ready" if mode else "not_configured"),
        default="not_configured",
    )
    detail = _first_text(
        notebooklm.get("detail"),
        notebooklm.get("beta_note"),
        "NotebookLM export pack is ready." if directory or source_url_bundle else "",
    )
    actions = ["inspect_export"]
    if directory:
        actions.append("reveal_directory")
    return {
        "kind": "notebooklm",
        "label": "NotebookLM",
        "status": status,
        "detail": detail,
        "directory": directory,
        "mode": mode,
        "source_url_bundle": source_url_bundle,
        "available": bool(directory or source_url_bundle or mode or notebooklm),
        "actions": actions,
        "metadata": deepcopy(notebooklm),
    }


def build_delivery_snapshot(result_summary: Any = None, *, metadata: Any = None) -> dict[str, Any]:
    """Build a generic destination snapshot for operator-facing UIs."""
    result_mapping = _coerce_object(result_summary)
    summary = _coerce_object(result_mapping.get("summary") or result_mapping)
    metadata_mapping = _coerce_object(metadata)
    publication = _coerce_object(summary.get("publication") or metadata_mapping.get("publication"))
    payload_preview = _first_text(
        summary.get("channel_text"),
        publication.get("channel_text"),
    )
    explicit_lanes = _lane_entries(summary, metadata_mapping)
    channels = _merge_channel_catalog(explicit_entries=explicit_lanes, payload_preview=payload_preview)
    notion = _normalize_notion_destination(summary, metadata_mapping)
    notebooklm = _normalize_notebooklm_destination(summary, metadata_mapping)
    return {
        "notion": notion,
        "notebooklm": notebooklm,
        "channels": channels,
        "publication_preview": payload_preview,
    }


__all__ = [
    "B2B_CHANNEL_KINDS",
    "build_delivery_snapshot",
    "default_b2b_channels",
    "normalize_channel_lane",
]
