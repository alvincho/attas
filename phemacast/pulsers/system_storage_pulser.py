"""
Shared system storage pulser implementation for the Pulsers area.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, these modules implement pulse sources for
APIs, files, bosses, MCP tools, and path-based workflows.

Core types exposed here include `SystemStoragePulser`, which carries the shared
storage behavior used by `SystemPulser`.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import mimetypes
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import quote

try:
    import boto3
except Exception:  # pragma: no cover - optional import for environments without boto3
    boto3 = None

try:
    from botocore.exceptions import ClientError
except Exception:  # pragma: no cover - botocore ships with boto3
    ClientError = Exception

from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from phemacast.agents.pulser import ConfigInput, Pulser, _read_config, validate_pulser_config_test_parameters


SYSTEM_PARTY = "System"
DEFAULT_STORAGE_ROOT = Path(__file__).resolve().parents[2] / "storage" / "system_pulser"


def _utcnow_iso() -> str:
    """Internal helper for utcnow iso."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _resolve_config_value(value: Any) -> Any:
    """Internal helper to resolve the config value."""
    if isinstance(value, Mapping):
        env_name = value.get("env") or value.get("name")
        fallback = value.get("value", value.get("fallback"))
        if env_name:
            resolved = os.getenv(str(env_name))
            if resolved not in (None, ""):
                return resolved
            return fallback
        if "value" in value:
            return fallback
    elif isinstance(value, str):
        trimmed = value.strip()
        if trimmed.startswith("env:"):
            return os.getenv(trimmed[4:].strip())
        if trimmed.startswith("${") and trimmed.endswith("}"):
            return os.getenv(trimmed[2:-1].strip())
    return value


def _normalize_bucket_name(value: Any) -> str:
    """Internal helper to normalize the bucket name."""
    bucket_name = str(value or "").strip().lower()
    if not bucket_name:
        raise ValueError("bucket_name is required.")
    if len(bucket_name) < 3 or len(bucket_name) > 63:
        raise ValueError("bucket_name must be between 3 and 63 characters.")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789.-")
    if any(char not in allowed for char in bucket_name):
        raise ValueError("bucket_name may only include lowercase letters, numbers, dots, and hyphens.")
    if bucket_name.startswith((".", "-")) or bucket_name.endswith((".", "-")):
        raise ValueError("bucket_name cannot start or end with a dot or hyphen.")
    if ".." in bucket_name:
        raise ValueError("bucket_name cannot contain consecutive dots.")
    return bucket_name


def _normalize_object_key(value: Any) -> str:
    """Internal helper to normalize the object key."""
    raw_key = str(value or "").strip()
    if not raw_key:
        raise ValueError("object_key is required.")
    parts = [part for part in raw_key.replace("\\", "/").split("/") if part]
    if not parts:
        raise ValueError("object_key is required.")
    if any(part in {".", ".."} for part in parts):
        raise ValueError("object_key cannot contain '.' or '..' path segments.")
    return "/".join(parts)


def _coerce_visibility(value: Any) -> str:
    """Internal helper to coerce the visibility."""
    visibility = str(value or "private").strip().lower()
    if visibility not in {"private", "public"}:
        raise ValueError("visibility must be 'private' or 'public'.")
    return visibility


def _coerce_limit(value: Any, default: int = 200) -> int:
    """Internal helper to coerce the limit."""
    try:
        limit = int(value if value is not None else default)
    except (TypeError, ValueError):
        return default
    if limit <= 0:
        return default
    return limit


class _StorageBackend:
    """Represent a storage backend."""
    backend_type = "unknown"

    def write_bytes(self, relative_key: str, payload: bytes, *, content_type: str = "application/octet-stream") -> None:
        """Write the bytes."""
        raise NotImplementedError

    def read_bytes(self, relative_key: str) -> Optional[bytes]:
        """Read the bytes."""
        raise NotImplementedError

    def exists(self, relative_key: str) -> bool:
        """Return whether the value exists for value."""
        raise NotImplementedError

    def list_keys(self, prefix: str = "") -> List[str]:
        """List the keys."""
        raise NotImplementedError


class _FilesystemStorageBackend(_StorageBackend):
    """Represent a filesystem storage backend."""
    backend_type = "filesystem"

    def __init__(self, root_path: Path):
        """Initialize the filesystem storage backend."""
        self.root_path = Path(root_path).expanduser().resolve()
        self.root_path.mkdir(parents=True, exist_ok=True)

    def _path_for(self, relative_key: str) -> Path:
        """Internal helper to return the path for."""
        cleaned = str(relative_key or "").strip().strip("/")
        target = self.root_path
        if cleaned:
            target = self.root_path.joinpath(*[part for part in cleaned.split("/") if part])
        resolved = target.resolve()
        if resolved != self.root_path and self.root_path not in resolved.parents:
            raise ValueError("Resolved storage path escaped the configured root.")
        return resolved

    def write_bytes(self, relative_key: str, payload: bytes, *, content_type: str = "application/octet-stream") -> None:
        """Write the bytes."""
        target_path = self._path_for(relative_key)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(payload)

    def read_bytes(self, relative_key: str) -> Optional[bytes]:
        """Read the bytes."""
        target_path = self._path_for(relative_key)
        if not target_path.exists() or not target_path.is_file():
            return None
        return target_path.read_bytes()

    def exists(self, relative_key: str) -> bool:
        """Return whether the value exists for value."""
        target_path = self._path_for(relative_key)
        return target_path.exists()

    def list_keys(self, prefix: str = "") -> List[str]:
        """List the keys."""
        base_path = self._path_for(prefix) if str(prefix or "").strip() else self.root_path
        if not base_path.exists():
            return []
        if base_path.is_file():
            return [str(prefix or "").strip("/")]
        return sorted(path.relative_to(self.root_path).as_posix() for path in base_path.rglob("*") if path.is_file())


