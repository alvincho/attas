"""
Plaza integration and web runtime for `prompits.practices.plaza`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the practices package bundles
reusable behaviors that agents can mount or execute remotely.

Core types exposed here include `PlazaAuthenticatePractice`, `PlazaCredentialStore`,
`PlazaEndpointPractice`, `PlazaHeartbeatPractice`, and `PlazaPractice`, which carry the
main behavior or state managed by this module.
"""

import uuid
import httpx
import time
import threading
import secrets
import json
import os
import logging
import concurrent.futures
import re
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.concurrency import run_in_threadpool
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel
from prompits.core.agent_config import AgentConfigStore
from prompits.core.init_schema import (
    builtin_schema_cards,
    plaza_credentials_table_schema,
    plaza_login_history_table_schema,
    plaza_directory_table_schema,
    pulse_pulser_pairs_table_schema,
)
from prompits.core.pulse_runtime import normalize_pulse_pair_entry, normalize_runtime_pulse_entry
from prompits.core.practice import Practice
from prompits.core.pool import Pool
from prompits.core.pit import PitAddress

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)

class RegisterRequest(BaseModel):
    """Request body for `/register` used to create or relogin an agent identity."""
    agent_name: str
    address: str
    expires_in: int = 3600
    pit_type: str = "Agent"
    card: Optional[Dict[str, Any]] = None
    pulse_pulser_pairs: Optional[List[Dict[str, Any]]] = None
    agent_id: Optional[str] = None
    api_key: Optional[str] = None
    owner_key: Optional[str] = None
    accepts_inbound_from_plaza: Optional[bool] = None

class RenewRequest(BaseModel):
    """Request body for `/renew` used to rotate bearer tokens."""
    agent_name: str
    expires_in: int = 3600

class RelayMessage(BaseModel):
    """Request body for `/relay` used to forward messages between agents."""
    receiver: str
    content: Any
    msg_type: str = "message"

class HeartbeatRequest(BaseModel):
    """Request body for `/heartbeat` used to mark an agent as active."""
    agent_id: Optional[str] = None
    agent_name: Optional[str] = None
    content: Optional[Dict[str, Any]] = None


