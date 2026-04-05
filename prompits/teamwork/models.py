"""
Typed data models for `prompits.teamwork.models`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the teamwork package models
cooperative agent workflows and their supporting runtime pieces.

Experimental notice: these models are intended to stay small and stable, but the
package itself is still under active development and some fields may evolve while the
teamwork contract is being finalized.

The models in this module intentionally define a small, stable contract for managed
work so higher layers can reason about work items, tickets, assignments, execution
state, and result summaries without depending on raw dispatcher rows.
"""

from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field

from prompits.dispatcher.models import JOB_TIMESTAMP_FIELDS, JobDetail, JobResult


TEAMWORK_API_VERSION = "teamwork.v1"
MANAGED_WORK_METADATA_KEY = "managed_work"
TERMINAL_JOB_STATUSES = {"completed", "failed", "stopped", "cancelled", "deleted"}
ATTENTION_JOB_STATUSES = {"failed", "stopped", "cancelled", "deleted"}


class ManagedWorkItem(BaseModel):
    """Stable description of the requested work payload."""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    title: str = ""
    required_capability: str = ""
    targets: List[str] = Field(default_factory=list)
    payload: Any = Field(default_factory=dict)
    target_table: str = ""
    source_url: str = ""
    parse_rules: Any = Field(default_factory=dict)
    capability_tags: List[str] = Field(default_factory=list)
    job_type: str = "run"
    priority: int = 100
    premium: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ManagedTicketRef(BaseModel):
    """Stable identifier block for one managed ticket."""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    work_id: str = ""
    source: str = "manual"
    schedule_id: str = ""
    workflow_id: str = ""
    title: str = ""
    created_at: str = ""
    updated_at: str = ""


class ManagedManagerAssignment(BaseModel):
    """Stable manager assignment details for one managed ticket or schedule."""

    model_config = ConfigDict(extra="allow")

    manager_address: str = ""
    manager_name: str = ""
    manager_party: str = ""
    assigned_at: str = ""
    assignment_source: str = "manual"


class ManagedWorkerAssignment(BaseModel):
    """Stable worker assignment details for one managed ticket."""

    model_config = ConfigDict(extra="allow")

    worker_id: str = ""
    worker_name: str = ""
    worker_address: str = ""
    assigned_at: str = ""
    claimed_at: str = ""
    completed_at: str = ""
    status: str = "unassigned"


class TeamWorkerHireState(BaseModel):
    """Stable manager-hire state for one teamwork worker."""

    model_config = ConfigDict(extra="allow")

    status: str = "awaiting_hire"
    hire_required: bool = True
    manager_address: str = ""
    manager_name: str = ""
    manager_party: str = ""
    hired_at: str = ""
    assignment_source: str = ""


class ManagedExecutionState(BaseModel):
    """Stable execution status for one managed ticket."""

    model_config = ConfigDict(extra="allow")

    status: str = "queued"
    scheduled_for: str = ""
    claimed_at: str = ""
    completed_at: str = ""
    created_at: str = ""
    updated_at: str = ""
    attempts: int = 0
    max_attempts: int = 1
    error: str = ""
    attention_required: bool = False


class ManagedResultSummary(BaseModel):
    """Stable result summary for one managed ticket."""

    model_config = ConfigDict(extra="allow")

    status: str = "queued"
    summary: Dict[str, Any] = Field(default_factory=dict)
    error: str = ""
    target_table: str = ""
    stored_rows: int = 0
    reissued_ticket_id: str = ""
    raw_payload_recorded: bool = False


class ManagedWorkTicket(BaseModel):
    """Stable managed-work ticket payload returned to higher layers."""

    model_config = ConfigDict(extra="allow")

    ticket: ManagedTicketRef = Field(default_factory=ManagedTicketRef)
    work_item: ManagedWorkItem = Field(default_factory=ManagedWorkItem)
    manager_assignment: ManagedManagerAssignment = Field(default_factory=ManagedManagerAssignment)
    worker_assignment: ManagedWorkerAssignment = Field(default_factory=ManagedWorkerAssignment)
    execution_state: ManagedExecutionState = Field(default_factory=ManagedExecutionState)
    result_summary: ManagedResultSummary = Field(default_factory=ManagedResultSummary)