class _S3StorageBackend(_StorageBackend):
    """Represent a s 3 storage backend."""
    backend_type = "s3"

    def __init__(self, config: Mapping[str, Any]):
        """Initialize the s 3 storage backend."""
        if boto3 is None:
            raise RuntimeError("S3 backend requires boto3 to be installed.")

        self.bucket_name = str(_resolve_config_value(config.get("bucket")) or _resolve_config_value(config.get("bucket_name")) or "").strip()
        if not self.bucket_name:
            raise ValueError("S3 storage backend requires a bucket or bucket_name.")
        self.prefix = str(_resolve_config_value(config.get("prefix")) or "").strip().strip("/")
        self.client = boto3.client(
            "s3",
            region_name=_resolve_config_value(config.get("region_name") or config.get("region")),
            endpoint_url=_resolve_config_value(config.get("endpoint_url")),
            aws_access_key_id=_resolve_config_value(config.get("aws_access_key_id")),
            aws_secret_access_key=_resolve_config_value(config.get("aws_secret_access_key")),
            aws_session_token=_resolve_config_value(config.get("aws_session_token")),
        )

    def _full_key(self, relative_key: str) -> str:
        """Internal helper to return the full key."""
        cleaned = str(relative_key or "").strip().strip("/")
        if self.prefix and cleaned:
            return f"{self.prefix}/{cleaned}"
        if self.prefix:
            return self.prefix
        return cleaned

    def write_bytes(self, relative_key: str, payload: bytes, *, content_type: str = "application/octet-stream") -> None:
        """Write the bytes."""
        self.client.put_object(
            Bucket=self.bucket_name,
            Key=self._full_key(relative_key),
            Body=payload,
            ContentType=content_type,
        )

    def read_bytes(self, relative_key: str) -> Optional[bytes]:
        """Read the bytes."""
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=self._full_key(relative_key))
        except ClientError as exc:
            error_code = str(((exc.response or {}).get("Error") or {}).get("Code") or "")
            if error_code in {"NoSuchKey", "404", "NotFound"}:
                return None
            raise
        return response["Body"].read()

    def exists(self, relative_key: str) -> bool:
        """Return whether the value exists for value."""
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=self._full_key(relative_key))
            return True
        except ClientError as exc:
            error_code = str(((exc.response or {}).get("Error") or {}).get("Code") or "")
            if error_code in {"404", "NotFound", "NoSuchKey"}:
                return False
            raise

    def list_keys(self, prefix: str = "") -> List[str]:
        """List the keys."""
        requested_prefix = str(prefix or "").strip().strip("/")
        full_prefix = self._full_key(requested_prefix)
        keys: List[str] = []
        continuation_token: Optional[str] = None
        while True:
            params: Dict[str, Any] = {"Bucket": self.bucket_name, "Prefix": full_prefix}
            if continuation_token:
                params["ContinuationToken"] = continuation_token
            response = self.client.list_objects_v2(**params)
            for entry in response.get("Contents") or []:
                full_key = str(entry.get("Key") or "")
                prefix_base = f"{self.prefix}/" if self.prefix else ""
                relative_key = full_key[len(prefix_base):] if prefix_base and full_key.startswith(prefix_base) else full_key
                if relative_key:
                    keys.append(relative_key)
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
        return sorted(keys)


