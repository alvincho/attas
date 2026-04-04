"""
User module for `prompits.agents.user`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, these modules provide reusable
agent hosts and user-facing agent variants.

Core types exposed here include `UserAgent`, which carry the main behavior or state
managed by this module.
"""

import json
import logging
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

import requests
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from prompits.agents.base import BaseAgent
from prompits.core.message import Message
from prompits.core.pool import Pool
from prompits.practices.plaza import PlazaPractice

logger = logging.getLogger(__name__)

ConfigInput = Union[str, Path, Mapping[str, Any]]


def _read_config(config: Optional[ConfigInput]) -> Dict[str, Any]:
    """Internal helper to read the config."""
    if config is None:
        return {}
    if isinstance(config, Mapping):
        return dict(config)

    config_path = Path(config)
    with config_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


class UserAgent(BaseAgent):
    """
    Browser-facing multi-plaza operator UI.

    The user agent keeps a primary BaseAgent identity for backwards
    compatibility, while also managing independent auth sessions for any number
    of additional plazas used for discovery and remote practice invocation.
    """

    SESSION_EXPIRES_IN = 3600
    SAVED_RESULTS_TABLE = "user_agent_saved_results"
    SAVED_ARTIFACTS_DIR = "saved_outputs"
    PLAZA_CONNECTION_ACTIVE_WINDOW_SEC = 60

    def __init__(
        self,
        name: str,
        host: str = "127.0.0.1",
        port: int = 8000,
        plaza_url: Optional[str] = None,
        plaza_urls: Optional[Any] = None,
        agent_card: Optional[Dict[str, Any]] = None,
        pool: Optional[Pool] = None,
        config: Optional[ConfigInput] = None,
        config_path: Optional[ConfigInput] = None,
        applications: Optional[List[Dict[str, Any]]] = None,
    ):
        """Initialize the user agent."""
        config_data = _read_config(config if config is not None else config_path)
        user_config = config_data.get("user_agent") if isinstance(config_data.get("user_agent"), dict) else {}

        resolved_primary_plaza = str(
            plaza_url
            or config_data.get("plaza_url")
            or user_config.get("plaza_url")
            or ""
        ).strip() or None

        super().__init__(name, host, port, resolved_primary_plaza, agent_card, pool)

        self.raw_config = dict(config_data)
        self.user_plaza_urls = self._normalize_plaza_urls(
            plaza_urls,
            user_config.get("plaza_urls"),
            config_data.get("plaza_urls"),
            resolved_primary_plaza,
        )
        if not self.user_plaza_urls and self.plaza_url:
            self.user_plaza_urls = [self.plaza_url]

        raw_applications = applications
        if raw_applications is None:
            raw_applications = user_config.get("applications")
        if raw_applications is None:
            raw_applications = config_data.get("applications")
        self.configured_applications = self._normalize_configured_applications(raw_applications)
        self.disabled_components = self._normalize_disabled_components(
            user_config.get("disabled_components")
            if isinstance(user_config.get("disabled_components"), dict)
            else config_data.get("disabled_components")
        )

        self._plaza_sessions: Dict[str, Dict[str, Any]] = {}
        self._plaza_sessions_lock = threading.RLock()
        self._seed_primary_session()

        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_dir = os.path.join(current_dir, "templates")
        static_dir = os.path.join(current_dir, "static")

        os.makedirs(template_dir, exist_ok=True)
        os.makedirs(static_dir, exist_ok=True)

        self.templates = Jinja2Templates(directory=template_dir)
        self.app.mount("/static", StaticFiles(directory=static_dir), name="static")

        self.setup_user_agent_routes()

    @staticmethod
    def _normalize_plaza_urls(*values: Any) -> List[str]:
        """Internal helper to normalize the Plaza URLs."""
        urls: List[str] = []
        seen = set()

        def collect(value: Any):
            """Collect the value."""
            if value is None:
                return
            if isinstance(value, str):
                normalized = value.strip().rstrip("/")
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    urls.append(normalized)
                return
            if isinstance(value, (list, tuple, set)):
                for item in value:
                    collect(item)
                return
            if isinstance(value, dict):
                for key in ("plaza_urls", "plazas", "urls"):
                    collect(value.get(key))

        for value in values:
            collect(value)
        return urls

    @staticmethod
    def _normalize_configured_applications(raw: Any) -> List[Dict[str, Any]]:
        """Internal helper to normalize the configured applications."""
        if not isinstance(raw, list):
            return []
        normalized: List[Dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            entry = {str(key): value for key, value in item.items()}
            entry["name"] = str(entry.get("name") or "").strip()
            if not entry["name"]:
                continue
            normalized.append(entry)
        return normalized

    @staticmethod
    def _normalize_name_set(raw: Any) -> set[str]:
        """Internal helper to normalize the name set."""
        if isinstance(raw, (list, tuple, set)):
            return {
                str(item).strip().lower()
                for item in raw
                if str(item).strip()
            }
        if isinstance(raw, str) and raw.strip():
            return {raw.strip().lower()}
        return set()

    @classmethod
    def _normalize_disabled_components(cls, raw: Any) -> Dict[str, set[str]]:
        """Internal helper to normalize the disabled components."""
        source = raw if isinstance(raw, dict) else {}
        return {
            "applications": cls._normalize_name_set(source.get("applications")),
            "phemars": cls._normalize_name_set(source.get("phemars")),
            "castrs": cls._normalize_name_set(source.get("castrs")),
            "agent_configs": cls._normalize_name_set(source.get("agent_configs")),
        }

    @staticmethod
    def _normalized_text(value: Any) -> str:
        """Internal helper for normalized text."""
        return str(value or "").strip().lower()

    def _matches_disabled_name(self, value: Any, *groups: str) -> bool:
        """Return whether the value matches disabled name."""
        normalized = self._normalized_text(value)
        if not normalized:
            return False
        for group in groups:
            if normalized in self.disabled_components.get(group, set()):
                return True
        return False

    def _is_application_disabled(self, item: Dict[str, Any]) -> bool:
        """Return whether the value is an application disabled."""
        return any(
            self._matches_disabled_name(candidate, "applications", "phemars")
            for candidate in (
                item.get("name"),
                item.get("owner"),
                item.get("host_phemar_name"),
            )
        )

    def _is_agent_disabled(self, item: Dict[str, Any], group: str) -> bool:
        """Return whether the value is an agent disabled."""
        return self._matches_disabled_name(item.get("name"), group)

    def _infer_agent_config_role(self, item: Dict[str, Any]) -> str:
        """Internal helper for infer agent config role."""
        role = self._normalized_text(item.get("role"))
        if role:
            return role
        agent_type = self._normalized_text(item.get("agent_type"))
        if "castr" in agent_type:
            return "castr"
        if "phemar" in agent_type:
            return "phemar"
        return ""

    def _is_agent_config_disabled(self, item: Dict[str, Any]) -> bool:
        """Return whether the value is an agent config disabled."""
        config = item.get("config") if isinstance(item.get("config"), dict) else {}
        agent_card = config.get("agent_card") if isinstance(config.get("agent_card"), dict) else {}
        candidates = [
            item.get("name"),
            config.get("name"),
            agent_card.get("name"),
        ]
        role = self._infer_agent_config_role(item)
        groups = ["agent_configs"]
        if role == "castr":
            groups.append("castrs")
        elif role == "phemar":
            groups.append("phemars")
        return any(self._matches_disabled_name(candidate, *groups) for candidate in candidates)

    def _agent_config_entry_from_config(self, config: Dict[str, Any], *, config_id: str = "") -> Dict[str, Any]:
        """Internal helper to return the agent config entry from config."""
        agent_card = config.get("agent_card") if isinstance(config.get("agent_card"), dict) else {}
        return {
            "id": str(config_id or "").strip(),
            "name": str(config.get("name") or agent_card.get("name") or "").strip(),
            "role": str(config.get("role") or agent_card.get("role") or "").strip(),
            "agent_type": str(config.get("type") or "").strip(),
            "config": dict(config or {}),
        }

    def _ensure_agent_config_launch_allowed(
        self,
        *,
        plaza_url: str,
        config_id: str = "",
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Internal helper to ensure the agent config launch allowed exists."""
        if isinstance(config, dict) and config:
            if self._is_agent_config_disabled(self._agent_config_entry_from_config(config, config_id=config_id)):
                raise HTTPException(status_code=403, detail="This component is temporarily disabled")
            return

        normalized_id = str(config_id or "").strip()
        if not normalized_id:
            return
        try:
            rows = self._fetch_plaza_agent_configs(plaza_url, include_config="true")
        except Exception:
            return
        for row in rows:
            if str(row.get("id") or "").strip() != normalized_id:
                continue
            if self._is_agent_config_disabled(row):
                raise HTTPException(status_code=403, detail="This component is temporarily disabled")
            return

    def _seed_primary_session(self) -> None:
        """Internal helper for seed primary session."""
        if not self.plaza_url:
            return
        normalized = self.plaza_url.rstrip("/")
        with self._plaza_sessions_lock:
            self._plaza_sessions[normalized] = {
                "plaza_url": normalized,
                "agent_id": str(self.agent_id or ""),
                "api_key": str(self.api_key or ""),
                "token": str(self.plaza_token or ""),
                "token_expires_at": float(self.token_expires_at or 0),
            }

    def _get_session_state(self, plaza_url: str) -> Dict[str, Any]:
        """Internal helper to return the session state."""
        normalized = str(plaza_url or "").strip().rstrip("/")
        if not normalized:
            raise ValueError("plaza_url is required")

        with self._plaza_sessions_lock:
            session = self._plaza_sessions.setdefault(
                normalized,
                {
                    "plaza_url": normalized,
                    "agent_id": "",
                    "api_key": "",
                    "token": "",
                    "token_expires_at": 0.0,
                },
            )

            # Mirror the BaseAgent primary session when available.
            if normalized == str(self.plaza_url or "").rstrip("/"):
                if self.agent_id:
                    session["agent_id"] = str(self.agent_id)
                if self.api_key:
                    session["api_key"] = str(self.api_key)
                # Keep the primary per-plaza session aligned with the BaseAgent state.
                # Heartbeat renewal and reconnect update the primary token directly on the
                # BaseAgent, so stale cached tokens here can break remote UsePractice calls.
                session["token"] = str(self.plaza_token or "")
                session["token_expires_at"] = float(self.token_expires_at or 0)

        if not session.get("agent_id") and self.pool:
            creds = self.plaza_credential_store.load(agent_name=self.name, plaza_url=normalized)
            if creds:
                with self._plaza_sessions_lock:
                    session["agent_id"] = str(creds.get("agent_id") or "")
                    session["api_key"] = str(creds.get("api_key") or "")
        return session

    def _sync_primary_agent_state(self, plaza_url: str, session: Dict[str, Any]) -> None:
        """Internal helper to synchronize the primary agent state."""
        normalized = str(plaza_url or "").rstrip("/")
        if normalized != str(self.plaza_url or "").rstrip("/"):
            return
        self.agent_id = str(session.get("agent_id") or "") or None
        self.api_key = str(session.get("api_key") or "") or None
        self.plaza_token = str(session.get("token") or "") or None
        self.token_expires_at = float(session.get("token_expires_at") or 0)
        if self.agent_id:
            self.agent_card["agent_id"] = self.agent_id
            self._refresh_pit_address()

    def _register_plaza_session(self, plaza_url: str, session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Internal helper to register the Plaza session."""
        normalized = str(plaza_url or "").rstrip("/")
        payload = self.build_register_payload(
            plaza_url=normalized,
            card=dict(self.agent_card or {}),
            address=f"http://{self.host}:{self.port}",
            expires_in=self.SESSION_EXPIRES_IN,
            pit_type=self.agent_card.get("pit_type"),
            accepts_inbound_from_plaza=self.agent_card.get("accepts_inbound_from_plaza"),
        )
        if session.get("agent_id") and session.get("api_key"):
            payload["agent_id"] = session["agent_id"]
            payload["api_key"] = session["api_key"]

        response = self._plaza_post("/register", plaza_url=normalized, json=payload, retries=0)
        if response.status_code == 401 and payload.get("agent_id") and payload.get("api_key"):
            with self._plaza_sessions_lock:
                session["agent_id"] = ""
                session["api_key"] = ""
                session["token"] = ""
                session["token_expires_at"] = 0.0
            retry_payload = dict(payload)
            retry_payload.pop("agent_id", None)
            retry_payload.pop("api_key", None)
            response = self._plaza_post("/register", plaza_url=normalized, json=retry_payload, retries=0)

        if response.status_code != 200:
            self.logger.warning(
                "Failed to register UserAgent against plaza %s: %s",
                normalized,
                getattr(response, "text", ""),
            )
            return None

        data = response.json() if response.content else {}
        with self._plaza_sessions_lock:
            session["agent_id"] = str(data.get("agent_id") or "")
            session["api_key"] = str(data.get("api_key") or "")
            session["token"] = str(data.get("token") or "")
            session["token_expires_at"] = time.time() + float(data.get("expires_in") or self.SESSION_EXPIRES_IN)

        if session.get("agent_id") and session.get("api_key"):
            self.plaza_credential_store.save(
                self.name,
                session["agent_id"],
                session["api_key"],
                plaza_url=normalized,
            )
        self._sync_primary_agent_state(normalized, session)
        return session

    def _renew_plaza_session(self, plaza_url: str, session: Dict[str, Any]) -> bool:
        """Internal helper for renew Plaza session."""
        token = str(session.get("token") or "").strip()
        if not token:
            return False

        response = self._plaza_post(
            "/renew",
            plaza_url=plaza_url,
            json={"agent_name": self.name, "expires_in": self.SESSION_EXPIRES_IN},
            headers={"Authorization": f"Bearer {token}"},
            retries=0,
        )
        if response.status_code != 200:
            return False

        data = response.json() if response.content else {}
        with self._plaza_sessions_lock:
            session["token"] = str(data.get("token") or token)
            session["token_expires_at"] = time.time() + float(data.get("expires_in") or self.SESSION_EXPIRES_IN)
        self._sync_primary_agent_state(plaza_url, session)
        return True

    def _ensure_plaza_session(self, plaza_url: str) -> Optional[Dict[str, Any]]:
        """Internal helper to ensure the Plaza session exists."""
        session = self._get_session_state(plaza_url)
        if float(session.get("token_expires_at") or 0) > (time.time() + 60) and session.get("token"):
            return session
        if self._renew_plaza_session(plaza_url, session):
            return session
        return self._register_plaza_session(plaza_url, session)

    def _search_plaza(self, plaza_url: str, **params: Any) -> List[Dict[str, Any]]:
        """Internal helper to search the Plaza."""
        session = self._ensure_plaza_session(plaza_url)
        if not session or not session.get("token"):
            return []

        filtered_params = {key: value for key, value in params.items() if value not in (None, "", [])}
        response = self._plaza_get(
            "/search",
            plaza_url=plaza_url,
            params=filtered_params,
            headers={"Authorization": f"Bearer {session['token']}"},
            retries=0,
        )
        if response.status_code in (401, 403):
            with self._plaza_sessions_lock:
                session["token"] = ""
                session["token_expires_at"] = 0.0
            session = self._ensure_plaza_session(plaza_url)
            if not session or not session.get("token"):
                return []
            response = self._plaza_get(
                "/search",
                plaza_url=plaza_url,
                params=filtered_params,
                headers={"Authorization": f"Bearer {session['token']}"},
                retries=0,
            )
        if response.status_code != 200:
            return []
        payload = response.json() if response.content else []
        return payload if isinstance(payload, list) else []

    def _resolve_config_plaza_urls(self, plaza_url: str = "") -> List[str]:
        """Internal helper to resolve the config Plaza URLs."""
        selected = self._normalize_plaza_urls(plaza_url) if plaza_url else list(self.user_plaza_urls)
        if not selected and self.plaza_url:
            selected = [str(self.plaza_url).rstrip("/")]
        return selected

    def _fetch_plaza_agent_configs(self, plaza_url: str, **params: Any) -> List[Dict[str, Any]]:
        """Internal helper to fetch the Plaza agent configs."""
        filtered_params = {key: value for key, value in params.items() if value not in (None, "", [])}
        response = self._plaza_get(
            "/api/agent_configs",
            plaza_url=plaza_url,
            params=filtered_params,
            retries=0,
        )
        if response.status_code != 200:
            return []
        payload = response.json() if response.content else {}
        rows = payload.get("agent_configs") if isinstance(payload, dict) else []
        results: List[Dict[str, Any]] = []
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            item = dict(row)
            item["plaza_url"] = plaza_url
            results.append(item)
        return results

    def _save_plaza_agent_config(
        self,
        *,
        plaza_url: str,
        config: Dict[str, Any],
        config_id: str = "",
        owner: str = "",
        name: str = "",
        description: str = "",
    ) -> Dict[str, Any]:
        """Internal helper to save the Plaza agent config."""
        response = self._plaza_post(
            "/api/agent_configs",
            plaza_url=plaza_url,
            json={
                "config": dict(config or {}),
                "config_id": str(config_id or "").strip() or None,
                "owner": str(owner or "").strip() or None,
                "name": str(name or "").strip() or None,
                "description": str(description or "").strip() or None,
            },
            retries=0,
        )
        if response.status_code != 200:
            detail = ""
            try:
                parsed = response.json()
                if isinstance(parsed, dict):
                    detail = str(parsed.get("detail") or parsed.get("message") or "")
            except Exception:
                detail = response.text
            raise HTTPException(status_code=response.status_code, detail=detail or "Could not save agent config")

        payload = response.json() if response.content else {}
        saved = payload.get("agent_config") if isinstance(payload, dict) else {}
        if not isinstance(saved, dict):
            raise HTTPException(status_code=502, detail="Plaza did not return an agent config payload")
        saved["plaza_url"] = plaza_url
        return saved

    def _launch_plaza_agent_config(
        self,
        *,
        plaza_url: str,
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
        """Internal helper to return the launch Plaza agent config."""
        normalized_id = str(config_id or "").strip()
        if not normalized_id and not isinstance(config, dict):
            raise HTTPException(status_code=400, detail="config_id or config is required")

        response = self._plaza_post(
            "/api/agent_configs/launch",
            plaza_url=plaza_url,
            json={
                "config_id": normalized_id or None,
                "config": dict(config or {}) if isinstance(config, dict) else None,
                "owner": str(owner or "").strip() or None,
                "name": str(name or "").strip() or None,
                "description": str(description or "").strip() or None,
                "agent_name": str(agent_name or "").strip() or None,
                "host": str(host or "").strip() or None,
                "port": int(port) if port is not None else None,
                "pool_type": str(pool_type or "").strip() or None,
                "pool_location": str(pool_location or "").strip() or None,
                "wait_for_health_sec": float(wait_for_health_sec or 15.0),
            },
            retries=0,
        )
        if response.status_code != 200:
            detail = ""
            try:
                parsed = response.json()
                if isinstance(parsed, dict):
                    detail = str(parsed.get("detail") or parsed.get("message") or "")
            except Exception:
                detail = response.text
            raise HTTPException(status_code=response.status_code, detail=detail or "Could not launch agent config")

        payload = response.json() if response.content else {}
        launch = payload.get("launch") if isinstance(payload, dict) else {}
        if not isinstance(launch, dict):
            raise HTTPException(status_code=502, detail="Plaza did not return a launch payload")
        launch["plaza_url"] = plaza_url
        return launch

    def _lookup_plaza_agent(
        self,
        plaza_url: str,
        *,
        agent_id: Optional[str] = None,
        name: Optional[str] = None,
        role: Optional[str] = None,
        pit_type: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Internal helper to look up the Plaza agent."""
        if agent_id:
            results = self._search_plaza(plaza_url, agent_id=agent_id, pit_type=pit_type)
            if results:
                return results[0]
        if name:
            results = self._search_plaza(plaza_url, name=name, role=role, pit_type=pit_type)
            if results:
                return results[0]
        return None

    @staticmethod
    def _query_blob(value: Any) -> str:
        """Internal helper to query the blob."""
        if isinstance(value, (dict, list, tuple, set)):
            try:
                return json.dumps(value, sort_keys=True, default=str).lower()
            except Exception:
                return str(value).lower()
        return str(value or "").lower()

    def _matches_query(self, *values: Any, query: str = "") -> bool:
        """Return whether the value matches query."""
        normalized_query = str(query or "").strip().lower()
        if not normalized_query:
            return True
        return any(normalized_query in self._query_blob(value) for value in values)

    @staticmethod
    def _guess_castr_format(card: Dict[str, Any], meta: Dict[str, Any]) -> str:
        """Internal helper for guess castr format."""
        media_type = str(meta.get("media_type") or card.get("media_type") or "").strip()
        if media_type:
            return media_type.upper()
        tags = [str(tag).strip().lower() for tag in (card.get("tags") or []) if str(tag).strip()]
        for candidate in ("pdf", "pptx", "ppt", "markdown", "html", "json", "text"):
            if candidate in tags:
                return candidate.upper()
        return "PDF"

    def _map_application_record(self, row: Dict[str, Any], plaza_url: str) -> Dict[str, Any]:
        """Internal helper to map the application record."""
        card = row.get("card") if isinstance(row.get("card"), dict) else {}
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        host_pit_address = meta.get("host_phemar_pit_address") if isinstance(meta.get("host_phemar_pit_address"), dict) else {}
        host_plazas = [str(item).rstrip("/") for item in host_pit_address.get("plazas", []) if item]
        return {
            "id": str(row.get("agent_id") or card.get("phema_id") or card.get("id") or "").strip(),
            "phema_id": str(card.get("phema_id") or row.get("agent_id") or "").strip(),
            "name": str(row.get("name") or card.get("name") or "").strip(),
            "description": str(row.get("description") or card.get("description") or "").strip(),
            "owner": str(row.get("owner") or card.get("owner") or "").strip(),
            "party": str(card.get("party") or meta.get("party") or "").strip(),
            "plaza_url": plaza_url,
            "pit_type": str(row.get("pit_type") or row.get("type") or "Phema"),
            "tags": [str(tag) for tag in (card.get("tags") or []) if str(tag).strip()],
            "input_schema": card.get("input_schema") if isinstance(card.get("input_schema"), dict) else {},
            "access_practice_id": str(meta.get("access_practice_id") or "generate_phema").strip() or "generate_phema",
            "host_phemar_name": str(meta.get("host_phemar_name") or meta.get("registered_by_phemar") or "").strip(),
            "host_phemar_agent_id": str(meta.get("host_phemar_agent_id") or meta.get("registered_by_agent_id") or "").strip(),
            "host_phemar_plaza_url": host_plazas[0] if host_plazas else plaza_url,
            "host_phemar_address": "",
            "host_phemar_last_active": 0.0,
            "last_active": float(row.get("last_active") or 0),
            "card": card,
            "meta": meta,
        }

    def _map_agent_record(self, row: Dict[str, Any], plaza_url: str) -> Dict[str, Any]:
        """Internal helper to map the agent record."""
        card = row.get("card") if isinstance(row.get("card"), dict) else {}
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        if not meta and isinstance(card.get("meta"), dict):
            meta = dict(card.get("meta") or {})
        role = str(card.get("role") or row.get("role") or "").strip()
        return {
            "agent_id": str(row.get("agent_id") or card.get("agent_id") or "").strip(),
            "name": str(row.get("name") or card.get("name") or "").strip(),
            "description": str(row.get("description") or card.get("description") or "").strip(),
            "owner": str(row.get("owner") or card.get("owner") or "").strip(),
            "role": role,
            "plaza_url": plaza_url,
            "address": str(card.get("address") or row.get("address") or "").strip(),
            "pit_address": card.get("pit_address") if isinstance(card.get("pit_address"), dict) else {},
            "tags": [str(tag) for tag in (card.get("tags") or []) if str(tag).strip()],
            "last_active": float(row.get("last_active") or 0),
            "supported_phemas": meta.get("supported_phemas") if isinstance(meta.get("supported_phemas"), list) else [],
            "media_type": self._guess_castr_format(card, meta) if role == "castr" else "",
            "card": card,
            "meta": meta,
        }

    def _map_llm_pulser_record(self, row: Dict[str, Any], plaza_url: str) -> Dict[str, Any]:
        """Internal helper to map the LLM pulser record."""
        mapped = self._map_agent_record(row, plaza_url)
        meta = mapped.get("meta") if isinstance(mapped.get("meta"), dict) else {}
        supported_pulses = meta.get("supported_pulses") if isinstance(meta.get("supported_pulses"), list) else []
        pulse_names = [
            str(entry.get("pulse_name") or entry.get("name") or "").strip()
            for entry in supported_pulses
            if isinstance(entry, dict) and str(entry.get("pulse_name") or entry.get("name") or "").strip()
        ]
        mapped["practice_id"] = "get_pulse_data"
        mapped["pulse_name"] = "llm_chat"
        mapped["pulse_names"] = pulse_names
        mapped["supports_llm_chat"] = "llm_chat" in pulse_names
        return mapped

    @classmethod
    def _heartbeat_is_active(cls, last_active: Any) -> bool:
        """Return whether the heartbeat is active."""
        try:
            timestamp = float(last_active or 0)
        except (TypeError, ValueError):
            return False
        if timestamp <= 0:
            return False
        return max(0.0, time.time() - timestamp) <= cls.PLAZA_CONNECTION_ACTIVE_WINDOW_SEC

    def _build_plaza_connection_summary(
        self,
        plaza_url: str,
        *,
        agent_id: str = "",
        fallback_name: str = "",
    ) -> Dict[str, Any]:
        """Internal helper to build the Plaza connection summary."""
        summary = {
            "connected_agent_id": str(agent_id or "").strip(),
            "connected_agent_name": str(fallback_name or self.name or "").strip(),
            "connected_last_active": 0.0,
            "connection_status": "disconnected",
        }

        normalized_agent_id = summary["connected_agent_id"]
        if not normalized_agent_id:
            return summary

        row = self._lookup_plaza_agent(plaza_url, agent_id=normalized_agent_id)
        if isinstance(row, dict):
            card = row.get("card") if isinstance(row.get("card"), dict) else {}
            summary["connected_agent_name"] = str(
                row.get("name")
                or card.get("name")
                or summary["connected_agent_name"]
                or self.name
            ).strip()
            summary["connected_last_active"] = float(row.get("last_active") or 0)

        if self._heartbeat_is_active(summary["connected_last_active"]):
            summary["connection_status"] = "connected"
        return summary

    def _fetch_single_plaza_catalog(self, plaza_url: str, query: str = "", party: str = "") -> Dict[str, Any]:
        """Internal helper to fetch the single Plaza catalog."""
        normalized = str(plaza_url or "").strip().rstrip("/")
        status: Dict[str, Any] = {
            "url": normalized,
            "online": False,
            "authenticated": False,
            "connected_agent_id": "",
            "connected_agent_name": "",
            "connected_last_active": 0.0,
            "connection_status": "disconnected",
            "card": None,
            "applications": [],
            "phemars": [],
            "castrs": [],
            "llm_pulsers": [],
            "error": "",
        }

        try:
            health = self._plaza_get("/health", plaza_url=normalized, retries=0)
            status["online"] = health.status_code == 200
        except Exception as exc:
            status["error"] = str(exc)
            return status

        try:
            card_resp = self._plaza_get("/.well-known/agent-card", plaza_url=normalized, retries=0)
            if card_resp.status_code == 200 and card_resp.content:
                status["card"] = card_resp.json()
        except Exception:
            pass

        try:
            session = self._ensure_plaza_session(normalized)
            if not session or not session.get("token"):
                status["error"] = status["error"] or "Unable to authenticate with plaza"
                return status
            status["authenticated"] = True
            status["connected_agent_id"] = str(session.get("agent_id") or "")
            status.update(
                self._build_plaza_connection_summary(
                    normalized,
                    agent_id=status["connected_agent_id"],
                    fallback_name=self.name,
                )
            )

            application_rows = self._search_plaza(normalized, pit_type="Phema", party=party or None)
            phemar_rows = self._search_plaza(normalized, role="phemar")
            castr_rows = self._search_plaza(normalized, role="castr")
            llm_pulser_rows = self._search_plaza(normalized, pit_type="Pulser", pulse_name="llm_chat")

            applications = [
                self._map_application_record(row, normalized)
                for row in application_rows
                if isinstance(row, dict)
            ]
            phemars = [
                self._map_agent_record(row, normalized)
                for row in phemar_rows
                if isinstance(row, dict)
            ]
            castrs = [
                self._map_agent_record(row, normalized)
                for row in castr_rows
                if isinstance(row, dict)
            ]
            llm_pulsers = [
                self._map_llm_pulser_record(row, normalized)
                for row in llm_pulser_rows
                if isinstance(row, dict)
            ]

            phemars_by_agent_id = {
                str(item.get("agent_id") or "").strip(): item
                for item in phemars
                if str(item.get("agent_id") or "").strip()
            }
            phemars_by_name = {
                str(item.get("name") or "").strip().lower(): item
                for item in phemars
                if str(item.get("name") or "").strip()
            }
            for application in applications:
                host_agent_id = str(application.get("host_phemar_agent_id") or "").strip()
                host_name = str(application.get("host_phemar_name") or "").strip().lower()
                matched_phemar = None
                if host_agent_id:
                    matched_phemar = phemars_by_agent_id.get(host_agent_id)
                if matched_phemar is None and host_name:
                    matched_phemar = phemars_by_name.get(host_name)
                if matched_phemar:
                    application["host_phemar_address"] = str(matched_phemar.get("address") or "").strip()
                    application["host_phemar_last_active"] = float(matched_phemar.get("last_active") or 0)

            status["applications"] = [
                item for item in applications
                if (
                    not self._is_application_disabled(item)
                    and self._matches_query(item.get("name"), item.get("description"), item.get("owner"), item.get("tags"), query=query)
                )
            ]
            status["phemars"] = [
                item for item in phemars
                if (
                    not self._is_agent_disabled(item, "phemars")
                    and self._matches_query(item.get("name"), item.get("description"), item.get("tags"), query=query)
                )
            ]
            status["castrs"] = [
                item for item in castrs
                if (
                    not self._is_agent_disabled(item, "castrs")
                    and self._matches_query(item.get("name"), item.get("description"), item.get("tags"), item.get("media_type"), query=query)
                )
            ]
            status["llm_pulsers"] = [
                item for item in llm_pulsers
                if self._matches_query(item.get("name"), item.get("description"), item.get("tags"), item.get("pulse_names"), query=query)
            ]
        except Exception as exc:
            status["error"] = str(exc)

        status["applications"].sort(key=lambda item: (item.get("name") or "").lower())
        status["phemars"].sort(key=lambda item: (item.get("name") or "").lower())
        status["castrs"].sort(key=lambda item: (item.get("name") or "").lower())
        status["llm_pulsers"].sort(key=lambda item: (item.get("name") or "").lower())
        return status

    def _build_catalog(self, query: str = "", party: str = "", plaza_url: str = "") -> Dict[str, Any]:
        """Internal helper to build the catalog."""
        selected_plazas = self._normalize_plaza_urls(plaza_url) if plaza_url else list(self.user_plaza_urls)
        if not selected_plazas and self.plaza_url:
            selected_plazas = [self.plaza_url.rstrip("/")]

        plazas = [self._fetch_single_plaza_catalog(url, query=query, party=party) for url in selected_plazas]

        applications: List[Dict[str, Any]] = []
        phemars: List[Dict[str, Any]] = []
        castrs: List[Dict[str, Any]] = []
        llm_pulsers: List[Dict[str, Any]] = []
        for plaza in plazas:
            applications.extend(plaza.get("applications") or [])
            phemars.extend(plaza.get("phemars") or [])
            castrs.extend(plaza.get("castrs") or [])
            llm_pulsers.extend(plaza.get("llm_pulsers") or [])

        return {
            "status": "success",
            "query": query,
            "party": party,
            "configured_applications": list(self.configured_applications),
            "plazas": plazas,
            "applications": applications,
            "phemars": phemars,
            "castrs": castrs,
            "llm_pulsers": llm_pulsers,
        }

    def _build_legacy_plaza_status(self, pit_type: Optional[str] = None) -> Dict[str, Any]:
        """Internal helper to build the legacy Plaza status."""
        plazas = []
        selected = list(self.user_plaza_urls)
        if not selected and self.plaza_url:
            selected = [self.plaza_url.rstrip("/")]

        for plaza_url in selected:
            status = {
                "url": plaza_url,
                "online": False,
                "authenticated": False,
                "connected_agent_id": "",
                "connected_agent_name": "",
                "connected_last_active": 0.0,
                "connection_status": "disconnected",
                "agents": [],
                "card": None,
                "error": "",
            }
            try:
                health = self._plaza_get("/health", plaza_url=plaza_url, retries=0)
                status["online"] = health.status_code == 200
                card_resp = self._plaza_get("/.well-known/agent-card", plaza_url=plaza_url, retries=0)
                if card_resp.status_code == 200 and card_resp.content:
                    status["card"] = card_resp.json()
                session = self._ensure_plaza_session(plaza_url)
                if session and session.get("token"):
                    status["authenticated"] = True
                    status.update(
                        self._build_plaza_connection_summary(
                            plaza_url,
                            agent_id=str(session.get("agent_id") or ""),
                            fallback_name=self.name,
                        )
                    )
                    status["agents"] = self._search_plaza(plaza_url, pit_type=pit_type or None)
                else:
                    status["error"] = "Unable to authenticate with plaza"
            except Exception as exc:
                status["error"] = str(exc)
            plazas.append(status)

        return {"status": "success", "plazas": plazas}

    def _resolve_catalog_item(
        self,
        items: List[Dict[str, Any]],
        *,
        item_id: str = "",
        name: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Internal helper to resolve the catalog item."""
        normalized_id = str(item_id or "").strip()
        if normalized_id:
            for item in items:
                if normalized_id in {
                    str(item.get("id") or "").strip(),
                    str(item.get("phema_id") or "").strip(),
                    str(item.get("agent_id") or "").strip(),
                }:
                    return item

        normalized_name = str(name or "").strip().lower()
        if normalized_name:
            exact = next((item for item in items if str(item.get("name") or "").strip().lower() == normalized_name), None)
            if exact:
                return exact
            partial = next((item for item in items if normalized_name in str(item.get("name") or "").strip().lower()), None)
            if partial:
                return partial
        return items[0] if items else None

    def _resolve_application_selection(
        self,
        *,
        application_id: str = "",
        application_name: str = "",
        query: str = "",
        party: str = "",
        plaza_url: str = "",
    ) -> Dict[str, Any]:
        """Internal helper to resolve the application selection."""
        catalog = self._build_catalog(query=query, party=party, plaza_url=plaza_url)
        selection = self._resolve_catalog_item(
            catalog.get("applications") or [],
            item_id=application_id,
            name=application_name or query,
        )
        if not selection:
            raise HTTPException(status_code=404, detail="No matching application was found on the selected plazas")
        return selection

    def _resolve_agent_selection(
        self,
        role: str,
        *,
        agent_id: str = "",
        agent_name: str = "",
        plaza_url: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Internal helper to resolve the agent selection."""
        catalog = self._build_catalog(plaza_url=plaza_url)
        key = "phemars" if role == "phemar" else "castrs"
        return self._resolve_catalog_item(catalog.get(key) or [], item_id=agent_id, name=agent_name)

    def _resolve_host_phemar_context(
        self,
        selected_application: Dict[str, Any],
        *,
        phemar_agent_id: str = "",
        phemar_name: str = "",
        phemar_address: str = "",
        phemar_plaza_url: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Internal helper to resolve the host phemar context."""
        preferred_agent_id = str(phemar_agent_id or selected_application.get("host_phemar_agent_id") or "").strip()
        preferred_name = str(phemar_name or selected_application.get("host_phemar_name") or "").strip()
        preferred_address = str(phemar_address or selected_application.get("host_phemar_address") or "").strip()
        preferred_plaza_url = str(
            phemar_plaza_url
            or selected_application.get("host_phemar_plaza_url")
            or selected_application.get("plaza_url")
            or ""
        ).strip()

        resolved = None
        if preferred_agent_id or preferred_name:
            resolved = self._resolve_agent_selection(
                "phemar",
                agent_id=preferred_agent_id,
                agent_name=preferred_name,
                plaza_url=preferred_plaza_url,
            )
        if resolved:
            merged = dict(resolved)
            if preferred_address and not str(merged.get("address") or "").strip():
                merged["address"] = preferred_address
            if preferred_plaza_url and not str(merged.get("plaza_url") or "").strip():
                merged["plaza_url"] = preferred_plaza_url
            if preferred_agent_id and not str(merged.get("agent_id") or "").strip():
                merged["agent_id"] = preferred_agent_id
            if preferred_name and not str(merged.get("name") or "").strip():
                merged["name"] = preferred_name
            return merged

        if preferred_address:
            return {
                "agent_id": preferred_agent_id,
                "name": preferred_name,
                "plaza_url": preferred_plaza_url,
                "address": preferred_address,
            }
        return None

    @staticmethod
    def _row_supports_practice(row: Dict[str, Any], practice_id: str) -> bool:
        """Return whether the row supports practice."""
        card = row.get("card") if isinstance(row.get("card"), dict) else {}
        practices = card.get("practices") if isinstance(card.get("practices"), list) else []
        normalized = str(practice_id or "").strip()
        if not normalized:
            return False
        return any(
            isinstance(entry, dict) and str(entry.get("id") or "").strip() == normalized
            for entry in practices
        )

    @staticmethod
    def _looks_like_llm_row(row: Dict[str, Any]) -> bool:
        """Internal helper to return the looks like LLM row."""
        card = row.get("card") if isinstance(row.get("card"), dict) else {}
        role = str(card.get("role") or row.get("role") or "").strip().lower()
        tags = [
            str(tag).strip().lower()
            for tag in (card.get("tags") or row.get("tags") or [])
            if str(tag).strip()
        ]
        text = " ".join(
            [
                str(row.get("name") or card.get("name") or ""),
                str(row.get("description") or card.get("description") or ""),
                " ".join(tags),
            ]
        ).lower()
        return (
            role == "llm"
            or "llm" in tags
            or "openai" in tags
            or "ollama" in tags
            or " llm" in f" {text}"
            or "openai" in text
            or "ollama" in text
        )

    @staticmethod
    def _candidate_llm_plaza_urls(*values: Any) -> List[str]:
        """Internal helper to return the candidate LLM Plaza URLs."""
        urls: List[str] = []
        seen = set()
        for value in values:
            for url in UserAgent._normalize_plaza_urls(value):
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
        return urls

    def _resolve_llm_preprocessor(
        self,
        *,
        selected_application: Dict[str, Any],
        resolved_phemar: Optional[Dict[str, Any]] = None,
        selected_castr: Optional[Dict[str, Any]] = None,
        llm_agent_id: str = "",
        llm_plaza_url: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Internal helper to resolve the LLM preprocessor."""
        candidate_plazas = self._candidate_llm_plaza_urls(
            llm_plaza_url,
            (selected_castr or {}).get("plaza_url"),
            (resolved_phemar or {}).get("plaza_url"),
            selected_application.get("plaza_url"),
            self.user_plaza_urls,
        )

        normalized_llm_agent_id = str(llm_agent_id or "").strip()
        if normalized_llm_agent_id:
            for plaza_url in candidate_plazas:
                pulser_rows = [
                    row for row in self._search_plaza(
                        plaza_url,
                        pit_type="Pulser",
                        pulse_name="llm_chat",
                        agent_id=normalized_llm_agent_id,
                    )
                    if isinstance(row, dict)
                ]
                if pulser_rows:
                    return self._map_llm_pulser_record(pulser_rows[0], plaza_url)

            for plaza_url in candidate_plazas:
                row = self._lookup_plaza_agent(plaza_url, agent_id=normalized_llm_agent_id)
                if not row or not self._row_supports_practice(row, "get_pulse_data"):
                    continue
                mapped = self._map_llm_pulser_record(row, plaza_url)
                if mapped.get("supports_llm_chat"):
                    return mapped

        for plaza_url in candidate_plazas:
            pulser_rows = [
                row for row in self._search_plaza(plaza_url, pit_type="Pulser", pulse_name="llm_chat")
                if isinstance(row, dict)
            ]
            if pulser_rows:
                return self._map_llm_pulser_record(pulser_rows[0], plaza_url)

        return None

    @staticmethod
    def _compose_cast_preferences(
        *,
        preferences: Optional[Dict[str, Any]] = None,
        personalization: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Internal helper for compose cast preferences."""
        merged = dict(preferences or {})
        personal = dict(personalization or {})

        for key in ("audience", "language", "tone", "style", "modifier", "instructions"):
            value = personal.get(key)
            if value not in (None, ""):
                merged[key] = value

        if personal.get("style") and "theme" not in merged:
            merged["theme"] = str(personal.get("style"))

        return merged

    @staticmethod
    def _strip_code_fences(value: str) -> str:
        """Internal helper to strip the code fences."""
        text = str(value or "").strip()
        if not text.startswith("```"):
            return text
        return re.sub(r"^```[a-zA-Z0-9_-]*\s*|\s*```$", "", text, flags=re.DOTALL).strip()

    @classmethod
    def _extract_json_object(cls, value: Any) -> Dict[str, Any]:
        """Internal helper to extract the JSON object."""
        if isinstance(value, dict):
            return dict(value)

        text = cls._strip_code_fences(str(value or ""))
        if not text:
            return {}

        candidates = [text]
        if "{" in text and "}" in text:
            candidates.append(text[text.find("{"):text.rfind("}") + 1])

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed
        return {}

    @staticmethod
    def _normalize_script_sections(sections: Any) -> List[Dict[str, Any]]:
        """Internal helper to normalize the script sections."""
        normalized: List[Dict[str, Any]] = []
        raw_sections = sections if isinstance(sections, list) else []
        for index, section in enumerate(raw_sections, start=1):
            if isinstance(section, dict):
                content = section.get("content")
                if isinstance(content, list):
                    items = [str(item).strip() for item in content if str(item).strip()]
                elif content in (None, ""):
                    items = []
                else:
                    items = [str(content).strip()]
                normalized.append(
                    {
                        "name": str(section.get("name") or f"Section {index}").strip() or f"Section {index}",
                        "description": str(section.get("description") or "").strip(),
                        "modifier": str(section.get("modifier") or "").strip(),
                        "content": items or ["No section content provided."],
                    }
                )
                continue

            text = str(section or "").strip()
            if not text:
                continue
            normalized.append(
                {
                    "name": f"Section {index}",
                    "description": "",
                    "modifier": "",
                    "content": [text],
                }
            )
        return normalized

    def _build_llm_precast_prompt(
        self,
        *,
        application: Dict[str, Any],
        snapshot: Dict[str, Any],
        selected_castr: Dict[str, Any],
        personalization: Optional[Dict[str, Any]] = None,
        format: str = "",
    ) -> str:
        """Internal helper to build the LLM precast prompt."""
        personalization_payload = dict(personalization or {})
        source_snapshot = dict(snapshot or {})
        prompt_payload = {
            "application": {
                "phema_id": application.get("phema_id") or application.get("id"),
                "name": application.get("name"),
                "description": application.get("description"),
            },
            "castr": {
                "agent_id": selected_castr.get("agent_id"),
                "name": selected_castr.get("name"),
                "media_type": selected_castr.get("media_type"),
            },
            "target_format": str(format or selected_castr.get("media_type") or "PDF"),
            "personalization": personalization_payload,
            "source_snapshot": source_snapshot,
        }

        schema = {
            "name": "string",
            "description": "string",
            "sections": [
                {
                    "name": "string",
                    "description": "string",
                    "modifier": "string",
                    "content": ["string"],
                }
            ],
            "preferences": {
                "tone": "string",
                "style": "string",
                "modifier": "string",
                "audience": "string",
                "language": "string",
                "instructions": "string",
            },
            "script_summary": "string",
        }

        return (
            "Create a temporary cast script for the selected snapshot.\n"
            "Rewrite the source snapshot so the final delivery matches the requested tone, style, and modifiers.\n"
            "Do not invent facts, figures, source names, or claims that are not already supported by the source snapshot.\n"
            "You may reorganize wording, emphasis, titles, descriptions, and section phrasing.\n"
            "Return valid JSON only. Do not wrap it in markdown.\n"
            f"Required JSON schema:\n{json.dumps(schema, indent=2, ensure_ascii=True)}\n\n"
            f"Context:\n{json.dumps(prompt_payload, indent=2, ensure_ascii=True, default=str)}"
        )

    def _build_temporary_cast_script(
        self,
        *,
        source_snapshot: Dict[str, Any],
        application: Dict[str, Any],
        selected_castr: Dict[str, Any],
        llm_result: Any,
        personalization: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Internal helper to build the temporary cast script."""
        parsed = self._extract_json_object(llm_result)
        base_snapshot = dict(source_snapshot or {})
        normalized_sections = self._normalize_script_sections(parsed.get("sections"))
        if not normalized_sections:
            normalized_sections = self._normalize_script_sections(base_snapshot.get("sections"))

        raw_text = self._strip_code_fences(str(llm_result or "")).strip()
        if not normalized_sections and raw_text:
            normalized_sections = [
                {
                    "name": "Generated Script",
                    "description": "",
                    "modifier": str((personalization or {}).get("modifier") or "").strip(),
                    "content": [raw_text],
                }
            ]

        temporary_script = dict(base_snapshot)
        temporary_script["name"] = str(
            parsed.get("name")
            or base_snapshot.get("name")
            or application.get("name")
            or "Temporary Script"
        ).strip()
        temporary_script["description"] = str(
            parsed.get("description")
            or base_snapshot.get("description")
            or application.get("description")
            or ""
        ).strip()
        temporary_script["sections"] = normalized_sections or [
            {
                "name": "Generated Script",
                "description": "",
                "modifier": str((personalization or {}).get("modifier") or "").strip(),
                "content": ["No temporary script content was generated."],
            }
        ]

        script_preferences = parsed.get("preferences") if isinstance(parsed.get("preferences"), dict) else {}
        if script_preferences:
            temporary_script["script_preferences"] = dict(script_preferences)
        if personalization:
            temporary_script["llm_personalization"] = dict(personalization)

        summary = str(parsed.get("script_summary") or "").strip()
        if summary:
            temporary_script["llm_script_summary"] = summary
        if raw_text:
            temporary_script["llm_raw_response"] = raw_text
        temporary_script["llm_target_castr"] = {
            "agent_id": str(selected_castr.get("agent_id") or "").strip(),
            "name": str(selected_castr.get("name") or "").strip(),
            "media_type": str(selected_castr.get("media_type") or "").strip(),
        }
        return temporary_script

    def _fetch_remote_snapshot_history(
        self,
        *,
        phemar: Dict[str, Any],
        phema_id: str,
        limit: int = 50,
        query: str = "",
    ) -> List[Dict[str, Any]]:
        """Internal helper to fetch the remote snapshot history."""
        target_url = str(phemar.get("address") or (phemar.get("card") or {}).get("address") or "").strip()
        if not target_url:
            raise HTTPException(status_code=400, detail=f"Phemar '{phemar.get('name') or phemar.get('agent_id')}' has no reachable address")

        response = requests.get(
            f"{target_url.rstrip('/')}/api/phema-snapshots",
            params={
                "phema_id": str(phema_id or "").strip(),
                "limit": max(int(limit or 0), 0) or 50,
                "q": str(query or "").strip(),
            },
            timeout=60,
        )
        if response.status_code != 200:
            detail = ""
            try:
                parsed = response.json()
                if isinstance(parsed, dict):
                    detail = str(parsed.get("detail") or parsed.get("message") or "")
            except Exception:
                detail = response.text
            raise HTTPException(
                status_code=response.status_code,
                detail=detail or f"Could not load snapshot history from {phemar.get('name') or phemar.get('agent_id')}",
            )

        payload = response.json() if response.content else {}
        snapshots = payload.get("snapshots") if isinstance(payload, dict) else []
        return [dict(item) for item in snapshots if isinstance(item, dict)]

    def _fetch_remote_snapshot(
        self,
        *,
        phemar: Dict[str, Any],
        snapshot_id: str,
    ) -> Dict[str, Any]:
        """Internal helper to fetch the remote snapshot."""
        normalized_snapshot_id = str(snapshot_id or "").strip()
        if not normalized_snapshot_id:
            raise HTTPException(status_code=400, detail="snapshot_id is required")

        target_url = str(phemar.get("address") or (phemar.get("card") or {}).get("address") or "").strip()
        if not target_url:
            raise HTTPException(status_code=400, detail=f"Phemar '{phemar.get('name') or phemar.get('agent_id')}' has no reachable address")

        response = requests.get(
            f"{target_url.rstrip('/')}/api/phema-snapshots/{normalized_snapshot_id}",
            timeout=60,
        )
        if response.status_code != 200:
            detail = ""
            try:
                parsed = response.json()
                if isinstance(parsed, dict):
                    detail = str(parsed.get("detail") or parsed.get("message") or "")
            except Exception:
                detail = response.text
            raise HTTPException(
                status_code=response.status_code,
                detail=detail or f"Could not load snapshot '{normalized_snapshot_id}' from {phemar.get('name') or phemar.get('agent_id')}",
            )

        payload = response.json() if response.content else {}
        snapshot = payload.get("snapshot") if isinstance(payload, dict) else None
        if not isinstance(snapshot, dict):
            raise HTTPException(status_code=404, detail="Requested snapshot was not returned by the remote Phemar")
        return snapshot

    def list_snapshots(
        self,
        *,
        application_id: str = "",
        application_name: str = "",
        phema_id: str = "",
        query: str = "",
        party: str = "",
        plaza_url: str = "",
        phemar_agent_id: str = "",
        phemar_name: str = "",
        phemar_address: str = "",
        phemar_plaza_url: str = "",
        limit: int = 50,
    ) -> Dict[str, Any]:
        """List remote snapshots for the selected application."""
        selected_application = self._resolve_application_selection(
            application_id=application_id,
            application_name=application_name,
            query=query,
            party=party,
            plaza_url=plaza_url,
        )

        resolved_phemar = self._resolve_host_phemar_context(
            selected_application,
            phemar_agent_id=phemar_agent_id,
            phemar_name=phemar_name,
            phemar_address=phemar_address,
            phemar_plaza_url=phemar_plaza_url,
        )
        if not resolved_phemar:
            raise HTTPException(status_code=404, detail="No matching Phemar was found for the selected application")

        snapshots = self._fetch_remote_snapshot_history(
            phemar=resolved_phemar,
            phema_id=str(phema_id or selected_application.get("phema_id") or selected_application.get("id") or "").strip(),
            limit=limit,
        )

        return {
            "status": "success",
            "application": selected_application,
            "phemar": resolved_phemar,
            "snapshots": snapshots,
        }

    def _unwrap_remote_response(self, payload: Any) -> Any:
        """Internal helper for unwrap remote response."""
        if isinstance(payload, dict) and payload.get("status") == "ok" and "result" in payload:
            return payload["result"]
        return payload

    @staticmethod
    def _safe_local_filename(value: str, fallback: str = "generated-result") -> str:
        """Internal helper for safe local filename."""
        cleaned = "".join(char.lower() if char.isalnum() else "-" for char in str(value or ""))
        compact = "-".join(part for part in cleaned.split("-") if part)
        return compact[:80] or fallback

    @staticmethod
    def _parse_json_like(value: Any) -> Any:
        """Internal helper to parse the JSON like."""
        if isinstance(value, (dict, list)):
            return value
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return raw

    def _saved_results_root(self) -> Optional[str]:
        """Internal helper for saved results root."""
        root_path = getattr(self.pool, "root_path", None)
        if not isinstance(root_path, str) or not root_path:
            return None
        return root_path

    def _saved_artifacts_root(self) -> Optional[str]:
        """Internal helper for saved artifacts root."""
        root = self._saved_results_root()
        if not root:
            return None
        target = os.path.join(root, self.SAVED_ARTIFACTS_DIR)
        os.makedirs(target, exist_ok=True)
        return target

    def _copy_cast_artifact_to_local(
        self,
        *,
        cast_payload: Dict[str, Any],
        title: str,
    ) -> Dict[str, str]:
        """Internal helper for copy cast artifact to local."""
        public_url = str(cast_payload.get("public_url") or "").strip()
        if not public_url:
            return {}
        artifacts_root = self._saved_artifacts_root()
        if not artifacts_root:
            return {}

        ext = ""
        location = str(cast_payload.get("location") or "").strip()
        if location and "." in os.path.basename(location):
            _, ext = os.path.splitext(location)
        if not ext:
            url_path = public_url.split("?", 1)[0]
            _, ext = os.path.splitext(url_path)
        if not ext:
            ext = f".{str(cast_payload.get('format') or 'txt').strip().lower()}"

        filename = f"{self._safe_local_filename(title)}-{int(time.time())}{ext}"
        file_path = os.path.join(artifacts_root, filename)

        response = requests.get(public_url, timeout=60)
        response.raise_for_status()
        with open(file_path, "wb") as handle:
            handle.write(response.content)

        return {
            "local_artifact_name": filename,
            "local_artifact_path": file_path,
            "local_artifact_url": f"/api/saved_artifacts/{filename}",
        }

    def _build_saved_result_summary(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to build the saved result summary."""
        metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}
        payload = self._parse_json_like(record.get("content"))
        if not isinstance(payload, dict):
            payload = {}

        application = payload.get("application") if isinstance(payload.get("application"), dict) else {}
        snapshot_wrapper = payload.get("snapshot") if isinstance(payload.get("snapshot"), dict) else {}
        snapshot = snapshot_wrapper.get("snapshot") if isinstance(snapshot_wrapper.get("snapshot"), dict) else {}
        temporary_script = payload.get("temporary_script") if isinstance(payload.get("temporary_script"), dict) else {}
        cast = payload.get("cast") if isinstance(payload.get("cast"), dict) else {}

        return {
            "id": str(record.get("id") or ""),
            "title": str(
                metadata.get("title")
                or temporary_script.get("name")
                or snapshot.get("name")
                or application.get("name")
                or "Saved generated result"
            ).strip(),
            "saved_at": str(metadata.get("saved_at") or record.get("updated_at") or record.get("created_at") or ""),
            "application_name": str(metadata.get("application_name") or application.get("name") or "").strip(),
            "phema_name": str(metadata.get("phema_name") or temporary_script.get("name") or snapshot.get("name") or "").strip(),
            "castr_name": str(metadata.get("castr_name") or (payload.get("castr") or {}).get("name") or "").strip(),
            "format": str(metadata.get("format") or cast.get("format") or "").strip(),
            "local_artifact_name": str(metadata.get("local_artifact_name") or "").strip(),
            "local_artifact_path": str(metadata.get("local_artifact_path") or "").strip(),
            "local_artifact_url": str(metadata.get("local_artifact_url") or "").strip(),
            "public_artifact_url": str(cast.get("public_url") or "").strip(),
            "payload": payload,
        }

    def _list_saved_results(self, query: str = "") -> List[Dict[str, Any]]:
        """Internal helper to list the saved results."""
        if not self.pool or not self.pool._TableExists(self.SAVED_RESULTS_TABLE):
            return []

        if query.strip():
            rows = self.pool.search_memory(query.strip(), limit=100, table_name=self.SAVED_RESULTS_TABLE)
        else:
            rows = self.pool._GetTableData(self.SAVED_RESULTS_TABLE) or []

        summaries = [self._build_saved_result_summary(row) for row in rows if isinstance(row, dict)]
        summaries.sort(key=lambda item: str(item.get("saved_at") or ""), reverse=True)
        return summaries

    def _save_local_result(self, result: Dict[str, Any], title: str = "") -> Dict[str, Any]:
        """Internal helper to save the local result."""
        if not self.pool:
            raise HTTPException(status_code=400, detail="This user agent has no local pool configured")
        if not isinstance(result, dict):
            raise HTTPException(status_code=400, detail="Saved result payload must be a JSON object")

        application = result.get("application") if isinstance(result.get("application"), dict) else {}
        snapshot_wrapper = result.get("snapshot") if isinstance(result.get("snapshot"), dict) else {}
        snapshot = snapshot_wrapper.get("snapshot") if isinstance(snapshot_wrapper.get("snapshot"), dict) else {}
        temporary_script = result.get("temporary_script") if isinstance(result.get("temporary_script"), dict) else {}
        cast = result.get("cast") if isinstance(result.get("cast"), dict) else {}

        resolved_title = str(
            title
            or temporary_script.get("name")
            or snapshot.get("name")
            or application.get("name")
            or "Saved generated result"
        ).strip()
        metadata = {
            "title": resolved_title,
            "application_name": str(application.get("name") or "").strip(),
            "phema_name": str(temporary_script.get("name") or snapshot.get("name") or application.get("name") or "").strip(),
            "castr_name": str((result.get("castr") or {}).get("name") or "").strip(),
            "format": str(cast.get("format") or "").strip(),
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        try:
            if cast:
                metadata.update(self._copy_cast_artifact_to_local(cast_payload=cast, title=resolved_title))
        except Exception as exc:
            metadata["local_artifact_error"] = str(exc)

        record = self.pool.store_memory(
            content=result,
            metadata=metadata,
            tags=[
                "prompits",
                "user-agent",
                "saved-result",
                str(application.get("name") or "").strip(),
                str((result.get("castr") or {}).get("name") or "").strip(),
            ],
            memory_type="json",
            table_name=self.SAVED_RESULTS_TABLE,
        )
        return self._build_saved_result_summary(record)

    def _invoke_remote_practice_on_agent(
        self,
        *,
        plaza_url: str,
        agent: Dict[str, Any],
        practice_id: str,
        content: Any,
        timeout: int = 120,
    ) -> Any:
        """Internal helper to invoke the remote practice on agent."""
        normalized_plaza = str(plaza_url or "").strip().rstrip("/")
        target_url = str(agent.get("address") or (agent.get("card") or {}).get("address") or "").strip()
        target_agent_id = str(agent.get("agent_id") or (agent.get("card") or {}).get("agent_id") or "").strip()
        if not target_url:
            raise HTTPException(status_code=400, detail=f"Target agent '{agent.get('name') or target_agent_id}' has no reachable address")

        session = self._ensure_plaza_session(normalized_plaza)
        if not session or not session.get("token") or not session.get("agent_id"):
            raise HTTPException(status_code=503, detail=f"UserAgent could not authenticate against plaza '{normalized_plaza}'")

        payload = {
            "sender": str(session.get("agent_id") or self.name),
            "receiver": target_agent_id,
            "content": content,
            "msg_type": practice_id,
            "caller_agent_address": {
                "pit_id": str(session.get("agent_id") or ""),
                "plazas": [normalized_plaza],
            },
            "caller_plaza_token": str(session.get("token") or ""),
            "caller_direct_token": self.direct_auth_token,
        }
        response = requests.post(
            f"{target_url.rstrip('/')}/use_practice/{practice_id}",
            json=payload,
            timeout=timeout,
        )
        if response.status_code != 200:
            detail = ""
            try:
                parsed = response.json()
                if isinstance(parsed, dict):
                    detail = str(parsed.get("detail") or parsed.get("message") or "")
            except Exception:
                detail = response.text
            raise HTTPException(
                status_code=response.status_code,
                detail=detail or f"Remote practice '{practice_id}' failed on {agent.get('name') or target_agent_id}",
            )
        parsed = response.json() if response.content else {}
        return self._unwrap_remote_response(parsed)

    def generate_result(
        self,
        *,
        application_id: str = "",
        application_name: str = "",
        phema_id: str = "",
        query: str = "",
        party: str = "",
        plaza_url: str = "",
        phemar_agent_id: str = "",
        phemar_name: str = "",
        phemar_address: str = "",
        phemar_plaza_url: str = "",
        castr_agent_id: str = "",
        castr_plaza_url: str = "",
        llm_agent_id: str = "",
        llm_plaza_url: str = "",
        snapshot_id: str = "",
        params: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None,
        personalization: Optional[Dict[str, Any]] = None,
        use_llm_preprocessor: bool = False,
        format: str = "",
        cache_time: Optional[int] = 300,
    ) -> Dict[str, Any]:
        """Generate a user-agent result."""
        selected_application = self._resolve_application_selection(
            application_id=application_id,
            application_name=application_name,
            query=query,
            party=party,
            plaza_url=plaza_url,
        )

        resolved_phemar = self._resolve_host_phemar_context(
            selected_application,
            phemar_agent_id=phemar_agent_id,
            phemar_name=phemar_name,
            phemar_address=phemar_address,
            phemar_plaza_url=phemar_plaza_url,
        )
        if not resolved_phemar:
            raise HTTPException(status_code=404, detail="No matching Phemar was found for the selected application")

        snapshot_source = "generated"
        normalized_snapshot_id = str(snapshot_id or "").strip()
        if normalized_snapshot_id:
            snapshot_row = self._fetch_remote_snapshot(
                phemar=resolved_phemar,
                snapshot_id=normalized_snapshot_id,
            )
            selected_phema_id = str(selected_application.get("phema_id") or selected_application.get("id") or "").strip()
            snapshot_phema_id = str(snapshot_row.get("phema_id") or "").strip()
            if selected_phema_id and snapshot_phema_id and selected_phema_id != snapshot_phema_id:
                raise HTTPException(status_code=400, detail="The selected snapshot does not belong to the chosen Phema")
            snapshot_result = {
                "status": "success",
                "snapshot_id": str(snapshot_row.get("snapshot_id") or snapshot_row.get("id") or normalized_snapshot_id),
                "cached": True,
                "history": snapshot_row,
                "snapshot": snapshot_row.get("snapshot") if isinstance(snapshot_row.get("snapshot"), dict) else {},
            }
            snapshot_source = "existing"
        else:
            snapshot_payload: Dict[str, Any] = {
                "phema_id": phema_id or selected_application.get("phema_id") or selected_application.get("id"),
                "phema_name": selected_application.get("name"),
                "params": dict(params or {}),
            }
            if cache_time is not None:
                snapshot_payload["cache_time"] = int(cache_time)

            snapshot_result = self._invoke_remote_practice_on_agent(
                plaza_url=resolved_phemar.get("plaza_url") or selected_application.get("plaza_url") or "",
                agent=resolved_phemar,
                practice_id="snapshot_phema",
                content=snapshot_payload,
            )
            if isinstance(snapshot_result, dict) and snapshot_result.get("cached"):
                snapshot_source = "cached"

        selected_castr = None
        cast_result = None
        selected_llm = None
        temporary_script = None
        if castr_agent_id:
            selected_castr = self._resolve_agent_selection(
                "castr",
                agent_id=castr_agent_id,
                plaza_url=castr_plaza_url,
            )
            if not selected_castr:
                raise HTTPException(status_code=404, detail="No matching Castr was found for the selected renderer")

            cast_source = snapshot_result.get("snapshot") if isinstance(snapshot_result, dict) else snapshot_result
            cast_preferences = self._compose_cast_preferences(
                preferences=preferences,
                personalization=personalization,
            )

            if use_llm_preprocessor:
                selected_llm = self._resolve_llm_preprocessor(
                    selected_application=selected_application,
                    resolved_phemar=resolved_phemar,
                    selected_castr=selected_castr,
                    llm_agent_id=llm_agent_id,
                    llm_plaza_url=llm_plaza_url,
                )
                if not selected_llm:
                    raise HTTPException(status_code=503, detail="No LLM pulser or agent is available for pre-cast personalization")

                llm_prompt = self._build_llm_precast_prompt(
                    application=selected_application,
                    snapshot=cast_source if isinstance(cast_source, dict) else {},
                    selected_castr=selected_castr,
                    personalization=personalization,
                    format=str(format or selected_castr.get("media_type") or "PDF"),
                )
                llm_practice_id = str(selected_llm.get("practice_id") or "llm")
                llm_content: Dict[str, Any]
                if llm_practice_id == "get_pulse_data":
                    llm_content = {
                        "pulse_name": str(selected_llm.get("pulse_name") or "llm_chat"),
                        "input_data": {"prompt": llm_prompt},
                    }
                else:
                    llm_content = {"prompt": llm_prompt}
                llm_response = self._invoke_remote_practice_on_agent(
                    plaza_url=selected_llm.get("plaza_url") or "",
                    agent=selected_llm,
                    practice_id=llm_practice_id,
                    content=llm_content,
                    timeout=240,
                )
                llm_output = llm_response.get("response") if isinstance(llm_response, dict) else llm_response
                temporary_script = self._build_temporary_cast_script(
                    source_snapshot=cast_source if isinstance(cast_source, dict) else {},
                    application=selected_application,
                    selected_castr=selected_castr,
                    llm_result=llm_output,
                    personalization=personalization,
                )
                cast_source = temporary_script

            cast_result = self._invoke_remote_practice_on_agent(
                plaza_url=selected_castr.get("plaza_url") or "",
                agent=selected_castr,
                practice_id="cast_phema",
                content={
                    "phema": cast_source,
                    "format": str(format or selected_castr.get("media_type") or "PDF"),
                    "preferences": cast_preferences,
                },
            )
            if isinstance(cast_result, dict):
                relative_url = str(cast_result.get("url") or "").strip()
                if relative_url.startswith("/"):
                    cast_result["public_url"] = f"{str(selected_castr.get('address') or '').rstrip('/')}{relative_url}"

        return {
            "status": "success",
            "application": selected_application,
            "phemar": resolved_phemar,
            "castr": selected_castr,
            "llm": selected_llm,
            "snapshot_source": snapshot_source,
            "snapshot": snapshot_result,
            "temporary_script": temporary_script,
            "cast": cast_result,
        }

    def setup_user_agent_routes(self):
        """Set up the user agent routes."""
        supported_pit_types = sorted(PlazaPractice.SUPPORTED_PIT_TYPES)

        @self.app.get("/")
        async def index(request: Request):
            """Route handler for GET /."""
            return self.templates.TemplateResponse(
                request=request,
                name="user_agent.html",
                context={
                    "request": request,
                    "agent_name": self.name,
                    "plaza_urls": list(self.user_plaza_urls),
                },
            )

        @self.app.get("/user-agent")
        async def user_agent_index(request: Request):
            """Route handler for GET /user-agent."""
            return self.templates.TemplateResponse(
                request=request,
                name="user_agent.html",
                context={
                    "request": request,
                    "agent_name": self.name,
                    "plaza_urls": list(self.user_plaza_urls),
                },
            )

        @self.app.get("/plazas")
        async def plazas(request: Request):
            """Route handler for GET /plazas."""
            return self.templates.TemplateResponse(
                request=request,
                name="plazas.html",
                context={"request": request, "agent_name": self.name, "supported_pit_types": supported_pit_types},
            )

        @self.app.get("/api/plazas_status")
        async def plazas_status(request: Request):
            """Route handler for GET /api/plazas_status."""
            pit_type = request.query_params.get("pit_type")

            def _plazas_status_sync() -> Dict[str, Any]:
                """Internal helper for plazas status sync."""
                if pit_type:
                    selected = self._normalize_plaza_urls(request.query_params.get("plaza_url")) or list(self.user_plaza_urls)
                    plazas = []
                    for plaza_url in selected:
                        status = self._fetch_single_plaza_catalog(plaza_url)
                        status["agents"] = (
                            self._search_plaza(plaza_url, pit_type=pit_type)
                            if status.get("authenticated")
                            else []
                        )
                        plazas.append(status)
                    return {"status": "success", "plazas": plazas}
                return self._build_legacy_plaza_status()

            return await run_in_threadpool(_plazas_status_sync)

        @self.app.get("/api/catalog")
        async def catalog(request: Request):
            """Route handler for GET /api/catalog."""
            query = str(request.query_params.get("q") or "").strip()
            party = str(request.query_params.get("party") or "").strip()
            plaza_filter = str(request.query_params.get("plaza_url") or "").strip()
            return await run_in_threadpool(self._build_catalog, query, party, plaza_filter)

        @self.app.get("/api/agent_configs")
        async def list_agent_configs(request: Request):
            """Route handler for GET /api/agent_configs."""
            query = str(request.query_params.get("q") or "").strip()
            name = str(request.query_params.get("name") or "").strip()
            owner = str(request.query_params.get("owner") or "").strip()
            role = str(request.query_params.get("role") or "").strip()
            agent_type = str(request.query_params.get("agent_type") or "").strip()
            plaza_filter = str(request.query_params.get("plaza_url") or "").strip()
            include_config = str(request.query_params.get("include_config") or "").strip().lower() in {"1", "true", "yes"}

            def _list_agent_configs_sync() -> Dict[str, Any]:
                """Internal helper to list the agent configs sync."""
                plazas = []
                all_configs: List[Dict[str, Any]] = []
                for plaza_url in self._resolve_config_plaza_urls(plaza_filter):
                    status = {"url": plaza_url, "agent_configs": [], "error": ""}
                    try:
                        rows = self._fetch_plaza_agent_configs(
                            plaza_url,
                            q=query,
                            name=name,
                            owner=owner,
                            role=role,
                            agent_type=agent_type,
                            include_config=str(include_config).lower(),
                        )
                        rows = [row for row in rows if not self._is_agent_config_disabled(row)]
                        status["agent_configs"] = rows
                        all_configs.extend(rows)
                    except Exception as exc:
                        status["error"] = str(exc)
                    plazas.append(status)

                all_configs.sort(key=lambda item: ((item.get("name") or "").lower(), item.get("plaza_url") or ""))
                return {"status": "success", "plazas": plazas, "agent_configs": all_configs}

            return await run_in_threadpool(_list_agent_configs_sync)

        @self.app.post("/api/agent_configs")
        async def save_agent_config(request: Request):
            """Route handler for POST /api/agent_configs."""
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Agent config payload must be a JSON object")

            config = payload.get("config")
            if not isinstance(config, dict):
                raise HTTPException(status_code=400, detail="config must be a JSON object")

            selected_plaza = self._resolve_config_plaza_urls(str(payload.get("plaza_url") or "").strip())
            if not selected_plaza:
                raise HTTPException(status_code=400, detail="No plaza is configured for agent config storage")

            saved = await run_in_threadpool(
                self._save_plaza_agent_config,
                plaza_url=selected_plaza[0],
                config=config,
                config_id=str(payload.get("config_id") or "").strip(),
                owner=str(payload.get("owner") or "").strip(),
                name=str(payload.get("name") or "").strip(),
                description=str(payload.get("description") or "").strip(),
            )
            return {"status": "success", "agent_config": saved}

        @self.app.post("/api/agent_configs/launch")
        async def launch_agent_config(request: Request):
            """Route handler for POST /api/agent_configs/launch."""
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Launch payload must be a JSON object")

            selected_plaza = self._resolve_config_plaza_urls(str(payload.get("plaza_url") or "").strip())
            if not selected_plaza:
                raise HTTPException(status_code=400, detail="No plaza is configured for agent launches")

            config_id = str(payload.get("config_id") or "").strip()
            config = payload.get("config") if isinstance(payload.get("config"), dict) else None
            await run_in_threadpool(
                self._ensure_agent_config_launch_allowed,
                plaza_url=selected_plaza[0],
                config_id=config_id,
                config=config,
            )

            launch = await run_in_threadpool(
                self._launch_plaza_agent_config,
                plaza_url=selected_plaza[0],
                config_id=config_id,
                config=config,
                owner=str(payload.get("owner") or "").strip(),
                name=str(payload.get("name") or "").strip(),
                description=str(payload.get("description") or "").strip(),
                agent_name=str(payload.get("agent_name") or "").strip(),
                host=str(payload.get("host") or "").strip(),
                port=payload.get("port"),
                pool_type=str(payload.get("pool_type") or "").strip(),
                pool_location=str(payload.get("pool_location") or "").strip(),
                wait_for_health_sec=float(payload.get("wait_for_health_sec") or 15.0),
            )
            return {"status": "success", "launch": launch}

        @self.app.get("/api/snapshots")
        async def snapshots(request: Request):
            """Route handler for GET /api/snapshots."""
            return await run_in_threadpool(
                self.list_snapshots,
                application_id=str(request.query_params.get("application_id") or "").strip(),
                application_name=str(request.query_params.get("application_name") or "").strip(),
                phema_id=str(request.query_params.get("phema_id") or "").strip(),
                query=str(request.query_params.get("q") or "").strip(),
                party=str(request.query_params.get("party") or "").strip(),
                plaza_url=str(request.query_params.get("plaza_url") or "").strip(),
                phemar_agent_id=str(request.query_params.get("phemar_agent_id") or "").strip(),
                phemar_name=str(request.query_params.get("phemar_name") or "").strip(),
                phemar_address=str(request.query_params.get("phemar_address") or "").strip(),
                phemar_plaza_url=str(request.query_params.get("phemar_plaza_url") or "").strip(),
                limit=int(request.query_params.get("limit") or 50),
            )

        @self.app.post("/api/generate")
        async def generate(request: Request):
            """Route handler for POST /api/generate."""
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Generate payload must be a JSON object")

            return await run_in_threadpool(
                self.generate_result,
                application_id=str(payload.get("application_id") or "").strip(),
                application_name=str(payload.get("application_name") or "").strip(),
                phema_id=str(payload.get("phema_id") or "").strip(),
                query=str(payload.get("query") or payload.get("q") or "").strip(),
                party=str(payload.get("party") or "").strip(),
                plaza_url=str(payload.get("plaza_url") or "").strip(),
                phemar_agent_id=str(payload.get("phemar_agent_id") or "").strip(),
                phemar_name=str(payload.get("phemar_name") or "").strip(),
                phemar_address=str(payload.get("phemar_address") or "").strip(),
                phemar_plaza_url=str(payload.get("phemar_plaza_url") or "").strip(),
                castr_agent_id=str(payload.get("castr_agent_id") or "").strip(),
                castr_plaza_url=str(payload.get("castr_plaza_url") or "").strip(),
                llm_agent_id=str(payload.get("llm_agent_id") or "").strip(),
                llm_plaza_url=str(payload.get("llm_plaza_url") or "").strip(),
                snapshot_id=str(payload.get("snapshot_id") or "").strip(),
                params=dict(payload.get("params") or {}),
                preferences=dict(payload.get("preferences") or {}),
                personalization=dict(payload.get("personalization") or {}),
                use_llm_preprocessor=bool(payload.get("use_llm_preprocessor")),
                format=str(payload.get("format") or "").strip(),
                cache_time=payload.get("cache_time", 300),
            )

        @self.app.get("/api/saved_results")
        async def saved_results(request: Request):
            """Route handler for GET /api/saved_results."""
            query = str(request.query_params.get("q") or "").strip()
            return {"status": "success", "results": await run_in_threadpool(self._list_saved_results, query)}

        @self.app.post("/api/saved_results")
        async def save_result(request: Request):
            """Route handler for POST /api/saved_results."""
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Save payload must be a JSON object")
            result = payload.get("result")
            saved = await run_in_threadpool(self._save_local_result, result, str(payload.get("title") or "").strip())
            return {"status": "success", "saved_result": saved}

        @self.app.get("/api/saved_artifacts/{filename}")
        async def saved_artifact(filename: str):
            """Route handler for GET /api/saved_artifacts/{filename}."""
            artifacts_root = self._saved_artifacts_root()
            if not artifacts_root:
                raise HTTPException(status_code=404, detail="No local saved artifacts directory is configured")
            safe_name = os.path.basename(filename)
            if safe_name != filename:
                raise HTTPException(status_code=400, detail="Invalid filename")
            file_path = os.path.join(artifacts_root, safe_name)
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="Saved artifact not found")
            return FileResponse(file_path)

        @self.app.post("/api/send_message")
        async def api_send_message(request: Request):
            """Route handler for POST /api/send_message."""
            try:
                data = await request.json()
                receiver = data.get("receiver")
                content = data.get("content")
                msg_type = data.get("msg_type", "message")

                if not receiver or not content:
                    return {"status": "error", "message": "Missing receiver or content"}

                result = await run_in_threadpool(self.send, receiver, content, msg_type)
                if result:
                    return {
                        "status": "success",
                        "message": f"Message sent to {receiver}",
                        "data": result if isinstance(result, dict) else None,
                    }
                return {"status": "error", "message": f"Failed to send message to {receiver}"}
            except Exception as exc:
                self.logger.error("API send_message failed: %s", exc)
                return {"status": "error", "message": str(exc)}

    def receive(self, message: Message):
        """Handle receive for the user agent."""
        self.logger.info("Received message: %s", message)

    def run(self):
        """Run the value."""
        import uvicorn

        uvicorn.run(self.app, host=self.host, port=self.port)
