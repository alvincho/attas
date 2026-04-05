"""
Boss pulser implementation for the Pulsers area.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, these modules implement pulse sources for
APIs, files, bosses, MCP tools, and path-based workflows.

Experimental notice: `BossPulser` is still under active development. Its UI surface,
payload contracts, and orchestration flows may change as managed-work and teamwork
integration continue to stabilize.

Core types exposed here include `BossPulser`, which carry the main behavior or state
managed by this module.
"""

from __future__ import annotations

import copy
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

import requests
from fastapi import HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from phemacast.agents.pulser import Pulser, _read_config
from prompits.dispatcher.boss import DispatcherBossAgent, SCHEDULED_JOBS_SCHEMA, TABLE_SCHEDULED_JOBS
from prompits.dispatcher.agents import WORKER_HEARTBEAT_INTERVAL_SEC, WORKER_JOB_TIMEOUT_SEC
from prompits.dispatcher.jobcap import infer_job_cap_name
from prompits.dispatcher.runtime import normalize_capabilities, parse_datetime_value
from prompits.teamwork.models import ManagedScheduleRequest, ManagedTicketRequest
from prompits.teamwork.runtime import (
    build_id,
    build_managed_work_monitor,
    build_managed_work_metadata,
    managed_schedule_from_row,
    managed_ticket_from_job_row,
    utcnow_iso,
)
from prompits.teamwork.schema import TABLE_JOBS, TABLE_WORKER_HISTORY, TABLE_WORKERS


DEFAULT_TEAMWORK_PARTY = "Phemacast"
DEFAULT_MANAGER_CLASS = "prompits.teamwork.agents.DispatcherManagerAgent"
DEFAULT_BOSS_CLASS = "prompits.teamwork.boss.TeamBossAgent"
DEFAULT_WORKER_CLASS = "prompits.teamwork.agents.TeamWorkerAgent"
TEAM_MANIFEST_VERSION = "phemacast.team_manifest.v1"
BASE_DIR = Path(__file__).resolve().parent / "boss_ui"


def _slugify(value: Any, fallback: str = "team") -> str:
    """Internal helper for slugify."""
    text = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return text or fallback


def _titleify_slug(value: str) -> str:
    """Internal helper for titleify slug."""
    pieces = [piece for piece in re.split(r"[^a-zA-Z0-9]+", str(value or "")) if piece]
    return "".join(piece[:1].upper() + piece[1:] for piece in pieces) or "Team"


def _safe_int(value: Any, default: int) -> int:
    """Internal helper for safe int."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    """Internal helper for safe bool."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _normalize_url(value: Any) -> str:
    """Internal helper to normalize the URL."""
    return str(value or "").strip().rstrip("/")


def _coerce_object(value: Any) -> dict[str, Any]:
    """Internal helper to coerce the object."""
    return dict(value or {}) if isinstance(value, Mapping) else {}


def _coerce_list(value: Any) -> list[Any]:
    """Internal helper to coerce the list."""
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, set):
        return list(value)
    return [value]


def _normalize_job_cap_entry(entry: Any) -> dict[str, Any]:
    """Internal helper to normalize the job cap entry."""
    if isinstance(entry, Mapping):
        normalized = copy.deepcopy(dict(entry))
        normalized_name = infer_job_cap_name(normalized) or str(normalized.get("name") or "").strip().lower()
        if normalized_name:
            normalized["name"] = normalized_name
        return normalized
    if isinstance(entry, str):
        normalized_name = infer_job_cap_name(entry)
        return {"name": normalized_name or str(entry).strip().lower(), "callable": entry}
    return {}


def _normalize_job_cap_entries(entries: Any) -> list[dict[str, Any]]:
    """Internal helper to normalize the job cap entries."""
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in _coerce_list(entries):
        normalized_entry = _normalize_job_cap_entry(entry)
        name = str(normalized_entry.get("name") or "").strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        normalized.append(normalized_entry)
    return normalized


