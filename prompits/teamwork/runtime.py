"""
Runtime helpers for `prompits.teamwork.runtime`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the teamwork package models
cooperative agent workflows and their supporting runtime pieces.

Experimental notice: the teamwork runtime is still under active development, and
normalization rules or managed-work helper behavior may continue to evolve.

Important callables in this file include `normalize_teamwork_config`,
`build_managed_work_metadata`, `managed_ticket_from_job_row`, and
`managed_schedule_from_row`, which together define the shared managed-work contract
used by BossPulser and teamwork bosses.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Mapping

from prompits.dispatcher.runtime import (
    ConfigInput,
    build_dispatch_job,
    build_id,
    build_raw_payload_row,
    build_result_row,
    build_worker_history_entry,
    build_worker_registration,
    coerce_job_detail,
    coerce_job_result,
    coerce_json_object,
    coerce_json_payload,
    coerce_record_list,
    job_is_ready,
    job_matches_capabilities,
    job_sort_key,
    normalize_capabilities,
    normalize_string_list,
    normalize_target,
    parse_datetime_value,
    prepare_table_records,
    read_dispatcher_config,
    utcnow_iso,
)
from prompits.teamwork.models import (
    ATTENTION_JOB_STATUSES,
    MANAGED_WORK_METADATA_KEY,
    ManagedExecutionState,
    ManagedManagerAssignment,
    ManagedResultSummary,
    ManagedScheduleState,
    ManagedWorkMonitor,
    ManagedTicketRef,
    ManagedWorkItem,
    ManagedWorkSchedule,
    ManagedWorkTicket,
    ManagedWorkerAssignment,
    TeamWorkerHireState,
    TEAMWORK_API_VERSION,
)


def read_teamwork_config(config: ConfigInput) -> Dict[str, Any]:
    """Read the teamwork config."""
    return read_dispatcher_config(config)


def normalize_teamwork_config(config: ConfigInput, *, role: str = "") -> Dict[str, Any]:
    """Normalize the teamwork config."""
    loaded = read_teamwork_config(config)
    normalized = dict(loaded or {})

    teamwork_settings = loaded.get("teamwork") if isinstance(loaded.get("teamwork"), Mapping) else {}
    dispatcher_settings = loaded.get("dispatcher") if isinstance(loaded.get("dispatcher"), Mapping) else {}
    role_settings = loaded.get(role) if role and isinstance(loaded.get(role), Mapping) else {}
    manager_settings = loaded.get("manager") if isinstance(loaded.get("manager"), Mapping) else {}

    merged_settings: Dict[str, Any] = {}
    for source in (teamwork_settings, dispatcher_settings, role_settings):
        if isinstance(source, Mapping):
            merged_settings.update(dict(source))
    normalized["dispatcher"] = merged_settings

    address_candidates = (
        merged_settings.get("manager_address"),
        merged_settings.get("dispatcher_address"),
        merged_settings.get("upstream_manager_address"),
        manager_settings.get("manager_address"),
        manager_settings.get("dispatcher_address"),
        loaded.get("manager_address"),
        loaded.get("dispatcher_address"),
    )
    dispatcher_address = next((str(value or "").strip() for value in address_candidates if str(value or "").strip()), "")
    if dispatcher_address:
        normalized["dispatcher_address"] = dispatcher_address

    party_candidates = (
        merged_settings.get("manager_party"),
        merged_settings.get("dispatcher_party"),
        merged_settings.get("upstream_manager_party"),
        manager_settings.get("manager_party"),
        manager_settings.get("dispatcher_party"),
        loaded.get("manager_party"),
        loaded.get("dispatcher_party"),
        loaded.get("party"),
    )
    dispatcher_party = next((str(value or "").strip() for value in party_candidates if str(value or "").strip()), "")
    if dispatcher_party:
        normalized["dispatcher_party"] = dispatcher_party

    return normalized


def _copy_payload(value: Any) -> Any:
    """Return a JSON-like payload copy."""
    if isinstance(value, Mapping):
        return copy.deepcopy(dict(value))
    if isinstance(value, list):
        return copy.deepcopy(list(value))
    return copy.deepcopy(value)


def _safe_int(value: Any, default: int = 0) -> int:
    """Safely coerce an integer value."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _managed_work_payload(metadata: Any) -> dict[str, Any]:
    """Return the managed-work metadata payload."""
    normalized = coerce_json_object(metadata)
    return coerce_json_object(normalized.get(MANAGED_WORK_METADATA_KEY))


