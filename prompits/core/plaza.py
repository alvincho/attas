import os
import logging
import time
import uuid
import uvicorn
import httpx
from prompits.core.pool import Pool
from typing import Dict, Any, List, Optional, Set

from datetime import datetime, timezone

from fastapi import Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from prompits.agents.base import BaseAgent
from prompits.core.init_schema import phemas_table_schema, plaza_ui_users_table_schema
from prompits.core.message import Message
from prompits.practices.plaza import PlazaPractice
from phemacast.core.phema import Phema

logger = logging.getLogger(__name__)


class PlazaUiSignUpRequest(BaseModel):
    email: str
    password: str
    display_name: Optional[str] = None


class PlazaUiSignInRequest(BaseModel):
    email: str
    password: str


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


class PlazaAgent(BaseAgent):
    """
    Concrete agent host for Plaza service runtime.

    Plaza endpoints themselves are provided by `PlazaPractice` loaded via
    configuration; this class focuses on base identity and core service routes.
    """

    UI_USERS_TABLE = "plaza_ui_users"
    PHEMA_TABLE = "phemas"
    UI_USER_ROLES = {"admin", "moderator", "user"}
    UI_USER_STATUSES = {"active", "disabled"}

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

        current_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.abspath(os.path.join(current_dir, "..", "agents", "templates"))
        static_dir = os.path.abspath(os.path.join(current_dir, "..", "agents", "static"))
        self.templates = Jinja2Templates(directory=templates_dir)
        self.app.mount("/static", StaticFiles(directory=static_dir), name="static")

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
                "plazas.html",
                {"request": request, "agent_name": self.name, "supported_pit_types": supported_pit_types},
            )

        @self.app.get("/plazas")
        async def plaza_ui_alias(request: Request):
            return self.templates.TemplateResponse(
                "plazas.html",
                {"request": request, "agent_name": self.name, "supported_pit_types": supported_pit_types},
            )

        @self.app.get("/phemas/editor")
        async def phema_editor(request: Request):
            return self.templates.TemplateResponse(
                "phema_editor.html",
                {"request": request, "agent_name": self.name, "initial_phema_id": ""},
            )

        @self.app.get("/phemas/editor/{phema_id}")
        async def phema_editor_existing(request: Request, phema_id: str):
            return self.templates.TemplateResponse(
                "phema_editor.html",
                {"request": request, "agent_name": self.name, "initial_phema_id": phema_id},
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
                            supported_name = supported_row.get("pulse_name")
                            supported_address = supported_row.get("pulse_address")
                            supported_key = f"{str(supported_name or '').strip().lower()}::{str(supported_address or '').strip().lower()}"
                            if supported_key in seen_supported:
                                continue
                            seen_supported.add(supported_key)
                            supported.append(
                                {
                                    "name": supported_name,
                                    "pulse_name": supported_name,
                                    "pulse_address": supported_address,
                                    "input_schema": supported_row.get("input_schema") if isinstance(supported_row.get("input_schema"), dict) else {},
                                }
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
                        row_pulse_name = row.get("pulse_name")
                        row_pulse_address = row.get("pulse_address")
                        for entry in supported:
                            if not isinstance(entry, dict):
                                continue
                            entry_name = entry.get("pulse_name") or entry.get("name")
                            entry_address = entry.get("pulse_address")
                            if row_pulse_name and not practice.state.contains(entry_name, row_pulse_name):
                                continue
                            if row_pulse_address and entry_address and not practice.state.same_pit_ref(entry_address, row_pulse_address):
                                continue
                            matched = dict(entry)
                            break

                        if row_pulse_name and not matched.get("pulse_name"):
                            matched["pulse_name"] = row_pulse_name
                        if row_pulse_name and not matched.get("name"):
                            matched["name"] = row_pulse_name
                        if row_pulse_address and not matched.get("pulse_address"):
                            matched["pulse_address"] = row_pulse_address
                        if not isinstance(matched.get("input_schema"), dict) and isinstance(row.get("input_schema"), dict):
                            matched["input_schema"] = row.get("input_schema")
                        return matched

                    for agent in agents:
                        resolved_type = str(agent.get("pit_type") or "")
                        card = agent.get("card") if isinstance(agent.get("card"), dict) else {}
                        meta = agent.get("meta") if isinstance(agent.get("meta"), dict) else {}
                        if resolved_type == "Pulser":
                            supported = meta.get("supported_pulses") if isinstance(meta.get("supported_pulses"), list) else []
                            seen = {
                                f"{str(entry.get('pulse_name') or '').strip().lower()}::{str(entry.get('pulse_address') or '').strip().lower()}"
                                for entry in supported if isinstance(entry, dict)
                            }
                            for row in pulser_rows_by_id.get(str(agent.get("agent_id") or ""), []):
                                pulse_name = row.get("pulse_name")
                                pulse_address = row.get("pulse_address")
                                key = f"{str(pulse_name or '').strip().lower()}::{str(pulse_address or '').strip().lower()}"
                                if key in seen:
                                    continue
                                seen.add(key)
                                supported.append({
                                    "name": pulse_name,
                                    "pulse_name": pulse_name,
                                    "pulse_address": pulse_address,
                                    "input_schema": row.get("input_schema") if isinstance(row.get("input_schema"), dict) else {},
                                })
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
                        pulse_name = agent.get("name")
                        pulse_address = meta.get("pulse_address") or card.get("address") or agent.get("address")
                        available_pulsers: List[Dict[str, Any]] = []
                        seen_pulser_ids: Set[str] = set()
                        for row in pulse_pulser_rows:
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

        @self.app.get("/api/ui_auth/config")
        async def ui_auth_config():
            return {
                "status": "success",
                "auth_enabled": self._has_supabase_auth(),
                "service_role_enabled": self._has_supabase_service_role(),
                "roles": sorted(self.UI_USER_ROLES),
            }

        @self.app.post("/api/ui_auth/signup")
        async def ui_auth_signup(request: PlazaUiSignUpRequest):
            def _signup_sync() -> Dict[str, Any]:
                auth_response = self._supabase_sign_up(
                    email=request.email,
                    password=request.password,
                    display_name=request.display_name,
                )
                user_payload = auth_response.get("user") or {}
                if not user_payload.get("id"):
                    raise HTTPException(status_code=502, detail="Supabase sign-up returned no user payload")
                preferred_role = "admin" if not self._list_ui_users() else "user"
                profile = self._sync_ui_user_profile(
                    user_payload,
                    preferred_role=preferred_role,
                    display_name=request.display_name,
                    touch_sign_in=bool(auth_response.get("session")),
                )
                return {"status": "success", "session": auth_response.get("session"), "user": profile}

            return await run_in_threadpool(_signup_sync)

        @self.app.post("/api/ui_auth/signin")
        async def ui_auth_signin(request: PlazaUiSignInRequest):
            def _signin_sync() -> Dict[str, Any]:
                auth_response = self._supabase_sign_in(email=request.email, password=request.password)
                user_payload = auth_response.get("user") or {}
                if not user_payload.get("id"):
                    raise HTTPException(status_code=401, detail="Supabase sign-in returned no user")
                profile = self._sync_ui_user_profile(
                    user_payload,
                    touch_sign_in=True,
                )
                if profile.get("status") == "disabled":
                    raise HTTPException(status_code=403, detail="This account is disabled")
                return {"status": "success", "session": auth_response.get("session"), "user": profile}

            return await run_in_threadpool(_signin_sync)

        @self.app.get("/api/ui_auth/me")
        async def ui_auth_me(request: Request):
            def _me_sync() -> Dict[str, Any]:
                access_token = self._extract_bearer_token(request)
                user_payload = self._get_supabase_user(access_token)
                profile = self._sync_ui_user_profile(user_payload)
                if profile.get("status") == "disabled":
                    raise HTTPException(status_code=403, detail="This account is disabled")
                return {"status": "success", "user": profile}

            return await run_in_threadpool(_me_sync)

        @self.app.post("/api/ui_auth/signout")
        async def ui_auth_signout():
            return {"status": "success"}

        @self.app.get("/api/ui_users")
        async def ui_list_users(request: Request):
            def _list_users_sync() -> Dict[str, Any]:
                actor = self._require_ui_user(request)
                if actor.get("role") in {"admin", "moderator"}:
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
                    email=target.get("email", ""),
                    display_name=next_name,
                    role=next_role,
                    status=next_status,
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
        if not self.pool:
            return None
        url = getattr(self.pool, "url", None)
        key = getattr(self.pool, "key", None)
        if not url or not key:
            return None
        return {"url": url, "key": key}

    def _has_supabase_auth(self) -> bool:
        return self._get_supabase_pool_config() is not None

    def _has_supabase_service_role(self) -> bool:
        return bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("PLAZA_SUPABASE_SERVICE_ROLE_KEY"))

    def _build_supabase_client(self, use_service_role: bool = False):
        config = self._get_supabase_pool_config()
        if config is None:
            raise HTTPException(status_code=501, detail="Supabase auth is unavailable for this Plaza")
        from supabase import create_client

        key = config["key"]
        if use_service_role:
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("PLAZA_SUPABASE_SERVICE_ROLE_KEY") or key
        return create_client(config["url"], key)

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

    def _supabase_sign_up(self, email: str, password: str, display_name: Optional[str] = None) -> Dict[str, Any]:
        client = self._build_supabase_client()
        credentials: Dict[str, Any] = {"email": email, "password": password}
        if display_name:
            credentials["options"] = {"data": {"display_name": display_name}}
        try:
            response = client.auth.sign_up(credentials)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Supabase sign-up failed: {exc}") from exc
        return self._normalize_auth_response(response)

    def _supabase_sign_in(self, email: str, password: str) -> Dict[str, Any]:
        client = self._build_supabase_client()
        try:
            response = client.auth.sign_in_with_password({"email": email, "password": password})
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Supabase sign-in failed: {exc}") from exc
        return self._normalize_auth_response(response)

    def _get_supabase_user(self, access_token: str) -> Dict[str, Any]:
        client = self._build_supabase_client()
        try:
            response = client.auth.get_user(access_token)
        except Exception as exc:
            raise HTTPException(status_code=401, detail=f"Supabase token verification failed: {exc}") from exc
        user = getattr(response, "user", None)
        user_payload = self._model_to_dict(user)
        if not user_payload.get("id"):
            raise HTTPException(status_code=401, detail="Supabase token did not resolve to a user")
        return user_payload

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

    def _normalize_ui_user_record(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(row.get("id") or ""),
            "email": row.get("email", ""),
            "display_name": row.get("display_name", ""),
            "role": row.get("role", "user"),
            "status": row.get("status", "active"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "last_sign_in_at": row.get("last_sign_in_at"),
        }

    def _list_ui_users(self) -> List[Dict[str, Any]]:
        self._ensure_ui_users_table()
        rows = self.pool._GetTableData(self.UI_USERS_TABLE) or []
        normalized = [self._normalize_ui_user_record(row) for row in rows if row.get("id")]
        return sorted(normalized, key=lambda row: (row.get("email") or row.get("id") or "").lower())

    def _get_ui_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        self._ensure_ui_users_table()
        rows = self.pool._GetTableData(self.UI_USERS_TABLE, {"id": user_id}) or []
        if not rows:
            return None
        return self._normalize_ui_user_record(rows[-1])

    def _upsert_ui_user(
        self,
        user_id: str,
        email: str,
        display_name: Optional[str],
        role: str,
        status: str = "active",
        created_at: Optional[str] = None,
        last_sign_in_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._ensure_ui_users_table()
        normalized_role = str(role or "user").strip().lower()
        normalized_status = str(status or "active").strip().lower()
        if normalized_role not in self.UI_USER_ROLES:
            raise HTTPException(status_code=400, detail=f"Unsupported role '{role}'")
        if normalized_status not in self.UI_USER_STATUSES:
            raise HTTPException(status_code=400, detail=f"Unsupported status '{status}'")

        existing = self._get_ui_user(user_id)
        row = {
            "id": user_id,
            "email": email or existing.get("email", "") if existing else email,
            "display_name": display_name if display_name is not None else (existing.get("display_name", "") if existing else ""),
            "role": normalized_role,
            "status": normalized_status,
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
        display_name: Optional[str] = None,
        touch_sign_in: bool = False,
    ) -> Dict[str, Any]:
        user_id = str(user_payload.get("id") or "")
        if not user_id:
            raise HTTPException(status_code=400, detail="Missing auth user id")
        existing = self._get_ui_user(user_id)
        metadata = user_payload.get("user_metadata") or {}
        email = user_payload.get("email", "")
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
            email=email or (existing.get("email", "") if existing else ""),
            display_name=next_display_name,
            role=next_role,
            status=next_status,
            created_at=existing.get("created_at") if existing else None,
            last_sign_in_at=last_sign_in_at,
        )

    def _require_ui_user(self, request: Request) -> Dict[str, Any]:
        access_token = self._extract_bearer_token(request)
        user_payload = self._get_supabase_user(access_token)
        profile = self._sync_ui_user_profile(user_payload)
        if profile.get("status") == "disabled":
            raise HTTPException(status_code=403, detail="This account is disabled")
        return profile

    def _assert_ui_user_update_allowed(
        self,
        actor: Dict[str, Any],
        target: Dict[str, Any],
        payload: PlazaUiUserUpdateRequest,
    ):
        actor_id = actor.get("id")
        actor_role = actor.get("role", "user")
        target_role = target.get("role", "user")
        requested_role = payload.role or target_role

        if actor_role == "admin":
            return

        if actor_role == "moderator":
            if target_role == "admin":
                raise HTTPException(status_code=403, detail="Moderators cannot modify admins")
            if requested_role == "admin":
                raise HTTPException(status_code=403, detail="Moderators cannot assign admin role")
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
