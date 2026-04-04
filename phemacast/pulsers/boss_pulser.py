"""
Boss pulser implementation for the Pulsers area.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, these modules implement pulse sources for
APIs, files, bosses, MCP tools, and path-based workflows.

Core types exposed here include `BossPulser`, which carry the main behavior or state
managed by this module.
"""

from __future__ import annotations

import copy
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping

from fastapi import HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from phemacast.agents.pulser import Pulser, _read_config
from prompits.dispatcher.agents import WORKER_HEARTBEAT_INTERVAL_SEC, WORKER_JOB_TIMEOUT_SEC
from prompits.dispatcher.jobcap import infer_job_cap_name
from prompits.dispatcher.runtime import normalize_capabilities, parse_datetime_value
from prompits.teamwork.schema import TABLE_JOBS, TABLE_WORKER_HISTORY, TABLE_WORKERS


DEFAULT_TEAMWORK_PARTY = "Phemacast"
DEFAULT_MANAGER_CLASS = "prompits.teamwork.agents.DispatcherManagerAgent"
DEFAULT_BOSS_CLASS = "prompits.teamwork.boss.TeamBossAgent"
DEFAULT_WORKER_CLASS = "prompits.teamwork.agents.TeamWorkerAgent"
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


class BossPulser(Pulser):
    """
    Phemacast-facing pulser that provisions and monitors teamwork teams.

    The pulser keeps orchestration thin:
    - Plaza discovery is used to find managers and workers on the network.
    - Team status/history comes from teamwork manager practices.
    - Team creation returns ready-to-save teamwork config documents instead of
      launching local processes directly.
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
            },
        }

    def _ui_context(self) -> dict[str, Any]:
        """Internal helper for UI context."""
        return {
            "asset_version": self._asset_version(),
            "initial_payload": self._ui_initial_payload(),
        }

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

        @self.app.post("/api/provision/worker")
        async def boss_pulser_create_worker(payload: Dict[str, Any]):
            """Route handler for POST /api/provision/worker."""
            try:
                return await run_in_threadpool(self._handle_create_worker, dict(payload or {}))
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

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
                "monitor_refresh_sec": _safe_int(input_data.get("monitor_refresh_sec"), 10),
                "auto_register": _safe_bool(input_data.get("boss_auto_register"), True),
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
                "auto_register": _safe_bool(input_data.get("manager_auto_register"), True),
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
                        "poll_interval_sec": _safe_int(input_data.get("poll_interval_sec"), 10),
                        "auto_register": _safe_bool(input_data.get("worker_auto_register"), True),
                    },
                    "config_path": str(config_root / f"{worker_slug}.agent"),
                }
            )

        return {
            "team_name": team_name,
            "team_slug": team_slug,
            "party": party,
            "manager_address": manager_address,
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
            "warnings": _job_capability_warnings(job_capabilities),
        }

    def _handle_create_manager(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Internal helper to handle the create manager."""
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