def _external_metadata(metadata: Any) -> dict[str, Any]:
    """Return metadata without the managed-work envelope."""
    normalized = coerce_json_object(metadata)
    normalized.pop(MANAGED_WORK_METADATA_KEY, None)
    return normalized


def _ticket_source(managed: Mapping[str, Any]) -> str:
    """Return the normalized ticket source."""
    normalized = str(managed.get("source") or "").strip().lower()
    if normalized:
        return normalized
    if str(managed.get("schedule_id") or "").strip():
        return "schedule"
    return "manual"


def build_managed_work_metadata(
    metadata: Any = None,
    *,
    work_id: str = "",
    ticket_id: str = "",
    source: str = "manual",
    manager_address: str = "",
    manager_name: str = "",
    manager_party: str = "",
    schedule_id: str = "",
    workflow_id: str = "",
    title: str = "",
    assigned_at: str = "",
) -> dict[str, Any]:
    """Build or update the stable managed-work metadata envelope."""
    base_metadata = coerce_json_object(metadata)
    existing = _managed_work_payload(base_metadata)
    resolved_source = str(source or existing.get("source") or "manual").strip().lower() or "manual"
    resolved_assigned_at = str(assigned_at or existing.get("assigned_at") or utcnow_iso()).strip()

    existing_manager_assignment = coerce_json_object(existing.get("manager_assignment"))
    manager_assignment = ManagedManagerAssignment.model_validate(
        {
            **existing_manager_assignment,
            "manager_address": str(
                manager_address or existing_manager_assignment.get("manager_address") or ""
            ).strip(),
            "manager_name": str(manager_name or existing_manager_assignment.get("manager_name") or "").strip(),
            "manager_party": str(
                manager_party or existing_manager_assignment.get("manager_party") or ""
            ).strip(),
            "assigned_at": str(
                existing_manager_assignment.get("assigned_at") or resolved_assigned_at
            ).strip(),
            "assignment_source": str(
                existing_manager_assignment.get("assignment_source") or resolved_source
            ).strip().lower() or "manual",
        }
    ).model_dump(mode="json")

    managed_payload = {
        **existing,
        "api_version": TEAMWORK_API_VERSION,
        "work_id": str(work_id or existing.get("work_id") or ticket_id or "").strip(),
        "ticket_id": str(ticket_id or existing.get("ticket_id") or "").strip(),
        "source": resolved_source,
        "assigned_at": resolved_assigned_at,
        "manager_assignment": manager_assignment,
    }
    if schedule_id or existing.get("schedule_id"):
        managed_payload["schedule_id"] = str(schedule_id or existing.get("schedule_id") or "").strip()
    if workflow_id or existing.get("workflow_id"):
        managed_payload["workflow_id"] = str(workflow_id or existing.get("workflow_id") or "").strip()
    if title or existing.get("title"):
        managed_payload["title"] = str(title or existing.get("title") or "").strip()

    base_metadata[MANAGED_WORK_METADATA_KEY] = managed_payload
    return base_metadata


def build_team_worker_hire_state(
    current: Any = None,
    *,
    hire_required: bool = True,
    manager_address: str = "",
    manager_name: str = "",
    manager_party: str = "",
    hired_at: str = "",
    assignment_source: str = "",
    status: str = "",
) -> dict[str, Any]:
    """Build the stable worker-hire state payload."""
    existing = coerce_json_object(current)
    resolved_manager_address = str(manager_address or existing.get("manager_address") or "").strip()
    resolved_manager_name = str(manager_name or existing.get("manager_name") or "").strip()
    resolved_manager_party = str(manager_party or existing.get("manager_party") or "").strip()
    resolved_hire_required = bool(existing.get("hire_required")) if existing else False
    if hire_required or not existing:
        resolved_hire_required = bool(hire_required)
    resolved_hired_at = str(
        hired_at
        or existing.get("hired_at")
        or (utcnow_iso() if resolved_manager_address else "")
    ).strip()
    resolved_status = str(
        status
        or existing.get("status")
        or ("hired" if resolved_manager_address else "awaiting_hire")
    ).strip().lower() or ("hired" if resolved_manager_address else "awaiting_hire")
    if not resolved_manager_address:
        resolved_hired_at = ""
        if resolved_hire_required:
            resolved_status = "awaiting_hire"
    payload = TeamWorkerHireState.model_validate(
        {
            **existing,
            "status": resolved_status,
            "hire_required": resolved_hire_required,
            "manager_address": resolved_manager_address,
            "manager_name": resolved_manager_name,
            "manager_party": resolved_manager_party,
            "hired_at": resolved_hired_at,
            "assignment_source": str(
                assignment_source or existing.get("assignment_source") or ("hire" if resolved_manager_address else "")
            ).strip().lower(),
        }
    )
    return payload.model_dump(mode="json")


