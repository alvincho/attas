"""
Agent implementations for `prompits.teamwork.agents`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the teamwork package models
cooperative agent workflows and their supporting runtime pieces.

Experimental notice: the teamwork agents in this module are still under active
development, so advertised behaviors and configuration affordances may continue to
shift.

Core types exposed here include `DispatcherManagerAgent`, `TeamManagerAgent`, and
`TeamWorkerAgent`, which carry the main behavior or state managed by this module.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Mapping

from prompits.dispatcher.agents import (
    DISPATCHER_PARTY,
    DispatcherAgent,
    DispatcherWorkerAgent,
    _merge_tags,
)
from prompits.dispatcher.models import JobDetail, JobResult
from prompits.dispatcher.runtime import (
    build_id,
    coerce_job_detail,
    coerce_job_result,
    coerce_json_object,
    coerce_json_payload,
    coerce_record_list,
    normalize_capabilities,
    normalize_string_list,
    utcnow_iso,
)
from prompits.teamwork.practices import (
    ControlManagerJobPractice,
    GetManagerJobPractice,
    HireWorkerManagerPractice,
    ListManagerDbTablesPractice,
    PostManagerJobResultPractice,
    PreviewManagerDbTablePractice,
    QueryManagerDbPractice,
    RegisterManagerWorkerPractice,
    ReportManagerJobPractice,
    SubmitManagerJobPractice,
)
from prompits.teamwork.runtime import build_team_worker_hire_state, normalize_teamwork_config


class _ManagerDiscoveryMixin:
    """Mixin for manager discovery mixin behavior."""
    MANAGER_DISCOVERY_PRACTICES = (
        "manager-get-job",
        "manager-register-worker",
        "manager-post-job-result",
    )

    def _log_manager_discovery_message(
        self,
        message: str,
        *,
        level: str = "info",
        min_interval_sec: float = 30.0,
    ) -> None:
        """Internal helper to log the manager discovery message."""
        normalized = str(message or "").strip()
        if not normalized:
            return
        now = time.time()
        previous_message = str(getattr(self, "_manager_discovery_log_message", "") or "")
        previous_at = float(getattr(self, "_manager_discovery_log_at", 0.0) or 0.0)
        if normalized == previous_message and (now - previous_at) < max(float(min_interval_sec), 0.0):
            return
        getattr(self.logger, level, self.logger.info)(normalized)
        self._manager_discovery_log_message = normalized
        self._manager_discovery_log_at = now

    @staticmethod
    def _extract_manager_address(entry: Any) -> str:
        """Internal helper to extract the manager address."""
        if not isinstance(entry, Mapping):
            return ""
        card = entry.get("card") if isinstance(entry.get("card"), Mapping) else {}
        for candidate in (entry.get("address"), card.get("address"), entry.get("pit_address")):
            normalized = str(candidate or "").strip().rstrip("/")
            if normalized:
                return normalized
        return ""

    @classmethod
    def _manager_candidate_sort_key(cls, entry: Any) -> tuple[int, int, int, int, float]:
        """Internal helper to return the manager candidate sort key."""
        if not isinstance(entry, Mapping):
            return (0, 0, 0, 0, 0.0)
        card = entry.get("card") if isinstance(entry.get("card"), Mapping) else {}
        tags = {tag.lower() for tag in normalize_string_list(card.get("tags"))}
        practices = card.get("practices") if isinstance(card.get("practices"), list) else []
        practice_ids = {
            str(practice.get("id") or "").strip().lower()
            for practice in practices
            if isinstance(practice, Mapping)
        }
        role = str(card.get("role") or entry.get("role") or "").strip().lower()
        name = str(entry.get("name") or card.get("name") or "").strip().lower()
        last_active = entry.get("last_active")
        try:
            normalized_last_active = float(last_active or 0.0)
        except (TypeError, ValueError):
            normalized_last_active = 0.0
        return (
            1 if role in {"manager", "dispatcher"} else 0,
            sum(1 for practice_id in cls.MANAGER_DISCOVERY_PRACTICES if practice_id in practice_ids),
            1 if "manager" in tags or "dispatcher" in tags else 0,
            1 if name in {"manager", "dispatcher"} else 0,
            normalized_last_active,
        )

    def _remember_manager_address(self, address: Any, *, source: str = "") -> str:
        """Internal helper to remember the manager address."""
        normalized = str(address or "").strip().rstrip("/")
        if not normalized:
            return ""
        previous = str(getattr(self, "manager_address", "") or "").strip().rstrip("/")
        self.manager_address = normalized
        if hasattr(self, "dispatcher_address"):
            self.dispatcher_address = normalized
        meta = dict(self.agent_card.get("meta") or {})
        meta["manager_address"] = normalized
        if hasattr(self, "dispatcher_address"):
            meta["dispatcher_address"] = normalized
        self.agent_card["meta"] = meta
        if normalized != previous:
            suffix = f" via {source}" if str(source or "").strip() else ""
            self.logger.info("Resolved manager at %s%s.", normalized, suffix)
        return normalized

    def _discover_manager_address(self, *, force: bool = False) -> str:
        """Internal helper to discover the manager address."""
        current = str(getattr(self, "manager_address", "") or "").strip()
        if current and not force:
            return current
        if not getattr(self, "plaza_url", ""):
            return ""
        party = str(
            getattr(self, "manager_party", "")
            or self.agent_card.get("party")
            or DISPATCHER_PARTY
        ).strip() or DISPATCHER_PARTY

        search_plans = (
            {"role": "manager", "practice": "manager-get-job", "pit_type": "Agent", "party": party},
            {"role": "dispatcher", "practice": "dispatcher-get-job", "pit_type": "Agent", "party": party},
            {"role": "manager", "pit_type": "Agent", "party": party},
            {"role": "dispatcher", "pit_type": "Agent", "party": party},
            {"practice": "manager-get-job", "pit_type": "Agent", "party": party},
            {"name": "Manager", "pit_type": "Agent", "party": party},
            {"name": "Dispatcher", "pit_type": "Agent", "party": party},
        )

        candidates: dict[str, Any] = {}
        for search_params in search_plans:
            results = self.search(**search_params) or []
            for entry in results:
                address = self._extract_manager_address(entry)
                if not address:
                    continue
                candidate_key = str(entry.get("agent_id") or address)
                existing = candidates.get(candidate_key)
                if existing is None or self._manager_candidate_sort_key(entry) > self._manager_candidate_sort_key(existing):
                    candidates[candidate_key] = entry

        if candidates:
            selected = max(candidates.values(), key=self._manager_candidate_sort_key)
            return self._remember_manager_address(self._extract_manager_address(selected), source="Plaza search")

        if not getattr(self, "plaza_token", None):
            self._log_manager_discovery_message(
                "Worker is waiting for Plaza registration before manager discovery.",
                level="info",
            )
        else:
            self._log_manager_discovery_message(
                "Worker could not find a manager via Plaza yet.",
                level="warning",
            )
        return ""

    def _resolve_manager_address(self) -> str:
        """Internal helper to resolve the manager address."""
        return self._remember_manager_address(getattr(self, "manager_address", "")) or self._discover_manager_address()


class TeamManagerAgent(_ManagerDiscoveryMixin, DispatcherAgent):
    """Experimental agent implementation for team manager workflows."""
    def __init__(
        self,
        name: str = "Manager",
        host: str = "127.0.0.1",
        port: int = 8060,
        plaza_url: str | None = None,
        agent_card: Dict[str, Any] | None = None,
        pool: Any = None,
        config: Any = None,
        config_path: Any = None,
        manager_type: str = "generic",
        manager_address: str = "",
        manager_party: str = "",
        auto_register: bool | None = None,
    ):
        """Initialize the team manager agent."""
        normalized_config = normalize_teamwork_config(config_path or config, role="manager")
        manager_settings = normalized_config.get("dispatcher") if isinstance(normalized_config.get("dispatcher"), Mapping) else {}
        resolved_auto_register = bool(
            auto_register if auto_register is not None else manager_settings.get("auto_register", False)
        )
        card = dict(agent_card or normalized_config.get("agent_card") or {})
        card.setdefault("name", str(normalized_config.get("name") or name))
        card["role"] = str(normalized_config.get("role") or card.get("role") or "manager")
        card["description"] = str(
            normalized_config.get("description")
            or card.get("description")
            or "Teamwork manager that coordinates queued jobs and workers."
        )
        card["tags"] = _merge_tags(card.get("tags"), normalized_config.get("tags"), ["prompits", "teamwork", "manager"])

        super().__init__(
            name=str(normalized_config.get("name") or name),
            host=host,
            port=port,
            plaza_url=plaza_url,
            agent_card=card,
            pool=pool,
            config=normalized_config,
            config_path=None,
            auto_register=False,
        )

        self.manager_type = str(normalized_config.get("manager_type") or manager_type or "generic").strip() or "generic"
        self.manager_address = str(
            manager_address or normalized_config.get("dispatcher_address") or ""
        ).strip()
        self.manager_party = str(
            manager_party or normalized_config.get("dispatcher_party") or normalized_config.get("party") or self.agent_card.get("party") or DISPATCHER_PARTY
        ).strip() or DISPATCHER_PARTY
        self.manager_worker_id = build_id("manager-worker")
        self._manager_discovery_log_message = ""
        self._manager_discovery_log_at = 0.0

        meta = dict(self.agent_card.get("meta") or {})
        meta["manager_type"] = self.manager_type
        meta["manager_party"] = self.manager_party
        if self.manager_address:
            meta["manager_address"] = self.manager_address
        self.agent_card["meta"] = meta

        self.add_practice(SubmitManagerJobPractice())
        self.add_practice(RegisterManagerWorkerPractice())
        self.add_practice(GetManagerJobPractice())
        self.add_practice(PostManagerJobResultPractice())
        self.add_practice(ControlManagerJobPractice())
        self.add_practice(ListManagerDbTablesPractice())
        self.add_practice(PreviewManagerDbTablePractice())
        self.add_practice(QueryManagerDbPractice())
        self.add_practice(ReportManagerJobPractice())

        if self.plaza_url and resolved_auto_register:
            self.register()

    def _manager_worker_identity(self) -> str:
        """Internal helper to return the manager worker identity."""
        return str(self.manager_worker_id or self.name)

    @staticmethod
    def _extract_worker_address(entry: Any) -> str:
        """Internal helper to extract the worker address."""
        if not isinstance(entry, Mapping):
            return ""
        card = entry.get("card") if isinstance(entry.get("card"), Mapping) else {}
        for candidate in (entry.get("address"), card.get("address"), entry.get("pit_address")):
            normalized = str(candidate or "").strip().rstrip("/")
            if normalized:
                return normalized
        return ""

    @staticmethod
    def _worker_card(entry: Any) -> Mapping[str, Any]:
        """Internal helper to return the worker card mapping."""
        if not isinstance(entry, Mapping):
            return {}
        card = entry.get("card")
        return card if isinstance(card, Mapping) else {}

    @classmethod
    def _worker_supports_capability(cls, entry: Any, capability: str = "") -> bool:
        """Internal helper to determine whether the worker supports a capability."""
        normalized_capability = str(capability or "").strip().lower()
        if not normalized_capability:
            return True
        card = cls._worker_card(entry)
        advertised = normalize_capabilities(card.get("capabilities"))
        if normalized_capability in advertised or "*" in advertised:
            return True
        metadata = card.get("meta") if isinstance(card.get("meta"), Mapping) else {}
        job_capabilities = metadata.get("job_capabilities")
        if isinstance(job_capabilities, list):
            for item in job_capabilities:
                if not isinstance(item, Mapping):
                    continue
                if str(item.get("name") or item.get("capability") or "").strip().lower() == normalized_capability:
                    return True
        return False

    @classmethod
    def _worker_can_be_hired(cls, entry: Any) -> bool:
        """Internal helper to determine whether the worker exposes the hire practice."""
        card = cls._worker_card(entry)
        practices = card.get("practices") if isinstance(card.get("practices"), list) else []
        return any(
            isinstance(practice, Mapping)
            and str(practice.get("id") or "").strip().lower() == "worker-hire-manager"
            for practice in practices
        )

    @classmethod
    def _worker_is_available_for_hire(cls, entry: Any) -> bool:
        """Internal helper to determine whether the worker is waiting for a manager."""
        card = cls._worker_card(entry)
        meta = card.get("meta") if isinstance(card.get("meta"), Mapping) else {}
        assignment = meta.get("manager_assignment") if isinstance(meta.get("manager_assignment"), Mapping) else {}
        if str(assignment.get("manager_address") or "").strip():
            return False
        status = str(assignment.get("status") or "").strip().lower()
        if not status:
            return True
        return status in {"awaiting_hire", "available", "unassigned"}

    @classmethod
    def _worker_candidate_sort_key(cls, entry: Any) -> tuple[int, int, float, str]:
        """Internal helper to sort hireable worker candidates."""
        if not isinstance(entry, Mapping):
            return (0, 0, 0.0, "")
        card = cls._worker_card(entry)
        assignment = (
            card.get("meta", {}).get("manager_assignment", {})
            if isinstance(card.get("meta"), Mapping)
            else {}
        )
        try:
            normalized_last_active = float(entry.get("last_active") or 0.0)
        except (TypeError, ValueError):
            normalized_last_active = 0.0
        return (
            1 if cls._worker_can_be_hired(entry) else 0,
            1 if str(assignment.get("status") or "").strip().lower() == "awaiting_hire" else 0,
            normalized_last_active,
            str(entry.get("name") or card.get("name") or "").strip().lower(),
        )

    def hire_worker(
        self,
        *,
        worker_address: str = "",
        capability: str = "",
        worker_name: str = "",
        party: str = "",
        assignment_source: str = "manager_hire",
    ) -> Dict[str, Any]:
        """Hire an available worker via Plaza-backed discovery or an explicit address."""
        resolved_worker_address = str(worker_address or "").strip().rstrip("/")
        normalized_worker_name = str(worker_name or "").strip().lower()
        normalized_party = str(
            party or self.manager_party or self.agent_card.get("party") or DISPATCHER_PARTY
        ).strip() or DISPATCHER_PARTY

        if not resolved_worker_address:
            search_params = {"pit_type": "Agent", "role": "worker", "party": normalized_party}
            if capability:
                search_params["capability"] = str(capability or "").strip().lower()
            results = self.search(**search_params) or []
            candidates = [
                entry
                for entry in results
                if self._worker_can_be_hired(entry)
                and self._worker_is_available_for_hire(entry)
                and self._worker_supports_capability(entry, capability)
                and (
                    not normalized_worker_name
                    or str(entry.get("name") or self._worker_card(entry).get("name") or "").strip().lower() == normalized_worker_name
                )
            ]
            if candidates:
                selected = max(candidates, key=self._worker_candidate_sort_key)
                resolved_worker_address = self._extract_worker_address(selected)

        if not resolved_worker_address:
            return {
                "status": "pending",
                "worker_address": "",
                "error": "No available teamwork worker matched the requested hire criteria.",
            }

        payload = {
            "manager_address": self.agent_card.get("address") or f"http://{self.host}:{self.port}",
            "manager_name": self.name,
            "manager_party": self.manager_party,
            "assignment_source": str(assignment_source or "manager_hire").strip().lower() or "manager_hire",
        }
        response = self.UsePractice(
            "worker-hire-manager",
            payload,
            pit_address=resolved_worker_address,
        )
        normalized_response = dict(response or {}) if isinstance(response, Mapping) else {}
        normalized_response.setdefault("worker_address", resolved_worker_address)
        return normalized_response

    def submit_job_to_manager(self, payload: Mapping[str, Any], *, manager_address: str = "") -> Dict[str, Any]:
        """Submit the job to manager."""
        resolved_manager_address = self._resolve_manager_address() if not manager_address else self._remember_manager_address(manager_address)
        if not resolved_manager_address:
            raise ValueError("manager_address is required for delegated submission.")
        return self.UsePractice("manager-submit-job", dict(payload or {}), pit_address=resolved_manager_address)

    def register_with_manager(
        self,
        *,
        manager_address: str = "",
        worker_id: str = "",
        capabilities: Any = None,
        metadata: Any = None,
        event_type: str = "register",
    ) -> Dict[str, Any]:
        """Register the with manager."""
        resolved_manager_address = self._resolve_manager_address() if not manager_address else self._remember_manager_address(manager_address)
        if not resolved_manager_address:
            return {"status": "pending", "worker_id": worker_id or self._manager_worker_identity(), "error": "Manager is not available yet."}
        resolved_capabilities = normalize_capabilities(capabilities or [])
        return self.UsePractice(
            "manager-register-worker",
            {
                "worker_id": str(worker_id or self._manager_worker_identity()),
                "name": self.name,
                "address": self.agent_card.get("address") or f"http://{self.host}:{self.port}",
                "capabilities": resolved_capabilities,
                "metadata": coerce_json_object(metadata),
                "plaza_url": self.plaza_url or "",
                "status": "working" if event_type == "job_start" else "online",
                "event_type": event_type,
            },
            pit_address=resolved_manager_address,
        )

    def request_parent_job(
        self,
        *,
        manager_address: str = "",
        worker_id: str = "",
        capabilities: Any = None,
        metadata: Any = None,
    ) -> Dict[str, Any]:
        """Request the parent job."""
        resolved_manager_address = self._resolve_manager_address() if not manager_address else self._remember_manager_address(manager_address)
        if not resolved_manager_address:
            return {"status": "pending", "job": None, "error": "Manager is not available yet."}
        response = self.UsePractice(
            "manager-get-job",
            {
                "worker_id": str(worker_id or self._manager_worker_identity()),
                "name": self.name,
                "address": self.agent_card.get("address") or f"http://{self.host}:{self.port}",
                "capabilities": normalize_capabilities(capabilities or []),
                "metadata": coerce_json_object(metadata),
                "plaza_url": self.plaza_url or "",
            },
            pit_address=resolved_manager_address,
        )
        payload = dict(response or {}) if isinstance(response, Mapping) else {}
        payload["job"] = coerce_job_detail(payload.get("job"))
        return payload

    def post_parent_job_result(
        self,
        job_result: JobResult | Mapping[str, Any],
        *,
        manager_address: str = "",
        worker_id: str = "",
    ) -> Dict[str, Any]:
        """Post the parent job result."""
        resolved_manager_address = self._resolve_manager_address() if not manager_address else self._remember_manager_address(manager_address)
        if not resolved_manager_address:
            raise ValueError("manager_address is required for delegated job reporting.")
        result = coerce_job_result(job_result, worker_id=str(worker_id or self._manager_worker_identity()))
        return self.UsePractice("manager-post-job-result", result.to_payload(), pit_address=resolved_manager_address)

    def _normalize_delegate_result(self, job: JobDetail, result: Any, *, worker_id: str) -> JobResult:
        """Internal helper to normalize the delegate result."""
        if isinstance(result, JobResult):
            return result.with_defaults(job_id=job.id, worker_id=worker_id)
        if isinstance(result, Mapping):
            status_text = str(result.get("status") or "").strip().lower()
            has_job_fields = any(key in result for key in ("collected_rows", "raw_payload", "result_summary", "error", "target_table"))
            if status_text in {"completed", "failed", "retry", "stopped"}:
                return coerce_job_result(result, job_id=job.id, worker_id=worker_id)
            if has_job_fields:
                normalized_result = dict(result)
                normalized_result["status"] = "completed"
                return coerce_job_result(normalized_result, job_id=job.id, worker_id=worker_id)
            return JobResult(
                job_id=job.id,
                worker_id=worker_id,
                status="completed",
                collected_rows=[dict(result)],
                raw_payload=dict(result),
                result_summary={"rows": 1},
            )
        if isinstance(result, list):
            return JobResult(
                job_id=job.id,
                worker_id=worker_id,
                status="completed",
                collected_rows=[dict(item) for item in result if isinstance(item, Mapping)],
                raw_payload=result,
                result_summary={"rows": len(result)},
            )
        if result is None:
            raise ValueError("Delegated manager job handler returned None.")
        return JobResult(
            job_id=job.id,
            worker_id=worker_id,
            status="completed",
            collected_rows=[],
            raw_payload=coerce_json_payload(result),
            result_summary={"value": result},
        )

    def run_delegate_once(
        self,
        handler: Callable[[JobDetail], Any],
        *,
        manager_address: str = "",
        worker_id: str = "",
        capabilities: Any = None,
        metadata: Any = None,
    ) -> Dict[str, Any]:
        """Run the delegate once."""
        delegated_worker_id = str(worker_id or self._manager_worker_identity())
        self.register_with_manager(
            manager_address=manager_address,
            worker_id=delegated_worker_id,
            capabilities=capabilities,
            metadata=metadata,
            event_type="register",
        )
        response = self.request_parent_job(
            manager_address=manager_address,
            worker_id=delegated_worker_id,
            capabilities=capabilities,
            metadata=metadata,
        )
        job = response.get("job") if isinstance(response, Mapping) else None
        if not isinstance(job, JobDetail):
            return {"status": "idle", "job": None}

        self.register_with_manager(
            manager_address=manager_address,
            worker_id=delegated_worker_id,
            capabilities=capabilities,
            metadata={"started_at": utcnow_iso(), **coerce_json_object(metadata)},
            event_type="job_start",
        )
        outcome = handler(job)
        normalized = self._normalize_delegate_result(job, outcome, worker_id=delegated_worker_id)
        report = self.post_parent_job_result(
            normalized,
            manager_address=manager_address,
            worker_id=delegated_worker_id,
        )
        return {"status": normalized.status, "job": job, "job_result": normalized, "report": report}


class DispatcherManagerAgent(TeamManagerAgent):
    """Experimental agent implementation for dispatcher manager workflows."""
    def __init__(self, *args: Any, agent_card: Dict[str, Any] | None = None, manager_type: str = "dispatcher", **kwargs: Any):
        """Initialize the dispatcher manager agent."""
        card = dict(agent_card or {})
        card.setdefault("role", "dispatcher")
        card.setdefault("description", "Dispatcher-style teamwork manager with legacy dispatcher practices enabled.")
        super().__init__(*args, agent_card=card, manager_type=manager_type, **kwargs)


class TeamWorkerAgent(_ManagerDiscoveryMixin, DispatcherWorkerAgent):
    """Experimental agent implementation for team worker workflows."""
    def __init__(
        self,
        name: str = "Worker",
        host: str = "127.0.0.1",
        port: int = 8061,
        plaza_url: str | None = None,
        agent_card: Dict[str, Any] | None = None,
        pool: Any = None,
        manager_address: str = "",
        manager_party: str = "",
        capabilities: Any = None,
        job_capabilities: Any = None,
        poll_interval_sec: float | int | None = None,
        hire_required: bool | None = None,
        config: Any = None,
        config_path: Any = None,
        auto_register: bool | None = None,
    ):
        """Initialize the team worker agent."""
        normalized_config = normalize_teamwork_config(config_path or config, role="worker")
        worker_settings = normalized_config.get("dispatcher") if isinstance(normalized_config.get("dispatcher"), Mapping) else {}
        card = dict(agent_card or normalized_config.get("agent_card") or {})
        card.setdefault("name", str(normalized_config.get("name") or name))
        card["role"] = str(normalized_config.get("role") or card.get("role") or "worker")
        card["description"] = str(
            normalized_config.get("description")
            or card.get("description")
            or "Teamwork worker that discovers a manager and processes matching jobs."
        )
        card["tags"] = _merge_tags(card.get("tags"), normalized_config.get("tags"), ["prompits", "teamwork", "worker"])

        resolved_manager_address = str(
            manager_address or normalized_config.get("dispatcher_address") or ""
        ).strip()
        resolved_auto_register = bool(
            auto_register if auto_register is not None else worker_settings.get("auto_register", False)
        )
        resolved_hire_required = bool(
            hire_required if hire_required is not None else worker_settings.get("hire_required", False)
        )

        super().__init__(
            name=str(normalized_config.get("name") or name),
            host=host,
            port=port,
            plaza_url=plaza_url,
            agent_card=card,
            pool=pool,
            dispatcher_address=resolved_manager_address,
            capabilities=capabilities,
            job_capabilities=job_capabilities,
            poll_interval_sec=poll_interval_sec,
            config=normalized_config,
            config_path=None,
            auto_register=False,
        )

        self.manager_address = resolved_manager_address or str(self.dispatcher_address or "").strip()
        self.manager_name = str(
            worker_settings.get("manager_name")
            or normalized_config.get("manager_name")
            or ""
        ).strip()
        self.manager_party = str(
            manager_party or normalized_config.get("dispatcher_party") or normalized_config.get("party") or self.agent_card.get("party") or DISPATCHER_PARTY
        ).strip() or DISPATCHER_PARTY
        self.hire_required = resolved_hire_required
        self._manager_discovery_log_message = ""
        self._manager_discovery_log_at = 0.0

        self.add_practice(HireWorkerManagerPractice())
        self._sync_manager_assignment(
            manager_address=self.manager_address,
            manager_name=self.manager_name,
            manager_party=self.manager_party,
            assignment_source="config" if self.manager_address else "",
        )

        if self.plaza_url and resolved_auto_register:
            self.register()

    def _sync_manager_assignment(
        self,
        *,
        manager_address: str = "",
        manager_name: str = "",
        manager_party: str = "",
        assignment_source: str = "",
        hired_at: str = "",
        status: str = "",
    ) -> dict[str, Any]:
        """Internal helper to synchronize manager-assignment state onto the agent card."""
        normalized_manager_address = str(manager_address or "").strip().rstrip("/")
        if manager_name:
            self.manager_name = str(manager_name or "").strip()
        if manager_party:
            self.manager_party = str(manager_party or "").strip() or self.manager_party
        self.manager_address = normalized_manager_address
        self.dispatcher_address = normalized_manager_address
        self.worker_environment = self._build_worker_environment_snapshot()

        meta = dict(self.agent_card.get("meta") or {})
        meta["manager_party"] = self.manager_party
        if self.manager_name:
            meta["manager_name"] = self.manager_name
        else:
            meta.pop("manager_name", None)
        assignment = build_team_worker_hire_state(
            meta.get("manager_assignment"),
            hire_required=self.hire_required,
            manager_address=self.manager_address,
            manager_name=self.manager_name,
            manager_party=self.manager_party,
            assignment_source=assignment_source,
            hired_at=hired_at,
            status=status,
        )
        meta["manager_assignment"] = assignment
        if self.manager_address:
            meta["manager_address"] = self.manager_address
            meta["dispatcher_address"] = self.manager_address
        else:
            meta.pop("manager_address", None)
            meta.pop("dispatcher_address", None)
        self.agent_card["meta"] = meta
        return assignment

    def _worker_hire_state(self) -> dict[str, Any]:
        """Return the current worker hire-state payload."""
        meta = dict(self.agent_card.get("meta") or {})
        return build_team_worker_hire_state(
            meta.get("manager_assignment"),
            hire_required=self.hire_required,
            manager_address=self.manager_address,
            manager_name=self.manager_name,
            manager_party=self.manager_party,
        )

    def _remember_manager_address(self, address: Any, *, source: str = "") -> str:
        """Remember the manager address and keep the worker assignment metadata in sync."""
        normalized = str(address or "").strip().rstrip("/")
        if not normalized:
            self._sync_manager_assignment(
                manager_address="",
                manager_name=self.manager_name,
                manager_party=self.manager_party,
                assignment_source="",
            )
            return ""
        remembered = super()._remember_manager_address(normalized, source=source)
        self._sync_manager_assignment(
            manager_address=remembered,
            manager_name=self.manager_name,
            manager_party=self.manager_party,
            assignment_source=str(source or "manager_assignment").strip().lower().replace(" ", "_"),
        )
        return remembered

    def accept_manager_hire(
        self,
        *,
        manager_address: str,
        manager_name: str = "",
        manager_party: str = "",
        assignment_source: str = "hire",
        hired_at: str = "",
    ) -> Dict[str, Any]:
        """Accept an explicit manager hire assignment from a teamwork manager."""
        normalized_manager_address = str(manager_address or "").strip().rstrip("/")
        if not normalized_manager_address:
            raise ValueError("manager_address is required to hire a teamwork worker.")
        self.manager_name = str(manager_name or self.manager_name or "").strip()
        if manager_party:
            self.manager_party = str(manager_party or "").strip() or self.manager_party
        remembered = super()._remember_manager_address(
            normalized_manager_address,
            source=str(assignment_source or "hire").strip().lower() or "hire",
        )
        assignment = self._sync_manager_assignment(
            manager_address=remembered,
            manager_name=self.manager_name,
            manager_party=self.manager_party,
            assignment_source=assignment_source,
            hired_at=hired_at,
            status="hired",
        )
        if self.plaza_url and getattr(self, "plaza_token", ""):
            try:
                self.register()
            except Exception:
                self.logger.warning("Worker could not refresh Plaza registration after hire.", exc_info=True)
        return {
            "status": "hired",
            "worker_id": self._worker_identity(),
            "worker_address": self.agent_card.get("address") or f"http://{self.host}:{self.port}",
            "manager_assignment": assignment,
            "capabilities": self.advertised_capabilities(),
        }

    def _resolve_dispatcher_address(self) -> str:
        """Internal helper to resolve the dispatcher address."""
        return self._resolve_manager_address()

    def _resolve_manager_address(self) -> str:
        """Internal helper to resolve the manager address."""
        remembered = str(getattr(self, "manager_address", "") or "").strip().rstrip("/")
        if remembered:
            return self._remember_manager_address(remembered)
        if self.hire_required:
            self._log_manager_discovery_message(
                "Worker is advertised on Plaza and waiting for a manager hire assignment.",
                level="info",
            )
            return ""
        return super()._resolve_manager_address()

    def _build_worker_environment_snapshot(self, *, config: Any = None, config_path: Any = None) -> dict[str, Any]:
        """Internal helper to build the worker environment snapshot."""
        environment = super()._build_worker_environment_snapshot(config=config, config_path=config_path)
        environment["manager_address"] = str(getattr(self, "manager_address", "") or "").strip()
        environment["manager_party"] = str(getattr(self, "manager_party", "") or "").strip()
        environment["hire_required"] = bool(getattr(self, "hire_required", False))
        return environment

    def _send_worker_heartbeat(self, *, event_type: str = "heartbeat") -> Dict[str, Any]:
        """Internal helper to send the worker heartbeat."""
        manager_address = self._resolve_manager_address()
        if not manager_address:
            if self.hire_required:
                return {
                    "status": "waiting_for_hire",
                    "worker_id": self._worker_identity(),
                    "error": "Manager has not hired this worker yet.",
                    "manager_assignment": self._worker_hire_state(),
                }
            return {"status": "pending", "worker_id": self._worker_identity(), "error": "Manager is not available yet."}
        return self.UsePractice(
            "manager-register-worker",
            {
                "worker_id": self._worker_identity(),
                "name": self.name,
                "address": self.agent_card.get("address") or f"http://{self.host}:{self.port}",
                "capabilities": self.advertised_capabilities(),
                "metadata": self._worker_metadata(),
                "plaza_url": self.plaza_url or "",
                "status": self._worker_status(),
                "event_type": event_type,
            },
            pit_address=manager_address,
        )

    def request_job(self) -> Dict[str, Any]:
        """Request the job."""
        manager_address = self._resolve_manager_address()
        if not manager_address:
            if self.hire_required:
                return {
                    "status": "waiting_for_hire",
                    "job": None,
                    "error": "Manager has not hired this worker yet.",
                    "manager_assignment": self._worker_hire_state(),
                }
            return {"status": "pending", "job": None, "error": "Manager is not available yet."}
        response = self.UsePractice(
            "manager-get-job",
            {
                "worker_id": self._worker_identity(),
                "name": self.name,
                "address": self.agent_card.get("address") or f"http://{self.host}:{self.port}",
                "capabilities": self.advertised_capabilities(),
                "metadata": self._worker_metadata(),
                "plaza_url": self.plaza_url or "",
            },
            pit_address=manager_address,
        )
        payload = dict(response or {}) if isinstance(response, Mapping) else {}
        payload["job"] = coerce_job_detail(payload.get("job"))
        job = payload.get("job")
        if isinstance(job, JobDetail):
            self.logger.info("Claimed manager job %s for capability '%s'.", job.id, job.required_capability)
        else:
            self.logger.info("No matching manager job available.")
        return payload

    def post_job_result(self, job_result: JobResult | Mapping[str, Any]) -> Dict[str, Any]:
        """Post the job result."""
        manager_address = self._resolve_manager_address()
        if not manager_address:
            raise ValueError("manager_address is required for job reporting.")
        result = coerce_job_result(job_result, worker_id=self._worker_identity())
        return self.UsePractice("manager-post-job-result", result.to_payload(), pit_address=manager_address)

    def submit_job_to_manager(self, payload: Mapping[str, Any]) -> Dict[str, Any]:
        """Submit the job to manager."""
        manager_address = self._resolve_manager_address()
        if not manager_address:
            raise ValueError("manager_address is required for job submission.")
        return self.UsePractice("manager-submit-job", dict(payload or {}), pit_address=manager_address)

    def run_once(self, handler: Callable[[JobDetail], Any] | None = None) -> Dict[str, Any]:
        """Run the worker once, waiting for hire when explicit assignment is required."""
        if self.hire_required and not self._resolve_manager_address():
            self.register_capabilities()
            self._reset_progress(phase="idle", message="Waiting for a manager hire assignment.")
            return {
                "status": "waiting_for_hire",
                "job": None,
                "error": "Manager has not hired this worker yet.",
                "manager_assignment": self._worker_hire_state(),
            }
        return super().run_once(handler=handler)


__all__ = [
    "DispatcherManagerAgent",
    "TeamManagerAgent",
    "TeamWorkerAgent",
]
