"""
Typed data models for `prompits.dispatcher.models`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the dispatcher package
coordinates job routing, worker selection, and queue management.

Core types exposed here include `JobDetail` and `JobResult`, which carry the main
behavior or state managed by this module.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


JOB_TIMESTAMP_FIELDS = (
    "scheduled_for",
    "claimed_at",
    "completed_at",
    "created_at",
    "updated_at",
)

JOB_TEXT_FIELDS = (
    "id",
    "job_type",
    "status",
    "required_capability",
    "target_table",
    "source_url",
    "claimed_by",
    "error",
)

JOB_DICT_FIELDS = (
    "metadata",
    "result_summary",
)


def _normalize_timestamp_text(value: Any) -> str:
    """Internal helper to normalize the timestamp text."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.isoformat()
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


class JobDetail(BaseModel):
    """Represent a job detail."""
    model_config = ConfigDict(extra="allow")

    id: str
    job_type: str = "run"
    status: str = "queued"
    required_capability: str = ""
    capability_tags: List[str] = Field(default_factory=list)
    targets: List[str] = Field(default_factory=list)
    payload: Any = Field(default_factory=dict)
    target_table: str = ""
    source_url: str = ""
    parse_rules: Any = Field(default_factory=dict)
    priority: int = 100
    premium: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    scheduled_for: str = ""
    claimed_by: str = ""
    claimed_at: str = ""
    completed_at: str = ""
    result_summary: Dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    attempts: int = 0
    max_attempts: int = 1
    created_at: str = ""
    updated_at: str = ""

    @field_validator(*JOB_TEXT_FIELDS, mode="before")
    @classmethod
    def _normalize_text_fields(cls, value: Any) -> str:
        """Normalize nullable job text fields to plain strings."""
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        return str(value)

    @field_validator(*JOB_DICT_FIELDS, mode="before")
    @classmethod
    def _normalize_dict_fields(cls, value: Any) -> Dict[str, Any]:
        """Normalize nullable mapping fields to plain dictionaries."""
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return dict(value)
        return dict(value)

    @classmethod
    def from_row(cls, value: Mapping[str, Any] | "JobDetail" | None) -> "JobDetail":
        """Build an instance from row."""
        if isinstance(value, cls):
            return value
        row = dict(value or {})
        for field_name in JOB_TIMESTAMP_FIELDS:
            row[field_name] = _normalize_timestamp_text(row.get(field_name))
        return cls.model_validate(row)

    def to_row(self) -> Dict[str, Any]:
        """Convert the value to row."""
        row = self.model_dump(mode="python")
        for field_name in JOB_TIMESTAMP_FIELDS:
            value = row.get(field_name)
            if isinstance(value, str) and not value.strip():
                row[field_name] = None
        return row

    def to_payload(self) -> Dict[str, Any]:
        """Convert the value to payload."""
        return self.model_dump(mode="json")


class JobResult(BaseModel):
    """Represent a job result."""
    model_config = ConfigDict(extra="allow")

    job_id: str = ""
    worker_id: str = ""
    status: str = "completed"
    collected_rows: List[Dict[str, Any]] = Field(default_factory=list)
    additional_targets: List[Dict[str, Any]] = Field(default_factory=list)
    raw_payload: Any = None
    result_summary: Dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    target_table: str = ""

    @field_validator("result_summary", mode="before")
    @classmethod
    def _normalize_result_summary(cls, value: Any) -> Dict[str, Any]:
        """Normalize nullable result-summary payloads to plain dictionaries."""
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return dict(value)
        return dict(value)

    @classmethod
    def from_value(cls, value: Mapping[str, Any] | "JobResult" | None) -> "JobResult":
        """Build an instance from value."""
        if isinstance(value, cls):
            return value
        return cls.model_validate(dict(value or {}))

    def with_defaults(self, *, job_id: str, worker_id: str) -> "JobResult":
        """Handle with defaults for the job result."""
        data = self.model_dump(mode="python")
        data["job_id"] = str(data.get("job_id") or job_id)
        data["worker_id"] = str(data.get("worker_id") or worker_id)
        status = str(data.get("status") or "completed").strip().lower()
        if status not in {"completed", "failed", "retry", "stopped"}:
            status = "completed"
        data["status"] = status
        return self.__class__.model_validate(data)

    def to_payload(self) -> Dict[str, Any]:
        """Convert the value to payload."""
        return self.model_dump(mode="json")