def _default_supported_pulses() -> List[Dict[str, Any]]:
    """Internal helper to return the default supported pulses."""
    return [
        {
            "name": "bucket_create",
            "aliases": ["create_bucket"],
            "pulse_address": "plaza://pulse/bucket_create",
            "description": "Create a logical bucket with private or public visibility.",
            "party": SYSTEM_PARTY,
            "tags": ["storage", "bucket", "create", "system"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "bucket_name": {"type": "string"},
                    "visibility": {"type": "string", "enum": ["private", "public"], "default": "private"},
                },
                "required": ["bucket_name"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "bucket_name": {"type": "string"},
                    "visibility": {"type": "string"},
                    "owner_agent_id": {"type": "string"},
                    "owner_agent_name": {"type": "string"},
                    "created_at": {"type": "string"},
                },
                "required": ["status", "bucket_name", "visibility"],
            },
            "test_data": {"bucket_name": "demo-assets", "visibility": "private"},
        },
        {
            "name": "list_bucket",
            "aliases": ["bucket_list", "list_buckets"],
            "pulse_address": "plaza://pulse/list_bucket",
            "description": "List logical buckets visible to the requesting agent in this storage pulser.",
            "party": SYSTEM_PARTY,
            "tags": ["storage", "bucket", "list", "system"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "visibility": {"type": "string", "enum": ["all", "private", "public"], "default": "all"},
                    "limit": {"type": "integer", "default": 200},
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "visibility_filter": {"type": "string"},
                    "returned_count": {"type": "integer"},
                    "buckets": {"type": "array"},
                },
                "required": ["visibility_filter", "returned_count", "buckets"],
            },
            "test_data": {"visibility": "all"},
        },
        {
            "name": "bucket_browse",
            "aliases": ["browse_bucket"],
            "pulse_address": "plaza://pulse/bucket_browse",
            "description": "List stored objects in a logical bucket.",
            "party": SYSTEM_PARTY,
            "tags": ["storage", "bucket", "browse", "system"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "bucket_name": {"type": "string"},
                    "prefix": {"type": "string"},
                    "limit": {"type": "integer", "default": 200},
                },
                "required": ["bucket_name"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "bucket_name": {"type": "string"},
                    "visibility": {"type": "string"},
                    "returned_count": {"type": "integer"},
                    "objects": {"type": "array"},
                },
                "required": ["bucket_name", "objects"],
            },
            "test_data": {"bucket_name": "demo-assets"},
        },
        {
            "name": "object_save",
            "aliases": ["save_object", "object_put"],
            "pulse_address": "plaza://pulse/object_save",
            "description": "Persist text, JSON, or binary content in a logical bucket.",
            "party": SYSTEM_PARTY,
            "tags": ["storage", "object", "save", "system"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "bucket_name": {"type": "string"},
                    "object_key": {"type": "string"},
                    "text": {"type": "string"},
                    "data": {"description": "Any JSON-serializable payload."},
                    "base64_data": {
                        "type": "string",
                        "contentEncoding": "base64",
                        "description": "Base64-encoded binary blob such as a PDF, image, audio file, or video clip.",
                    },
                    "content_type": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["bucket_name", "object_key"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "bucket_name": {"type": "string"},
                    "object_key": {"type": "string"},
                    "content_type": {"type": "string"},
                    "size_bytes": {"type": "integer"},
                    "etag": {"type": "string"},
                },
                "required": ["status", "bucket_name", "object_key", "etag"],
            },
            "test_data": {
                "bucket_name": "demo-assets",
                "object_key": "notes/hello.txt",
                "text": "hello world",
            },
        },
        {
            "name": "object_load",
            "aliases": ["load_object", "object_get"],
            "pulse_address": "plaza://pulse/object_load",
            "description": "Load text, JSON, or binary content from a logical bucket.",
            "party": SYSTEM_PARTY,
            "tags": ["storage", "object", "load", "system"],
            "input_schema": {
                "type": "object",
                "properties": {
                    "bucket_name": {"type": "string"},
                    "object_key": {"type": "string"},
                    "response_format": {"type": "string", "enum": ["auto", "json", "text", "base64"], "default": "auto"},
                },
                "required": ["bucket_name", "object_key"],
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "bucket_name": {"type": "string"},
                    "object_key": {"type": "string"},
                    "content_type": {"type": "string"},
                    "size_bytes": {"type": "integer"},
                    "etag": {"type": "string"},
                    "text": {"type": "string"},
                    "data": {},
                    "base64_data": {"type": "string", "contentEncoding": "base64"},
                },
                "required": ["bucket_name", "object_key", "etag"],
            },
            "test_data": {
                "bucket_name": "demo-assets",
                "object_key": "notes/hello.txt",
                "response_format": "text",
            },
        },
    ]