def _job_option_entries(entries: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Internal helper for job option entries."""
    options: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        name = str(entry.get("name") or "").strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        option = {"name": name}
        if str(entry.get("description") or "").strip():
            option["description"] = str(entry.get("description") or "").strip()
        if "default_priority" in entry:
            option["default_priority"] = _safe_int(entry.get("default_priority"), 100)
        if "payload_template" in entry and entry.get("payload_template") is not None:
            option["payload_template"] = entry.get("payload_template")
        options.append(option)
    return options


def _job_capability_warnings(entries: Iterable[Mapping[str, Any]]) -> list[str]:
    """Internal helper for job capability warnings."""
    warnings: list[str] = []
    for entry in entries:
        if not isinstance(entry, Mapping):
            continue
        if any(key in entry for key in ("callable", "fn", "handler", "function", "type", "class", "job_cap_type")):
            continue
        normalized_name = str(entry.get("name") or "").strip() or "unnamed capability"
        warnings.append(
            f"Job capability '{normalized_name}' is missing a callable or type reference for worker execution."
        )
    return warnings


def _safe_json_copy(value: Any) -> Any:
    """Return a deepcopy-safe value for response payloads."""
    try:
        return copy.deepcopy(value)
    except Exception:
        return value


class BossPulser(Pulser):
    """
    Experimental Phemacast-facing pulser that provisions and monitors teamwork teams.

    The pulser keeps orchestration thin:
    - Plaza discovery is used to find managers and workers on the network.
    - Team status/history comes from teamwork manager practices.
    - Team creation returns ready-to-save teamwork config documents instead of
      launching local processes directly.
    - API shapes and UI affordances are expected to evolve while BossPulser is
      still being developed.
    """

    def __init__(
        self,
        *args: Any,
        supported_pulses: list[dict[str, Any]] | None = None,
        agent_card: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the boss pulser."""
        config = kwargs.pop("config", None)
        if isinstance(config, Mapping):
            config_data = dict(config or {})
        elif isinstance(config, (str, Path)):
            config_data = _read_config(config)
        else:
            config_data = {}
        raw_config = config_data.get("raw_config") if isinstance(config_data.get("raw_config"), Mapping) else {}
        resolved_party = str(
            config_data.get("party")
            or (agent_card or {}).get("party")
            or DEFAULT_TEAMWORK_PARTY
        ).strip() or DEFAULT_TEAMWORK_PARTY

        card = dict(agent_card or config_data.get("agent_card") or {})
        card.setdefault("party", resolved_party)
        configured_role = str(config_data.get("role") or raw_config.get("role") or "").strip().lower()
        current_role = str(card.get("role") or "").strip().lower()
        if configured_role:
            card["role"] = configured_role
        elif not current_role or current_role == "generic":
            card["role"] = "boss"
        card.setdefault(
            "description",
            "Phemacast pulser for teamwork team provisioning, capability discovery, and live monitoring.",
        )
        existing_tags = list(card.get("tags") or [])
        for tag in ("phemacast", "teamwork", "boss", "pulser"):
            if tag not in existing_tags:
                existing_tags.append(tag)
        card["tags"] = existing_tags

        effective_config = dict(config_data)
        effective_config.setdefault("party", resolved_party)
        effective_config.setdefault("type", "phemacast.pulsers.boss_pulser.BossPulser")

        super().__init__(
            *args,
            supported_pulses=supported_pulses or self._default_supported_pulses(),
            agent_card=card,
            config=effective_config if config_data else config,
            **kwargs,
        )
        self.default_party = resolved_party
        self.templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
        self.app.mount("/boss-pulser-static", StaticFiles(directory=str(BASE_DIR / "static")), name="boss_pulser_static")
        self.scheduler_poll_sec = max(
            _safe_int(
                raw_config.get("scheduler_poll_sec") if isinstance(raw_config, Mapping) else config_data.get("scheduler_poll_sec"),
                5,
            ),
            0,
        )
        self._schedule_issue_lock = threading.Lock()
        self._schedule_stop_event = threading.Event()
        self._schedule_thread: threading.Thread | None = None
        self._schedule_thread_lock = threading.Lock()
        self.ensure_managed_schedule_tables()
        self._setup_scheduler_events()
        self._setup_routes()

    @staticmethod
    def _default_supported_pulses() -> list[dict[str, Any]]:
        """Internal helper to return the default supported pulses."""
        return [
            {
                "name": "create_team",
                "pulse_address": "plaza://pulse/create_team",
                "description": "Generate boss, manager, and worker teamwork configs for a new Phemacast team.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "team_name": {"type": "string"},
                        "party": {"type": "string"},
                        "plaza_url": {"type": "string"},
                        "worker_count": {"type": "integer"},
                        "job_capabilities": {"type": "array"},
                    },
                },
                "test_data": {
                    "team_name": "Map Runner",
                    "party": "Phemacast",
                    "plaza_url": "http://127.0.0.1:8011",
                    "worker_count": 2,
                    "job_capabilities": [
                        {
                            "name": "run map",
                            "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                            "description": "Execute a stored map phema through MapCastr.",
                            "default_priority": 100,
                        }
                    ],
                },
            },
            {
                "name": "create_worker",
                "pulse_address": "plaza://pulse/create_worker",
                "description": "Generate a teamwork worker config aimed at one manager.",
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
                    "worker_name": "MapRunnerWorkerA",
                    "manager_address": "http://127.0.0.1:8170",
                    "job_capabilities": [
                        {
                            "name": "run map",
                            "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                        }
                    ],
                },
            },
            {
                "name": "create_manager",
                "pulse_address": "plaza://pulse/create_manager",
                "description": "Generate a teamwork manager config for one Phemacast team.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "team_name": {"type": "string"},
                        "manager_name": {"type": "string"},
                        "party": {"type": "string"},
                        "job_capabilities": {"type": "array"},
                    },
                },
                "test_data": {
                    "team_name": "Map Runner",
                    "manager_name": "MapRunnerManager",
                    "party": "Phemacast",
                    "job_capabilities": [
                        {
                            "name": "run map",
                            "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                            "description": "Execute a stored map phema through MapCastr.",
                            "default_priority": 100,
                        }
                    ],
                },
            },
            {
                "name": "connect_manager",
                "pulse_address": "plaza://pulse/connect_manager",
                "description": "Connect one manager environment to an existing team and optionally generate local workers.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "team_manifest": {"type": "object"},
                        "manager_name": {"type": "string"},
                        "worker_count": {"type": "integer"},
                        "manager_port": {"type": "integer"},
                    },
                },
                "test_data": {
                    "team_manifest": {
                        "team_name": "Map Runner",
                        "team_slug": "map-runner",
                        "party": "Phemacast",
                        "plaza_url": "http://127.0.0.1:8011",
                        "job_capabilities": [
                            {
                                "name": "run map",
                                "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                                "description": "Execute a stored map phema through MapCastr.",
                                "default_priority": 100,
                            }
                        ],
                    },
                    "manager_name": "MapRunnerManagerEast",
                    "worker_count": 2,
                    "manager_port": 8270,
                },
            },
            {
                "name": "discover_teams",
                "pulse_address": "plaza://pulse/discover_teams",
                "description": "Discover teamwork managers and associated workers from Plaza.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "party": {"type": "string"},
                        "name": {"type": "string"},
                        "include_workers": {"type": "boolean"},
                    },
                },
                "test_data": {"party": "Phemacast", "include_workers": True},
            },
            {
                "name": "supported_jobcaps",
                "pulse_address": "plaza://pulse/supported_jobcaps",
                "description": "Aggregate supported job capabilities from teamwork managers and workers.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "party": {"type": "string"},
                        "manager_address": {"type": "string"},
                    },
                },
                "test_data": {"party": "Phemacast"},
            },
            {
                "name": "team_status",
                "pulse_address": "plaza://pulse/team_status",
                "description": "Summarize current queue and worker health for one teamwork manager.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "manager_address": {"type": "string"},
                        "party": {"type": "string"},
                        "preview_limit": {"type": "integer"},
                    },
                },
                "test_data": {"manager_address": "http://127.0.0.1:8170", "preview_limit": 500},
            },
            {
                "name": "team_history",
                "pulse_address": "plaza://pulse/team_history",
                "description": "Return recent job and worker history from one teamwork manager.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "manager_address": {"type": "string"},
                        "party": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                },
                "test_data": {"manager_address": "http://127.0.0.1:8170", "limit": 20},
            },
            {
                "name": "submit_team_job",
                "pulse_address": "plaza://pulse/submit_team_job",
                "description": "Submit a job to a teamwork manager for workers to process.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "manager_address": {"type": "string"},
                        "required_capability": {"type": "string"},
                        "payload": {"type": "object"},
                        "priority": {"type": "integer"},
                    },
                },
                "test_data": {
                    "manager_address": "http://127.0.0.1:8170",
                    "required_capability": "run map",
                    "payload": {"phema_path": "phemacast/configs/map.phemar"},
                    "priority": 100,
                },
            },
            {
                "name": "create_managed_ticket",
                "pulse_address": "plaza://pulse/create_managed_ticket",
                "description": "Create one manual managed-work ticket through BossPulser and teamwork.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "manager_address": {"type": "string"},
                        "required_capability": {"type": "string"},
                        "payload": {"type": "object"},
                        "targets": {"type": "array"},
                        "priority": {"type": "integer"},
                    },
                },
                "test_data": {
                    "manager_address": "http://127.0.0.1:8170",
                    "required_capability": "run map",
                    "payload": {"phema_path": "phemacast/configs/map.phemar"},
                    "targets": ["taipei-basemap"],
                    "priority": 100,
                },
            },
            {
                "name": "create_managed_schedule",
                "pulse_address": "plaza://pulse/create_managed_schedule",
                "description": "Save one managed-work schedule that BossPulser will issue through teamwork when due.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "manager_address": {"type": "string"},
                        "required_capability": {"type": "string"},
                        "scheduled_for": {"type": "string"},
                        "payload": {"type": "object"},
                        "targets": {"type": "array"},
                    },
                },
                "test_data": {
                    "manager_address": "http://127.0.0.1:8170",
                    "required_capability": "run map",
                    "scheduled_for": "2026-04-05T08:00:00+00:00",
                    "payload": {"phema_path": "phemacast/configs/map.phemar"},
                    "targets": ["taipei-basemap"],
                },
            },
            {
                "name": "monitor_managed_work",
                "pulse_address": "plaza://pulse/monitor_managed_work",
                "description": "Return the BossPulser managed-work monitor payload for one teamwork manager.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "manager_address": {"type": "string"},
                        "party": {"type": "string"},
                    },
                },
                "test_data": {
                    "manager_address": "http://127.0.0.1:8170",
                    "party": "Phemacast",
                },
            },
        ]

    def fetch_pulse_payload(
        self,
        pulse_name: str,
        input_data: dict[str, Any],
        pulse_definition: dict[str, Any],
    ) -> dict[str, Any]:
        """Fetch the pulse payload."""
        handler = getattr(self, f"_handle_{str(pulse_name or '').strip().lower()}", None)
        if not callable(handler):
            return {"error": f"Unsupported BossPulser pulse '{pulse_name}'."}
        try:
            return handler(dict(input_data or {}))
        except Exception as exc:
            return {
                "error": str(exc),
                "pulse_name": str(pulse_name or ""),
                "input_data": dict(input_data or {}),
            }

    def _party_from_input(self, input_data: Mapping[str, Any]) -> str:
        """Internal helper to return the party from input."""
        return str(
            input_data.get("party")
            or input_data.get("network_party")
            or self.agent_card.get("party")
            or self.default_party
            or DEFAULT_TEAMWORK_PARTY
        ).strip() or DEFAULT_TEAMWORK_PARTY

    @staticmethod
    def _entry_card(entry: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to return the entry card."""
        return dict(entry.get("card") or {}) if isinstance(entry.get("card"), Mapping) else {}

    def _entry_meta(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper for entry meta."""
        card = self._entry_card(entry)
        return dict(card.get("meta") or {}) if isinstance(card.get("meta"), Mapping) else {}

    def _entry_address(self, entry: Mapping[str, Any]) -> str:
        """Internal helper to return the entry address."""
        card = self._entry_card(entry)
        for candidate in (entry.get("address"), card.get("address"), entry.get("pit_address")):
            normalized = str(candidate or "").strip().rstrip("/")
            if normalized:
                return normalized
        return ""

    def _entry_name(self, entry: Mapping[str, Any]) -> str:
        """Internal helper to return the entry name."""
        card = self._entry_card(entry)
        return str(entry.get("name") or card.get("name") or "").strip()

    def _supported_pulse_names(self, entry: Mapping[str, Any]) -> list[str]:
        """Internal helper to return supported pulse names for one entry."""
        meta = self._entry_meta(entry)
        supported = meta.get("supported_pulses") if isinstance(meta.get("supported_pulses"), list) else []
        names: list[str] = []
        for pulse in supported:
            if isinstance(pulse, Mapping):
                normalized = str(pulse.get("name") or "").strip()
            else:
                normalized = str(pulse or "").strip()
            if normalized and normalized not in names:
                names.append(normalized)
        return names

    def _entry_last_active(self, entry: Mapping[str, Any]) -> float:
        """Internal helper to return the entry last active."""
        try:
            return float(entry.get("last_active") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _search_entries(self, **params: Any) -> list[dict[str, Any]]:
        """Internal helper to search the entries."""
        rows = self.search(**params) or []
        return [dict(row) for row in rows if isinstance(row, Mapping)]

    @staticmethod
    def _asset_version() -> str:
        """Internal helper to return the asset version."""
        return str(
            max(
                int((BASE_DIR / "static" / "boss.css").stat().st_mtime),
                int((BASE_DIR / "static" / "boss.js").stat().st_mtime),
                int((BASE_DIR / "templates" / "index.html").stat().st_mtime),
            )
        )

    @staticmethod
    def _example_job_capabilities() -> list[dict[str, Any]]:
        """Internal helper for example job capabilities."""
        return [
            {
                "name": "run map",
                "type": "phemacast.jobcaps.map_jobcap:RunMapJobCap",
                "description": "Execute a stored map phema through MapCastr.",
                "default_priority": 100,
            }
        ]

    @staticmethod
    def _example_job_payload() -> dict[str, Any]:
        """Internal helper to return the example job payload."""
        return {
            "phema_path": "phemacast/configs/map.phemar",
            "targets": ["taipei-basemap"],
        }

    def _example_team_manifest(self) -> dict[str, Any]:
        """Internal helper to return the example team manifest."""
        team_name = "Map Runner"
        team_slug = "map-runner"
        party = self.default_party or DEFAULT_TEAMWORK_PARTY
        plaza_url = str(self.plaza_url or "http://127.0.0.1:8011").strip()
        job_capabilities = self._example_job_capabilities()
        capabilities = normalize_capabilities([entry.get("name") for entry in job_capabilities if entry.get("name")])
        return self._build_team_manifest_payload(
            team_name=team_name,
            team_slug=team_slug,
            party=party,
            plaza_url=plaza_url,
            boss_name="MapRunnerBoss",
            boss_host="127.0.0.1",
            boss_port=8175,
            manager_name="MapRunnerManager",
            manager_host="127.0.0.1",
            manager_port=8170,
            manager_class=DEFAULT_MANAGER_CLASS,
            worker_prefix="MapRunnerWorker",
            worker_host="127.0.0.1",
            worker_base_port=8171,
            worker_count=2,
            job_capabilities=job_capabilities,
            capabilities=capabilities,
            monitor_refresh_sec=10,
            poll_interval_sec=10,
            boss_auto_register=True,
            manager_auto_register=True,
            worker_auto_register=True,
        )

    def _ui_initial_payload(self) -> dict[str, Any]:
        """Internal helper to return the UI initial payload."""
        return {
            "status": "success",
            "name": self.name,
            "description": str(self.agent_card.get("description") or "").strip(),
            "party": self.default_party,
            "plaza_url": str(self.plaza_url or "").strip(),
            "supported_pulses": [pulse.get("name") for pulse in self.supported_pulses if pulse.get("name")],
            "examples": {
                "team_job_capabilities": self._example_job_capabilities(),
                "job_payload": self._example_job_payload(),
                "team_manifest": self._example_team_manifest(),
            },
            "defaults": {
                "hire_worker_count": 1,
                "hire_worker_name_prefix": "TeamWorker",
                "hire_worker_base_port": 8271,
            },
        }

    def _ui_context(self) -> dict[str, Any]:
        """Internal helper for UI context."""
        return {
            "asset_version": self._asset_version(),
            "initial_payload": self._ui_initial_payload(),
        }

    def _setup_scheduler_events(self) -> None:
        """Internal helper to set up the BossPulser scheduler events."""

        @self.app.on_event("startup")
        def _start_boss_pulser_scheduler():
            """Start the BossPulser schedule loop."""
            self._start_scheduler_thread()

        @self.app.on_event("shutdown")
        def _stop_boss_pulser_scheduler():
            """Stop the BossPulser schedule loop."""
            self._stop_scheduler_thread()

    def _start_scheduler_thread(self) -> bool:
        """Internal helper to start the BossPulser scheduler thread."""
        if self.pool is None or self.scheduler_poll_sec <= 0:
            return False
        with self._schedule_thread_lock:
            current = self._schedule_thread
            if current and current.is_alive():
                return False
            self._schedule_stop_event = threading.Event()
            schedule_thread = threading.Thread(
                target=self._scheduler_loop,
                daemon=True,
                name=f"{self.name}-managed-scheduler",
            )
            self._schedule_thread = schedule_thread
            schedule_thread.start()
            return True

    def _stop_scheduler_thread(self, join_timeout: float | None = None) -> bool:
        """Internal helper to stop the BossPulser scheduler thread."""
        with self._schedule_thread_lock:
            schedule_thread = self._schedule_thread
            if schedule_thread is None:
                return False
            self._schedule_stop_event.set()
        schedule_thread.join(timeout=max(float(join_timeout or (self.scheduler_poll_sec + 1.0)), 0.2))
        with self._schedule_thread_lock:
            if self._schedule_thread is schedule_thread and not schedule_thread.is_alive():
                self._schedule_thread = None
        return True

    def _scheduler_loop(self) -> None:
        """Internal helper for the BossPulser schedule loop."""
        interval = max(float(self.scheduler_poll_sec or 0), 0.2)
        while not self._schedule_stop_event.is_set():
            try:
                self.process_due_managed_schedules(limit=20)
            except Exception as exc:
                self.logger.exception("BossPulser managed schedule iteration failed: %s", exc)
            if self._schedule_stop_event.wait(interval):
                break

    def ensure_managed_schedule_tables(self) -> None:
        """Ensure the local managed schedule storage exists."""
        if self.pool is None:
            return
        if not self.pool._TableExists(TABLE_SCHEDULED_JOBS):
            self.pool._CreateTable(TABLE_SCHEDULED_JOBS, SCHEDULED_JOBS_SCHEMA)

    @staticmethod
    def _manager_identity_from_entry(manager_entry: Mapping[str, Any]) -> dict[str, str]:
        """Internal helper to return the manager identity payload."""
        card = dict(manager_entry.get("card") or {}) if isinstance(manager_entry.get("card"), Mapping) else {}
        return {
            "manager_address": str(
                manager_entry.get("address") or card.get("address") or manager_entry.get("pit_address") or ""
            ).strip().rstrip("/"),
            "manager_name": str(manager_entry.get("name") or card.get("name") or "Manager").strip() or "Manager",
            "manager_party": str(card.get("party") or manager_entry.get("party") or "").strip(),
        }

    @staticmethod
    def _manager_entry_from_identity(identity: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to synthesize one manager entry from identity data."""
        manager_address = str(identity.get("manager_address") or "").strip().rstrip("/")
        manager_name = str(identity.get("manager_name") or "Manager").strip() or "Manager"
        manager_party = str(identity.get("manager_party") or "").strip()
        return {
            "address": manager_address,
            "name": manager_name,
            "card": {
                "address": manager_address,
                "name": manager_name,
                "party": manager_party,
                "role": "manager",
            },
        }

    @staticmethod
    def _normalized_ticket_targets(request: ManagedTicketRequest) -> list[str]:
        """Internal helper to return normalized ticket targets."""
        normalized_targets = [str(value).strip() for value in list(request.targets or []) if str(value).strip()]
        if not normalized_targets:
            normalized_targets = [str(value).strip() for value in list(request.symbols or []) if str(value).strip()]
        return normalized_targets

    @staticmethod
    def _normalize_managed_submission_job(payload: Mapping[str, Any], result: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Internal helper to normalize one manager submission response into a job row."""
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
        return DispatcherBossAgent._normalize_job_row(normalized)

    def _ticket_submission_payload(
        self,
        request: ManagedTicketRequest,
        *,
        manager_identity: Mapping[str, str],
        ticket_id: str,
        work_id: str,
    ) -> dict[str, Any]:
        """Internal helper to build one manager-submit payload."""
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
            "capability_tags": list(request.capability_tags or []),
            "job_type": str(request.job_type or "run").strip() or "run",
            "priority": int(request.priority),
            "premium": bool(request.premium),
            "metadata": metadata,
            "scheduled_for": str(request.scheduled_for or "").strip(),
            "max_attempts": max(int(request.max_attempts), 1),
            "job_id": ticket_id,
        }

    def _normalize_managed_schedule_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to normalize one saved managed schedule row."""
        return DispatcherBossAgent._normalize_schedule_row(row)

    def _load_managed_schedule_rows(self) -> list[dict[str, Any]]:
        """Internal helper to load saved managed schedule rows."""
        if self.pool is None:
            return []
        self.ensure_managed_schedule_tables()
        rows = self.pool._GetTableData(TABLE_SCHEDULED_JOBS, table_schema=SCHEDULED_JOBS_SCHEMA) or []
        return [self._normalize_managed_schedule_row(row) for row in rows if isinstance(row, Mapping)]

    def _get_managed_schedule_row(self, schedule_id: str) -> dict[str, Any]:
        """Internal helper to return one saved managed schedule row."""
        normalized_schedule_id = str(schedule_id or "").strip()
        if not normalized_schedule_id:
            raise ValueError("schedule_id is required.")
        if self.pool is None:
            raise ValueError("Managed schedule storage is not configured.")
        self.ensure_managed_schedule_tables()
        rows = self.pool._GetTableData(TABLE_SCHEDULED_JOBS, normalized_schedule_id, table_schema=SCHEDULED_JOBS_SCHEMA) or []
        if not rows:
            raise LookupError(f"Managed schedule '{normalized_schedule_id}' was not found.")
        return self._normalize_managed_schedule_row(rows[0])

    def _save_managed_schedule_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to persist one managed schedule row."""
        if self.pool is None:
            raise ValueError("Managed schedule storage is not configured.")
        normalized = self._normalize_managed_schedule_row(row)
        storage_row = dict(normalized)
        storage_row.pop("symbols", None)
        for field_name in ("scheduled_for", "issued_at", "last_attempted_at", "created_at", "updated_at"):
            value = storage_row.get(field_name)
            if isinstance(value, str) and not value.strip():
                storage_row[field_name] = None
        if not self.pool._Insert(TABLE_SCHEDULED_JOBS, storage_row):
            raise RuntimeError("Failed to persist managed schedule.")
        return normalized

    def create_managed_ticket(self, input_data: Mapping[str, Any]) -> dict[str, Any]:
        """Create one manual managed ticket through the selected teamwork manager."""
        request = ManagedTicketRequest.model_validate(dict(input_data or {}))
        manager_entry = self._resolve_manager_entry(input_data)
        manager_identity = self._manager_identity_from_entry(manager_entry)
        ticket_id = str(request.ticket_id or build_id("managed-ticket")).strip()
        work_id = str(request.work_id or ticket_id).strip()
        payload = self._ticket_submission_payload(
            request,
            manager_identity=manager_identity,
            ticket_id=ticket_id,
            work_id=work_id,
        )
        result = self._use_manager_practice(manager_identity["manager_address"], "manager-submit-job", payload)
        job = self._normalize_managed_submission_job(payload, result if isinstance(result, Mapping) else None)
        return {
            "status": "success",
            "manager": self._team_descriptor(manager_entry),
            "ticket": managed_ticket_from_job_row(
                job,
                manager_address=manager_identity["manager_address"],
                manager_name=manager_identity["manager_name"],
                manager_party=manager_identity["manager_party"],
            ),
        }

    def _handle_create_managed_ticket(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to handle manual managed ticket creation."""
        return self.create_managed_ticket(input_data)

    def create_managed_schedule(self, input_data: Mapping[str, Any]) -> dict[str, Any]:
        """Create one saved managed-work schedule in BossPulser storage."""
        request = ManagedScheduleRequest.model_validate(dict(input_data or {}))
        manager_entry = self._resolve_manager_entry(input_data)
        manager_identity = self._manager_identity_from_entry(manager_entry)
        repeat_frequency = DispatcherBossAgent._normalize_repeat_frequency(request.repeat_frequency)
        schedule_timezone = DispatcherBossAgent._normalize_schedule_timezone(request.schedule_timezone)
        schedule_times = DispatcherBossAgent._normalize_schedule_times(request.schedule_times or request.schedule_time)
        schedule_weekdays = DispatcherBossAgent._normalize_schedule_weekdays(request.schedule_weekdays)
        schedule_days_of_month = DispatcherBossAgent._normalize_schedule_days_of_month(
            request.schedule_days_of_month or request.schedule_day_of_month
        )
        if repeat_frequency == "once":
            scheduled_for = DispatcherBossAgent._normalize_schedule_timestamp(request.scheduled_for)
            schedule_times = []
            schedule_weekdays = []
            schedule_days_of_month = []
        else:
            if not schedule_times:
                raise ValueError("schedule_times is required for repeating schedules.")
            scheduled_for = DispatcherBossAgent._compute_next_occurrence(
                repeat_frequency=repeat_frequency,
                timezone_name=schedule_timezone,
                schedule_times=schedule_times,
                weekdays=schedule_weekdays,
                days_of_month=schedule_days_of_month,
            )
        schedule_id = str(request.work_id or build_id("managed-schedule")).strip()
        now = utcnow_iso()
        metadata = build_managed_work_metadata(
            request.metadata,
            work_id=schedule_id,
            source="schedule",
            manager_address=manager_identity["manager_address"],
            manager_name=manager_identity["manager_name"],
            manager_party=manager_identity["manager_party"],
            schedule_id=schedule_id,
            workflow_id=str(request.workflow_id or ""),
            title=str(request.title or request.name or request.required_capability or schedule_id).strip(),
            assigned_at=now,
        )
        record = {
            "id": schedule_id,
            "name": DispatcherBossAgent._build_schedule_name(
                request.name or request.title,
                str(request.required_capability or ""),
                self._normalized_ticket_targets(request),
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
            "required_capability": str(request.required_capability or "").strip(),
            "targets": self._normalized_ticket_targets(request),
            "payload": request.payload,
            "target_table": str(request.target_table or "").strip(),
            "source_url": str(request.source_url or "").strip(),
            "parse_rules": request.parse_rules,
            "capability_tags": list(request.capability_tags or []),
            "job_type": str(request.job_type or "run").strip() or "run",
            "priority": int(request.priority),
            "premium": bool(request.premium),
            "metadata": metadata,
            "scheduled_for": scheduled_for,
            "max_attempts": max(int(request.max_attempts), 1),
            "dispatcher_job_id": "",
            "issued_at": "",
            "last_attempted_at": "",
            "last_error": "",
            "issue_attempts": 0,
            "created_at": now,
            "updated_at": now,
        }
        saved = self._save_managed_schedule_row(record)
        return {
            "status": "success",
            "schedule": managed_schedule_from_row(
                saved,
                manager_address=manager_identity["manager_address"],
                manager_name=manager_identity["manager_name"],
                manager_party=manager_identity["manager_party"],
            ),
        }

    def _handle_create_managed_schedule(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to handle managed schedule creation."""
        return self.create_managed_schedule(input_data)

    def list_managed_schedules(self, input_data: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """List saved managed-work schedules from BossPulser storage."""
        payload = dict(input_data or {})
        normalized_status = str(payload.get("status") or "").strip().lower()
        normalized_search = str(payload.get("search") or "").strip().lower()
        manager_address_filter = str(payload.get("manager_address") or "").strip().rstrip("/")
        try:
            normalized_limit = max(1, min(int(payload.get("limit") or 100), 200))
        except (TypeError, ValueError):
            normalized_limit = 100

        rows: list[dict[str, Any]] = []
        for row in self._load_managed_schedule_rows():
            row_status = str(row.get("status") or "").strip().lower()
            if not normalized_status and row_status == "deleted":
                continue
            if normalized_status and row_status != normalized_status:
                continue
            if manager_address_filter and str(row.get("dispatcher_address") or "").strip().rstrip("/") != manager_address_filter:
                continue
            if normalized_search:
                haystack = " ".join(
                    [
                        str(row.get("id") or ""),
                        str(row.get("name") or ""),
                        str(row.get("required_capability") or ""),
                        str(row.get("dispatcher_job_id") or ""),
                        str(row.get("last_error") or ""),
                        " ".join(row.get("targets") or []),
                    ]
                ).lower()
                if normalized_search not in haystack:
                    continue
            rows.append(row)
        rows.sort(key=DispatcherBossAgent._schedule_sort_tuple)
        schedules = [
            managed_schedule_from_row(row, manager_address=str(row.get("dispatcher_address") or ""))
            for row in rows[:normalized_limit]
        ]
        return {"status": "success", "count": len(rows), "schedules": schedules}

    def issue_managed_schedule(self, schedule_id: str, *, force_now: bool = False) -> dict[str, Any]:
        """Issue one saved managed schedule through the selected teamwork manager."""
        with self._schedule_issue_lock:
            schedule = self._get_managed_schedule_row(schedule_id)
            status = str(schedule.get("status") or "").strip().lower()
            if status == "deleted":
                raise ValueError(f"Managed schedule '{schedule_id}' has been deleted.")
            if status == "issued" and str(schedule.get("repeat_frequency") or "once").strip().lower() == "once":
                return {
                    "status": "success",
                    "schedule": managed_schedule_from_row(schedule, manager_address=str(schedule.get("dispatcher_address") or "")),
                    "ticket": None,
                    "already_issued": True,
                }

            metadata = _coerce_object(schedule.get("metadata"))
            managed = _coerce_object(metadata.get("managed_work"))
            manager_assignment = _coerce_object(managed.get("manager_assignment"))
            manager_identity = {
                "manager_address": str(schedule.get("dispatcher_address") or "").strip(),
                "manager_name": str(manager_assignment.get("manager_name") or "Manager").strip() or "Manager",
                "manager_party": str(manager_assignment.get("manager_party") or "").strip(),
            }
            manager_entry = self._manager_entry_from_identity(manager_identity)
            ticket_id = build_id("managed-ticket")
            now = utcnow_iso()
            updated_metadata = build_managed_work_metadata(
                metadata,
                work_id=str(managed.get("work_id") or schedule.get("id") or ticket_id).strip(),
                ticket_id=ticket_id,
                source="schedule",
                manager_address=manager_identity["manager_address"],
                manager_name=manager_identity["manager_name"],
                manager_party=manager_identity["manager_party"],
                schedule_id=str(schedule.get("id") or ""),
                workflow_id=str(managed.get("workflow_id") or "").strip(),
                title=str(managed.get("title") or schedule.get("name") or schedule.get("required_capability") or ticket_id).strip(),
                assigned_at=now,
            )
            updated_metadata["boss_schedule_id"] = str(schedule.get("id") or "")
            payload = {
                "required_capability": str(schedule.get("required_capability") or ""),
                "targets": list(schedule.get("targets") or []),
                "payload": schedule.get("payload"),
                "target_table": str(schedule.get("target_table") or ""),
                "source_url": str(schedule.get("source_url") or ""),
                "parse_rules": schedule.get("parse_rules"),
                "capability_tags": list(schedule.get("capability_tags") or []),
                "job_type": str(schedule.get("job_type") or "run"),
                "priority": int(schedule.get("priority") or 100),
                "premium": bool(schedule.get("premium")),
                "metadata": updated_metadata,
                "scheduled_for": now if force_now else str(schedule.get("scheduled_for") or ""),
                "max_attempts": int(schedule.get("max_attempts") or 3),
                "job_id": ticket_id,
            }
            next_attempt_count = int(schedule.get("issue_attempts") or 0) + 1
            try:
                result = self._use_manager_practice(
                    manager_identity["manager_address"],
                    "manager-submit-job",
                    payload,
                )
            except Exception as exc:
                failed = dict(schedule)
                failed["last_attempted_at"] = now
                failed["last_error"] = str(exc)
                failed["issue_attempts"] = next_attempt_count
                failed["updated_at"] = now
                self._save_managed_schedule_row(failed)
                raise

            job = self._normalize_managed_submission_job(payload, result if isinstance(result, Mapping) else None)
            issued = dict(schedule)
            repeat_frequency = DispatcherBossAgent._normalize_repeat_frequency(schedule.get("repeat_frequency"))
            issued["status"] = "issued" if repeat_frequency == "once" else "scheduled"
            issued["dispatcher_job_id"] = str(job.get("id") or ticket_id)
            issued["issued_at"] = now
            issued["last_attempted_at"] = now
            issued["last_error"] = ""
            issued["issue_attempts"] = next_attempt_count
            if repeat_frequency != "once":
                issued["scheduled_for"] = DispatcherBossAgent._compute_next_occurrence(
                    repeat_frequency=repeat_frequency,
                    timezone_name=str(schedule.get("schedule_timezone") or "UTC"),
                    schedule_times=list(schedule.get("schedule_times") or []),
                    weekdays=list(schedule.get("schedule_weekdays") or []),
                    days_of_month=list(schedule.get("schedule_days_of_month") or []),
                    after=datetime.now(timezone.utc),
                )
            issued["updated_at"] = now
            saved = self._save_managed_schedule_row(issued)
            return {
                "status": "success",
                "schedule": managed_schedule_from_row(
                    saved,
                    manager_address=manager_identity["manager_address"],
                    manager_name=manager_identity["manager_name"],
                    manager_party=manager_identity["manager_party"],
                ),
                "ticket": managed_ticket_from_job_row(
                    job,
                    manager_address=manager_identity["manager_address"],
                    manager_name=manager_identity["manager_name"],
                    manager_party=manager_identity["manager_party"],
                ),
                "manager": self._team_descriptor(manager_entry),
            }

    def delete_managed_schedule(self, schedule_id: str) -> dict[str, Any]:
        """Delete one saved managed schedule."""
        with self._schedule_issue_lock:
            schedule = self._get_managed_schedule_row(schedule_id)
            if str(schedule.get("status") or "").strip().lower() == "deleted":
                return {
                    "status": "success",
                    "schedule": managed_schedule_from_row(schedule, manager_address=str(schedule.get("dispatcher_address") or "")),
                }
            updated = dict(schedule)
            updated["status"] = "deleted"
            updated["updated_at"] = utcnow_iso()
            saved = self._save_managed_schedule_row(updated)
            return {
                "status": "success",
                "schedule": managed_schedule_from_row(saved, manager_address=str(saved.get("dispatcher_address") or "")),
            }

    def process_due_managed_schedules(self, *, limit: int = 20) -> dict[str, Any]:
        """Process due managed schedules and issue tickets through teamwork managers."""
        now = datetime.now(timezone.utc)
        due_rows = [
            row
            for row in self._load_managed_schedule_rows()
            if str(row.get("status") or "").strip().lower() == "scheduled"
            and parse_datetime_value(row.get("scheduled_for")) <= now
        ]
        due_rows.sort(
            key=lambda row: (
                parse_datetime_value(row.get("scheduled_for")),
                parse_datetime_value(row.get("created_at")),
                str(row.get("id") or ""),
            )
        )
        attempted = 0
        issued_count = 0
        schedules: list[dict[str, Any]] = []
        tickets: list[dict[str, Any]] = []
        for row in due_rows[: max(int(limit or 20), 1)]:
            attempted += 1
            try:
                result = self.issue_managed_schedule(str(row.get("id") or ""))
                if isinstance(result.get("schedule"), Mapping):
                    schedules.append(dict(result["schedule"]))
                if isinstance(result.get("ticket"), Mapping):
                    tickets.append(dict(result["ticket"]))
                issued_count += 1
            except Exception as exc:
                self.logger.exception("Failed issuing managed schedule %s: %s", row.get("id"), exc)
        return {
            "status": "success",
            "attempted": attempted,
            "issued_count": issued_count,
            "schedules": schedules,
            "tickets": tickets,
        }

    def list_managed_tickets(self, input_data: Mapping[str, Any]) -> dict[str, Any]:
        """List managed tickets from the selected teamwork manager."""
        manager_entry = self._resolve_manager_entry(input_data)
        manager_identity = self._manager_identity_from_entry(manager_entry)
        preview_limit = max(_safe_int(input_data.get("preview_limit"), 500), 50)
        jobs_preview = self._manager_preview_table(manager_identity["manager_address"], TABLE_JOBS, limit=preview_limit)
        latest_jobs = self._latest_rows(jobs_preview.get("rows") or [], key_field="id")
        normalized_status = str(input_data.get("status") or "").strip().lower()
        normalized_capability = str(input_data.get("capability") or "").strip().lower()
        normalized_search = str(input_data.get("search") or "").strip().lower()
        try:
            normalized_limit = max(1, min(int(input_data.get("limit") or 100), 200))
        except (TypeError, ValueError):
            normalized_limit = 100
        filtered_jobs: list[dict[str, Any]] = []
        for job in latest_jobs:
            status_text = str(job.get("status") or "").strip().lower()
            capability_name = str(job.get("required_capability") or "").strip().lower()
            searchable = " ".join(
                [
                    str(job.get("id") or ""),
                    str(job.get("required_capability") or ""),
                    str(job.get("claimed_by") or ""),
                    str(job.get("target_table") or ""),
                    str(job.get("source_url") or ""),
                    " ".join(job.get("targets") or []),
                ]
            ).lower()
            if normalized_status and status_text != normalized_status:
                continue
            if normalized_capability and normalized_capability not in capability_name:
                continue
            if normalized_search and normalized_search not in searchable:
                continue
            filtered_jobs.append(job)
        tickets = [
            managed_ticket_from_job_row(
                job,
                manager_address=manager_identity["manager_address"],
                manager_name=manager_identity["manager_name"],
                manager_party=manager_identity["manager_party"],
            )
            for job in filtered_jobs[:normalized_limit]
        ]
        return {
            "status": "success",
            "manager": self._team_descriptor(manager_entry),
            "count": len(filtered_jobs),
            "tickets": tickets,
        }

    def get_managed_ticket(self, ticket_id: str, input_data: Mapping[str, Any]) -> dict[str, Any]:
        """Return one managed ticket detail from the selected teamwork manager."""
        manager_entry = self._resolve_manager_entry(input_data)
        manager_identity = self._manager_identity_from_entry(manager_entry)
        jobs_preview = self._manager_preview_table(manager_identity["manager_address"], TABLE_JOBS, limit=500)
        latest_jobs = self._latest_rows(jobs_preview.get("rows") or [], key_field="id")
        normalized_ticket_id = str(ticket_id or "").strip()
        match = next((job for job in latest_jobs if str(job.get("id") or "").strip() == normalized_ticket_id), None)
        if match is None:
            raise LookupError(f"Managed ticket '{normalized_ticket_id}' was not found.")
        return {
            "status": "success",
            "manager": self._team_descriptor(manager_entry),
            "ticket": managed_ticket_from_job_row(
                match,
                manager_address=manager_identity["manager_address"],
                manager_name=manager_identity["manager_name"],
                manager_party=manager_identity["manager_party"],
            ),
        }

    def get_managed_schedule_history(self, schedule_id: str, input_data: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Return managed ticket history for one saved schedule."""
        schedule = self._get_managed_schedule_row(schedule_id)
        metadata = _coerce_object(schedule.get("metadata"))
        managed = _coerce_object(metadata.get("managed_work"))
        manager_assignment = _coerce_object(managed.get("manager_assignment"))
        manager_identity = self._manager_identity_from_entry(
            self._manager_entry_from_identity(
                {
                    "manager_address": str(schedule.get("dispatcher_address") or ""),
                    "manager_name": str(manager_assignment.get("manager_name") or "Manager").strip() or "Manager",
                    "manager_party": str(manager_assignment.get("manager_party") or "").strip(),
                }
            )
        )
        try:
            normalized_limit = max(1, min(int((input_data or {}).get("limit") or 20), 100))
        except (TypeError, ValueError):
            normalized_limit = 20
        jobs_preview = self._manager_preview_table(manager_identity["manager_address"], TABLE_JOBS, limit=500)
        latest_jobs = self._latest_rows(jobs_preview.get("rows") or [], key_field="id")
        filtered = []
        for job in latest_jobs:
            metadata = _coerce_object(job.get("metadata"))
            managed = _coerce_object(metadata.get("managed_work"))
            if str(managed.get("schedule_id") or metadata.get("boss_schedule_id") or "").strip() == str(schedule_id or "").strip():
                filtered.append(job)
        filtered.sort(
            key=lambda row: (
                parse_datetime_value(row.get("updated_at") or row.get("created_at")),
                parse_datetime_value(row.get("created_at")),
                str(row.get("id") or ""),
            ),
            reverse=True,
        )
        return {
            "status": "success",
            "schedule": managed_schedule_from_row(
                schedule,
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
                for row in filtered[:normalized_limit]
            ],
            "count": len(filtered),
            "limit": normalized_limit,
        }

    def monitor_managed_work(self, input_data: Mapping[str, Any]) -> dict[str, Any]:
        """Return the BossPulser managed-work monitor payload for UI consumers."""
        manager_entry = self._resolve_manager_entry(input_data)
        manager_identity = self._manager_identity_from_entry(manager_entry)
        team_status = self._handle_team_status(dict(input_data or {}))
        tickets = self.list_managed_tickets(
            {
                **dict(input_data or {}),
                "manager_address": manager_identity["manager_address"],
                "party": manager_identity["manager_party"] or self.default_party,
                "limit": input_data.get("ticket_limit") if isinstance(input_data, Mapping) else 20,
            }
        )
        schedules = self.list_managed_schedules({"manager_address": manager_identity["manager_address"], "limit": input_data.get("schedule_limit") if isinstance(input_data, Mapping) else 20})
        managed_work = build_managed_work_monitor(
            manager_assignment=manager_identity,
            summary=team_status,
            workers=team_status.get("workers", {}).get("roster", []) if isinstance(team_status.get("workers"), Mapping) else [],
            tickets=tickets.get("tickets", []),
            schedules=schedules.get("schedules", []),
            captured_at=str(team_status.get("captured_at") or ""),
        )
        return {
            "status": "success",
            "api_version": managed_work.get("api_version"),
            "manager_assignment": manager_identity,
            "manager": self._team_descriptor(manager_entry),
            "summary": {
                "jobs": team_status.get("jobs", {}),
                "workers": team_status.get("workers", {}),
            },
            "workers": managed_work.get("workers", []),
            "tickets": managed_work.get("tickets", []),
            "schedules": managed_work.get("schedules", []),
            "counts": managed_work.get("counts", {}),
            "captured_at": managed_work.get("captured_at", datetime.now(timezone.utc).isoformat()),
            "managed_work": managed_work,
        }

    def _handle_monitor_managed_work(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to handle managed-work monitor payloads."""
        return self.monitor_managed_work(input_data)

    def _setup_routes(self) -> None:
        """Internal helper to set up the routes."""
        def render_page(request: Request):
            """Render the page."""
            context = self._ui_context()
            context["request"] = request
            return self.templates.TemplateResponse(request, "index.html", context)

        @self.app.get("/", include_in_schema=False)
        async def boss_pulser_home(request: Request):
            """Route handler for GET /."""
            return render_page(request)

        @self.app.get("/api/context")
        async def boss_pulser_context():
            """Route handler for GET /api/context."""
            return self._ui_initial_payload()

        @self.app.get("/api/teams")
        async def boss_pulser_teams(party: str = "", name: str = "", include_workers: bool = True):
            """Route handler for GET /api/teams."""
            try:
                return await run_in_threadpool(
                    self._handle_discover_teams,
                    {
                        "party": party or self.default_party,
                        "name": name,
                        "include_workers": include_workers,
                    },
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/jobcaps")
        async def boss_pulser_jobcaps(party: str = "", manager_address: str = "", manager_name: str = ""):
            """Route handler for GET /api/jobcaps."""
            try:
                return await run_in_threadpool(
                    self._handle_supported_jobcaps,
                    {
                        "party": party or self.default_party,
                        "manager_address": manager_address,
                        "manager_name": manager_name,
                    },
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/provision/catalog")
        async def boss_pulser_provision_catalog(party: str = "", manager_name: str = ""):
            """Route handler for GET /api/provision/catalog."""
            try:
                return await run_in_threadpool(
                    self._handle_provision_catalog,
                    {
                        "party": party or self.default_party,
                        "manager_name": manager_name,
                    },
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/status")
        async def boss_pulser_status(manager_address: str = "", party: str = "", preview_limit: int = 500):
            """Route handler for GET /api/status."""
            try:
                return await run_in_threadpool(
                    self._handle_team_status,
                    {
                        "manager_address": manager_address,
                        "party": party or self.default_party,
                        "preview_limit": preview_limit,
                    },
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/history")
        async def boss_pulser_history(manager_address: str = "", party: str = "", limit: int = 20):
            """Route handler for GET /api/history."""
            try:
                return await run_in_threadpool(
                    self._handle_team_history,
                    {
                        "manager_address": manager_address,
                        "party": party or self.default_party,
                        "limit": limit,
                    },
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/jobs")
        async def boss_pulser_submit_job(payload: Dict[str, Any]):
            """Route handler for POST /api/jobs."""
            try:
                return await run_in_threadpool(self._handle_submit_team_job, dict(payload or {}))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/provision/team")
        async def boss_pulser_create_team(payload: Dict[str, Any]):
            """Route handler for POST /api/provision/team."""
            try:
                return await run_in_threadpool(self._handle_create_team, dict(payload or {}))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/provision/manager")
        async def boss_pulser_create_manager(payload: Dict[str, Any]):
            """Route handler for POST /api/provision/manager."""
            try:
                return await run_in_threadpool(self._handle_create_manager, dict(payload or {}))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/provision/connect-manager")
        async def boss_pulser_connect_manager(payload: Dict[str, Any]):
            """Route handler for POST /api/provision/connect-manager."""
            try:
                return await run_in_threadpool(self._handle_connect_manager, dict(payload or {}))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/provision/worker")
        async def boss_pulser_create_worker(payload: Dict[str, Any]):
            """Route handler for POST /api/provision/worker."""
            try:
                return await run_in_threadpool(self._handle_create_worker, dict(payload or {}))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/team-actions/add-manager")
        async def boss_pulser_add_team_manager(payload: Dict[str, Any]):
            """Route handler for POST /api/team-actions/add-manager."""
            try:
                return await run_in_threadpool(self._handle_add_team_manager, dict(payload or {}))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/team-actions/hire-worker")
        async def boss_pulser_hire_team_worker(payload: Dict[str, Any]):
            """Route handler for POST /api/team-actions/hire-worker."""
            try:
                return await run_in_threadpool(self._handle_hire_team_worker, dict(payload or {}))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/team-actions/create-local-worker")
        async def boss_pulser_create_local_team_worker(payload: Dict[str, Any]):
            """Route handler for POST /api/team-actions/create-local-worker."""
            try:
                return await run_in_threadpool(self._handle_create_local_team_worker, dict(payload or {}))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/managed-work/monitor")
        async def boss_pulser_managed_work_monitor(
            manager_address: str = "",
            party: str = "",
            preview_limit: int = 500,
            ticket_limit: int = 20,
            schedule_limit: int = 20,
        ):
            """Route handler for GET /api/managed-work/monitor."""
            try:
                return await run_in_threadpool(
                    self.monitor_managed_work,
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

        @self.app.get("/api/managed-work/tickets")
        async def boss_pulser_managed_work_tickets(
            manager_address: str = "",
            party: str = "",
            status: str = "",
            capability: str = "",
            search: str = "",
            limit: int = 100,
            preview_limit: int = 500,
        ):
            """Route handler for GET /api/managed-work/tickets."""
            try:
                return await run_in_threadpool(
                    self.list_managed_tickets,
                    {
                        "manager_address": manager_address,
                        "party": party or self.default_party,
                        "status": status,
                        "capability": capability,
                        "search": search,
                        "limit": limit,
                        "preview_limit": preview_limit,
                    },
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/managed-work/tickets")
        async def boss_pulser_create_managed_ticket(payload: ManagedTicketRequest):
            """Route handler for POST /api/managed-work/tickets."""
            try:
                return await run_in_threadpool(self.create_managed_ticket, payload.model_dump(mode="python"))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/managed-work/tickets/{ticket_id}")
        async def boss_pulser_managed_ticket_detail(ticket_id: str, manager_address: str = "", party: str = ""):
            """Route handler for GET /api/managed-work/tickets/{ticket_id}."""
            try:
                return await run_in_threadpool(
                    self.get_managed_ticket,
                    ticket_id,
                    {
                        "manager_address": manager_address,
                        "party": party or self.default_party,
                    },
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/managed-work/schedules")
        async def boss_pulser_managed_work_schedules(
            manager_address: str = "",
            status: str = "",
            search: str = "",
            limit: int = 100,
        ):
            """Route handler for GET /api/managed-work/schedules."""
            try:
                return await run_in_threadpool(
                    self.list_managed_schedules,
                    {
                        "manager_address": manager_address,
                        "status": status,
                        "search": search,
                        "limit": limit,
                    },
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/managed-work/schedules")
        async def boss_pulser_create_managed_schedule(payload: ManagedScheduleRequest):
            """Route handler for POST /api/managed-work/schedules."""
            try:
                return await run_in_threadpool(self.create_managed_schedule, payload.model_dump(mode="python"))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.get("/api/managed-work/schedules/{schedule_id}/history")
        async def boss_pulser_managed_schedule_history(schedule_id: str, limit: int = 20):
            """Route handler for GET /api/managed-work/schedules/{schedule_id}/history."""
            try:
                return await run_in_threadpool(
                    self.get_managed_schedule_history,
                    schedule_id,
                    {"limit": limit},
                )
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @self.app.post("/api/managed-work/schedules/{schedule_id}/control")
        async def boss_pulser_managed_schedule_control(schedule_id: str, payload: Dict[str, Any]):
            """Route handler for POST /api/managed-work/schedules/{schedule_id}/control."""
            action = str((payload or {}).get("action") or "").strip().lower()
            try:
                if action == "issue":
                    result = await run_in_threadpool(self.issue_managed_schedule, schedule_id, force_now=True)
                elif action == "delete":
                    result = await run_in_threadpool(self.delete_managed_schedule, schedule_id)
                else:
                    raise HTTPException(status_code=400, detail="action must be one of: issue, delete.")
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {"status": "success", "control": result}

    def _discover_managers(self, *, party: str, name: str = "") -> list[dict[str, Any]]:
        """Internal helper to discover the managers."""
        seen: dict[str, dict[str, Any]] = {}
        for role in ("manager", "dispatcher"):
            params: dict[str, Any] = {"pit_type": "Agent", "party": party, "role": role}
            if str(name or "").strip():
                params["name"] = str(name).strip()
            for entry in self._search_entries(**params):
                address = self._entry_address(entry)
                if not address:
                    continue
                current = seen.get(address)
                if current is None or self._entry_last_active(entry) > self._entry_last_active(current):
                    seen[address] = entry
        return sorted(seen.values(), key=self._entry_last_active, reverse=True)

    def _discover_hireable_managers(self, *, party: str, name: str = "") -> list[dict[str, Any]]:
        """Internal helper to discover ManagerPulsers that can join a team."""
        seen: dict[str, dict[str, Any]] = {}
        for pit_type in ("Pulser", "Agent"):
            params: dict[str, Any] = {"pit_type": pit_type, "party": party, "role": "manager_pulser"}
            if str(name or "").strip():
                params["name"] = str(name).strip()
            for entry in self._search_entries(**params):
                address = self._entry_address(entry)
                if not address:
                    continue
                if "join_team" not in {pulse_name.strip().lower() for pulse_name in self._supported_pulse_names(entry)}:
                    continue
                if not self._manager_pulser_is_reachable(address):
                    continue
                current = seen.get(address)
                if current is None or self._entry_last_active(entry) > self._entry_last_active(current):
                    seen[address] = entry
        return sorted(seen.values(), key=self._entry_last_active, reverse=True)

    @staticmethod
    def _manager_pulser_is_reachable(address: str) -> bool:
        """Return whether one ManagerPulser currently answers on its advertised address."""
        normalized = _normalize_url(address)
        if not normalized:
            return False
        try:
            response = requests.get(f"{normalized}/api/context", timeout=1.0)
        except requests.RequestException:
            return False
        return int(response.status_code or 0) == 200

    @staticmethod
    def _worker_is_reachable(address: str) -> bool:
        """Return whether one teamwork worker currently answers on its advertised address."""
        return BossPulser._manager_pulser_is_reachable(address)

    def _worker_can_be_hired(self, entry: Mapping[str, Any]) -> bool:
        """Return whether one worker exposes the teamwork hire practice."""
        practices = self._entry_card(entry).get("practices")
        if not isinstance(practices, list):
            return False
        for practice in practices:
            if not isinstance(practice, Mapping):
                continue
            if str(practice.get("id") or "").strip().lower() == "worker-hire-manager":
                return True
        return False

    def _worker_is_available_for_hire(self, entry: Mapping[str, Any]) -> bool:
        """Return whether one worker is still awaiting manager assignment."""
        meta = self._entry_meta(entry)
        assignment = meta.get("manager_assignment") if isinstance(meta.get("manager_assignment"), Mapping) else {}
        if str(assignment.get("manager_address") or meta.get("manager_address") or meta.get("dispatcher_address") or "").strip():
            return False
        status = str(assignment.get("status") or "").strip().lower()
        if not status:
            return True
        return status in {"awaiting_hire", "available", "unassigned"}

    def _worker_supports_capabilities(self, entry: Mapping[str, Any], capability_names: Iterable[str]) -> bool:
        """Return whether one worker matches at least one requested capability."""
        requested = normalize_capabilities(capability_names or [])
        if not requested:
            return True
        card = self._entry_card(entry)
        meta = self._entry_meta(entry)
        advertised = set(
            normalize_capabilities(
                meta.get("capabilities") or entry.get("capabilities") or card.get("capabilities") or []
            )
        )
        if "*" in advertised:
            return True
        job_capabilities = _normalize_job_cap_entries(meta.get("job_capabilities") or card.get("job_capabilities"))
        advertised_job_caps = {
            str(item.get("name") or "").strip().lower()
            for item in job_capabilities
            if str(item.get("name") or "").strip()
        }
        return any(capability in advertised or capability in advertised_job_caps for capability in requested)

    def _discover_hireable_workers(
        self,
        *,
        party: str,
        name: str = "",
        capabilities: Iterable[str] = (),
    ) -> list[dict[str, Any]]:
        """Return teamwork workers that are available for manager hire."""
        seen: dict[str, dict[str, Any]] = {}
        for entry in self._discover_workers(party=party, name=name):
            address = self._entry_address(entry)
            if not address:
                continue
            if not self._worker_can_be_hired(entry):
                continue
            if not self._worker_is_available_for_hire(entry):
                continue
            if not self._worker_supports_capabilities(entry, capabilities):
                continue
            if not self._worker_is_reachable(address):
                continue
            current = seen.get(address)
            if current is None or self._entry_last_active(entry) > self._entry_last_active(current):
                seen[address] = entry
        return sorted(seen.values(), key=self._entry_last_active, reverse=True)

    @staticmethod
    def _worker_is_reachable(address: str) -> bool:
        """Return whether one teamwork worker currently answers on its advertised address."""
        return BossPulser._manager_pulser_is_reachable(address)

    def _worker_can_be_hired(self, entry: Mapping[str, Any]) -> bool:
        """Return whether one worker advertises the teamwork hire practice."""
        card = self._entry_card(entry)
        practices = card.get("practices") if isinstance(card.get("practices"), list) else []
        for practice in practices:
            if not isinstance(practice, Mapping):
                continue
            if str(practice.get("id") or "").strip().lower() == "worker-hire-manager":
                return True
        return False

    def _worker_is_available_for_hire(self, entry: Mapping[str, Any]) -> bool:
        """Return whether one worker is still awaiting manager assignment."""
        meta = self._entry_meta(entry)
        assignment = meta.get("manager_assignment") if isinstance(meta.get("manager_assignment"), Mapping) else {}
        if str(assignment.get("manager_address") or meta.get("manager_address") or meta.get("dispatcher_address") or "").strip():
            return False
        status = str(assignment.get("status") or "").strip().lower()
        if not status:
            return True
        return status in {"awaiting_hire", "available", "unassigned"}

    def _worker_supports_capabilities(self, entry: Mapping[str, Any], capability_names: Iterable[str]) -> bool:
        """Return whether one worker matches at least one requested capability."""
        requested = normalize_capabilities(capability_names or [])
        if not requested:
            return True
        card = self._entry_card(entry)
        meta = self._entry_meta(entry)
        advertised = set(
            normalize_capabilities(
                meta.get("capabilities") or entry.get("capabilities") or card.get("capabilities") or []
            )
        )
        if "*" in advertised:
            return True
        job_caps = _normalize_job_cap_entries(meta.get("job_capabilities") or card.get("job_capabilities"))
        job_cap_names = {str(item.get("name") or "").strip().lower() for item in job_caps if str(item.get("name") or "").strip()}
        return any(capability in advertised or capability in job_cap_names for capability in requested)

    def _discover_hireable_workers(
        self,
        *,
        party: str,
        name: str = "",
        capabilities: Iterable[str] = (),
    ) -> list[dict[str, Any]]:
        """Return available teamwork workers that can be hired by a manager."""
        seen: dict[str, dict[str, Any]] = {}
        for entry in self._discover_workers(party=party, name=name):
            address = self._entry_address(entry)
            if not address:
                continue
            if not self._worker_can_be_hired(entry):
                continue
            if not self._worker_is_available_for_hire(entry):
                continue
            if not self._worker_supports_capabilities(entry, capabilities):
                continue
            if not self._worker_is_reachable(address):
                continue
            current = seen.get(address)
            if current is None or self._entry_last_active(entry) > self._entry_last_active(current):
                seen[address] = entry
        return sorted(seen.values(), key=self._entry_last_active, reverse=True)

    def _discover_workers(self, *, party: str, name: str = "") -> list[dict[str, Any]]:
        """Internal helper to discover the workers."""
        params: dict[str, Any] = {"pit_type": "Agent", "party": party, "role": "worker"}
        if str(name or "").strip():
            params["name"] = str(name).strip()
        return sorted(self._search_entries(**params), key=self._entry_last_active, reverse=True)

    def _resolve_manager_entry(self, input_data: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to resolve the manager entry."""
        explicit_address = str(input_data.get("manager_address") or "").strip().rstrip("/")
        if explicit_address:
            return {"address": explicit_address, "card": {"address": explicit_address}}

        party = self._party_from_input(input_data)
        name = str(input_data.get("manager_name") or input_data.get("team_name") or input_data.get("name") or "").strip()
        candidates = self._discover_managers(party=party, name=name)
        if candidates:
            return candidates[0]
        raise ValueError(f"No teamwork manager was discovered for party '{party}'.")

    def _use_manager_practice(self, manager_address: str, practice_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper to use the manager practice."""
        try:
            response = self.UsePractice(practice_id, dict(payload or {}), pit_address=manager_address)
        except Exception:
            if practice_id.startswith("manager-"):
                fallback_id = f"dispatcher-{practice_id[len('manager-'):]}"
                response = self.UsePractice(fallback_id, dict(payload or {}), pit_address=manager_address)
            else:
                raise
        return dict(response or {}) if isinstance(response, Mapping) else {}

    @staticmethod
    def _latest_rows(
        rows: Iterable[Mapping[str, Any]],
        *,
        key_field: str,
        alternate_keys: Iterable[str] = (),
        time_fields: Iterable[str] = ("updated_at", "last_seen_at", "completed_at", "created_at"),
    ) -> list[dict[str, Any]]:
        """Internal helper to return the latest rows."""
        latest_by_id: dict[str, tuple[datetime, int, dict[str, Any]]] = {}
        for index, row in enumerate(rows or []):
            if not isinstance(row, Mapping):
                continue
            normalized = dict(row)
            key = str(normalized.get(key_field) or "").strip()
            if not key:
                for alternate in alternate_keys:
                    key = str(normalized.get(alternate) or "").strip()
                    if key:
                        break
            if not key:
                continue
            timestamps = [parse_datetime_value(normalized.get(field)) for field in time_fields]
            timestamp = max(timestamps) if timestamps else datetime.min.replace(tzinfo=timezone.utc)
            current = latest_by_id.get(key)
            if current is None or (timestamp, index) >= (current[0], current[1]):
                latest_by_id[key] = (timestamp, index, normalized)
        return [item[2] for item in sorted(latest_by_id.values(), key=lambda value: (value[0], value[1]), reverse=True)]

    def _monitor_worker_health(self, worker: Mapping[str, Any]) -> dict[str, Any]:
        """Internal helper for monitor worker health."""
        normalized = dict(worker or {})
        metadata = dict(normalized.get("metadata") or {}) if isinstance(normalized.get("metadata"), Mapping) else {}
        heartbeat = dict(metadata.get("heartbeat") or {}) if isinstance(metadata.get("heartbeat"), Mapping) else {}
        raw_status = str(normalized.get("status") or "").strip().lower()
        last_seen_text = str(
            normalized.get("last_seen_at")
            or normalized.get("updated_at")
            or heartbeat.get("captured_at")
            or ""
        ).strip()
        now_value = datetime.now(timezone.utc)
        last_seen_at = parse_datetime_value(last_seen_text)
        heartbeat_age_sec = None
        if last_seen_at != datetime.min.replace(tzinfo=timezone.utc):
            heartbeat_age_sec = max((now_value - last_seen_at).total_seconds(), 0.0)

        heartbeat_interval_sec = max(
            float(heartbeat.get("heartbeat_interval_sec") or WORKER_HEARTBEAT_INTERVAL_SEC),
            1.0,
        )
        online_threshold_sec = max(heartbeat_interval_sec * 2.5, heartbeat_interval_sec + 5.0)
        stale_threshold_sec = max(float(WORKER_JOB_TIMEOUT_SEC), online_threshold_sec + heartbeat_interval_sec)

        if raw_status in {"offline", "stopped", "error"}:
            health_status = "offline"
        elif heartbeat_age_sec is None:
            health_status = "offline"
        elif heartbeat_age_sec <= online_threshold_sec:
            health_status = "online"
        elif heartbeat_age_sec < stale_threshold_sec:
            health_status = "stale"
        else:
            health_status = "offline"

        normalized["heartbeat_age_sec"] = heartbeat_age_sec
        normalized["heartbeat_interval_sec"] = heartbeat_interval_sec
        normalized["health_status"] = health_status
        return normalized

    def _manager_preview_table(self, manager_address: str, table_name: str, *, limit: int) -> dict[str, Any]:
        """Internal helper to return the manager preview table."""
        return self._use_manager_practice(
            manager_address,
            "manager-db-preview-table",
            {"table_name": table_name, "limit": max(_safe_int(limit, 100), 1), "offset": 0},
        )

    def _team_descriptor(
        self,
        manager_entry: Mapping[str, Any],
        workers: Iterable[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Internal helper for team descriptor."""
        card = self._entry_card(manager_entry)
        meta = self._entry_meta(manager_entry)
        manager_address = self._entry_address(manager_entry)
        manager_name = self._entry_name(manager_entry) or "Manager"
        party = str(card.get("party") or meta.get("party") or self.default_party or DEFAULT_TEAMWORK_PARTY).strip()
        discovered_workers = [dict(worker) for worker in (workers or []) if isinstance(worker, Mapping)]
        worker_summaries = []
        for worker in discovered_workers:
            worker_card = self._entry_card(worker)
            worker_meta = self._entry_meta(worker)
            worker_summaries.append(
                {
                    "name": self._entry_name(worker),
                    "address": self._entry_address(worker),
                    "capabilities": normalize_capabilities(
                        worker_meta.get("capabilities") or worker.get("capabilities") or worker_card.get("capabilities") or []
                    ),
                    "job_capabilities": [
                        _normalize_job_cap_entry(entry)
                        for entry in _coerce_list(worker_meta.get("job_capabilities") or worker_card.get("job_capabilities"))
                        if _normalize_job_cap_entry(entry)
                    ],
                }
            )
        return {
            "party": party,
            "manager_name": manager_name,
            "manager_address": manager_address,
            "role": str(card.get("role") or manager_entry.get("role") or "manager"),
            "description": str(card.get("description") or manager_entry.get("description") or "").strip(),
            "job_capabilities": [
                _normalize_job_cap_entry(entry)
                for entry in _coerce_list(meta.get("job_capabilities") or card.get("job_capabilities"))
                if _normalize_job_cap_entry(entry)
            ],
            "workers": worker_summaries,
            "worker_count": len(worker_summaries),
        }

    def _hireable_manager_descriptor(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        """Build the stable hireable-manager descriptor for the Boss UI."""
        card = self._entry_card(entry)
        meta = self._entry_meta(entry)
        supported_pulses = self._supported_pulse_names(entry)
        return {
            "name": self._entry_name(entry) or "ManagerPulser",
            "pulser_address": self._entry_address(entry),
            "party": str(card.get("party") or meta.get("party") or self.default_party or DEFAULT_TEAMWORK_PARTY).strip(),
            "role": str(card.get("role") or entry.get("role") or "manager_pulser").strip() or "manager_pulser",
            "description": str(card.get("description") or entry.get("description") or "").strip(),
            "manager_address": str(meta.get("manager_address") or meta.get("dispatcher_address") or "").strip().rstrip("/"),
            "supported_pulses": supported_pulses,
            "last_active": self._entry_last_active(entry),
            "hire_ready": "join_team" in {name.strip().lower() for name in supported_pulses},
        }

    def _hireable_worker_descriptor(self, entry: Mapping[str, Any]) -> dict[str, Any]:
        """Build the stable hireable-worker descriptor for the Boss UI."""
        card = self._entry_card(entry)
        meta = self._entry_meta(entry)
        assignment = meta.get("manager_assignment") if isinstance(meta.get("manager_assignment"), Mapping) else {}
        capabilities = normalize_capabilities(
            meta.get("capabilities") or entry.get("capabilities") or card.get("capabilities") or []
        )
        job_capabilities = _normalize_job_cap_entries(meta.get("job_capabilities") or card.get("job_capabilities"))
        return {
            "name": self._entry_name(entry) or "Worker",
            "worker_address": self._entry_address(entry),
            "party": str(card.get("party") or meta.get("party") or self.default_party or DEFAULT_TEAMWORK_PARTY).strip(),
            "role": str(card.get("role") or entry.get("role") or "worker").strip() or "worker",
            "description": str(card.get("description") or entry.get("description") or "").strip(),
            "capabilities": capabilities,
            "job_capabilities": job_capabilities,
            "hire_ready": self._worker_can_be_hired(entry) and self._worker_is_available_for_hire(entry),
            "assignment_status": str(assignment.get("status") or "").strip().lower() or "available",
            "last_active": self._entry_last_active(entry),
        }

    def _handle_provision_catalog(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Return a Boss UI provisioning catalog with jobcaps and hireable managers."""
        party = self._party_from_input(input_data)
        manager_name = str(input_data.get("manager_name") or "").strip()
        jobcaps_payload = self._handle_supported_jobcaps({"party": party})
        hireable_managers = [
            self._hireable_manager_descriptor(entry)
            for entry in self._discover_hireable_managers(party=party, name=manager_name)
        ]
        hireable_workers = [
            self._hireable_worker_descriptor(entry)
            for entry in self._discover_hireable_workers(party=party)
        ]
        return {
            "status": "success",
            "party": party,
            "job_capabilities": list(jobcaps_payload.get("job_capabilities") or []),
            "managers_for_hire": hireable_managers,
            "workers_for_hire": hireable_workers,
            "counts": {
                "job_capabilities": len(jobcaps_payload.get("job_capabilities") or []),
                "managers_for_hire": len(hireable_managers),
                "workers_for_hire": len(hireable_workers),
            },
            "captured_at": utcnow_iso(),
        }

    @staticmethod
    def _normalize_manager_hire_requests(input_data: Mapping[str, Any], *, team_manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
        """Normalize selected manager-hire requests from the team-creation payload."""
        worker_defaults = _coerce_object(team_manifest.get("worker_defaults"))
        default_worker_count = max(_safe_int(input_data.get("hire_worker_count"), _safe_int(worker_defaults.get("count"), 1)), 0)
        default_worker_name_prefix = str(
            input_data.get("hire_worker_name_prefix")
            or worker_defaults.get("name_prefix")
            or "TeamWorker"
        ).strip() or "TeamWorker"
        default_worker_base_port = _safe_int(
            input_data.get("hire_worker_base_port"),
            _safe_int(worker_defaults.get("base_port"), 8271),
        )
        normalized: list[dict[str, Any]] = []
        raw_items = (
            _coerce_list(input_data.get("manager_hires"))
            or _coerce_list(input_data.get("hire_managers"))
            or _coerce_list(input_data.get("hire_manager_addresses"))
            or _coerce_list(input_data.get("manager_pulser_addresses"))
        )
        for index, raw_item in enumerate(raw_items):
            if isinstance(raw_item, Mapping):
                pulser_address = _normalize_url(raw_item.get("pulser_address") or raw_item.get("address"))
                pulser_name = str(raw_item.get("name") or raw_item.get("pulser_name") or "").strip()
                manager_name = str(raw_item.get("manager_name") or pulser_name).strip()
                worker_name_prefix = str(
                    raw_item.get("worker_name_prefix") or default_worker_name_prefix
                ).strip() or default_worker_name_prefix
                normalized_item = {
                    "pulser_address": pulser_address,
                    "pulser_name": pulser_name,
                    "manager_name": manager_name,
                    "worker_count": max(_safe_int(raw_item.get("worker_count"), default_worker_count), 0),
                    "worker_name_prefix": worker_name_prefix,
                    "worker_base_port": _safe_int(raw_item.get("worker_base_port"), default_worker_base_port),
                }
            else:
                normalized_item = {
                    "pulser_address": _normalize_url(raw_item),
                    "pulser_name": "",
                    "manager_name": "",
                    "worker_count": default_worker_count,
                    "worker_name_prefix": default_worker_name_prefix,
                    "worker_base_port": default_worker_base_port,
                }
            if not normalized_item["pulser_address"]:
                continue
            normalized_item["selection_index"] = index
            normalized.append(normalized_item)
        return normalized

    def _start_manager_hire(
        self,
        *,
        hire_request: Mapping[str, Any],
        team_manifest: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Issue one live ManagerPulser join-team request."""
        pulser_address = _normalize_url(hire_request.get("pulser_address"))
        if not pulser_address:
            raise ValueError("pulser_address is required to hire a manager.")
        params = {
            "team_manifest": _safe_json_copy(team_manifest),
            "worker_count": max(_safe_int(hire_request.get("worker_count"), 0), 0),
            "worker_name_prefix": str(hire_request.get("worker_name_prefix") or "").strip(),
            "worker_base_port": _safe_int(hire_request.get("worker_base_port"), 8271),
        }
        manager_name = str(hire_request.get("manager_name") or "").strip()
        if manager_name:
            params["manager_name"] = manager_name
        result = self.UsePractice(
            "get_pulse_data",
            {"pulse_name": "join_team", "params": params},
            pit_address=pulser_address,
        )
        payload = dict(result or {}) if isinstance(result, Mapping) else {}
        membership = _coerce_object(payload.get("team_membership"))
        joined = str(membership.get("status") or "").strip().lower() == "joined"
        return {
            "status": "joined" if joined else str(payload.get("status") or "pending").strip().lower() or "pending",
            "pulser_address": pulser_address,
            "pulser_name": str(hire_request.get("pulser_name") or "").strip(),
            "manager_address": str(payload.get("manager_address") or membership.get("manager_address") or "").strip(),
            "manager_name": str(membership.get("manager_name") or payload.get("manager_name") or manager_name).strip(),
            "local_worker_count": int(membership.get("local_worker_count") or len(payload.get("worker_configs") or [])),
            "team_membership": membership,
            "result": payload,
        }

    def _handle_add_team_manager(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Add one or more ManagerPulsers to the selected team manifest."""
        team_manifest = _coerce_object(input_data.get("team_manifest"))
        if not team_manifest:
            raise ValueError("team_manifest is required to add a manager.")
        manager_hires = self._normalize_manager_hire_requests(input_data, team_manifest=team_manifest)
        if not manager_hires:
            raise ValueError("Select at least one manager to add.")
        results: list[dict[str, Any]] = []
        warnings: list[str] = []
        primary_manager_address = ""
        for request in manager_hires:
            try:
                result = self._start_manager_hire(hire_request=request, team_manifest=team_manifest)
            except Exception as exc:
                result = {
                    "status": "failed",
                    "pulser_address": str(request.get("pulser_address") or "").strip(),
                    "pulser_name": str(request.get("pulser_name") or "").strip(),
                    "manager_address": "",
                    "manager_name": str(request.get("manager_name") or "").strip(),
                    "local_worker_count": max(_safe_int(request.get("worker_count"), 0), 0),
                    "error": str(exc),
                }
            results.append(result)
            if result.get("status") == "joined" and not primary_manager_address:
                primary_manager_address = str(result.get("manager_address") or "").strip()
            if str(result.get("error") or "").strip():
                warnings.append(str(result.get("error") or "").strip())
        return {
            "status": "success",
            "team_name": str(team_manifest.get("team_name") or input_data.get("team_name") or "Phemacast Team").strip(),
            "team_manifest": _safe_json_copy(team_manifest),
            "manager_hires": results,
            "primary_manager_address": primary_manager_address,
            "added": len([entry for entry in results if entry.get("status") == "joined"]),
            "warnings": warnings,
        }

    def _handle_hire_team_worker(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Assign one teamwork worker to the selected manager."""
        party = self._party_from_input(input_data)
        manager_address = _normalize_url(input_data.get("manager_address"))
        manager_name = str(input_data.get("manager_name") or "").strip()
        if not manager_address:
            manager_entry = self._resolve_manager_entry(input_data)
            manager_address = self._entry_address(manager_entry)
            manager_name = manager_name or self._entry_name(manager_entry) or "Manager"
        if not manager_address:
            raise ValueError("manager_address is required to hire a worker.")

        capability = str(input_data.get("capability") or input_data.get("required_capability") or "").strip().lower()
        worker_address = _normalize_url(input_data.get("worker_address"))
        worker_name = str(input_data.get("worker_name") or "").strip()
        if not worker_address:
            capability_filters = [capability] if capability else normalize_capabilities(input_data.get("capabilities") or [])
            candidates = self._discover_hireable_workers(
                party=party,
                name=worker_name,
                capabilities=capability_filters,
            )
            if not candidates:
                raise ValueError("No hireable worker matched the requested capability.")
            worker_address = self._entry_address(candidates[0])
        payload = {
            "manager_address": manager_address,
            "manager_name": manager_name or "Manager",
            "manager_party": party,
            "assignment_source": str(input_data.get("assignment_source") or "boss_team_hire").strip().lower() or "boss_team_hire",
        }
        result = self.UsePractice("worker-hire-manager", payload, pit_address=worker_address)
        normalized_result = dict(result or {}) if isinstance(result, Mapping) else {}
        normalized_result.setdefault("worker_address", worker_address)
        normalized_result.setdefault("manager_address", manager_address)
        normalized_result.setdefault("manager_name", manager_name or "Manager")
        return {
            "status": "success",
            "assignment": normalized_result,
        }

    def _handle_create_local_team_worker(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Ask one ManagerPulser to generate a local worker blueprint for its environment."""
        party = self._party_from_input(input_data)
        manager_pulser_address = _normalize_url(input_data.get("manager_pulser_address"))
        manager_address = _normalize_url(input_data.get("manager_address"))
        if not manager_pulser_address and manager_address:
            for entry in self._discover_hireable_managers(party=party):
                descriptor = self._hireable_manager_descriptor(entry)
                if _normalize_url(descriptor.get("manager_address")) == manager_address:
                    manager_pulser_address = _normalize_url(descriptor.get("pulser_address"))
                    break
        if not manager_pulser_address:
            raise ValueError("manager_pulser_address is required to create a local worker.")

        payload = {
            "team_name": str(input_data.get("team_name") or "Phemacast Team").strip(),
            "worker_name": str(input_data.get("worker_name") or "").strip(),
            "manager_address": manager_address,
            "capabilities": normalize_capabilities(input_data.get("capabilities") or []),
            "job_capabilities": _normalize_job_cap_entries(input_data.get("job_capabilities") or []),
        }
        worker_port = input_data.get("worker_port")
        if worker_port not in (None, "", 0):
            payload["worker_port"] = _safe_int(worker_port, 0)
        payload = {key: value for key, value in payload.items() if value not in ("", None, [], {})}
        result = self.UsePractice(
            "get_pulse_data",
            {"pulse_name": "create_local_worker", "params": payload},
            pit_address=manager_pulser_address,
        )
        normalized_result = dict(result or {}) if isinstance(result, Mapping) else {}
        normalized_result.setdefault("manager_pulser_address", manager_pulser_address)
        return {
            "status": "success",
            "worker": normalized_result,
        }

    def _build_team_manifest_payload(
        self,
        *,
        team_name: str,
        team_slug: str,
        party: str,
        plaza_url: str,
        boss_name: str,
        boss_host: str,
        boss_port: int,
        manager_name: str,
        manager_host: str,
        manager_port: int,
        manager_class: str,
        worker_prefix: str,
        worker_host: str,
        worker_base_port: int,
        worker_count: int,
        job_capabilities: list[dict[str, Any]],
        capabilities: list[str],
        monitor_refresh_sec: int,
        poll_interval_sec: int,
        boss_auto_register: bool,
        manager_auto_register: bool,
        worker_auto_register: bool,
    ) -> dict[str, Any]:
        """Build the stable BossPulser team manifest payload."""
        return {
            "api_version": TEAM_MANIFEST_VERSION,
            "team_name": team_name,
            "team_slug": team_slug,
            "party": party,
            "plaza_url": plaza_url,
            "job_capabilities": copy.deepcopy(job_capabilities),
            "capabilities": list(capabilities),
            "boss_defaults": {
                "name": boss_name,
                "host": boss_host,
                "port": boss_port,
                "type": DEFAULT_BOSS_CLASS,
                "monitor_refresh_sec": monitor_refresh_sec,
                "auto_register": boss_auto_register,
            },
            "manager_defaults": {
                "name": manager_name,
                "host": manager_host,
                "port": manager_port,
                "type": manager_class,
                "auto_register": manager_auto_register,
            },
            "worker_defaults": {
                "name_prefix": worker_prefix,
                "host": worker_host,
                "base_port": worker_base_port,
                "count": max(int(worker_count), 0),
                "capabilities": list(capabilities),
                "job_capabilities": copy.deepcopy(job_capabilities),
                "poll_interval_sec": poll_interval_sec,
                "auto_register": worker_auto_register,
            },
        }

    def _handle_create_team(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to handle the create team."""
        party = self._party_from_input(input_data)
        team_name = str(input_data.get("team_name") or "Phemacast Team").strip()
        team_slug = _slugify(input_data.get("team_slug") or team_name, fallback="phemacast-team")
        title_root = _titleify_slug(team_slug)
        plaza_url = str(input_data.get("plaza_url") or self.plaza_url or "").strip()
        storage_root = str(input_data.get("storage_root") or f"phemacast/teamwork/{team_slug}").strip().rstrip("/")

        boss_name = str(input_data.get("boss_name") or f"{title_root}Boss").strip()
        manager_name = str(input_data.get("manager_name") or f"{title_root}Manager").strip()
        worker_prefix = str(input_data.get("worker_name_prefix") or f"{title_root}Worker").strip()

        boss_host = str(input_data.get("boss_host") or "127.0.0.1").strip()
        manager_host = str(input_data.get("manager_host") or "127.0.0.1").strip()
        worker_host = str(input_data.get("worker_host") or "127.0.0.1").strip()
        boss_port = _safe_int(input_data.get("boss_port"), 8175)
        manager_port = _safe_int(input_data.get("manager_port"), 8170)
        worker_base_port = _safe_int(input_data.get("worker_base_port"), 8171)
        worker_count = max(_safe_int(input_data.get("worker_count"), 1), 1)
        manager_address = str(input_data.get("manager_address") or f"http://{manager_host}:{manager_port}").strip()

        job_capabilities = _normalize_job_cap_entries(
            input_data.get("job_capabilities") or input_data.get("supported_jobcaps") or []
        )
        default_capabilities = normalize_capabilities(
            input_data.get("capabilities") or [entry.get("name") for entry in job_capabilities if entry.get("name")]
        )
        job_options = _job_option_entries(job_capabilities)
        monitor_refresh_sec = _safe_int(input_data.get("monitor_refresh_sec"), 10)
        poll_interval_sec = _safe_int(input_data.get("poll_interval_sec"), 10)
        boss_auto_register = _safe_bool(input_data.get("boss_auto_register"), True)
        manager_auto_register = _safe_bool(input_data.get("manager_auto_register"), True)
        worker_auto_register = _safe_bool(input_data.get("worker_auto_register"), True)
        team_manifest = self._build_team_manifest_payload(
            team_name=team_name,
            team_slug=team_slug,
            party=party,
            plaza_url=plaza_url,
            boss_name=boss_name,
            boss_host=boss_host,
            boss_port=boss_port,
            manager_name=manager_name,
            manager_host=manager_host,
            manager_port=manager_port,
            manager_class=str(input_data.get("manager_class") or DEFAULT_MANAGER_CLASS).strip() or DEFAULT_MANAGER_CLASS,
            worker_prefix=worker_prefix,
            worker_host=worker_host,
            worker_base_port=worker_base_port,
            worker_count=worker_count,
            job_capabilities=job_capabilities,
            capabilities=default_capabilities,
            monitor_refresh_sec=monitor_refresh_sec,
            poll_interval_sec=poll_interval_sec,
            boss_auto_register=boss_auto_register,
            manager_auto_register=manager_auto_register,
            worker_auto_register=worker_auto_register,
        )
        manager_hire_requests = self._normalize_manager_hire_requests(input_data, team_manifest=team_manifest)
        require_manager_hire = _safe_bool(input_data.get("require_manager_hire"), False)
        start_hiring_managers = _safe_bool(
            input_data.get("start_hiring_managers"),
            require_manager_hire or bool(manager_hire_requests),
        )
        if start_hiring_managers and not manager_hire_requests:
            raise ValueError("Select at least one manager for hire before creating a team.")

        team_root = Path(storage_root)
        config_root = team_root / "configs"
        db_root = team_root / "storage"

        boss_config = {
            "name": boss_name,
            "host": boss_host,
            "port": boss_port,
            "plaza_url": plaza_url,
            "party": party,
            "type": DEFAULT_BOSS_CLASS,
            "description": f"Teamwork boss UI for the {team_name} team on the Phemacast network.",
            "pools": [
                {
                    "type": "SQLitePool",
                    "name": f"{team_slug}_boss_pool",
                    "description": f"{team_name} boss state",
                    "db_path": str(db_root / f"{team_slug}_boss.sqlite"),
                }
            ],
            "boss": {
                "manager_party": party,
                "manager_address": manager_address,
                "monitor_refresh_sec": monitor_refresh_sec,
                "auto_register": boss_auto_register,
                "job_capabilities": job_options,
            },
        }

        manager_config = {
            "name": manager_name,
            "host": manager_host,
            "port": manager_port,
            "plaza_url": plaza_url,
            "party": party,
            "type": str(input_data.get("manager_class") or DEFAULT_MANAGER_CLASS).strip() or DEFAULT_MANAGER_CLASS,
            "description": f"Teamwork manager for the {team_name} team on the Phemacast network.",
            "pools": [
                {
                    "type": "SQLitePool",
                    "name": f"{team_slug}_manager_pool",
                    "description": f"{team_name} manager queue state",
                    "db_path": str(db_root / f"{team_slug}_manager.sqlite"),
                }
            ],
            "manager": {
                "auto_register": manager_auto_register,
                "job_capabilities": job_options,
            },
        }

        worker_specs = []
        custom_workers = [entry for entry in _coerce_list(input_data.get("workers")) if isinstance(entry, Mapping)]
        if custom_workers:
            for index, worker_entry in enumerate(custom_workers):
                worker_specs.append(
                    {
                        "name": str(worker_entry.get("name") or f"{worker_prefix}{index + 1}").strip(),
                        "host": str(worker_entry.get("host") or worker_host).strip(),
                        "port": _safe_int(worker_entry.get("port"), worker_base_port + index),
                        "capabilities": normalize_capabilities(worker_entry.get("capabilities") or default_capabilities),
                        "job_capabilities": _normalize_job_cap_entries(
                            worker_entry.get("job_capabilities") or job_capabilities
                        ),
                    }
                )
        else:
            for index in range(worker_count):
                worker_specs.append(
                    {
                        "name": f"{worker_prefix}{index + 1}",
                        "host": worker_host,
                        "port": worker_base_port + index,
                        "capabilities": list(default_capabilities),
                        "job_capabilities": copy.deepcopy(job_capabilities),
                    }
                )

        worker_configs = []
        for index, worker_spec in enumerate(worker_specs):
            worker_slug = _slugify(worker_spec["name"], fallback=f"worker-{index + 1}")
            worker_configs.append(
                {
                    "name": worker_spec["name"],
                    "host": worker_spec["host"],
                    "port": worker_spec["port"],
                    "plaza_url": plaza_url,
                    "party": party,
                    "type": DEFAULT_WORKER_CLASS,
                    "description": f"Worker for the {team_name} teamwork manager.",
                    "worker": {
                        "manager_party": party,
                        "manager_address": manager_address,
                        "capabilities": worker_spec["capabilities"],
                        "job_capabilities": worker_spec["job_capabilities"],
                        "poll_interval_sec": poll_interval_sec,
                        "auto_register": worker_auto_register,
                    },
                    "config_path": str(config_root / f"{worker_slug}.agent"),
                }
            )
        team_manifest["worker_defaults"]["count"] = len(worker_configs)
        manager_hires: list[dict[str, Any]] = []
        primary_hired_manager_address = ""
        hire_errors: list[str] = []
        if start_hiring_managers:
            for hire_request in manager_hire_requests:
                try:
                    hire_result = self._start_manager_hire(
                        hire_request=hire_request,
                        team_manifest=team_manifest,
                    )
                except Exception as exc:
                    hire_result = {
                        "status": "failed",
                        "pulser_address": str(hire_request.get("pulser_address") or "").strip(),
                        "pulser_name": str(hire_request.get("pulser_name") or "").strip(),
                        "manager_address": "",
                        "manager_name": str(hire_request.get("manager_name") or "").strip(),
                        "local_worker_count": max(_safe_int(hire_request.get("worker_count"), 0), 0),
                        "error": str(exc),
                    }
                manager_hires.append(hire_result)
                if hire_result.get("status") == "joined" and not primary_hired_manager_address:
                    primary_hired_manager_address = str(hire_result.get("manager_address") or "").strip()
                if str(hire_result.get("error") or "").strip():
                    hire_errors.append(str(hire_result.get("error") or "").strip())
            if not primary_hired_manager_address:
                raise ValueError("The team could not hire any selected managers.")

        effective_manager_address = primary_hired_manager_address or manager_address
        boss_config["boss"]["manager_address"] = effective_manager_address
        for worker_config in worker_configs:
            worker_settings = worker_config.get("worker")
            if isinstance(worker_settings, dict):
                worker_settings["manager_address"] = effective_manager_address

        return {
            "team_name": team_name,
            "team_slug": team_slug,
            "party": party,
            "manager_address": effective_manager_address,
            "team_manifest": team_manifest,
            "job_capabilities": job_capabilities,
            "capabilities": default_capabilities,
            "boss_config": boss_config,
            "manager_config": manager_config,
            "worker_configs": worker_configs,
            "config_paths": {
                "boss": str(config_root / "boss.agent"),
                "manager": str(config_root / "manager.agent"),
                "workers": [entry["config_path"] for entry in worker_configs],
            },
            "launch_plan": [
                {"role": "manager", "type": manager_config["type"], "config_path": str(config_root / "manager.agent")},
                {"role": "boss", "type": boss_config["type"], "config_path": str(config_root / "boss.agent")},
                *[
                    {"role": "worker", "type": entry["type"], "config_path": entry["config_path"]}
                    for entry in worker_configs
                ],
            ],
            "manager_hires": manager_hires,
            "hiring": {
                "requested": len(manager_hire_requests),
                "started": len([entry for entry in manager_hires if entry.get("status") == "joined"]),
                "required_manager_count": 1 if start_hiring_managers else 0,
                "primary_manager_address": effective_manager_address if start_hiring_managers else "",
            },
            "warnings": list(dict.fromkeys([*_job_capability_warnings(job_capabilities), *hire_errors])),
        }

    def _handle_create_manager(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to handle the create manager."""
        if _coerce_object(input_data.get("team_manifest")):
            return self._handle_connect_manager(input_data)

        party = self._party_from_input(input_data)
        team_name = str(input_data.get("team_name") or "Phemacast Team").strip()
        team_slug = _slugify(input_data.get("team_slug") or team_name, fallback="phemacast-team")
        manager_name = str(input_data.get("manager_name") or f"{_titleify_slug(team_slug)}Manager").strip()
        manager_host = str(input_data.get("manager_host") or "127.0.0.1").strip()
        manager_port = _safe_int(input_data.get("manager_port"), 8170)
        plaza_url = str(input_data.get("plaza_url") or self.plaza_url or "").strip()
        storage_root = str(input_data.get("storage_root") or f"phemacast/teamwork/{team_slug}").strip().rstrip("/")
        config_root = Path(storage_root) / "configs"
        db_root = Path(storage_root) / "storage"
        job_capabilities = _normalize_job_cap_entries(
            input_data.get("job_capabilities") or input_data.get("supported_jobcaps") or []
        )
        manager_config = {
            "name": manager_name,
            "host": manager_host,
            "port": manager_port,
            "plaza_url": plaza_url,
            "party": party,
            "type": str(input_data.get("manager_class") or DEFAULT_MANAGER_CLASS).strip() or DEFAULT_MANAGER_CLASS,
            "description": f"Teamwork manager for the {team_name} team on the Phemacast network.",
            "pools": [
                {
                    "type": "SQLitePool",
                    "name": f"{team_slug}_manager_pool",
                    "description": f"{team_name} manager queue state",
                    "db_path": str(db_root / f"{team_slug}_manager.sqlite"),
                }
            ],
            "manager": {
                "auto_register": _safe_bool(input_data.get("manager_auto_register"), True),
                "job_capabilities": _job_option_entries(job_capabilities),
            },
        }
        manager_address = str(input_data.get("manager_address") or f"http://{manager_host}:{manager_port}").strip()
        return {
            "team_name": team_name,
            "team_slug": team_slug,
            "party": party,
            "manager_address": manager_address,
            "job_capabilities": job_capabilities,
            "manager_config": manager_config,
            "config_path": str(config_root / "manager.agent"),
            "launch_plan": [
                {
                    "role": "manager",
                    "type": manager_config["type"],
                    "config_path": str(config_root / "manager.agent"),
                }
            ],
            "warnings": _job_capability_warnings(job_capabilities),
        }

    def _handle_connect_manager(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to connect one manager environment to an existing team."""
        raw_manifest = _coerce_object(input_data.get("team_manifest"))
        if not raw_manifest:
            raise ValueError("team_manifest is required to connect a manager to an existing team.")

        manifest_boss = _coerce_object(raw_manifest.get("boss_defaults"))
        manifest_manager = _coerce_object(raw_manifest.get("manager_defaults"))
        manifest_worker = _coerce_object(raw_manifest.get("worker_defaults"))

        team_name = str(input_data.get("team_name") or raw_manifest.get("team_name") or "Phemacast Team").strip()
        team_slug = _slugify(input_data.get("team_slug") or raw_manifest.get("team_slug") or team_name, fallback="phemacast-team")
        party = str(input_data.get("party") or raw_manifest.get("party") or self.default_party).strip() or self.default_party
        plaza_url = str(input_data.get("plaza_url") or raw_manifest.get("plaza_url") or self.plaza_url or "").strip()
        storage_root = str(input_data.get("storage_root") or f"phemacast/teamwork/{team_slug}").strip().rstrip("/")

        boss_name = str(manifest_boss.get("name") or f"{_titleify_slug(team_slug)}Boss").strip()
        boss_host = str(manifest_boss.get("host") or "127.0.0.1").strip()
        boss_port = _safe_int(manifest_boss.get("port"), 8175)
        monitor_refresh_sec = _safe_int(manifest_boss.get("monitor_refresh_sec"), 10)
        boss_auto_register = _safe_bool(manifest_boss.get("auto_register"), True)

        manager_name = str(
            input_data.get("manager_name")
            or manifest_manager.get("name")
            or f"{_titleify_slug(team_slug)}Manager"
        ).strip()
        manager_host = str(input_data.get("manager_host") or manifest_manager.get("host") or "127.0.0.1").strip()
        manager_port = _safe_int(input_data.get("manager_port"), _safe_int(manifest_manager.get("port"), 8170))
        manager_class = str(
            input_data.get("manager_class") or manifest_manager.get("type") or DEFAULT_MANAGER_CLASS
        ).strip() or DEFAULT_MANAGER_CLASS
        manager_auto_register = _safe_bool(
            input_data.get("manager_auto_register"),
            _safe_bool(manifest_manager.get("auto_register"), True),
        )

        job_capabilities = _normalize_job_cap_entries(
            input_data.get("job_capabilities")
            or raw_manifest.get("job_capabilities")
            or manifest_worker.get("job_capabilities")
            or []
        )
        capabilities = normalize_capabilities(
            input_data.get("capabilities")
            or raw_manifest.get("capabilities")
            or manifest_worker.get("capabilities")
            or [entry.get("name") for entry in job_capabilities if entry.get("name")]
        )

        worker_count = max(_safe_int(input_data.get("worker_count"), _safe_int(manifest_worker.get("count"), 0)), 0)
        worker_prefix = str(
            input_data.get("worker_name_prefix")
            or manifest_worker.get("name_prefix")
            or f"{_titleify_slug(team_slug)}Worker"
        ).strip()
        worker_host = str(input_data.get("worker_host") or manifest_worker.get("host") or "127.0.0.1").strip()
        worker_base_port = _safe_int(
            input_data.get("worker_base_port"),
            _safe_int(manifest_worker.get("base_port"), manager_port + 1),
        )
        poll_interval_sec = _safe_int(
            input_data.get("poll_interval_sec"),
            _safe_int(manifest_worker.get("poll_interval_sec"), 10),
        )
        worker_auto_register = _safe_bool(
            input_data.get("worker_auto_register"),
            _safe_bool(manifest_worker.get("auto_register"), True),
        )

        normalized_manifest = self._build_team_manifest_payload(
            team_name=team_name,
            team_slug=team_slug,
            party=party,
            plaza_url=plaza_url,
            boss_name=boss_name,
            boss_host=boss_host,
            boss_port=boss_port,
            manager_name=manager_name,
            manager_host=manager_host,
            manager_port=manager_port,
            manager_class=manager_class,
            worker_prefix=worker_prefix,
            worker_host=worker_host,
            worker_base_port=worker_base_port,
            worker_count=worker_count,
            job_capabilities=job_capabilities,
            capabilities=capabilities,
            monitor_refresh_sec=monitor_refresh_sec,
            poll_interval_sec=poll_interval_sec,
            boss_auto_register=boss_auto_register,
            manager_auto_register=manager_auto_register,
            worker_auto_register=worker_auto_register,
        )

        manager_blueprint = self._handle_create_manager(
            {
                "team_name": team_name,
                "team_slug": team_slug,
                "manager_name": manager_name,
                "party": party,
                "manager_host": manager_host,
                "manager_port": manager_port,
                "manager_address": input_data.get("manager_address"),
                "plaza_url": plaza_url,
                "storage_root": storage_root,
                "manager_class": manager_class,
                "manager_auto_register": manager_auto_register,
                "job_capabilities": job_capabilities,
            }
        )
        manager_address = str(manager_blueprint.get("manager_address") or "").strip()

        worker_configs: list[dict[str, Any]] = []
        worker_config_paths: list[str] = []
        for index in range(worker_count):
            requested_worker_name = input_data.get("worker_name") if worker_count == 1 else ""
            worker_name = str(requested_worker_name or f"{worker_prefix}{index + 1}").strip() or f"{worker_prefix}{index + 1}"
            worker_blueprint = self._handle_create_worker(
                {
                    "team_name": team_name,
                    "team_slug": team_slug,
                    "worker_name": worker_name,
                    "party": party,
                    "worker_host": worker_host,
                    "worker_port": worker_base_port + index,
                    "manager_address": manager_address,
                    "plaza_url": plaza_url,
                    "storage_root": storage_root,
                    "job_capabilities": job_capabilities,
                    "capabilities": capabilities,
                    "poll_interval_sec": poll_interval_sec,
                    "worker_auto_register": worker_auto_register,
                }
            )
            worker_configs.append(dict(worker_blueprint.get("worker_config") or {}))
            worker_config_paths.append(str(worker_blueprint.get("config_path") or "").strip())

        launch_plan = list(manager_blueprint.get("launch_plan") or [])
        launch_plan.extend(
            {"role": "worker", "type": entry.get("type") or DEFAULT_WORKER_CLASS, "config_path": path}
            for entry, path in zip(worker_configs, worker_config_paths)
        )

        warnings = list(dict.fromkeys(
            [
                *[str(item) for item in _coerce_list(manager_blueprint.get("warnings")) if str(item).strip()],
                *[str(item) for item in _job_capability_warnings(job_capabilities) if str(item).strip()],
            ]
        ))

        return {
            "team_name": team_name,
            "team_slug": team_slug,
            "party": party,
            "manager_address": manager_address,
            "team_manifest": normalized_manifest,
            "team_membership": {
                "status": "joined",
                "join_source": "team_manifest",
                "team_name": team_name,
                "team_slug": team_slug,
                "party": party,
                "manager_name": manager_name,
                "manager_address": manager_address,
                "local_worker_count": len(worker_configs),
            },
            "job_capabilities": job_capabilities,
            "capabilities": capabilities,
            "manager_config": manager_blueprint.get("manager_config"),
            "worker_configs": worker_configs,
            "config_path": manager_blueprint.get("config_path"),
            "config_paths": {
                "manager": manager_blueprint.get("config_path"),
                "workers": worker_config_paths,
            },
            "launch_plan": launch_plan,
            "warnings": warnings,
        }

    def _handle_create_worker(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to handle the create worker."""
        party = self._party_from_input(input_data)
        team_name = str(input_data.get("team_name") or "Phemacast Team").strip()
        team_slug = _slugify(input_data.get("team_slug") or team_name, fallback="phemacast-team")
        worker_name = str(input_data.get("worker_name") or f"{_titleify_slug(team_slug)}Worker").strip()
        worker_host = str(input_data.get("worker_host") or "127.0.0.1").strip()
        worker_port = _safe_int(input_data.get("worker_port"), 8171)
        manager_address = str(input_data.get("manager_address") or "").strip()
        if not manager_address:
            manager_address = self._entry_address(self._resolve_manager_entry(input_data))
        plaza_url = str(input_data.get("plaza_url") or self.plaza_url or "").strip()
        storage_root = str(input_data.get("storage_root") or f"phemacast/teamwork/{team_slug}").strip().rstrip("/")
        config_root = Path(storage_root) / "configs"
        job_capabilities = _normalize_job_cap_entries(input_data.get("job_capabilities") or [])
        capabilities = normalize_capabilities(
            input_data.get("capabilities") or [entry.get("name") for entry in job_capabilities if entry.get("name")]
        )
        worker_config = {
            "name": worker_name,
            "host": worker_host,
            "port": worker_port,
            "plaza_url": plaza_url,
            "party": party,
            "type": DEFAULT_WORKER_CLASS,
            "description": f"Worker for the {team_name} teamwork manager.",
            "worker": {
                "manager_party": party,
                "manager_address": manager_address,
                "capabilities": capabilities,
                "job_capabilities": job_capabilities,
                "poll_interval_sec": _safe_int(input_data.get("poll_interval_sec"), 10),
                "auto_register": _safe_bool(input_data.get("worker_auto_register"), True),
            },
        }
        return {
            "team_name": team_name,
            "party": party,
            "manager_address": manager_address,
            "worker_config": worker_config,
            "config_path": str(config_root / f"{_slugify(worker_name)}.agent"),
            "warnings": _job_capability_warnings(job_capabilities),
        }

    def _handle_discover_teams(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to handle the discover teams."""
        party = self._party_from_input(input_data)
        name = str(input_data.get("name") or input_data.get("team_name") or "").strip()
        include_workers = _safe_bool(input_data.get("include_workers"), True)
        managers = self._discover_managers(party=party, name=name)
        workers = self._discover_workers(party=party) if include_workers else []

        worker_groups: dict[str, list[dict[str, Any]]] = {}
        for worker in workers:
            manager_address = str(
                self._entry_meta(worker).get("manager_address")
                or self._entry_meta(worker).get("dispatcher_address")
                or ""
            ).strip().rstrip("/")
            worker_groups.setdefault(manager_address, []).append(worker)

        teams = [
            self._team_descriptor(manager, worker_groups.get(self._entry_address(manager), []))
            for manager in managers
        ]
        return {"party": party, "count": len(teams), "teams": teams}

    def _handle_supported_jobcaps(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to handle the supported jobcaps."""
        manager_entry = None
        if str(input_data.get("manager_address") or "").strip():
            manager_entry = self._resolve_manager_entry(input_data)
            managers = [manager_entry]
            party = self._party_from_input(input_data)
            workers = self._discover_workers(party=party)
        else:
            party = self._party_from_input(input_data)
            managers = self._discover_managers(party=party, name=str(input_data.get("manager_name") or "").strip())
            workers = self._discover_workers(party=party)

        capability_map: dict[str, dict[str, Any]] = {}

        def add_provider(name: str, *, provider_type: str, provider_name: str, provider_address: str, entry: Mapping[str, Any] | None = None) -> None:
            """Add the provider."""
            normalized_name = str(name or "").strip().lower()
            if not normalized_name:
                return
            bucket = capability_map.setdefault(
                normalized_name,
                {
                    "name": normalized_name,
                    "description": str((entry or {}).get("description") or "").strip(),
                    "callable": str((entry or {}).get("callable") or "").strip(),
                    "type": str((entry or {}).get("type") or (entry or {}).get("class") or "").strip(),
                    "providers": [],
                },
            )
            provider_key = (provider_type, provider_name, provider_address)
            existing_keys = {
                (provider["type"], provider["name"], provider["address"])
                for provider in bucket["providers"]
            }
            if provider_key not in existing_keys:
                bucket["providers"].append(
                    {
                        "type": provider_type,
                        "name": provider_name,
                        "address": provider_address,
                    }
                )
            if entry:
                if not bucket.get("description") and str(entry.get("description") or "").strip():
                    bucket["description"] = str(entry.get("description") or "").strip()
                if not bucket.get("callable") and str(entry.get("callable") or "").strip():
                    bucket["callable"] = str(entry.get("callable") or "").strip()
                if not bucket.get("type") and str(entry.get("type") or entry.get("class") or "").strip():
                    bucket["type"] = str(entry.get("type") or entry.get("class") or "").strip()

        for manager in managers:
            manager_name = self._entry_name(manager) or "Manager"
            manager_address = self._entry_address(manager)
            meta = self._entry_meta(manager)
            for entry in _normalize_job_cap_entries(meta.get("job_capabilities") or self._entry_card(manager).get("job_capabilities")):
                add_provider(
                    entry.get("name"),
                    provider_type="manager",
                    provider_name=manager_name,
                    provider_address=manager_address,
                    entry=entry,
                )

        for worker in workers:
            worker_name = self._entry_name(worker) or "Worker"
            worker_address = self._entry_address(worker)
            worker_meta = self._entry_meta(worker)
            for entry in _normalize_job_cap_entries(worker_meta.get("job_capabilities") or self._entry_card(worker).get("job_capabilities")):
                add_provider(
                    entry.get("name"),
                    provider_type="worker",
                    provider_name=worker_name,
                    provider_address=worker_address,
                    entry=entry,
                )
            for capability_name in normalize_capabilities(
                worker_meta.get("capabilities") or worker.get("capabilities") or self._entry_card(worker).get("capabilities") or []
            ):
                add_provider(
                    capability_name,
                    provider_type="worker",
                    provider_name=worker_name,
                    provider_address=worker_address,
                )

        capability_rows = sorted(capability_map.values(), key=lambda row: row["name"])
        return {
            "party": party,
            "manager_count": len(managers),
            "worker_count": len(workers),
            "count": len(capability_rows),
            "job_capabilities": capability_rows,
        }

    def _handle_team_status(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to handle the team status."""
        manager_entry = self._resolve_manager_entry(input_data)
        manager_address = self._entry_address(manager_entry)
        preview_limit = max(_safe_int(input_data.get("preview_limit"), 1000), 50)

        jobs_preview = self._manager_preview_table(manager_address, TABLE_JOBS, limit=preview_limit)
        workers_preview = self._manager_preview_table(manager_address, TABLE_WORKERS, limit=preview_limit)

        latest_jobs = self._latest_rows(jobs_preview.get("rows") or [], key_field="id")
        latest_workers = self._latest_rows(
            workers_preview.get("rows") or [],
            key_field="worker_id",
            alternate_keys=("id", "name"),
            time_fields=("updated_at", "last_seen_at"),
        )
        monitored_workers = [self._monitor_worker_health(worker) for worker in latest_workers]

        jobs_by_status: dict[str, int] = {}
        for job in latest_jobs:
            status = str(job.get("status") or "unknown").strip().lower() or "unknown"
            jobs_by_status[status] = jobs_by_status.get(status, 0) + 1

        workers_by_health = {"online": 0, "stale": 0, "offline": 0}
        for worker in monitored_workers:
            health = str(worker.get("health_status") or "offline").strip().lower()
            if health not in workers_by_health:
                workers_by_health[health] = 0
            workers_by_health[health] += 1

        active_jobs = [
            {
                "id": str(job.get("id") or ""),
                "required_capability": str(job.get("required_capability") or ""),
                "status": str(job.get("status") or ""),
                "claimed_by": str(job.get("claimed_by") or ""),
                "updated_at": str(job.get("updated_at") or ""),
                "priority": _safe_int(job.get("priority"), 0),
            }
            for job in latest_jobs
            if str(job.get("status") or "").strip().lower() in {"claimed", "stopping", "queued", "retry", "unfinished"}
        ][:20]

        recent_jobs = [
            {
                "id": str(job.get("id") or ""),
                "required_capability": str(job.get("required_capability") or ""),
                "status": str(job.get("status") or ""),
                "updated_at": str(job.get("updated_at") or ""),
                "completed_at": str(job.get("completed_at") or ""),
                "priority": _safe_int(job.get("priority"), 0),
                "error": str(job.get("error") or ""),
            }
            for job in latest_jobs[:10]
        ]

        return {
            "manager": self._team_descriptor(manager_entry),
            "jobs": {
                "total": len(latest_jobs),
                "by_status": jobs_by_status,
                "active": active_jobs,
                "recent": recent_jobs,
                "raw_rows_scanned": len(jobs_preview.get("rows") or []),
                "raw_total_rows": _safe_int(jobs_preview.get("total_rows"), len(jobs_preview.get("rows") or [])),
            },
            "workers": {
                "total": len(monitored_workers),
                "by_health": workers_by_health,
                "roster": monitored_workers[:25],
                "raw_rows_scanned": len(workers_preview.get("rows") or []),
                "raw_total_rows": _safe_int(workers_preview.get("total_rows"), len(workers_preview.get("rows") or [])),
            },
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }

    def _handle_team_history(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to handle the team history."""
        manager_entry = self._resolve_manager_entry(input_data)
        manager_address = self._entry_address(manager_entry)
        limit = max(_safe_int(input_data.get("limit"), 20), 1)

        jobs_preview = self._manager_preview_table(manager_address, TABLE_JOBS, limit=limit)
        worker_history_preview = self._manager_preview_table(manager_address, TABLE_WORKER_HISTORY, limit=limit)

        recent_jobs = [
            {
                "id": str(row.get("id") or ""),
                "required_capability": str(row.get("required_capability") or ""),
                "status": str(row.get("status") or ""),
                "claimed_by": str(row.get("claimed_by") or ""),
                "updated_at": str(row.get("updated_at") or ""),
                "completed_at": str(row.get("completed_at") or ""),
                "error": str(row.get("error") or ""),
            }
            for row in jobs_preview.get("rows") or []
            if isinstance(row, Mapping)
        ]
        worker_events = [
            {
                "worker_id": str(row.get("worker_id") or ""),
                "name": str(row.get("name") or ""),
                "status": str(row.get("status") or ""),
                "event_type": str(row.get("event_type") or ""),
                "active_job_id": str(row.get("active_job_id") or ""),
                "captured_at": str(row.get("captured_at") or ""),
            }
            for row in worker_history_preview.get("rows") or []
            if isinstance(row, Mapping)
        ]
        return {
            "manager": self._team_descriptor(manager_entry),
            "jobs": recent_jobs,
            "worker_history": worker_events,
            "limit": limit,
        }

    def _handle_submit_team_job(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to handle the submit team job."""
        manager_entry = self._resolve_manager_entry(input_data)
        manager_address = self._entry_address(manager_entry)
        required_capability = str(input_data.get("required_capability") or input_data.get("capability") or "").strip().lower()
        if not required_capability:
            raise ValueError("required_capability is required.")

        payload = {
            "required_capability": required_capability,
            "payload": input_data.get("payload") if isinstance(input_data.get("payload"), Mapping) else input_data.get("payload"),
            "target_table": str(input_data.get("target_table") or "").strip(),
            "source_url": str(input_data.get("source_url") or "").strip(),
            "parse_rules": input_data.get("parse_rules"),
            "targets": input_data.get("targets"),
            "capability_tags": input_data.get("capability_tags"),
            "job_type": str(input_data.get("job_type") or "run").strip(),
            "priority": _safe_int(input_data.get("priority"), 100),
            "premium": _safe_bool(input_data.get("premium"), False),
            "metadata": _coerce_object(input_data.get("metadata")),
            "scheduled_for": input_data.get("scheduled_for"),
            "max_attempts": max(_safe_int(input_data.get("max_attempts"), 3), 1),
            "job_id": str(input_data.get("job_id") or "").strip() or None,
        }
        result = self._use_manager_practice(manager_address, "manager-submit-job", payload)
        return {
            "manager": self._team_descriptor(manager_entry),
            "submitted": result,
            "required_capability": required_capability,
        }
