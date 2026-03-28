import json
import logging
import os
import re
import threading
import time
import uuid
from urllib.parse import urlencode

import httpx
import uvicorn
from prompits.core.pool import Pool
from typing import Dict, Any, List, Optional, Set, Tuple

from datetime import datetime, timezone

from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from attas.pds import normalize_runtime_pulse_entry
from prompits.agents.base import BaseAgent
from prompits.core.agent_config import AgentConfigStore, AgentLaunchManager
from prompits.core.init_schema import phemas_table_schema, plaza_ui_users_table_schema
from prompits.core.message import Message
from prompits.practices.plaza import PlazaPractice
from phemacast.core.phema import Phema

logger = logging.getLogger(__name__)


class PlazaUiSignUpRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str
    display_name: Optional[str] = None


class PlazaUiSignInRequest(BaseModel):
    identifier: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None
    password: str


class PlazaUiRefreshRequest(BaseModel):
    refresh_token: str


class PlazaUiProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = None


class PlazaUiPasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PlazaUiUserUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[str] = None


class PlazaPhemaUpsertRequest(BaseModel):
    phema: Dict[str, Any]


class PlazaPulserTestRequest(BaseModel):
    pulser_id: Optional[str] = None
    pulser_name: Optional[str] = None
    pulser_address: Optional[str] = None
    practice_id: Optional[str] = None
    pulse_name: Optional[str] = None
    pulse_address: Optional[str] = None
    output_schema: Optional[Dict[str, Any]] = None
    input: Any = None


class PlazaAgentConfigUpsertRequest(BaseModel):
    config: Dict[str, Any]
    config_id: Optional[str] = None
    owner: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None


class PlazaAgentConfigLaunchRequest(BaseModel):
    config_id: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    owner: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    agent_name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    pool_type: Optional[str] = None
    pool_location: Optional[str] = None
    wait_for_health_sec: float = 15.0


