"""
API pulser implementation for the Pulsers area.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, these modules implement pulse sources for
APIs, files, bosses, MCP tools, and path-based workflows.

Core types exposed here include `APIsPulser`, which carry the main behavior or state
managed by this module.
"""

import json
import logging
import os
import socket
from pathlib import Path
from typing import Any, Dict, Mapping
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from phemacast.agents.pulser import Pulser, _resolve_path, validate_pulser_config_test_parameters
from prompits.core.pit import PitAddress

logger = logging.getLogger(__name__)

class APIsPulser(Pulser):
    """
    A generic Pulser implementation that fetches pulse payloads from external REST APIs.
    The APIs and methods are defined entirely within the pulser's configuration.

    Supports a top-level `apis` registry so a single pulser can route different
    supported pulses to different upstream API endpoints and credentials.
    """

    def __init__(self, *args, **kwargs):
        """Initialize the ap is pulser."""
        super().__init__(*args, **kwargs)
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        self.templates = Jinja2Templates(directory=template_dir)
        self.last_fetch_debug: Dict[str, Any] = {}
        self._setup_api_pulser_routes()

    def _setup_api_pulser_routes(self) -> None:
        """Internal helper to set up the API pulser routes."""
        @self.app.get("/")
        async def api_pulser_ui(request: Request):
            """Route handler for GET /."""
            return self.templates.TemplateResponse(
                request=request,
                name="phemacast/pulsers/templates/api_pulser_editor.html",
                context={
                    "agent_name": self.agent_card.get("name", self.name),
                    "config_path": str(self.config_path) if self.config_path else "",
                },
            )

        @self.app.get("/api/config")
        async def get_api_pulser_config():
            """Route handler for GET /api/config."""
            config = await run_in_threadpool(self._load_config_document)
            return {
                "status": "success",
                "config": config,
                "config_path": str(self.config_path) if self.config_path else None,
            }

        @self.app.get("/api/plaza/pulses")
        async def get_plaza_pulses(search: str = ""):
            """Route handler for GET /api/plaza/pulses."""
            rows = await run_in_threadpool(self._search_plaza_directory, pit_type="Pulse", name=search.strip() or None)
            pulses = []
            for row in rows:
                card = row.get("card") or {}
                meta = card.get("meta") or {}
                pit_address = PitAddress.from_value(card.get("pit_address"))
                pulses.append(
                    {
                        "pit_address": pit_address.to_ref(reference_plaza=self.plaza_url),
                        "pit_id": pit_address.pit_id,
                        "name": card.get("name") or row.get("name"),
                        "description": card.get("description") or row.get("description") or meta.get("description", ""),
                        "tags": list(card.get("tags") or meta.get("tags") or []),
                        "output_schema": meta.get("output_schema") if isinstance(meta.get("output_schema"), dict) else {},
                    }
                )
            return {"status": "success", "pulses": pulses}

        @self.app.post("/api/config")
        async def save_api_pulser_config(request: Request):
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
        async def test_api_pulser_pulse(request: Request):
            """Exercise the test_api_pulser_pulse regression scenario."""
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
                raw_payload = runner.fetch_pulse_payload(str(pulse_name), params, pulse_definition) or {}
                mapping_rules = pulse_definition.get("mapping") or runner.mapping
                if isinstance(raw_payload, dict) and raw_payload.get("error"):
                    result = raw_payload
                elif mapping_rules:
                    result = runner.transform(
                        raw_payload,
                        pulse_name=str(pulse_name),
                        pulse_address=pulse_definition.get("pulse_address"),
                        output_schema=pulse_definition.get("output_schema"),
                        mapping=mapping_rules,
                    )
                else:
                    result = raw_payload
                return runner, pulse_definition, raw_payload, mapping_rules, result

            try:
                runner, pulse_definition, raw_payload, mapping_rules, result = await run_in_threadpool(_run_test_sync)
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
                    "fetch": dict(runner.last_fetch_debug or {}),
                    "mapping": mapping_rules,
                    "raw_payload": raw_payload,
                    "result": result,
                }
            return response

    def _load_config_document(self) -> Dict[str, Any]:
        """Internal helper to load the config document."""
        if self.config_path and self.config_path.exists():
            with self.config_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            self.raw_config = dict(loaded)
            return self._build_editor_config_document(loaded)
        return self._build_editor_config_document(self.raw_config or self._synthesize_runtime_config())

    def _save_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to save the config document."""
        if not self.config_path:
            raise HTTPException(status_code=400, detail="This APIsPulser was not started from a config file.")

        normalized = self._normalize_config_document(config)
        try:
            validate_pulser_config_test_parameters(normalized)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(normalized, indent=4), encoding="utf-8")

        self.raw_config = dict(normalized)
        self.apply_pulser_config(normalized)
        return self._build_editor_config_document(normalized)

    def _normalize_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the config document."""
        document = dict(config or {})
        document.setdefault("name", self.agent_card.get("name", self.name))
        document.setdefault("type", "phemacast.pulsers.api_pulser.APIsPulser")
        document.setdefault("host", self.host)
        document.setdefault("port", self.port)
        if self.plaza_url and "plaza_url" not in document:
            document["plaza_url"] = self.plaza_url
        document.setdefault("role", "pulser")
        document.setdefault("description", self.agent_card.get("description", ""))
        document["tags"] = list(document.get("tags") or [])
        has_api_registry = any(key in document for key in ("api_keys", "credentials"))
        if has_api_registry:
            api_registry = document.get("api_keys")
            if api_registry is None:
                api_registry = document.get("credentials")
            normalized_registry = self._normalize_api_key_registry(api_registry)
            document["api_keys"] = normalized_registry
            if "credentials" in document:
                document["credentials"] = list(normalized_registry)
        elif any(key in self.raw_config for key in ("api_keys", "credentials")):
            api_registry = self.raw_config.get("api_keys")
            if api_registry is None:
                api_registry = self.raw_config.get("credentials")
            document["api_keys"] = self._normalize_api_key_registry(api_registry)

        api_registry_value = (
            document.get("apis")
            if "apis" in document
            else document.get("api_sources")
            if "api_sources" in document
            else document.get("api_endpoints")
        )
        if api_registry_value is not None:
            document["apis"] = self._normalize_api_registry(api_registry_value)
        elif any(key in self.raw_config for key in ("apis", "api_sources", "api_endpoints")):
            raw_registry = (
                self.raw_config.get("apis")
                or self.raw_config.get("api_sources")
                or self.raw_config.get("api_endpoints")
            )
            document["apis"] = self._normalize_api_registry(raw_registry)

        document["supported_pulses"] = [
            self._normalize_config_pulse(pulse)
            for pulse in (document.get("supported_pulses") or self.supported_pulses or [])
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
        if self.supported_pulses:
            document["supported_pulses"] = [dict(pulse) for pulse in self.supported_pulses]
        return document

    @staticmethod
    def _normalize_config_pulse(pulse: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the config pulse."""
        normalized = dict(pulse)
        pulse_address = PitAddress.from_value(normalized.get("pulse_address"))
        if pulse_address.pit_id:
            normalized["pulse_address"] = pulse_address.to_ref()
            normalized.pop("output_schema", None)
        return normalized

    def _synthesize_runtime_config(self) -> Dict[str, Any]:
        """Internal helper to return the synthesize runtime config."""
        runtime_api_registry = self.raw_config.get("api_keys")
        if runtime_api_registry is None:
            runtime_api_registry = self.raw_config.get("credentials")
        runtime_apis = self.raw_config.get("apis")
        if runtime_apis is None:
            runtime_apis = self.config.get("apis")
        return {
            "name": self.agent_card.get("name", self.name),
            "type": "phemacast.pulsers.api_pulser.APIsPulser",
            "host": self.host,
            "port": self.port,
            "plaza_url": self.plaza_url,
            "role": self.agent_card.get("role", "pulser"),
            "description": self.agent_card.get("description", ""),
            "tags": list(self.agent_card.get("tags") or []),
            "api_key": self.raw_config.get("api_key"),
            "api_keys": self._normalize_api_key_registry(runtime_api_registry),
            "credentials": self._normalize_api_key_registry(self.raw_config.get("credentials")),
            "apis": self._normalize_api_registry(runtime_apis),
            "supported_pulses": [dict(pulse) for pulse in self.supported_pulses],
            "pools": list(self.raw_config.get("pools") or []),
            "practices": list(self.raw_config.get("practices") or []),
        }

    @staticmethod
    def _normalize_api_key_registry(value: Any) -> list[Dict[str, Any]]:
        """Internal helper to normalize the API key registry."""
        if value is None:
            return []
        entries: list[Dict[str, Any]] = []
        if isinstance(value, dict):
            for key_id, entry in value.items():
                if isinstance(entry, dict):
                    normalized = dict(entry)
                    normalized.setdefault("id", str(key_id))
                else:
                    normalized = {"id": str(key_id), "value": entry}
                entries.append(normalized)
            return entries
        if isinstance(value, list):
            for entry in value:
                if not isinstance(entry, dict):
                    continue
                normalized = dict(entry)
                if normalized.get("id"):
                    entries.append(normalized)
            return entries
        return []

    @classmethod
    def _normalize_api_registry(cls, value: Any) -> list[Dict[str, Any]]:
        """Internal helper to normalize the API registry."""
        if value is None:
            return []

        entries: list[Dict[str, Any]] = []
        if isinstance(value, dict):
            for api_id, entry in value.items():
                if isinstance(entry, dict):
                    normalized = dict(entry)
                    normalized.setdefault("id", str(api_id))
                else:
                    normalized = {"id": str(api_id), "base_url": str(entry)}
                entries.append(normalized)
        elif isinstance(value, list):
            for entry in value:
                if not isinstance(entry, dict):
                    continue
                normalized = dict(entry)
                if normalized.get("id"):
                    entries.append(normalized)

        normalized_entries: list[Dict[str, Any]] = []
        for entry in entries:
            normalized = cls._normalize_api_source(entry)
            if normalized.get("id"):
                normalized_entries.append(normalized)
        return normalized_entries

    @staticmethod
    def _normalize_api_source(entry: Mapping[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the API source."""
        normalized = dict(entry)
        normalized["id"] = str(normalized.get("id") or "").strip()
        if "headers" in normalized and not isinstance(normalized.get("headers"), dict):
            normalized["headers"] = {}
        if "method" in normalized and normalized.get("method") is not None:
            normalized["method"] = str(normalized["method"]).upper()

        api_key_id = normalized.get("api_key_id")
        if not api_key_id:
            api_key_id = normalized.get("credential_id") or normalized.get("credentials_id")
        if api_key_id:
            normalized["api_key_id"] = str(api_key_id)

        if "api_key" not in normalized:
            credential_value = normalized.get("credential")
            if credential_value is None:
                credential_value = normalized.get("credentials")
            if credential_value is not None:
                normalized["api_key"] = credential_value

        if "api_key_header" not in normalized and normalized.get("credential_header"):
            normalized["api_key_header"] = normalized.get("credential_header")
        if "api_key_prefix" not in normalized and normalized.get("credential_prefix") is not None:
            normalized["api_key_prefix"] = normalized.get("credential_prefix")
        if "api_key_param" not in normalized and normalized.get("credential_param"):
            normalized["api_key_param"] = normalized.get("credential_param")
        return normalized

    @staticmethod
    def _deep_merge_dicts(base: Dict[str, Any], overlay: Mapping[str, Any]) -> Dict[str, Any]:
        """Internal helper for deep merge dicts."""
        merged = dict(base)
        for key, value in overlay.items():
            if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
                merged[key] = APIsPulser._deep_merge_dicts(dict(merged[key]), value)
            elif isinstance(value, list):
                merged[key] = list(value)
            else:
                merged[key] = value
        return merged

    @staticmethod
    def _resolve_api_key_value(value: Any) -> str | None:
        """Internal helper to resolve the API key value."""
        if value is None:
            return None

        if isinstance(value, dict):
            env_name = value.get("env") or value.get("name")
            if env_name:
                return os.getenv(str(env_name)) or None
            literal = value.get("value")
            if literal is not None:
                return str(literal)
            return None

        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                return None
            if trimmed.startswith("env:"):
                return os.getenv(trimmed[4:].strip()) or None
            if trimmed.startswith("${") and trimmed.endswith("}"):
                return os.getenv(trimmed[2:-1].strip()) or None
            return trimmed

        return str(value)

    def _lookup_registered_api_key(self, api_key_id: Any) -> Dict[str, Any] | None:
        """Internal helper to look up the registered API key."""
        if not api_key_id:
            return None
        registries = [
            self.config.get("api_keys"),
            self.config.get("credentials"),
            self.raw_config.get("api_keys"),
            self.raw_config.get("credentials"),
        ]
        for registry in registries:
            for entry in self._normalize_api_key_registry(registry):
                if str(entry.get("id")) == str(api_key_id):
                    return entry
        return None

    def _lookup_api_source(self, api_id: Any) -> Dict[str, Any] | None:
        """Internal helper to look up the API source."""
        if not api_id:
            return None
        registries = [
            self.config.get("apis"),
            self.config.get("api_sources"),
            self.config.get("api_endpoints"),
            self.raw_config.get("apis"),
            self.raw_config.get("api_sources"),
            self.raw_config.get("api_endpoints"),
        ]
        for registry in registries:
            for entry in self._normalize_api_registry(registry):
                if str(entry.get("id")) == str(api_id):
                    return entry
        return None

    @staticmethod
    def _append_query_param(url: str, name: str, value: str) -> str:
        """Internal helper to append the query param."""
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query[str(name)] = value
        return urlunsplit(parts._replace(query=urlencode(query)))

    @staticmethod
    def _is_sensitive_key(name: str) -> bool:
        """Return whether the value is a sensitive key."""
        key = str(name).strip().lower()
        return any(token in key for token in ("auth", "token", "secret", "key"))

    def _redact_headers(self, headers: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper for redact headers."""
        redacted: Dict[str, Any] = {}
        for key, value in (headers or {}).items():
            redacted[str(key)] = "***redacted***" if self._is_sensitive_key(str(key)) else value
        return redacted

    def _redact_url(self, url: str) -> str:
        """Internal helper to return the redact URL."""
        parts = urlsplit(url)
        query_items = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            query_items.append((key, "***redacted***" if self._is_sensitive_key(key) else value))
        return urlunsplit(parts._replace(query=urlencode(query_items)))

    @staticmethod
    def _apply_input_templates(value: Any, input_data: Dict[str, Any]) -> str:
        """Internal helper for apply input templates."""
        rendered = str(value or "")
        for key, item in (input_data or {}).items():
            rendered = rendered.replace(f"{{{key}}}", str(item))
        return rendered

    @staticmethod
    def _join_base_and_path(base_url: str, path: str) -> str:
        """Internal helper to return the join base and path."""
        base = str(base_url or "").strip()
        endpoint = str(path or "").strip()
        if not base:
            return endpoint
        if not endpoint:
            return base
        if endpoint.lower().startswith(("http://", "https://")):
            return endpoint
        if base.endswith("/") and endpoint.startswith("/"):
            return f"{base[:-1]}{endpoint}"
        if not base.endswith("/") and not endpoint.startswith("/"):
            return f"{base}/{endpoint}"
        return f"{base}{endpoint}"

    def _build_api_url_template(self, api_config: Mapping[str, Any]) -> str:
        """Internal helper to build the API URL template."""
        url_template = api_config.get("url")
        if url_template:
            return str(url_template)

        base_url = api_config.get("base_url") or api_config.get("base")
        endpoint = api_config.get("path")
        if endpoint is None:
            endpoint = api_config.get("endpoint")
        if endpoint is None:
            endpoint = api_config.get("route")

        if endpoint and str(endpoint).lower().startswith(("http://", "https://")):
            return str(endpoint)
        if base_url or endpoint:
            return self._join_base_and_path(str(base_url or ""), str(endpoint or ""))
        return ""

    def _resolve_effective_api_config(self, pulse_definition: Dict[str, Any]) -> tuple[Dict[str, Any], str | None, str | None]:
        """Internal helper to resolve the effective API config."""
        pulse_api = pulse_definition.get("api")
        if not isinstance(pulse_api, Mapping):
            return {}, None, "Pulse API config must be a JSON object."

        source_id = pulse_api.get("api_id") or pulse_api.get("source_id")
        source = None
        if source_id:
            source = self._lookup_api_source(source_id)
            if source is None:
                return {}, str(source_id), f"Unknown api_id '{source_id}' in pulse API config."

        merged: Dict[str, Any] = {}
        global_api = self.config.get("api")
        if isinstance(global_api, Mapping):
            merged = self._deep_merge_dicts(merged, global_api)
        if source is not None:
            merged = self._deep_merge_dicts(merged, source)
        merged = self._deep_merge_dicts(merged, pulse_api)
        merged = self._normalize_api_source(merged)
        if source_id and not merged.get("api_id"):
            merged["api_id"] = str(source_id)
        return merged, str(source_id) if source_id else None, None

    def _resolve_api_key_binding(self, api_config: Dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
        """Internal helper to resolve the API key binding."""
        inline_value = api_config.get("api_key")
        if inline_value is None:
            inline_value = api_config.get("credential")
        inline_header = api_config.get("api_key_header") or api_config.get("credential_header")
        inline_prefix = api_config.get("api_key_prefix")
        if inline_prefix is None:
            inline_prefix = api_config.get("credential_prefix")
        inline_param = api_config.get("api_key_param") or api_config.get("credential_param")
        if inline_value is not None:
            return (
                self._resolve_api_key_value(inline_value),
                str(inline_header) if inline_header else "Authorization",
                inline_prefix,
                str(inline_param) if inline_param else None,
            )

        registry_id = api_config.get("api_key_id") or api_config.get("credential_id") or api_config.get("credentials_id")
        registry_entry = self._lookup_registered_api_key(registry_id)
        if registry_entry is not None:
            return (
                self._resolve_api_key_value(registry_entry.get("api_key", registry_entry)),
                str(inline_header or registry_entry.get("api_key_header") or registry_entry.get("header") or "Authorization"),
                inline_prefix if inline_prefix is not None else registry_entry.get("api_key_prefix", registry_entry.get("prefix")),
                str(inline_param or registry_entry.get("api_key_param") or registry_entry.get("param")) if (inline_param or registry_entry.get("api_key_param") or registry_entry.get("param")) else None,
            )

        return (
            self._resolve_api_key_value(self.config.get("api_key")),
            str(inline_header) if inline_header else "Authorization",
            inline_prefix,
            str(inline_param or self.config.get("api_key_param")) if (inline_param or self.config.get("api_key_param")) else None,
        )

    @staticmethod
    def _normalize_fetch_error(exc: Exception) -> str:
        """Internal helper to normalize the fetch error."""
        if isinstance(exc, socket.gaierror):
            return "DNS resolution failed for the upstream API host. Outbound internet/DNS may be unavailable."
        cause = getattr(exc, "__cause__", None)
        if isinstance(cause, socket.gaierror):
            return "DNS resolution failed for the upstream API host. Outbound internet/DNS may be unavailable."
        context = getattr(exc, "__context__", None)
        if isinstance(context, socket.gaierror):
            return "DNS resolution failed for the upstream API host. Outbound internet/DNS may be unavailable."
        text = str(exc)
        if "nodename nor servname provided" in text or "Name or service not known" in text:
            return "DNS resolution failed for the upstream API host. Outbound internet/DNS may be unavailable."
        return text

    def fetch_pulse_payload(self, pulse_name: str, input_data: Dict[str, Any], pulse_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch payload from an external API defined in pulse_definition."""
        self.last_fetch_debug = {
            "pulse_name": pulse_name,
            "input_data": dict(input_data or {}),
        }
        api_config, api_id, api_error = self._resolve_effective_api_config(pulse_definition)
        if api_error:
            self.last_fetch_debug["error"] = api_error
            return {"error": api_error}

        url_template = self._build_api_url_template(api_config)
        if not url_template:
            return {"error": f"No API URL defined for pulse '{pulse_name}'"}

        # Naive template substitution.
        url = self._apply_input_templates(url_template, input_data)
        
        method = api_config.get("method", "GET").upper()
        headers = dict(api_config.get("headers", {}))
        api_key, api_key_header, api_key_prefix, api_key_param = self._resolve_api_key_binding(api_config)
        if not api_key:
            registry_id = api_config.get("api_key_id") or api_config.get("credential_id") or api_config.get("credentials_id")
            if registry_id:
                registry_entry = self._lookup_registered_api_key(registry_id) or {}
                source = registry_entry.get("env") or registry_entry.get("id") or registry_id
                message = f"Missing API key value for registry '{registry_id}'"
                if source:
                    message += f" ({source})"
                self.last_fetch_debug["error"] = message
                return {"error": message}
            if api_config.get("api_key") is not None:
                message = f"Missing inline API key value for pulse '{pulse_name}'"
                self.last_fetch_debug["error"] = message
                return {"error": message}
        if api_key and api_key_param:
            url = self._append_query_param(url, api_key_param, api_key)
        elif api_key and api_key_header and api_key_header.lower() not in {k.lower() for k in headers}:
            if api_key_prefix is None:
                api_key_prefix = "Bearer " if api_key_header.lower() == "authorization" else ""
            headers[api_key_header] = f"{api_key_prefix}{api_key}"
        if "user-agent" not in {k.lower() for k in headers}:
            headers["User-Agent"] = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

        self.last_fetch_debug["request"] = {
            "method": method,
            "url": self._redact_url(url),
            "headers": self._redact_headers(headers),
            "root_path": api_config.get("root_path"),
            "api_id": api_id,
        }
        
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.request(method, url, headers=headers)
                response.raise_for_status()
                data = response.json()
                self.last_fetch_debug["response"] = {
                    "status_code": getattr(response, "status_code", None),
                    "json": data,
                }
        except Exception as e:
            message = self._normalize_fetch_error(e)
            self.logger.error(f"Error fetching API for pulse '{pulse_name}': {message}")
            self.last_fetch_debug["error"] = message
            return {"error": message}

        # Optional: extract root to avoid dict indexing issues mapping on arrays
        root_path = api_config.get("root_path")
        if root_path:
            resolved_root_path = self._apply_input_templates(root_path, input_data)
            current = _resolve_path(data, resolved_root_path)
            if current is None:
                self.last_fetch_debug["extracted_payload"] = {"error": f"Could not extract root_path {resolved_root_path} from API response"}
                return {"error": f"Could not extract root_path {resolved_root_path} from API response"}
            data = current

        if isinstance(data, list):
            data = {
                "items": data,
                "_input": dict(input_data or {}),
            }
        elif isinstance(data, dict):
            data.setdefault("_input", dict(input_data or {}))
        else:
            self.last_fetch_debug["extracted_payload"] = {"error": "API response root is not a dictionary or list, cannot apply mapping rules"}
            return {"error": "API response root is not a dictionary or list, cannot apply mapping rules"}

        self.last_fetch_debug["extracted_payload"] = data
        return data
