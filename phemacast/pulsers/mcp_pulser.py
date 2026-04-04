"""
MCP pulser implementation for the Pulsers area.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, these modules implement pulse sources for
APIs, files, bosses, MCP tools, and path-based workflows.

Core types exposed here include `MCPPulser`, which carry the main behavior or state
managed by this module.
"""

from __future__ import annotations

import json
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, Dict, Iterable, Mapping
from uuid import uuid4

import anyio
import httpx
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
import mcp.types as mcp_types

try:
    from mcp.client.sse import sse_client
except ImportError:  # pragma: no cover - depends on optional transport support
    sse_client = None

from phemacast.agents.pulser import _resolve_path
from phemacast.pulsers.api_pulser import APIsPulser

logger = logging.getLogger(__name__)

_PLACEHOLDER_PATTERN = re.compile(r"\{([^{}]+)\}")
_JSON_FENCE_PATTERN = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class MCPPulser(APIsPulser):
    """
    Generic pulser that fetches pulse payloads by invoking MCP tools.

    The editor and mapping flow are inherited from ``APIsPulser``. Each supported
    pulse supplies an ``mcp`` block instead of an ``api`` block.
    """

    def _normalize_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the config document."""
        document = super()._normalize_config_document(config)
        document["type"] = "phemacast.pulsers.mcp_pulser.MCPPulser"
        document["mcp"] = self._normalize_mcp_config(document.get("mcp"))
        document["supported_pulses"] = [
            self._normalize_config_pulse(pulse)
            for pulse in (document.get("supported_pulses") or self.supported_pulses or [])
            if isinstance(pulse, dict)
        ]
        return document

    def _normalize_config_pulse(self, pulse: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the config pulse."""
        normalized = super()._normalize_config_pulse(pulse)
        normalized["mcp"] = self._normalize_mcp_config(normalized.get("mcp"))
        normalized.pop("api", None)
        return normalized

    def _synthesize_runtime_config(self) -> Dict[str, Any]:
        """Internal helper to return the synthesize runtime config."""
        document = super()._synthesize_runtime_config()
        document["type"] = "phemacast.pulsers.mcp_pulser.MCPPulser"
        document["mcp"] = self._normalize_mcp_config(self.raw_config.get("mcp") or self.config.get("mcp"))
        return document

    @staticmethod
    def _normalize_mcp_config(config: Any) -> Dict[str, Any]:
        """Internal helper to normalize the MCP config."""
        if not isinstance(config, Mapping):
            return {}

        normalized = dict(config)
        transport = str(normalized.get("transport") or normalized.get("type") or "").strip().lower()
        if not transport:
            transport = "stdio" if normalized.get("command") else "sse" if normalized.get("url") else ""
        if transport:
            normalized["transport"] = transport

        if "args" in normalized:
            args = normalized.get("args")
            if isinstance(args, tuple):
                normalized["args"] = list(args)
            elif not isinstance(args, list):
                normalized["args"] = [] if args is None else [args]

        if "env" in normalized:
            env = normalized.get("env")
            normalized["env"] = dict(env) if isinstance(env, Mapping) else {}

        if "headers" in normalized:
            headers = normalized.get("headers")
            normalized["headers"] = dict(headers) if isinstance(headers, Mapping) else {}

        if "arguments" in normalized:
            arguments = normalized.get("arguments")
            normalized["arguments"] = dict(arguments) if isinstance(arguments, Mapping) else {}
        return normalized

    def _merge_mcp_config(self, *configs: Any) -> Dict[str, Any]:
        """Internal helper to merge the MCP config."""
        merged: Dict[str, Any] = {}
        for config in configs:
            merged = self._deep_merge_dicts(merged, self._normalize_mcp_config(config))
        return merged

    def _deep_merge_dicts(self, base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper for deep merge dicts."""
        merged = dict(base)
        for key, value in overlay.items():
            if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
                merged[key] = self._deep_merge_dicts(dict(merged[key]), dict(value))
            elif isinstance(value, list):
                merged[key] = list(value)
            else:
                merged[key] = value
        return merged

    def _resolve_mcp_api_key(self, mcp_config: Mapping[str, Any]) -> tuple[str | None, str | None]:
        """Internal helper to resolve the MCP API key."""
        if mcp_config.get("api_key") is not None:
            return self._resolve_api_key_value(mcp_config.get("api_key")), None

        api_key_id = mcp_config.get("api_key_id")
        if api_key_id:
            registry_entry = self._lookup_registered_api_key(api_key_id)
            if registry_entry is not None:
                return self._resolve_api_key_value(registry_entry.get("api_key", registry_entry)), str(registry_entry.get("id") or "")

        return self._resolve_api_key_value(self.config.get("api_key")), None

    def _missing_mcp_api_key_message(self, mcp_config: Mapping[str, Any]) -> str | None:
        """Internal helper to return the missing MCP API key message."""
        api_key, _api_key_id = self._resolve_mcp_api_key(mcp_config)
        if api_key:
            return None

        registry_id = mcp_config.get("api_key_id")
        if registry_id:
            registry_entry = self._lookup_registered_api_key(registry_id) or {}
            source = registry_entry.get("env") or registry_entry.get("id") or registry_id
            message = f"Missing API key value for registry '{registry_id}'"
            if source:
                message += f" ({source})"
            return message

        if mcp_config.get("api_key") is not None:
            return "Missing inline MCP API key value"

        if self.config.get("api_key") is not None:
            return "Missing pulser-level MCP API key value"

        return None

    def _build_render_context(self, input_data: Dict[str, Any], mcp_config: Mapping[str, Any]) -> Dict[str, Any]:
        """Internal helper to build the render context."""
        context = dict(input_data or {})
        api_key, api_key_id = self._resolve_mcp_api_key(mcp_config)
        if api_key is not None:
            context.setdefault("api_key", api_key)
            context.setdefault("mcp_api_key", api_key)
            if api_key_id:
                context.setdefault(f"{api_key_id}_api_key", api_key)
        return context

    def _resolve_template_token(self, context: Mapping[str, Any], token: str) -> Any:
        """Internal helper to resolve the template token."""
        value = _resolve_path(context, token)
        if value is not None:
            return value
        if token in context:
            return context[token]
        return None

    def _render_template_value(self, value: Any, context: Mapping[str, Any]) -> Any:
        """Internal helper to render the template value."""
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed.startswith("env:"):
                return os.getenv(trimmed[4:].strip())
            if trimmed.startswith("${") and trimmed.endswith("}"):
                env_name = trimmed[2:-1].strip()
                if env_name and env_name.isupper():
                    return os.getenv(env_name)

            exact_match = _PLACEHOLDER_PATTERN.fullmatch(value)
            if exact_match:
                resolved = self._resolve_template_token(context, exact_match.group(1).strip())
                return value if resolved is None else resolved

            def _replace(match: re.Match[str]) -> str:
                """Internal helper for replace."""
                resolved = self._resolve_template_token(context, match.group(1).strip())
                return match.group(0) if resolved is None else str(resolved)

            return _PLACEHOLDER_PATTERN.sub(_replace, value)

        if isinstance(value, Mapping):
            return {str(key): self._render_template_value(item, context) for key, item in value.items()}

        if isinstance(value, list):
            return [self._render_template_value(item, context) for item in value]

        if isinstance(value, tuple):
            return [self._render_template_value(item, context) for item in value]

        return value

    def _prepare_mcp_request(self, pulse_definition: Dict[str, Any], input_data: Dict[str, Any]) -> tuple[Dict[str, Any], str, Dict[str, Any]]:
        """Internal helper to prepare the MCP request."""
        merged_config = self._merge_mcp_config(self.raw_config.get("mcp"), self.config.get("mcp"), pulse_definition.get("mcp"))
        missing_api_key_message = self._missing_mcp_api_key_message(merged_config)
        if missing_api_key_message:
            raise ValueError(missing_api_key_message)
        render_context = self._build_render_context(input_data, merged_config)
        rendered_config = self._normalize_mcp_config(self._render_template_value(merged_config, render_context))

        tool_name = str(
            rendered_config.get("tool")
            or rendered_config.get("name")
            or rendered_config.get("tool_name")
            or ""
        ).strip()
        if not tool_name:
            raise ValueError("Pulse MCP config requires a tool name.")

        raw_arguments = rendered_config.get("arguments")
        if isinstance(raw_arguments, Mapping) and raw_arguments:
            arguments = dict(raw_arguments)
        else:
            arguments = self._render_template_value(dict(input_data or {}), render_context)

        if arguments is None:
            arguments = {}
        if not isinstance(arguments, dict):
            raise ValueError("MCP tool arguments must resolve to a JSON object.")

        return rendered_config, tool_name, arguments

    async def _call_mcp_tool_async(self, mcp_config: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper for call MCP tool async."""
        transport = str(mcp_config.get("transport") or "stdio").strip().lower()
        if transport == "http":
            return await self._call_mcp_tool_over_http_async(mcp_config, tool_name, arguments)

        read_timeout_seconds = mcp_config.get("read_timeout_seconds")
        read_timeout = None
        if read_timeout_seconds is not None:
            read_timeout = timedelta(seconds=float(read_timeout_seconds))

        async with self._open_mcp_transport(mcp_config) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream, read_timeout_seconds=read_timeout) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
        return result.model_dump(mode="python") if hasattr(result, "model_dump") else dict(result)

    def _call_mcp_tool_sync(self, mcp_config: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper for call MCP tool sync."""
        return anyio.run(self._call_mcp_tool_async, mcp_config, tool_name, arguments)

    @staticmethod
    def _build_jsonrpc_message(method: str, *, params: Dict[str, Any] | None = None, request_id: str | None = None) -> Dict[str, Any]:
        """Internal helper to build the jsonrpc message."""
        payload: Dict[str, Any] = {
            "jsonrpc": "2.0",
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        if request_id is not None:
            payload["id"] = request_id
        return payload

    @staticmethod
    def _extract_sse_json_events(text: str) -> list[Any]:
        """Internal helper to extract the sse JSON events."""
        events: list[Any] = []
        for block in text.split("\n\n"):
            lines = [line for line in block.splitlines() if line.startswith("data:")]
            if not lines:
                continue
            payload = "\n".join(line[5:].lstrip() for line in lines).strip()
            if not payload:
                continue
            try:
                events.append(json.loads(payload))
            except Exception:
                events.append(payload)
        return events

    def _parse_jsonrpc_http_response(self, response: Any) -> Any:
        """Internal helper to parse the jsonrpc HTTP response."""
        response.raise_for_status()
        content_type = str(response.headers.get("content-type") or "").lower()

        if "text/event-stream" in content_type:
            events = self._extract_sse_json_events(getattr(response, "text", "") or "")
            if not events:
                raise ValueError("Streamable HTTP response did not include any JSON events.")
            payload = events[-1]
        else:
            try:
                payload = response.json() if getattr(response, "content", b"") else {}
            except Exception:
                text = (getattr(response, "text", "") or "").strip()
                raise ValueError(text or "HTTP MCP endpoint returned a non-JSON response.")

        if isinstance(payload, Mapping) and payload.get("error"):
            error_payload = payload.get("error")
            if isinstance(error_payload, Mapping):
                message = error_payload.get("message") or error_payload.get("detail") or json.dumps(error_payload)
            else:
                message = str(error_payload)
            raise ValueError(str(message))

        if isinstance(payload, Mapping) and "result" in payload:
            return payload["result"]

        return payload

    async def _call_mcp_tool_over_http_async(self, mcp_config: Dict[str, Any], tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper for call MCP tool over HTTP async."""
        url = str(mcp_config.get("url") or "").strip()
        if not url:
            raise ValueError("HTTP MCP transport requires a url.")

        timeout = float(mcp_config.get("timeout") or 30.0)
        base_headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        for key, value in (mcp_config.get("headers") or {}).items():
            if value is not None:
                base_headers[str(key)] = str(value)

        initialize_params = {
            "protocolVersion": mcp_types.LATEST_PROTOCOL_VERSION,
            "capabilities": {
                "sampling": {},
                "roots": {"listChanged": True},
            },
            "clientInfo": {
                "name": "phemacast-mcp-pulser",
                "version": "0.1.0",
            },
        }

        async with httpx.AsyncClient(timeout=timeout, headers=base_headers) as client:
            init_response = await client.post(
                url,
                json=self._build_jsonrpc_message("initialize", params=initialize_params, request_id=f"init-{uuid4()}"),
            )
            init_result = self._parse_jsonrpc_http_response(init_response)
            session_id = init_response.headers.get("mcp-session-id") or init_response.headers.get("Mcp-Session-Id")
            session_headers = {"mcp-session-id": str(session_id)} if session_id else {}

            initialized_payload = self._build_jsonrpc_message("notifications/initialized", params={})
            initialized_response = await client.post(url, json=initialized_payload, headers=session_headers or None)
            initialized_response.raise_for_status()

            supported_versions = {str(value) for value in (1, mcp_types.LATEST_PROTOCOL_VERSION)}
            protocol_version = str((init_result or {}).get("protocolVersion") or "")
            if protocol_version and protocol_version not in supported_versions:
                raise ValueError(f"Unsupported protocol version from the server: {protocol_version}")

            tool_response = await client.post(
                url,
                json=self._build_jsonrpc_message(
                    "tools/call",
                    params={"name": tool_name, "arguments": arguments},
                    request_id=f"call-{uuid4()}",
                ),
                headers=session_headers or None,
            )
            return self._parse_jsonrpc_http_response(tool_response)

    @asynccontextmanager
    async def _open_mcp_transport(self, mcp_config: Dict[str, Any]):
        """Internal helper to open the MCP transport."""
        transport = str(mcp_config.get("transport") or "stdio").strip().lower()
        if transport == "stdio":
            command = str(mcp_config.get("command") or "").strip()
            if not command:
                raise ValueError("stdio MCP transport requires a command.")
            server = StdioServerParameters(
                command=command,
                args=[str(arg) for arg in mcp_config.get("args") or []],
                env={str(key): str(value) for key, value in (mcp_config.get("env") or {}).items() if value is not None} or None,
                cwd=mcp_config.get("cwd"),
            )
            async with stdio_client(server) as streams:
                yield streams
            return

        if transport == "sse":
            if sse_client is None:
                raise ValueError("SSE MCP transport is unavailable in the installed MCP client.")
            url = str(mcp_config.get("url") or "").strip()
            if not url:
                raise ValueError("SSE MCP transport requires a url.")
            timeout = float(mcp_config.get("timeout") or 5.0)
            sse_read_timeout = float(mcp_config.get("sse_read_timeout") or 300.0)
            headers = {str(key): str(value) for key, value in (mcp_config.get("headers") or {}).items() if value is not None}
            async with sse_client(url, headers=headers or None, timeout=timeout, sse_read_timeout=sse_read_timeout) as streams:
                yield streams
            return

        raise ValueError(f"Unsupported MCP transport '{transport}'.")

    @staticmethod
    def _extract_text_fragments(content: Iterable[Any]) -> list[str]:
        """Internal helper to extract the text fragments."""
        fragments: list[str] = []
        for item in content:
            if not isinstance(item, Mapping):
                continue
            item_type = str(item.get("type") or "").strip().lower()
            if item_type == "text":
                text = item.get("text")
                if isinstance(text, str):
                    fragments.append(text)
                continue
            if item_type == "resource":
                resource = item.get("resource")
                if isinstance(resource, Mapping):
                    text = resource.get("text")
                    if isinstance(text, str):
                        fragments.append(text)
        return fragments

    @staticmethod
    def _maybe_parse_json_text(text: str) -> Any:
        """Internal helper for maybe parse JSON text."""
        candidate = text.strip()
        fenced = _JSON_FENCE_PATTERN.match(candidate)
        if fenced:
            candidate = fenced.group(1).strip()
        if not candidate:
            return None
        try:
            return json.loads(candidate)
        except Exception:
            return None

    def _extract_mcp_payload(self, result: Any) -> Any:
        """Internal helper to extract the MCP payload."""
        if hasattr(result, "model_dump"):
            result = result.model_dump(mode="python")

        if isinstance(result, Mapping):
            content = result.get("content")
            if result.get("isError"):
                message = "\n".join(self._extract_text_fragments(content or [])) if isinstance(content, list) else ""
                return {"error": message or "MCP tool call failed."}

            structured = result.get("structuredContent")
            if structured not in (None, "", {}, []):
                return structured

            if isinstance(content, list):
                parsed_items = []
                text_fragments = []
                for fragment in self._extract_text_fragments(content):
                    parsed = self._maybe_parse_json_text(fragment)
                    if parsed is None:
                        text_fragments.append(fragment)
                    else:
                        parsed_items.append(parsed)

                if len(parsed_items) == 1:
                    return parsed_items[0]
                if parsed_items:
                    return {"items": parsed_items}
                if len(text_fragments) == 1:
                    return {"content": text_fragments[0]}
                if text_fragments:
                    return {"items": text_fragments}

            if "result" in result:
                return result["result"]

        return result

    def _redact_value(self, value: Any, key_hint: str | None = None) -> Any:
        """Internal helper to return the redact value."""
        if key_hint and self._is_sensitive_key(key_hint):
            return "***redacted***"
        if isinstance(value, Mapping):
            return {str(key): self._redact_value(item, str(key)) for key, item in value.items()}
        if isinstance(value, list):
            return [self._redact_value(item, key_hint) for item in value]
        return value

    def fetch_pulse_payload(self, pulse_name: str, input_data: Dict[str, Any], pulse_definition: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch the pulse payload."""
        self.last_fetch_debug = {
            "pulse_name": pulse_name,
            "input_data": dict(input_data or {}),
        }

        try:
            mcp_config, tool_name, arguments = self._prepare_mcp_request(pulse_definition, input_data)
        except Exception as exc:
            self.last_fetch_debug["error"] = str(exc)
            return {"error": str(exc)}

        self.last_fetch_debug["request"] = {
            "transport": str(mcp_config.get("transport") or "stdio"),
            "tool": tool_name,
            "arguments": self._redact_value(arguments),
            "mcp": self._redact_value(
                {
                    "command": mcp_config.get("command"),
                    "args": mcp_config.get("args"),
                    "env": mcp_config.get("env"),
                    "url": mcp_config.get("url"),
                    "headers": mcp_config.get("headers"),
                    "cwd": mcp_config.get("cwd"),
                    "root_path": mcp_config.get("root_path"),
                }
            ),
        }

        try:
            result = self._call_mcp_tool_sync(mcp_config, tool_name, arguments)
            self.last_fetch_debug["response"] = self._redact_value(result)
            data = self._extract_mcp_payload(result)
        except Exception as exc:
            message = self._normalize_fetch_error(exc)
            logger.error("Error fetching MCP payload for pulse '%s': %s", pulse_name, message)
            self.last_fetch_debug["error"] = message
            return {"error": message}

        if isinstance(data, Mapping) and data.get("error"):
            self.last_fetch_debug["extracted_payload"] = data
            return dict(data)

        root_path = mcp_config.get("root_path")
        if root_path:
            resolved_root_path = self._render_template_value(str(root_path), self._build_render_context(input_data, mcp_config))
            current = _resolve_path(data, str(resolved_root_path))
            if current is None:
                message = f"Could not extract root_path {resolved_root_path} from MCP response"
                self.last_fetch_debug["extracted_payload"] = {"error": message}
                return {"error": message}
            data = current

        if isinstance(data, list):
            data = {
                "items": data,
                "_input": dict(input_data or {}),
            }
        elif isinstance(data, dict):
            data.setdefault("_input", dict(input_data or {}))
        else:
            message = "MCP response root is not a dictionary or list, cannot apply mapping rules"
            self.last_fetch_debug["extracted_payload"] = {"error": message}
            return {"error": message}

        self.last_fetch_debug["extracted_payload"] = self._redact_value(data)
        return data