class PlazaAgent(BaseAgent):
    """
    Concrete agent host for Plaza service runtime.

    Plaza endpoints themselves are provided by `PlazaPractice` loaded via
    configuration; this class focuses on base identity and core service routes.
    """

    UI_USERS_TABLE = "plaza_ui_users"
    PHEMA_TABLE = "phemas"
    UI_USER_ROLES = {"admin", "user"}
    UI_USER_STATUSES = {"active", "disabled"}
    UI_OAUTH_PROVIDERS = ("google", "github", "apple")
    DEFAULT_ADMIN_USERNAME = "admin"
    DEFAULT_ADMIN_PASSWORD = "admin"
    DEFAULT_AUTH_EMAIL_DOMAIN = "plaza.local"
    USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,30}[a-z0-9])?$")

    def __init__(self, host="127.0.0.1", port=8000, pool: Optional[Pool] = None):
        # Plaza Config
        agent_card = {
             "name": "Plaza", 
             "role": "coordinator", 
             "tags": ["mediator"],
             "host": host,
             "port": port,
             "address": f"http://{host}:{port}"
        }
        super().__init__(name="Plaza", host=host, port=port, agent_card=agent_card, pool=pool)
        self.agent_cards: Dict[str, Dict[str, Any]] = {}
        self._phema_cache: Dict[str, Dict[str, Any]] = {}
        self.plaza_practice: Optional[PlazaPractice] = None
        self._ui_auth_bootstrap_lock = threading.Lock()
        self._ui_auth_bootstrap_error: Optional[str] = None
        self._oauth_state_lock = threading.Lock()
        self._oauth_states: Dict[str, Dict[str, Any]] = {}
        self._supabase_http_client: Optional[httpx.Client] = None
        self._supabase_http_timeout_cache: Optional[float] = None

        current_dir = os.path.dirname(os.path.abspath(__file__))
        workspace_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
        templates_dir = os.path.abspath(os.path.join(current_dir, "..", "agents", "templates"))
        static_dir = os.path.abspath(os.path.join(current_dir, "..", "agents", "static"))
        self.templates = Jinja2Templates(directory=templates_dir)
        self.app.mount("/static", StaticFiles(directory=static_dir), name="static")
        self.agent_config_store = AgentConfigStore(pool=pool)
        self.agent_launch_manager = AgentLaunchManager(
            default_plaza_url=str(self.agent_card.get("address") or ""),
            default_bind_host="127.0.0.1",
            workspace_root=workspace_root,
        )

        # Note: Practices are dynamically loaded via attas/configs/plaza.agent
        

        
        # Register Self
        self.agent_cards[self.name] = self.agent_card
        logger.info(f"[Plaza] Registered self: {self.name} at {self.agent_card['address']}")
        
        self.setup_plaza_routes()

    def setup_plaza_routes(self):
        supported_pit_types = sorted(PlazaPractice.SUPPORTED_PIT_TYPES)

        @self.app.get("/")
        async def plaza_ui(request: Request):
            return self.templates.TemplateResponse(
                request=request,
                name="plazas.html",
                context={"request": request, "agent_name": self.name, "supported_pit_types": supported_pit_types},
            )

        @self.app.get("/plazas")
        async def plaza_ui_alias(request: Request):
            return self.templates.TemplateResponse(
                request=request,
                name="plazas.html",
                context={"request": request, "agent_name": self.name, "supported_pit_types": supported_pit_types},
            )

        @self.app.get("/phemas/editor")
        async def phema_editor(request: Request):
            return self.templates.TemplateResponse(
                request=request,
                name="phema_editor.html",
                context={"request": request, "agent_name": self.name, "initial_phema_id": ""},
            )

        @self.app.get("/phemas/editor/{phema_id}")
        async def phema_editor_existing(request: Request, phema_id: str):
            return self.templates.TemplateResponse(
                request=request,
                name="phema_editor.html",
                context={"request": request, "agent_name": self.name, "initial_phema_id": phema_id},
            )

        @self.app.get("/api/plazas_status")
        async def plaza_status(request: Request):
            pit_type = request.query_params.get("pit_type")

            def _plaza_status_sync() -> Dict[str, Any]:
                practice = self._get_plaza_practice()
                if practice is None:
                    return {"status": "success", "plazas": []}

                agents = practice.state.search_entries(pit_type=pit_type)
                if not pit_type:
                    pulse_pulser_rows = practice.state.get_pulse_pulser_rows()
                    pulser_rows_by_id: Dict[str, List[Dict[str, Any]]] = {}
                    for row in pulse_pulser_rows:
                        pulser_id = str(row.get("pulser_id") or "").strip()
                        if not pulser_id:
                            continue
                        pulser_rows_by_id.setdefault(pulser_id, []).append(row)

                    pulser_summaries_by_id: Dict[str, Dict[str, Any]] = {}
                    pulser_summaries_by_name: Dict[str, Dict[str, Any]] = {}
                    pulser_summaries_by_address: Dict[str, Dict[str, Any]] = {}

                    def register_pulser_summary(summary: Dict[str, Any]):
                        summary_id = str(summary.get("agent_id") or "").strip()
                        if summary_id:
                            pulser_summaries_by_id[summary_id] = summary

                        summary_name = str(summary.get("name") or "").strip().lower()
                        if summary_name and summary_name not in pulser_summaries_by_name:
                            pulser_summaries_by_name[summary_name] = summary

                        summary_address = str(summary.get("address") or "").strip().lower()
                        if summary_address and summary_address not in pulser_summaries_by_address:
                            pulser_summaries_by_address[summary_address] = summary

                    def build_fallback_pulser_summary(row: Dict[str, Any]) -> Dict[str, Any]:
                        pulser_id = str(row.get("pulser_id") or "").strip()
                        pulser_name = str(row.get("pulser_name") or "").strip() or "Unnamed Pulser"
                        pulser_address = str(row.get("pulser_address") or "").strip()
                        supported: List[Dict[str, Any]] = []
                        seen_supported: Set[str] = set()
                        for supported_row in pulser_rows_by_id.get(pulser_id, []):
                            pulse_id = str(supported_row.get("pulse_id") or "").strip()
                            supported_name = supported_row.get("pulse_name")
                            supported_address = supported_row.get("pulse_address")
                            supported_key = pulse_id or f"{str(supported_name or '').strip().lower()}::{str(supported_address or '').strip().lower()}"
                            if supported_key in seen_supported:
                                continue
                            seen_supported.add(supported_key)
                            supported.append(
                                normalize_runtime_pulse_entry(
                                    {
                                        "pulse_id": pulse_id,
                                        "name": supported_name,
                                        "pulse_name": supported_name,
                                        "pulse_address": supported_address,
                                        "pulse_definition": supported_row.get("pulse_definition"),
                                        "input_schema": supported_row.get("input_schema") if isinstance(supported_row.get("input_schema"), dict) else {},
                                    },
                                    default_name=str(supported_name or ""),
                                    default_pulse_address=str(supported_address or ""),
                                )
                            )
                        return {
                            "agent_id": pulser_id,
                            "name": pulser_name,
                            "address": pulser_address,
                            "description": "",
                            "owner": "",
                            "meta": {"supported_pulses": supported} if supported else {},
                            "last_active": 0,
                            "plaza_name": self.agent_card.get("name", self.name),
                        }

                    def resolve_pulser_summary(row: Dict[str, Any]) -> Dict[str, Any]:
                        pulser_id = str(row.get("pulser_id") or "").strip()
                        pulser_name = str(row.get("pulser_name") or "").strip().lower()
                        pulser_address = str(row.get("pulser_address") or "").strip().lower()

                        summary = pulser_summaries_by_id.get(pulser_id)
                        if summary is None and pulser_address:
                            summary = pulser_summaries_by_address.get(pulser_address)
                        if summary is None and pulser_name:
                            summary = pulser_summaries_by_name.get(pulser_name)
                        if summary is not None:
                            return summary
                        return build_fallback_pulser_summary(row)

                    def resolve_pulse_definition(summary: Dict[str, Any], row: Dict[str, Any]) -> Dict[str, Any]:
                        meta = summary.get("meta") if isinstance(summary.get("meta"), dict) else {}
                        supported = meta.get("supported_pulses") if isinstance(meta.get("supported_pulses"), list) else []
                        matched: Dict[str, Any] = {}
                        row_pulse_id = row.get("pulse_id")
                        row_pulse_name = row.get("pulse_name")
                        row_pulse_address = row.get("pulse_address")
                        for entry in supported:
                            if not isinstance(entry, dict):
                                continue
                            entry_pulse_id = entry.get("pulse_id")
                            entry_name = entry.get("pulse_name") or entry.get("name")
                            entry_address = entry.get("pulse_address")
                            if row_pulse_id and str(entry_pulse_id or "").strip() != str(row_pulse_id).strip():
                                continue
                            if row_pulse_name and not practice.state.contains(entry_name, row_pulse_name):
                                continue
                            if row_pulse_address and entry_address and not practice.state.same_pit_ref(entry_address, row_pulse_address):
                                continue
                            matched = dict(entry)
                            break

                        if row_pulse_id and not matched.get("pulse_id"):
                            matched["pulse_id"] = row_pulse_id
                        if row_pulse_name and not matched.get("pulse_name"):
                            matched["pulse_name"] = row_pulse_name
                        if row_pulse_name and not matched.get("name"):
                            matched["name"] = row_pulse_name
                        if row_pulse_address and not matched.get("pulse_address"):
                            matched["pulse_address"] = row_pulse_address
                        if not isinstance(matched.get("pulse_definition"), dict) and isinstance(row.get("pulse_definition"), dict):
                            matched["pulse_definition"] = dict(row.get("pulse_definition") or {})
                        if not isinstance(matched.get("input_schema"), dict) and isinstance(row.get("input_schema"), dict):
                            matched["input_schema"] = row.get("input_schema")
                        return normalize_runtime_pulse_entry(
                            matched,
                            default_name=str(row_pulse_name or ""),
                            default_pulse_address=str(row_pulse_address or ""),
                        )

                    for agent in agents:
                        resolved_type = str(agent.get("pit_type") or "")
                        card = agent.get("card") if isinstance(agent.get("card"), dict) else {}
                        meta = agent.get("meta") if isinstance(agent.get("meta"), dict) else {}
                        if resolved_type == "Pulser":
                            supported = meta.get("supported_pulses") if isinstance(meta.get("supported_pulses"), list) else []
                            seen = {
                                str(entry.get("pulse_id") or "").strip().lower()
                                or f"{str(entry.get('pulse_name') or '').strip().lower()}::{str(entry.get('pulse_address') or '').strip().lower()}"
                                for entry in supported if isinstance(entry, dict)
                            }
                            for row in pulser_rows_by_id.get(str(agent.get("agent_id") or ""), []):
                                pulse_id = str(row.get("pulse_id") or "").strip()
                                pulse_name = row.get("pulse_name")
                                pulse_address = row.get("pulse_address")
                                key = pulse_id or f"{str(pulse_name or '').strip().lower()}::{str(pulse_address or '').strip().lower()}"
                                if key in seen:
                                    continue
                                seen.add(key)
                                supported.append(
                                    normalize_runtime_pulse_entry(
                                        {
                                            "pulse_id": pulse_id,
                                            "name": pulse_name,
                                            "pulse_name": pulse_name,
                                            "pulse_address": pulse_address,
                                            "pulse_definition": row.get("pulse_definition"),
                                            "input_schema": row.get("input_schema") if isinstance(row.get("input_schema"), dict) else {},
                                        },
                                        default_name=str(pulse_name or ""),
                                        default_pulse_address=str(pulse_address or ""),
                                    )
                                )
                            meta["supported_pulses"] = supported
                            agent["meta"] = meta
                            summary = {
                                "agent_id": agent.get("agent_id"),
                                "name": agent.get("name") or card.get("name") or "Unnamed Pulser",
                                "address": card.get("address") or agent.get("address") or "",
                                "description": agent.get("description") or card.get("description") or "",
                                "owner": agent.get("owner") or card.get("owner") or "",
                                "meta": meta,
                                "last_active": float(agent.get("last_active") or 0),
                                "practices": card.get("practices") if isinstance(card.get("practices"), list) else [],
                                "plaza_name": self.agent_card.get("name", self.name),
                            }
                            register_pulser_summary(summary)

                    for agent in agents:
                        resolved_type = str(agent.get("pit_type") or "")
                        if resolved_type != "Pulse":
                            continue

                        card = agent.get("card") if isinstance(agent.get("card"), dict) else {}
                        meta = agent.get("meta") if isinstance(agent.get("meta"), dict) else {}
                        pulse_id = meta.get("pulse_id") or (meta.get("pulse_definition") or {}).get("id")
                        pulse_name = agent.get("name")
                        pulse_address = meta.get("pulse_address") or card.get("address") or agent.get("address")
                        available_pulsers: List[Dict[str, Any]] = []
                        seen_pulser_ids: Set[str] = set()
                        for row in pulse_pulser_rows:
                            row_pulse_id = str(row.get("pulse_id") or "").strip()
                            if pulse_id and row_pulse_id and row_pulse_id != str(pulse_id).strip():
                                continue
                            if pulse_name and not practice.state.contains(row.get("pulse_name"), pulse_name):
                                continue
                            if pulse_address and not practice.state.same_pit_ref(row.get("pulse_address"), pulse_address):
                                continue
                            summary = resolve_pulser_summary(row)
                            pulse_definition = resolve_pulse_definition(summary, row)
                            if not practice.state.pulse_definition_is_complete(pulse_definition):
                                continue
                            summary_key = str(
                                summary.get("agent_id")
                                or row.get("pulser_id")
                                or f"{summary.get('name') or ''}::{summary.get('address') or ''}"
                            ).strip().lower()
                            if not summary_key or summary_key in seen_pulser_ids:
                                continue
                            seen_pulser_ids.add(summary_key)
                            enriched_summary = dict(summary)
                            enriched_summary["pulse_definition"] = pulse_definition
                            available_pulsers.append(enriched_summary)

                        available_pulsers.sort(key=lambda item: str(item.get("name") or "").lower())
                        agent["available_pulser_count"] = len(available_pulsers)
                        agent["available_pulsers"] = available_pulsers
                status = {
                    "url": self.agent_card.get("address", f"http://{self.host}:{self.port}"),
                    "online": True,
                    "agents": agents,
                    "card": self.agent_card,
                }
                return {"status": "success", "plazas": [status]}

            return await run_in_threadpool(_plaza_status_sync)

        @self.app.post("/api/pulsers/test")
        async def run_pulser_test(request: PlazaPulserTestRequest):
            def _prepare_pulser_test_sync() -> Dict[str, Any]:
                practice = self._get_plaza_practice()
                if practice is None:
                    raise HTTPException(status_code=503, detail="Plaza practice is unavailable")

                candidates = practice.state.search_entries(
                    agent_id=request.pulser_id.strip() if request.pulser_id else None,
                    pit_type="Pulser",
                )
                if not candidates and request.pulser_name:
                    candidates = practice.state.search_entries(name=request.pulser_name.strip(), pit_type="Pulser")

                pulser_entry = None
                for candidate in candidates:
                    card = candidate.get("card") if isinstance(candidate.get("card"), dict) else {}
                    candidate_address = str(card.get("address") or candidate.get("address") or "").strip()
                    if request.pulser_address and candidate_address and candidate_address != request.pulser_address.strip():
                        continue
                    pulser_entry = candidate
                    break

                if pulser_entry is None:
                    raise HTTPException(status_code=404, detail="Pulser not found")

                card = pulser_entry.get("card") if isinstance(pulser_entry.get("card"), dict) else {}
                practices = card.get("practices") if isinstance(card.get("practices"), list) else []
                requested_practice_id = str(request.practice_id or "").strip() or "get_pulse_data"

                if practices and not any(p.get("id") == requested_practice_id for p in practices if isinstance(p, dict)):
                    raise HTTPException(status_code=400, detail=f"Practice '{requested_practice_id}' is not available on this pulser")

                target_address = str(card.get("address") or pulser_entry.get("address") or "").strip()
                target_agent_id = str(pulser_entry.get("agent_id") or card.get("agent_id") or "").strip()
                if not target_address or not target_agent_id:
                    raise HTTPException(status_code=400, detail="Pulser address or identity is missing")

                plaza_agent_id = str(self.agent_card.get("agent_id") or practice.state.agent_ids.get(self.name) or "").strip()
                plaza_url = str(self.agent_card.get("address") or f"http://{self.host}:{self.port}").rstrip("/")
                if not plaza_agent_id:
                    raise HTTPException(status_code=500, detail="Plaza identity is unavailable")

                caller_token = str(uuid.uuid4())
                practice.state.tokens[caller_token] = {
                    "agent_name": self.name,
                    "agent_id": plaza_agent_id,
                    "expires_at": time.time() + 60,
                }
                practice.state.agent_tokens[self.name] = caller_token

                content = request.input if isinstance(request.input, dict) else request.input or {}
                if requested_practice_id == "get_pulse_data":
                    content = {
                        "pulse_name": request.pulse_name,
                        "pulse_address": request.pulse_address,
                        "params": content if isinstance(content, dict) else {},
                        "output_schema": request.output_schema if isinstance(request.output_schema, dict) else {},
                    }

                payload = {
                    "sender": self.name,
                    "receiver": target_agent_id,
                    "content": content,
                    "msg_type": requested_practice_id,
                    "caller_agent_address": {
                        "pit_id": plaza_agent_id,
                        "plazas": [plaza_url],
                    },
                    "caller_plaza_token": caller_token,
                }
                return {
                    "practice": practice,
                    "target_address": target_address,
                    "target_agent_id": target_agent_id,
                    "requested_practice_id": requested_practice_id,
                    "caller_token": caller_token,
                    "payload": payload,
                }

            prepared = await run_in_threadpool(_prepare_pulser_test_sync)

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{prepared['target_address'].rstrip('/')}/use_practice/{prepared['requested_practice_id']}",
                        json=prepared["payload"],
                        timeout=30.0,
                    )
                data = response.json() if response.content else {}
                if response.status_code >= 400:
                    raise HTTPException(status_code=response.status_code, detail=data.get("detail") or "Pulser test failed")
                return {
                    "status": "success",
                    "practice_id": prepared["requested_practice_id"],
                    "result": data.get("result", data),
                }
            finally:
                prepared["practice"].state.tokens.pop(prepared["caller_token"], None)

        @self.app.on_event("startup")
        async def plaza_ui_auth_startup():
            await run_in_threadpool(self._bootstrap_default_admin_if_needed)

        @self.app.get("/api/ui_auth/config")
        async def ui_auth_config():
            def _config_sync() -> Dict[str, Any]:
                default_admin = self._find_ui_user_by_username(self.DEFAULT_ADMIN_USERNAME)
                return {
                    "status": "success",
                    "auth_enabled": self._has_supabase_auth(),
                    "service_role_enabled": self._has_supabase_service_role(),
                    "default_admin_ready": bool(default_admin),
                    "default_admin_error": self._ui_auth_bootstrap_error,
                    "roles": sorted(self.UI_USER_ROLES),
                    "oauth_providers": list(self.UI_OAUTH_PROVIDERS),
                    "identifier_label": "Username or email",
                }

            return await run_in_threadpool(_config_sync)

        @self.app.post("/api/ui_auth/signup")
        async def ui_auth_signup(request: PlazaUiSignUpRequest):
            def _signup_sync() -> Dict[str, Any]:
                username = self._resolve_signup_username(
                    username=request.username,
                    email=request.email,
                )
                email = self._resolve_signup_email(username=username, email=request.email)
                auth_response = self._create_password_user(
                    username=username,
                    email=email,
                    password=request.password,
                    display_name=request.display_name,
                )
                user_payload = auth_response.get("user") or {}
                if not user_payload.get("id"):
                    raise HTTPException(status_code=502, detail="Supabase sign-up returned no user payload")
                preferred_role = "user"
                if not self._has_supabase_service_role() and not self._list_ui_users():
                    preferred_role = "admin"
                profile = self._sync_ui_user_profile(
                    user_payload,
                    preferred_role=preferred_role,
                    username=username,
                    display_name=request.display_name,
                    auth_provider="password",
                    touch_sign_in=bool(auth_response.get("session")),
                )
                return {"status": "success", "session": auth_response.get("session"), "user": profile}

            return await run_in_threadpool(_signup_sync)

        @self.app.post("/api/ui_auth/signin")
        async def ui_auth_signin(request: PlazaUiSignInRequest):
            def _signin_sync() -> Dict[str, Any]:
                identifier = self._resolve_signin_identifier(
                    identifier=request.identifier,
                    username=request.username,
                    email=request.email,
                )
                if self._matches_default_admin_identity(identifier) and request.password == self.DEFAULT_ADMIN_PASSWORD:
                    self._bootstrap_default_admin_if_needed()
                email = self._resolve_password_signin_email(identifier)
                auth_response = self._supabase_sign_in(email=email, password=request.password)
                user_payload = auth_response.get("user") or {}
                if not user_payload.get("id"):
                    raise HTTPException(status_code=401, detail="Supabase sign-in returned no user")
                profile = self._sync_ui_user_profile(
                    user_payload,
                    username=identifier if "@" not in identifier else None,
                    auth_provider="password",
                    touch_sign_in=True,
                )
                if profile.get("status") == "disabled":
                    raise HTTPException(status_code=403, detail="This account is disabled")
                return {"status": "success", "session": auth_response.get("session"), "user": profile}

            return await run_in_threadpool(_signin_sync)

        @self.app.get("/api/ui_auth/oauth/{provider}/start")
        async def ui_auth_oauth_start(provider: str, request: Request):
            def _oauth_start_sync() -> RedirectResponse:
                next_path = self._normalize_auth_next_path(request.query_params.get("next"))
                redirect_url = self._build_oauth_redirect(provider=provider, next_path=next_path)
                return RedirectResponse(url=redirect_url, status_code=307)

            return await run_in_threadpool(_oauth_start_sync)

        @self.app.get("/api/ui_auth/oauth/callback", response_class=HTMLResponse)
        async def ui_auth_oauth_callback(request: Request):
            def _oauth_callback_sync() -> HTMLResponse:
                return self._handle_oauth_callback(dict(request.query_params))

            return await run_in_threadpool(_oauth_callback_sync)

        @self.app.get("/api/ui_auth/me")
        async def ui_auth_me(request: Request):
            def _me_sync() -> Dict[str, Any]:
                _, _, profile = self._get_authenticated_ui_context(request)
                return {"status": "success", "user": profile}

            return await run_in_threadpool(_me_sync)

        @self.app.post("/api/ui_auth/refresh")
        async def ui_auth_refresh(payload: PlazaUiRefreshRequest):
            def _refresh_sync() -> Dict[str, Any]:
                refresh_token = str(payload.refresh_token or "").strip()
                if not refresh_token:
                    raise HTTPException(status_code=400, detail="Refresh token is required")

                auth_response = self._supabase_refresh_session(refresh_token)
                session = auth_response.get("session") or {}
                access_token = str(session.get("access_token") or "").strip()
                user_payload = auth_response.get("user") or {}
                if not user_payload.get("id") and access_token:
                    user_payload = self._get_supabase_user(access_token)
                if not user_payload.get("id"):
                    raise HTTPException(status_code=401, detail="Supabase session refresh returned no user")

                profile = self._sync_ui_user_profile(user_payload)
                if profile.get("status") == "disabled":
                    raise HTTPException(status_code=403, detail="This account is disabled")
                return {"status": "success", "session": session, "user": profile}

            return await run_in_threadpool(_refresh_sync)

        @self.app.patch("/api/ui_auth/profile")
        async def ui_auth_update_profile(payload: PlazaUiProfileUpdateRequest, request: Request):
            def _update_profile_sync() -> Dict[str, Any]:
                access_token, user_payload, profile = self._get_authenticated_ui_context(request)
                current_display_name = str(profile.get("display_name") or "")
                next_display_name = current_display_name if payload.display_name is None else str(payload.display_name).strip()

                if next_display_name != current_display_name:
                    metadata = (
                        user_payload.get("user_metadata")
                        if isinstance(user_payload.get("user_metadata"), dict)
                        else {}
                    )
                    next_metadata = dict(metadata)
                    next_metadata["display_name"] = next_display_name
                    updated_user_payload = self._supabase_update_user(
                        access_token=access_token,
                        attributes={"data": next_metadata},
                    )
                else:
                    updated_user_payload = user_payload

                updated_profile = self._sync_ui_user_profile(
                    updated_user_payload,
                    display_name=next_display_name,
                )
                return {"status": "success", "user": updated_profile}

            return await run_in_threadpool(_update_profile_sync)

        @self.app.post("/api/ui_auth/password")
        async def ui_auth_change_password(payload: PlazaUiPasswordChangeRequest, request: Request):
            def _change_password_sync() -> Dict[str, Any]:
                access_token, user_payload, profile = self._get_authenticated_ui_context(request)
                if profile.get("auth_provider") != "password":
                    raise HTTPException(status_code=400, detail="Password changes are only available for password accounts")

                current_password = str(payload.current_password or "")
                new_password = str(payload.new_password or "")
                if not current_password or not new_password:
                    raise HTTPException(status_code=400, detail="Current and new passwords are required")
                if current_password == new_password:
                    raise HTTPException(status_code=400, detail="Choose a new password that is different from the current password")

                email = str(profile.get("email") or user_payload.get("email") or "").strip().lower()
                if not email:
                    raise HTTPException(status_code=400, detail="This account does not have an email address for password verification")

                try:
                    self._supabase_sign_in(email=email, password=current_password)
                except HTTPException as exc:
                    raise HTTPException(status_code=400, detail="Current password is incorrect") from exc

                updated_user_payload = self._supabase_update_user(
                    access_token=access_token,
                    attributes={"password": new_password},
                )
                updated_profile = self._sync_ui_user_profile(updated_user_payload)
                return {"status": "success", "message": "Password updated.", "user": updated_profile}

            return await run_in_threadpool(_change_password_sync)

        @self.app.post("/api/ui_auth/signout")
        async def ui_auth_signout():
            return {"status": "success"}

        @self.app.get("/api/ui_users")
        async def ui_list_users(request: Request):
            def _list_users_sync() -> Dict[str, Any]:
                actor = self._require_ui_user(request)
                if actor.get("role") == "admin":
                    users = self._list_ui_users()
                else:
                    users = [actor]
                return {"status": "success", "users": users, "viewer": actor}

            return await run_in_threadpool(_list_users_sync)

        @self.app.patch("/api/ui_users/{user_id}")
        async def ui_update_user(user_id: str, payload: PlazaUiUserUpdateRequest, request: Request):
            def _update_user_sync() -> Dict[str, Any]:
                actor = self._require_ui_user(request)
                target = self._get_ui_user(user_id)
                if target is None:
                    raise HTTPException(status_code=404, detail="User not found")

                self._assert_ui_user_update_allowed(actor, target, payload)

                next_role = payload.role or target.get("role", "user")
                next_status = payload.status or target.get("status", "active")
                next_name = payload.display_name if payload.display_name is not None else target.get("display_name", "")

                updated = self._upsert_ui_user(
                    user_id=user_id,
                    username=target.get("username", ""),
                    email=target.get("email", ""),
                    display_name=next_name,
                    role=next_role,
                    status=next_status,
                    auth_provider=target.get("auth_provider", "password"),
                    created_at=target.get("created_at"),
                    last_sign_in_at=target.get("last_sign_in_at"),
                )
                return {"status": "success", "user": updated}

            return await run_in_threadpool(_update_user_sync)

        @self.app.get("/api/phemas")
        async def list_phemas():
            phemas = await run_in_threadpool(self._list_phemas)
            return {"status": "success", "phemas": phemas}

        @self.app.get("/api/phemas/{phema_id}")
        async def get_phema(phema_id: str):
            row = await run_in_threadpool(self._get_phema_row, phema_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Phema not found")
            return {"status": "success", "phema": row}

        @self.app.post("/api/phemas")
        async def save_phema(request: PlazaPhemaUpsertRequest):
            try:
                saved = await run_in_threadpool(self._save_phema, request.phema)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {"status": "success", "phema": saved}

        @self.app.delete("/api/phemas/{phema_id}")
        async def delete_phema(phema_id: str):
            await run_in_threadpool(self._delete_phema, phema_id)
            return {"status": "success", "phema_id": phema_id}

        @self.app.get("/api/site-settings")
        async def get_site_settings():
            practice = self._get_plaza_practice()
            if not practice:
                return {"status": "error", "message": "Plaza practice not loaded"}
            return {"status": "success", "settings": practice.state.site_settings}

        @self.app.post("/api/site-settings")
        async def post_site_settings(settings: Dict[str, Any], request: Request):
            # In a production system, we'd check for admin role here.
            # self._require_ui_user(request, role="admin")
            practice = self._get_plaza_practice()
            if not practice:
                raise HTTPException(status_code=503, detail="Plaza practice not loaded")
            
            await run_in_threadpool(practice.state.save_site_settings, settings)
            return {"status": "success", "settings": practice.state.site_settings}

        @self.app.get("/api/agent_configs")
        async def list_agent_configs(request: Request):
            query = str(request.query_params.get("q") or "").strip()
            name = str(request.query_params.get("name") or "").strip()
            owner = str(request.query_params.get("owner") or "").strip()
            role = str(request.query_params.get("role") or "").strip()
            agent_type = str(request.query_params.get("agent_type") or "").strip()
            include_config = str(request.query_params.get("include_config") or "").strip().lower() in {"1", "true", "yes"}
            configs = await run_in_threadpool(
                self._list_agent_configs,
                query,
                name,
                owner,
                role,
                agent_type,
                include_config,
            )
            return {"status": "success", "agent_configs": configs}

        @self.app.get("/api/agent_configs/{config_id}")
        async def get_agent_config(config_id: str):
            config = await run_in_threadpool(self._get_agent_config, config_id)
            if config is None:
                raise HTTPException(status_code=404, detail="Agent config not found")
            return {"status": "success", "agent_config": config}

        @self.app.post("/api/agent_configs")
        async def save_agent_config(request: PlazaAgentConfigUpsertRequest):
            try:
                saved = await run_in_threadpool(
                    self._save_agent_config,
                    request.config,
                    str(request.config_id or "").strip(),
                    str(request.owner or "").strip(),
                    str(request.name or "").strip(),
                    str(request.description or "").strip(),
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return {"status": "success", "agent_config": saved}

        @self.app.post("/api/agent_configs/{config_id}/launch")
        async def launch_agent_config(config_id: str, request: PlazaAgentConfigLaunchRequest):
            try:
                launch = await run_in_threadpool(
                    self._launch_agent_config,
                    config_id=config_id,
                    config=request.config if isinstance(request.config, dict) else None,
                    owner=str(request.owner or "").strip(),
                    name=str(request.name or "").strip(),
                    description=str(request.description or "").strip(),
                    agent_name=str(request.agent_name or "").strip(),
                    host=str(request.host or "").strip(),
                    port=request.port,
                    pool_type=str(request.pool_type or "").strip(),
                    pool_location=str(request.pool_location or "").strip(),
                    wait_for_health_sec=float(request.wait_for_health_sec or 15.0),
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            return {"status": "success", "launch": launch}

        @self.app.post("/api/agent_configs/launch")
        async def launch_agent_config_from_payload(request: PlazaAgentConfigLaunchRequest):
            try:
                launch = await run_in_threadpool(
                    self._launch_agent_config,
                    config_id=str(request.config_id or "").strip(),
                    config=request.config if isinstance(request.config, dict) else None,
                    owner=str(request.owner or "").strip(),
                    name=str(request.name or "").strip(),
                    description=str(request.description or "").strip(),
                    agent_name=str(request.agent_name or "").strip(),
                    host=str(request.host or "").strip(),
                    port=request.port,
                    pool_type=str(request.pool_type or "").strip(),
                    pool_location=str(request.pool_location or "").strip(),
                    wait_for_health_sec=float(request.wait_for_health_sec or 15.0),
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            except RuntimeError as exc:
                raise HTTPException(status_code=500, detail=str(exc)) from exc
            return {"status": "success", "launch": launch}

        @self.app.get("/.well-known/agent-card")
        async def get_agent_card():
            return self.agent_card

    def add_practice(self, practice):
        super().add_practice(practice)
        if isinstance(practice, PlazaPractice):
            self.plaza_practice = practice

    def _get_plaza_practice(self) -> Optional[PlazaPractice]:
        if self.plaza_practice is not None:
            return self.plaza_practice
        for practice in self.practices:
            if isinstance(practice, PlazaPractice):
                self.plaza_practice = practice
                break
        return self.plaza_practice

    def _ensure_phemas_table(self):
        if not self.pool:
            return
        if self.pool._TableExists(self.PHEMA_TABLE):
            return
        self.pool._CreateTable(self.PHEMA_TABLE, phemas_table_schema())

    def _list_agent_configs(
        self,
        query: str = "",
        name: str = "",
        owner: str = "",
        role: str = "",
        agent_type: str = "",
        include_config: bool = False,
    ) -> List[Dict[str, Any]]:
        return self.agent_config_store.search(
            query=query,
            name=name,
            owner=owner,
            role=role,
            agent_type=agent_type,
            include_config=include_config,
        )

    def _get_agent_config(self, config_id: str) -> Optional[Dict[str, Any]]:
        return self.agent_config_store.get(config_id, include_config=True)

    def _save_agent_config(
        self,
        config: Dict[str, Any],
        config_id: str = "",
        owner: str = "",
        name: str = "",
        description: str = "",
    ) -> Dict[str, Any]:
        return self.agent_config_store.upsert(
            config,
            config_id=config_id,
            owner=owner,
            name=name,
            description=description,
        )

    def _launch_agent_config(
        self,
        *,
        config_id: str = "",
        config: Optional[Dict[str, Any]] = None,
        owner: str = "",
        name: str = "",
        description: str = "",
        agent_name: str = "",
        host: str = "",
        port: Optional[int] = None,
        pool_type: str = "",
        pool_location: str = "",
        wait_for_health_sec: float = 15.0,
    ) -> Dict[str, Any]:
        config_row: Optional[Dict[str, Any]] = None
        if isinstance(config, dict):
            config_row = self.agent_config_store.upsert(
                config,
                config_id=config_id,
                owner=owner,
                name=name,
                description=description,
            )
        elif config_id:
            config_row = self.agent_config_store.get(config_id, include_config=True)

        if config_row is None:
            raise ValueError("Agent config not found.")

        runtime_plaza_url = "" if AgentConfigStore._is_plaza_config(config_row.get("config") or {}) else self._get_public_ui_url()
        effective_agent_name = (
            str(agent_name or "").strip()
            or str(config_row.get("name") or "").strip()
            or str((config_row.get("config") or {}).get("name") or "").strip()
        )
        credentials = (
            self.plaza_credential_store.load(agent_name=effective_agent_name, plaza_url=runtime_plaza_url)
            if effective_agent_name and runtime_plaza_url
            else None
        )
        active_agent = self._lookup_active_agent_entry(
            agent_name=effective_agent_name,
            agent_id=str((credentials or {}).get("agent_id") or "").strip(),
        )
        if active_agent is not None:
            return {
                "status": "already_running",
                "config_id": str(config_row.get("id") or ""),
                "agent_config": self.agent_config_store.get(str(config_row.get("id") or ""), include_config=False),
                "existing_agent": active_agent,
                "used_existing_identity": bool(credentials and credentials.get("agent_id") and credentials.get("api_key")),
            }

        launch = self.agent_launch_manager.launch_config(
            config_row,
            plaza_url=runtime_plaza_url,
            host=host,
            port=port,
            agent_name=effective_agent_name,
            pool_type=pool_type,
            pool_location=pool_location,
            credentials=credentials,
            wait_for_health_sec=wait_for_health_sec,
        )
        launch["status"] = "running"
        launch["agent_config"] = self.agent_config_store.get(str(config_row.get("id") or ""), include_config=False)
        launch["requested_agent_name"] = effective_agent_name
        return launch

    def _lookup_active_agent_entry(self, *, agent_name: str = "", agent_id: str = "") -> Optional[Dict[str, Any]]:
        practice = self._get_plaza_practice()
        if practice is None:
            return None

        candidates: List[Dict[str, Any]] = []
        if agent_id:
            candidates.extend(
                practice.state.search_entries(
                    agent_id=agent_id,
                    use_persisted_fallback=False,
                )
            )
        if agent_name:
            candidates.extend(
                practice.state.search_entries(
                    name=agent_name,
                    use_persisted_fallback=False,
                )
            )

        exact_name = str(agent_name or "").strip().lower()
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            candidate_id = str(candidate.get("agent_id") or "").strip()
            candidate_name = str(candidate.get("name") or "").strip().lower()
            if agent_id and candidate_id and candidate_id != agent_id:
                continue
            if exact_name and candidate_name and candidate_name != exact_name:
                continue
            if not BaseAgent._heartbeat_is_active(candidate.get("last_active")):
                continue
            return {
                "agent_id": candidate_id,
                "name": str(candidate.get("name") or "").strip(),
                "description": str(candidate.get("description") or "").strip(),
                "owner": str(candidate.get("owner") or "").strip(),
                "address": str((candidate.get("card") or {}).get("address") or candidate.get("address") or "").strip(),
                "pit_type": str(candidate.get("pit_type") or candidate.get("type") or "").strip(),
                "last_active": float(candidate.get("last_active") or 0),
            }
        return None

    @staticmethod
    def _normalize_phema_row(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(row, dict):
            return None
        phema_id = str(row.get("id") or row.get("phema_id") or row.get("agent_id") or "").strip()
        if not phema_id:
            return None
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        sections = row.get("sections") if isinstance(row.get("sections"), list) else []
        tags = row.get("tags") if isinstance(row.get("tags"), list) else []
        input_schema = row.get("input_schema") if isinstance(row.get("input_schema"), dict) else {}
        resolution_mode = Phema.infer_resolution_mode(
            sections=sections,
            meta=meta,
            explicit_mode=row.get("resolution_mode"),
        )
        meta = {**meta, "resolution_mode": resolution_mode}
        registration_mode = str(meta.get("registration_mode") or "hosted").strip().lower() or "hosted"
        if registration_mode not in {"hosted", "info_only"}:
            registration_mode = "hosted"
        return {
            "id": phema_id,
            "phema_id": phema_id,
            "name": str(row.get("name") or "").strip(),
            "description": str(row.get("description") or ""),
            "owner": str(row.get("owner") or ""),
            "address": str(row.get("address") or ""),
            "pit_type": "Phema",
            "tags": [str(tag) for tag in tags if str(tag).strip()],
            "input_schema": input_schema,
            "sections": sections,
            "resolution_mode": resolution_mode,
            "meta": meta,
            "registration_mode": registration_mode,
            "hosted_on_plaza": registration_mode == "hosted",
            "downloadable": bool(meta.get("downloadable")) if "downloadable" in meta else registration_mode == "hosted",
            "host_phemar_name": str(meta.get("host_phemar_name") or meta.get("registered_by_phemar") or ""),
            "host_phemar_agent_id": str(meta.get("host_phemar_agent_id") or meta.get("registered_by_agent_id") or ""),
            "host_phemar_pit_address": meta.get("host_phemar_pit_address") if isinstance(meta.get("host_phemar_pit_address"), dict) else {},
            "phema_pit_address": meta.get("phema_pit_address") if isinstance(meta.get("phema_pit_address"), dict) else {},
            "access_practice_id": str(meta.get("access_practice_id") or "generate_phema"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def _list_phemas(self) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if self.pool:
            self._ensure_phemas_table()
            rows = self.pool._GetTableData(self.PHEMA_TABLE) or []
        rows.extend(list(self._phema_cache.values()))
        normalized = []
        seen = set()
        for row in rows:
            item = self._normalize_phema_row(row)
            if not item or item["id"] in seen:
                continue
            seen.add(item["id"])
            normalized.append(item)
        return sorted(normalized, key=lambda item: (item.get("name") or item["id"]).lower())

    def _get_phema_row(self, phema_id: str) -> Optional[Dict[str, Any]]:
        if not phema_id:
            return None
        if self.pool:
            self._ensure_phemas_table()
            rows = self.pool._GetTableData(self.PHEMA_TABLE, {"id": phema_id}) or []
            if rows:
                return self._normalize_phema_row(rows[-1])
        cached = self._phema_cache.get(phema_id)
        return self._normalize_phema_row(cached) if cached else None

    def _delete_pool_row(self, table_name: str, row_id: str):
        if not self.pool or not row_id:
            return

        tables = getattr(self.pool, "tables", None)
        if isinstance(tables, dict):
            table = tables.get(table_name)
            if isinstance(table, dict):
                table.pop(row_id, None)
                return

        root_path = getattr(self.pool, "root_path", None)
        if isinstance(root_path, str) and root_path:
            safe_id = self.pool._safe_item_id(row_id) if hasattr(self.pool, "_safe_item_id") else row_id
            file_path = os.path.join(root_path, table_name, f"{safe_id}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
            return

        conn = getattr(self.pool, "conn", None)
        cursor = getattr(self.pool, "cursor", None)
        if conn is not None and cursor is not None:
            cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (row_id,))
            conn.commit()
            return

        supabase = getattr(self.pool, "supabase", None)
        if supabase is not None:
            supabase.table(table_name).delete().eq("id", row_id).execute()

    def _build_phema_registry_card(self, phema: Phema, row: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self._normalize_phema_row(row) or {}
        registration_mode = str(normalized.get("registration_mode") or "hosted")
        base_meta = dict(normalized.get("meta") or {})
        base_meta.setdefault("registration_mode", registration_mode)
        base_meta.setdefault("hosted_on_plaza", registration_mode == "hosted")
        base_meta.setdefault("downloadable", registration_mode == "hosted")
        base_meta.setdefault("access_practice_id", "generate_phema")
        base_meta.setdefault("phema_pit_address", phema.address.to_dict())
        include_details = registration_mode == "hosted"
        if include_details:
            base_meta["input_schema"] = dict(normalized.get("input_schema") or {})
            base_meta["sections"] = list(normalized.get("sections") or [])
        else:
            base_meta.pop("input_schema", None)
            base_meta.pop("sections", None)
        return phema.to_card(
            self.agent_card.get("address", ""),
            include_details=include_details,
            extra_meta=base_meta,
        )

    def _sync_phema_registry(self, phema: Phema, row: Dict[str, Any], previous_name: str = ""):
        practice = self._get_plaza_practice()
        if practice is None:
            return
        state = practice.state
        card = self._build_phema_registry_card(phema, row)
        if previous_name and previous_name != phema.name and state.agent_ids.get(previous_name) == phema.phema_id:
            state.agent_ids.pop(previous_name, None)
        state.agent_cards[phema.phema_id] = card
        state.pit_types[phema.phema_id] = "Phema"
        state.agent_names_by_id[phema.phema_id] = phema.name
        state.agent_ids[phema.name] = phema.phema_id
        state.last_active[phema.phema_id] = time.time()
        state.upsert_directory_entry(phema.phema_id, phema.name, phema.resolved_address, "Phema", card)

    def _remove_phema_registry(self, phema_id: str, phema_name: str = ""):
        practice = self._get_plaza_practice()
        if practice is None:
            return
        state = practice.state
        resolved_name = phema_name or state.agent_names_by_id.get(phema_id, "")
        if resolved_name and state.agent_ids.get(resolved_name) == phema_id:
            state.agent_ids.pop(resolved_name, None)
        state.agent_cards.pop(phema_id, None)
        state.pit_types.pop(phema_id, None)
        state.agent_names_by_id.pop(phema_id, None)
        state.last_active.pop(phema_id, None)
        if state.directory_pool:
            self._delete_pool_row(state.DIRECTORY_TABLE, phema_id)

    def _save_phema(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Phema payload must be an object.")

        normalized_payload = dict(payload)
        existing_id = str(normalized_payload.get("phema_id") or normalized_payload.get("id") or normalized_payload.get("agent_id") or "").strip()
        existing = self._get_phema_row(existing_id) if existing_id else None
        if not existing_id:
            generated_id = str(uuid.uuid4())
            normalized_payload["phema_id"] = generated_id
            existing_id = generated_id
        elif existing is not None:
            normalized_payload.setdefault("address", existing.get("address", ""))
        phema = Phema.from_dict(normalized_payload)
        if not phema.name:
            raise ValueError("Phema name is required.")
        registration_mode = str((normalized_payload.get("meta") or {}).get("registration_mode") or "hosted").strip().lower() or "hosted"
        if registration_mode not in {"hosted", "info_only"}:
            registration_mode = "hosted"
        host_phemar_pit_address = (normalized_payload.get("meta") or {}).get("host_phemar_pit_address")
        if not isinstance(host_phemar_pit_address, dict):
            host_phemar_pit_address = {}

        now = datetime.now(timezone.utc).isoformat()
        row_meta = {
            **dict(phema.meta),
            "resolution_mode": phema.resolution_mode,
            "registration_mode": registration_mode,
            "hosted_on_plaza": registration_mode == "hosted",
            "downloadable": registration_mode == "hosted",
            "host_phemar_name": str(phema.meta.get("host_phemar_name") or phema.meta.get("registered_by_phemar") or ""),
            "host_phemar_agent_id": str(phema.meta.get("host_phemar_agent_id") or phema.meta.get("registered_by_agent_id") or ""),
            "host_phemar_pit_address": host_phemar_pit_address,
            "phema_pit_address": phema.address.to_dict(),
            "access_practice_id": str(phema.meta.get("access_practice_id") or "generate_phema"),
        }
        row = {
            "id": phema.phema_id,
            "name": phema.name,
            "description": phema.description,
            "owner": phema.owner,
            "address": phema.resolved_address,
            "tags": list(phema.tags),
            "input_schema": dict(phema.input_schema) if registration_mode == "hosted" else {},
            "sections": [section.to_dict() for section in phema.sections] if registration_mode == "hosted" else [],
            "resolution_mode": phema.resolution_mode,
            "meta": row_meta,
            "created_at": existing.get("created_at") if existing else now,
            "updated_at": now,
        }

        self._phema_cache[phema.phema_id] = dict(row)
        if self.pool:
            self._ensure_phemas_table()
            persisted = self.pool._Insert(self.PHEMA_TABLE, row)
            if persisted is False:
                logger.warning("[Plaza] Failed persisting Phema %s to pool; keeping cached/registered copy", phema.phema_id)

        self._sync_phema_registry(phema, row, previous_name=existing.get("name", "") if existing else "")
        return self._normalize_phema_row(row) or row

    def _delete_phema(self, phema_id: str):
        existing = self._get_phema_row(phema_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Phema not found")
        self._phema_cache.pop(phema_id, None)
        if self.pool:
            self._delete_pool_row(self.PHEMA_TABLE, phema_id)
        self._remove_phema_registry(phema_id, phema_name=existing.get("name", ""))

    def _get_supabase_pool_config(self) -> Optional[Dict[str, str]]:
        url = (
            getattr(self.pool, "url", None)
            or os.getenv("PLAZA_SUPABASE_URL")
            or os.getenv("SUPABASE_URL")
        )
        key = (
            getattr(self.pool, "key", None)
            or os.getenv("PLAZA_SUPABASE_PUBLISHABLE_KEY")
            or os.getenv("SUPABASE_PUBLISHABLE_KEY")
            or os.getenv("PLAZA_SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        )
        if not url or not key:
            return None
        return {"url": url, "key": key}

    def _has_supabase_auth(self) -> bool:
        return self._get_supabase_pool_config() is not None

    def _has_supabase_service_role(self) -> bool:
        return bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("PLAZA_SUPABASE_SERVICE_ROLE_KEY"))

    def _get_public_ui_url(self) -> str:
        return self._normalize_url(
            os.getenv("PROMPITS_PUBLIC_URL")
            or self.agent_card.get("address")
            or f"http://{self.host}:{self.port}"
        )

    def _normalize_auth_next_path(self, value: Optional[str]) -> str:
        next_path = str(value or "/plazas").strip() or "/plazas"
        if not next_path.startswith("/") or next_path.startswith("//"):
            return "/plazas"
        return next_path

    def _ui_auth_email_domain(self) -> str:
        domain = str(
            os.getenv("PLAZA_AUTH_EMAIL_DOMAIN")
            or os.getenv("PROMPITS_AUTH_EMAIL_DOMAIN")
            or self.DEFAULT_AUTH_EMAIL_DOMAIN
        ).strip().lower()
        return domain or self.DEFAULT_AUTH_EMAIL_DOMAIN

    def _build_username_email(self, username: str) -> str:
        return f"{self._normalize_username(username)}@{self._ui_auth_email_domain()}"

    def _username_from_email(self, email: Optional[str]) -> str:
        candidate = str(email or "").strip().split("@", 1)[0]
        return self._normalize_username(candidate, allow_empty=True)

    def _normalize_username(self, value: Optional[str], *, allow_empty: bool = False) -> str:
        lowered = str(value or "").strip().lower()
        lowered = re.sub(r"[^a-z0-9._-]+", "-", lowered)
        lowered = lowered.strip("._-")
        if len(lowered) > 32:
            lowered = lowered[:32].strip("._-")
        if not lowered:
            if allow_empty:
                return ""
            raise HTTPException(status_code=400, detail="Username is required")
        if len(lowered) < 3:
            raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
        if not self.USERNAME_PATTERN.match(lowered):
            raise HTTPException(status_code=400, detail="Username can only contain letters, numbers, dots, dashes, and underscores")
        return lowered

    def _resolve_signup_username(self, *, username: Optional[str], email: Optional[str]) -> str:
        if username:
            return self._normalize_username(username)
        derived = self._username_from_email(email)
        if derived:
            return derived
        raise HTTPException(status_code=400, detail="Username is required")

    def _resolve_signup_email(self, *, username: str, email: Optional[str]) -> str:
        value = str(email or "").strip().lower()
        if value:
            return value
        return self._build_username_email(username)

    def _resolve_signin_identifier(
        self,
        *,
        identifier: Optional[str],
        username: Optional[str],
        email: Optional[str],
    ) -> str:
        value = str(identifier or username or email or "").strip()
        if not value:
            raise HTTPException(status_code=400, detail="Username or email is required")
        return value

    def _matches_default_admin_identity(self, identifier: Optional[str]) -> bool:
        normalized = str(identifier or "").strip().lower()
        if not normalized:
            return False
        return normalized in {
            self.DEFAULT_ADMIN_USERNAME,
            self._build_username_email(self.DEFAULT_ADMIN_USERNAME),
        }

    def _supabase_http_timeout_seconds(self) -> float:
        raw_value = str(
            os.getenv("PLAZA_SUPABASE_TIMEOUT_SEC")
            or os.getenv("SUPABASE_HTTP_TIMEOUT_SEC")
            or "12"
        ).strip()
        try:
            timeout = float(raw_value)
        except (TypeError, ValueError):
            timeout = 12.0
        return max(3.0, timeout)

    def _get_supabase_http_client(self) -> httpx.Client:
        timeout_seconds = self._supabase_http_timeout_seconds()
        if self._supabase_http_client is None or self._supabase_http_timeout_cache != timeout_seconds:
            if self._supabase_http_client is not None:
                try:
                    self._supabase_http_client.close()
                except Exception:
                    pass
            self._supabase_http_timeout_cache = timeout_seconds
            self._supabase_http_client = httpx.Client(
                timeout=httpx.Timeout(timeout=timeout_seconds, connect=min(timeout_seconds, 5.0))
            )
        return self._supabase_http_client

    def _supabase_http_headers(
        self,
        *,
        use_service_role: bool = False,
        access_token: Optional[str] = None,
    ) -> Dict[str, str]:
        config = self._get_supabase_pool_config()
        if config is None:
            raise HTTPException(status_code=501, detail="Supabase auth is unavailable for this Plaza")

        if use_service_role:
            api_key = os.getenv("PLAZA_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            if not api_key:
                raise HTTPException(status_code=501, detail="Supabase service-role auth is unavailable for this Plaza")
        else:
            api_key = (
                os.getenv("PLAZA_SUPABASE_PUBLISHABLE_KEY")
                or os.getenv("SUPABASE_PUBLISHABLE_KEY")
                or config["key"]
            )

        headers = {
            "apikey": api_key,
            "Content-Type": "application/json",
        }
        bearer = access_token or (api_key if use_service_role else None)
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"
        return headers

    @staticmethod
    def _supabase_error_detail(payload: Any, fallback: str) -> str:
        if isinstance(payload, dict):
            for key in ("msg", "message", "error_description", "error"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        text = str(fallback or "").strip()
        return text or "Unexpected Supabase response"

    def _supabase_auth_request(
        self,
        method: str,
        path: str,
        *,
        use_service_role: bool = False,
        access_token: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        error_prefix: str = "Supabase request failed",
    ) -> Dict[str, Any]:
        config = self._get_supabase_pool_config()
        if config is None:
            raise HTTPException(status_code=501, detail="Supabase auth is unavailable for this Plaza")

        url = f"{config['url'].rstrip('/')}/auth/v1/{path.lstrip('/')}"
        try:
            response = self._get_supabase_http_client().request(
                method,
                url,
                headers=self._supabase_http_headers(
                    use_service_role=use_service_role,
                    access_token=access_token,
                ),
                params=params,
                json=json_body,
            )
        except httpx.TimeoutException as exc:
            raise HTTPException(status_code=504, detail=f"{error_prefix}: timed out") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"{error_prefix}: {exc}") from exc

        payload: Dict[str, Any] = {}
        if response.content:
            try:
                payload = response.json()
            except ValueError:
                payload = {}

        if response.status_code >= 400:
            detail = self._supabase_error_detail(payload, response.text or response.reason_phrase)
            raise HTTPException(status_code=response.status_code, detail=f"{error_prefix}: {detail}")
        return payload

    def _normalize_supabase_auth_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        user_payload = self._model_to_dict(payload.get("user") or {})
        session_payload = self._model_to_dict(payload.get("session") or {})
        if not session_payload and payload.get("access_token") and payload.get("refresh_token"):
            session_payload = {
                key: value
                for key, value in payload.items()
                if key
                in {
                    "access_token",
                    "refresh_token",
                    "expires_in",
                    "expires_at",
                    "token_type",
                    "provider_token",
                    "provider_refresh_token",
                    "weak_password",
                }
            }
        return {
            "user": user_payload,
            "session": session_payload,
        }

    def _create_supabase_admin_user(self, attributes: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._supabase_auth_request(
            "POST",
            "admin/users",
            use_service_role=True,
            json_body=attributes,
            error_prefix="Supabase admin user creation failed",
        )
        return self._model_to_dict(payload.get("user") or payload)

    def _build_supabase_client(self, use_service_role: bool = False):
        config = self._get_supabase_pool_config()
        if config is None:
            raise HTTPException(status_code=501, detail="Supabase auth is unavailable for this Plaza")
        from supabase import create_client

        key = config["key"]
        if use_service_role:
            key = os.getenv("PLAZA_SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY") or key
        else:
            key = os.getenv("PLAZA_SUPABASE_PUBLISHABLE_KEY") or os.getenv("SUPABASE_PUBLISHABLE_KEY") or key
        options = None
        try:
            from supabase.lib.client_options import ClientOptions

            timeout_seconds = self._supabase_http_timeout_seconds()
            options = ClientOptions(
                httpx_client=self._get_supabase_http_client(),
                postgrest_client_timeout=timeout_seconds,
                storage_client_timeout=timeout_seconds,
                function_client_timeout=min(timeout_seconds, 10.0),
            )
        except Exception:
            options = None

        if options is None:
            return create_client(config["url"], key)
        return create_client(config["url"], key, options=options)

    def _extract_bearer_token(self, request: Request) -> str:
        header = request.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            raise HTTPException(status_code=401, detail="Missing bearer token")
        token = header[len(prefix):].strip()
        if not token:
            raise HTTPException(status_code=401, detail="Missing bearer token")
        return token

    @staticmethod
    def _model_to_dict(value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _normalize_auth_response(self, response: Any) -> Dict[str, Any]:
        user = getattr(response, "user", None)
        session = getattr(response, "session", None)
        return {
            "user": self._model_to_dict(user),
            "session": self._model_to_dict(session),
        }

    def _normalize_user_response(self, response: Any) -> Dict[str, Any]:
        return self._model_to_dict(getattr(response, "user", None))

    def _supabase_sign_up(
        self,
        email: str,
        password: str,
        display_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        auth_metadata = dict(metadata or {})
        if display_name and not auth_metadata.get("display_name"):
            auth_metadata["display_name"] = display_name
        payload: Dict[str, Any] = {
            "email": email,
            "password": password,
            "data": auth_metadata,
            "gotrue_meta_security": {"captcha_token": None},
        }
        response = self._supabase_auth_request(
            "POST",
            "signup",
            json_body=payload,
            error_prefix="Supabase sign-up failed",
        )
        return self._normalize_supabase_auth_payload(response)

    def _create_password_user(
        self,
        *,
        username: str,
        email: str,
        password: str,
        display_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        existing_username = self._find_ui_user_by_username(username)
        if existing_username is not None:
            raise HTTPException(status_code=400, detail=f"Username '{username}' already exists")

        metadata = {
            "username": username,
            "auth_provider": "password",
        }
        if display_name:
            metadata["display_name"] = display_name

        if self._has_supabase_service_role():
            try:
                created = self._create_supabase_admin_user(
                    {
                        "email": email,
                        "password": password,
                        "email_confirm": True,
                        "user_metadata": metadata,
                    }
                )
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, str) else "Supabase sign-up failed"
                raise HTTPException(status_code=400, detail=detail) from exc

            auth_response = self._supabase_sign_in(email=email, password=password)
            if not auth_response.get("user"):
                auth_response["user"] = self._model_to_dict(created)
            return auth_response

        return self._supabase_sign_up(
            email=email,
            password=password,
            display_name=display_name,
            metadata=metadata,
        )

    def _supabase_sign_in(self, email: str, password: str) -> Dict[str, Any]:
        response = self._supabase_auth_request(
            "POST",
            "token",
            params={"grant_type": "password"},
            json_body={
                "email": email,
                "password": password,
                "data": {},
                "gotrue_meta_security": {"captcha_token": None},
            },
            error_prefix="Supabase sign-in failed",
        )
        return self._normalize_supabase_auth_payload(response)

    def _supabase_exchange_code_for_session(
        self,
        *,
        auth_code: str,
        code_verifier: str,
        redirect_to: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "auth_code": auth_code,
            "code_verifier": code_verifier,
        }
        if redirect_to:
            payload["redirect_to"] = redirect_to
        response = self._supabase_auth_request(
            "POST",
            "token",
            params={"grant_type": "pkce"},
            json_body=payload,
            error_prefix="Supabase OAuth sign-in failed",
        )
        return self._normalize_supabase_auth_payload(response)

    def _supabase_refresh_session(self, refresh_token: str) -> Dict[str, Any]:
        response = self._supabase_auth_request(
            "POST",
            "token",
            params={"grant_type": "refresh_token"},
            json_body={"refresh_token": refresh_token},
            error_prefix="Supabase session refresh failed",
        )
        return self._normalize_supabase_auth_payload(response)

    def _supabase_update_user(self, *, access_token: str, attributes: Dict[str, Any]) -> Dict[str, Any]:
        response = self._supabase_auth_request(
            "PUT",
            "user",
            access_token=access_token,
            json_body=attributes,
            error_prefix="Supabase user update failed",
        )
        user_payload = self._model_to_dict(response.get("user") or response)
        if user_payload.get("id"):
            return user_payload
        return self._get_supabase_user(access_token)

    def _get_supabase_user(self, access_token: str) -> Dict[str, Any]:
        response = self._supabase_auth_request(
            "GET",
            "user",
            access_token=access_token,
            error_prefix="Supabase token verification failed",
        )
        user_payload = self._model_to_dict(response.get("user") or response)
        if not user_payload.get("id"):
            raise HTTPException(status_code=401, detail="Supabase token did not resolve to a user")
        return user_payload

    def _build_oauth_callback_url(self) -> str:
        return f"{self._get_public_ui_url()}/api/ui_auth/oauth/callback"

    def _cleanup_oauth_states(self):
        cutoff = time.time() - 600
        with self._oauth_state_lock:
            expired = [key for key, value in self._oauth_states.items() if float(value.get("created_at", 0)) < cutoff]
            for key in expired:
                self._oauth_states.pop(key, None)

    def _build_oauth_redirect(self, *, provider: str, next_path: str) -> str:
        normalized_provider = str(provider or "").strip().lower()
        if normalized_provider not in self.UI_OAUTH_PROVIDERS:
            raise HTTPException(status_code=404, detail=f"Unsupported OAuth provider '{provider}'")
        if not self._has_supabase_auth():
            raise HTTPException(status_code=501, detail="Supabase auth is unavailable for this Plaza")

        from supabase_auth.helpers import generate_pkce_challenge, generate_pkce_verifier

        state = uuid.uuid4().hex
        code_verifier = generate_pkce_verifier()
        code_challenge = generate_pkce_challenge(code_verifier)
        redirect_to = self._build_oauth_callback_url()
        params = {
            "provider": normalized_provider,
            "redirect_to": redirect_to,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "plain" if code_verifier == code_challenge else "s256",
        }
        config = self._get_supabase_pool_config()
        if config is None:
            raise HTTPException(status_code=501, detail="Supabase auth is unavailable for this Plaza")

        self._cleanup_oauth_states()
        with self._oauth_state_lock:
            self._oauth_states[state] = {
                "code_verifier": code_verifier,
                "created_at": time.time(),
                "next_path": self._normalize_auth_next_path(next_path),
                "provider": normalized_provider,
                "redirect_to": redirect_to,
            }
        return f"{config['url'].rstrip('/')}/auth/v1/authorize?{urlencode(params)}"

    def _render_oauth_callback_html(
        self,
        *,
        session: Optional[Dict[str, Any]],
        next_path: str,
        message: str,
    ) -> HTMLResponse:
        session_json = json.dumps(session or {})
        next_json = json.dumps(self._normalize_auth_next_path(next_path))
        message_json = json.dumps(str(message or "").strip())
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Plaza Authentication</title>
</head>
<body>
    <p>Completing sign-in...</p>
    <script>
        try {{
            const session = {session_json};
            if (session && session.access_token) {{
                localStorage.setItem('plaza.ui.authSession', JSON.stringify(session));
            }} else {{
                localStorage.removeItem('plaza.ui.authSession');
            }}
            sessionStorage.setItem('plaza.ui.flash', {message_json});
        }} catch (error) {{
            console.error('Failed to persist Plaza auth session', error);
        }}
        window.location.replace({next_json});
    </script>
</body>
</html>"""
        return HTMLResponse(content=html)

    def _handle_oauth_callback(self, params: Dict[str, Any]) -> HTMLResponse:
        error_message = str(params.get("error_description") or params.get("error") or "").strip()
        if error_message:
            return self._render_oauth_callback_html(
                session=None,
                next_path="/plazas",
                message=f"OAuth sign-in failed: {error_message}",
            )

        state = str(params.get("state") or "").strip()
        auth_code = str(params.get("code") or "").strip()
        if not state or not auth_code:
            return self._render_oauth_callback_html(
                session=None,
                next_path="/plazas",
                message="OAuth sign-in failed: missing state or authorization code.",
            )

        self._cleanup_oauth_states()
        with self._oauth_state_lock:
            oauth_state = self._oauth_states.pop(state, None)
        if oauth_state is None:
            return self._render_oauth_callback_html(
                session=None,
                next_path="/plazas",
                message="OAuth sign-in failed: the sign-in request has expired.",
            )

        try:
            auth_response = self._supabase_exchange_code_for_session(
                auth_code=auth_code,
                code_verifier=str(oauth_state.get("code_verifier") or ""),
                redirect_to=str(oauth_state.get("redirect_to") or ""),
            )
            user_payload = auth_response.get("user") or {}
            if not user_payload.get("id"):
                raise HTTPException(status_code=401, detail="Supabase OAuth sign-in returned no user")
            profile = self._sync_ui_user_profile(
                user_payload,
                preferred_role="user",
                auth_provider=str(oauth_state.get("provider") or "password"),
                touch_sign_in=True,
            )
            if profile.get("status") == "disabled":
                raise HTTPException(status_code=403, detail="This account is disabled")
            return self._render_oauth_callback_html(
                session=auth_response.get("session") or {},
                next_path=str(oauth_state.get("next_path") or "/plazas"),
                message=f"Signed in with {str(oauth_state.get('provider') or 'OAuth').title()}.",
            )
        except HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else "OAuth sign-in failed."
            return self._render_oauth_callback_html(
                session=None,
                next_path=str(oauth_state.get("next_path") or "/plazas"),
                message=detail,
            )

    def _bootstrap_default_admin_if_needed(self):
        if not self._has_supabase_auth() or not self._has_supabase_service_role():
            return

        with self._ui_auth_bootstrap_lock:
            default_username = self.DEFAULT_ADMIN_USERNAME
            default_email = self._build_username_email(default_username)
            existing_local = self._find_ui_user_by_username(default_username)
            auth_user = None

            try:
                auth_response = self._supabase_sign_in(email=default_email, password=self.DEFAULT_ADMIN_PASSWORD)
                auth_user = auth_response.get("user") or {}
            except HTTPException:
                auth_user = None

            if auth_user is None:
                try:
                    auth_user = self._create_supabase_admin_user(
                        {
                            "email": default_email,
                            "password": self.DEFAULT_ADMIN_PASSWORD,
                            "email_confirm": True,
                            "user_metadata": {
                                "username": default_username,
                                "display_name": "Administrator",
                                "auth_provider": "password",
                            },
                        }
                    )
                except HTTPException as exc:
                    detail = exc.detail if isinstance(exc.detail, str) else str(exc)
                    if self._default_admin_already_exists_error(detail):
                        detail = "Default admin exists in Supabase, but the built-in admin/admin credentials no longer match it."
                    self._ui_auth_bootstrap_error = detail
                    logger.warning("[Plaza] Failed bootstrapping default admin user: %s", detail)
                    return

            if not auth_user or not auth_user.get("id"):
                return

            profile = self._sync_ui_user_profile(
                auth_user,
                preferred_role="admin",
                username=default_username,
                display_name="Administrator",
                auth_provider="password",
                touch_sign_in=bool(existing_local and existing_local.get("last_sign_in_at")),
            )
            if profile.get("role") != "admin" or profile.get("status") != "active":
                self._upsert_ui_user(
                    user_id=profile["id"],
                    username=profile.get("username") or default_username,
                    email=profile.get("email") or default_email,
                    display_name=profile.get("display_name") or "Administrator",
                    role="admin",
                    status="active",
                    auth_provider="password",
                    created_at=profile.get("created_at"),
                    last_sign_in_at=profile.get("last_sign_in_at"),
                )
            self._ui_auth_bootstrap_error = None

    @staticmethod
    def _default_admin_already_exists_error(detail: Optional[str]) -> bool:
        message = str(detail or "").strip().lower()
        if not message:
            return False
        return any(token in message for token in ("already", "exists", "registered", "duplicate"))

    def _find_supabase_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        if not email or not self._has_supabase_service_role():
            return None
        client = self._build_supabase_client(use_service_role=True)
        try:
            users = client.auth.admin.list_users(page=1, per_page=1000)
        except Exception as exc:
            self._ui_auth_bootstrap_error = str(exc)
            logger.warning("[Plaza] Failed listing Supabase users during admin bootstrap: %s", exc)
            return None
        target = str(email or "").strip().lower()
        for user in users or []:
            payload = self._model_to_dict(user)
            if str(payload.get("email") or "").strip().lower() == target:
                return payload
        return None

    def _ensure_ui_users_table(self):
        if not self.pool:
            raise HTTPException(status_code=501, detail="Plaza user storage is unavailable")
        if self.pool._TableExists(self.UI_USERS_TABLE):
            return
        self.pool._CreateTable(self.UI_USERS_TABLE, plaza_ui_users_table_schema())

    @staticmethod
    def _normalize_timestamp(value: Any) -> str:
        if isinstance(value, str) and value:
            return value
        return datetime.now(timezone.utc).isoformat()

    def _normalize_auth_provider(self, provider: Optional[str]) -> str:
        value = str(provider or "").strip().lower()
        return value or "password"

    def _resolve_password_signin_email(self, identifier: str) -> str:
        normalized_identifier = str(identifier or "").strip()
        if not normalized_identifier:
            raise HTTPException(status_code=400, detail="Username or email is required")
        if "@" in normalized_identifier:
            return normalized_identifier.lower()
        normalized_username = self._normalize_username(normalized_identifier)
        existing = self._find_ui_user_by_username(normalized_username)
        if existing and existing.get("email"):
            return str(existing["email"]).strip().lower()
        return self._build_username_email(normalized_username)

    def _extract_auth_provider(self, user_payload: Dict[str, Any]) -> str:
        app_metadata = user_payload.get("app_metadata") if isinstance(user_payload.get("app_metadata"), dict) else {}
        provider = app_metadata.get("provider")
        if not provider:
            providers = app_metadata.get("providers")
            if isinstance(providers, list) and providers:
                provider = providers[0]
        if not provider:
            identities = user_payload.get("identities")
            if isinstance(identities, list) and identities:
                first_identity = identities[0] if isinstance(identities[0], dict) else {}
                provider = first_identity.get("provider")
        return self._normalize_auth_provider(provider)

    def _normalize_ui_user_record(self, row: Dict[str, Any]) -> Dict[str, Any]:
        email = str(row.get("email") or "").strip().lower()
        username = str(row.get("username") or "").strip()
        if not username:
            username = self._username_from_email(email) or f"user-{str(row.get('id') or '')[:8]}"
        return {
            "id": str(row.get("id") or ""),
            "username": username,
            "email": email,
            "display_name": str(row.get("display_name") or ""),
            "role": str(row.get("role") or "user").strip().lower() or "user",
            "status": str(row.get("status") or "active").strip().lower() or "active",
            "auth_provider": self._normalize_auth_provider(row.get("auth_provider")),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "last_sign_in_at": row.get("last_sign_in_at"),
        }

    def _list_ui_users(self) -> List[Dict[str, Any]]:
        self._ensure_ui_users_table()
        rows = self.pool._GetTableData(self.UI_USERS_TABLE) or []
        normalized = [self._normalize_ui_user_record(row) for row in rows if row.get("id")]
        return sorted(normalized, key=lambda row: (row.get("username") or row.get("email") or row.get("id") or "").lower())

    def _find_ui_user_by_username(self, username: Optional[str]) -> Optional[Dict[str, Any]]:
        normalized = self._normalize_username(username, allow_empty=True)
        if not normalized:
            return None
        for user in self._list_ui_users():
            if self._normalize_username(user.get("username"), allow_empty=True) == normalized:
                return user
        return None

    def _get_ui_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_ui_users_table()
        rows = self.pool._GetTableData(self.UI_USERS_TABLE, {"id": user_id}) or []
        if not rows:
            return None
        return self._normalize_ui_user_record(rows[-1])

    def _ensure_unique_username(self, username: str, *, exclude_user_id: Optional[str] = None) -> str:
        base = self._normalize_username(username)
        existing_names = {
            user.get("username")
            for user in self._list_ui_users()
            if user.get("id") != exclude_user_id
        }
        if base not in existing_names:
            return base
        for suffix in range(2, 1000):
            candidate = self._normalize_username(f"{base}-{suffix}")
            if candidate not in existing_names:
                return candidate
        raise HTTPException(status_code=409, detail=f"Unable to allocate a username for '{base}'")

    def _resolve_profile_username(
        self,
        user_payload: Dict[str, Any],
        *,
        existing: Optional[Dict[str, Any]] = None,
        preferred_username: Optional[str] = None,
    ) -> str:
        metadata = user_payload.get("user_metadata") if isinstance(user_payload.get("user_metadata"), dict) else {}
        app_metadata = user_payload.get("app_metadata") if isinstance(user_payload.get("app_metadata"), dict) else {}
        user_id = str(user_payload.get("id") or "")
        candidates = [
            preferred_username,
            existing.get("username") if existing else None,
            metadata.get("username"),
            metadata.get("preferred_username"),
            metadata.get("user_name"),
            app_metadata.get("user_name"),
            self._username_from_email(user_payload.get("email")),
            f"user-{user_id[:8]}" if user_id else None,
        ]
        for candidate in candidates:
            normalized = self._normalize_username(candidate, allow_empty=True)
            if normalized:
                return self._ensure_unique_username(normalized, exclude_user_id=existing.get("id") if existing else user_id)
        raise HTTPException(status_code=400, detail="Unable to determine a username for this account")

    def _upsert_ui_user(
        self,
        user_id: str,
        username: str,
        email: str,
        display_name: Optional[str],
        role: str,
        status: str = "active",
        auth_provider: str = "password",
        created_at: Optional[str] = None,
        last_sign_in_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._ensure_ui_users_table()
        normalized_role = str(role or "user").strip().lower()
        normalized_status = str(status or "active").strip().lower()
        normalized_provider = self._normalize_auth_provider(auth_provider)
        if normalized_role not in self.UI_USER_ROLES:
            raise HTTPException(status_code=400, detail=f"Unsupported role '{role}'")
        if normalized_status not in self.UI_USER_STATUSES:
            raise HTTPException(status_code=400, detail=f"Unsupported status '{status}'")

        existing = self._get_ui_user(user_id)
        email_value = str(email or (existing.get("email", "") if existing else "")).strip().lower()
        username_value = self._ensure_unique_username(
            username or (existing.get("username", "") if existing else self._username_from_email(email_value) or user_id[:8]),
            exclude_user_id=user_id,
        )
        row = {
            "id": user_id,
            "username": username_value,
            "email": email_value,
            "display_name": display_name if display_name is not None else (existing.get("display_name", "") if existing else ""),
            "role": normalized_role,
            "status": normalized_status,
            "auth_provider": normalized_provider,
            "created_at": existing.get("created_at") if existing else self._normalize_timestamp(created_at),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_sign_in_at": last_sign_in_at if last_sign_in_at is not None else (existing.get("last_sign_in_at") if existing else None),
        }
        self.pool._Insert(self.UI_USERS_TABLE, row)
        return self._normalize_ui_user_record(row)

    def _sync_ui_user_profile(
        self,
        user_payload: Dict[str, Any],
        preferred_role: Optional[str] = None,
        username: Optional[str] = None,
        display_name: Optional[str] = None,
        auth_provider: Optional[str] = None,
        touch_sign_in: bool = False,
    ) -> Dict[str, Any]:
        user_id = str(user_payload.get("id") or "")
        if not user_id:
            raise HTTPException(status_code=400, detail="Missing auth user id")
        existing = self._get_ui_user(user_id)
        metadata = user_payload.get("user_metadata") or {}
        extracted_provider = auth_provider or self._extract_auth_provider(user_payload)
        next_username = self._resolve_profile_username(
            user_payload,
            existing=existing,
            preferred_username=username,
        )
        email = str(user_payload.get("email") or "").strip().lower()
        if not email and extracted_provider == "password":
            email = self._build_username_email(next_username)
        if not email and existing:
            email = existing.get("email", "")
        next_display_name = display_name
        if next_display_name is None:
            next_display_name = metadata.get("display_name") or metadata.get("name") or (existing.get("display_name") if existing else "")
        next_role = existing.get("role") if existing else (preferred_role or "user")
        next_status = existing.get("status") if existing else "active"
        last_sign_in_at = existing.get("last_sign_in_at") if existing else None
        if touch_sign_in:
            last_sign_in_at = datetime.now(timezone.utc).isoformat()
        return self._upsert_ui_user(
            user_id=user_id,
            username=next_username,
            email=email or (existing.get("email", "") if existing else ""),
            display_name=next_display_name,
            role=next_role,
            status=next_status,
            auth_provider=extracted_provider,
            created_at=existing.get("created_at") if existing else None,
            last_sign_in_at=last_sign_in_at,
        )

    def _get_authenticated_ui_context(self, request: Request) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        access_token = self._extract_bearer_token(request)
        user_payload = self._get_supabase_user(access_token)
        profile = self._sync_ui_user_profile(user_payload)
        if profile.get("status") == "disabled":
            raise HTTPException(status_code=403, detail="This account is disabled")
        return access_token, user_payload, profile

    def _require_ui_user(self, request: Request) -> Dict[str, Any]:
        _, _, profile = self._get_authenticated_ui_context(request)
        return profile

    def _assert_ui_user_update_allowed(
        self,
        actor: Dict[str, Any],
        target: Dict[str, Any],
        payload: PlazaUiUserUpdateRequest,
    ):
        actor_id = actor.get("id")
        actor_role = actor.get("role", "user")

        if actor_role == "admin":
            return

        if actor_id != target.get("id"):
            raise HTTPException(status_code=403, detail="Users can only modify their own profile")
        if payload.role is not None or payload.status is not None:
            raise HTTPException(status_code=403, detail="Users cannot change role or status")

    def receive(self, message: Message):
        # Plaza specific logic for its own mailbox
        logger.info(f"[Plaza] Received direct message: {message}")

    def run(self):
        # This will be handled by create_agent.py using uvicorn
        pass
