from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

import requests
from fastapi import HTTPException, Request
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from phemacast.agents.pulser import Pulser, _resolve_path
from prompits.core.pit import PitAddress

logger = logging.getLogger(__name__)

_TEMPLATE_PATTERN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")
_SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}


class PathPulser(Pulser):
    """
    Pulser that composes multiple upstream pulsers through step-based scripts.

    Each supported pulse can define:
    - `steps`: ordered list of fetch/script steps
    - `result_path`: dotted path inside the execution context for the final payload
    - `test_data`: editor-only sample params used by the UI
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
        self.templates = Jinja2Templates(directory=template_dir)
        self.last_fetch_debug: Dict[str, Any] = {}
        self._setup_path_pulser_routes()

    def _setup_path_pulser_routes(self) -> None:
        @self.app.get("/")
        async def path_pulser_ui(request: Request):
            return self.templates.TemplateResponse(
                request,
                "phemacast/pulsers/templates/path_pulser_editor.html",
                {
                    "agent_name": self.agent_card.get("name", self.name),
                    "config_path": str(self.config_path) if self.config_path else "",
                },
            )

        @self.app.get("/api/config")
        async def get_path_pulser_config():
            config = await run_in_threadpool(self._load_config_document)
            return {
                "status": "success",
                "config": config,
                "config_path": str(self.config_path) if self.config_path else None,
            }

        @self.app.get("/api/plaza/pulsers")
        async def get_plaza_pulsers(search: str = "", pulse_name: str = ""):
            params: Dict[str, Any] = {"pit_type": "Pulser"}
            if search.strip():
                params["name"] = search.strip()
            if pulse_name.strip():
                params["pulse_name"] = pulse_name.strip()
            rows = await run_in_threadpool(self._search_plaza_directory, **params)
            pulsers = []
            for row in rows or []:
                card = row.get("card") or {}
                meta = card.get("meta") or {}
                pulses = meta.get("supported_pulses") or []
                pit_address = PitAddress.from_value(card.get("pit_address"))
                pulsers.append(
                    {
                        "pit_address": pit_address.to_ref(reference_plaza=self.plaza_url),
                        "pit_id": pit_address.pit_id,
                        "name": card.get("name") or row.get("name"),
                        "description": card.get("description") or row.get("description") or "",
                        "tags": list(card.get("tags") or []),
                        "supported_pulses": [
                            {
                                "name": pulse.get("pulse_name") or pulse.get("name"),
                                "pulse_address": pulse.get("pulse_address"),
                                "input_schema": pulse.get("input_schema") if isinstance(pulse.get("input_schema"), dict) else {},
                            }
                            for pulse in pulses
                            if isinstance(pulse, dict)
                        ],
                    }
                )
            return {"status": "success", "pulsers": pulsers}

        @self.app.get("/api/plaza/pulses")
        async def get_plaza_pulses(search: str = ""):
            rows = await run_in_threadpool(self._search_plaza_directory, pit_type="Pulse", name=search.strip() or None)
            pulses = []
            for row in rows or []:
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
        async def save_path_pulser_config(request: Request):
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
        async def test_path_pulser_pulse(request: Request):
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
                result = runner._materialize_result(raw_payload, pulse_definition, pulse_name=str(pulse_name))
                if mapping_rules and not (isinstance(result, dict) and result.get("error")):
                    result = runner.transform(
                        raw_payload,
                        pulse_name=str(pulse_name),
                        pulse_address=pulse_definition.get("pulse_address"),
                        output_schema=pulse_definition.get("output_schema"),
                        mapping=mapping_rules,
                    )
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
            raise HTTPException(status_code=400, detail="This PathPulser was not started from a config file.")

        normalized = self._normalize_config_document(config)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(json.dumps(normalized, indent=4), encoding="utf-8")

        self.raw_config = dict(normalized)
        self.apply_pulser_config(normalized)
        return self._build_editor_config_document(normalized)

    def _normalize_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        document = dict(config or {})
        document.setdefault("name", self.agent_card.get("name", self.name))
        document.setdefault("type", "phemacast.pulsers.path_pulser.PathPulser")
        document.setdefault("host", self.host)
        document.setdefault("port", self.port)
        if self.plaza_url and "plaza_url" not in document:
            document["plaza_url"] = self.plaza_url
        document.setdefault("role", "pulser")
        document.setdefault("description", self.agent_card.get("description", ""))
        document["tags"] = list(document.get("tags") or [])
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
        if isinstance(normalized.get("steps"), list):
            normalized["steps"] = [dict(step) for step in normalized["steps"] if isinstance(step, dict)]
        else:
            normalized["steps"] = []
        normalized["result_path"] = str(normalized.get("result_path") or "result")
        return normalized

    def _synthesize_runtime_config(self) -> Dict[str, Any]:
        return {
            "name": self.agent_card.get("name", self.name),
            "type": "phemacast.pulsers.path_pulser.PathPulser",
            "host": self.host,
            "port": self.port,
            "plaza_url": self.plaza_url,
            "role": self.agent_card.get("role", "pulser"),
            "description": self.agent_card.get("description", ""),
            "tags": list(self.agent_card.get("tags") or []),
            "supported_pulses": [dict(pulse) for pulse in self.supported_pulses],
            "pools": list(self.raw_config.get("pools") or []),
            "practices": list(self.raw_config.get("practices") or []),
        }

    def _normalize_pulse_definition(self, pulse: Mapping[str, Any]) -> Dict[str, Any]:
        normalized = super()._normalize_pulse_definition(pulse)
        steps = pulse.get("steps") if isinstance(pulse, Mapping) else None
        normalized["steps"] = [dict(step) for step in steps if isinstance(step, Mapping)] if isinstance(steps, list) else []
        normalized["result_path"] = str(pulse.get("result_path") or "result")
        if "test_data" in pulse:
            normalized["test_data"] = dict(pulse.get("test_data") or {}) if isinstance(pulse.get("test_data"), Mapping) else {}
        normalized["is_complete"] = bool(pulse.get("is_complete")) if "is_complete" in pulse else False
        normalized["completion_status"] = str(pulse.get("completion_status") or ("complete" if normalized["is_complete"] else "unfinished"))
        normalized["completion_errors"] = list(pulse.get("completion_errors") or [])
        return normalized

    def apply_pulser_config(self, *args, **kwargs) -> None:
        super().apply_pulser_config(*args, **kwargs)
        self._refresh_completion_status()

    def _refresh_completion_status(self) -> None:
        updated: List[Dict[str, Any]] = []
        for pulse in self.supported_pulses:
            if not isinstance(pulse, dict):
                continue
            updated.append(self._with_completion_status(dict(pulse)))
        self.supported_pulses = updated
        if self.supported_pulses:
            primary = self.supported_pulses[0]
            self.pulse_address = primary.get("pulse_address")
            self.input_schema = primary.get("input_schema", {})
            self.mapping = primary.get("mapping", {})
            self.output_schema = primary.get("output_schema", {})
        meta = dict(self.agent_card.get("meta") or {})
        meta["supported_pulses"] = [dict(pulse) for pulse in self.supported_pulses]
        self.agent_card["meta"] = meta
        self._refresh_get_pulse_practice_metadata()

    def _with_completion_status(self, pulse_definition: Dict[str, Any]) -> Dict[str, Any]:
        errors = self._validate_pulse_definition(pulse_definition)
        pulse_definition["completion_errors"] = errors
        pulse_definition["is_complete"] = not errors
        pulse_definition["completion_status"] = "complete" if not errors else "unfinished"
        return pulse_definition

    def _validate_pulse_definition(self, pulse_definition: Dict[str, Any]) -> List[str]:
        errors: List[str] = []
        if not pulse_definition.get("pulse_address"):
            errors.append("Pulse must be linked to an existing Plaza pulse.")
        expected_schema = pulse_definition.get("output_schema")
        if not isinstance(expected_schema, dict) or not expected_schema:
            errors.append("Pulse output_schema is required.")
        steps = pulse_definition.get("steps") or []
        if not isinstance(steps, list) or not steps:
            errors.append("At least one step is required.")
            return errors

        if pulse_definition.get("result_path") in {"", "result"} and steps:
            # A bare `result` path does not point at the step chain output in this pulser.
            errors.append("result_path must point at the final step output, for example steps.final_step.")

        test_data = pulse_definition.get("test_data")
        if not isinstance(test_data, dict) or not test_data:
            errors.append("Pulse test_data is required to validate the final step against the pulse schema.")
            return errors

        try:
            raw_payload = self.fetch_pulse_payload(str(pulse_definition.get("name") or "path_pulse"), dict(test_data), pulse_definition)
            if isinstance(raw_payload, dict) and raw_payload.get("error"):
                errors.append(str(raw_payload.get("error")))
                return errors
            result = self._materialize_result(raw_payload, pulse_definition, pulse_name=str(pulse_definition.get("name") or "path_pulse"))
            schema_errors = self._validate_against_schema(result, expected_schema, path="result")
            errors.extend(schema_errors)
        except Exception as exc:
            errors.append(str(exc))

        return errors

    def fetch_pulse_payload(self, pulse_name: str, input_data: Dict[str, Any], pulse_definition: Dict[str, Any]) -> Dict[str, Any]:
        steps = pulse_definition.get("steps") or []
        if not isinstance(steps, list) or not steps:
            return {
                "error": f"Pulse '{pulse_name}' requires a non-empty steps list.",
                "_input": dict(input_data or {}),
                "steps": {},
                "result": {},
            }

        context: Dict[str, Any] = {
            "_input": dict(input_data or {}),
            "input": dict(input_data or {}),
            "_previous": dict(input_data or {}),
            "previous": dict(input_data or {}),
            "pulse_name": pulse_name,
            "steps": {},
            "sources": {},
        }
        self.last_fetch_debug = {
            "pulse_name": pulse_name,
            "input_data": dict(input_data or {}),
            "steps": [],
        }

        for index, raw_step in enumerate(steps):
            if not isinstance(raw_step, Mapping):
                raise ValueError(f"Step {index + 1} for pulse '{pulse_name}' must be a JSON object.")
            step = dict(raw_step)
            step_name = str(step.get("name") or f"step_{index + 1}")
            result = self._execute_step(step_name=step_name, step=step, context=context, pulse_definition=pulse_definition)
            context["steps"][step_name] = result
            context["_previous"] = result
            context["previous"] = result
            context["sources"] = context.get("sources") or {}
            self.last_fetch_debug["steps"].append(
                {
                    "name": step_name,
                    "type": step.get("type") or ("python" if step.get("script") else "source"),
                    "sources": list((result.get("_sources") or {}).keys()) if isinstance(result, dict) else [],
                    "result": result,
                }
            )

        result_path = str(pulse_definition.get("result_path") or "result")
        final_result = _resolve_path(context, result_path)
        return {
            "_input": dict(input_data or {}),
            "steps": context["steps"],
            "result": final_result if final_result is not None else context["steps"].get(list(context["steps"].keys())[-1]),
            "context": context,
        }

    def get_pulse_data(
        self,
        input_data: Dict[str, Any],
        pulse_name: Optional[str] = None,
        pulse_address: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        pulse_definition = self.resolve_pulse_definition(pulse_name=pulse_name, pulse_address=pulse_address)
        active_name = pulse_name or pulse_definition.get("name")
        raw_payload = self.fetch_pulse_payload(active_name, input_data, pulse_definition) or {}
        if not isinstance(raw_payload, dict):
            raise TypeError("fetch_pulse_payload() must return a dict.")

        materialized = self._materialize_result(raw_payload, pulse_definition, pulse_name=active_name)
        mapping_rules = pulse_definition.get("mapping") or self.mapping
        if mapping_rules and not (isinstance(materialized, dict) and materialized.get("error")):
            return self.transform(
                raw_payload,
                pulse_name=active_name,
                pulse_address=pulse_definition.get("pulse_address"),
                output_schema=output_schema or pulse_definition.get("output_schema"),
                mapping=mapping_rules,
            )
        if isinstance(materialized, dict):
            return materialized
        return {"result": materialized}

    def _materialize_result(self, raw_payload: Dict[str, Any], pulse_definition: Dict[str, Any], *, pulse_name: Optional[str] = None) -> Any:
        if isinstance(raw_payload, dict) and raw_payload.get("error"):
            return raw_payload
        result_path = str(pulse_definition.get("result_path") or "result")
        materialized = _resolve_path(raw_payload, result_path)
        if materialized is not None:
            return materialized
        if isinstance(raw_payload, dict) and "result" in raw_payload:
            return raw_payload["result"]
        return raw_payload

    def _execute_step(
        self,
        *,
        step_name: str,
        step: Dict[str, Any],
        context: Dict[str, Any],
        pulse_definition: Dict[str, Any],
    ) -> Any:
        sources = self._fetch_step_sources(step_name=step_name, step=step, context=context)
        step_type = str(step.get("type") or ("python" if step.get("script") else "source")).strip().lower()

        if step_type == "source":
            if len(sources) == 1:
                return next(iter(sources.values()))
            return {"_sources": sources, **sources}

        if step_type == "python":
            return self._execute_python_step(
                step_name=step_name,
                step=step,
                sources=sources,
                context=context,
                pulse_definition=pulse_definition,
            )

        raise ValueError(f"Unsupported step type '{step_type}' in step '{step_name}'.")

    def _fetch_step_sources(self, *, step_name: str, step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        source_defs = step.get("sources")
        if source_defs is None and any(key in step for key in ("pulser_url", "pulser_name", "pulse_name", "pulse_address", "params", "pulser_address")):
            source_defs = [step]
        if source_defs is None:
            return {}
        if not isinstance(source_defs, list):
            raise ValueError(f"Step '{step_name}' sources must be a list.")

        results: Dict[str, Any] = {}
        for index, raw_source in enumerate(source_defs):
            if not isinstance(raw_source, Mapping):
                raise ValueError(f"Source {index + 1} in step '{step_name}' must be a JSON object.")
            source = dict(raw_source)
            alias = str(source.get("name") or source.get("alias") or f"source_{index + 1}")
            raw_params = source.get("params")
            if raw_params is None:
                previous_output = context.get("_previous")
                if isinstance(previous_output, dict):
                    raw_params = dict(previous_output)
                elif previous_output is None:
                    raw_params = {}
                else:
                    raw_params = {"value": previous_output}
            rendered_params = self._render_structure(raw_params, context)
            if not isinstance(rendered_params, dict):
                raise ValueError(f"Source '{alias}' params in step '{step_name}' must resolve to a JSON object.")
            results[alias] = self._call_source_pulser(source=source, params=rendered_params)
        return results

    def _call_source_pulser(self, *, source: Dict[str, Any], params: Dict[str, Any]) -> Any:
        target_url = self._resolve_source_url(source)
        if not target_url:
            raise ValueError("Each path pulser source requires pulser_url, pulser_address, or a plaza-resolvable pulser_name.")

        pulse_name = source.get("pulse_name")
        pulse_address = source.get("pulse_address")
        if not pulse_name and not pulse_address:
            raise ValueError("Each path pulser source requires pulse_name or pulse_address.")

        payload = {
            "sender": self.name,
            "receiver": target_url,
            "msg_type": "get_pulse_data",
            "content": {
                "pulse_name": pulse_name,
                "pulse_address": pulse_address,
                "params": params,
            },
        }
        response = requests.post(f"{target_url.rstrip('/')}/use_practice/get_pulse_data", json=payload, timeout=30)
        if response.status_code != 200:
            raise ValueError(f"Source pulser call failed with status {response.status_code}: {response.text}")
        if not response.content:
            return {}
        return response.json()

    def _resolve_source_url(self, source: Dict[str, Any]) -> Optional[str]:
        explicit = source.get("pulser_url") or source.get("url") or source.get("address")
        if explicit:
            return str(explicit).rstrip("/")

        pulser_address = source.get("pulser_address") or source.get("pit_address")
        if pulser_address:
            target = self._resolve_remote_target(pulser_address)
            if target and target.get("url"):
                return str(target["url"]).rstrip("/")

        if self.plaza_url and (source.get("pulser_name") or source.get("pulse_name") or source.get("pulse_address")):
            rows = self._search_plaza_directory(
                pit_type="Pulser",
                name=source.get("pulser_name"),
                pulse_name=source.get("pulse_name"),
                pulse_address=source.get("pulse_address"),
            )
            for row in rows or []:
                card = row.get("card") or {}
                address = card.get("address")
                if address:
                    return str(address).rstrip("/")

        return None

    def _execute_python_step(
        self,
        *,
        step_name: str,
        step: Dict[str, Any],
        sources: Dict[str, Any],
        context: Dict[str, Any],
        pulse_definition: Dict[str, Any],
    ) -> Any:
        script = step.get("script")
        if not isinstance(script, str) or not script.strip():
            raise ValueError(f"Python step '{step_name}' requires a non-empty script.")

        local_vars: Dict[str, Any] = {
            "step_name": step_name,
            "step": dict(step),
            "pulse": dict(pulse_definition),
            "input_data": dict(context.get("_input") or {}),
            "previous_output": context.get("_previous"),
            "context": context,
            "steps": context.get("steps") or {},
            "sources": sources,
            "json": json,
            "result": None,
            "output": None,
            "resolve_path": _resolve_path,
        }
        exec_globals = {"__builtins__": _SAFE_BUILTINS}
        exec(script, exec_globals, local_vars)

        transform = local_vars.get("transform")
        if callable(transform):
            return transform(
                sources=sources,
                steps=context.get("steps") or {},
                input_data=dict(context.get("_input") or {}),
                context=context,
                step=dict(step),
                pulse=dict(pulse_definition),
            )

        if local_vars.get("result") is not None:
            return local_vars["result"]
        if local_vars.get("output") is not None:
            return local_vars["output"]

        raise ValueError(f"Python step '{step_name}' did not set `result`, `output`, or `transform`.")

    def _render_structure(self, value: Any, context: Dict[str, Any]) -> Any:
        if isinstance(value, str):
            return self._render_template_value(value, context)
        if isinstance(value, list):
            return [self._render_structure(item, context) for item in value]
        if isinstance(value, dict):
            return {str(key): self._render_structure(item, context) for key, item in value.items()}
        return value

    def _render_template_value(self, template: str, context: Dict[str, Any]) -> Any:
        matches = list(_TEMPLATE_PATTERN.finditer(template))
        if not matches:
            return template

        stripped = template.strip()
        if len(matches) == 1 and matches[0].span() == (0, len(stripped)) and stripped == matches[0].group(0):
            return _resolve_path(context, matches[0].group(1).strip())

        def _replace(match: re.Match[str]) -> str:
            resolved = _resolve_path(context, match.group(1).strip())
            return "" if resolved is None else str(resolved)

        return _TEMPLATE_PATTERN.sub(_replace, template)

    def _validate_against_schema(self, value: Any, schema: Any, *, path: str = "value") -> List[str]:
        if not isinstance(schema, Mapping) or not schema:
            return []

        errors: List[str] = []
        expected_type = schema.get("type")
        if expected_type == "object":
            if not isinstance(value, Mapping):
                return [f"{path} must be an object."]
            properties = schema.get("properties") if isinstance(schema.get("properties"), Mapping) else {}
            for key in schema.get("required") or []:
                if key not in value:
                    errors.append(f"{path}.{key} is required.")
            for key, child_schema in properties.items():
                if key in value:
                    errors.extend(self._validate_against_schema(value.get(key), child_schema, path=f"{path}.{key}"))
            return errors

        if expected_type == "array":
            if not isinstance(value, list):
                return [f"{path} must be an array."]
            item_schema = schema.get("items")
            if item_schema:
                for index, item in enumerate(value):
                    errors.extend(self._validate_against_schema(item, item_schema, path=f"{path}[{index}]"))
            return errors

        if expected_type == "string" and not isinstance(value, str):
            return [f"{path} must be a string."]
        if expected_type == "number" and not isinstance(value, (int, float)):
            return [f"{path} must be a number."]
        if expected_type == "integer" and not isinstance(value, int):
            return [f"{path} must be an integer."]
        if expected_type == "boolean" and not isinstance(value, bool):
            return [f"{path} must be a boolean."]

        return errors