class SystemStoragePulser(Pulser):
    """Represent the shared system storage pulser behavior."""
    def __init__(
        self,
        config: Optional[ConfigInput] = None,
        *,
        config_path: Optional[ConfigInput] = None,
        name: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        plaza_url: Optional[str] = None,
        agent_card: Optional[Dict[str, Any]] = None,
        pool: Any = None,
        supported_pulses: Optional[List[Dict[str, Any]]] = None,
        auto_register: Optional[bool] = None,
    ):
        """Initialize the shared system storage pulser."""
        config_data = _read_config(config) if config is not None else {}
        resolved_config_path = config_path
        if resolved_config_path is None and isinstance(config, (str, Path)):
            resolved_config_path = config

        self.config_path = Path(resolved_config_path).resolve() if resolved_config_path else None
        self._config_root = self.config_path.parent if self.config_path else Path.cwd()
        self.raw_config = dict(config_data or {})

        storage_config = self.raw_config.get("storage")
        if not isinstance(storage_config, Mapping):
            storage_config = self.raw_config.get("backend")
        self.storage_config = dict(storage_config or {})
        self.backend = self._build_storage_backend(self.storage_config)

        resolved_name = str(name or self.raw_config.get("name") or "SystemPulser")
        resolved_host = str(host or self.raw_config.get("host") or "127.0.0.1")
        try:
            resolved_port = int(port if port is not None else self.raw_config.get("port") or 8063)
        except (TypeError, ValueError):
            resolved_port = 8063
        resolved_plaza_url = str(plaza_url or self.raw_config.get("plaza_url") or "").strip() or None
        resolved_auto_register = bool(
            auto_register if auto_register is not None else self.raw_config.get("auto_register", True)
        )

        card = dict(agent_card or self.raw_config.get("agent_card") or {})
        card.setdefault("name", resolved_name)
        card["party"] = str(self.raw_config.get("party") or card.get("party") or SYSTEM_PARTY).strip() or SYSTEM_PARTY
        card["role"] = str(self.raw_config.get("role") or card.get("role") or "pulser")
        card["description"] = str(
            self.raw_config.get("description")
            or card.get("description")
            or "System storage pulser with S3-style buckets and object operations."
        )
        card["tags"] = self._merge_tags(
            card.get("tags"),
            self.raw_config.get("tags"),
            ["storage", "s3", "bucket", "object", "system"],
        )
        meta = dict(card.get("meta") or {})
        meta.setdefault("party", card["party"])
        meta["storage_backend"] = self.backend.backend_type
        card["meta"] = meta

        resolved_supported_pulses = supported_pulses or self.raw_config.get("supported_pulses") or _default_supported_pulses()
        self._storage_supported_pulses = [copy.deepcopy(dict(pulse)) for pulse in resolved_supported_pulses if isinstance(pulse, Mapping)]

        super().__init__(
            config=self.raw_config or {"name": card["name"]},
            config_path=self.config_path,
            name=card["name"],
            host=resolved_host,
            port=resolved_port,
            plaza_url=resolved_plaza_url,
            agent_card=card,
            pool=pool,
            supported_pulses=[copy.deepcopy(pulse) for pulse in self._storage_supported_pulses],
            auto_register=resolved_auto_register,
        )

        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        self.templates = Jinja2Templates(directory=template_dir)
        self._sync_storage_card_metadata(card["party"])
        self._setup_system_routes()

    def _setup_system_routes(self) -> None:
        """Internal helper to set up the system pulser routes."""
        @self.app.get("/")
        async def system_pulser_ui(request: Request):
            """Route handler for GET /."""
            return self.templates.TemplateResponse(
                request=request,
                name="phemacast/pulsers/templates/system_pulser_editor.html",
                context={
                    "agent_name": self.agent_card.get("name", self.name),
                    "config_path": str(self.config_path) if self.config_path else "",
                },
            )

        @self.app.get("/api/config")
        async def get_system_pulser_config():
            """Route handler for GET /api/config."""
            config = await run_in_threadpool(self._load_config_document)
            return {
                "status": "success",
                "config": config,
                "config_path": str(self.config_path) if self.config_path else None,
            }

        @self.app.post("/api/config")
        async def save_system_pulser_config(request: Request):
            """Route handler for POST /api/config."""
            payload = await request.json()
            config = payload.get("config") if isinstance(payload, dict) and isinstance(payload.get("config"), dict) else payload
            if not isinstance(config, dict):
                raise HTTPException(status_code=400, detail="Config payload must be a JSON object.")
            saved = await run_in_threadpool(self._save_config_document, config)
            return {
                "status": "success",
                "config": saved,
                "config_path": str(self.config_path) if self.config_path else None,
            }

        @self.app.post("/api/test-pulse")
        async def test_system_pulser_pulse(request: Request):
            """Exercise the test_system_pulser_pulse regression scenario."""
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Test payload must be a JSON object.")

            pulse_name = payload.get("pulse_name")
            params = payload.get("params") or {}
            config = payload.get("config")
            include_debug = bool(payload.get("debug"))
            if not pulse_name:
                raise HTTPException(status_code=400, detail="pulse_name is required.")
            if not isinstance(params, dict):
                raise HTTPException(status_code=400, detail="params must be a JSON object.")
            if config is not None and not isinstance(config, dict):
                raise HTTPException(status_code=400, detail="config must be a JSON object when provided.")

            def _run_test_sync():
                """Internal helper to run the test sync."""
                runtime_config = config if isinstance(config, dict) else self._load_config_document()
                runner = self.__class__(config=runtime_config, auto_register=False)
                pulse_definition = runner.resolve_pulse_definition(pulse_name=str(pulse_name))
                result = runner.fetch_pulse_payload(str(pulse_name), params, pulse_definition) or {}
                return runner, pulse_definition, result

            try:
                runner, pulse_definition, result = await run_in_threadpool(_run_test_sync)
            except Exception as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

            response = {
                "status": "success",
                "pulse_name": str(pulse_name),
                "params": params,
                "result": result,
            }
            if include_debug:
                response["debug"] = {
                    "pulse_definition": pulse_definition,
                    "storage_backend": runner.backend.backend_type,
                    "storage_config": runner._normalize_storage_config(runner.storage_config),
                    "result": result,
                }
            return response

    def _load_config_document(self) -> Dict[str, Any]:
        """Internal helper to load the config document."""
        if self.config_path and self.config_path.exists():
            with self.config_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            self._apply_runtime_document(loaded)
            return self._build_editor_config_document(loaded)
        return self._build_editor_config_document(self.raw_config or self._synthesize_runtime_config())

    def _save_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to save the config document."""
        if not self.config_path:
            raise HTTPException(status_code=400, detail="This SystemPulser was not started from a config file.")

        normalized = self._normalize_config_document(config)
        try:
            validate_pulser_config_test_parameters(normalized)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(normalized, indent=4), encoding="utf-8")
        self._apply_runtime_document(normalized)
        return self._build_editor_config_document(normalized)

    def _apply_runtime_document(self, config: Mapping[str, Any]) -> None:
        """Internal helper for apply runtime document."""
        document = dict(config or {})
        configured_party = str(document.get("party") or self.agent_card.get("party") or SYSTEM_PARTY).strip() or SYSTEM_PARTY
        supported_pulses = self._resolve_supported_pulses_for_document(document)
        if supported_pulses and "supported_pulses" not in document:
            document["supported_pulses"] = [self._normalize_config_pulse(pulse) for pulse in supported_pulses]
        self.raw_config = document
        self.agent_card["party"] = configured_party
        self.apply_pulser_config(document, supported_pulses=supported_pulses)
        self._apply_storage_settings(document)
        self._sync_storage_card_metadata(configured_party)

    def _apply_storage_settings(self, config: Mapping[str, Any]) -> None:
        """Internal helper to return the apply storage settings."""
        storage_config = config.get("storage") if isinstance(config.get("storage"), Mapping) else None
        if storage_config is None and isinstance(config.get("backend"), Mapping):
            storage_config = config.get("backend")
        self.storage_config = dict(storage_config or {})
        self.backend = self._build_storage_backend(self.storage_config)

    def _resolve_supported_pulses_for_document(self, config: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
        """Internal helper to resolve the supported pulses for the document."""
        if isinstance(config, Mapping):
            configured_pulses = config.get("supported_pulses")
            if isinstance(configured_pulses, list) and any(isinstance(pulse, Mapping) for pulse in configured_pulses):
                return [copy.deepcopy(dict(pulse)) for pulse in configured_pulses if isinstance(pulse, Mapping)]
        return [copy.deepcopy(dict(pulse)) for pulse in self._storage_supported_pulses]

    @staticmethod
    def _normalize_config_pulse(pulse: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the config pulse."""
        normalized = dict(pulse or {})
        for key in (
            "pulse_definition",
            "pulse_id",
            "resource_type",
            "pds_version",
            "status",
            "pulse_class",
            "title",
            "concept",
            "interface",
            "resolved_test_data",
            "resolved_test_data_error",
            "completion_status",
            "completion_errors",
            "is_complete",
        ):
            normalized.pop(key, None)
        return normalized

    @staticmethod
    def _build_editor_pulse(pulse: Mapping[str, Any]) -> Dict[str, Any]:
        """Internal helper to build the editor pulse."""
        editor_pulse = dict(pulse or {})
        for key in ("pulse_id", "completion_status", "completion_errors", "is_complete", "resolved_test_data_error"):
            editor_pulse.pop(key, None)
        if isinstance(editor_pulse.get("pulse_definition"), Mapping):
            editor_pulse["pulse_definition"] = dict(editor_pulse["pulse_definition"])
        if isinstance(editor_pulse.get("test_data"), Mapping):
            editor_pulse["test_data"] = dict(editor_pulse["test_data"])
        if isinstance(editor_pulse.get("resolved_test_data"), Mapping):
            editor_pulse["resolved_test_data"] = dict(editor_pulse["resolved_test_data"])
        return editor_pulse

    @staticmethod
    def _normalize_storage_field(value: Any) -> Any:
        """Internal helper to normalize the storage field."""
        if value in (None, ""):
            return ""
        if isinstance(value, Mapping):
            return dict(value)
        return str(value)

    def _normalize_storage_config(self, storage_config: Any) -> Dict[str, Any]:
        """Internal helper to normalize the storage config."""
        raw = dict(storage_config or {}) if isinstance(storage_config, Mapping) else {}
        backend_type = str(_resolve_config_value(raw.get("type") or raw.get("backend_type")) or "filesystem").strip().lower()
        if backend_type in {"file", "local"}:
            backend_type = "filesystem"
        normalized: Dict[str, Any] = {"type": backend_type or "filesystem"}
        if normalized["type"] == "s3":
            for key in ("bucket", "bucket_name", "prefix", "region_name", "region", "endpoint_url", "aws_access_key_id", "aws_secret_access_key", "aws_session_token"):
                if key in raw:
                    normalized[key] = self._normalize_storage_field(raw.get(key))
            if "bucket" not in normalized and "bucket_name" in normalized:
                normalized["bucket"] = normalized.pop("bucket_name")
            return normalized
        normalized["type"] = "filesystem"
        normalized["root_path"] = self._normalize_storage_field(raw.get("root_path") or raw.get("path") or "storage/system_pulser")
        return normalized

    def _normalize_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the config document."""
        document = dict(config or {})
        document.setdefault("name", self.agent_card.get("name", self.name))
        document.setdefault("type", "phemacast.pulsers.system_pulser.SystemPulser")
        document.setdefault("host", self.host)
        document.setdefault("port", self.port)
        if self.plaza_url and "plaza_url" not in document:
            document["plaza_url"] = self.plaza_url
        document.setdefault("party", self.agent_card.get("party", SYSTEM_PARTY))
        document.setdefault("role", "pulser")
        document.setdefault("description", self.agent_card.get("description", ""))
        document["tags"] = list(document.get("tags") or [])
        document["storage"] = self._normalize_storage_config(document.get("storage") or document.get("backend") or self.storage_config)
        document["supported_pulses"] = [
            self._normalize_config_pulse(pulse)
            for pulse in self._resolve_supported_pulses_for_document(document)
            if isinstance(pulse, dict)
        ]
        if "pools" in self.raw_config and "pools" not in document:
            document["pools"] = self.raw_config["pools"]
        if "practices" in self.raw_config and "practices" not in document:
            document["practices"] = self.raw_config["practices"]
        return document

    def _build_editor_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to build the editor config document."""
        document = self._normalize_config_document(config)
        runtime_supported_pulses = (
            self.supported_pulses
            if isinstance(getattr(self, "supported_pulses", None), list) and self.supported_pulses
            else self._resolve_supported_pulses_for_document(document)
        )
        document["supported_pulses"] = [self._build_editor_pulse(pulse) for pulse in runtime_supported_pulses]
        document["storage"] = self._normalize_storage_config(document.get("storage") or self.storage_config or {})
        return document

    def _synthesize_runtime_config(self) -> Dict[str, Any]:
        """Internal helper to return the synthesize runtime config."""
        return {
            "name": self.agent_card.get("name", self.name),
            "type": "phemacast.pulsers.system_pulser.SystemPulser",
            "host": self.host,
            "port": self.port,
            "plaza_url": self.plaza_url,
            "party": self.agent_card.get("party", SYSTEM_PARTY),
            "role": self.agent_card.get("role", "pulser"),
            "description": self.agent_card.get("description", ""),
            "tags": list(self.agent_card.get("tags") or []),
            "storage": self._normalize_storage_config(self.storage_config),
            "supported_pulses": [
                self._normalize_config_pulse(pulse)
                for pulse in self._resolve_supported_pulses_for_document(self.raw_config)
            ],
            "pools": list(self.raw_config.get("pools") or []),
            "practices": list(self.raw_config.get("practices") or []),
        }

    def _sync_storage_card_metadata(self, party: Optional[str] = None) -> None:
        """Internal helper to synchronize the storage card metadata."""
        configured_party = str(party or self.agent_card.get("party") or SYSTEM_PARTY).strip() or SYSTEM_PARTY
        meta = dict(self.agent_card.get("meta") or {})
        meta["party"] = configured_party
        meta["storage_backend"] = self.backend.backend_type
        if isinstance(self.backend, _FilesystemStorageBackend):
            meta["storage_root"] = str(self.backend.root_path)
            meta.pop("storage_bucket", None)
            meta.pop("storage_prefix", None)
        elif isinstance(self.backend, _S3StorageBackend):
            meta["storage_bucket"] = self.backend.bucket_name
            meta["storage_prefix"] = self.backend.prefix
            meta.pop("storage_root", None)
        self.agent_card["party"] = configured_party
        self.agent_card["meta"] = meta

    def _build_storage_backend(self, storage_config: Mapping[str, Any]) -> _StorageBackend:
        """Internal helper to build the storage backend."""
        backend_type = str(
            _resolve_config_value(storage_config.get("type") or storage_config.get("backend_type")) or "filesystem"
        ).strip().lower()
        if backend_type in {"filesystem", "file", "local"}:
            configured_root = _resolve_config_value(storage_config.get("root_path") or storage_config.get("path"))
            root_path = Path(str(configured_root or DEFAULT_STORAGE_ROOT)).expanduser()
            if not root_path.is_absolute():
                workspace_relative = root_path.resolve()
                config_relative = (self._config_root / root_path).resolve()
                root_path = workspace_relative if workspace_relative.exists() or not config_relative.exists() else config_relative
            return _FilesystemStorageBackend(root_path)
        if backend_type == "s3":
            return _S3StorageBackend(storage_config)
        raise ValueError(f"Unsupported storage backend type: {backend_type}")

    @staticmethod
    def _bucket_metadata_key(bucket_name: str) -> str:
        """Internal helper to return the bucket metadata key."""
        return f"__meta__/buckets/{bucket_name}.json"

    @staticmethod
    def _object_metadata_key(bucket_name: str, object_key: str) -> str:
        """Internal helper to return the object metadata key."""
        return f"__meta__/objects/{bucket_name}/{quote(object_key, safe='')}.json"

    @staticmethod
    def _object_data_key(bucket_name: str, object_key: str) -> str:
        """Internal helper to return the object data key."""
        return f"data/{bucket_name}/{object_key}"

    def _load_json_document(self, relative_key: str) -> Optional[Dict[str, Any]]:
        """Internal helper to load the JSON document."""
        payload = self.backend.read_bytes(relative_key)
        if payload is None:
            return None
        loaded = json.loads(payload.decode("utf-8"))
        return dict(loaded) if isinstance(loaded, Mapping) else None

    def _save_json_document(self, relative_key: str, document: Mapping[str, Any]) -> None:
        """Internal helper to save the JSON document."""
        self.backend.write_bytes(
            relative_key,
            json.dumps(dict(document), ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"),
            content_type="application/json",
        )

    def _load_bucket(self, bucket_name: str) -> Optional[Dict[str, Any]]:
        """Internal helper to load the bucket."""
        return self._load_json_document(self._bucket_metadata_key(bucket_name))

    def _save_bucket(self, bucket: Mapping[str, Any]) -> None:
        """Internal helper to save the bucket."""
        self._save_json_document(self._bucket_metadata_key(str(bucket.get("bucket_name") or bucket.get("name"))), bucket)

    def _load_object_metadata(self, bucket_name: str, object_key: str) -> Optional[Dict[str, Any]]:
        """Internal helper to load the object metadata."""
        return self._load_json_document(self._object_metadata_key(bucket_name, object_key))

    def _save_object_metadata(self, bucket_name: str, object_key: str, metadata: Mapping[str, Any]) -> None:
        """Internal helper to save the object metadata."""
        self._save_json_document(self._object_metadata_key(bucket_name, object_key), metadata)

    def _resolve_caller(self, input_data: Mapping[str, Any]) -> Dict[str, str]:
        """Internal helper to resolve the caller."""
        caller = input_data.get("_caller") if isinstance(input_data.get("_caller"), Mapping) else {}
        agent_id = str(
            caller.get("agent_id")
            or caller.get("pit_id")
            or input_data.get("requester_agent_id")
            or input_data.get("agent_id")
            or self.agent_id
            or self.name
        ).strip()
        agent_name = str(
            caller.get("agent_name")
            or input_data.get("requester_agent_name")
            or input_data.get("agent_name")
            or self.name
        ).strip()
        return {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "auth_mode": str(caller.get("auth_mode") or "").strip(),
        }

    @staticmethod
    def _check_bucket_access(bucket: Mapping[str, Any], caller: Mapping[str, Any]) -> None:
        """Internal helper for check bucket access."""
        visibility = str(bucket.get("visibility") or "private").strip().lower()
        if visibility == "public":
            return
        owner_agent_id = str(bucket.get("owner_agent_id") or "").strip()
        owner_agent_name = str(bucket.get("owner_agent_name") or "").strip()
        caller_agent_id = str(caller.get("agent_id") or "").strip()
        caller_agent_name = str(caller.get("agent_name") or "").strip()
        if owner_agent_id and caller_agent_id and owner_agent_id == caller_agent_id:
            return
        if owner_agent_name and caller_agent_name and owner_agent_name == caller_agent_name:
            return
        raise PermissionError(f"Bucket '{bucket.get('bucket_name') or bucket.get('name')}' is private to its creating agent.")

    def _resolve_object_payload(self, input_data: Mapping[str, Any]) -> tuple[bytes, str, str]:
        """Internal helper to resolve the object payload."""
        provided = [
            field_name
            for field_name in ("text", "data", "base64_data")
            if input_data.get(field_name) is not None
        ]
        if not provided:
            raise ValueError("object_save requires one of text, data, or base64_data.")
        if len(provided) > 1:
            raise ValueError("Provide only one of text, data, or base64_data.")

        if "text" in provided:
            payload = str(input_data.get("text") or "").encode("utf-8")
            content_type = str(input_data.get("content_type") or "text/plain; charset=utf-8").strip()
            return payload, content_type, "text"

        if "data" in provided:
            payload = json.dumps(input_data.get("data"), ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
            content_type = str(input_data.get("content_type") or "application/json").strip()
            return payload, content_type, "json"

        try:
            payload = base64.b64decode(str(input_data.get("base64_data") or ""), validate=True)
        except Exception as exc:
            raise ValueError("base64_data must be valid base64.") from exc
        object_key = _normalize_object_key(input_data.get("object_key"))
        inferred_content_type = mimetypes.guess_type(object_key)[0] or "application/octet-stream"
        content_type = str(input_data.get("content_type") or inferred_content_type).strip()
        return payload, content_type, "base64"

    def _handle_bucket_create(self, input_data: Mapping[str, Any]) -> Dict[str, Any]:
        """Internal helper to handle the bucket create."""
        bucket_name = _normalize_bucket_name(input_data.get("bucket_name"))
        visibility = _coerce_visibility(input_data.get("visibility"))
        if self._load_bucket(bucket_name):
            raise ValueError(f"Bucket '{bucket_name}' already exists.")

        caller = self._resolve_caller(input_data)
        bucket = {
            "status": "created",
            "bucket_name": bucket_name,
            "visibility": visibility,
            "owner_agent_id": caller.get("agent_id"),
            "owner_agent_name": caller.get("agent_name"),
            "created_at": _utcnow_iso(),
            "updated_at": _utcnow_iso(),
            "storage_backend": self.backend.backend_type,
        }
        self._save_bucket(bucket)
        return bucket

    def _handle_list_bucket(self, input_data: Mapping[str, Any]) -> Dict[str, Any]:
        """Internal helper to handle the list bucket."""
        caller = self._resolve_caller(input_data)
        visibility_filter = str(input_data.get("visibility") or "all").strip().lower()
        if visibility_filter not in {"all", "private", "public"}:
            raise ValueError("visibility must be one of all, private, or public.")
        limit = _coerce_limit(input_data.get("limit"), default=200)

        buckets: List[Dict[str, Any]] = []
        for relative_key in self.backend.list_keys("__meta__/buckets"):
            document = self._load_json_document(relative_key)
            if not document:
                continue
            bucket_name = str(document.get("bucket_name") or document.get("name") or "").strip()
            if not bucket_name:
                continue
            visibility = str(document.get("visibility") or "private").strip().lower()
            if visibility_filter != "all" and visibility != visibility_filter:
                continue
            try:
                self._check_bucket_access(document, caller)
            except PermissionError:
                continue
            buckets.append(
                {
                    "bucket_name": bucket_name,
                    "visibility": visibility,
                    "owner_agent_id": document.get("owner_agent_id"),
                    "owner_agent_name": document.get("owner_agent_name"),
                    "created_at": document.get("created_at"),
                    "updated_at": document.get("updated_at"),
                    "storage_backend": document.get("storage_backend"),
                }
            )

        buckets.sort(key=lambda entry: str(entry.get("bucket_name") or ""))
        buckets = buckets[:limit]
        return {
            "visibility_filter": visibility_filter,
            "returned_count": len(buckets),
            "buckets": buckets,
        }

    def _handle_bucket_browse(self, input_data: Mapping[str, Any]) -> Dict[str, Any]:
        """Internal helper to handle the bucket browse."""
        bucket_name = _normalize_bucket_name(input_data.get("bucket_name"))
        bucket = self._load_bucket(bucket_name)
        if not bucket:
            raise ValueError(f"Bucket '{bucket_name}' does not exist.")
        self._check_bucket_access(bucket, self._resolve_caller(input_data))

        requested_prefix = str(input_data.get("prefix") or "").strip().strip("/")
        limit = _coerce_limit(input_data.get("limit"), default=200)
        metadata_prefix = f"__meta__/objects/{bucket_name}"
        objects: List[Dict[str, Any]] = []
        for relative_key in self.backend.list_keys(metadata_prefix):
            document = self._load_json_document(relative_key)
            if not document:
                continue
            object_key = str(document.get("object_key") or "").strip()
            if requested_prefix and not object_key.startswith(requested_prefix):
                continue
            objects.append(
                {
                    "object_key": object_key,
                    "content_type": document.get("content_type"),
                    "size_bytes": document.get("size_bytes"),
                    "etag": document.get("etag"),
                    "created_at": document.get("created_at"),
                    "updated_at": document.get("updated_at"),
                    "metadata": dict(document.get("metadata") or {}),
                }
            )
        objects.sort(key=lambda entry: str(entry.get("object_key") or ""))
        objects = objects[:limit]
        return {
            "bucket_name": bucket_name,
            "visibility": bucket.get("visibility"),
            "owner_agent_id": bucket.get("owner_agent_id"),
            "owner_agent_name": bucket.get("owner_agent_name"),
            "prefix": requested_prefix,
            "returned_count": len(objects),
            "objects": objects,
        }

    def _handle_object_save(self, input_data: Mapping[str, Any]) -> Dict[str, Any]:
        """Internal helper to handle the object save."""
        bucket_name = _normalize_bucket_name(input_data.get("bucket_name"))
        object_key = _normalize_object_key(input_data.get("object_key"))
        bucket = self._load_bucket(bucket_name)
        if not bucket:
            raise ValueError(f"Bucket '{bucket_name}' does not exist.")
        caller = self._resolve_caller(input_data)
        self._check_bucket_access(bucket, caller)

        payload, content_type, payload_format = self._resolve_object_payload(input_data)
        metadata = dict(input_data.get("metadata") or {}) if isinstance(input_data.get("metadata"), Mapping) else {}
        existing = self._load_object_metadata(bucket_name, object_key) or {}
        timestamp = _utcnow_iso()
        document = {
            "status": "saved",
            "bucket_name": bucket_name,
            "object_key": object_key,
            "content_type": content_type,
            "payload_format": payload_format,
            "size_bytes": len(payload),
            "etag": hashlib.md5(payload).hexdigest(),
            "visibility": bucket.get("visibility"),
            "owner_agent_id": bucket.get("owner_agent_id"),
            "owner_agent_name": bucket.get("owner_agent_name"),
            "created_at": existing.get("created_at") or timestamp,
            "updated_at": timestamp,
            "last_writer_agent_id": caller.get("agent_id"),
            "last_writer_agent_name": caller.get("agent_name"),
            "metadata": metadata,
        }
        self.backend.write_bytes(self._object_data_key(bucket_name, object_key), payload, content_type=content_type)
        self._save_object_metadata(bucket_name, object_key, document)
        return document

    def _handle_object_load(self, input_data: Mapping[str, Any]) -> Dict[str, Any]:
        """Internal helper to handle the object load."""
        bucket_name = _normalize_bucket_name(input_data.get("bucket_name"))
        object_key = _normalize_object_key(input_data.get("object_key"))
        bucket = self._load_bucket(bucket_name)
        if not bucket:
            raise ValueError(f"Bucket '{bucket_name}' does not exist.")
        self._check_bucket_access(bucket, self._resolve_caller(input_data))

        metadata = self._load_object_metadata(bucket_name, object_key)
        payload = self.backend.read_bytes(self._object_data_key(bucket_name, object_key))
        if metadata is None or payload is None:
            raise ValueError(f"Object '{object_key}' does not exist in bucket '{bucket_name}'.")

        response_format = str(input_data.get("response_format") or "auto").strip().lower()
        if response_format not in {"auto", "json", "text", "base64"}:
            raise ValueError("response_format must be one of auto, json, text, or base64.")

        result = {
            "bucket_name": bucket_name,
            "object_key": object_key,
            "content_type": metadata.get("content_type"),
            "size_bytes": metadata.get("size_bytes"),
            "etag": metadata.get("etag"),
            "created_at": metadata.get("created_at"),
            "updated_at": metadata.get("updated_at"),
            "metadata": dict(metadata.get("metadata") or {}),
        }

        payload_format = str(metadata.get("payload_format") or "").strip().lower()
        content_type = str(metadata.get("content_type") or "").strip().lower()
        if response_format == "json" or (response_format == "auto" and (payload_format == "json" or "json" in content_type)):
            result["data"] = json.loads(payload.decode("utf-8"))
            return result

        if response_format == "text" or (response_format == "auto" and (payload_format == "text" or content_type.startswith("text/"))):
            result["text"] = payload.decode("utf-8")
            return result

        if response_format == "auto":
            try:
                result["text"] = payload.decode("utf-8")
                return result
            except UnicodeDecodeError:
                pass

        result["base64_data"] = base64.b64encode(payload).decode("ascii")
        return result

    def fetch_pulse_payload(self, pulse_name: str, input_data: Dict[str, Any], pulse_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch the pulse payload."""
        requested_name = str(pulse_name or pulse_definition.get("name") or "").strip().lower()
        handlers = {
            "bucket_create": self._handle_bucket_create,
            "create_bucket": self._handle_bucket_create,
            "list_bucket": self._handle_list_bucket,
            "bucket_list": self._handle_list_bucket,
            "list_buckets": self._handle_list_bucket,
            "bucket_browse": self._handle_bucket_browse,
            "browse_bucket": self._handle_bucket_browse,
            "object_save": self._handle_object_save,
            "save_object": self._handle_object_save,
            "object_put": self._handle_object_save,
            "object_load": self._handle_object_load,
            "load_object": self._handle_object_load,
            "object_get": self._handle_object_load,
        }
        handler = handlers.get(requested_name)
        if handler is None:
            return {"error": f"Unsupported storage pulse '{pulse_name}'."}
        try:
            return handler(dict(input_data or {}))
        except Exception as exc:
            return {"error": str(exc)}