def managed_ticket_from_job_row(
    job_row: Mapping[str, Any] | None,
    *,
    manager_address: str = "",
    manager_name: str = "",
    manager_party: str = "",
) -> dict[str, Any]:
    """Normalize one dispatcher job row into the managed-work ticket contract."""
    job = coerce_job_detail(job_row)
    row = job.model_dump(mode="python")
    metadata = coerce_json_object(row.get("metadata"))
    managed = _managed_work_payload(metadata)
    external_metadata = _external_metadata(metadata)
    ticket_source = _ticket_source(managed)
    title = str(
        managed.get("title")
        or row.get("required_capability")
        or managed.get("ticket_id")
        or row.get("id")
        or ""
    ).strip()

    manager_assignment = ManagedManagerAssignment.model_validate(
        {
            **coerce_json_object(managed.get("manager_assignment")),
            "manager_address": str(
                manager_address
                or coerce_json_object(managed.get("manager_assignment")).get("manager_address")
                or ""
            ).strip(),
            "manager_name": str(
                manager_name
                or coerce_json_object(managed.get("manager_assignment")).get("manager_name")
                or ""
            ).strip(),
            "manager_party": str(
                manager_party
                or coerce_json_object(managed.get("manager_assignment")).get("manager_party")
                or ""
            ).strip(),
            "assigned_at": str(
                coerce_json_object(managed.get("manager_assignment")).get("assigned_at")
                or managed.get("assigned_at")
                or row.get("created_at")
                or ""
            ).strip(),
            "assignment_source": str(
                coerce_json_object(managed.get("manager_assignment")).get("assignment_source")
                or ticket_source
            ).strip().lower() or "manual",
        }
    )

    worker_assignment_data = coerce_json_object(managed.get("worker_assignment"))
    derived_worker_status = str(worker_assignment_data.get("status") or "").strip().lower()
    if not derived_worker_status:
        if str(row.get("claimed_by") or "").strip():
            derived_worker_status = str(row.get("status") or "claimed").strip().lower() or "claimed"
        elif str(row.get("status") or "").strip().lower() in ATTENTION_JOB_STATUSES:
            derived_worker_status = str(row.get("status") or "").strip().lower()
        else:
            derived_worker_status = "unassigned"
    worker_assignment = ManagedWorkerAssignment.model_validate(
        {
            **worker_assignment_data,
            "worker_id": str(
                worker_assignment_data.get("worker_id")
                or row.get("claimed_by")
                or ""
            ).strip(),
            "worker_name": str(worker_assignment_data.get("worker_name") or "").strip(),
            "worker_address": str(worker_assignment_data.get("worker_address") or "").strip(),
            "assigned_at": str(
                worker_assignment_data.get("assigned_at")
                or row.get("claimed_at")
                or ""
            ).strip(),
            "claimed_at": str(
                worker_assignment_data.get("claimed_at")
                or row.get("claimed_at")
                or ""
            ).strip(),
            "completed_at": str(
                worker_assignment_data.get("completed_at")
                or row.get("completed_at")
                or ""
            ).strip(),
            "status": derived_worker_status,
        }
    )

    execution_state = ManagedExecutionState.model_validate(
        {
            **coerce_json_object(managed.get("execution_state")),
            "status": str(row.get("status") or "queued").strip().lower() or "queued",
            "scheduled_for": str(row.get("scheduled_for") or "").strip(),
            "claimed_at": str(row.get("claimed_at") or "").strip(),
            "completed_at": str(row.get("completed_at") or "").strip(),
            "created_at": str(row.get("created_at") or "").strip(),
            "updated_at": str(row.get("updated_at") or row.get("created_at") or "").strip(),
            "attempts": max(_safe_int(row.get("attempts"), 0), 0),
            "max_attempts": max(_safe_int(row.get("max_attempts"), 1), 1),
            "error": str(row.get("error") or "").strip(),
            "attention_required": str(row.get("status") or "").strip().lower() in ATTENTION_JOB_STATUSES,
        }
    )

    row_summary = coerce_json_object(row.get("result_summary"))
    managed_summary = coerce_json_object(managed.get("result_summary"))
    merged_summary = dict(managed_summary)
    merged_summary.update(row_summary)
    result_summary = ManagedResultSummary.model_validate(
        {
            **managed_summary,
            "status": str(row.get("status") or "queued").strip().lower() or "queued",
            "summary": merged_summary,
            "error": str(row.get("error") or merged_summary.get("last_error") or "").strip(),
            "target_table": str(row.get("target_table") or managed_summary.get("target_table") or "").strip(),
            "stored_rows": max(
                _safe_int(
                    merged_summary.get("stored_rows")
                    or merged_summary.get("rows")
                    or merged_summary.get("row_count"),
                    0,
                ),
                0,
            ),
            "reissued_ticket_id": str(
                merged_summary.get("reissued_ticket_id")
                or merged_summary.get("reissued_job_id")
                or ""
            ).strip(),
            "raw_payload_recorded": bool(
                merged_summary.get("raw_payload_recorded")
                or merged_summary.get("raw_record")
                or False
            ),
        }
    )

    payload = ManagedWorkTicket(
        ticket=ManagedTicketRef(
            id=str(managed.get("ticket_id") or row.get("id") or "").strip(),
            work_id=str(managed.get("work_id") or row.get("id") or "").strip(),
            source=ticket_source,
            schedule_id=str(managed.get("schedule_id") or "").strip(),
            workflow_id=str(managed.get("workflow_id") or "").strip(),
            title=title,
            created_at=str(row.get("created_at") or "").strip(),
            updated_at=str(row.get("updated_at") or row.get("created_at") or "").strip(),
        ),
        work_item=ManagedWorkItem(
            id=str(managed.get("work_id") or row.get("id") or "").strip(),
            title=title,
            required_capability=str(row.get("required_capability") or "").strip(),
            targets=list(normalize_string_list(row.get("targets"))),
            payload=_copy_payload(row.get("payload")),
            target_table=str(row.get("target_table") or "").strip(),
            source_url=str(row.get("source_url") or "").strip(),
            parse_rules=_copy_payload(row.get("parse_rules")),
            capability_tags=list(normalize_string_list(row.get("capability_tags"))),
            job_type=str(row.get("job_type") or "run").strip() or "run",
            priority=_safe_int(row.get("priority"), 100),
            premium=bool(row.get("premium")),
            metadata=external_metadata,
        ),
        manager_assignment=manager_assignment,
        worker_assignment=worker_assignment,
        execution_state=execution_state,
        result_summary=result_summary,
    )
    return payload.model_dump(mode="json")


