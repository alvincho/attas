"""
Agent Config module for `prompits.core.agent_config`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the core package defines the
shared abstractions that the rest of the runtime builds on.

Core types exposed here include `AgentConfigStore` and `AgentLaunchManager`, which carry
the main behavior or state managed by this module.
"""

from __future__ import annotations

import copy
import json
import re
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from prompits.core.process_utils import background_popen_kwargs, terminate_process

from prompits.core.init_schema import plaza_directory_table_schema
from prompits.core.pool import Pool


class AgentConfigStore:
    """Persist sanitized agent launch templates as Plaza directory entries."""

    TABLE_NAME = "plaza_directory"
    PIT_TYPE = "AgentConfig"

    def __init__(self, pool: Optional[Pool] = None):
        """Initialize the agent config store."""
        self.pool = pool

    @staticmethod
    def _as_text(value: Any) -> str:
        """Internal helper for as text."""
        return str(value or "").strip()

    @staticmethod
    def _normalize_tags(value: Any) -> List[str]:
        """Internal helper to normalize the tags."""
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value in (None, ""):
            return []
        return [str(value).strip()]

    @classmethod
    def sanitize_config(cls, raw_config: Dict[str, Any]) -> Dict[str, Any]:
        """Strip runtime-specific network and credential fields from a config template."""
        config = copy.deepcopy(dict(raw_config or {}))

        for key in (
            "id",
            "uuid",
            "ip",
            "ip_address",
            "host",
            "port",
            "address",
            "pit_address",
            "plaza_url",
            "plaza_urls",
            "agent_id",
            "api_key",
            "worker_id",
            "session_id",
            "session_started_at",
            "last_seen_at",
            "updated_at",
            "plaza_token",
            "token_expires_at",
            "plaza_owner_key",
            "owner_key",
            "plaza_owner_key_secret",
            "owner_key_secret",
        ):
            config.pop(key, None)

        agent_card = config.get("agent_card")
        if isinstance(agent_card, dict):
            for key in (
                "id",
                "uuid",
                "ip",
                "ip_address",
                "host",
                "port",
                "address",
                "pit_address",
                "agent_id",
                "api_key",
                "plaza_owner_key",
                "owner_key",
                "plaza_owner_key_secret",
                "owner_key_secret",
            ):
                agent_card.pop(key, None)
            meta = agent_card.get("meta")
            if isinstance(meta, dict):
                meta.pop("id", None)
                meta.pop("uuid", None)
                meta.pop("direct_auth_token", None)
                meta.pop("worker_id", None)
                meta.pop("environment", None)
                meta.pop("heartbeat", None)
                meta.pop("plaza_owner_key", None)
                meta.pop("owner_key", None)
                meta.pop("plaza_owner_key_secret", None)
                meta.pop("owner_key_secret", None)

        user_agent = config.get("user_agent")
        if isinstance(user_agent, dict):
            user_agent.pop("id", None)
            user_agent.pop("uuid", None)
            user_agent.pop("plaza_url", None)
            user_agent.pop("plaza_urls", None)

        return config

    @staticmethod
    def _is_plaza_config(config: Dict[str, Any]) -> bool:
        """Return whether the value is a Plaza config."""
        agent_type = str(config.get("type") or "").strip()
        return agent_type.endswith("PlazaAgent")

    @staticmethod
    def _is_user_agent_config(config: Dict[str, Any]) -> bool:
        """Return whether the value is an user agent config."""
        agent_type = str(config.get("type") or "").strip()
        return agent_type.endswith("UserAgent") or isinstance(config.get("user_agent"), dict)

    @staticmethod
    def prefers_ephemeral_identity(config: Dict[str, Any]) -> bool:
        """Return the prefers ephemeral identity."""
        if not isinstance(config, dict):
            return False
        agent_type = str(config.get("type") or "").strip()
        if agent_type.endswith("ADSWorkerAgent"):
            return True
        agent_card = config.get("agent_card") if isinstance(config.get("agent_card"), dict) else {}
        meta = agent_card.get("meta") if isinstance(agent_card.get("meta"), dict) else {}
        configured = agent_card.get("reuse_plaza_identity")
        if configured is None:
            configured = meta.get("reuse_plaza_identity")
        if configured is None:
            return False
        if isinstance(configured, bool):
            return not configured
        lowered = str(configured).strip().lower()
        if lowered in {"0", "false", "no", "n", "off"}:
            return True
        if lowered in {"1", "true", "yes", "y", "on"}:
            return False
        return False

    @classmethod
    def _derived_name(cls, config: Dict[str, Any]) -> str:
        """Internal helper to return the derived name."""
        agent_card = config.get("agent_card") if isinstance(config.get("agent_card"), dict) else {}
        return cls._as_text(config.get("name") or agent_card.get("name"))

    @classmethod
    def _derived_description(cls, config: Dict[str, Any]) -> str:
        """Internal helper for derived description."""
        agent_card = config.get("agent_card") if isinstance(config.get("agent_card"), dict) else {}
        return cls._as_text(config.get("description") or agent_card.get("description"))

    @classmethod
    def _derived_role(cls, config: Dict[str, Any]) -> str:
        """Internal helper for derived role."""
        agent_card = config.get("agent_card") if isinstance(config.get("agent_card"), dict) else {}
        return cls._as_text(config.get("role") or agent_card.get("role"))

    @classmethod
    def _derived_tags(cls, config: Dict[str, Any]) -> List[str]:
        """Internal helper for derived tags."""
        agent_card = config.get("agent_card") if isinstance(config.get("agent_card"), dict) else {}
        tags = config.get("tags")
        if not isinstance(tags, list):
            tags = agent_card.get("tags")
        return cls._normalize_tags(tags)

    @classmethod
    def _owner_key_id(cls, config: Dict[str, Any]) -> str:
        """Internal helper for owner key ID."""
        if not isinstance(config, dict):
            return ""
        agent_card = config.get("agent_card") if isinstance(config.get("agent_card"), dict) else {}
        card_meta = agent_card.get("meta") if isinstance(agent_card.get("meta"), dict) else {}
        return cls._as_text(
            card_meta.get("plaza_owner_key_id")
            or agent_card.get("plaza_owner_key_id")
            or config.get("plaza_owner_key_id")
        )

    @classmethod
    def _row_id(
        cls,
        *,
        config_id: str = "",
        name: str = "",
    ) -> str:
        """Internal helper to return the row ID."""
        explicit = cls._as_text(config_id)
        if explicit:
            return explicit
        normalized_name = re.sub(r"[^a-z0-9._-]+", "-", cls._as_text(name).lower()).strip("._-")
        if not normalized_name:
            normalized_name = "agent-config"
        return f"agent-config:{normalized_name}"

    @classmethod
    def looks_like_config_payload(cls, payload: Any) -> bool:
        """Return the looks like config payload."""
        if not isinstance(payload, dict):
            return False
        if not isinstance(payload.get("pools"), list) or not payload.get("pools"):
            return False
        return bool(cls._derived_name(payload) and cls._as_text(payload.get("type")))

    def ensure_table(self) -> bool:
        """Ensure the table exists."""
        if getattr(self, "_table_ready", False):
            return True
        if not self.pool:
            return False
        batch_upsert_tables = getattr(self.pool, "BATCH_UPSERT_RPC_BY_TABLE", None)
        if isinstance(batch_upsert_tables, dict) and self.TABLE_NAME in batch_upsert_tables:
            self._table_ready = True
            return True
        if self.pool._TableExists(self.TABLE_NAME):
            self._table_ready = True
            return True
        created = bool(self.pool._CreateTable(self.TABLE_NAME, plaza_directory_table_schema()))
        self._table_ready = created
        return created

    @staticmethod
    def _load_jsonish(value: Any, *, default: Any) -> Any:
        """Internal helper to load the jsonish."""
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
            except Exception:
                return copy.deepcopy(default)
            if isinstance(parsed, type(default)):
                return parsed
        return copy.deepcopy(default)

    def _coerce_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to coerce the row."""
        item = dict(row or {})
        item["card"] = self._load_jsonish(item.get("card"), default={})
        item["meta"] = self._load_jsonish(item.get("meta"), default={})
        return item

    def _public_row(self, row: Dict[str, Any], *, include_config: bool = False) -> Dict[str, Any]:
        """Internal helper to return the public row."""
        row = self._coerce_row(row)
        card = row.get("card") if isinstance(row.get("card"), dict) else {}
        meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        config = meta.get("config") if isinstance(meta.get("config"), dict) else {}
        card_meta = card.get("meta") if isinstance(card.get("meta"), dict) else {}
        item = {
            "id": self._as_text(row.get("id")),
            "name": self._as_text(row.get("name")),
            "description": self._as_text(row.get("description")),
            "owner": self._as_text(row.get("owner")),
            "role": self._as_text(card.get("role") or meta.get("role")),
            "agent_type": self._as_text(meta.get("agent_type") or card_meta.get("agent_type") or config.get("type")),
            "tags": self._normalize_tags(card.get("tags") or meta.get("tags")),
            "pit_type": self.PIT_TYPE,
            "address": self._as_text(row.get("address")),
            "owner_key_id": self._owner_key_id(config),
            "created_at": self._as_text(meta.get("created_at")),
            "updated_at": self._as_text(row.get("updated_at")),
        }
        if include_config:
            item["config"] = dict(config) if isinstance(config, dict) else {}
        return item

    def get(self, config_id: str, *, include_config: bool = True) -> Optional[Dict[str, Any]]:
        """Return the value."""
        if not self.pool or not self.ensure_table():
            return None
        rows = self.pool._GetTableData(self.TABLE_NAME, {"id": self._as_text(config_id)}) or []
        filtered = [self._coerce_row(raw) for raw in rows if self._as_text((raw or {}).get("type")) == self.PIT_TYPE]
        if not filtered:
            return None
        return self._public_row(filtered[-1], include_config=include_config)

    def search(
        self,
        *,
        query: str = "",
        name: str = "",
        owner: str = "",
        role: str = "",
        agent_type: str = "",
        include_config: bool = False,
    ) -> List[Dict[str, Any]]:
        """Search the value."""
        if not self.pool or not self.ensure_table():
            return []

        normalized_query = self._as_text(query).lower()
        normalized_name = self._as_text(name).lower()
        normalized_owner = self._as_text(owner).lower()
        normalized_role = self._as_text(role).lower()
        normalized_agent_type = self._as_text(agent_type).lower()

        rows = self.pool._GetTableData(self.TABLE_NAME) or []
        results: List[Dict[str, Any]] = []
        for raw_row in rows:
            row = self._coerce_row(raw_row)
            if self._as_text(row.get("type")) != self.PIT_TYPE:
                continue
            meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
            card = row.get("card") if isinstance(row.get("card"), dict) else {}
            haystack = " ".join(
                [
                    self._as_text(row.get("name")),
                    self._as_text(row.get("description")),
                    self._as_text(row.get("owner")),
                    self._as_text(card.get("role") or meta.get("role")),
                    self._as_text(meta.get("agent_type")),
                    " ".join(self._normalize_tags(card.get("tags") or meta.get("tags"))),
                ]
            ).lower()
            if normalized_query and normalized_query not in haystack:
                continue
            if normalized_name and normalized_name not in self._as_text(row.get("name")).lower():
                continue
            if normalized_owner and normalized_owner not in self._as_text(row.get("owner")).lower():
                continue
            if normalized_role and normalized_role != self._as_text(card.get("role") or meta.get("role")).lower():
                continue
            if normalized_agent_type and normalized_agent_type not in self._as_text(meta.get("agent_type")).lower():
                continue
            results.append(self._public_row(row, include_config=include_config))

        latest_by_name: Dict[str, Dict[str, Any]] = {}
        for item in results:
            key = self._as_text(item.get("name")).lower() or self._as_text(item.get("id"))
            current = latest_by_name.get(key)
            if current is None or self._as_text(item.get("updated_at")) >= self._as_text(current.get("updated_at")):
                latest_by_name[key] = item

        deduped = list(latest_by_name.values())
        deduped.sort(key=lambda item: ((item.get("name") or "").lower(), item.get("updated_at") or ""), reverse=False)
        return deduped

    def resolve(self, *, config_id: str = "", name: str = "", include_config: bool = True) -> Optional[Dict[str, Any]]:
        """Resolve the value."""
        normalized_id = self._as_text(config_id)
        if normalized_id:
            return self.get(normalized_id, include_config=include_config)

        normalized_name = self._as_text(name).lower()
        if not normalized_name:
            return None
        for item in self.search(name=normalized_name, include_config=include_config):
            if self._as_text(item.get("name")).lower() == normalized_name:
                return item
        matches = self.search(name=normalized_name, include_config=include_config)
        return matches[0] if matches else None

    def upsert(
        self,
        config: Dict[str, Any],
        *,
        config_id: str = "",
        owner: str = "",
        name: str = "",
        description: str = "",
    ) -> Dict[str, Any]:
        """Handle upsert for the agent config store."""
        if not self.pool:
            raise ValueError("No pool is configured for agent config persistence.")
        if not isinstance(config, dict):
            raise ValueError("Agent config must be a JSON object.")
        if not self.ensure_table():
            raise ValueError("Plaza directory storage is unavailable.")

        sanitized = self.sanitize_config(config)
        resolved_name = self._as_text(name or self._derived_name(sanitized))
        if not resolved_name:
            raise ValueError("Agent config name is required.")

        resolved_description = self._as_text(description or self._derived_description(sanitized))
        resolved_role = self._derived_role(sanitized)
        resolved_tags = self._derived_tags(sanitized)
        resolved_type = self._as_text(sanitized.get("type"))
        resolved_owner = self._as_text(owner or sanitized.get("owner") or (sanitized.get("agent_card") or {}).get("owner"))
        row_id = self._row_id(config_id=config_id, name=resolved_name)
        now = datetime.now(timezone.utc).isoformat()
        raw_meta = sanitized.get("meta") if isinstance(sanitized.get("meta"), dict) else {}
        created_at = self._as_text(
            sanitized.get("created_at")
            or raw_meta.get("created_at")
        ) or now
        meta = {
            "resource_type": "agent_config",
            "agent_type": resolved_type,
            "role": resolved_role,
            "tags": resolved_tags,
            "config": sanitized,
            "created_at": created_at,
            "updated_at": now,
        }
        card = {
            "name": resolved_name,
            "description": resolved_description,
            "owner": resolved_owner,
            "role": resolved_role,
            "tags": resolved_tags,
            "pit_type": self.PIT_TYPE,
            "meta": {
                "resource_type": "agent_config",
                "agent_type": resolved_type,
                "config_id": row_id,
            },
        }
        row = {
            "id": row_id,
            "agent_id": row_id,
            "name": resolved_name,
            "type": self.PIT_TYPE,
            "description": resolved_description,
            "owner": resolved_owner,
            "address": "",
            "meta": meta,
            "card": card,
            "updated_at": now,
        }
        if self.pool._Insert(self.TABLE_NAME, row) is False:
            raise ValueError("Failed saving agent config.")
        return self._public_row(row, include_config=True)


class AgentLaunchManager:
    """Launch agents from stored config templates with fresh runtime networking."""

    def __init__(
        self,
        *,
        default_plaza_url: str = "",
        default_bind_host: str = "127.0.0.1",
        workspace_root: Optional[str] = None,
    ):
        """Initialize the agent launch manager."""
        self.default_plaza_url = str(default_plaza_url or "").strip().rstrip("/")
        self.default_bind_host = str(default_bind_host or "").strip() or "127.0.0.1"
        self.workspace_root = Path(workspace_root or Path(__file__).resolve().parents[2]).resolve()
        self.runtime_root = Path(tempfile.gettempdir()) / "prompits-agent-launches"
        self.runtime_root.mkdir(parents=True, exist_ok=True)
        self._launches: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _normalize_url(value: Any) -> str:
        """Internal helper to normalize the URL."""
        return str(value or "").strip().rstrip("/")

    @staticmethod
    def _find_free_port(bind_host: str = "127.0.0.1") -> int:
        """Internal helper to find the free port."""
        candidates = [str(bind_host or "").strip(), "127.0.0.1", "0.0.0.0"]
        for host in candidates:
            if not host:
                continue
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.bind((host, 0))
                    return int(sock.getsockname()[1])
            except OSError:
                continue
        raise RuntimeError("Could not allocate a free TCP port.")

    @staticmethod
    def _tail_log(path: Path, *, lines: int = 20) -> str:
        """Internal helper for tail log."""
        if not path.exists():
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""
        parts = text.splitlines()
        return "\n".join(parts[-lines:])

    @staticmethod
    def _is_plaza_config(config: Dict[str, Any]) -> bool:
        """Return whether the value is a Plaza config."""
        return AgentConfigStore._is_plaza_config(config)

    @staticmethod
    def _is_user_agent_config(config: Dict[str, Any]) -> bool:
        """Return whether the value is an user agent config."""
        return AgentConfigStore._is_user_agent_config(config)

    def _compose_runtime_config(
        self,
        template: Dict[str, Any],
        *,
        host: str,
        port: int,
        plaza_url: str = "",
    ) -> Dict[str, Any]:
        """Internal helper to return the compose runtime config."""
        runtime_config = copy.deepcopy(dict(template or {}))
        runtime_config["host"] = host
        runtime_config["port"] = int(port)

        normalized_plaza_url = self._normalize_url(plaza_url or self.default_plaza_url)
        if normalized_plaza_url and not self._is_plaza_config(runtime_config):
            runtime_config["plaza_url"] = normalized_plaza_url
            if self._is_user_agent_config(runtime_config):
                runtime_config["plaza_urls"] = [normalized_plaza_url]
                user_agent = runtime_config.get("user_agent")
                if not isinstance(user_agent, dict):
                    user_agent = {}
                    runtime_config["user_agent"] = user_agent
                user_agent["plaza_url"] = normalized_plaza_url
                user_agent["plaza_urls"] = [normalized_plaza_url]

        return runtime_config

    @staticmethod
    def _ensure_agent_card(runtime_config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to ensure the agent card exists."""
        agent_card = runtime_config.get("agent_card")
        if not isinstance(agent_card, dict):
            agent_card = {}
            runtime_config["agent_card"] = agent_card
        return agent_card

    @staticmethod
    def _default_pool_name(agent_name: str = "") -> str:
        """Internal helper to return the default pool name."""
        normalized_name = str(agent_name or "").strip() or "agent"
        return f"{normalized_name}_pool"

    def _apply_pool_override(
        self,
        runtime_config: Dict[str, Any],
        *,
        agent_name: str = "",
        pool_type: str = "",
        pool_location: str = "",
    ) -> Dict[str, Any]:
        """Internal helper for apply pool override."""
        normalized_pool_type = str(pool_type or "").strip()
        normalized_pool_location = str(pool_location or "").strip()
        if not normalized_pool_type and not normalized_pool_location:
            return runtime_config

        pools = runtime_config.get("pools") if isinstance(runtime_config.get("pools"), list) else []
        current_pool = dict(pools[0]) if pools and isinstance(pools[0], dict) else {}
        effective_type = normalized_pool_type or str(current_pool.get("type") or "FileSystemPool").strip() or "FileSystemPool"
        updated_pool = dict(current_pool)
        updated_pool["type"] = effective_type
        updated_pool.setdefault("name", self._default_pool_name(agent_name))
        updated_pool.setdefault("description", f"{agent_name or 'Agent'} runtime pool")

        if effective_type == "FileSystemPool":
            updated_pool["root_path"] = normalized_pool_location or str(updated_pool.get("root_path") or "").strip()
            if not updated_pool.get("root_path"):
                raise ValueError("A pool location is required for FileSystemPool.")
            updated_pool.pop("db_path", None)
            updated_pool.pop("dsn", None)
        elif effective_type == "SQLitePool":
            updated_pool["db_path"] = normalized_pool_location or str(updated_pool.get("db_path") or "").strip()
            if not updated_pool.get("db_path"):
                raise ValueError("A pool location is required for SQLitePool.")
            updated_pool.pop("root_path", None)
            updated_pool.pop("dsn", None)
        elif effective_type == "PostgresPool":
            if normalized_pool_location:
                updated_pool["dsn"] = normalized_pool_location
            updated_pool.setdefault("schema", str(updated_pool.get("schema") or "public").strip() or "public")
            updated_pool.pop("root_path", None)
            updated_pool.pop("db_path", None)
            updated_pool.pop("url", None)
            updated_pool.pop("key", None)
        elif effective_type == "SupabasePool":
            if normalized_pool_location:
                updated_pool["url"] = normalized_pool_location
            if not updated_pool.get("url") or not updated_pool.get("key"):
                raise ValueError("SupabasePool requires an existing url and key configuration.")
            updated_pool.pop("root_path", None)
            updated_pool.pop("db_path", None)
            updated_pool.pop("dsn", None)
        else:
            raise ValueError(f"Unsupported pool type '{effective_type}'.")

        runtime_config["pools"] = [updated_pool]
        return runtime_config

    def _apply_launch_identity(
        self,
        runtime_config: Dict[str, Any],
        *,
        agent_name: str = "",
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Internal helper to return the apply launch identity."""
        normalized_name = str(agent_name or runtime_config.get("name") or "").strip()
        if normalized_name:
            runtime_config["name"] = normalized_name

        agent_card = self._ensure_agent_card(runtime_config)
        if normalized_name:
            agent_card["name"] = normalized_name

        if not isinstance(agent_card.get("tags"), list):
            tags = runtime_config.get("tags")
            agent_card["tags"] = list(tags) if isinstance(tags, list) else []
        if runtime_config.get("role") and not agent_card.get("role"):
            agent_card["role"] = runtime_config.get("role")

        if credentials:
            credential_agent_id = str(credentials.get("agent_id") or "").strip()
            credential_api_key = str(credentials.get("api_key") or "").strip()
            if credential_agent_id:
                agent_card["agent_id"] = credential_agent_id
            if credential_api_key:
                agent_card["api_key"] = credential_api_key

        return runtime_config

    def _wait_for_health(self, url: str, *, timeout_sec: float) -> bool:
        """Internal helper for wait for the health."""
        deadline = time.time() + max(float(timeout_sec), 0.1)
        while time.time() < deadline:
            try:
                response = requests.get(url, timeout=0.5)
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(0.25)
        return False

    def launch_config(
        self,
        config_row: Dict[str, Any],
        *,
        plaza_url: str = "",
        host: str = "",
        port: Optional[int] = None,
        wait_for_health_sec: float = 15.0,
        agent_name: str = "",
        pool_type: str = "",
        pool_location: str = "",
        credentials: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Return the launch config."""
        if not isinstance(config_row, dict):
            raise ValueError("Agent config row is required.")
        template = config_row.get("config") if isinstance(config_row.get("config"), dict) else {}
        if not template:
            raise ValueError("Stored agent config has no launchable config payload.")

        bind_host = str(host or self.default_bind_host).strip() or self.default_bind_host
        bind_port = int(port or self._find_free_port(bind_host))
        runtime_config = self._compose_runtime_config(
            template,
            host=bind_host,
            port=bind_port,
            plaza_url=plaza_url,
        )
        runtime_config = self._apply_launch_identity(
            runtime_config,
            agent_name=agent_name or str(config_row.get("name") or "").strip(),
            credentials=credentials,
        )
        runtime_config = self._apply_pool_override(
            runtime_config,
            agent_name=str(runtime_config.get("name") or config_row.get("name") or "").strip(),
            pool_type=pool_type,
            pool_location=pool_location,
        )

        launch_id = str(uuid.uuid4())
        launch_dir = self.runtime_root / launch_id
        launch_dir.mkdir(parents=True, exist_ok=True)
        config_path = launch_dir / "config.agent"
        log_path = launch_dir / "agent.log"
        config_path.write_text(json.dumps(runtime_config, indent=2), encoding="utf-8")

        process = None
        log_handle = log_path.open("ab")
        try:
            process = subprocess.Popen(
                [sys.executable, str(self.workspace_root / "prompits" / "create_agent.py"), "--config", str(config_path)],
                cwd=str(self.workspace_root),
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                **background_popen_kwargs(),
            )
        finally:
            log_handle.close()

        address = f"http://{bind_host}:{bind_port}"
        healthy = self._wait_for_health(f"{address}/health", timeout_sec=wait_for_health_sec)
        if not healthy:
            if process and process.poll() is None:
                terminate_process(process, timeout_sec=2.0)
            log_tail = self._tail_log(log_path)
            raise RuntimeError(
                "Launched agent did not become healthy in time."
                + (f"\n{log_tail}" if log_tail else "")
            )

        started_at = datetime.now(timezone.utc).isoformat()
        result = {
            "launch_id": launch_id,
            "config_id": str(config_row.get("id") or ""),
            "name": str(config_row.get("name") or runtime_config.get("name") or "").strip(),
            "pid": int(process.pid) if process else 0,
            "host": bind_host,
            "port": bind_port,
            "address": address,
            "plaza_url": self._normalize_url(plaza_url or self.default_plaza_url),
            "config_path": str(config_path),
            "log_path": str(log_path),
            "started_at": started_at,
            "status": "running",
            "used_existing_identity": bool(credentials and (credentials.get("agent_id") or credentials.get("api_key"))),
        }
        self._launches[launch_id] = dict(result)
        return result

    def list_launches(self) -> List[Dict[str, Any]]:
        """List the launches."""
        launches = list(self._launches.values())
        launches.sort(key=lambda item: str(item.get("started_at") or ""), reverse=True)
        return launches
