import json
import logging
import os
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx
from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from phemacast.agents.pulser import Pulser, _resolve_path
from prompits.core.pit import PitAddress

logger = logging.getLogger(__name__)

class ApiPulser(Pulser):
    """
    A generic Pulser implementation that fetches pulse payloads from external REST APIs.
    The APIs and methods are defined entirely within the pulser's configuration.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        self.templates = Jinja2Templates(directory=template_dir)
        self.last_fetch_debug: Dict[str, Any] = {}
        self._setup_api_pulser_routes()

    def _setup_api_pulser_routes(self) -> None:
        @self.app.get("/")
        async def api_pulser_ui(request: Request):
            return self.templates.TemplateResponse(
                request,
                "phemacast/pulsers/templates/api_pulser_editor.html",
                {
                    "agent_name": self.agent_card.get("name", self.name),
                    "config_path": str(self.config_path) if self.config_path else "",
                },
            )

        @self.app.get("/api/config")
        async def get_api_pulser_config():
            config = await run_in_threadpool(self._load_config_document)
            return {
                "status": "success",
                "config": config,
                "config_path": str(self.config_path) if self.config_path else None,
            }

        @self.app.get("/api/plaza/pulses")
        async def get_plaza_pulses(search: str = ""):
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
        if self.config_path and self.config_path.exists():
            with self.config_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            self.raw_config = dict(loaded)
            return self._build_editor_config_document(loaded)
        return self._build_editor_config_document(self.raw_config or self._synthesize_runtime_config())

    def _save_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        if not self.config_path:
            raise HTTPException(status_code=400, detail="This APIPulser was not started from a config file.")

        normalized = self._normalize_config_document(config)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(normalized, indent=4), encoding="utf-8")

        self.raw_config = dict(normalized)
        self.apply_pulser_config(normalized)
        return self._build_editor_config_document(normalized)

    def _normalize_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        document = dict(config or {})
        document.setdefault("name", self.agent_card.get("name", self.name))
        document.setdefault("type", "phemacast.pulsers.api_pulser.ApiPulser")
        document.setdefault("host", self.host)
        document.setdefault("port", self.port)
        if self.plaza_url and "plaza_url" not in document:
            document["plaza_url"] = self.plaza_url
        document.setdefault("role", "pulser")
        document.setdefault("description", self.agent_card.get("description", ""))
        document["tags"] = list(document.get("tags") or [])
        if "api_keys" in document:
            document["api_keys"] = self._normalize_api_key_registry(document.get("api_keys"))
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
        document = self._normalize_config_document(config)
        if self.supported_pulses:
            document["supported_pulses"] = [dict(pulse) for pulse in self.supported_pulses]
        return document

    @staticmethod
    def _normalize_config_pulse(pulse: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(pulse)
        pulse_address = PitAddress.from_value(normalized.get("pulse_address"))
        if pulse_address.pit_id:
            normalized["pulse_address"] = pulse_address.to_ref()
            normalized.pop("output_schema", None)
        return normalized

    def _synthesize_runtime_config(self) -> Dict[str, Any]:
        return {
            "name": self.agent_card.get("name", self.name),
            "type": "phemacast.pulsers.api_pulser.ApiPulser",
            "host": self.host,
            "port": self.port,
            "plaza_url": self.plaza_url,
            "role": self.agent_card.get("role", "pulser"),
            "description": self.agent_card.get("description", ""),
            "tags": list(self.agent_card.get("tags") or []),
            "api_key": self.raw_config.get("api_key"),
            "api_keys": self._normalize_api_key_registry(self.raw_config.get("api_keys")),
            "supported_pulses": [dict(pulse) for pulse in self.supported_pulses],
            "pools": list(self.raw_config.get("pools") or []),
            "practices": list(self.raw_config.get("practices") or []),
        }

    @staticmethod
    def _normalize_api_key_registry(value: Any) -> list[Dict[str, Any]]:
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

    @staticmethod
    def _resolve_api_key_value(value: Any) -> str | None:
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
        if not api_key_id:
            return None
        for entry in self._normalize_api_key_registry(self.config.get("api_keys") or self.raw_config.get("api_keys")):
            if str(entry.get("id")) == str(api_key_id):
                return entry
        return None

    @staticmethod
    def _append_query_param(url: str, name: str, value: str) -> str:
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query[str(name)] = value
        return urlunsplit(parts._replace(query=urlencode(query)))

    @staticmethod
    def _is_sensitive_key(name: str) -> bool:
        key = str(name).strip().lower()
        return any(token in key for token in ("auth", "token", "secret", "key"))

    def _redact_headers(self, headers: Dict[str, Any]) -> Dict[str, Any]:
        redacted: Dict[str, Any] = {}
        for key, value in (headers or {}).items():
            redacted[str(key)] = "***redacted***" if self._is_sensitive_key(str(key)) else value
        return redacted

    def _redact_url(self, url: str) -> str:
        parts = urlsplit(url)
        query_items = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            query_items.append((key, "***redacted***" if self._is_sensitive_key(key) else value))
        return urlunsplit(parts._replace(query=urlencode(query_items)))

    def _resolve_api_key_binding(self, api_config: Dict[str, Any]) -> tuple[str | None, str | None, str | None, str | None]:
        inline_value = api_config.get("api_key")
        inline_header = api_config.get("api_key_header")
        inline_prefix = api_config.get("api_key_prefix")
        inline_param = api_config.get("api_key_param")
        if inline_value is not None:
            return (
                self._resolve_api_key_value(inline_value),
                str(inline_header) if inline_header else "Authorization",
                inline_prefix,
                str(inline_param) if inline_param else None,
            )

        registry_entry = self._lookup_registered_api_key(api_config.get("api_key_id"))
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

    def fetch_pulse_payload(self, pulse_name: str, input_data: Dict[str, Any], pulse_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch payload from an external API defined in pulse_definition."""
        self.last_fetch_debug = {
            "pulse_name": pulse_name,
            "input_data": dict(input_data or {}),
        }
        api_config = pulse_definition.get("api", {})
        url_template = api_config.get("url")
        if not url_template:
            return {"error": f"No API URL defined for pulse '{pulse_name}'"}

        # naive template substitution
        url = url_template
        for key, value in input_data.items():
            url = url.replace(f"{{{key}}}", str(value))
        
        method = api_config.get("method", "GET").upper()
        headers = dict(api_config.get("headers", {}))
        api_key, api_key_header, api_key_prefix, api_key_param = self._resolve_api_key_binding(api_config)
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
            self.logger.error(f"Error fetching API for pulse '{pulse_name}': {e}")
            self.last_fetch_debug["error"] = str(e)
            return {"error": str(e)}

        # Optional: extract root to avoid dict indexing issues mapping on arrays
        root_path = api_config.get("root_path")
        if root_path:
            resolved_root_path = str(root_path)
            for key, value in input_data.items():
                resolved_root_path = resolved_root_path.replace(f"{{{key}}}", str(value))
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
