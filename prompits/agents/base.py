"""
Base module for `prompits.agents.base`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, these modules provide reusable
agent hosts and user-facing agent variants.

Core types exposed here include `BaseAgent` and `PracticeInvocationRequest`, which carry
the main behavior or state managed by this module.
"""

import logging
import asyncio
import inspect
import json
import os
import requests
import httpx
import uvicorn
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from prompits.core.message import Message
from prompits.core.init_schema import agent_practices_table_schema
from prompits.core.pit import Pit, PitAddress
from prompits.core.practice import Practice
from prompits.practices.plaza import PlazaCredentialStore
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

from prompits.core.pool import Pool


class PracticeInvocationRequest(BaseModel):
    """Envelope used for remote `UsePractice` execution between agents."""

    sender: str
    receiver: str
    content: Any = None
    msg_type: str
    caller_agent_address: Optional[Dict[str, Any]] = None
    caller_plaza_token: Optional[str] = None
    caller_direct_token: Optional[str] = None

class BaseAgent(Pit, ABC):
    """
    Core runtime abstraction for every networked agent in the Prompits system.

    Responsibilities:
    - Host a FastAPI app and mount practices.
    - Register/authenticate with Plaza and maintain heartbeat/token lifecycle.
    - Resolve peers and route local/remote practice invocations.
    - Persist and reload practice metadata and Plaza credentials through `Pool`.
    """

    AGENT_PRACTICES_TABLE = "agent_practices"
    PLAZA_REQUEST_TIMEOUT = 30
    PLAZA_REQUEST_RETRIES = 5
    PLAZA_RETRY_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
    PLAZA_HEARTBEAT_INTERVAL = 10
    PLAZA_REJECTED_CREDENTIAL_RETRY_DELAY = 60
    PLAZA_RECONNECT_INTERVAL = 60
    PLAZA_CONNECTION_ACTIVE_WINDOW_SEC = 60
    MAILBOX_PRACTICE_ID = "mailbox"
    LEGACY_REMOVED_PRACTICE_IDS = ("chat-practice", "llm")

    @staticmethod
    def _normalize_url(value: Any) -> str:
        """Internal helper to normalize the URL."""
        if value is None:
            return ""
        return str(value).strip().rstrip("/")

    @staticmethod
    def _coerce_optional_bool(value: Any) -> Optional[bool]:
        """Internal helper to coerce the optional bool."""
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        lowered = str(value).strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
        return None

    def __init__(self, name: str, host: str = "127.0.0.1", port: int = 8000, plaza_url: Optional[str] = None, agent_card: Dict[str, Any] = None, pool: Optional[Pool] = None):
        """Initialize the base agent."""
        seed_card = agent_card or {"name": name, "role": "generic", "tags": []}
        super().__init__(
            name=name,
            description=seed_card.get("description", ""),
            address=PitAddress.from_value(seed_card.get("pit_address")),
            meta=seed_card.get("meta", {})
        )
        self.name = name
        self.host = host
        self.port = port
        self.plaza_url = plaza_url
        self.agent_card = seed_card
        self.agent_card.setdefault("pit_type", "Agent")
        self.agent_card.setdefault("meta", {})
        self.agent_card.setdefault("host", host)
        self.agent_card.setdefault("port", port)
        self.agent_card["address"] = self._resolve_advertised_address()
        self.pool = pool
        self.plaza_credential_store = PlazaCredentialStore(pool=pool)
        self.agent_id: Optional[str] = self.agent_card.get("agent_id")
        self.api_key: Optional[str] = self.agent_card.get("api_key")
        configured_direct_token = (
            self.agent_card.get("meta", {}).get("direct_auth_token")
            or os.getenv("PROMPITS_DIRECT_TOKEN")
            or ""
        )
        self.direct_auth_token: Optional[str] = str(configured_direct_token).strip() or None
        self._sync_connectivity_metadata()
        self.pit_address: PitAddress = self.address
        self._refresh_pit_address()
        
        self.plaza_token: Optional[str] = None
        self.token_expires_at: float = 0.0
        self._credential_retry_after: float = 0.0
        self.last_plaza_heartbeat_at: float = 0.0
        self._plaza_connection_error: str = ""
        self._register_lock = threading.Lock()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_thread_lock = threading.Lock()
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_thread_lock = threading.Lock()
        
        # Ensure practices list exists in card
        if "practices" not in self.agent_card:
            self.agent_card["practices"] = []
        self._practice_persistence_batch_depth = 0
        self._pending_practice_rows: Dict[str, Dict[str, Any]] = {}

        self._ensure_agent_practices_table()
        self._load_practices_info_from_pool()
        
        # FastAPI App
        self.app = FastAPI(title=name)
        
        self.practices: List[Practice] = []
        self.logger = logging.LoggerAdapter(logger, {"agent_name": self.name})

        # Static Files mapping
        from pathlib import Path
        base_dir = Path(__file__).parent.resolve()
        static_dir = base_dir / "static"
        
        if static_dir.exists():
            self.app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
            self.logger.info(f"Mounted static directory: {static_dir}")
        else:
            self.logger.warning(f"Static directory NOT FOUND: {static_dir}")

        self.site_settings: Dict[str, Any] = {}
        self._install_request_logging()

        self._begin_practice_persistence_batch()
        try:
            self._prune_legacy_practices()
            self.add_practice_endpoint(self._mailbox_practice_metadata())
            self._register_pool_operation_practices()
        finally:
            self._end_practice_persistence_batch()
        self.setup_routes()

    def _install_request_logging(self):
        """Internal helper for install request logging."""
        @self.app.middleware("http")
        async def log_incoming_request(request: Request, call_next):
            """Log the incoming request."""
            started_at = time.perf_counter()
            client_host = request.client.host if request.client else "-"
            client_port = request.client.port if request.client else "-"
            query = f"?{request.url.query}" if request.url.query else ""
            path = f"{request.url.path}{query}"

            self.logger.info(
                f"Incoming request {request.method} {path} from {client_host}:{client_port}"
            )
            try:
                response = await call_next(request)
            except Exception:
                elapsed_ms = (time.perf_counter() - started_at) * 1000
                self.logger.exception(
                    f"Request failed {request.method} {path} from {client_host}:{client_port} "
                    f"after {elapsed_ms:.1f}ms"
                )
                raise

            elapsed_ms = (time.perf_counter() - started_at) * 1000
            self.logger.info(
                f"Completed request {request.method} {path} from {client_host}:{client_port} "
                f"with {response.status_code} in {elapsed_ms:.1f}ms"
            )
            return response

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

    def _mark_plaza_connection_alive(self, timestamp: Optional[float] = None):
        """Internal helper for mark Plaza connection alive."""
        self.last_plaza_heartbeat_at = float(timestamp or time.time())
        self._plaza_connection_error = ""

    def _fetch_remote_plaza_last_active(self, headers: Optional[Dict[str, str]] = None) -> float:
        """Internal helper to fetch the remote Plaza last active."""
        if not self.plaza_url or not self.agent_id:
            return 0.0

        request_headers = headers if isinstance(headers, dict) and headers.get("Authorization") else self._ensure_token_valid()
        if not request_headers or not request_headers.get("Authorization"):
            return 0.0

        try:
            response = self._plaza_get(
                "/search",
                params={"agent_id": self.agent_id},
                headers=request_headers,
                retries=0,
            )
        except Exception as exc:
            self._plaza_connection_error = self._plaza_connection_error or str(exc)
            return 0.0

        if response.status_code in (401, 403):
            self._plaza_connection_error = self._plaza_connection_error or f"Plaza rejected agent lookup ({response.status_code})"
            return 0.0
        if response.status_code != 200:
            return 0.0

        try:
            payload = response.json() if response.content else []
        except Exception:
            return 0.0
        if not isinstance(payload, list) or not payload:
            return 0.0
        first = payload[0] if isinstance(payload[0], dict) else {}
        return float(first.get("last_active") or 0)

    def get_plaza_connection_status(self) -> Dict[str, Any]:
        """Return the Plaza connection status."""
        normalized_plaza_url = self._normalize_url(self.plaza_url)
        base_status = {
            "status": "success",
            "plaza_url": normalized_plaza_url,
            "agent_name": self.name,
            "agent_id": str(self.agent_id or ""),
            "online": False,
            "authenticated": False,
            "last_active": 0.0,
            "connection_status": "not_configured",
            "error": "",
        }

        if not normalized_plaza_url:
            return base_status

        try:
            health = self._plaza_get("/health", plaza_url=normalized_plaza_url, retries=0)
            base_status["online"] = health.status_code == 200
        except Exception as exc:
            self._plaza_connection_error = self._plaza_connection_error or str(exc)

        headers = self._ensure_token_valid()
        base_status["authenticated"] = bool(headers and headers.get("Authorization"))

        remote_last_active = self._fetch_remote_plaza_last_active(headers=headers)
        last_active = max(float(self.last_plaza_heartbeat_at or 0), float(remote_last_active or 0))
        base_status["last_active"] = last_active
        base_status["connection_status"] = (
            "connected"
            if base_status["online"] and self._heartbeat_is_active(last_active)
            else "disconnected"
        )

        if self._plaza_connection_error:
            base_status["error"] = self._plaza_connection_error
        elif not base_status["online"]:
            base_status["error"] = "Plaza is unreachable."
        elif not base_status["authenticated"]:
            base_status["error"] = "Waiting for Plaza authentication."
        elif not last_active:
            base_status["error"] = "No heartbeat reported yet."

        return base_status

    def _load_plaza_credentials_from_pool(self):
        """Internal helper to load the Plaza credentials from pool."""
        if not self.pool or not self.plaza_url:
            return
        if not self._reuse_plaza_identity():
            return
        if self.agent_id and self.api_key:
            return
        try:
            creds = self.plaza_credential_store.load(agent_name=self.name, plaza_url=self.plaza_url)
            if not creds:
                return
            agent_id = creds.get("agent_id")
            api_key = creds.get("api_key")
            if agent_id and api_key:
                self.agent_id = agent_id
                self.api_key = api_key
                self.agent_card["agent_id"] = agent_id
                self._refresh_pit_address()
                self.logger.info(f"Loaded Plaza credentials from pool for {self.plaza_url}")
        except Exception as e:
            self.logger.warning(f"Failed loading Plaza credentials from pool: {e}")

    def _reuse_plaza_identity(self) -> bool:
        """Internal helper to return the reuse Plaza identity."""
        meta = self.agent_card.get("meta") if isinstance(self.agent_card.get("meta"), dict) else {}
        configured = self._coerce_optional_bool(
            self.agent_card.get("reuse_plaza_identity")
            if self.agent_card.get("reuse_plaza_identity") is not None
            else meta.get("reuse_plaza_identity")
        )
        return True if configured is None else configured

    @staticmethod
    def _coerce_pit_address(value: Any) -> Optional[PitAddress]:
        """Internal helper to coerce the pit address."""
        if value is None:
            return None
        if isinstance(value, PitAddress):
            return value
        if isinstance(value, dict):
            return PitAddress.from_value(value)
        return None

    def _refresh_pit_address(self):
        """Internal helper to return the refresh pit address."""
        if not isinstance(self.address, PitAddress):
            self.address = PitAddress.from_value(self.address)
        self.pit_address = self.address
        if self.agent_id:
            self.pit_address.pit_id = str(self.agent_id)
        if self.plaza_url:
            self.pit_address.register_plaza(self.plaza_url)
        self.agent_card["pit_address"] = self.pit_address.to_dict()
        self.agent_card.pop("agent_address", None)

    def _resolve_advertised_address(self) -> str:
        """Internal helper to resolve the advertised address."""
        configured_address = self._normalize_url(self.agent_card.get("address"))
        if configured_address:
            return configured_address

        env_address = self._normalize_url(os.getenv("PROMPITS_PUBLIC_URL"))
        if env_address:
            return env_address

        return f"http://{self.host}:{self.port}"

    def _resolve_accepts_inbound_from_plaza(self) -> bool:
        """Internal helper to resolve the accepts inbound from Plaza."""
        meta = self.agent_card.get("meta", {})
        if not isinstance(meta, dict):
            meta = {}
            self.agent_card["meta"] = meta
        configured = self._coerce_optional_bool(self.agent_card.get("accepts_inbound_from_plaza"))
        if configured is None:
            configured = self._coerce_optional_bool(meta.get("accepts_inbound_from_plaza"))
        if configured is None:
            configured = self._coerce_optional_bool(os.getenv("PROMPITS_ACCEPTS_INBOUND_FROM_PLAZA"))
        return True if configured is None else configured

    def _sync_connectivity_metadata(self):
        """Internal helper to synchronize the connectivity metadata."""
        meta = self.agent_card.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            self.agent_card["meta"] = meta

        accepts_inbound = self._resolve_accepts_inbound_from_plaza()
        existing_mode = (
            str(self.agent_card.get("connectivity_mode") or meta.get("connectivity_mode") or "").strip()
        )
        if accepts_inbound:
            connectivity_mode = existing_mode or "plaza-forward"
        else:
            connectivity_mode = "outbound-only"

        self.agent_card["accepts_inbound_from_plaza"] = accepts_inbound
        self.agent_card["accepts_direct_call"] = accepts_inbound
        self.agent_card["connectivity_mode"] = connectivity_mode
        meta["accepts_inbound_from_plaza"] = accepts_inbound
        meta["accepts_direct_call"] = accepts_inbound
        meta["connectivity_mode"] = connectivity_mode

    def _save_plaza_credentials_to_pool(self):
        """Internal helper to save the Plaza credentials to pool."""
        if not self.pool or not self.plaza_url:
            return
        if not self._reuse_plaza_identity():
            return
        if not (self.agent_id and self.api_key):
            return
        try:
            self.plaza_credential_store.save(
                self.name,
                self.agent_id,
                self.api_key,
                plaza_url=self.plaza_url,
            )
        except Exception as e:
            self.logger.warning(f"Failed saving Plaza credentials to pool: {e}")

    def _clear_plaza_credentials_in_pool(self):
        """Internal helper for clear Plaza credentials in pool."""
        if not self.pool or not self.plaza_url:
            return
        if not self._reuse_plaza_identity():
            return
        if not self.agent_id:
            return
        try:
            self.plaza_credential_store.clear(self.agent_id, self.name, plaza_url=self.plaza_url)
        except Exception as e:
            self.logger.warning(f"Failed clearing Plaza credentials in pool: {e}")

    def _plaza_request(
        self,
        method: str,
        path: str,
        *,
        plaza_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None,
        retries: Optional[int] = None,
    ) -> requests.Response:
        """Internal helper for Plaza request."""
        base_url = (plaza_url or self.plaza_url or "").rstrip("/")
        if not base_url:
            raise ValueError("plaza_url is required for Plaza requests")
        request_fn = getattr(requests, method.lower())
        url = f"{base_url}/{str(path).lstrip('/')}"
        request_headers = dict(headers or {})
        request_headers.setdefault("Connection", "close")
        timeout_value = timeout if timeout is not None else self.PLAZA_REQUEST_TIMEOUT
        retry_count = self.PLAZA_REQUEST_RETRIES if retries is None else max(int(retries), 0)
        last_response: Optional[requests.Response] = None

        for attempt in range(retry_count + 1):
            try:
                response = request_fn(
                    url,
                    headers=request_headers,
                    params=params,
                    json=json,
                    timeout=timeout_value,
                )
                if self._is_plaza_starting_response(response):
                    return response
                if response.status_code not in self.PLAZA_RETRY_STATUS_CODES or attempt == retry_count:
                    return response
                last_response = response
                self.logger.warning(
                    f"Plaza {method.upper()} {url} returned {response.status_code}; "
                    f"retrying {attempt + 1}/{retry_count}."
                )
            except requests.RequestException as exc:
                if attempt == retry_count:
                    raise
                self.logger.warning(
                    f"Plaza {method.upper()} {url} failed: {exc}. "
                    f"Retrying {attempt + 1}/{retry_count}."
                )

        if last_response is not None:
            return last_response
        raise RuntimeError(f"Plaza {method.upper()} {url} failed without a response")

    async def _plaza_request_async(
        self,
        method: str,
        path: str,
        *,
        plaza_url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = None,
        retries: Optional[int] = None,
    ) -> httpx.Response:
        """Internal helper for Plaza request async."""
        base_url = (plaza_url or self.plaza_url or "").rstrip("/")
        if not base_url:
            raise ValueError("plaza_url is required for Plaza requests")
        url = f"{base_url}/{str(path).lstrip('/')}"
        request_headers = dict(headers or {})
        request_headers.setdefault("Connection", "close")
        timeout_value = timeout if timeout is not None else float(self.PLAZA_REQUEST_TIMEOUT)
        retry_count = self.PLAZA_REQUEST_RETRIES if retries is None else max(int(retries), 0)
        last_response: Optional[httpx.Response] = None

        async with httpx.AsyncClient() as client:
            for attempt in range(retry_count + 1):
                try:
                    response = await client.request(
                        method.upper(),
                        url,
                        headers=request_headers,
                        params=params,
                        json=json,
                        timeout=timeout_value,
                    )
                    if self._is_plaza_starting_response(response):
                        return response
                    if response.status_code not in self.PLAZA_RETRY_STATUS_CODES or attempt == retry_count:
                        return response
                    last_response = response
                    self.logger.warning(
                        f"Plaza {method.upper()} {url} returned {response.status_code}; "
                        f"retrying {attempt + 1}/{retry_count}."
                    )
                except httpx.RequestError as exc:
                    if attempt == retry_count:
                        raise
                    self.logger.warning(
                        f"Plaza {method.upper()} {url} failed: {exc}. "
                        f"Retrying {attempt + 1}/{retry_count}."
                    )

        if last_response is not None:
            return last_response
        raise RuntimeError(f"Plaza {method.upper()} {url} failed without a response")

    def _plaza_get(self, path: str, **kwargs: Any) -> requests.Response:
        """Internal helper for Plaza get."""
        return self._plaza_request("get", path, **kwargs)

    def _plaza_post(self, path: str, **kwargs: Any) -> requests.Response:
        """Internal helper for Plaza post."""
        return self._plaza_request("post", path, **kwargs)

    def _ensure_agent_practices_table(self):
        """Internal helper to ensure the agent practices table exists."""
        if not self.pool:
            return
        if getattr(self, "_agent_practices_table_ensured", False):
            return
        if self.pool._TableExists(self.AGENT_PRACTICES_TABLE):
            self._agent_practices_table_ensured = True
            return
        schema = agent_practices_table_schema()
        self.pool._CreateTable(self.AGENT_PRACTICES_TABLE, schema)
        self._agent_practices_table_ensured = True

    def _practice_row_id(self, practice_id: str) -> str:
        """Internal helper for practice row ID."""
        return f"{self.name}:{practice_id}"

    @staticmethod
    def _parse_practice_updated_at(value: Any) -> datetime:
        """Internal helper to parse the practice updated at."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return datetime.fromtimestamp(0, tz=timezone.utc)
        return datetime.fromtimestamp(0, tz=timezone.utc)

    def _upsert_practice_metadata_in_card(self, metadata: Dict[str, Any]):
        """Internal helper to return the upsert practice metadata in card."""
        practices = self.agent_card.setdefault("practices", [])
        for idx, current in enumerate(practices):
            if current.get("id") == metadata.get("id"):
                practices[idx] = metadata
                return
        practices.append(metadata)

    def _default_practice_metadata(self, practice: Practice) -> Dict[str, Any]:
        """Internal helper to return the default practice metadata."""
        return {
            "name": practice.name,
            "description": practice.description,
            "id": practice.id,
            "cost": practice.cost,
            "tags": practice.tags,
            "examples": practice.examples,
            "inputModes": practice.inputModes,
            "outputModes": practice.outputModes,
            "parameters": practice.parameters,
            "path": practice.path
        }

    def _mailbox_practice_metadata(self) -> Dict[str, Any]:
        """Internal helper for mailbox practice metadata."""
        return {
            "name": "Mailbox",
            "description": "Default inbound message endpoint for generic agent delivery.",
            "id": self.MAILBOX_PRACTICE_ID,
            "cost": 0,
            "tags": ["message", "mailbox"],
            "examples": ["POST /mailbox {'sender':'alice','content':'hello','msg_type':'message'}"],
            "inputModes": ["http-post", "json"],
            "outputModes": ["json"],
            "parameters": {
                "sender": {"type": "string", "description": "Sending agent name or id."},
                "receiver": {"type": "string", "description": "Target agent name or id."},
                "content": {"type": "object", "description": "Message payload."},
                "msg_type": {"type": "string", "description": "Message routing key."},
            },
            "path": "/mailbox",
        }

    def _prune_legacy_practices(self) -> None:
        """Internal helper for prune legacy practices."""
        for practice_id in self.LEGACY_REMOVED_PRACTICE_IDS:
            self.delete_practice(practice_id)

    def _normalize_practice_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the practice metadata."""
        normalized = dict(metadata or {})
        normalized["cost"] = Practice._normalize_cost(normalized.get("cost", 0))
        return normalized

    def _resolve_callable_practice_entries(self, practice: Practice) -> List[Dict[str, Any]]:
        # Practices can expose multiple callable endpoints (e.g., Plaza bundle).
        # If a practice does not define that expansion, we expose its default endpoint.
        """Internal helper to resolve the callable practice entries."""
        if hasattr(practice, "get_callable_endpoints"):
            entries = practice.get_callable_endpoints()
            if isinstance(entries, list):
                resolved = []
                for entry in entries:
                    if isinstance(entry, dict) and entry.get("id") and entry.get("path"):
                        resolved.append(self._normalize_practice_metadata(entry))
                if resolved:
                    return resolved
        return [self._default_practice_metadata(practice)]

    def _build_practice_pool_row(self, practice_metadata: Dict[str, Any], is_deleted: bool = False) -> Optional[Dict[str, Any]]:
        """Internal helper to build the practice pool row."""
        if not practice_metadata:
            return None
        practice_id = practice_metadata.get("id")
        if not practice_id:
            return None
        return {
            "id": self._practice_row_id(practice_id),
            "agent_name": self.name,
            "practice_id": practice_id,
            "practice_name": practice_metadata.get("name", ""),
            "practice_description": practice_metadata.get("description", ""),
            "practice_data": practice_metadata,
            "is_deleted": bool(is_deleted),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _begin_practice_persistence_batch(self):
        """Internal helper for begin practice persistence batch."""
        self._practice_persistence_batch_depth = max(int(self._practice_persistence_batch_depth), 0) + 1

    def _end_practice_persistence_batch(self):
        """Internal helper for end practice persistence batch."""
        current_depth = max(int(self._practice_persistence_batch_depth), 0)
        if current_depth == 0:
            return
        self._practice_persistence_batch_depth = current_depth - 1
        if self._practice_persistence_batch_depth == 0:
            self._flush_pending_practice_rows()

    def _flush_pending_practice_rows(self):
        """Internal helper to return the flush pending practice rows."""
        if not self.pool:
            self._pending_practice_rows = {}
            return
        rows = list((self._pending_practice_rows or {}).values())
        self._pending_practice_rows = {}
        if not rows:
            return
        self._ensure_agent_practices_table()
        if len(rows) == 1:
            self.pool._Insert(self.AGENT_PRACTICES_TABLE, rows[0])
            return
        self.pool._InsertMany(self.AGENT_PRACTICES_TABLE, rows)

    def _persist_practices_to_pool(self, practice_metadata_list: List[Dict[str, Any]], is_deleted: bool = False):
        """Internal helper to persist the practices to pool."""
        if not self.pool or not practice_metadata_list:
            return
        rows = []
        for practice_metadata in practice_metadata_list:
            row = self._build_practice_pool_row(practice_metadata, is_deleted=is_deleted)
            if row is not None:
                rows.append(row)
        if not rows:
            return
        if self._practice_persistence_batch_depth > 0:
            for row in rows:
                row_id = str(row.get("id") or "")
                if row_id:
                    self._pending_practice_rows[row_id] = row
            return
        self._ensure_agent_practices_table()
        if len(rows) == 1:
            self.pool._Insert(self.AGENT_PRACTICES_TABLE, rows[0])
            return
        self.pool._InsertMany(self.AGENT_PRACTICES_TABLE, rows)

    def _persist_practice_to_pool(self, practice_metadata: Dict[str, Any], is_deleted: bool = False):
        """Internal helper to persist the practice to pool."""
        self._persist_practices_to_pool([practice_metadata], is_deleted=is_deleted)

    def _load_practices_info_from_pool(self):
        """Internal helper to load the practices info from pool."""
        if not self.pool:
            return
        try:
            self._ensure_agent_practices_table()
            rows = self.pool._GetTableData(
                self.AGENT_PRACTICES_TABLE,
                {"agent_name": self.name}
            ) or []
        except Exception as e:
            self.logger.warning(f"Failed loading practices info from pool: {e}")
            return

        # Keep newest row per practice_id to honor append-only upsert behavior.
        latest_by_id: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            practice_id = row.get("practice_id")
            if not practice_id:
                continue
            current = latest_by_id.get(practice_id)
            if (not current or
                self._parse_practice_updated_at(row.get("updated_at")) >= self._parse_practice_updated_at(current.get("updated_at"))):
                latest_by_id[practice_id] = row

        for row in latest_by_id.values():
            if row.get("is_deleted"):
                self.agent_card["practices"] = [
                    p for p in self.agent_card.get("practices", [])
                    if p.get("id") != row.get("practice_id")
                ]
                continue
            metadata = row.get("practice_data")
            if isinstance(metadata, dict) and metadata.get("id"):
                self._upsert_practice_metadata_in_card(self._normalize_practice_metadata(metadata))

    def add_practice(self, practice: Practice):
        """Bind and mount a practice to the agent."""
        # Check for duplicates by ID
        if any(p.id == practice.id for p in self.practices):
            self.logger.warning(f"Practice with ID '{practice.id}' already exists. Skipping.")
            return

        practice.bind(self)
        practice.mount(self.app)
        self.practices.append(practice)
        practice_entries = self._resolve_callable_practice_entries(practice)
        for practice_entry in practice_entries:
            self._upsert_practice_metadata_in_card(practice_entry)
        self._persist_practices_to_pool(practice_entries, is_deleted=False)
        
        self.logger.info(f"Mounted practice: {practice.name}")

    def _register_pool_operation_practices(self):
        """Internal helper to register the pool operation practices."""
        if not self.pool or not hasattr(self.pool, "get_operation_practices"):
            return
        try:
            for practice in self.pool.get_operation_practices() or []:
                if isinstance(practice, Practice):
                    self.add_practice(practice)
        except Exception as e:
            self.logger.warning(f"Failed registering pool operation practices: {e}")

    def add_practice_endpoint(self, metadata: Dict[str, Any]) -> bool:
        """Add one callable endpoint entry to the agent card and persist it."""
        if not isinstance(metadata, dict):
            return False
        if not metadata.get("id") or not metadata.get("path"):
            return False
        normalized = self._normalize_practice_metadata(metadata)
        self._upsert_practice_metadata_in_card(normalized)
        self._persist_practice_to_pool(normalized, is_deleted=False)
        return True

    def delete_practice(self, practice_id: str) -> bool:
        """Delete a callable endpoint at runtime and persist the deletion state."""
        if not practice_id:
            return False

        removed_practice: Optional[Practice] = None
        for idx, practice in enumerate(self.practices):
            if practice.id == practice_id:
                removed_practice = self.practices.pop(idx)
                break

        removed_card_entry: Optional[Dict[str, Any]] = None
        remaining_practices = []
        for entry in self.agent_card.get("practices", []):
            if entry.get("id") == practice_id and removed_card_entry is None:
                removed_card_entry = dict(entry)
                continue
            remaining_practices.append(entry)
        self.agent_card["practices"] = remaining_practices

        metadata = removed_card_entry
        if not metadata and removed_practice:
            metadata = self._default_practice_metadata(removed_practice)
        if metadata:
            self._persist_practice_to_pool(metadata, is_deleted=True)

        deleted = removed_practice is not None or removed_card_entry is not None
        if deleted:
            self.logger.info(f"Deleted practice: {practice_id}")
        return deleted

    def delete_practice_endpoint(self, practice_id: str) -> bool:
        """Delete the practice endpoint."""
        return self.delete_practice(practice_id)

    def setup_routes(self):
        """Set up the routes."""
        @self.app.get("/health")
        async def health_check():
            """Route handler for GET /health."""
            return {"status": "ok", "agent": self.name}

        @self.app.get("/api/local-site-settings")
        async def get_local_site_settings():
            """Route handler for GET /api/local-site-settings."""
            return {"status": "success", "settings": self.site_settings}

        @self.app.get("/api/plaza_connection_status")
        async def get_plaza_connection_status():
            """Route handler for GET /api/plaza_connection_status."""
            return await run_in_threadpool(self.get_plaza_connection_status)

        @self.app.post("/mailbox")
        async def mailbox(message: Message):
            """Route handler for POST /mailbox."""
            result = None
            if hasattr(self, "receive"):
                result = await run_in_threadpool(self.receive, message)
                if inspect.isawaitable(result):
                    result = await result
            payload = {"status": "received"}
            if result is not None:
                payload["result"] = result
            return payload

        @self.app.post("/use_practice/{practice_id}")
        async def use_practice(practice_id: str, request: PracticeInvocationRequest):
            """Route handler for POST /use_practice/{practice_id}."""
            self.logger.debug(
                f"Received remote UsePractice request for '{practice_id}' "
                f"from '{request.sender}' to '{request.receiver}'"
            )
            verified = await self._verify_remote_caller(
                caller_agent_address=request.caller_agent_address,
                caller_plaza_token=request.caller_plaza_token,
                caller_direct_token=request.caller_direct_token,
            )
            local_practice = next((p for p in self.practices if p.id == practice_id), None)
            if not local_practice:
                raise HTTPException(status_code=404, detail=f"Practice '{practice_id}' not found")

            try:
                execution_content = self._inject_remote_caller_context_for_practice(
                    practice_id=practice_id,
                    content=request.content,
                    request=request,
                    verified=verified,
                )
                result = await self._execute_local_practice_async(local_practice, execution_content)
            except HTTPException:
                raise
            except Exception as exc:
                self.logger.exception(f"Remote UsePractice '{practice_id}' failed: {exc}")
                raise HTTPException(status_code=500, detail=str(exc)) from exc

            self.logger.debug(
                f"Completed remote UsePractice '{practice_id}' for "
                f"verified caller '{verified.get('agent_id')}'"
            )
            return {"status": "ok", "practice_id": practice_id, "result": result}

        # Lifecycle events to auto-register on startup
        @self.app.on_event("startup")
        def startup_event():
            """Handle startup event for the base agent."""
            if self.plaza_url and self.name != "Plaza":
                threading.Thread(target=self.register).start()

    def _start_heartbeat_thread(self) -> bool:
        """Internal helper to start the heartbeat thread."""
        with self._heartbeat_thread_lock:
            current_thread = self._heartbeat_thread
            if current_thread and current_thread.is_alive():
                return False
            heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                daemon=True,
                name=f"{self.name}-heartbeat",
            )
            self._heartbeat_thread = heartbeat_thread
            heartbeat_thread.start()
            return True

    def _start_reconnect_thread(self, initial_delay: Optional[float] = None) -> bool:
        """Internal helper to start the reconnect thread."""
        with self._reconnect_thread_lock:
            current_thread = self._reconnect_thread
            if current_thread and current_thread.is_alive():
                return False
            reconnect_thread = threading.Thread(
                target=self._reconnect_loop,
                args=(self.PLAZA_RECONNECT_INTERVAL if initial_delay is None else float(initial_delay),),
                daemon=True,
                name=f"{self.name}-plaza-reconnect",
            )
            self._reconnect_thread = reconnect_thread
            reconnect_thread.start()
            return True

    def _has_active_reconnect_thread(self) -> bool:
        """Return whether the value has active reconnect thread."""
        with self._reconnect_thread_lock:
            current_thread = self._reconnect_thread
            return bool(current_thread and current_thread.is_alive())

    @staticmethod
    def _is_plaza_starting_response(response: Any) -> bool:
        """Return whether the value is a Plaza starting response."""
        if response is None or getattr(response, "status_code", None) != 503:
            return False
        try:
            body = response.json()
            if isinstance(body, dict) and str(body.get("detail", "")).strip().lower() == "starting":
                return True
        except Exception:
            pass
        return "starting" in str(getattr(response, "text", "")).lower()

    def _schedule_reconnect(self, reason: str, *, initial_delay: Optional[float] = None):
        """Internal helper to schedule the reconnect."""
        self._plaza_connection_error = str(reason or "").strip() or "Plaza connection lost"
        self.plaza_token = None
        self.token_expires_at = 0.0
        started = self._start_reconnect_thread(initial_delay=initial_delay)
        if started:
            self.logger.warning(
                f"Lost Plaza connection ({reason}). "
                f"Will retry registration every {self.PLAZA_RECONNECT_INTERVAL}s until shutdown."
            )

    def _reconnect_loop(self, initial_delay: float = 0.0):
        """Internal helper for reconnect loop."""
        delay = max(float(initial_delay), 0.0)
        while True:
            if not self.plaza_url:
                return
            if delay > 0:
                time.sleep(delay)
            if self.plaza_token and time.time() < (self.token_expires_at - 60):
                return
            response = self.register(start_reconnect_on_failure=False, request_retries=0)
            if response is not None and response.status_code == 200 and self.plaza_token:
                self.logger.info(f"Reconnected to Plaza at {self.plaza_url}.")
                return
            delay = self.PLAZA_RECONNECT_INTERVAL

    def register(self, *, start_reconnect_on_failure: bool = True, request_retries: Optional[int] = None):
        """Register this agent with the Plaza via HTTP."""
        if not self.plaza_url:
            return
        with self._register_lock:
            if self.plaza_token and time.time() < (self.token_expires_at - 60):
                self._start_heartbeat_thread()
                return

            self._load_plaza_credentials_from_pool()
            self._sync_connectivity_metadata()

            # Ensure our address is known in the card
            self.agent_card["host"] = self.host
            self.agent_card["port"] = self.port
            self.agent_card["address"] = self._resolve_advertised_address()

            try:
                attempt = 0
                while True:
                    has_stored_creds = bool(self.agent_id and self.api_key)
                    if has_stored_creds and self._credential_retry_after > time.time():
                        delay = max(self._credential_retry_after - time.time(), 0.0)
                        if delay > 0:
                            self.logger.warning(
                                f"Plaza rejected stored credentials. Waiting {int(delay)}s before retrying."
                            )
                            time.sleep(delay)

                    payload = self.build_register_payload(
                        plaza_url=self.plaza_url,
                        card=self.agent_card,
                        address=self.agent_card["address"],
                        expires_in=3600,
                        pit_type=self.agent_card.get("pit_type"),
                        pit_id=self.agent_id if has_stored_creds else None,
                        api_key=self.api_key if has_stored_creds else None,
                        accepts_inbound_from_plaza=self.agent_card.get("accepts_inbound_from_plaza"),
                    )
                    response = self._plaza_post("/register", json=payload, retries=request_retries)
                    if response.status_code == 401 and has_stored_creds:
                        self.plaza_token = None
                        self.token_expires_at = 0.0
                        self._credential_retry_after = time.time() + self.PLAZA_REJECTED_CREDENTIAL_RETRY_DELAY
                        self.logger.warning(
                            f"Stored Plaza credentials were rejected. "
                            f"Retrying with the same credential after {self.PLAZA_REJECTED_CREDENTIAL_RETRY_DELAY}s."
                        )
                        if attempt >= 1:
                            return response
                        attempt += 1
                        continue
                    self._credential_retry_after = 0.0
                    break
                if response.status_code == 200:
                    data = response.json()
                    self.plaza_token = data.get("token")
                    self.token_expires_at = time.time() + data.get("expires_in", 3600)
                    self.agent_id = data.get("agent_id", self.agent_id)
                    self.api_key = data.get("api_key", self.api_key)
                    self.agent_card["agent_id"] = self.agent_id
                    self._refresh_pit_address()
                    self._save_plaza_credentials_to_pool()
                    self._mark_plaza_connection_alive()
                    self.logger.info(f"Successfully registered with Plaza at {self.plaza_url}. Token expires in {data.get('expires_in', 3600)}s")
                    self._start_heartbeat_thread()
                elif self._is_plaza_starting_response(response):
                    self.logger.info(f"Plaza at {self.plaza_url} is still starting. Deferring reconnect.")
                    if start_reconnect_on_failure:
                        self._schedule_reconnect("plaza starting")
                else:
                    self.logger.error(f"Registration failed: {response.text}")
                    if start_reconnect_on_failure:
                        self._schedule_reconnect(f"registration failed with status {response.status_code}")
                return response
            except Exception as e:
                self.logger.error(f"Failed to contact Plaza: {e}")
                if start_reconnect_on_failure:
                    self._schedule_reconnect(str(e))
                return None

    def _ensure_token_valid(self) -> Optional[Dict[str, str]]:
        """Ensures the token is valid, renewing it if it is close to expiry (within 60s)."""
        if not self.plaza_token:
            return None
            
        if time.time() > (self.token_expires_at - 60):
            try:
                response = self._plaza_post(
                    "/renew",
                    json={"agent_name": self.name, "expires_in": 3600},
                    headers={"Authorization": f"Bearer {self.plaza_token}"},
                )
                if response.status_code == 200:
                    data = response.json()
                    self.plaza_token = data.get("token")
                    self.token_expires_at = time.time() + data.get("expires_in", 3600)
                    self._plaza_connection_error = ""
                    self.logger.info(f"Token renewed successfully.")
                else:
                    self.logger.warning(f"Token renewal failed: {response.text}. Will attempt re-register with existing agent_id.")
                    self.plaza_token = None
                    self._schedule_reconnect(f"token renewal failed with status {response.status_code}")
            except Exception as e:
                self.logger.error(f"Token renewal request failed: {e}")
                self._schedule_reconnect(str(e))
                
        if self.plaza_token:
            return {"Authorization": f"Bearer {self.plaza_token}"}
        return None

    def send(self, receiver_addr: str, content: Any, msg_type: str = "message"):
        """Send a message to another agent via HTTP."""
        target_url = receiver_addr
        target_card = None
        
        # Autocomplete URL if missing
        if not target_url.startswith("http"):
             # Try to lookup via Plaza
             resolved = self.lookup_agent_info(receiver_addr)
             if resolved:
                 target_url = resolved['card'].get('address')
                 target_card = resolved['card']
             else:
                 self.logger.error(f"Could not resolve address for {receiver_addr}")
                 return False

        if target_card:
            practices_list = target_card.get("practices", [])
            has_mailbox = any(p.get("id") == "mailbox" for p in practices_list)
            target_url = target_card.get("address")
        else:
            self.logger.error(f"No target card found for {receiver_addr}")
            return False
            
        message = Message(sender=self.name, receiver=receiver_addr, content=content, msg_type=msg_type)
        try:
            import json
            payload = json.loads(message.json())
            
            # Check if msg_type matches a specific practice endpoint
            practice_info = next((p for p in practices_list if p.get("id") == msg_type), None)
            
            if practice_info and "path" in practice_info:
                endpoint = practice_info["path"]
                resp = requests.post(f"{target_url}{endpoint}", json=payload, timeout=120)
            elif has_mailbox:
                resp = requests.post(f"{target_url}/mailbox", json=payload, timeout=120)
            else:
                self.logger.error(f"Agent {receiver_addr} has no communication practice or mailbox endpoint.")
                return False
                
            if resp.status_code == 200:
                try:
                    return resp.json()
                except:
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to send message to {target_url}: {e}")
            return False

    def _heartbeat_loop(self):
        """Send heartbeats to Plaza while authenticated."""
        self.logger.info(f"Starting heartbeat loop...")
        while True:
            try:
                time.sleep(self.PLAZA_HEARTBEAT_INTERVAL)
                if not self.plaza_url: break
                
                headers = self._ensure_token_valid()
                if not headers:
                    if not self._has_active_reconnect_thread():
                        self._schedule_reconnect(
                            self._plaza_connection_error or "heartbeat waiting for plaza token",
                            initial_delay=self.PLAZA_RECONNECT_INTERVAL,
                        )
                    continue
                
                payload = {"agent_id": self.agent_id, "agent_name": self.name}
                response = self._plaza_post("/heartbeat", json=payload, headers=headers)
                if response.status_code == 401:
                    self.logger.warning(f"Heartbeat unauthorized (401). Forcing re-register.")
                    self._schedule_reconnect("heartbeat unauthorized (401)")
                elif self._is_plaza_starting_response(response):
                    self._schedule_reconnect("plaza starting")
                elif response.status_code == 200:
                    data = response.json()
                    self._mark_plaza_connection_alive()
                    if isinstance(data.get("site_settings"), dict):
                        self.site_settings = data["site_settings"]
                elif response.status_code != 200:
                    self.logger.warning(f"Heartbeat failed with status {response.status_code}: {response.text}")
                    self._schedule_reconnect(f"heartbeat failed with status {response.status_code}")
            except Exception as e:
                self.logger.warning(f"Heartbeat failed: {e}")
                self._schedule_reconnect(str(e))

    def lookup_agent_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Resolve agent name to full info (including card) via Plaza."""
        if not self.plaza_url: 
            return None
        try:
            headers = self._ensure_token_valid()
            if not headers:
                return None
                
            # Prefer resolving by agent_id first (id-only identity), then fall back to name for compatibility.
            resp = self._plaza_get("/search", params={"agent_id": name}, headers=headers)
            if resp.status_code == 200:
                results = resp.json()
                if results and len(results) > 0:
                    return results[0]

            resp = self._plaza_get("/search", params={"name": name}, headers=headers)
            if resp.status_code == 200:
                results = resp.json()
                if results and len(results) > 0:
                    # Search returns a list of matches, we take the first one
                    return results[0]
            elif resp.status_code == 401:
                logger.warning(f"[{self.name}] Lookup unauthorized (401). Forcing re-register.")
                self.register()
        except Exception as e:
            logger.error(f"[{self.name}] Lookup info failed for {name}: {e}")
        return None

    def lookup_agent(self, name: str) -> Optional[str]:
        """Look up the agent."""
        info = self.lookup_agent_info(name)
        if info:
            return info['card'].get('address')
        return None

    def search(self, role: str = None, practice: str = None, tag: str = None, **kwargs: Any):
        """Search for other agents via the Plaza HTTP API."""
        if not self.plaza_url:
            return []
        try:
            headers = self._ensure_token_valid()
            if not headers:
                return []
                
            params = dict(kwargs)
            if role: params['role'] = role
            if practice: params['practice'] = practice
            if tag: params['tag'] = tag
            
            logger.debug(f"[{self.name}] Searching Plaza with params: {params}")
            resp = self._plaza_get("/search", params=params, headers=headers)
            if resp.status_code == 200:
                results = resp.json()
                logger.debug(f"[{self.name}] Plaza search returned {len(results)} results")
                return results
            elif resp.status_code == 401:
                logger.warning(f"[{self.name}] Search unauthorized (401). Forcing re-register.")
                self.register()
                
            return []
        except Exception as e:
            logger.error(f"[{self.name}] Search failed: {e}")
            return []

    def _execute_local_practice_sync(self, practice: Practice, content: Any) -> Any:
        """Execute local practice in sync context; bridge awaitables when no event loop is running."""
        if isinstance(content, dict):
            result = practice.execute(**content)
        elif content is None:
            result = practice.execute()
        else:
            result = practice.execute(content=content)

        if inspect.isawaitable(result):
            try:
                asyncio.get_running_loop()
                raise RuntimeError("Local practice returned an awaitable; call UsePractice(..., async_mode=True).")
            except RuntimeError as e:
                if "no running event loop" in str(e).lower():
                    return asyncio.run(result)
                raise
        return result

    async def _execute_local_practice_async(self, practice: Practice, content: Any) -> Any:
        """Execute local practice in async context with awaitable passthrough."""
        if inspect.iscoroutinefunction(practice.execute):
            if isinstance(content, dict):
                result = await practice.execute(**content)
            elif content is None:
                result = await practice.execute()
            else:
                result = await practice.execute(content=content)
            return result

        if isinstance(content, dict):
            result = await run_in_threadpool(practice.execute, **content)
        elif content is None:
            result = await run_in_threadpool(practice.execute)
        else:
            result = await run_in_threadpool(practice.execute, content=content)
        if inspect.isawaitable(result):
            return await result
        return result

    @staticmethod
    def _practice_path_from_card(card: Dict[str, Any], practice_id: str) -> str:
        """Resolve endpoint path from agent card metadata with compatibility fallbacks."""
        practices = card.get("practices", []) if isinstance(card, dict) else []
        entry = next((p for p in practices if p.get("id") == practice_id), None)
        if entry and entry.get("path"):
            path = str(entry["path"])
            return path if path.startswith("/") else f"/{path}"
        if practice_id == BaseAgent.MAILBOX_PRACTICE_ID:
            return "/mailbox"
        return f"/{practice_id.replace('-', '_')}"

    def _resolve_remote_target(self, pit_address: Any) -> Optional[Dict[str, Any]]:
        """Resolve PitAddress into current searchable target card + URL."""
        if isinstance(pit_address, str):
            target_url = pit_address.strip()
            if target_url.startswith(("http://", "https://")):
                return {
                    "agent_id": "",
                    "card": {"address": target_url, "practices": []},
                    "url": target_url,
                }

        if isinstance(pit_address, dict):
            target_url = str(
                pit_address.get("address")
                or pit_address.get("url")
                or pit_address.get("target_url")
                or ""
            ).strip()
            if target_url.startswith(("http://", "https://")):
                target_card = pit_address.get("card") if isinstance(pit_address.get("card"), dict) else {}
                resolved_card = dict(target_card or {})
                resolved_card.setdefault("address", target_url)
                if not isinstance(resolved_card.get("practices"), list) and isinstance(pit_address.get("practices"), list):
                    resolved_card["practices"] = pit_address.get("practices")
                target_agent_id = str(
                    pit_address.get("pit_id")
                    or pit_address.get("agent_id")
                    or resolved_card.get("agent_id")
                    or ""
                )
                return {"agent_id": target_agent_id, "card": resolved_card, "url": target_url}

        target_address = self._coerce_pit_address(pit_address)
        if not target_address:
            return None
        target_agent_id = str(target_address.pit_id)
        target_info = self.lookup_agent_info(target_agent_id)
        if not target_info:
            return None
        target_card = target_info.get("card", {})
        target_url = target_card.get("address")
        if not target_url:
            return None
        return {"agent_id": target_agent_id, "card": target_card, "url": target_url}

    @staticmethod
    def _extract_bearer_token(headers: Optional[Dict[str, str]]) -> Optional[str]:
        """Internal helper to extract the bearer token."""
        if not headers:
            return None
        auth_header = headers.get("Authorization") or headers.get("authorization")
        if not auth_header:
            return None
        prefix = "Bearer "
        if auth_header.startswith(prefix):
            return auth_header[len(prefix):]
        return auth_header

    def _build_remote_practice_payload(self, practice_id: str, content: Any, target: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to build the remote practice payload."""
        caller_headers = self._ensure_token_valid() if self.plaza_url else None
        caller_token = self._extract_bearer_token(caller_headers)
        caller_direct_token = self.direct_auth_token
        payload = PracticeInvocationRequest(
            sender=str(self.agent_id or self.name),
            receiver=str(target.get("agent_id") or ""),
            content=content,
            msg_type=practice_id,
            caller_agent_address=self.pit_address.to_dict(),
            caller_plaza_token=caller_token,
            caller_direct_token=caller_direct_token,
        )
        return payload.model_dump()

    @staticmethod
    def _unwrap_remote_practice_response(payload: Any) -> Any:
        """Internal helper for unwrap remote practice response."""
        if isinstance(payload, dict) and payload.get("status") == "ok" and "result" in payload:
            return payload["result"]
        return payload

    def _inject_remote_caller_context_for_practice(
        self,
        *,
        practice_id: str,
        content: Any,
        request: PracticeInvocationRequest,
        verified: Dict[str, Any],
    ) -> Any:
        """Internal helper for inject remote caller context for the practice."""
        if practice_id != "get_pulse_data" or not isinstance(content, dict):
            return content

        caller_pit_address = self._coerce_pit_address(request.caller_agent_address)
        caller_context = {
            "agent_id": str(verified.get("agent_id") or caller_pit_address.pit_id or ""),
            "agent_name": str(verified.get("agent_name") or request.sender or ""),
            "pit_id": str(caller_pit_address.pit_id or ""),
            "pit_address": caller_pit_address.to_dict() if caller_pit_address else {},
            "plaza_url": str(verified.get("plaza_url") or ""),
            "auth_mode": str(verified.get("auth_mode") or ""),
            "sender": str(request.sender or ""),
        }

        enriched = dict(content)
        injected = False
        for key in ("input_data", "params"):
            value = enriched.get(key)
            if not isinstance(value, dict):
                continue
            nested = dict(value)
            nested.setdefault("_caller", caller_context)
            enriched[key] = nested
            injected = True

        if not injected:
            enriched.setdefault("_caller", caller_context)
        return enriched

    async def _verify_remote_caller(
        self,
        caller_agent_address: Any,
        caller_plaza_token: Optional[str],
        caller_direct_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Internal helper for verify remote caller."""
        caller_pit_address = self._coerce_pit_address(caller_agent_address)
        if not caller_pit_address or not caller_pit_address.pit_id:
            logger.warning(f"[{self.name}] Rejecting remote UsePractice request without caller PitAddress.")
            raise HTTPException(status_code=401, detail="Caller agent address is required")
        if caller_plaza_token:
            plazas: List[str] = []
            for plaza in caller_pit_address.plazas:
                normalized = str(plaza).rstrip("/")
                if normalized and normalized not in plazas:
                    plazas.append(normalized)
            if self.plaza_url:
                normalized_self_plaza = self.plaza_url.rstrip("/")
                if normalized_self_plaza not in plazas:
                    plazas.append(normalized_self_plaza)

            for plaza_url in plazas:
                try:
                    response = await self._plaza_request_async(
                        "post",
                        "/authenticate",
                        plaza_url=plaza_url,
                        headers={"Authorization": f"Bearer {caller_plaza_token}"},
                    )
                except Exception as exc:
                    logger.debug(
                        f"[{self.name}] Failed caller verification against Plaza '{plaza_url}' "
                        f"for '{caller_pit_address.pit_id}': {exc}"
                    )
                    continue

                if response.status_code != 200:
                    logger.debug(
                        f"[{self.name}] Plaza '{plaza_url}' rejected caller "
                        f"'{caller_pit_address.pit_id}' with status {response.status_code}"
                    )
                    continue

                auth_payload = response.json() if response.content else {}
                authenticated_agent_id = str(auth_payload.get("agent_id") or "")
                if authenticated_agent_id != str(caller_pit_address.pit_id):
                    logger.warning(
                        f"[{self.name}] Caller verification mismatch: Plaza '{plaza_url}' authenticated "
                        f"'{authenticated_agent_id}' but request claimed '{caller_pit_address.pit_id}'."
                    )
                    continue

                logger.debug(
                    f"[{self.name}] Verified remote caller '{caller_pit_address.pit_id}' through Plaza '{plaza_url}'."
                )
                return {
                    "agent_id": authenticated_agent_id,
                    "agent_name": auth_payload.get("agent_name"),
                    "plaza_url": plaza_url,
                    "auth_mode": "plaza",
                }

        if self.direct_auth_token:
            if caller_direct_token == self.direct_auth_token:
                logger.debug(
                    f"[{self.name}] Verified remote caller '{caller_pit_address.pit_id}' "
                    "through direct shared token."
                )
                return {
                    "agent_id": str(caller_pit_address.pit_id),
                    "agent_name": None,
                    "plaza_url": None,
                    "auth_mode": "direct",
                }
            logger.warning(
                f"[{self.name}] Rejecting remote UsePractice request from '{caller_pit_address.pit_id}' "
                "because direct shared token verification failed."
            )
            raise HTTPException(status_code=401, detail="Caller direct token is invalid")

        if not caller_plaza_token:
            logger.warning(
                f"[{self.name}] Rejecting remote UsePractice request from '{caller_pit_address.pit_id}' "
                "without a Plaza token."
            )
            raise HTTPException(status_code=401, detail="Caller plaza token is required")

        logger.warning(
            f"[{self.name}] Rejecting remote UsePractice request because caller "
            f"'{caller_pit_address.pit_id}' failed Plaza verification."
        )
        raise HTTPException(status_code=401, detail="Caller verification failed")

    def _invoke_remote_practice_sync(self, practice_id: str, content: Any, pit_address: Any, timeout: int = 30) -> Any:
        """Invoke another agent's practice synchronously via HTTP POST."""
        target = self._resolve_remote_target(pit_address)
        if not target:
            raise ValueError(f"Unable to resolve remote target from pit_address: {pit_address}")
        payload = self._build_remote_practice_payload(practice_id=practice_id, content=content, target=target)
        logger.debug(
            f"[{self.name}] Invoking remote practice '{practice_id}' on '{target['agent_id']}' "
            f"via {target['url']}/use_practice/{practice_id}"
        )
        response = requests.post(f"{target['url']}/use_practice/{practice_id}", json=payload, timeout=timeout)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        try:
            return self._unwrap_remote_practice_response(response.json())
        except Exception:
            return response.text

    async def _invoke_remote_practice_async(self, practice_id: str, content: Any, pit_address: Any, timeout: int = 30) -> Any:
        """Invoke another agent's practice asynchronously via `httpx`."""
        import httpx

        target = await run_in_threadpool(self._resolve_remote_target, pit_address)
        if not target:
            raise ValueError(f"Unable to resolve remote target from pit_address: {pit_address}")
        payload = await run_in_threadpool(
            self._build_remote_practice_payload,
            practice_id=practice_id,
            content=content,
            target=target,
        )
        logger.debug(
            f"[{self.name}] Invoking remote async practice '{practice_id}' on '{target['agent_id']}' "
            f"via {target['url']}/use_practice/{practice_id}"
        )
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{target['url']}/use_practice/{practice_id}", json=payload, timeout=timeout)
            response.raise_for_status()
            if not response.content:
                return {}
            return self._unwrap_remote_practice_response(response.json())

    async def UsePracticeAsync(
        self,
        practice_id: str,
        content: Any = None,
        pit_address: Any = None,
        timeout: int = 30
    ) -> Any:
        """Use the practice async."""
        local_practice = next((p for p in self.practices if p.id == practice_id), None)
        target_pit_address = self._coerce_pit_address(pit_address)
        if pit_address is None or (
            target_pit_address and str(target_pit_address.pit_id) == str(self.pit_address.pit_id)
        ):
            if not local_practice:
                raise ValueError(f"Local practice '{practice_id}' not found")
            return await self._execute_local_practice_async(local_practice, content)

        return await self._invoke_remote_practice_async(
            practice_id=practice_id,
            content=content,
            pit_address=pit_address,
            timeout=timeout
        )

    def UsePractice(
        self,
        practice_id: str,
        content: Any = None,
        pit_address: Any = None,
        async_mode: bool = False,
        timeout: int = 30
    ) -> Any:
        """Use the practice."""
        if async_mode:
            return self.UsePracticeAsync(
                practice_id=practice_id,
                content=content,
                pit_address=pit_address,
                timeout=timeout
            )

        local_practice = next((p for p in self.practices if p.id == practice_id), None)
        target_pit_address = self._coerce_pit_address(pit_address)
        if pit_address is None or (
            target_pit_address and str(target_pit_address.pit_id) == str(self.pit_address.pit_id)
        ):
            if not local_practice:
                raise ValueError(f"Local practice '{practice_id}' not found")
            return self._execute_local_practice_sync(local_practice, content)

        return self._invoke_remote_practice_sync(
            practice_id=practice_id,
            content=content,
            pit_address=pit_address,
            timeout=timeout
        )

    @abstractmethod
    def receive(self, message: Message):
        """Handle incoming messages."""
        pass

    @abstractmethod
    def run(self):
        """Legacy run method, now we use uvicorn to run app."""
        pass
