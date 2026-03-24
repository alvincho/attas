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
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from prompits.core.message import Message
from prompits.core.init_schema import agent_practices_table_schema
from prompits.core.pit import Pit, PitAddress
from prompits.core.practice import Practice
from prompits.practices.chat import ChatPractice
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
    PLAZA_REJECTED_CREDENTIAL_RETRY_DELAY = 60
    PLAZA_RECONNECT_INTERVAL = 30

    @staticmethod
    def _coerce_optional_bool(value: Any) -> Optional[bool]:
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
        self._register_lock = threading.Lock()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._heartbeat_thread_lock = threading.Lock()
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_thread_lock = threading.Lock()
        
        # Ensure practices list exists in card
        if "practices" not in self.agent_card:
            self.agent_card["practices"] = []

        self._ensure_agent_practices_table()
        self._load_practices_info_from_pool()
        
        # FastAPI App
        self.app = FastAPI(title=name)
        self.practices: List[Practice] = []
        self.logger = logging.LoggerAdapter(logger, {"agent_name": self.name})
        self._install_request_logging()

        self._register_pool_operation_practices()
        
        # Mount Chat Practice by default
        self.add_practice(ChatPractice())
        self.setup_routes()

    def _install_request_logging(self):
        @self.app.middleware("http")
        async def log_incoming_request(request: Request, call_next):
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

    def _load_plaza_credentials_from_pool(self):
        if not self.pool or not self.plaza_url:
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

    @staticmethod
    def _coerce_pit_address(value: Any) -> Optional[PitAddress]:
        if value is None:
            return None
        if isinstance(value, PitAddress):
            return value
        if isinstance(value, dict):
            return PitAddress.from_value(value)
        return None

    def _refresh_pit_address(self):
        if not isinstance(self.address, PitAddress):
            self.address = PitAddress.from_value(self.address)
        self.pit_address = self.address
        if self.agent_id:
            self.pit_address.pit_id = str(self.agent_id)
        if self.plaza_url:
            self.pit_address.register_plaza(self.plaza_url)
        self.agent_card["pit_address"] = self.pit_address.to_dict()
        self.agent_card.pop("agent_address", None)

    def _resolve_accepts_inbound_from_plaza(self) -> bool:
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
        self.agent_card["connectivity_mode"] = connectivity_mode
        meta["accepts_inbound_from_plaza"] = accepts_inbound
        meta["connectivity_mode"] = connectivity_mode

    def _save_plaza_credentials_to_pool(self):
        if not self.pool or not self.plaza_url:
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
        if not self.pool or not self.plaza_url:
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
        return self._plaza_request("get", path, **kwargs)

    def _plaza_post(self, path: str, **kwargs: Any) -> requests.Response:
        return self._plaza_request("post", path, **kwargs)

    def _authenticate_with_plaza_credentials(self) -> bool:
        if not self.plaza_url or not self.agent_id or not self.api_key:
            return False
        try:
            response = self._plaza_post(
                "/authenticate",
                json={"agent_id": self.agent_id, "api_key": self.api_key},
            )
            if response.status_code != 200:
                self.logger.warning(f"Credential authentication failed: {response.text}")
                return False
            data = response.json()
            token = data.get("token")
            if not token:
                self.logger.warning(f"Credential authentication returned no token.")
                return False
            self.plaza_token = token
            self.token_expires_at = time.time() + data.get("expires_in", 3600)
            return True
        except Exception as e:
            self.logger.error(f"Credential authentication request failed: {e}")
            return False

    def _ensure_agent_practices_table(self):
        if not self.pool:
            return
        if self.pool._TableExists(self.AGENT_PRACTICES_TABLE):
            return
        schema = agent_practices_table_schema()
        self.pool._CreateTable(self.AGENT_PRACTICES_TABLE, schema)

    def _practice_row_id(self, practice_id: str) -> str:
        return f"{self.name}:{practice_id}"

    @staticmethod
    def _parse_practice_updated_at(value: Any) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return datetime.fromtimestamp(0, tz=timezone.utc)
        return datetime.fromtimestamp(0, tz=timezone.utc)

    def _upsert_practice_metadata_in_card(self, metadata: Dict[str, Any]):
        practices = self.agent_card.setdefault("practices", [])
        for idx, current in enumerate(practices):
            if current.get("id") == metadata.get("id"):
                practices[idx] = metadata
                return
        practices.append(metadata)

    def _default_practice_metadata(self, practice: Practice) -> Dict[str, Any]:
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

    def _normalize_practice_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(metadata or {})
        normalized["cost"] = Practice._normalize_cost(normalized.get("cost", 0))
        return normalized

    def _resolve_callable_practice_entries(self, practice: Practice) -> List[Dict[str, Any]]:
        # Practices can expose multiple callable endpoints (e.g., Plaza bundle).
        # If a practice does not define that expansion, we expose its default endpoint.
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

    def _persist_practice_to_pool(self, practice_metadata: Dict[str, Any], is_deleted: bool = False):
        if not self.pool or not practice_metadata:
            return
        practice_id = practice_metadata.get("id")
        if not practice_id:
            return
        self._ensure_agent_practices_table()
        self.pool._Insert(self.AGENT_PRACTICES_TABLE, {
            "id": self._practice_row_id(practice_id),
            "agent_name": self.name,
            "practice_id": practice_id,
            "practice_name": practice_metadata.get("name", ""),
            "practice_description": practice_metadata.get("description", ""),
            "practice_data": practice_metadata,
            "is_deleted": bool(is_deleted),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })

    def _load_practices_info_from_pool(self):
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
        for practice_entry in self._resolve_callable_practice_entries(practice):
            self._upsert_practice_metadata_in_card(practice_entry)
            self._persist_practice_to_pool(practice_entry, is_deleted=False)
        
        self.logger.info(f"Mounted practice: {practice.name}")

    def _register_pool_operation_practices(self):
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
        return self.delete_practice(practice_id)

    def setup_routes(self):
        @self.app.get("/health")
        async def health_check():
            return {"status": "ok", "agent": self.name}

        @self.app.post("/use_practice/{practice_id}")
        async def use_practice(practice_id: str, request: PracticeInvocationRequest):
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
                result = await self._execute_local_practice_async(local_practice, request.content)
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
            if self.plaza_url and self.name != "Plaza":
                threading.Thread(target=self.register).start()

    def _start_heartbeat_thread(self) -> bool:
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

    @staticmethod
    def _is_plaza_starting_response(response: Any) -> bool:
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
        self.plaza_token = None
        self.token_expires_at = 0.0
        started = self._start_reconnect_thread(initial_delay=initial_delay)
        if started:
            self.logger.warning(
                f"Lost Plaza connection ({reason}). "
                f"Will retry registration every {self.PLAZA_RECONNECT_INTERVAL}s until shutdown."
            )

    def _reconnect_loop(self, initial_delay: float = 0.0):
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
            self.agent_card["address"] = f"http://{self.host}:{self.port}"

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
            has_chat = any(p.get("id") == "chat-practice" for p in practices_list)
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
            elif has_chat:
                # If only chat is available, we'll try to use the /chat endpoint
                resp = requests.post(f"{target_url}/chat", json=payload, timeout=120)
            else:
                self.logger.error(f"Agent {receiver_addr} has no communication practices (mailbox or chat).")
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
        """Send a heartbeat to Plaza every 10 seconds."""
        self.logger.info(f"Starting heartbeat loop...")
        while True:
            try:
                time.sleep(10)
                if not self.plaza_url: break
                
                headers = self._ensure_token_valid()
                if not headers:
                    self.logger.warning(f"Skipping heartbeat, no valid token.")
                    continue
                
                payload = {"agent_id": self.agent_id, "agent_name": self.name}
                response = self._plaza_post("/heartbeat", json=payload, headers=headers)
                if response.status_code == 401:
                    self.logger.warning(f"Heartbeat unauthorized (401). Forcing re-register.")
                    self._schedule_reconnect("heartbeat unauthorized (401)")
                elif response.status_code == 503 and "Starting" in response.text:
                    self.logger.info(f"Plaza is starting, will retry heartbeat...")
                elif response.status_code != 200:
                    self.logger.warning(f"Heartbeat failed with status {response.status_code}: {response.text}")
                    self._schedule_reconnect(f"heartbeat failed with status {response.status_code}")
            except Exception as e:
                # If Plaza is completely down, it might throw ConnectionError which is caught here.
                # Just log and continue retrying.
                if "Starting" in str(e) or "503" in str(e):
                    self.logger.info(f"Plaza is starting or unavailable, waiting...")
                else:
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
        if practice_id == "chat-practice":
            return "/chat"
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
        if isinstance(payload, dict) and payload.get("status") == "ok" and "result" in payload:
            return payload["result"]
        return payload

    async def _verify_remote_caller(
        self,
        caller_agent_address: Any,
        caller_plaza_token: Optional[str],
        caller_direct_token: Optional[str] = None,
    ) -> Dict[str, Any]:
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
