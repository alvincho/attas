"""
Shared dispatcher-backed report feed helpers.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Mapping

from prompits.core.schema import TableSchema
from prompits.dispatcher.schema import ensure_dispatcher_tables


TABLE_DISPATCHER_REPORT_ITEMS = "dispatcher_report_items"
REPORT_ITEM_KINDS = {"report", "alert"}
REPORT_ITEM_SEVERITIES = {"info", "success", "warning", "error"}
REPORT_ITEM_RESPONSE_STATUSES = {"new", "acknowledged", "resolved"}


def _as_text(value: Any) -> str:
    """Return a normalized string."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _as_bool(value: Any, *, default: bool = False) -> bool:
    """Return a best-effort bool."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = _as_text(value).lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def normalize_report_item_kind(value: Any, *, default: str = "report") -> str:
    """Return a normalized report-item kind."""
    normalized = _as_text(value).lower()
    return normalized if normalized in REPORT_ITEM_KINDS else default


def normalize_report_item_severity(value: Any, *, default: str = "info") -> str:
    """Return a normalized report-item severity."""
    normalized = _as_text(value).lower()
    return normalized if normalized in REPORT_ITEM_SEVERITIES else default


def normalize_report_item_response_status(value: Any, *, default: str = "new") -> str:
    """Return a normalized report-item response status."""
    normalized = _as_text(value).lower().replace(" ", "_")
    return normalized if normalized in REPORT_ITEM_RESPONSE_STATUSES else default


def _json_mapping(value: Any) -> dict[str, Any]:
    """Return one JSON-safe mapping."""
    return dict(value) if isinstance(value, Mapping) else {}


def report_item_payload(row: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Return one normalized dispatcher report-item payload."""
    mapping = row if isinstance(row, Mapping) else {}
    return {
        "id": _as_text(mapping.get("id")),
        "kind": normalize_report_item_kind(mapping.get("kind")),
        "source_key": _as_text(mapping.get("source_key")).lower(),
        "source_label": _as_text(mapping.get("source_label")),
        "category_key": _as_text(mapping.get("category_key")).lower(),
        "title": _as_text(mapping.get("title")),
        "summary": _as_text(mapping.get("summary")),
        "body": _as_text(mapping.get("body")),
        "status": _as_text(mapping.get("status")).lower(),
        "severity": normalize_report_item_severity(mapping.get("severity")),
        "metrics": _json_mapping(mapping.get("metrics")),
        "payload": _json_mapping(mapping.get("payload")),
        "response_status": normalize_report_item_response_status(mapping.get("response_status")),
        "response_note": _as_text(mapping.get("response_note")),
        "response_payload": _json_mapping(mapping.get("response_payload")),
        "responded_by": _as_text(mapping.get("responded_by")),
        "responded_at": _as_text(mapping.get("responded_at")),
        "created_at": _as_text(mapping.get("created_at")),
        "updated_at": _as_text(mapping.get("updated_at")),
        "derived": _as_bool(mapping.get("derived"), default=False),
    }


def dispatcher_report_items_schema_dict() -> dict[str, object]:
    """Return the dispatcher-shared report item schema."""
    return {
        "name": TABLE_DISPATCHER_REPORT_ITEMS,
        "description": "Shared console-visible report and alert feed items for dispatcher-backed work.",
        "primary_key": ["id"],
        "rowSchema": {
            "id": {"type": "string"},
            "kind": {"type": "string"},
            "source_key": {"type": "string"},
            "source_label": {"type": "string"},
            "category_key": {"type": "string"},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "body": {"type": "string"},
            "status": {"type": "string"},
            "severity": {"type": "string"},
            "metrics": {"type": "json"},
            "payload": {"type": "json"},
            "response_status": {"type": "string"},
            "response_note": {"type": "string"},
            "response_payload": {"type": "json"},
            "responded_by": {"type": "string"},
            "responded_at": {"type": "datetime"},
            "created_at": {"type": "datetime"},
            "updated_at": {"type": "datetime"},
        },
    }


def dispatcher_report_items_table_schema() -> TableSchema:
    """Return the dispatcher report-item table schema."""
    return TableSchema(dispatcher_report_items_schema_dict())


def ensure_dispatcher_report_tables(pool: Any | None) -> None:
    """Ensure shared dispatcher report tables exist."""
    if pool is None:
        return
    ensure_dispatcher_tables(
        pool,
        [TABLE_DISPATCHER_REPORT_ITEMS],
        extra_schemas={TABLE_DISPATCHER_REPORT_ITEMS: dispatcher_report_items_table_schema()},
    )
    query = getattr(pool, "_Query", None)
    if not callable(query):
        return
    quoted = getattr(pool, "_quoted_table_name", None)
    table_name = quoted(TABLE_DISPATCHER_REPORT_ITEMS) if callable(quoted) else TABLE_DISPATCHER_REPORT_ITEMS
    query(
        f"""
        create index if not exists dispatcher_report_items_created_idx
        on {table_name} (created_at desc, updated_at desc)
        """
    )
    query(
        f"""
        create index if not exists dispatcher_report_items_kind_idx
        on {table_name} (kind, created_at desc)
        """
    )
    query(
        f"""
        create index if not exists dispatcher_report_items_source_idx
        on {table_name} (source_key, created_at desc)
        """
    )
    query(
        f"""
        create index if not exists dispatcher_report_items_response_idx
        on {table_name} (response_status, created_at desc)
        """
    )
