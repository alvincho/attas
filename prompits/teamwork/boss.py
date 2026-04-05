"""
Coordinator and boss-agent logic for `prompits.teamwork.boss`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the teamwork package models
cooperative agent workflows and their supporting runtime pieces.

Experimental notice: the teamwork boss layer is still under active development. UI
routes, manager aliases, and managed-work orchestration details may change while this
surface is being stabilized.

Core types exposed here include `TeamBossAgent`, which acts as the teamwork control
plane for manager-mediated managed work.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from prompits.dispatcher.boss import BossScheduleControlRequest, DispatcherBossAgent
from prompits.teamwork.models import ManagedScheduleRequest, ManagedTicketRequest
from prompits.teamwork.runtime import (
    build_id,
    build_managed_work_monitor,
    build_managed_work_metadata,
    coerce_json_object,
    managed_schedule_from_row,
    managed_ticket_from_job_row,
    normalize_string_list,
    normalize_teamwork_config,
    utcnow_iso,
)


MANAGER_ALIAS_PRACTICES = {
    "dispatcher-submit-job": "manager-submit-job",
    "dispatcher-get-job": "manager-get-job",
    "dispatcher-post-job-result": "manager-post-job-result",
    "dispatcher-control-job": "manager-control-job",
    "dispatcher-db-list-tables": "manager-db-list-tables",
    "dispatcher-db-preview-table": "manager-db-preview-table",
    "dispatcher-db-query": "manager-db-query",
    "dispatcher-report-job": "manager-report-job",
}


class TeamBossAgent(DispatcherBossAgent):
    """Experimental agent implementation for team boss workflows."""

    def __init__(
        self,
        name: str = "TeamBoss",
        host: str = "127.0.0.1",
        port: int = 8065,
        plaza_url: str | None = None,
        agent_card: Dict[str, Any] | None = None,
        pool: Any = None,
        config: Any = None,
        config_path: Any = None,
        manager_address: str = "",
        manager_party: str = "",
        auto_register: bool | None = None,
    ):
        """Initialize the team boss agent."""
        normalized_config = normalize_teamwork_config(config_path or config, role="boss")
        card = dict(agent_card or normalized_config.get("agent_card") or {})
        card.setdefault("name", str(normalized_config.get("name") or name))
        card["role"] = str(normalized_config.get("role") or card.get("role") or "boss")
        card["description"] = str(
            normalized_config.get("description")
            or card.get("description")
            or "Teamwork boss UI for issuing and monitoring manager jobs."
        )

        super().__init__(
            name=str(normalized_config.get("name") or name),
            host=host,
            port=port,
            plaza_url=plaza_url,
            agent_card=card,
            pool=pool,
            config=normalized_config,
            config_path=None,
            dispatcher_address=str(manager_address or normalized_config.get("dispatcher_address") or "").strip(),
            dispatcher_party=str(
                manager_party or normalized_config.get("dispatcher_party") or normalized_config.get("party") or ""
            ).strip(),
            auto_register=auto_register,
        )

        self.manager_address = self.dispatcher_address
        self.manager_party = self.dispatcher_party

    def _translate_dispatcher_practice(self, practice_id: str) -> str:
        """Translate dispatcher practice ids into manager aliases when available."""
        return MANAGER_ALIAS_PRACTICES.get(str(practice_id or "").strip(), str(practice_id or "").strip())

    def _call_dispatcher(self, practice_id: str, payload: Any, *, dispatcher_address: str = "") -> Any:
        """Call the manager using teamwork aliases with dispatcher fallback."""
        resolved = self._resolve_dispatcher_address(dispatcher_address)
        translated = self._translate_dispatcher_practice(practice_id)
        try:
            return self.UsePractice(translated, payload, pit_address=resolved)
        except Exception:
            if translated != practice_id:
                return self.UsePractice(practice_id, payload, pit_address=resolved)
            raise

    def _manager_identity(
        self,
        *,
        manager_address: str = "",
        manager_name: str = "",
        manager_party: str = "",
    ) -> dict[str, str]:
        """Return the resolved manager identity used in managed-work payloads."""
        resolved_address = self._resolve_dispatcher_address(manager_address)
        return {
            "manager_address": resolved_address,
            "manager_name": str(manager_name or "").strip() or "Manager",
            "manager_party": str(
                manager_party
                or self.manager_party
                or self.dispatcher_party
                or self.agent_card.get("party")
                or ""
            ).strip(),
        }

    @staticmethod
    def _normalized_ticket_targets(request: ManagedTicketRequest) -> list[str]:
        """Return normalized ticket targets."""
        targets = normalize_string_list(request.targets)
        if not targets:
            targets = normalize_string_list(request.symbols)
        return targets

    def _ticket_submission_payload(
        self,
        request: ManagedTicketRequest,
        *,
        manager_identity: Mapping[str, str],
        ticket_id: str,
        work_id: str,
    ) -> dict[str, Any]:
        """Build the manager-submit payload for one managed ticket."""
        metadata = build_managed_work_metadata(
            request.metadata,
            work_id=work_id,
            ticket_id=ticket_id,
            source=str(request.source or "manual"),
            manager_address=str(manager_identity.get("manager_address") or ""),
            manager_name=str(manager_identity.get("manager_name") or ""),
            manager_party=str(manager_identity.get("manager_party") or ""),
            workflow_id=str(request.workflow_id or ""),
            title=str(request.title or request.required_capability or ticket_id).strip(),
        )
        return {
            "required_capability": str(request.required_capability or "").strip(),
            "targets": self._normalized_ticket_targets(request),
            "payload": request.payload,
            "target_table": str(request.target_table or "").strip(),
            "source_url": str(request.source_url or "").strip(),
            "parse_rules": request.parse_rules,
            "capability_tags": normalize_string_list(request.capability_tags),
            "job_type": str(request.job_type or "run").strip() or "run",
            "priority": int(request.priority),
            "premium": bool(request.premium),
            "metadata": metadata,
            "scheduled_for": str(request.scheduled_for or "").strip(),
            "max_attempts": max(int(request.max_attempts), 1),
            "job_id": ticket_id,
        }

    def _normalize_ticket_job_payload(self, payload: Mapping[str, Any], result: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Normalize one manager submission response into a job row."""
        response_job = result.get("job") if isinstance(result, Mapping) and isinstance(result.get("job"), Mapping) else {}
        normalized = {
            "id": str(response_job.get("id") or payload.get("job_id") or "").strip(),
            "required_capability": str(
                response_job.get("required_capability") or payload.get("required_capability") or ""
            ).strip(),
            "targets": list(response_job.get("targets") or payload.get("targets") or []),
            "payload": response_job.get("payload") if "payload" in response_job else payload.get("payload"),
            "target_table": str(response_job.get("target_table") or payload.get("target_table") or "").strip(),
            "source_url": str(response_job.get("source_url") or payload.get("source_url") or "").strip(),
            "parse_rules": response_job.get("parse_rules") if "parse_rules" in response_job else payload.get("parse_rules"),
            "capability_tags": list(response_job.get("capability_tags") or payload.get("capability_tags") or []),
            "job_type": str(response_job.get("job_type") or payload.get("job_type") or "run").strip() or "run",
            "priority": int(response_job.get("priority") or payload.get("priority") or 100),
            "premium": bool(response_job.get("premium") or payload.get("premium")),
            "metadata": response_job.get("metadata") if "metadata" in response_job else payload.get("metadata"),
            "scheduled_for": str(response_job.get("scheduled_for") or payload.get("scheduled_for") or "").strip(),
            "status": str(response_job.get("status") or "queued").strip().lower() or "queued",
            "claimed_by": str(response_job.get("claimed_by") or "").strip(),
            "claimed_at": str(response_job.get("claimed_at") or "").strip(),
            "completed_at": str(response_job.get("completed_at") or "").strip(),
            "result_summary": response_job.get("result_summary") if "result_summary" in response_job else {},
            "error": str(response_job.get("error") or "").strip(),
            "attempts": int(response_job.get("attempts") or 0),
            "max_attempts": int(response_job.get("max_attempts") or payload.get("max_attempts") or 1),
            "created_at": str(response_job.get("created_at") or utcnow_iso()).strip(),
            "updated_at": str(response_job.get("updated_at") or response_job.get("created_at") or utcnow_iso()).strip(),
        }
        return self._normalize_job_row(normalized)

    def create_managed_ticket(self, request: ManagedTicketRequest | Mapping[str, Any]) -> Dict[str, Any]:
        """Create one manager-mediated managed ticket."""
        normalized_request = (
            request if isinstance(request, ManagedTicketRequest) else ManagedTicketRequest.model_validate(dict(request or {}))
        )
        manager_identity = self._manager_identity(
            manager_address=str(normalized_request.manager_address or ""),
            manager_name=str(normalized_request.manager_name or ""),
            manager_party=str(normalized_request.manager_party or ""),
        )
        ticket_id = str(normalized_request.ticket_id or build_id("managed-ticket")).strip()
        work_id = str(normalized_request.work_id or ticket_id).strip()
        payload = self._ticket_submission_payload(
            normalized_request,
            manager_identity=manager_identity,
            ticket_id=ticket_id,
            work_id=work_id,
        )
        result = self._call_dispatcher(
            "dispatcher-submit-job",
            payload,
            dispatcher_address=manager_identity["manager_address"],
        )
        job = self._normalize_ticket_job_payload(payload, result if isinstance(result, Mapping) else None)
        return {
            "status": "success",
            "manager_address": manager_identity["manager_address"],
            "ticket": managed_ticket_from_job_row(
                job,
                manager_address=manager_identity["manager_address"],
                manager_name=manager_identity["manager_name"],
                manager_party=manager_identity["manager_party"],
            ),
        }

    def create_managed_schedule(self, request: ManagedScheduleRequest | Mapping[str, Any]) -> Dict[str, Any]:
        """Persist one saved managed-work schedule for manager-mediated automation."""
        normalized_request = (
            request if isinstance(request, ManagedScheduleRequest) else ManagedScheduleRequest.model_validate(dict(request or {}))
        )
        manager_identity = self._manager_identity(
            manager_address=str(normalized_request.manager_address or ""),
            manager_name=str(normalized_request.manager_name or ""),
            manager_party=str(normalized_request.manager_party or ""),
        )
        repeat_frequency = self._normalize_repeat_frequency(normalized_request.repeat_frequency)
        schedule_timezone = self._normalize_schedule_timezone(normalized_request.schedule_timezone)
        schedule_times = self._normalize_schedule_times(
            normalized_request.schedule_times or normalized_request.schedule_time
        )
        schedule_weekdays = self._normalize_schedule_weekdays(normalized_request.schedule_weekdays)
        schedule_days_of_month = self._normalize_schedule_days_of_month(
            normalized_request.schedule_days_of_month or normalized_request.schedule_day_of_month
        )
        if repeat_frequency == "once":
            scheduled_for = self._normalize_schedule_timestamp(normalized_request.scheduled_for)
            schedule_times = []
            schedule_weekdays = []
            schedule_days_of_month = []
        else:
            if not schedule_times:
                raise ValueError("schedule_times is required for repeating schedules.")
            scheduled_for = self._compute_next_occurrence(
                repeat_frequency=repeat_frequency,
                timezone_name=schedule_timezone,
                schedule_times=schedule_times,
                weekdays=schedule_weekdays,
                days_of_month=schedule_days_of_month,
            )

        schedule_id = str(normalized_request.work_id or build_id("managed-schedule")).strip()
        now = utcnow_iso()
        metadata = build_managed_work_metadata(
            normalized_request.metadata,
            work_id=schedule_id,
            source="schedule",
            manager_address=manager_identity["manager_address"],
            manager_name=manager_identity["manager_name"],
            manager_party=manager_identity["manager_party"],
            schedule_id=schedule_id,
            workflow_id=str(normalized_request.workflow_id or ""),
            title=str(
                normalized_request.title
                or normalized_request.name
                or normalized_request.required_capability
                or schedule_id
            ).strip(),
            assigned_at=now,
        )
        record = {
            "id": schedule_id,
            "name": self._build_schedule_name(
                normalized_request.name or normalized_request.title,
                str(normalized_request.required_capability or ""),
                self._normalized_ticket_targets(normalized_request),
            ),
            "status": "scheduled",
            "dispatcher_address": manager_identity["manager_address"],
            "repeat_frequency": repeat_frequency,
            "schedule_timezone": schedule_timezone,
            "schedule_time": schedule_times[0] if schedule_times else "",
            "schedule_times": schedule_times,
            "schedule_weekdays": schedule_weekdays,
            "schedule_day_of_month": schedule_days_of_month[0] if schedule_days_of_month else None,
            "schedule_days_of_month": schedule_days_of_month,
            "required_capability": str(normalized_request.required_capability or "").strip(),
            "targets": self._normalized_ticket_targets(normalized_request),
            "payload": normalized_request.payload,
            "target_table": str(normalized_request.target_table or "").strip(),
            "source_url": str(normalized_request.source_url or "").strip(),
            "parse_rules": normalized_request.parse_rules,
            "capability_tags": normalize_string_list(normalized_request.capability_tags),
            "job_type": str(normalized_request.job_type or "run").strip() or "run",
            "priority": int(normalized_request.priority),
            "premium": bool(normalized_request.premium),
            "metadata": metadata,
            "scheduled_for": scheduled_for,
            "max_attempts": max(int(normalized_request.max_attempts), 1),
            "dispatcher_job_id": "",
            "issued_at": "",
            "last_attempted_at": "",
            "last_error": "",
            "issue_attempts": 0,
            "created_at": now,
            "updated_at": now,
        }
        saved = self._save_schedule_row(record)
        return {
            "status": "success",
            "schedule": managed_schedule_from_row(
                saved,
                manager_address=manager_identity["manager_address"],
                manager_name=manager_identity["manager_name"],
                manager_party=manager_identity["manager_party"],
            ),
        }

    def _schedule_submission_payload(self, row: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        """Build one manager-mediated payload for scheduled ticket issuance."""
        normalized = self._normalize_schedule_row(row)
        metadata = coerce_json_object(normalized.get("metadata"))
        managed = coerce_json_object(metadata.get("managed_work"))
        manager_assignment = coerce_json_object(managed.get("manager_assignment"))
        manager_identity = self._manager_identity(
            manager_address=str(normalized.get("dispatcher_address") or ""),
            manager_name=str(manager_assignment.get("manager_name") or ""),
            manager_party=str(manager_assignment.get("manager_party") or ""),
        )
        ticket_id = build_id("managed-ticket")
        schedule_id = str(normalized.get("id") or "").strip()
        updated_metadata = build_managed_work_metadata(
            metadata,
            work_id=str(managed.get("work_id") or schedule_id or ticket_id).strip(),
            ticket_id=ticket_id,
            source="schedule",
            manager_address=manager_identity["manager_address"],
            manager_name=manager_identity["manager_name"],
            manager_party=manager_identity["manager_party"],
            schedule_id=schedule_id,
            workflow_id=str(managed.get("workflow_id") or "").strip(),
            title=str(
                managed.get("title")
                or normalized.get("name")
                or normalized.get("required_capability")
                or ticket_id
            ).strip(),
        )
        updated_metadata["boss_schedule_id"] = schedule_id
        return manager_identity["manager_address"], {
            "required_capability": str(normalized.get("required_capability") or ""),
            "targets": list(normalized.get("targets") or []),
            "payload": normalized.get("payload"),
            "target_table": str(normalized.get("target_table") or ""),
            "source_url": str(normalized.get("source_url") or ""),
            "parse_rules": normalized.get("parse_rules"),
            "capability_tags": list(normalized.get("capability_tags") or []),
            "job_type": str(normalized.get("job_type") or "run"),
            "priority": int(normalized.get("priority") or 100),
            "premium": bool(normalized.get("premium")),
            "metadata": updated_metadata,
            "scheduled_for": str(normalized.get("scheduled_for") or ""),
            "max_attempts": int(normalized.get("max_attempts") or 3),
            "job_id": ticket_id,
        }

    def list_managed_tickets(
        self,
        *,
        manager_address: str = "",
        status: str = "",
        capability: str = "",
        search: str = "",
        limit: int = 100,
    ) -> Dict[str, Any]:
        """List managed tickets from the selected manager queue."""
        manager_identity = self._manager_identity(manager_address=manager_address)
        jobs_payload = self._list_jobs(
            dispatcher_address=manager_identity["manager_address"],
            status=status,
            capability=capability,
            search=search,
        )
        try:
            normalized_limit = max(1, min(int(limit), 200))
        except (TypeError, ValueError):
            normalized_limit = 100
        tickets = [
            managed_ticket_from_job_row(
                job,
                manager_address=manager_identity["manager_address"],
                manager_name=manager_identity["manager_name"],
                manager_party=manager_identity["manager_party"],
            )
            for job in jobs_payload.get("jobs", []) or []
            if isinstance(job, Mapping)
        ]
        return {
            "status": "success",
            "manager_address": manager_identity["manager_address"],
            "count": len(tickets),
            "tickets": tickets[:normalized_limit],
        }

    def get_managed_ticket(self, ticket_id: str, *, manager_address: str = "") -> Dict[str, Any]:
        """Return one managed ticket detail."""
        manager_identity = self._manager_identity(manager_address=manager_address)
        detail = self._job_detail(
            dispatcher_address=manager_identity["manager_address"],
            job_id=ticket_id,
        )
        return {
            "status": "success",
            "manager_address": manager_identity["manager_address"],
            "ticket": managed_ticket_from_job_row(
                detail.get("job"),
                manager_address=manager_identity["manager_address"],
                manager_name=manager_identity["manager_name"],
                manager_party=manager_identity["manager_party"],
            ),
            "raw_records": detail.get("raw_records", []),
            "latest_heartbeat": detail.get("latest_heartbeat", {}),
        }

    def list_managed_schedules(self, *, status: str = "", search: str = "", limit: int = 100) -> Dict[str, Any]:
        """List saved managed-work schedules."""
        result = self.list_schedules(status=status, search=search, limit=limit)
        schedules = [
            managed_schedule_from_row(
                row,
                manager_address=str(row.get("dispatcher_address") or ""),
            )
            for row in result.get("schedules", []) or []
            if isinstance(row, Mapping)
        ]
        return {
            "status": "success",
            "count": len(schedules),
            "schedules": schedules,
        }

    def get_managed_schedule_history(self, schedule_id: str, *, limit: int = 20) -> Dict[str, Any]:
        """Return managed ticket history for one saved schedule."""
        history = self.get_schedule_history_via_dispatcher(schedule_id, limit=limit)
        schedule_row = history.get("schedule") if isinstance(history.get("schedule"), Mapping) else {}
        manager_address = str(schedule_row.get("dispatcher_address") or "").strip()
        manager_identity = self._manager_identity(manager_address=manager_address)
        return {
            "status": "success",
            "schedule": managed_schedule_from_row(
                schedule_row,
                manager_address=manager_identity["manager_address"],
                manager_name=manager_identity["manager_name"],
                manager_party=manager_identity["manager_party"],
            ),
            "tickets": [
                managed_ticket_from_job_row(
                    row,
                    manager_address=manager_identity["manager_address"],
                    manager_name=manager_identity["manager_name"],
                    manager_party=manager_identity["manager_party"],
                )
                for row in history.get("jobs", []) or []
                if isinstance(row, Mapping)
            ],
            "count": int(history.get("count") or 0),
            "limit": int(history.get("limit") or limit),
        }

    def managed_monitor_summary(self, *, manager_address: str = "", schedule_limit: int = 20) -> Dict[str, Any]:
        """Return the manager-mediated monitor payload for UI consumers."""
        manager_identity = self._manager_identity(manager_address=manager_address)
        summary = self._monitor_summary(dispatcher_address=manager_identity["manager_address"])
        tickets = self.list_managed_tickets(manager_address=manager_identity["manager_address"], limit=20)
        schedules = self.list_managed_schedules(limit=schedule_limit)
        managed_work = build_managed_work_monitor(
            manager_assignment=manager_identity,
            summary=summary,
            workers=summary.get("workers", []),
            tickets=tickets.get("tickets", []),
            schedules=schedules.get("schedules", []),
            captured_at=str(summary.get("captured_at") or ""),
        )
        return {
            "status": "success",
            "api_version": managed_work.get("api_version"),
            "manager_assignment": manager_identity,
            "manager": manager_identity,
            "summary": summary.get("dispatcher", {}),
            "workers": managed_work.get("workers", []),
            "tickets": managed_work.get("tickets", []),
            "schedules": managed_work.get("schedules", []),
            "counts": managed_work.get("counts", {}),
            "captured_at": managed_work.get("captured_at", ""),
            "managed_work": managed_work,
        }

    def _setup_routes(self) -> None:
        """Set up the inherited dispatcher routes plus managed-work routes."""
        super()._setup_routes()

        @self.app.get("/api/managed-work/monitor")
        async def teamwork_managed_monitor(manager_address: str = "", schedule_limit: int = 20):
            """Route handler for GET /api/managed-work/monitor."""
            try:
                return await run_in_threadpool(
                    self.managed_monitor_summary,
                    manager_address=manager_address,
                    schedule_limit=schedule_limit,
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/managed-work/tickets")
        async def teamwork_managed_tickets(
            manager_address: str = "",
            status: str = "",
            capability: str = "",
            search: str = "",
            limit: int = 100,
        ):
            """Route handler for GET /api/managed-work/tickets."""
            try:
                return await run_in_threadpool(
                    self.list_managed_tickets,
                    manager_address=manager_address,
                    status=status,
                    capability=capability,
                    search=search,
                    limit=limit,
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/managed-work/tickets")
        async def teamwork_create_managed_ticket(payload: ManagedTicketRequest):
            """Route handler for POST /api/managed-work/tickets."""
            try:
                return await run_in_threadpool(self.create_managed_ticket, payload)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/managed-work/tickets/{ticket_id}")
        async def teamwork_managed_ticket_detail(ticket_id: str, manager_address: str = ""):
            """Route handler for GET /api/managed-work/tickets/{ticket_id}."""
            try:
                return await run_in_threadpool(
                    self.get_managed_ticket,
                    ticket_id,
                    manager_address=manager_address,
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/managed-work/schedules")
        async def teamwork_managed_schedules(status: str = "", search: str = "", limit: int = 100):
            """Route handler for GET /api/managed-work/schedules."""
            try:
                return await run_in_threadpool(
                    self.list_managed_schedules,
                    status=status,
                    search=search,
                    limit=limit,
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/managed-work/schedules")
        async def teamwork_create_managed_schedule(payload: ManagedScheduleRequest):
            """Route handler for POST /api/managed-work/schedules."""
            try:
                return await run_in_threadpool(self.create_managed_schedule, payload)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/managed-work/schedules/{schedule_id}/history")
        async def teamwork_managed_schedule_history(schedule_id: str, limit: int = 20):
            """Route handler for GET /api/managed-work/schedules/{schedule_id}/history."""
            try:
                return await run_in_threadpool(
                    self.get_managed_schedule_history,
                    schedule_id,
                    limit=limit,
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/managed-work/schedules/{schedule_id}/control")
        async def teamwork_managed_schedule_control(schedule_id: str, payload: BossScheduleControlRequest):
            """Route handler for POST /api/managed-work/schedules/{schedule_id}/control."""
            normalized_action = str(payload.action or "").strip().lower()
            try:
                if normalized_action == "issue":
                    result = await run_in_threadpool(self.issue_scheduled_job, schedule_id, force_now=True)
                elif normalized_action == "delete":
                    result = await run_in_threadpool(self.delete_schedule, schedule_id)
                else:
                    raise HTTPException(status_code=400, detail="action must be one of: issue, delete.")
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {"status": "success", "control": result}


__all__ = ["TeamBossAgent"]