def managed_schedule_from_row(
    schedule_row: Mapping[str, Any] | None,
    *,
    manager_address: str = "",
    manager_name: str = "",
    manager_party: str = "",
) -> dict[str, Any]:
    """Normalize one saved schedule row into the managed-work schedule contract."""
    row = dict(schedule_row or {})
    metadata = coerce_json_object(row.get("metadata"))
    managed = _managed_work_payload(metadata)
    external_metadata = _external_metadata(metadata)
    resolved_source = _ticket_source(managed)
    title = str(
        managed.get("title")
        or row.get("name")
        or row.get("required_capability")
        or row.get("id")
        or ""
    ).strip()
    manager_assignment = ManagedManagerAssignment.model_validate(
        {
            **coerce_json_object(managed.get("manager_assignment")),
            "manager_address": str(
                manager_address
                or coerce_json_object(managed.get("manager_assignment")).get("manager_address")
                or row.get("dispatcher_address")
                or ""
            ).strip(),
            "manager_name": str(
                manager_name
                or coerce_json_object(managed.get("manager_assignment")).get("manager_name")
                or ""
            ).strip(),
            "manager_party": str(
                manager_party
                or coerce_json_object(managed.get("manager_assignment")).get("manager_party")
                or ""
            ).strip(),
            "assigned_at": str(
                coerce_json_object(managed.get("manager_assignment")).get("assigned_at")
                or managed.get("assigned_at")
                or row.get("created_at")
                or ""
            ).strip(),
            "assignment_source": str(
                coerce_json_object(managed.get("manager_assignment")).get("assignment_source")
                or resolved_source
            ).strip().lower() or "manual",
        }
    )
    payload = ManagedWorkSchedule(
        schedule=ManagedScheduleState(
            id=str(row.get("id") or "").strip(),
            name=str(row.get("name") or title).strip(),
            status=str(row.get("status") or "scheduled").strip().lower() or "scheduled",
            repeat_frequency=str(row.get("repeat_frequency") or "once").strip().lower() or "once",
            schedule_timezone=str(row.get("schedule_timezone") or "UTC").strip() or "UTC",
            schedule_time=str(row.get("schedule_time") or "").strip(),
            schedule_times=list(row.get("schedule_times") or []),
            schedule_weekdays=list(row.get("schedule_weekdays") or []),
            schedule_day_of_month=row.get("schedule_day_of_month"),
            schedule_days_of_month=list(row.get("schedule_days_of_month") or []),
            scheduled_for=str(row.get("scheduled_for") or "").strip(),
            issue_attempts=max(_safe_int(row.get("issue_attempts"), 0), 0),
            last_error=str(row.get("last_error") or "").strip(),
            last_ticket_id=str(
                row.get("dispatcher_job_id")
                or managed.get("ticket_id")
                or ""
            ).strip(),
            issued_at=str(row.get("issued_at") or "").strip(),
            created_at=str(row.get("created_at") or "").strip(),
            updated_at=str(row.get("updated_at") or row.get("created_at") or "").strip(),
        ),
        work_item=ManagedWorkItem(
            id=str(managed.get("work_id") or row.get("id") or "").strip(),
            title=title,
            required_capability=str(row.get("required_capability") or "").strip(),
            targets=list(normalize_string_list(row.get("targets"))),
            payload=_copy_payload(row.get("payload")),
            target_table=str(row.get("target_table") or "").strip(),
            source_url=str(row.get("source_url") or "").strip(),
            parse_rules=_copy_payload(row.get("parse_rules")),
            capability_tags=list(normalize_string_list(row.get("capability_tags"))),
            job_type=str(row.get("job_type") or "run").strip() or "run",
            priority=_safe_int(row.get("priority"), 100),
            premium=bool(row.get("premium")),
            metadata=external_metadata,
        ),
        manager_assignment=manager_assignment,
    )
    return payload.model_dump(mode="json")


