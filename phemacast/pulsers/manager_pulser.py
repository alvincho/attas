"""
Manager pulser implementation for the Pulsers area.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, this pulser provides a manager-local
control plane that joins one boss-issued team manifest and prepares local workers.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any, Dict, Mapping

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from phemacast.agents.pulser import _read_config
from phemacast.pulsers.boss_pulser import (
    DEFAULT_TEAMWORK_PARTY,
    BossPulser,
    _coerce_object,
)


def _looks_generic_manager_pulser_name(value: Any) -> bool:
    """Return whether a manager-pulser name is still the generic default."""
    normalized = "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())
    return normalized in {"", "managerpulser"}


def _port_from_address(value: Any) -> int:
    """Extract a port number from one manager address when possible."""
    text = str(value or "").strip().rstrip("/")
    if not text or ":" not in text:
        return 0
    tail = text.rsplit(":", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def _coerce_port(value: Any) -> int:
    """Normalize one port-like value into an integer."""
    text = str(value or "").strip()
    return int(text) if text.isdigit() else 0


class ManagerPulser(BossPulser):
    """Manager-local pulser for team joins, worker provisioning, and monitoring."""

    def __init__(
        self,
        *args: Any,
        supported_pulses: list[dict[str, Any]] | None = None,
        agent_card: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the manager pulser."""
        config = kwargs.pop("config", None)
        if isinstance(config, Mapping):
            config_data = dict(config or {})
        elif isinstance(config, (str, Path)):
            config_data = _read_config(config)
        else:
            config_data = {}

        resolved_party = str(
            config_data.get("party")
            or (agent_card or {}).get("party")
            or DEFAULT_TEAMWORK_PARTY
        ).strip() or DEFAULT_TEAMWORK_PARTY

        effective_config = dict(config_data)
        effective_config.setdefault("party", resolved_party)
        effective_config.setdefault("role", "manager_pulser")
        effective_config.setdefault("type", "phemacast.pulsers.manager_pulser.ManagerPulser")

        card = dict(agent_card or config_data.get("agent_card") or {})
        configured_name = str(effective_config.get("name") or card.get("name") or "").strip()
        used_generic_name = _looks_generic_manager_pulser_name(configured_name)
        configured_port = (
            _coerce_port(effective_config.get("port"))
            or _coerce_port(card.get("port"))
            or _port_from_address(config_data.get("manager_address"))
            or 0
        )
        default_manager_address = str(config_data.get("manager_address") or "").strip().rstrip("/")
        resolved_name = configured_name
        if used_generic_name and configured_port > 0:
            resolved_name = f"ManagerPulser-{configured_port}"
        elif not resolved_name:
            resolved_name = "ManagerPulser"
        effective_config["name"] = resolved_name
        card["name"] = resolved_name
        card.setdefault("party", resolved_party)
        card.setdefault("role", "manager_pulser")
        card_meta = dict(card.get("meta") or {}) if isinstance(card.get("meta"), Mapping) else {}
        if default_manager_address and not str(card_meta.get("manager_address") or "").strip():
            card_meta["manager_address"] = default_manager_address
        card["meta"] = card_meta
        card.setdefault(
            "description",
            "Phemacast pulser for joining one teamwork team, preparing local workers, and monitoring a manager environment.",
        )
        existing_tags = list(card.get("tags") or [])
        for tag in ("phemacast", "teamwork", "manager", "pulser"):
            if tag not in existing_tags:
                existing_tags.append(tag)
        card["tags"] = existing_tags

        super().__init__(
            *args,
            supported_pulses=supported_pulses or self._default_supported_pulses(),
            agent_card=card,
            config=effective_config if config_data else config,
            **kwargs,
        )

        if used_generic_name and configured_port <= 0 and int(getattr(self, "port", 0) or 0) > 0:
            runtime_name = f"ManagerPulser-{int(self.port)}"
            self.name = runtime_name
            self.agent_card["name"] = runtime_name
            self.app.title = runtime_name
            self.logger = logging.LoggerAdapter(logging.getLogger(__name__), {"agent_name": self.name})

        source_config = dict(config_data or self.raw_config or {})
        source_meta = dict(self.agent_card.get("meta") or {}) if isinstance(self.agent_card.get("meta"), Mapping) else {}
        self.default_manager_address = str(
            source_config.get("manager_address")
            or source_meta.get("manager_address")
            or ""
        ).strip().rstrip("/")
        self.default_team_manifest = _coerce_object(source_config.get("team_manifest"))

    @staticmethod
    def _default_supported_pulses() -> list[dict[str, Any]]:
        """Return the manager pulser supported pulses."""
        pulses = list(BossPulser._default_supported_pulses())
        existing_names = {str(pulse.get("name") or "").strip() for pulse in pulses if isinstance(pulse, Mapping)}
        alias_pulses = [
            {
                "name": "join_team",
                "pulse_address": "plaza://pulse/join_team",
                "description": "Join one BossPulser team manifest and prepare one local manager environment.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "team_manifest": {"type": "object"},
                        "manager_name": {"type": "string"},
                        "manager_port": {"type": "integer"},
                        "worker_count": {"type": "integer"},
                    },
                },
                "test_data": {
                    "team_manifest": {
                        "api_version": "phemacast.team_manifest.v1",
                        "team_name": "Map Runner",
                        "team_slug": "map-runner",
                        "party": "Phemacast",
                        "plaza_url": "http://127.0.0.1:8011",
                    },
                    "manager_name": "MapRunnerManagerEast",
                    "manager_port": 8270,
                    "worker_count": 2,
                },
            },
            {
                "name": "create_local_worker",
                "pulse_address": "plaza://pulse/create_local_worker",
                "description": "Generate one worker config for a manager-local environment.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "team_name": {"type": "string"},
                        "worker_name": {"type": "string"},
                        "manager_address": {"type": "string"},
                        "job_capabilities": {"type": "array"},
                    },
                },
                "test_data": {
                    "team_name": "Map Runner",
                    "worker_name": "MapRunnerWorkerEast1",
                    "manager_address": "http://127.0.0.1:8270",
                    "job_capabilities": [
                        {
                            "name": "run map",
                            "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                        }
                    ],
                },
            },
            {
                "name": "monitor_local_manager",
                "pulse_address": "plaza://pulse/monitor_local_manager",
                "description": "Return the managed-work monitor payload for one manager-local environment.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "manager_address": {"type": "string"},
                        "party": {"type": "string"},
                    },
                },
                "test_data": {
                    "manager_address": "http://127.0.0.1:8270",
                    "party": "Phemacast",
                },
            },
        ]
        for pulse in alias_pulses:
            if pulse["name"] not in existing_names:
                pulses.append(pulse)
        return pulses

    def _ui_initial_payload(self) -> dict[str, Any]:
        """Return the manager pulser UI payload."""
        payload = super()._ui_initial_payload()
        payload["ui"] = {
            "page_title": "Phemacast Manager Pulse Deck",
            "hero_eyebrow": "Local Manager Command",
            "hero_heading": "Phemacast Manager Pulse Deck",
            "hero_summary": (
                "Join a boss-issued team manifest, prepare local workers, and monitor one manager environment "
                "from a single manager-local console."
            ),
            "operator_label": "Manager Pulser",
            "mission_title": "Local Mission Console",
            "mission_summary": "Issue or inspect work for the connected manager environment.",
            "provision_title": "Manager Provisioning Studio",
            "provision_summary": (
                "Join a saved team manifest, then generate the local manager and worker blueprints "
                "for this environment."
            ),
            "team_tab_label": "Full Team",
            "manager_tab_label": "Join Team",
            "worker_tab_label": "Worker",
            "default_provisioning_tab": "manager",
        }
        payload["defaults"] = {
            "manager_address": self.default_manager_address,
            "team_manifest": copy.deepcopy(self.default_team_manifest),
        }
        if self.default_team_manifest:
            payload["examples"]["team_manifest"] = copy.deepcopy(self.default_team_manifest)
        return payload

    def _normalize_manager_local_input(self, input_data: Mapping[str, Any] | None) -> dict[str, Any]:
        """Apply manager-local defaults to a request payload."""
        normalized = dict(input_data or {})
        if not normalized.get("party"):
            normalized["party"] = self.default_party
        if not normalized.get("manager_address") and self.default_manager_address:
            normalized["manager_address"] = self.default_manager_address
        if not normalized.get("team_manifest") and self.default_team_manifest:
            normalized["team_manifest"] = copy.deepcopy(self.default_team_manifest)
        return normalized

    def _handle_join_team(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Alias team join through the BossPulser manager-connect contract."""
        return self._handle_connect_manager(self._normalize_manager_local_input(input_data))

    def _handle_create_local_worker(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Alias local worker creation through the worker blueprint flow."""
        return self._handle_create_worker(self._normalize_manager_local_input(input_data))

    def _handle_monitor_local_manager(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Alias local monitoring through the managed-work monitor payload."""
        return self.monitor_managed_work(self._normalize_manager_local_input(input_data))

    def _setup_routes(self) -> None:
        """Set up manager-local routes and aliases."""
        super()._setup_routes()

        @self.app.post("/api/team/join")
        async def manager_pulser_join_team(payload: Dict[str, Any]):
            """Route handler for POST /api/team/join."""
            try:
                return await run_in_threadpool(self._handle_join_team, dict(payload or {}))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/workers/local")
        async def manager_pulser_create_local_worker(payload: Dict[str, Any]):
            """Route handler for POST /api/workers/local."""
            try:
                return await run_in_threadpool(self._handle_create_local_worker, dict(payload or {}))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/manager/monitor")
        async def manager_pulser_monitor_local_manager(
            manager_address: str = "",
            party: str = "",
            preview_limit: int = 500,
            ticket_limit: int = 20,
            schedule_limit: int = 20,
        ):
            """Route handler for GET /api/manager/monitor."""
            try:
                return await run_in_threadpool(
                    self._handle_monitor_local_manager,
                    {
                        "manager_address": manager_address,
                        "party": party or self.default_party,
                        "preview_limit": preview_limit,
                        "ticket_limit": ticket_limit,
                        "schedule_limit": schedule_limit,
                    },
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