class ManagedScheduleState(BaseModel):
    """Stable schedule state for saved managed work."""

    model_config = ConfigDict(extra="allow")

    id: str = ""
    name: str = ""
    status: str = "scheduled"
    repeat_frequency: str = "once"
    schedule_timezone: str = "UTC"
    schedule_time: str = ""
    schedule_times: List[str] = Field(default_factory=list)
    schedule_weekdays: List[str] = Field(default_factory=list)
    schedule_day_of_month: int | None = None
    schedule_days_of_month: List[int] = Field(default_factory=list)
    scheduled_for: str = ""
    issue_attempts: int = 0
    last_error: str = ""
    last_ticket_id: str = ""
    issued_at: str = ""
    created_at: str = ""
    updated_at: str = ""


class ManagedWorkSchedule(BaseModel):
    """Stable saved managed-work schedule payload."""

    model_config = ConfigDict(extra="allow")

    schedule: ManagedScheduleState = Field(default_factory=ManagedScheduleState)
    work_item: ManagedWorkItem = Field(default_factory=ManagedWorkItem)
    manager_assignment: ManagedManagerAssignment = Field(default_factory=ManagedManagerAssignment)


class ManagedWorkMonitor(BaseModel):
    """Stable managed-work monitor payload for UI consumers."""

    model_config = ConfigDict(extra="allow")

    api_version: str = TEAMWORK_API_VERSION
    manager_assignment: ManagedManagerAssignment = Field(default_factory=ManagedManagerAssignment)
    summary: Dict[str, Any] = Field(default_factory=dict)
    workers: List[Dict[str, Any]] = Field(default_factory=list)
    tickets: List[ManagedWorkTicket] = Field(default_factory=list)
    schedules: List[ManagedWorkSchedule] = Field(default_factory=list)
    captured_at: str = ""
    counts: Dict[str, int] = Field(default_factory=dict)


class ManagedTicketRequest(BaseModel):
    """Request contract for manual managed ticket creation."""

    model_config = ConfigDict(extra="allow")

    manager_address: str | None = None
    manager_name: str = ""
    manager_party: str = ""
    title: str = ""
    required_capability: str = Field(min_length=1)
    targets: List[str] = Field(default_factory=list)
    symbols: List[str] = Field(default_factory=list)
    payload: dict | list | str | int | float | bool | None = None
    target_table: str = ""
    source_url: str = ""
    parse_rules: dict | list | str | int | float | bool | None = None
    capability_tags: List[str] = Field(default_factory=list)
    job_type: str = "run"
    priority: int = 100
    premium: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)
    scheduled_for: str = ""
    max_attempts: int = 3
    work_id: str = ""
    ticket_id: str = ""
    source: str = "manual"
    workflow_id: str = ""


class ManagedScheduleRequest(ManagedTicketRequest):
    """Request contract for saved managed-work schedules."""

    name: str = ""
    repeat_frequency: str = "once"
    schedule_timezone: str = "UTC"
    schedule_time: str = ""
    schedule_times: List[str] = Field(default_factory=list)
    schedule_weekdays: List[str] = Field(default_factory=list)
    schedule_day_of_month: int | None = None
    schedule_days_of_month: List[int] = Field(default_factory=list)
    scheduled_for: str = ""


__all__ = [
    "ATTENTION_JOB_STATUSES",
    "JOB_TIMESTAMP_FIELDS",
    "JobDetail",
    "JobResult",
    "MANAGED_WORK_METADATA_KEY",
    "ManagedExecutionState",
    "ManagedManagerAssignment",
    "ManagedResultSummary",
    "ManagedScheduleRequest",
    "ManagedScheduleState",
    "ManagedWorkMonitor",
    "ManagedTicketRef",
    "ManagedTicketRequest",
    "ManagedWorkItem",
    "ManagedWorkSchedule",
    "ManagedWorkTicket",
    "ManagedWorkerAssignment",
    "TeamWorkerHireState",
    "TEAMWORK_API_VERSION",
    "TERMINAL_JOB_STATUSES",
]