class PlazaCredentialStore:
    """
    Persistence adapter for Plaza credentials and login-history audit records.

    This component isolates persistence mechanics from Plaza endpoint logic and
    safely degrades when optional history writes fail.
    """

    PLAZA_CREDENTIALS_TABLE = "plaza_credentials"
    PLAZA_LOGIN_HISTORY_TABLE = "plaza_login_history"

    def __init__(self, pool: Optional[Pool] = None):
        """Initialize the Plaza credential store."""
        self.pool = pool
        self._login_history_available = True

    def _ensure_plaza_credentials_table(self):
        """Create credential table if needed."""
        if getattr(self, "_credentials_table_ensured", False):
            return
        if not self.pool:
            return
        if self.pool._TableExists(self.PLAZA_CREDENTIALS_TABLE):
            self._credentials_table_ensured = True
            return
        schema = plaza_credentials_table_schema()
        self.pool._CreateTable(self.PLAZA_CREDENTIALS_TABLE, schema)
        self._credentials_table_ensured = True

    @staticmethod
    def _normalize_plaza_url(plaza_url: Optional[str]) -> str:
        """Internal helper to normalize the Plaza URL."""
        return str(plaza_url or "").rstrip("/")

    @classmethod
    def _credential_row_id(
        cls,
        agent_name: Optional[str] = None,
        plaza_url: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> str:
        """Internal helper for credential row ID."""
        normalized_plaza = cls._normalize_plaza_url(plaza_url)
        normalized_name = str(agent_name or "").strip()
        if normalized_name and normalized_plaza:
            return str(uuid.uuid5(uuid.NAMESPACE_URL, f"plaza-credentials:{normalized_name}:{normalized_plaza}"))
        return str(agent_id or normalized_name or "").strip()

    @classmethod
    def _legacy_credential_row_id(
        cls,
        agent_name: Optional[str] = None,
        plaza_url: Optional[str] = None,
        agent_id: Optional[str] = None,
    ) -> str:
        """Internal helper for legacy credential row ID."""
        normalized_plaza = cls._normalize_plaza_url(plaza_url)
        normalized_name = str(agent_name or "").strip()
        if normalized_name and normalized_plaza:
            return f"{normalized_name}:{normalized_plaza}"
        return str(agent_id or normalized_name or "").strip()

    def save(self, agent_name: str, agent_id: str, api_key: str, plaza_url: Optional[str] = None):
        """Save the value."""
        if not self.pool:
            return
        if not agent_name or not agent_id or not api_key:
            return
        self._ensure_plaza_credentials_table()
        normalized_plaza = self._normalize_plaza_url(plaza_url)
        row = {
            "id": self._credential_row_id(agent_name=agent_name, plaza_url=normalized_plaza, agent_id=agent_id),
            "agent_id": agent_id,
            "agent_name": agent_name,
            "api_key": api_key,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        if normalized_plaza:
            row["plaza_url"] = normalized_plaza
        self.pool._Insert(self.PLAZA_CREDENTIALS_TABLE, row)

    @staticmethod
    def _parse_updated_at(value: Any) -> datetime:
        """Internal helper to parse the updated at."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return datetime.fromtimestamp(0, tz=timezone.utc)
        return datetime.fromtimestamp(0, tz=timezone.utc)

    @staticmethod
    def _to_epoch_seconds(value: Any) -> float:
        """Convert the value to epoch seconds."""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, datetime):
            return value.timestamp()
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return 0.0
        return 0.0

    def load(
        self,
        agent_name: Optional[str] = None,
        agent_id: Optional[str] = None,
        plaza_url: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Load most recent credential record by `agent_id` or `agent_name`."""
        if not self.pool:
            return None
        if not agent_name and not agent_id:
            return None
        self._ensure_plaza_credentials_table()
        normalized_plaza = self._normalize_plaza_url(plaza_url)
        rows: List[Dict[str, Any]] = []
        if agent_name and normalized_plaza:
            row_id = self._credential_row_id(agent_name=agent_name, plaza_url=normalized_plaza, agent_id=agent_id)
            rows = self.pool._GetTableData(self.PLAZA_CREDENTIALS_TABLE, {"id": row_id}) or []
            if not rows:
                legacy_row_id = self._legacy_credential_row_id(
                    agent_name=agent_name,
                    plaza_url=normalized_plaza,
                    agent_id=agent_id,
                )
                rows = self.pool._GetTableData(self.PLAZA_CREDENTIALS_TABLE, {"id": legacy_row_id}) or []
            if not rows:
                rows = self.pool._GetTableData(
                    self.PLAZA_CREDENTIALS_TABLE,
                    {"agent_name": agent_name, "plaza_url": normalized_plaza},
                ) or []
        elif agent_id:
            rows = self.pool._GetTableData(self.PLAZA_CREDENTIALS_TABLE, {"agent_id": agent_id}) or []
        else:
            rows = self.pool._GetTableData(self.PLAZA_CREDENTIALS_TABLE, {"agent_name": agent_name}) or []
        if not rows and agent_id:
            rows = self.pool._GetTableData(self.PLAZA_CREDENTIALS_TABLE, {"agent_id": agent_id}) or []
        if not rows and agent_name:
            rows = self.pool._GetTableData(self.PLAZA_CREDENTIALS_TABLE, {"agent_name": agent_name}) or []
        if not rows:
            return None
        row = max(rows, key=lambda r: self._parse_updated_at(r.get("updated_at")))
        if row.get("agent_id") and row.get("api_key"):
            return {"agent_id": row["agent_id"], "api_key": row["api_key"]}
        return None

    def clear(self, agent_id: str, agent_name: str = "", plaza_url: Optional[str] = None):
        """Handle clear for the Plaza credential store."""
        if not self.pool:
            return
        if not agent_id:
            return
        self._ensure_plaza_credentials_table()
        normalized_plaza = self._normalize_plaza_url(plaza_url)
        row = {
            "id": self._credential_row_id(agent_name=agent_name, plaza_url=normalized_plaza, agent_id=agent_id),
            "agent_id": agent_id,
            "agent_name": agent_name,
            "api_key": "",
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        if normalized_plaza:
            row["plaza_url"] = normalized_plaza
        self.pool._Insert(self.PLAZA_CREDENTIALS_TABLE, row)

    def _ensure_login_history_table(self):
        """Internal helper to ensure the login history table exists."""
        if getattr(self, "_login_history_table_ensured", False):
            return
        if not self.pool or not self._login_history_available:
            return
        try:
            if self.pool._TableExists(self.PLAZA_LOGIN_HISTORY_TABLE):
                self._login_history_table_ensured = True
                return
            schema = plaza_login_history_table_schema()
            self.pool._CreateTable(self.PLAZA_LOGIN_HISTORY_TABLE, schema)
            self._login_history_table_ensured = True
        except Exception:
            # Fail open: history persistence is optional and must never block plaza ops.
            self._login_history_available = False

    def append_login_event(self, agent_id: str, agent_name: str, address: str, event: str, ts: float):
        """Append the login event."""
        if not self.pool or not agent_id or not self._login_history_available:
            return
        try:
            self._ensure_login_history_table()
            if not self._login_history_available:
                return
            ts_iso = datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
            self.pool._Insert(self.PLAZA_LOGIN_HISTORY_TABLE, {
                "id": str(uuid.uuid4()),
                "agent_id": agent_id,
                "agent_name": agent_name,
                "address": address,
                "event": event,
                "timestamp": ts_iso
            })
        except Exception:
            self._login_history_available = False

    def load_login_history(self, agent_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Load the login history."""
        if not self.pool or not agent_id or not self._login_history_available:
            return []
        try:
            self._ensure_login_history_table()
            if not self._login_history_available:
                return []
            rows = self.pool._GetTableData(self.PLAZA_LOGIN_HISTORY_TABLE, {"agent_id": agent_id}) or []
            normalized = []
            for row in rows:
                item = dict(row)
                item["timestamp"] = self._to_epoch_seconds(item.get("timestamp"))
                normalized.append(item)
            normalized.sort(key=lambda r: float(r.get("timestamp", 0)))
            return normalized[-limit:]
        except Exception:
            self._login_history_available = False
            return []

class PlazaState:
    """
    Shared mutable state backing all Plaza endpoint practices.

    Centralizes:
    - registration directory and card storage
    - token/auth state
    - credential and login history tracking
    - heartbeat/activity timestamps
    """

    SUPPORTED_PIT_TYPES = {"Agent", "AgentConfig", "Pulser", "Schema", "Pulse", "Phema", "Party"}
    DIRECTORY_TABLE = "plaza_directory"
    PULSE_PULSER_TABLE = "pulse_pulser_pairs"
    LOGIN_HISTORY_LIMIT = 10
    PLAZA_TOKENS_TABLE = "plaza_tokens"
    IMPORTED_INIT_SUFFIX = "_imported.json"
    LEGACY_INIT_PULSE_FILE = "init_pulse.json"
    INIT_PULSE_PREFIX = "init_pulse_"
    PULSE_ALIAS_FAMILIES = {
        "ohlc_bar_series": {
            "ohlc_bar_series",
            "intraday_ohlcv_bar",
            "daily_ohlcv_bar",
            "daily_price_history",
            "ai_demo_finance_price_ohlc_bar_series",
        }
    }

    def __init__(
        self,
        registry: Optional[Dict[str, Any]] = None,
        self_heartbeat_interval: int = 10,
        init_files: Optional[List[str] | str] = None,
        config_dir: Optional[str] = None,
    ):
        """Initialize the Plaza state."""
        self.registry = registry if registry is not None else {}
        self.self_heartbeat_interval = self_heartbeat_interval
        self.init_files = self._normalize_init_files(init_files)
        self.config_dir = str(config_dir or "").strip()
        self.tokens: Dict[str, Dict[str, Any]] = {}
        self.agent_tokens: Dict[str, str] = {}
        self.pit_types: Dict[str, str] = {}
        self.agent_ids: Dict[str, str] = {}
        self.registry_by_name: Dict[str, str] = {}
        self.agent_names_by_id: Dict[str, str] = {}
        self.credentials_by_id: Dict[str, Dict[str, Any]] = {}
        self._self_heartbeat_started = False
        self.credential_store: Optional[PlazaCredentialStore] = None
        self.plaza_url_for_store: str = ""
        self.directory_pool: Optional[Pool] = None
        self.agent_config_store: Optional[AgentConfigStore] = None
        self.agent_cards: Dict[str, Dict[str, Any]] = {}
        self.last_active: Dict[str, float] = {}
        self.login_history_by_id: Dict[str, List[Dict[str, Any]]] = {}
        self._loaded_login_history_ids: set[str] = set()
        self._login_history_load_events: Dict[str, threading.Event] = {}
        self._token_store_available = True
        self._directory_persistence_batch_depth = 0
        self._pending_directory_rows: Dict[str, Dict[str, Any]] = {}
        self.is_starting = True
        self.lock = threading.RLock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="plaza_bg_")
        self._housekeeping_started = False
        self.site_settings: Dict[str, Any] = self._default_site_settings()
        self._load_site_settings()

    def _default_site_settings(self) -> Dict[str, Any]:
        """Internal helper to return the default site settings."""
        return {
            "typography": {
                "title": {"size": "1.75rem", "color": "#0f172a", "weight": "700"},
                "header": {"size": "1.25rem", "color": "#1e293b", "weight": "600"},
                "content": {"size": "1rem", "color": "#334155", "weight": "400"}
            },
            "theme": "paper",
            "accent": "cobalt"
        }

    def _load_site_settings(self):
        """Internal helper to load the site settings."""
        if not self.directory_pool:
            return
        try:
            # We use a simple key-value storage in the pool or a separate file.
            # For simplicity, let's use a 'site_settings' table if possible, 
            # or just a file in the same directory as the database.
            root_path = getattr(self.directory_pool, "root_path", None)
            if root_path:
                settings_path = os.path.join(root_path, "site_settings.json")
                if os.path.exists(settings_path):
                    with open(settings_path, "r") as f:
                        loaded = json.load(f)
                        if isinstance(loaded, dict):
                            self.site_settings.update(loaded)
        except Exception as e:
            logging.getLogger(__name__).warning(f"Failed to load site settings: {e}")

    def save_site_settings(self, settings: Dict[str, Any]):
        """Save the site settings."""
        def deep_update(d, u):
            """Handle deep update for the Plaza state."""
            for k, v in u.items():
                if isinstance(v, dict):
                    d[k] = deep_update(d.get(k, {}), v)
                else:
                    d[k] = v
            return d

        with self.lock:
            deep_update(self.site_settings, settings)
            if not self.directory_pool:
                return
            try:
                root_path = getattr(self.directory_pool, "root_path", None)
                if root_path:
                    settings_path = os.path.join(root_path, "site_settings.json")
                    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
                    with open(settings_path, "w") as f:
                        json.dump(self.site_settings, f, indent=2)
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to save site settings: {e}")

    def _submit_background_task(self, fn, *args, **kwargs):
        """Internal helper to submit the background task."""
        future = self._executor.submit(fn, *args, **kwargs)

        def _log_failure(done_future: concurrent.futures.Future):
            """Internal helper to log the failure."""
            try:
                done_future.result()
            except Exception:
                logging.getLogger(__name__).exception("[Plaza] Background task failed")

        future.add_done_callback(_log_failure)
        return future

    def start_housekeeping_loop(self):
        """Start the housekeeping loop."""
        with self.lock:
            if self._housekeeping_started:
                return
            self._housekeeping_started = True

        def _housekeeping():
            """Internal helper for housekeeping."""
            logger = logging.getLogger(__name__)
            while True:
                try:
                    time.sleep(60)
                    now = time.time()
                    with self.lock:
                        # 1. Purge expired tokens
                        expired_tokens = [t for t, data in self.tokens.items() if data.get("expires_at", 0) < now]
                        for t in expired_tokens:
                            data = self.tokens.pop(t, None)
                            if data and data.get("agent_name"):
                                name = data["agent_name"]
                                if self.agent_tokens.get(name) == t:
                                    self.agent_tokens.pop(name, None)
                        
                        if expired_tokens:
                            logger.info(f"[Plaza Housekeeping] Purged {len(expired_tokens)} expired tokens")

                        # 2. Cleanup login history for old agents (optional/bounded)
                        # We already limit per-agent history to LOGIN_HISTORY_LIMIT, 
                        # but we can also limit the number of agents tracked in memory.
                        if len(self.login_history_by_id) > 1000:
                            # Prune oldest entries if memory gets very tight
                            pass

                except Exception as e:
                    logger.error(f"[Plaza Housekeeping] Error: {e}")

        threading.Thread(target=_housekeeping, daemon=True, name="PlazaHousekeeping").start()

    def ensure_tokens_table(self):
        """Ensure the tokens table exists."""
        if getattr(self, "_tokens_table_ensured", False):
            return True
        if not self.directory_pool or not self._token_store_available:
            return False
        try:
            if self.directory_pool._TableExists(self.PLAZA_TOKENS_TABLE):
                self._tokens_table_ensured = True
                return True
            schema = {
                "token": "TEXT PRIMARY KEY",
                "agent_id": "TEXT",
                "agent_name": "TEXT",
                "expires_at": "REAL",
                "created_at": "TEXT"
            }
            created = self.directory_pool._CreateTable(self.PLAZA_TOKENS_TABLE, schema)
            if created is False:
                self._token_store_available = False
                return False
            if not self.directory_pool._TableExists(self.PLAZA_TOKENS_TABLE):
                self._token_store_available = False
                return False
            self._tokens_table_ensured = True
            return True
        except Exception:
            self._token_store_available = False
            return False

    def persist_token(self, token: str, payload: Dict[str, Any]):
        """Persist the token."""
        if not self.directory_pool or not self._token_store_available:
            return
        try:
            if not self.ensure_tokens_table():
                return
            inserted = self.directory_pool._Insert(self.PLAZA_TOKENS_TABLE, {
                "token": token,
                "agent_id": payload.get("agent_id", ""),
                "agent_name": payload.get("agent_name", ""),
                "expires_at": float(payload.get("expires_at", 0)),
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            if inserted is False:
                self._token_store_available = False
        except Exception:
            self._token_store_available = False
            pass

    def _hydrate_plaza_state(self):
        """Internal helper to return the hydrate Plaza state."""
        try:
            if self.directory_pool:
                # Load tokens
                if self._token_store_available and self.directory_pool._TableExists(self.PLAZA_TOKENS_TABLE):
                    now = time.time()
                    token_rows = self.directory_pool._GetTableData(self.PLAZA_TOKENS_TABLE) or []
                    for row in token_rows:
                        token = row.get("token")
                        expires_at = float(row.get("expires_at", 0))
                        if token and expires_at > now:
                            agent_name = row.get("agent_name", "")
                            self.tokens[token] = {
                                "agent_name": agent_name,
                                "agent_id": row.get("agent_id", ""),
                                "expires_at": expires_at
                            }
                            if agent_name:
                                self.agent_tokens[agent_name] = token
                
                # Load directory statuses
                if self.directory_pool._TableExists(self.DIRECTORY_TABLE):
                    dir_rows = self.directory_pool._GetTableData(self.DIRECTORY_TABLE) or []
                    self._begin_directory_persistence_batch()
                    try:
                        for row in dir_rows:
                            agent_id = row.get("agent_id") or row.get("id")
                            if not agent_id:
                                continue
                            card = row.get("card", {})
                            if isinstance(card, str):
                                try:
                                    card = json.loads(card)
                                except Exception:
                                    card = {}
                            if not isinstance(card, dict):
                                card = {}

                            agent_name = row.get("name") or card.get("name")
                            pit_type = self.canonical_pit_type(row.get("type") or card.get("pit_type"), default="Agent") or "Agent"
                            address = row.get("address") or card.get("address")
                            updated_at = PlazaCredentialStore._to_epoch_seconds(row.get("updated_at"))
                            last_active = updated_at or time.time()
                            normalized_card = self.normalize_card_for_pit(
                                card,
                                pit_type,
                                agent_name=str(agent_name or ""),
                                address=str(address or ""),
                            )

                            self.agent_cards.setdefault(agent_id, normalized_card)
                            self.pit_types[agent_id] = pit_type
                            self.last_active[agent_id] = last_active
                            if agent_name:
                                self.agent_names_by_id[agent_id] = agent_name
                                self.agent_ids[agent_name] = agent_id
                            if address:
                                self.registry[agent_id] = address
                                if agent_name:
                                    self.registry_by_name[agent_name] = address
                            if normalized_card != card:
                                self.upsert_directory_entry(str(agent_id), str(agent_name or ""), str(address or ""), str(pit_type), normalized_card)
                                if pit_type == "Pulser":
                                    self.upsert_pulse_pulser_pairs(
                                        str(agent_id),
                                        str(agent_name or ""),
                                        normalized_card.get("pit_address") or address or "",
                                        normalized_card,
                                    )
                    finally:
                        self._end_directory_persistence_batch()
                self.ensure_pulse_directory_entries_from_pair_rows()
        except Exception:
            pass
        finally:
            self.is_starting = False

    def compact_pit_ref(self, value: Any) -> str:
        """Handle compact pit ref for the Plaza state."""
        pit_address = PitAddress.from_value(value)
        return pit_address.to_ref(reference_plaza=self.plaza_url_for_store)

    @staticmethod
    def _normalize_pulse_alias_token(value: Any) -> str:
        """Internal helper to normalize the pulse alias token."""
        text = str(value or "").strip().lower()
        if not text:
            return ""
        if text.startswith("urn:plaza:pulse:"):
            text = text.split("urn:plaza:pulse:", 1)[1]
        if text.startswith("plaza://pulse/"):
            text = text.split("plaza://pulse/", 1)[1]
        if "@" in text:
            text = text.split("@", 1)[0]
        text = re.sub(r"[^a-z0-9]+", "_", text)
        text = re.sub(r"_+", "_", text).strip("_")
        return text

    @classmethod
    def pulse_alias_family(
        cls,
        *,
        pulse_name: Any = None,
        pulse_id: Any = None,
        pulse_address: Any = None,
        title: Any = None,
    ) -> str:
        """Handle pulse alias family for the Plaza state."""
        tokens = {
            cls._normalize_pulse_alias_token(value)
            for value in (pulse_name, pulse_id, pulse_address, title)
        }
        tokens.discard("")
        for family, aliases in cls.PULSE_ALIAS_FAMILIES.items():
            if tokens & aliases:
                return family
        return ""

    @classmethod
    def pulse_identity_tokens(
        cls,
        *,
        pulse_name: Any = None,
        pulse_id: Any = None,
        pulse_address: Any = None,
        title: Any = None,
    ) -> set[str]:
        """Handle pulse identity tokens for the Plaza state."""
        tokens = {
            cls._normalize_pulse_alias_token(value)
            for value in (pulse_name, pulse_id, pulse_address, title)
        }
        tokens.discard("")
        family = cls.pulse_alias_family(
            pulse_name=pulse_name,
            pulse_id=pulse_id,
            pulse_address=pulse_address,
            title=title,
        )
        if family:
            tokens.add(family)
        return tokens

    def pulse_entries_match(
        self,
        *,
        left_name: Any = None,
        left_id: Any = None,
        left_address: Any = None,
        left_title: Any = None,
        right_name: Any = None,
        right_id: Any = None,
        right_address: Any = None,
        right_title: Any = None,
    ) -> bool:
        """Handle pulse entries match for the Plaza state."""
        left_id_text = str(left_id or "").strip()
        right_id_text = str(right_id or "").strip()
        if left_id_text and right_id_text and left_id_text == right_id_text:
            return True
        if left_address and right_address and self.same_pit_ref(left_address, right_address):
            return True
        left_tokens = self.pulse_identity_tokens(
            pulse_name=left_name,
            pulse_id=left_id,
            pulse_address=left_address,
            title=left_title,
        )
        right_tokens = self.pulse_identity_tokens(
            pulse_name=right_name,
            pulse_id=right_id,
            pulse_address=right_address,
            title=right_title,
        )
        return bool(left_tokens and right_tokens and left_tokens & right_tokens)

    @classmethod
    def canonical_pulse_family_name(
        cls,
        *,
        pulse_name: Any = None,
        pulse_id: Any = None,
        pulse_address: Any = None,
        title: Any = None,
    ) -> str:
        """Return the canonical pulse family name."""
        return cls.pulse_alias_family(
            pulse_name=pulse_name,
            pulse_id=pulse_id,
            pulse_address=pulse_address,
            title=title,
        )

    @staticmethod
    def same_pit_ref(left: Any, right: Any) -> bool:
        """Handle same pit ref for the Plaza state."""
        left_address = PitAddress.from_value(left)
        right_address = PitAddress.from_value(right)
        if left_address.pit_id and right_address.pit_id:
            return left_address.pit_id == right_address.pit_id
        return str(left or "").strip() == str(right or "").strip()

    def _supported_pulse_preference_key(self, entry: Dict[str, Any]) -> tuple:
        """Internal helper to return the supported pulse preference key."""
        pulse_definition = entry.get("pulse_definition") if isinstance(entry.get("pulse_definition"), dict) else {}
        input_schema = entry.get("input_schema") if isinstance(entry.get("input_schema"), dict) else {}
        output_schema = entry.get("output_schema") if isinstance(entry.get("output_schema"), dict) else {}
        test_data = entry.get("test_data") if isinstance(entry.get("test_data"), dict) else {}
        return (
            1 if self.pulse_definition_is_complete(entry) else 0,
            len(output_schema),
            len(input_schema),
            len(test_data),
            len(str(entry.get("description") or "")),
            len(str(pulse_definition.get("title") or "")),
        )

    def _dedupe_supported_pulses(self, supported_pulses: Any) -> List[Dict[str, Any]]:
        """Internal helper for dedupe supported pulses."""
        if not isinstance(supported_pulses, list):
            return []

        deduped: List[Dict[str, Any]] = []
        for entry in supported_pulses:
            if not isinstance(entry, dict):
                continue
            matched_index: Optional[int] = None
            for index, existing in enumerate(deduped):
                if self.pulse_entries_match(
                    left_name=existing.get("pulse_name") or existing.get("name"),
                    left_id=existing.get("pulse_id"),
                    left_address=existing.get("pulse_address"),
                    left_title=(existing.get("pulse_definition") or {}).get("title"),
                    right_name=entry.get("pulse_name") or entry.get("name"),
                    right_id=entry.get("pulse_id"),
                    right_address=entry.get("pulse_address"),
                    right_title=(entry.get("pulse_definition") or {}).get("title"),
                ):
                    matched_index = index
                    break
            if matched_index is None:
                deduped.append(entry)
                continue
            if self._supported_pulse_preference_key(entry) > self._supported_pulse_preference_key(deduped[matched_index]):
                deduped[matched_index] = entry
        return deduped

    @staticmethod
    def _pulser_result_dedupe_key(entry: Dict[str, Any]) -> str:
        """Internal helper to return the pulser result dedupe key."""
        card = entry.get("card") if isinstance(entry.get("card"), dict) else {}
        name = str(entry.get("name") or card.get("name") or "").strip().lower()
        address = str(card.get("address") or entry.get("address") or "").strip().lower()
        agent_id = str(entry.get("agent_id") or card.get("agent_id") or "").strip().lower()
        if name and address:
            return f"{name}|{address}"
        return name or address or agent_id

    def _normalize_pulser_search_result(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the pulser search result."""
        resolved_type = self.normalize_pit_type(entry.get("pit_type") or entry.get("type") or "Agent")
        if resolved_type != "Pulser":
            return entry

        meta = entry.get("meta")
        if not isinstance(meta, dict):
            return entry

        supported_pulses = self._dedupe_supported_pulses(meta.get("supported_pulses"))
        if not supported_pulses:
            return entry

        normalized_entry = dict(entry)
        normalized_meta = dict(meta)
        normalized_meta["supported_pulses"] = supported_pulses
        normalized_meta["pulse_id"] = supported_pulses[0].get("pulse_id")
        normalized_meta["pulse_definition"] = dict(supported_pulses[0].get("pulse_definition") or {})
        if not isinstance(normalized_meta.get("input_schema"), dict):
            normalized_meta["input_schema"] = dict(supported_pulses[0].get("input_schema") or {})
        if not normalized_meta.get("pulse_address"):
            normalized_meta["pulse_address"] = supported_pulses[0].get("pulse_address")
        normalized_entry["meta"] = normalized_meta
        return normalized_entry

    def _pulser_result_preference_key(self, entry: Dict[str, Any]) -> tuple:
        """Internal helper to return the pulser result preference key."""
        normalized = self._normalize_pulser_search_result(entry)
        meta = normalized.get("meta") if isinstance(normalized.get("meta"), dict) else {}
        supported_pulses = meta.get("supported_pulses") if isinstance(meta, dict) else []
        return (
            float(normalized.get("last_active") or 0),
            len(supported_pulses) if isinstance(supported_pulses, list) else 0,
            sum(1 for pulse in supported_pulses if isinstance(pulse, dict) and self.pulse_definition_is_complete(pulse))
            if isinstance(supported_pulses, list)
            else 0,
            len(str(normalized.get("description") or "")),
        )

    def _dedupe_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Internal helper for dedupe search results."""
        deduped: List[Dict[str, Any]] = []
        pulser_indexes: Dict[str, int] = {}

        for entry in results:
            normalized_entry = self._normalize_pulser_search_result(entry)
            resolved_type = self.normalize_pit_type(normalized_entry.get("pit_type") or normalized_entry.get("type") or "Agent")
            if resolved_type != "Pulser":
                deduped.append(normalized_entry)
                continue

            key = self._pulser_result_dedupe_key(normalized_entry)
            if not key:
                deduped.append(normalized_entry)
                continue

            existing_index = pulser_indexes.get(key)
            if existing_index is None:
                pulser_indexes[key] = len(deduped)
                deduped.append(normalized_entry)
                continue

            existing = deduped[existing_index]
            if self._pulser_result_preference_key(normalized_entry) > self._pulser_result_preference_key(existing):
                deduped[existing_index] = normalized_entry

        return deduped

    def normalize_card_for_pit(
        self,
        card: Dict[str, Any],
        pit_type: str,
        *,
        agent_name: str = "",
        address: str = "",
    ) -> Dict[str, Any]:
        """Normalize the card for the pit."""
        normalized_card = dict(card or {})
        meta = normalized_card.get("meta")
        if not isinstance(meta, dict):
            meta = {}

        if pit_type == "Pulser":
            supported_pulses = meta.get("supported_pulses")
            if isinstance(supported_pulses, list) and supported_pulses:
                default_pulse_address = meta.get("pulse_address")
                normalized_supported = [
                    normalize_runtime_pulse_entry(
                        pulse,
                        default_name=str(pulse.get("name") or ""),
                        default_description=str(pulse.get("description") or normalized_card.get("description") or ""),
                        default_pulse_address=str(pulse.get("pulse_address") or default_pulse_address or ""),
                    )
                    for pulse in supported_pulses
                    if isinstance(pulse, dict)
                ]
                normalized_supported = self._dedupe_supported_pulses(normalized_supported)
                if normalized_supported:
                    meta["supported_pulses"] = normalized_supported
                    meta["pulse_id"] = normalized_supported[0].get("pulse_id")
                    meta["pulse_definition"] = dict(normalized_supported[0].get("pulse_definition") or {})
                    if not isinstance(meta.get("input_schema"), dict):
                        meta["input_schema"] = dict(normalized_supported[0].get("input_schema") or {})
                    if not meta.get("pulse_address"):
                        meta["pulse_address"] = normalized_supported[0].get("pulse_address")
        elif pit_type == "Pulse":
            normalized_pulse = normalize_runtime_pulse_entry(
                meta or normalized_card,
                default_name=str(normalized_card.get("name") or agent_name),
                default_description=str(normalized_card.get("description") or ""),
                default_pulse_address=str(meta.get("pulse_address") or normalized_card.get("address") or address or ""),
            )
            meta["pulse_id"] = normalized_pulse.get("pulse_id")
            meta["pulse_definition"] = dict(normalized_pulse.get("pulse_definition") or {})
            meta["pulse_address"] = normalized_pulse.get("pulse_address")
            meta["input_schema"] = dict(normalized_pulse.get("input_schema") or {})
            meta["output_schema"] = dict(normalized_pulse.get("output_schema") or {})
            meta["description"] = normalized_pulse.get("description") or normalized_card.get("description", "")
            if "examples" not in meta and isinstance(normalized_pulse.get("pulse_definition"), dict):
                meta["examples"] = list(normalized_pulse["pulse_definition"].get("examples") or [])
            normalized_card["description"] = normalized_pulse.get("description") or normalized_card.get("description", "")

        normalized_card["meta"] = meta
        return normalized_card

    @staticmethod
    def _normalize_init_files(init_files: Optional[List[str] | str]) -> List[str]:
        """Internal helper to normalize the init files."""
        if init_files is None:
            return []
        if isinstance(init_files, str):
            return [init_files]
        if isinstance(init_files, (list, tuple, set)):
            return [str(item) for item in init_files if item]
        return []

    @staticmethod
    def stable_pulse_id(name: str) -> str:
        """Handle stable pulse ID for the Plaza state."""
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"plaza-pulse:{str(name).strip().lower()}"))

    @classmethod
    def is_imported_init_file(cls, path: str) -> bool:
        """Return whether the value is an imported init file."""
        base_name = os.path.basename(str(path or "")).strip().lower()
        return bool(base_name) and base_name.endswith(cls.IMPORTED_INIT_SUFFIX)

    @classmethod
    def is_tagged_init_pulse_file(cls, path: str) -> bool:
        """Return whether the value is a tagged init pulse file."""
        base_name = os.path.basename(str(path or "")).strip().lower()
        if not base_name or not base_name.endswith(".json"):
            return False
        if cls.is_imported_init_file(base_name):
            return False
        if base_name == cls.LEGACY_INIT_PULSE_FILE:
            return True
        stem, _ = os.path.splitext(base_name)
        return stem.startswith(cls.INIT_PULSE_PREFIX) and len(stem) > len(cls.INIT_PULSE_PREFIX)

    def build_pulse_directory_card(
        self,
        payload: Dict[str, Any],
        *,
        default_name: str = "",
        default_description: str = "",
        owner: str = "Plaza",
    ) -> Tuple[str, str, Dict[str, Any]]:
        """Build the pulse directory card."""
        raw_payload = dict(payload or {})
        raw_card = dict(raw_payload.get("card") or {})
        pulse_name = str(
            raw_payload.get("name")
            or raw_payload.get("pulse_name")
            or raw_card.get("name")
            or default_name
            or ""
        ).strip()
        normalized_pulse = normalize_runtime_pulse_entry(
            raw_payload,
            default_name=pulse_name or default_name,
            default_description=str(
                raw_payload.get("description")
                or raw_card.get("description")
                or default_description
                or ""
            ),
            default_pulse_address=str(raw_payload.get("pulse_address") or raw_card.get("address") or ""),
        )

        pulse_name = str(
            normalized_pulse.get("pulse_name")
            or normalized_pulse.get("name")
            or pulse_name
            or default_name
            or "default_pulse"
        ).strip()
        agent_id = self.stable_pulse_id(pulse_name)
        pulse_definition = dict(normalized_pulse.get("pulse_definition") or {})
        pulse_meta = self._normalize_seed_meta(raw_card.get("meta", raw_payload.get("meta")))
        pulse_meta.update({
            "pulse_id": normalized_pulse.get("pulse_id"),
            "pulse_address": normalized_pulse.get("pulse_address"),
            "pulse_definition": pulse_definition,
            "input_schema": normalized_pulse.get("input_schema"),
            "output_schema": normalized_pulse.get("output_schema"),
            "description": normalized_pulse.get("description"),
            "examples": pulse_definition.get("examples", raw_payload.get("examples", [])),
        })

        card = raw_card
        card["name"] = pulse_name
        card["description"] = normalized_pulse.get("description") or str(
            raw_payload.get("description")
            or card.get("description")
            or default_description
            or ""
        )
        card["pit_type"] = "Pulse"
        card["owner"] = str(card.get("owner") or raw_payload.get("owner") or owner)
        tags = raw_payload.get("tags", card.get("tags", []))
        if isinstance(tags, list):
            card["tags"] = list(tags)
        elif tags:
            card["tags"] = [str(tags)]
        else:
            card["tags"] = []
        card["meta"] = pulse_meta

        pit_address = PitAddress.from_value(card.get("pit_address"))
        pit_address.pit_id = agent_id
        if self.plaza_url_for_store:
            pit_address.register_plaza(self.plaza_url_for_store)
        card["pit_address"] = pit_address.to_dict()
        return agent_id, pulse_name, card

    def upsert_pulse_directory_entry(
        self,
        payload: Dict[str, Any],
        *,
        default_name: str = "",
        default_description: str = "",
        owner: str = "Plaza",
    ) -> str:
        """Handle upsert pulse directory entry for the Plaza state."""
        agent_id, agent_name, card = self.build_pulse_directory_card(
            payload,
            default_name=default_name,
            default_description=default_description,
            owner=owner,
        )
        self._remember_directory_entry(agent_id, agent_name, "Pulse", card)
        row = self._build_directory_row(agent_id, agent_name, card.get("address", ""), "Pulse", card)
        if row is not None:
            self._persist_directory_rows([row])
        return agent_id

    def ensure_pulse_directory_entries_from_pair_rows(
        self,
        pair_rows: Optional[List[Dict[str, Any]]] = None,
    ) -> int:
        """Ensure the pulse directory entries from pair rows exists."""
        rows = pair_rows if isinstance(pair_rows, list) else self.get_pulse_pulser_rows()
        if not rows:
            return 0

        existing_ids, existing_name_types = self._load_existing_directory_snapshot()
        restored = 0
        directory_rows: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            payload = dict(row.get("pulse_definition") or {})
            pulse_name = str(
                payload.get("name")
                or payload.get("pulse_name")
                or row.get("pulse_name")
                or ""
            ).strip()
            if not pulse_name:
                continue
            pulse_directory_id = self.stable_pulse_id(pulse_name)
            if pulse_directory_id in existing_ids or (pulse_name, "Pulse") in existing_name_types:
                continue

            payload.setdefault("name", pulse_name)
            payload.setdefault("pulse_name", pulse_name)
            payload.setdefault("pulse_id", row.get("pulse_id"))
            payload.setdefault("pulse_address", row.get("pulse_address"))
            payload.setdefault("input_schema", row.get("input_schema"))
            payload.setdefault("status", row.get("status"))
            if row.get("completion_status") not in (None, ""):
                payload.setdefault("completion_status", row.get("completion_status"))
            if row.get("completion_errors") not in (None, ""):
                payload.setdefault("completion_errors", row.get("completion_errors"))
            if row.get("is_complete") is not None:
                payload.setdefault("is_complete", row.get("is_complete"))

            agent_id, agent_name, card = self.build_pulse_directory_card(
                payload,
                default_name=pulse_name,
                default_description=str(payload.get("description") or ""),
                owner="Plaza",
            )
            self._remember_directory_entry(agent_id, agent_name, "Pulse", card)
            directory_row = self._build_directory_row(agent_id, agent_name, card.get("address", ""), "Pulse", card)
            if directory_row is not None:
                directory_rows.append(directory_row)
            restored += 1
            existing_ids.add(agent_id)
            existing_name_types.add((agent_name, "Pulse"))
        self._persist_directory_rows(directory_rows)
        return restored

    def verify_token(self, creds: HTTPAuthorizationCredentials = Depends(security)):
        """Validate bearer token existence and expiry, returning token payload."""
        token = creds.credentials
        with self.lock:
            if token not in self.tokens:
                raise HTTPException(status_code=401, detail="Invalid token")
            token_data = dict(self.tokens[token])
        if time.time() > token_data["expires_at"]:
            raise HTTPException(status_code=401, detail="Token expired")
        return token_data

    @classmethod
    def canonical_pit_type(cls, pit_type: Optional[str], *, default: str = "Agent") -> Optional[str]:
        """Handle canonical pit type for the Plaza state."""
        raw_value = str(pit_type or default or "").strip()
        if not raw_value:
            return None
        for candidate in cls.SUPPORTED_PIT_TYPES:
            if candidate.lower() == raw_value.lower():
                return candidate
        normalized = raw_value.title()
        for candidate in cls.SUPPORTED_PIT_TYPES:
            if candidate.lower() == normalized.lower():
                return candidate
        return None

    def normalize_pit_type(self, pit_type: Optional[str]) -> str:
        """Normalize the pit type."""
        normalized = self.canonical_pit_type(pit_type, default="Agent")
        if normalized not in self.SUPPORTED_PIT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported pit_type '{pit_type}'. Supported: {', '.join(sorted(self.SUPPORTED_PIT_TYPES))}"
            )
        return normalized

    def record_login_event(self, agent_id: str, agent_name: str, address: str, event: str):
        """Handle record login event for the Plaza state."""
        ts = time.time()
        event_entry = {
            "timestamp": ts,
            "agent_id": agent_id,
            "agent_name": agent_name,
            "address": address,
            "event": event
        }
        if agent_id:
            with self.lock:
                by_id = list(self.login_history_by_id.get(agent_id, []))
                by_id.append(event_entry)
                self.login_history_by_id[agent_id] = by_id[-self.LOGIN_HISTORY_LIMIT:]
                if event == "issued":
                    self._loaded_login_history_ids.add(agent_id)
        if self.credential_store:
            self._submit_background_task(
                self.credential_store.append_login_event,
                agent_id, agent_name, address, event, ts
            )

    @staticmethod
    def _merge_login_history_rows(*groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Internal helper to merge the login history rows."""
        merged: List[Dict[str, Any]] = []
        seen: set[Tuple[Any, ...]] = set()
        for group in groups:
            for row in group or []:
                item = dict(row)
                key = (
                    str(item.get("id") or ""),
                    str(item.get("agent_id") or ""),
                    str(item.get("agent_name") or ""),
                    str(item.get("address") or ""),
                    str(item.get("event") or ""),
                    float(item.get("timestamp") or 0),
                )
                if key in seen:
                    continue
                seen.add(key)
                merged.append(item)
        merged.sort(key=lambda r: float(r.get("timestamp", 0)))
        return merged

    def hydrate_login_history_for_id(self, agent_id: str, block: bool = True):
        """Handle hydrate login history for the ID for the Plaza state."""
        if not agent_id:
            return
        loader_event: Optional[threading.Event] = None
        while True:
            with self.lock:
                if agent_id in self._loaded_login_history_ids:
                    return
                loader_event = self._login_history_load_events.get(agent_id)
                if loader_event is None:
                    if not block:
                        return
                    loader_event = threading.Event()
                    self._login_history_load_events[agent_id] = loader_event
                    break
            if not block:
                return
            loader_event.wait()

        self._submit_background_task(self._run_hydrate_login_history, agent_id, loader_event)

    def _run_hydrate_login_history(self, agent_id: str, loader_event: threading.Event):
        """Internal helper to run the hydrate login history."""
        rows: List[Dict[str, Any]] = []
        try:
            if self.credential_store:
                rows = self.credential_store.load_login_history(agent_id, limit=self.LOGIN_HISTORY_LIMIT)
        finally:
            with self.lock:
                current_rows = list(self.login_history_by_id.get(agent_id, []))
                self.login_history_by_id[agent_id] = self._merge_login_history_rows(
                    rows,
                    current_rows,
                )[-self.LOGIN_HISTORY_LIMIT:]
                self._loaded_login_history_ids.add(agent_id)
                self._login_history_load_events.pop(agent_id, None)
                loader_event.set()

    def ensure_directory_table(self):
        """Ensure the directory table exists."""
        if getattr(self, "_directory_table_ensured", False):
            return
        if not self.directory_pool:
            return
        if self.directory_pool._TableExists(self.DIRECTORY_TABLE):
            self._directory_table_ensured = True
            return
        schema = plaza_directory_table_schema()
        self.directory_pool._CreateTable(self.DIRECTORY_TABLE, schema)
        self._directory_table_ensured = True

    def ensure_pulse_pulser_table(self):
        """Ensure the pulse pulser table exists."""
        if getattr(self, "_pulse_pulser_table_ensured", False):
            return
        if not self.directory_pool:
            return
        if self.directory_pool._TableExists(self.PULSE_PULSER_TABLE):
            self._pulse_pulser_table_ensured = True
            return
        schema = pulse_pulser_pairs_table_schema()
        self.directory_pool._CreateTable(self.PULSE_PULSER_TABLE, schema)
        self._pulse_pulser_table_ensured = True

    def _remember_directory_entry(self, agent_id: str, agent_name: str, pit_type: str, card: Dict[str, Any]):
        """Internal helper to remember the directory entry."""
        self.agent_cards[agent_id] = card
        self.pit_types[agent_id] = pit_type
        self.agent_ids[agent_name] = agent_id
        self.agent_names_by_id[agent_id] = agent_name
        self.last_active[agent_id] = time.time()

    def _build_directory_row(
        self,
        agent_id: str,
        agent_name: str,
        address: str,
        pit_type: str,
        card: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Internal helper to build the directory row."""
        if not agent_id:
            return None
        entry_card = dict(card or {})
        meta = entry_card.get("meta", {})
        if not isinstance(meta, (dict, list)):
            meta = {"value": meta}
        return {
            "id": agent_id,
            "agent_id": agent_id,
            "name": entry_card.get("name") or agent_name or agent_id,
            "type": pit_type,
            "description": entry_card.get("description", ""),
            "owner": entry_card.get("owner") or agent_name or "",
            "address": address or entry_card.get("address", ""),
            "meta": meta,
            "card": entry_card,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def _persist_directory_rows(self, rows: List[Dict[str, Any]]):
        """Internal helper to persist the directory rows."""
        if not self.directory_pool or not rows:
            return
        if self._directory_persistence_batch_depth > 0:
            for row in rows:
                row_id = str(row.get("id") or row.get("agent_id") or "").strip()
                if row_id:
                    self._pending_directory_rows[row_id] = dict(row)
            return
        try:
            self.ensure_directory_table()
            if len(rows) == 1:
                self.directory_pool._Insert(self.DIRECTORY_TABLE, rows[0])
                return
            self.directory_pool._InsertMany(self.DIRECTORY_TABLE, rows)
        except Exception:
            pass

    def _begin_directory_persistence_batch(self):
        """Internal helper for begin directory persistence batch."""
        self._directory_persistence_batch_depth = max(int(self._directory_persistence_batch_depth), 0) + 1

    def _end_directory_persistence_batch(self):
        """Internal helper for end directory persistence batch."""
        current_depth = max(int(self._directory_persistence_batch_depth), 0)
        if current_depth == 0:
            return
        self._directory_persistence_batch_depth = current_depth - 1
        if self._directory_persistence_batch_depth == 0:
            rows = list((self._pending_directory_rows or {}).values())
            self._pending_directory_rows = {}
            if rows:
                self._persist_directory_rows(rows)

    def upsert_directory_entry(self, agent_id: str, agent_name: str, address: str, pit_type: str, card: Dict[str, Any]):
        """Handle upsert directory entry for the Plaza state."""
        row = self._build_directory_row(agent_id, agent_name, address, pit_type, card)
        if row is not None:
            self._persist_directory_rows([row])

    def upsert_pulse_pulser_pairs(
        self,
        pulser_id: str,
        pulser_name: str,
        pulser_address: Any,
        card: Dict[str, Any],
        pulse_pulser_pairs: Optional[List[Dict[str, Any]]] = None,
    ):
        """Handle upsert pulse pulser pairs for the Plaza state."""
        if not self.directory_pool or not pulser_id:
            return

        card_meta = card.get("meta", {})
        if not isinstance(card_meta, dict):
            card_meta = {}

        default_pulse_address = card_meta.get("pulse_address")
        default_input_schema = card_meta.get("input_schema")
        supported_pulses = card_meta.get("supported_pulses")
        if not isinstance(supported_pulses, list):
            supported_pulses = []
        explicit_pairs = pulse_pulser_pairs if isinstance(pulse_pulser_pairs, list) else card_meta.get("pulse_pulser_pairs")
        if not isinstance(explicit_pairs, list):
            explicit_pairs = []

        entries: List[Dict[str, Any]] = []
        for pulse in supported_pulses:
            if not isinstance(pulse, dict):
                continue
            entries.append(dict(pulse))

        for pair in explicit_pairs:
            if not isinstance(pair, dict):
                continue
            entries.append(dict(pair))

        if not entries:
            return

        self.ensure_pulse_pulser_table()
        rows_by_id: Dict[str, Dict[str, Any]] = {}
        for entry in entries:
            effective_pulser_id = str(entry.get("pulser_id") or pulser_id or "").strip()
            if not effective_pulser_id:
                continue
            effective_pulser_name = str(entry.get("pulser_name") or pulser_name or "").strip()
            effective_pulser_address = entry.get("pulser_address") or pulser_address
            pulse_name = str(entry.get("pulse_name") or entry.get("name") or "").strip()
            pulse_address_value = entry.get("pulse_address") or default_pulse_address or (f"plaza://pulse/{pulse_name}" if pulse_name else "")
            compact_pulse_address = (
                self.compact_pit_ref(pulse_address_value)
                if PitAddress.from_value(pulse_address_value).pit_id
                else str(pulse_address_value)
            )
            normalized_pair = normalize_pulse_pair_entry(
                entry,
                pulser_id=effective_pulser_id,
                pulser_name=effective_pulser_name,
                pulser_address=self.compact_pit_ref(effective_pulser_address),
                default_name=pulse_name or str(card.get("name") or pulser_name),
                default_description=str(entry.get("description") or card.get("description") or ""),
                default_pulse_address=compact_pulse_address,
            )
            if not normalized_pair.get("pulse_name"):
                continue
            input_schema = normalized_pair.get("input_schema")
            if not isinstance(input_schema, dict):
                input_schema = default_input_schema if isinstance(default_input_schema, dict) else {}
                normalized_pair["input_schema"] = input_schema

            pulse_id = str(normalized_pair.get("pulse_id") or "").strip()
            pulse_name = str(normalized_pair.get("pulse_name") or "").strip()
            pulse_address = str(normalized_pair.get("pulse_address") or "").strip()
            pulse_directory_id = str(
                normalized_pair.get("pulse_directory_id")
                or (self.stable_pulse_id(pulse_name) if pulse_name else "")
            ).strip()
            pulser_directory_id = str(
                normalized_pair.get("pulser_directory_id") or effective_pulser_id
            ).strip()
            if pulse_directory_id:
                normalized_pair["pulse_directory_id"] = pulse_directory_id
            if pulser_directory_id:
                normalized_pair["pulser_directory_id"] = pulser_directory_id
            row_id_basis = f"{pulse_name}:{pulse_address}" if pulse_name and pulse_address else (pulse_id or pulse_name or pulse_address)
            row_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{effective_pulser_id}:{row_id_basis}"))
            normalized_pair["id"] = row_id
            normalized_pair["updated_at"] = datetime.now(timezone.utc).isoformat()
            rows_by_id[row_id] = normalized_pair
        rows = list(rows_by_id.values())
        if not rows:
            return
        try:
            self.directory_pool._InsertMany(self.PULSE_PULSER_TABLE, rows)
        except Exception:
            pass
        self.ensure_pulse_directory_entries_from_pair_rows(rows)

    def lookup_pulser_ids(self, pulse_id: Optional[str] = None, pulse_name: Optional[str] = None, pulse_address: Optional[str] = None) -> Optional[set[str]]:
        """Look up the pulser IDs."""
        if not self.directory_pool or (not pulse_id and not pulse_name and not pulse_address):
            return None
        try:
            rows = self.get_pulse_pulser_rows()
        except Exception:
            return None
        with self.lock:
            agent_cards_snapshot = dict(self.agent_cards)

        matched_ids: set[str] = set()
        for row in rows:
            if not self.pulse_entries_match(
                left_name=row.get("pulse_name"),
                left_id=row.get("pulse_id"),
                left_address=row.get("pulse_address"),
                right_name=pulse_name,
                right_id=pulse_id,
                right_address=pulse_address,
            ):
                continue
            pulser_id = row.get("pulser_id")
            if not pulser_id:
                continue
            card = agent_cards_snapshot.get(str(pulser_id), {})
            if not self._is_supported_pulse_complete(card, pulse_id, pulse_name, pulse_address):
                continue
            matched_ids.add(str(pulser_id))
        return matched_ids

    def get_pulse_pulser_rows(self) -> List[Dict[str, Any]]:
        """Return the pulse pulser rows."""
        if not self.directory_pool:
            return []
        try:
            self.ensure_pulse_pulser_table()
            rows = self.directory_pool._GetTableData(self.PULSE_PULSER_TABLE) or []
            return rows if isinstance(rows, list) else []
        except Exception:
            return []

    @staticmethod
    def contains(haystack: Any, needle: Optional[str]) -> bool:
        """Return whether the value contains value."""
        if not needle:
            return True
        return needle.lower() in str(haystack or "").lower()

    @staticmethod
    def pulse_definition_is_complete(entry: Any) -> bool:
        """Handle pulse definition is complete for the Plaza state."""
        if not isinstance(entry, dict):
            return True
        if entry.get("is_complete") is False:
            return False
        status = str(entry.get("completion_status") or entry.get("status") or "").strip().lower()
        if status in {"unfinished", "incomplete", "invalid"}:
            return False
        return True

    def resolve_supported_pulse_entry(
        self,
        supported_pulses: Any,
        *,
        pulse_id: Optional[str] = None,
        pulse_name: Optional[str] = None,
        pulse_address: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Resolve the supported pulse entry."""
        if not isinstance(supported_pulses, list):
            return None
        for entry in supported_pulses:
            if not isinstance(entry, dict):
                continue
            entry_pulse_id = entry.get("pulse_id")
            entry_name = entry.get("pulse_name") or entry.get("name")
            entry_address = entry.get("pulse_address")
            if (pulse_id or pulse_name or pulse_address) and not self.pulse_entries_match(
                left_name=entry_name,
                left_id=entry_pulse_id,
                left_address=entry_address,
                left_title=entry.get("title"),
                right_name=pulse_name,
                right_id=pulse_id,
                right_address=pulse_address,
            ):
                continue
            return entry
        return None

    def _is_supported_pulse_complete(self, card: Dict[str, Any], pulse_id: Optional[str], pulse_name: Optional[str], pulse_address: Optional[str]) -> bool:
        """Return whether the value is a supported pulse complete."""
        matched = self.resolve_supported_pulse_entry(
            card.get("meta", {}).get("supported_pulses") if isinstance(card.get("meta"), dict) else [],
            pulse_id=pulse_id,
            pulse_name=pulse_name,
            pulse_address=pulse_address,
        )
        if not isinstance(matched, dict):
            return True
        return self.pulse_definition_is_complete(matched)

    def search_entries(
        self,
        name: Optional[str] = None,
        agent_id: Optional[str] = None,
        type: Optional[str] = None,
        description: Optional[str] = None,
        owner: Optional[str] = None,
        meta: Optional[str] = None,
        role: Optional[str] = None,
        practice: Optional[str] = None,
        pit_type: Optional[str] = None,
        pulse_id: Optional[str] = None,
        pulse_name: Optional[str] = None,
        pulse_address: Optional[str] = None,
        party: Optional[str] = None,
        use_persisted_fallback: bool = True,
    ) -> List[Dict[str, Any]]:
        """Search the entries."""
        effective_type_filter = pit_type or type
        normalized_filter = self.normalize_pit_type(effective_type_filter) if effective_type_filter else None
        has_filters = any([
            name,
            agent_id,
            type,
            description,
            owner,
            meta,
            role,
            practice,
            pit_type,
            pulse_id,
            pulse_name,
            pulse_address,
            party,
        ])
        pulser_rows = self.get_pulse_pulser_rows() if (pulse_id or pulse_name or pulse_address) else []
        matched_pulser_ids: Optional[set[str]] = None
        if pulse_id or pulse_name or pulse_address:
            matched_pulser_ids = set()
            for row in pulser_rows:
                if not self.pulse_entries_match(
                    left_name=row.get("pulse_name"),
                    left_id=row.get("pulse_id"),
                    left_address=row.get("pulse_address"),
                    right_name=pulse_name,
                    right_id=pulse_id,
                    right_address=pulse_address,
                ):
                    continue
                pulser_id = row.get("pulser_id")
                if pulser_id:
                    matched_pulser_ids.add(str(pulser_id))
        if (pulse_id or pulse_name or pulse_address) and normalized_filter is None:
            normalized_filter = "Pulser"

        results: List[Dict[str, Any]] = []
        with self.lock:
            agent_cards_snapshot = list(self.agent_cards.items())
            agent_names_by_id = dict(self.agent_names_by_id)
            pit_types = dict(self.pit_types)
            last_active = dict(self.last_active)

        for aid, acard in agent_cards_snapshot:
            display_name = acard.get("name") or agent_names_by_id.get(aid) or aid
            resolved_type = self.normalize_pit_type(pit_types.get(aid) or acard.get("pit_type") or "Agent")
            entry_owner = acard.get("owner") or display_name
            entry_desc = acard.get("description", "")
            emeta = acard.get("meta", {})
            if not isinstance(emeta, (dict, list)):
                emeta = {"value": emeta}

            if agent_id and aid != agent_id:
                continue
            if name and not self.contains(display_name, name):
                continue
            if role and acard.get("role") != role:
                continue
            if normalized_filter and resolved_type != normalized_filter:
                continue
            if matched_pulser_ids is not None and aid not in matched_pulser_ids:
                continue
            if pulse_id or pulse_name or pulse_address:
                supported_pulses = emeta.get("supported_pulses") if isinstance(emeta, dict) else []
                matched_pulse = self.resolve_supported_pulse_entry(
                    supported_pulses,
                    pulse_id=pulse_id,
                    pulse_name=pulse_name,
                    pulse_address=pulse_address,
                )
                if matched_pulse is not None and not self.pulse_definition_is_complete(matched_pulse):
                    continue
            if description and not self.contains(entry_desc, description):
                continue
            if owner and not self.contains(entry_owner, owner):
                continue
            if meta and not self.contains(emeta, meta):
                continue
            if practice:
                practices_list = acard.get("practices", [])
                if not any(p.get("id") == practice for p in practices_list):
                    continue
            if party and acard.get("party") != party:
                continue
                self.hydrate_login_history_for_id(aid, block=False)
            with self.lock:
                login_history = list(self.login_history_by_id.get(aid, []))

            results.append({
                "name": display_name,
                "card": acard,
                "pit_type": resolved_type,
                "type": resolved_type,
                "description": entry_desc,
                "owner": entry_owner,
                "meta": emeta,
                "last_active": last_active.get(aid, 0),
                "agent_id": aid,
                "accepts_inbound_from_plaza": bool(acard.get("accepts_inbound_from_plaza", True)),
                "accepts_direct_call": bool(acard.get("accepts_direct_call", acard.get("accepts_inbound_from_plaza", True))),
                "connectivity_mode": str(
                    acard.get("connectivity_mode")
                    or ("plaza-forward" if acard.get("accepts_inbound_from_plaza", True) else "outbound-only")
                ),
                "login_history": login_history
            })

        should_fallback_to_pool = (
            use_persisted_fallback
            and bool(self.directory_pool)
            and (not results or len(agent_cards_snapshot) <= 1 or not has_filters)
        )
        if not should_fallback_to_pool:
            return results if agent_id else self._dedupe_search_results(results)

        directory_rows = []
        try:
            self.ensure_directory_table()
            directory_rows = self.directory_pool._GetTableData(self.DIRECTORY_TABLE) or []
        except Exception:
            directory_rows = []

        for row in directory_rows:
            aid = str(row.get("agent_id") or row.get("id") or "")
            if not aid:
                continue

            raw_card = row.get("card", {})
            if isinstance(raw_card, str):
                try:
                    parsed_card = json.loads(raw_card)
                    acard = parsed_card if isinstance(parsed_card, dict) else {}
                except Exception:
                    acard = {}
            elif isinstance(raw_card, dict):
                acard = raw_card
            else:
                acard = {}

            raw_meta = row.get("meta", {})
            if isinstance(raw_meta, str):
                try:
                    parsed_meta = json.loads(raw_meta)
                    emeta = parsed_meta if isinstance(parsed_meta, (dict, list)) else {"value": parsed_meta}
                except Exception:
                    emeta = {"value": raw_meta}
            elif isinstance(raw_meta, (dict, list)):
                emeta = raw_meta
            else:
                emeta = {"value": raw_meta}

            display_name = acard.get("name") or row.get("name") or agent_names_by_id.get(aid) or aid
            resolved_type = self.normalize_pit_type(row.get("type") or pit_types.get(aid) or acard.get("pit_type") or "Agent")
            entry_owner = row.get("owner") or acard.get("owner") or display_name
            entry_desc = row.get("description") or acard.get("description", "")
            if isinstance(acard, dict):
                acard = self.normalize_card_for_pit(
                    acard,
                    resolved_type,
                    agent_name=display_name,
                    address=str(acard.get("address") or row.get("address") or ""),
                )
                normalized_meta = acard.get("meta")
                if isinstance(normalized_meta, (dict, list)):
                    emeta = normalized_meta

            if agent_id and aid != agent_id:
                continue
            if name and not self.contains(display_name, name):
                continue
            if role and acard.get("role") != role:
                continue
            if normalized_filter and resolved_type != normalized_filter:
                continue
            if matched_pulser_ids is not None and aid not in matched_pulser_ids:
                continue
            if pulse_id or pulse_name or pulse_address:
                supported_pulses = emeta.get("supported_pulses") if isinstance(emeta, dict) else []
                matched_pulse = self.resolve_supported_pulse_entry(
                    supported_pulses,
                    pulse_id=pulse_id,
                    pulse_name=pulse_name,
                    pulse_address=pulse_address,
                )
                if matched_pulse is not None and not self.pulse_definition_is_complete(matched_pulse):
                    continue
            if description and not self.contains(entry_desc, description):
                continue
            if owner and not self.contains(entry_owner, owner):
                continue
            if meta and not self.contains(emeta, meta):
                continue
            if practice:
                practices_list = acard.get("practices", [])
                if not any(p.get("id") == practice for p in practices_list):
                    continue
            if party and acard.get("party") != party:
                continue

            fallback_active = 0
            if aid not in last_active:
                upd = row.get("updated_at")
                if isinstance(upd, (int, float)):
                    fallback_active = float(upd)
                elif isinstance(upd, str):
                    try:
                        fallback_active = datetime.fromisoformat(upd).timestamp()
                    except Exception:
                        pass
            self.hydrate_login_history_for_id(aid, block=False)
            with self.lock:
                login_history = list(self.login_history_by_id.get(aid, []))

            if any(existing.get("agent_id") == aid for existing in results):
                continue
            results.append({
                "name": display_name,
                "card": acard,
                "pit_type": resolved_type,
                "type": resolved_type,
                "description": entry_desc,
                "owner": entry_owner,
                "meta": emeta,
                "last_active": last_active.get(aid, fallback_active),
                "agent_id": aid,
                "login_history": login_history
            })

        return results if agent_id else self._dedupe_search_results(results)

    def hydrate_credentials_from_pool(self):
        """Handle hydrate credentials from pool for the Plaza state."""
        if not self.credential_store or not self.credential_store.pool:
            return
        self.credential_store._ensure_plaza_credentials_table()
        rows = self.credential_store.pool._GetTableData(self.credential_store.PLAZA_CREDENTIALS_TABLE) or []
        for row in rows:
            agent_id = row.get("agent_id")
            api_key = row.get("api_key")
            agent_name = row.get("agent_name")
            if not agent_id or not api_key:
                continue
            with self.lock:
                self.credentials_by_id[agent_id] = {
                    "api_key": api_key,
                    "created_at": row.get("updated_at", time.time())
                }
                if agent_name:
                    self.agent_names_by_id[agent_id] = agent_name

    def persist_credential_to_pool(self, agent_name: str, agent_id: str, api_key: str):
        """Persist the credential to pool."""
        if not self.credential_store:
            return
        self._submit_background_task(
            self.credential_store.save,
            agent_name, agent_id, api_key, self.plaza_url_for_store
        )

    def persist_token_async(self, token: str, payload: Dict[str, Any]):
        """Persist the token async."""
        self._submit_background_task(self.persist_token, token, payload)

    def upsert_directory_entry_async(
        self,
        agent_id: str,
        agent_name: str,
        address: str,
        pit_type: str,
        card: Dict[str, Any],
    ):
        """Handle upsert directory entry async for the Plaza state."""
        self._submit_background_task(
            self.upsert_directory_entry,
            agent_id,
            agent_name,
            address,
            pit_type,
            card,
        )

    def upsert_pulse_pulser_pairs_async(
        self,
        pulser_id: str,
        pulser_name: str,
        pulser_address: Any,
        card: Dict[str, Any],
        pulse_pulser_pairs: Optional[List[Dict[str, Any]]] = None,
    ):
        """Handle upsert pulse pulser pairs async for the Plaza state."""
        self._submit_background_task(
            self.upsert_pulse_pulser_pairs,
            pulser_id,
            pulser_name,
            pulser_address,
            card,
            pulse_pulser_pairs,
        )

    def start_self_heartbeat_loop(self, agent_id: str, agent_name: Optional[str] = None):
        """Start the self heartbeat loop."""
        if self._self_heartbeat_started:
            return
        self._self_heartbeat_started = True

        def _beat():
            """Internal helper for beat."""
            while True:
                with self.lock:
                    self.last_active[agent_id] = time.time()
                    if agent_name:
                        self.last_active[agent_name] = self.last_active[agent_id]
                time.sleep(self.self_heartbeat_interval)

        threading.Thread(target=_beat, daemon=True).start()

    def bootstrap_plaza_agent(self, agent: Any):
        """Handle bootstrap Plaza agent for the Plaza state."""
        if agent is None:
            return
        agent_name = getattr(agent, "name", None)
        agent_card = dict(getattr(agent, "agent_card", {}) or {})
        if not agent_name or not agent_card:
            return
        address = agent_card.get("address")
        agent_id = agent_card.get("agent_id") or f"plaza:{address or agent_name}"
        if address:
            self.registry[agent_id] = address
            self.registry_by_name[agent_name] = address
        pit_type = self.normalize_pit_type(agent_card.get("pit_type", "Agent"))
        agent_card["pit_type"] = pit_type
        agent_card["agent_id"] = agent_id
        agent_card = self.normalize_card_for_pit(
            agent_card,
            pit_type,
            agent_name=str(agent_name or ""),
            address=str(address or ""),
        )
        self.agent_cards[agent_id] = agent_card
        self.pit_types[agent_id] = pit_type
        self.agent_ids[agent_name] = agent_id
        self.agent_names_by_id[agent_id] = agent_name
        self.last_active[agent_id] = time.time()
        self.last_active[agent_name] = self.last_active[agent_id]
        self.start_self_heartbeat_loop(agent_id, agent_name=agent_name)
        self.plaza_url_for_store = address or f"http://{getattr(agent, 'host', '127.0.0.1')}:{getattr(agent, 'port', 8000)}"
        self.credential_store = PlazaCredentialStore(pool=getattr(agent, "pool", None))
        self.directory_pool = getattr(agent, "pool", None)
        self.agent_config_store = AgentConfigStore(pool=self.directory_pool)
        self.hydrate_credentials_from_pool()
        self._begin_directory_persistence_batch()
        try:
            self.upsert_directory_entry(agent_id, agent_name, address, pit_type, agent_card)
            if pit_type == "Pulser":
                self.upsert_pulse_pulser_pairs(agent_id, agent_name, address or "", agent_card)
            self.bootstrap_builtin_schemas()
            self.bootstrap_init_pits()
            self.bootstrap_agent_configs()
        finally:
            self._end_directory_persistence_batch()

        # Start background hydration and housekeeping
        self._submit_background_task(self._hydrate_plaza_state)
        self.start_housekeeping_loop()

    def bootstrap_builtin_schemas(self):
        """Handle bootstrap builtin schemas for the Plaza state."""
        plaza_url = self.plaza_url_for_store or ""
        for entry in builtin_schema_cards(plaza_url):
            schema_id = str(entry.get("schema_id") or "")
            card = dict(entry.get("card") or {})
            schema_name = card.get("name") or entry.get("name") or schema_id
            if not schema_id or schema_id in self.agent_cards:
                continue

            # Register schema pit in in-memory index and optional persisted directory.
            self.agent_cards[schema_id] = card
            self.pit_types[schema_id] = "Schema"
            self.agent_ids[schema_name] = schema_id
            self.agent_names_by_id[schema_id] = schema_name
            self.last_active[schema_id] = time.time()
            self.upsert_directory_entry(schema_id, schema_name, card.get("address", ""), "Schema", card)

    def _iter_init_files(self) -> List[str]:
        """Internal helper for iter init files."""
        files: List[str] = []
        for source in self.init_files:
            if not source:
                continue
            if os.path.isdir(source):
                for name in sorted(os.listdir(source)):
                    if name.startswith("."):
                        continue
                    if self.is_tagged_init_pulse_file(name):
                        files.append(os.path.join(source, name))
            elif os.path.isfile(source):
                if self.is_imported_init_file(source):
                    continue
                files.append(source)
        return files

    def _iter_agent_config_files(self) -> List[str]:
        """Internal helper for iter agent config files."""
        files: List[str] = []
        seen: set[str] = set()
        candidate_directories: List[str] = []

        if self.config_dir and os.path.isdir(self.config_dir):
            candidate_directories.append(self.config_dir)

        for source in self.init_files:
            if not source:
                continue
            if os.path.isdir(source):
                candidate_directories.append(source)
            elif os.path.isfile(source) and str(source).lower().endswith(".agent"):
                absolute = os.path.abspath(source)
                if absolute not in seen:
                    seen.add(absolute)
                    files.append(absolute)

        for directory in candidate_directories:
            try:
                names = sorted(os.listdir(directory))
            except Exception:
                continue
            for name in names:
                if name.startswith(".") or not name.lower().endswith(".agent"):
                    continue
                absolute = os.path.abspath(os.path.join(directory, name))
                if not os.path.isfile(absolute) or absolute in seen:
                    continue
                seen.add(absolute)
                files.append(absolute)

        return files

    def _load_init_entries(self, file_path: str) -> List[Tuple[Dict[str, Any], Optional[str]]]:
        """Internal helper to load the init entries."""
        try:
            with open(file_path, "r") as handle:
                payload = json.load(handle)
        except Exception:
            return []

        file_level_type = None
        if isinstance(payload, dict):
            file_level_type = (
                payload.get("PitType")
                or payload.get("pit_type")
                or payload.get("Type")
                or payload.get("type")
            )
            data = payload.get("data")
            if isinstance(data, list):
                return [(item, file_level_type) for item in data if isinstance(item, dict)]

        if isinstance(payload, dict):
            return [(payload, file_level_type)]
        if isinstance(payload, list):
            return [(item, None) for item in payload if isinstance(item, dict)]
        return []

    @staticmethod
    def _normalize_seed_meta(value: Any) -> Dict[str, Any]:
        """Internal helper to normalize the seed meta."""
        if isinstance(value, dict):
            return dict(value)
        if isinstance(value, list):
            return {"items": value}
        if value in (None, ""):
            return {}
        return {"value": value}

    def _infer_seed_pit_type(self, seed: Dict[str, Any], file_path: str, default_pit_type: Optional[str] = None) -> str:
        """Internal helper for infer seed pit type."""
        explicit = default_pit_type or seed.get("PitType") or seed.get("pit_type") or seed.get("Type") or seed.get("type")
        if explicit:
            normalized = self.canonical_pit_type(explicit)
            if normalized in self.SUPPORTED_PIT_TYPES:
                return normalized
        if seed.get("resource_type") == "pulse_definition":
            return "Pulse"
        if "pulse" in os.path.basename(file_path).lower():
            return "Pulse"
        if "sections" in seed:
            return "Phema"
        if any(key in seed for key in ("output_schema", "input_schema", "rowSchema", "primary_key", "schema_kind")):
            return "Schema"
        return "Agent"

    def _resolve_seed_id(self, seed: Dict[str, Any], file_path: str, pit_type: str, card: Dict[str, Any]) -> str:
        """Internal helper to resolve the seed ID."""
        for value in (
            seed.get("schema_id"),
            seed.get("agent_id"),
            seed.get("id"),
            (seed.get("pit_address") or {}).get("pit_id") if isinstance(seed.get("pit_address"), dict) else None,
            (card.get("pit_address") or {}).get("pit_id") if isinstance(card.get("pit_address"), dict) else None,
            card.get("agent_id"),
        ):
            if value:
                return str(value)

        seed_name = card.get("name") or seed.get("name") or os.path.splitext(os.path.basename(file_path))[0]
        seed_basis = f"{os.path.basename(file_path)}:{pit_type}:{seed_name}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, seed_basis))

    def _load_existing_directory_snapshot(self) -> Tuple[set[str], set[Tuple[str, str]]]:
        """Internal helper to load the existing directory snapshot."""
        existing_ids: set[str] = set()
        existing_name_types: set[Tuple[str, str]] = set()

        for existing_id, existing_card in self.agent_cards.items():
            existing_name = str(self.agent_names_by_id.get(existing_id) or existing_card.get("name") or "").strip()
            existing_type = self.canonical_pit_type(
                self.pit_types.get(existing_id) or existing_card.get("pit_type"),
                default="Agent",
            ) or "Agent"
            if existing_id:
                existing_ids.add(str(existing_id))
            if existing_name and existing_type:
                existing_name_types.add((existing_name, existing_type))

        if not self.directory_pool:
            return existing_ids, existing_name_types

        try:
            self.ensure_directory_table()
            rows = self.directory_pool._GetTableData(self.DIRECTORY_TABLE) or []
        except Exception:
            return existing_ids, existing_name_types

        for row in rows:
            row_id = row.get("agent_id") or row.get("id")
            row_name = str(row.get("name") or "").strip()
            row_type = self.canonical_pit_type(row.get("type"), default="Agent") or "Agent"
            if row_id:
                existing_ids.add(str(row_id))
            if row_name and row_type:
                existing_name_types.add((row_name, row_type))

        return existing_ids, existing_name_types

    def _build_seed_card(self, seed: Dict[str, Any], file_path: str, pit_type: str) -> Dict[str, Any]:
        """Internal helper to build the seed card."""
        card = dict(seed.get("card") or {})

        for key in ("name", "description", "owner", "address", "role"):
            if key in seed and key not in card:
                card[key] = seed.get(key)

        seed_name = card.get("name") or seed.get("name") or os.path.splitext(os.path.basename(file_path))[0]
        card["name"] = seed_name
        card.setdefault("description", seed.get("description", ""))

        tags = card.get("tags", seed.get("tags", []))
        if isinstance(tags, list):
            card["tags"] = list(tags)
        elif tags:
            card["tags"] = [str(tags)]
        else:
            card["tags"] = []

        card["pit_type"] = pit_type
        card["meta"] = self._normalize_seed_meta(card.get("meta", seed.get("meta")))
        return card

    def bootstrap_init_pits(self):
        """Handle bootstrap init pits for the Plaza state."""
        existing_ids, existing_name_types = self._load_existing_directory_snapshot()
        for file_path in self._iter_init_files():
            for seed, default_pit_type in self._load_init_entries(file_path):
                card = self._build_seed_card(seed, file_path, self._infer_seed_pit_type(seed, file_path, default_pit_type))
                pit_type = card.get("pit_type", "Agent")
                agent_id = self._resolve_seed_id(seed, file_path, pit_type, card)
                agent_name = card.get("name") or agent_id

                if pit_type == "Pulse":
                    pulse_payload = dict(seed)
                    pulse_payload["card"] = dict(card)
                    agent_id, agent_name, card = self.build_pulse_directory_card(
                        pulse_payload,
                        default_name=str(agent_name),
                        default_description=str(seed.get("description") or card.get("description") or ""),
                        owner=str(card.get("owner") or seed.get("owner") or "Plaza"),
                    )

                # Pulse seeds represent canonical shared schemas and should refresh
                # existing directory entries on startup when the source seed changes.
                if pit_type != "Pulse" and (agent_id in existing_ids or (agent_name, pit_type) in existing_name_types):
                    continue

                if pit_type != "Pulse":
                    pit_address = PitAddress.from_value(card.get("pit_address"))
                    pit_address.pit_id = agent_id
                    if self.plaza_url_for_store:
                        pit_address.register_plaza(self.plaza_url_for_store)
                    card["pit_address"] = pit_address.to_dict()

                if pit_type == "Schema":
                    card.setdefault("owner", seed.get("owner") or "Plaza")
                    schema_meta = self._normalize_seed_meta(card.get("meta"))
                    schema_meta.setdefault("schema_name", seed.get("schema_name") or agent_name)
                    schema_meta.setdefault("schema_kind", seed.get("schema_kind") or "data")
                    if "schema" not in schema_meta:
                        schema_payload = dict(seed)
                        schema_payload.pop("card", None)
                        schema_meta["schema"] = schema_payload
                    card["meta"] = schema_meta

                self.agent_cards[agent_id] = card
                self.pit_types[agent_id] = pit_type
                self.agent_ids.setdefault(agent_name, agent_id)
                self.agent_names_by_id[agent_id] = agent_name
                self.last_active[agent_id] = time.time()
                self.upsert_directory_entry(agent_id, agent_name, card.get("address", ""), pit_type, card)
                existing_ids.add(agent_id)
                existing_name_types.add((agent_name, pit_type))

    def bootstrap_agent_configs(self):
        """Return the bootstrap agent configs."""
        store = self.agent_config_store
        if store is None or not self.directory_pool:
            return

        for file_path in self._iter_agent_config_files():
            try:
                with open(file_path, "r") as handle:
                    payload = json.load(handle)
            except Exception:
                continue

            if not store.looks_like_config_payload(payload):
                continue

            agent_card = payload.get("agent_card")
            if not isinstance(agent_card, dict):
                agent_card = {}

            resolved_name = str(payload.get("name") or os.path.splitext(os.path.basename(file_path))[0])
            resolved_owner = str(
                payload.get("owner")
                or agent_card.get("owner")
                or "Plaza"
            )
            resolved_description = str(
                payload.get("description")
                or agent_card.get("description")
                or ""
            )

            try:
                saved = store.upsert(
                    payload,
                    name=resolved_name,
                    owner=resolved_owner,
                    description=resolved_description,
                )
            except Exception as exc:
                # Agent-config discovery should never prevent Plaza from starting.
                # Keep a searchable in-memory entry and let persistence recover later.
                sanitized = store.sanitize_config(payload)
                logging.getLogger(__name__).warning(
                    "[Plaza] Failed persisting bootstrapped agent config '%s' from %s; "
                    "keeping in-memory entry only: %s",
                    resolved_name,
                    file_path,
                    exc,
                )
                saved = {
                    "id": store._row_id(name=resolved_name),
                    "name": resolved_name,
                    "description": resolved_description,
                    "owner": resolved_owner,
                    "role": store._derived_role(sanitized),
                    "agent_type": store._as_text(sanitized.get("type")),
                    "tags": store._derived_tags(sanitized),
                }

            agent_id = str(saved.get("id") or "")
            agent_name = str(saved.get("name") or agent_id)
            card = {
                "name": agent_name,
                "description": str(saved.get("description") or ""),
                "owner": str(saved.get("owner") or "Plaza"),
                "role": str(saved.get("role") or ""),
                "tags": list(saved.get("tags") or []),
                "pit_type": "AgentConfig",
                "meta": {
                    "resource_type": "agent_config",
                    "agent_type": str(saved.get("agent_type") or ""),
                    "config_id": agent_id,
                },
            }
            self._remember_directory_entry(agent_id, agent_name, "AgentConfig", card)


class PlazaEndpointPractice(Practice):
    """
    Base class for individual Plaza HTTP endpoints implemented as practices.

    All endpoint practices share the same `PlazaState` instance to guarantee
    consistent state across register/search/auth/heartbeat/relay flows.
    """

    def __init__(
        self,
        state: PlazaState,
        name: str,
        description: str,
        id: str,
        tags: Optional[List[str]] = None,
        examples: Optional[List[str]] = None,
        input_modes: Optional[List[str]] = None,
        output_modes: Optional[List[str]] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the Plaza endpoint practice."""
        super().__init__(
            name=name,
            description=description,
            id=id,
            tags=tags or ["core", "plaza"],
            examples=examples or [],
            inputModes=input_modes or ["http-post", "json"],
            outputModes=output_modes or ["json"],
            parameters=parameters or {},
        )
        self.state = state


class PlazaRegisterPractice(PlazaEndpointPractice):
    """Endpoint practice for agent registration and identity issuance/relogin."""
    def __init__(self, state: PlazaState):
        """Initialize the Plaza register practice."""
        super().__init__(
            state,
            "Plaza Register",
            "Register agents with Plaza.",
            "register",
            examples=[
                "POST /register {'agent_name':'alice','address':'http://127.0.0.1:8012','accepts_inbound_from_plaza':true}"
            ],
            parameters={
                "agent_name": {"type": "string", "description": "Agent display name."},
                "address": {"type": "string", "description": "HTTP base URL for this agent."},
                "expires_in": {"type": "integer", "description": "Token TTL in seconds."},
                "pit_type": {"type": "string", "description": "Agent type: Agent | Pulser | Schema | Pulse | Phema."},
                "card": {"type": "object", "description": "Optional agent card payload."},
                "pulse_pulser_pairs": {"type": "array", "description": "Optional batch of pulse-pulser pair rows to index in the same request."},
                "agent_id": {"type": "string", "description": "Optional existing identity for relogin."},
                "api_key": {"type": "string", "description": "Optional existing secret for relogin."},
                "owner_key": {"type": "string", "description": "Optional Plaza UI owner key used to claim agent ownership for a signed-in user."},
                "accepts_inbound_from_plaza": {"type": "boolean", "description": "Whether Plaza can directly open inbound HTTP connections to this agent."},
            },
        )

    def mount(self, app):
        """Mount the value."""
        router = APIRouter()

        @router.post("/register")
        async def register(req: RegisterRequest):
            """Route handler for POST /register."""
            if self.state.is_starting:
                raise HTTPException(status_code=503, detail="Starting")
            card = dict(req.card or {})
            card_meta = card.get("meta")
            if not isinstance(card_meta, dict):
                card_meta = {}
                card["meta"] = card_meta
            owner_key = str(req.owner_key or "").strip()
            for container in (card, card_meta):
                if not isinstance(container, dict):
                    continue
                for key_name in ("plaza_owner_key", "owner_key", "plaza_owner_key_secret", "owner_key_secret"):
                    if not owner_key:
                        owner_key = str(container.get(key_name) or "").strip()
                    container.pop(key_name, None)
            owner_context = None
            if owner_key:
                owner_resolver = getattr(self.agent, "_resolve_agent_owner_from_key", None)
                if not callable(owner_resolver):
                    raise HTTPException(status_code=501, detail="Owner keys are unavailable for this Plaza")
                owner_context = owner_resolver(owner_key)
            requested_type = req.pit_type or card.get("pit_type") or card.get("type")
            pit_type = self.state.normalize_pit_type(requested_type)
            provided_id = (req.agent_id or "").strip()
            provided_key = (req.api_key or "").strip()
            issued_new_identity = False
            accepts_inbound = req.accepts_inbound_from_plaza
            if accepts_inbound is None:
                accepts_inbound = card.get("accepts_inbound_from_plaza")
            if accepts_inbound is None:
                accepts_inbound = card_meta.get("accepts_inbound_from_plaza")
            accepts_inbound = True if accepts_inbound is None else bool(accepts_inbound)

            with self.state.lock:
                if provided_id or provided_key:
                    if not (provided_id and provided_key):
                        raise HTTPException(status_code=400, detail="Both agent_id and api_key are required together")
                    creds = self.state.credentials_by_id.get(provided_id)
                    if creds and creds.get("api_key") != provided_key:
                        raise HTTPException(status_code=401, detail="Invalid agent_id or api_key")
                    if not creds:
                        self.state.credentials_by_id[provided_id] = {"api_key": provided_key, "created_at": time.time()}
                    agent_id = provided_id
                    api_key = provided_key
                    login_event = "relogin"
                else:
                    agent_id = str(uuid.uuid4())
                    api_key = secrets.token_urlsafe(32)
                    self.state.credentials_by_id[agent_id] = {"api_key": api_key, "created_at": time.time()}
                    issued_new_identity = True
                    login_event = "issued"

                token = str(uuid.uuid4())
                self.state.registry[agent_id] = req.address
                self.state.registry_by_name[req.agent_name] = req.address
                expires_at = time.time() + req.expires_in
                token_payload = {"agent_name": req.agent_name, "agent_id": agent_id, "expires_at": expires_at}
                self.state.tokens[token] = token_payload
                self.state.agent_tokens[req.agent_name] = token

                card.setdefault("name", req.agent_name)
                card.setdefault("address", req.address)
                card["pit_type"] = pit_type
                card["agent_id"] = agent_id
                if owner_context:
                    owner_label = str(owner_context.get("owner_label") or "").strip()
                    if owner_label:
                        card["owner"] = owner_label
                    card_meta["owner_source"] = "ui_agent_key"
                    card_meta["owner_user_id"] = str(owner_context.get("user_id") or "")
                    card_meta["owner_username"] = str(owner_context.get("username") or "")
                    card_meta["owner_display_name"] = str(owner_context.get("display_name") or "")
                    card_meta["owner_email"] = str(owner_context.get("email") or "")
                    card_meta["plaza_owner_key_id"] = str(owner_context.get("key_id") or card_meta.get("plaza_owner_key_id") or "")
                card["accepts_inbound_from_plaza"] = accepts_inbound
                card["accepts_direct_call"] = accepts_inbound
                card["connectivity_mode"] = "plaza-forward" if accepts_inbound else "outbound-only"
                card_meta["accepts_inbound_from_plaza"] = accepts_inbound
                card_meta["accepts_direct_call"] = accepts_inbound
                card_meta["connectivity_mode"] = card["connectivity_mode"]
                if pit_type == "Pulser":
                    supported_pulses = card_meta.get("supported_pulses")
                    if isinstance(supported_pulses, list) and supported_pulses:
                        default_pulse_address = card_meta.get("pulse_address")
                        normalized_supported = [
                            normalize_runtime_pulse_entry(
                                pulse,
                                default_name=str(pulse.get("name") or ""),
                                default_description=str(pulse.get("description") or card.get("description") or ""),
                                default_pulse_address=str(pulse.get("pulse_address") or default_pulse_address or ""),
                            )
                            for pulse in supported_pulses
                            if isinstance(pulse, dict)
                        ]
                        normalized_supported = self.state._dedupe_supported_pulses(normalized_supported)
                        if normalized_supported:
                            card_meta["supported_pulses"] = normalized_supported
                            card_meta["pulse_id"] = normalized_supported[0].get("pulse_id")
                            card_meta["pulse_definition"] = dict(normalized_supported[0].get("pulse_definition") or {})
                            if not isinstance(card_meta.get("input_schema"), dict):
                                card_meta["input_schema"] = dict(normalized_supported[0].get("input_schema") or {})
                            if not card_meta.get("pulse_address"):
                                card_meta["pulse_address"] = normalized_supported[0].get("pulse_address")
                elif pit_type == "Pulse":
                    normalized_pulse = normalize_runtime_pulse_entry(
                        card_meta,
                        default_name=str(card.get("name") or req.agent_name),
                        default_description=str(card.get("description") or ""),
                        default_pulse_address=str(card_meta.get("pulse_address") or card.get("address") or req.address or ""),
                    )
                    card_meta["pulse_id"] = normalized_pulse.get("pulse_id")
                    card_meta["pulse_definition"] = dict(normalized_pulse.get("pulse_definition") or {})
                    card_meta["input_schema"] = dict(normalized_pulse.get("input_schema") or {})
                    card_meta["output_schema"] = dict(normalized_pulse.get("output_schema") or {})
                    card_meta["description"] = normalized_pulse.get("description") or card.get("description", "")
                pit_address = PitAddress.from_value(card.get("pit_address"))
                pit_address.pit_id = agent_id
                if self.state.plaza_url_for_store:
                    pit_address.register_plaza(self.state.plaza_url_for_store)
                card["pit_address"] = pit_address.to_dict()
                self.state.agent_cards[agent_id] = card
                self.state.pit_types[agent_id] = pit_type
                self.state.agent_ids[req.agent_name] = agent_id
                self.state.agent_names_by_id[agent_id] = req.agent_name
                self.state.last_active[agent_id] = time.time()

            self.state.persist_token_async(token, token_payload)
            if not issued_new_identity:
                self.state.hydrate_login_history_for_id(agent_id)
            self.state.persist_credential_to_pool(req.agent_name, agent_id, api_key)
            self.state.record_login_event(agent_id=agent_id, agent_name=req.agent_name, address=req.address, event=login_event)
            self.state.upsert_directory_entry_async(agent_id, req.agent_name, req.address, pit_type, card)
            should_upsert_pairs = pit_type == "Pulser" or bool(req.pulse_pulser_pairs)
            if should_upsert_pairs:
                self.state.upsert_pulse_pulser_pairs_async(
                    agent_id,
                    req.agent_name,
                    card.get("pit_address"),
                    card,
                    pulse_pulser_pairs=req.pulse_pulser_pairs,
                )
            if owner_context:
                touch_owner_key = getattr(self.agent, "_touch_ui_agent_key_usage", None)
                if callable(touch_owner_key):
                    try:
                        touch_owner_key(str(owner_context.get("key_id") or ""))
                    except Exception as exc:
                        logger.warning("[Plaza] Failed updating owner key usage: %s", exc)

            return {
                "status": "registered",
                "token": token,
                "expires_in": req.expires_in,
                "pit_type": pit_type,
                "agent_id": agent_id,
                "api_key": api_key,
                "issued_new_identity": issued_new_identity
            }

        app.include_router(router)


class PlazaRenewPractice(PlazaEndpointPractice):
    """Endpoint practice for bearer token renewal."""
    def __init__(self, state: PlazaState):
        """Initialize the Plaza renew practice."""
        super().__init__(
            state,
            "Plaza Renew",
            "Renew Plaza tokens.",
            "renew",
            examples=["POST /renew {'agent_name':'alice','expires_in':3600}"],
            parameters={
                "agent_name": {"type": "string", "description": "Agent name bound to the token."},
                "expires_in": {"type": "integer", "description": "New token TTL in seconds."},
            },
        )

    def mount(self, app):
        """Mount the value."""
        router = APIRouter()

        @router.post("/renew")
        async def renew(req: RenewRequest, creds: HTTPAuthorizationCredentials = Depends(security)):
            """Route handler for POST /renew."""
            if self.state.is_starting:
                raise HTTPException(status_code=503, detail="Starting")
            token = creds.credentials
            with self.state.lock:
                if token not in self.state.tokens:
                    raise HTTPException(status_code=401, detail="Invalid token")
                token_data = dict(self.state.tokens[token])
                if token_data["agent_name"] != req.agent_name:
                    raise HTTPException(status_code=401, detail="Token does not belong to agent")

                del self.state.tokens[token]
                new_token = str(uuid.uuid4())
                token_payload = {
                    "agent_name": req.agent_name,
                    "agent_id": token_data.get("agent_id"),
                    "expires_at": time.time() + req.expires_in
                }
                self.state.tokens[new_token] = token_payload
                self.state.agent_tokens[req.agent_name] = new_token
            self.state.persist_token_async(new_token, token_payload)
            return {"status": "renewed", "token": new_token, "expires_in": req.expires_in}

        app.include_router(router)


class PlazaAuthenticatePractice(PlazaEndpointPractice):
    """Endpoint practice for bearer-token authentication."""
    def __init__(self, state: PlazaState):
        """Initialize the Plaza authenticate practice."""
        super().__init__(
            state,
            "Plaza Authenticate",
            "Authenticate Plaza bearer tokens.",
            "authenticate",
            examples=["POST /authenticate (Bearer token)"],
            parameters={},
        )

    def mount(self, app):
        """Mount the value."""
        router = APIRouter()

        @router.post("/authenticate")
        async def authenticate(creds: Optional[HTTPAuthorizationCredentials] = Depends(optional_security)):
            """Route handler for POST /authenticate."""
            if self.state.is_starting:
                raise HTTPException(status_code=503, detail="Starting")
            if creds is not None:
                auth = self.state.verify_token(creds)
                return {
                    "status": "authenticated",
                    "agent_name": auth.get("agent_name"),
                    "agent_id": auth.get("agent_id")
                }

            raise HTTPException(status_code=401, detail="Missing authentication credentials")

        app.include_router(router)


class PlazaHeartbeatPractice(PlazaEndpointPractice):
    """Endpoint practice for authenticated heartbeat updates."""
    def __init__(self, state: PlazaState):
        """Initialize the Plaza heartbeat practice."""
        super().__init__(
            state,
            "Plaza Heartbeat",
            "Accept heartbeat updates from agents.",
            "heartbeat",
            examples=["POST /heartbeat {'agent_id':'...'}"],
            parameters={
                "agent_id": {"type": "string", "description": "Agent id sending heartbeat."},
                "agent_name": {"type": "string", "description": "Fallback name to resolve agent id."},
                "content": {"type": "object", "description": "Optional payload that may include agent_id."},
            },
        )

    def mount(self, app):
        """Mount the value."""
        router = APIRouter()

        @router.post("/heartbeat")
        async def heartbeat(req: HeartbeatRequest, auth: Dict[str, Any] = Depends(self.state.verify_token)):
            """Route handler for POST /heartbeat."""
            if self.state.is_starting:
                raise HTTPException(status_code=503, detail="Starting")
            auth_agent_id = auth.get("agent_id")
            requested_agent_id = req.agent_id
            if not requested_agent_id and req.content:
                requested_agent_id = req.content.get("agent_id")
            if not requested_agent_id and req.agent_name:
                with self.state.lock:
                    requested_agent_id = self.state.agent_ids.get(req.agent_name)
            if not requested_agent_id:
                raise HTTPException(status_code=400, detail="Missing agent_id in heartbeat")
            if auth_agent_id != requested_agent_id:
                raise HTTPException(status_code=401, detail="Unauthorized heartbeat mismatch")
            with self.state.lock:
                self.state.last_active[requested_agent_id] = time.time()
            return {
                "status": "ok",
                "site_settings": self.state.site_settings
            }

        app.include_router(router)


class PlazaSearchPractice(PlazaEndpointPractice):
    """Endpoint practice for directory lookup across persisted and in-memory state."""
    def __init__(self, state: PlazaState):
        """Initialize the Plaza search practice."""
        super().__init__(
            state,
            "Plaza Search",
            "Search plaza directory and in-memory registry.",
            "search",
            examples=["GET /search?name=alice&practice=mailbox"],
            input_modes=["http-get", "query"],
            parameters={
                "name": {"type": "string", "description": "Filter by name substring."},
                "agent_id": {"type": "string", "description": "Filter by exact agent id."},
                "type": {"type": "string", "description": "Alias for pit_type filter."},
                "description": {"type": "string", "description": "Filter by description substring."},
                "owner": {"type": "string", "description": "Filter by owner substring."},
                "meta": {"type": "string", "description": "Filter by metadata substring."},
                "role": {"type": "string", "description": "Filter by agent card role."},
                "practice": {"type": "string", "description": "Filter by practice id in agent card."},
                "pit_type": {"type": "string", "description": "Agent type filter."},
                "pulse_id": {"type": "string", "description": "Filter pulsers by supported PDS pulse id."},
                "pulse_name": {"type": "string", "description": "Filter pulsers by supported pulse name."},
                "pulse_address": {"type": "string", "description": "Filter pulsers by supported pulse address."},
                "party": {"type": "string", "description": "Filter by party name."},
            },
        )

    def mount(self, app):
        """Mount the value."""
        router = APIRouter()

        @router.get("/search")
        async def search(
            name: Optional[str] = None,
            agent_id: Optional[str] = None,
            type: Optional[str] = None,
            description: Optional[str] = None,
            owner: Optional[str] = None,
            meta: Optional[str] = None,
            role: Optional[str] = None,
            practice: Optional[str] = None,
            pit_type: Optional[str] = None,
            pulse_id: Optional[str] = None,
            pulse_name: Optional[str] = None,
            pulse_address: Optional[str] = None,
            party: Optional[str] = None,
            auth: Dict[str, Any] = Depends(self.state.verify_token)
        ):
            """Route handler for GET /search."""
            if self.state.is_starting:
                raise HTTPException(status_code=503, detail="Starting")
            return await run_in_threadpool(
                self.state.search_entries,
                name=name,
                agent_id=agent_id,
                type=type,
                description=description,
                owner=owner,
                meta=meta,
                role=role,
                practice=practice,
                pit_type=pit_type,
                pulse_id=pulse_id,
                pulse_name=pulse_name,
                pulse_address=pulse_address,
                party=party,
                use_persisted_fallback=False,
            )

        app.include_router(router)


class PlazaRelayPractice(PlazaEndpointPractice):
    """Endpoint practice that proxies messages from one authenticated agent to another."""
    def __init__(self, state: PlazaState):
        """Initialize the Plaza relay practice."""
        super().__init__(
            state,
            "Plaza Relay",
            "Relay messages between agents.",
            "relay",
            examples=[
                "POST /relay {'receiver':'bob','content':'hi','msg_type':'message'}"
            ],
            parameters={
                "receiver": {"type": "string", "description": "Target agent id or name."},
                "content": {"type": "object", "description": "Relay payload for destination practice."},
                "msg_type": {"type": "string", "description": "Message type used for routing."},
            },
        )

    def mount(self, app):
        """Mount the value."""
        router = APIRouter()
        self._client = httpx.AsyncClient(timeout=10.0)

        @app.on_event("shutdown")
        async def shutdown_event():
            """Handle shutdown event for the Plaza relay practice."""
            await self._client.aclose()

        @router.post("/relay")
        async def relay_message(msg: RelayMessage, auth: Dict[str, Any] = Depends(self.state.verify_token)):
            """Route handler for POST /relay."""
            if self.state.is_starting:
                raise HTTPException(status_code=503, detail="Starting")
            receiver_id = msg.receiver
            if receiver_id not in self.state.registry:
                receiver_id = self.state.agent_ids.get(msg.receiver, msg.receiver)
            if receiver_id not in self.state.registry:
                raise HTTPException(status_code=404, detail="Receiver not found")

            receiver_address = self.state.registry[receiver_id]
            receiver_card = self.state.agent_cards.get(receiver_id, {})
            receiver_practices = receiver_card.get("practices", []) if isinstance(receiver_card, dict) else []
            practice_entry = next(
                (
                    entry for entry in receiver_practices
                    if isinstance(entry, dict) and str(entry.get("id") or "").strip() == str(msg.msg_type or "").strip()
                ),
                None,
            )
            path = str(practice_entry.get("path") or "/mailbox") if isinstance(practice_entry, dict) else "/mailbox"
            if not path.startswith("/"):
                path = f"/{path}"
            try:
                payload = {
                    "sender": auth.get("agent_name") or auth.get("agent_id"),
                    "receiver": msg.receiver,
                    "content": msg.content,
                    "msg_type": msg.msg_type
                }
                response = await self._client.post(f"{receiver_address}{path}", json=payload)
                response.raise_for_status()
                return {"status": "relayed", "response": response.json() if response.content else {}}
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Failed to relay: {str(e)}")

        app.include_router(router)


class PlazaPractice(Practice):
    """
    Composite practice that mounts the full Plaza endpoint suite.

    This class is a wrapper/aggregator around endpoint sub-practices and
    preserves backward-compatible attribute access for existing callers/tests.
    """

    SUPPORTED_PIT_TYPES = PlazaState.SUPPORTED_PIT_TYPES
    DIRECTORY_TABLE = PlazaState.DIRECTORY_TABLE
    PULSE_PULSER_TABLE = PlazaState.PULSE_PULSER_TABLE

    def __init__(
        self,
        registry: Optional[Dict[str, Any]] = None,
        self_heartbeat_interval: int = 10,
        init_files: Optional[List[str] | str] = None,
        config_dir: Optional[str] = None,
    ):
        """Initialize the Plaza practice."""
        super().__init__(
            name="Plaza Practice",
            description="Plaza endpoint bundle wrapper.",
            id="plaza",
            tags=["core", "plaza"]
        )
        self.state = PlazaState(
            registry=registry,
            self_heartbeat_interval=self_heartbeat_interval,
            init_files=init_files,
            config_dir=config_dir,
        )
        self.init_files = self.state.init_files
        self.config_dir = self.state.config_dir
        self.endpoint_practices: List[PlazaEndpointPractice] = [
            PlazaRegisterPractice(self.state),
            PlazaRenewPractice(self.state),
            PlazaAuthenticatePractice(self.state),
            PlazaHeartbeatPractice(self.state),
            PlazaSearchPractice(self.state),
            PlazaRelayPractice(self.state),
        ]
        # Backward-compatible attribute access used by tests/callers.
        self.registry = self.state.registry
        self.self_heartbeat_interval = self.state.self_heartbeat_interval
        self.tokens = self.state.tokens
        self.agent_tokens = self.state.agent_tokens
        self.pit_types = self.state.pit_types
        self.agent_ids = self.state.agent_ids
        self.registry_by_name = self.state.registry_by_name
        self.agent_names_by_id = self.state.agent_names_by_id
        self.credentials_by_id = self.state.credentials_by_id
        self.credential_store = self.state.credential_store
        self.plaza_url_for_store = self.state.plaza_url_for_store
        self.directory_pool = self.state.directory_pool
        self.agent_cards = self.state.agent_cards
        self.last_active = self.state.last_active
        self.login_history_by_id = self.state.login_history_by_id

    def get_callable_endpoints(self) -> List[Dict[str, Any]]:
        """Return the callable endpoints."""
        endpoints = []
        for practice in self.endpoint_practices:
            endpoints.append({
                "name": practice.name,
                "description": practice.description,
                "id": practice.id,
                "cost": practice.cost,
                "tags": practice.tags,
                "examples": practice.examples,
                "inputModes": practice.inputModes,
                "outputModes": practice.outputModes,
                "parameters": practice.parameters,
                "path": f"/{practice.id}"
            })
        return endpoints

    def mount(self, app):
        """Mount the value."""
        self.state.bootstrap_plaza_agent(self.agent)
        self.credential_store = self.state.credential_store
        self.plaza_url_for_store = self.state.plaza_url_for_store
        self.directory_pool = self.state.directory_pool
        for practice in self.endpoint_practices:
            practice.bind(self.agent)
            practice.mount(app)