def build_managed_work_monitor(
    *,
    manager_assignment: Mapping[str, Any] | None = None,
    summary: Mapping[str, Any] | None = None,
    workers: list[Mapping[str, Any]] | None = None,
    tickets: list[Mapping[str, Any]] | None = None,
    schedules: list[Mapping[str, Any]] | None = None,
    captured_at: str = "",
) -> dict[str, Any]:
    """Build the stable managed-work monitor envelope."""
    ticket_models = [
        ManagedWorkTicket.model_validate(ticket).model_dump(mode="json")
        for ticket in (tickets or [])
        if isinstance(ticket, Mapping)
    ]
    schedule_models = [
        ManagedWorkSchedule.model_validate(schedule).model_dump(mode="json")
        for schedule in (schedules or [])
        if isinstance(schedule, Mapping)
    ]
    payload = ManagedWorkMonitor(
        manager_assignment=ManagedManagerAssignment.model_validate(manager_assignment or {}),
        summary=dict(summary or {}),
        workers=[dict(worker) for worker in (workers or []) if isinstance(worker, Mapping)],
        tickets=ticket_models,
        schedules=schedule_models,
        captured_at=str(captured_at or utcnow_iso()).strip(),
        counts={
            "tickets": len(ticket_models),
            "schedules": len(schedule_models),
            "workers": len([worker for worker in (workers or []) if isinstance(worker, Mapping)]),
        },
    )
    return payload.model_dump(mode="json")


__all__ = [
    "ConfigInput",
    "build_managed_work_monitor",
    "build_dispatch_job",
    "build_id",
    "build_managed_work_metadata",
    "build_team_worker_hire_state",
    "build_raw_payload_row",
    "build_result_row",
    "build_worker_history_entry",
    "build_worker_registration",
    "coerce_job_detail",
    "coerce_job_result",
    "coerce_json_object",
    "coerce_json_payload",
    "coerce_record_list",
    "job_is_ready",
    "job_matches_capabilities",
    "job_sort_key",
    "managed_schedule_from_row",
    "managed_ticket_from_job_row",
    "normalize_capabilities",
    "normalize_string_list",
    "normalize_target",
    "normalize_teamwork_config",
    "parse_datetime_value",
    "prepare_table_records",
    "read_teamwork_config",
    "utcnow_iso",
]
