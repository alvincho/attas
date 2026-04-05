"""
Castr work pulser implementation for the Pulsers area.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, this module provides a teamwork worker that
advertises Castr-backed job capabilities and executes Castr output for managers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping

from phemacast.agents.pulser import _read_config
from prompits.dispatcher.runtime import normalize_capabilities
from prompits.teamwork.agents import TeamWorkerAgent


DEFAULT_CASTR_WORK_TYPE = "phemacast.pulsers.castr_work_pulser.CastrWorkPulser"
DEFAULT_MAP_JOB_CAPABILITY = {
    "name": "run map",
    "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
    "description": "Execute a Map Phema through MapCastr and persist the artifact output.",
    "castr_config_path": "phemacast/configs/map.castr",
    "target_table": "dispatcher_map_runs",
}


def _mapping_copy(value: Any) -> dict[str, Any]:
    """Return a shallow mapping copy when the value is a mapping."""
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _normalize_job_capability_entries(entries: Any) -> list[dict[str, Any]]:
    """Normalize configured job-capability entries."""
    if isinstance(entries, Mapping):
        return [dict(entries)]
    return [dict(entry) for entry in list(entries or []) if isinstance(entry, Mapping)]


def _runtime_job_capability_entries(entries: Any) -> list[dict[str, Any]]:
    """Strip presentation-only fields before building runtime job caps."""
    sanitized: list[dict[str, Any]] = []
    for entry in _normalize_job_capability_entries(entries):
        sanitized.append(
            {
                key: value
                for key, value in entry.items()
                if key not in {"description", "default_priority", "payload_template"}
            }
        )
    return sanitized


class CastrWorkPulser(TeamWorkerAgent):
    """
    Teamwork worker with Castr-backed job capabilities.

    Despite the pulser name, this class behaves like a teamwork worker so managers can
    hire it through the normal manager-mediated flow.
    """

    def __init__(
        self,
        config: Any = None,
        *,
        config_path: Any = None,
        name: str = "CastrWorkPulser",
        host: str = "127.0.0.1",
        port: int = 8281,
        plaza_url: str | None = None,
        agent_card: Dict[str, Any] | None = None,
        pool: Any = None,
        manager_address: str = "",
        manager_party: str = "",
        capabilities: Any = None,
        job_capabilities: Any = None,
        poll_interval_sec: float | int | None = None,
        hire_required: bool | None = None,
        auto_register: bool | None = None,
        castr_profile: str = "map",
    ):
        """Initialize the Castr work pulser."""
        if isinstance(config, Mapping):
            config_data = dict(config or {})
        elif isinstance(config, (str, Path)):
            config_data = _read_config(config)
        else:
            config_data = {}

        worker_settings = _mapping_copy(config_data.get("worker"))
        castr_settings = _mapping_copy(config_data.get("castr_work"))
        resolved_profile = str(castr_settings.get("profile") or castr_profile or "map").strip().lower() or "map"
        if resolved_profile != "map":
            raise ValueError(f"Unsupported CastrWorkPulser profile '{resolved_profile}'.")

        resolved_job_capabilities = (
            job_capabilities
            or worker_settings.get("job_capabilities")
            or config_data.get("job_capabilities")
            or [self._default_map_job_capability(castr_settings)]
        )
        runtime_job_capabilities = _runtime_job_capability_entries(resolved_job_capabilities)
        resolved_capabilities = normalize_capabilities(
            capabilities
            or worker_settings.get("capabilities")
            or config_data.get("capabilities")
            or [entry.get("name") for entry in runtime_job_capabilities if entry.get("name")]
        )
        resolved_poll_interval = (
            poll_interval_sec
            if poll_interval_sec is not None
            else worker_settings.get("poll_interval_sec")
            if worker_settings.get("poll_interval_sec") is not None
            else castr_settings.get("poll_interval_sec")
        )
        resolved_hire_required = (
            hire_required
            if hire_required is not None
            else worker_settings.get("hire_required")
        )
        if resolved_hire_required is None:
            resolved_hire_required = True

        card = dict(agent_card or config_data.get("agent_card") or {})
        card.setdefault("name", str(config_data.get("name") or name))
        card["role"] = "worker"
        card["description"] = str(
            config_data.get("description")
            or card.get("description")
            or "Phemacast teamwork worker that advertises Castr-backed job capabilities on Plaza and waits for manager hire."
        )
        existing_tags = list(card.get("tags") or config_data.get("tags") or [])
        for tag in ("phemacast", "teamwork", "worker", "castr", resolved_profile):
            if tag not in existing_tags:
                existing_tags.append(tag)
        card["tags"] = existing_tags

        super().__init__(
            name=str(config_data.get("name") or name),
            host=str(config_data.get("host") or host),
            port=int(config_data.get("port") or port),
            plaza_url=str(config_data.get("plaza_url") or plaza_url or "").strip() or None,
            agent_card=card,
            pool=pool,
            manager_address=manager_address,
            manager_party=manager_party,
            capabilities=resolved_capabilities,
            job_capabilities=runtime_job_capabilities,
            poll_interval_sec=resolved_poll_interval,
            hire_required=bool(resolved_hire_required),
            config=config_data if config_data else config,
            config_path=None,
            auto_register=auto_register,
        )

        meta = dict(self.agent_card.get("meta") or {})
        meta["castr_profile"] = resolved_profile
        meta["job_capabilities"] = list(meta.get("job_capabilities") or [])
        self.agent_card["meta"] = meta
        self.agent_card["capabilities"] = list(self.capabilities)
        self.agent_card["job_capabilities"] = list(meta.get("job_capabilities") or [])

    @staticmethod
    def _default_map_job_capability(settings: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Build the default MapCastr job-capability entry."""
        normalized = dict(DEFAULT_MAP_JOB_CAPABILITY)
        castr_settings = dict(settings or {})
        if str(castr_settings.get("job_capability_name") or "").strip():
            normalized["name"] = str(castr_settings.get("job_capability_name") or "").strip().lower()
        if str(castr_settings.get("castr_config_path") or "").strip():
            normalized["castr_config_path"] = str(castr_settings.get("castr_config_path") or "").strip()
        if isinstance(castr_settings.get("castr_config"), Mapping):
            normalized["castr_config"] = dict(castr_settings.get("castr_config") or {})
            normalized.pop("castr_config_path", None)
        if str(castr_settings.get("target_table") or "").strip():
            normalized["target_table"] = str(castr_settings.get("target_table") or "").strip()
        if castr_settings.get("timeout_sec") is not None:
            normalized["timeout_sec"] = castr_settings.get("timeout_sec")
        if str(castr_settings.get("description") or "").strip():
            normalized["description"] = str(castr_settings.get("description") or "").strip()
        return normalized


__all__ = ["CastrWorkPulser"]
