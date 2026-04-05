"""
System pulser implementation for the Pulsers area.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, these modules implement pulse sources for
APIs, files, bosses, MCP tools, and path-based workflows.

Core types exposed here include `SystemPulser`, which carry the main behavior or state
managed by this module.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import unquote, urlparse

import requests

from phemacast.agents.pulser import ConfigInput, _read_config
from phemacast.pulsers.system_storage_pulser import (
    SYSTEM_PARTY,
    SystemStoragePulser,
    _default_supported_pulses as _default_storage_supported_pulses,
    boto3,
)


def _default_file_pulse() -> Dict[str, Any]:
    """Internal helper to return the default file pulse."""
    return {
        "name": "file",
        "aliases": ["read_file", "load_file", "File"],
        "pulse_address": "plaza://pulse/file",
        "description": "Load file content from an HTTP(S) URL or a local filesystem path.",
        "party": SYSTEM_PARTY,
        "tags": ["system", "file", "url", "local-path"],
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "HTTP(S) URL or file:// URL to load.",
                },
                "local_path": {
                    "type": "string",
                    "description": "Absolute or relative filesystem path to load.",
                },
            },
            "oneOf": [
                {"required": ["url"]},
                {"required": ["local_path"]},
            ],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "format": {
                    "type": "string",
                    "enum": ["json", "text", "base64"],
                    "description": "Normalized representation used for content.",
                },
                "content": {
                    "type": ["object", "array", "string", "number", "boolean", "null"],
                    "description": "Parsed JSON value, UTF-8 text, or base64-encoded binary payload.",
                },
            },
            "required": ["format", "content"],
        },
        "test_data": {"local_path": "README.md"},
    }


def _default_supported_pulses() -> List[Dict[str, Any]]:
    """Internal helper to return the default supported pulses."""
    return [_default_file_pulse(), *_default_storage_supported_pulses()]


class SystemPulser(SystemStoragePulser):
    """Pulser that exposes system file loading plus storage operations."""

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
        """Initialize the system pulser."""
        config_input = config if config is not None else config_path
        config_data = _read_config(config_input) if config_input is not None else {}
        self.request_timeout_sec = self._coerce_timeout(config_data.get("request_timeout_sec"), default=30.0)

        card = dict(agent_card or config_data.get("agent_card") or {})
        resolved_name = str(name or config_data.get("name") or card.get("name") or "SystemPulser")
        card.setdefault("name", resolved_name)
        card["party"] = str(config_data.get("party") or card.get("party") or SYSTEM_PARTY).strip() or SYSTEM_PARTY
        card["role"] = str(config_data.get("role") or card.get("role") or "pulser")
        card["description"] = str(
            config_data.get("description")
            or card.get("description")
            or "System pulser that combines local file loading with storage bucket and object operations."
        )
        card["tags"] = self._merge_tags(
            card.get("tags"),
            config_data.get("tags"),
            ["system", "file", "url", "storage", "pulser"],
        )
        meta = dict(card.get("meta") or {})
        meta.setdefault("party", card["party"])
        meta["request_timeout_sec"] = self.request_timeout_sec
        card["meta"] = meta

        resolved_supported_pulses = supported_pulses or config_data.get("supported_pulses") or _default_supported_pulses()

        super().__init__(
            config=config_input,
            config_path=config_path,
            name=resolved_name,
            host=host,
            port=port,
            plaza_url=plaza_url,
            agent_card=card,
            pool=pool,
            supported_pulses=resolved_supported_pulses,
            auto_register=auto_register,
        )

    @staticmethod
    def _coerce_timeout(value: Any, *, default: float) -> float:
        """Internal helper to coerce the timeout."""
        try:
            timeout = float(value if value is not None else default)
        except (TypeError, ValueError):
            return default
        return timeout if timeout > 0 else default

    def _sync_storage_card_metadata(self, party: Optional[str] = None) -> None:
        """Internal helper to synchronize system and storage metadata."""
        super()._sync_storage_card_metadata(party=party)
        meta = dict(self.agent_card.get("meta") or {})
        meta["request_timeout_sec"] = self.request_timeout_sec
        self.agent_card["meta"] = meta

    def _apply_runtime_document(self, config: Mapping[str, Any]) -> None:
        """Internal helper for apply runtime document."""
        document = dict(config or {})
        self.request_timeout_sec = self._coerce_timeout(
            document.get("request_timeout_sec"),
            default=self.request_timeout_sec,
        )
        super()._apply_runtime_document(document)

    def _normalize_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the config document."""
        document = super()._normalize_config_document(config)
        document["type"] = "phemacast.pulsers.system_pulser.SystemPulser"
        document["request_timeout_sec"] = self._coerce_timeout(
            document.get("request_timeout_sec"),
            default=self.request_timeout_sec,
        )
        return document

    def _synthesize_runtime_config(self) -> Dict[str, Any]:
        """Internal helper to return the synthesize runtime config."""
        document = super()._synthesize_runtime_config()
        document["type"] = "phemacast.pulsers.system_pulser.SystemPulser"
        document["request_timeout_sec"] = self.request_timeout_sec
        return document

    def _resolve_local_path(self, raw_path: str) -> Path:
        """Resolve a local filesystem path relative to the config when needed."""
        candidate = Path(str(raw_path).strip()).expanduser()
        if not candidate.is_absolute():
            candidate = self._config_root / candidate
        resolved = candidate.resolve()
        if not resolved.exists():
            raise ValueError(f"Local path does not exist: {resolved}")
        if not resolved.is_file():
            raise ValueError(f"Local path is not a file: {resolved}")
        return resolved

    def _select_source(self, input_data: Mapping[str, Any]) -> Tuple[str, str]:
        """Return the requested source type and value."""
        url = str(input_data.get("url") or "").strip()
        local_path = str(
            input_data.get("local_path")
            or input_data.get("path")
            or input_data.get("file_path")
            or ""
        ).strip()
        if url and local_path:
            raise ValueError("Provide either url or local_path, not both.")
        if url:
            return "url", url
        if local_path:
            return "local_path", local_path
        raise ValueError("Either url or local_path is required.")

    def _read_local_file(self, raw_path: str) -> Tuple[bytes, str, str]:
        """Read bytes and content type for a local file."""
        resolved = self._resolve_local_path(raw_path)
        guessed_type = mimetypes.guess_type(str(resolved))[0] or ""
        return resolved.read_bytes(), guessed_type, resolved.name

    def _read_remote_file(self, raw_url: str) -> Tuple[bytes, str, str]:
        """Read bytes and content type for a remote file."""
        parsed = urlparse(raw_url)
        if parsed.scheme == "file":
            file_path = unquote(parsed.path or "")
            if parsed.netloc and parsed.netloc not in {"", "localhost"}:
                file_path = f"//{parsed.netloc}{file_path}"
            return self._read_local_file(file_path)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("url must use http, https, or file schemes.")

        response = requests.get(raw_url, timeout=self.request_timeout_sec)
        if response.status_code >= 400:
            raise ValueError(f"Request failed with status {response.status_code} for {raw_url}.")
        content_type = str(response.headers.get("Content-Type") or "").split(";", 1)[0].strip()
        source_name = Path(unquote(parsed.path or "")).name or "remote-file"
        return response.content, content_type, source_name

    @staticmethod
    def _normalize_content(payload: bytes, *, content_type: str = "", source_name: str = "") -> Dict[str, Any]:
        """Normalize file bytes into json, text, or base64 content."""
        normalized_type = str(content_type or "").strip().lower()
        source_suffix = str(source_name or "").strip().lower()

        try:
            text = payload.decode("utf-8")
        except UnicodeDecodeError:
            text = None

        json_hint = "json" in normalized_type or source_suffix.endswith(".json")
        if text is not None:
            stripped = text.lstrip()
            if json_hint or stripped.startswith("{") or stripped.startswith("["):
                try:
                    return {"format": "json", "content": json.loads(text)}
                except json.JSONDecodeError:
                    pass
            return {"format": "text", "content": text}

        return {"format": "base64", "content": base64.b64encode(payload).decode("ascii")}

    def _handle_file(self, input_data: Mapping[str, Any]) -> Dict[str, Any]:
        """Handle the file pulse."""
        source_type, source_value = self._select_source(input_data)
        if source_type == "url":
            payload, content_type, source_name = self._read_remote_file(source_value)
        else:
            payload, content_type, source_name = self._read_local_file(source_value)
        return self._normalize_content(payload, content_type=content_type, source_name=source_name)

    def fetch_pulse_payload(self, pulse_name: str, input_data: Dict[str, Any], pulse_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch the pulse payload."""
        requested_name = str(pulse_name or pulse_definition.get("name") or "").strip().lower()
        if requested_name in {"file", "read_file", "load_file"}:
            try:
                return self._handle_file(dict(input_data or {}))
            except Exception as exc:
                return {"error": str(exc)}
        return super().fetch_pulse_payload(pulse_name, input_data, pulse_definition)
