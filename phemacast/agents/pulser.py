from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

from attas.pds import normalize_runtime_pulse_entry
from fastapi.staticfiles import StaticFiles
from prompits.agents.standby import StandbyAgent
from prompits.core.message import Message
from prompits.core.pit import PitAddress

from phemacast.practices.pulser import GetPulseDataPractice


ConfigInput = Union[str, Path, Mapping[str, Any]]


def _read_config(config: ConfigInput) -> Dict[str, Any]:
    if isinstance(config, Mapping):
        return dict(config)

    config_path = Path(config)
    with config_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_path(data: Any, path: str) -> Any:
    current = data
    remaining = str(path or "").strip()
    if not remaining:
        return current

    while remaining:
        if isinstance(current, Mapping):
            if remaining in current:
                return current[remaining]

            matched = False
            for key in sorted(current.keys(), key=lambda value: len(str(value)), reverse=True):
                key_text = str(key)
                prefix = f"{key_text}."
                if remaining.startswith(prefix):
                    current = current[key]
                    remaining = remaining[len(prefix):]
                    matched = True
                    break
            if matched:
                continue
            return None

        if isinstance(current, list):
            part, separator, rest = remaining.partition(".")
            if not part.isdigit():
                return None
            index = int(part)
            if index < 0 or index >= len(current):
                return None
            current = current[index]
            if not separator:
                return current
            remaining = rest
            continue

        return None

    return current


def _assign_path(data: Dict[str, Any], path: str, value: Any) -> None:
    current = data
    parts = path.split(".")
    for part in parts[:-1]:
        node = current.get(part)
        if not isinstance(node, dict):
            node = {}
            current[part] = node
        current = node
    current[parts[-1]] = value


def _transform_item_mapping(item: Any, field_rules: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(item, Mapping):
        return {}

    transformed: Dict[str, Any] = {}
    for output_field, rule in field_rules.items():
        if isinstance(rule, str):
            value = _resolve_path(item, rule)
            if value is not None:
                _assign_path(transformed, output_field, value)
            continue

        if isinstance(rule, Mapping):
            if "value" in rule:
                _assign_path(transformed, output_field, rule["value"])
                continue

            source = rule.get("source") or rule.get("from") or rule.get("path") or rule.get("input")
            if source:
                value = _resolve_path(item, str(source))
                if value is not None:
                    _assign_path(transformed, output_field, value)
                    continue

            if "default" in rule:
                _assign_path(transformed, output_field, rule["default"])

    return transformed


def _coerce_positive_limit(value: Any) -> Optional[int]:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return None
    return limit if limit >= 0 else None


def _coerce_number(value: Any) -> Optional[float]:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


class Pulser(StandbyAgent):
    """
    Standby agent specialized for pulse payload delivery.

    A pulser advertises its supported pulses in `agent_card.meta.supported_pulses`,
    exposes `get_pulse_data` as a mounted practice, and registers with Plaza as
    soon as it is initialized when `plaza_url` is provided.
    """

    def __init__(
        self,
        config: Optional[ConfigInput] = None,
        *,
        config_path: Optional[ConfigInput] = None,
        name: str = "Pulser",
        host: str = "127.0.0.1",
        port: int = 8000,
        plaza_url: Optional[str] = None,
        agent_card: Optional[Dict[str, Any]] = None,
        pool: Any = None,
        pulse_name: Optional[str] = None,
        pulse_address: Optional[str] = None,
        input_schema: Optional[Dict[str, Any]] = None,
        mapping: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        supported_pulses: Optional[List[Dict[str, Any]]] = None,
        auto_register: bool = True,
    ):
        config_data = _read_config(config) if config is not None else {}
        resolved_config_path = config_path
        if resolved_config_path is None and isinstance(config, (str, Path)):
            resolved_config_path = config

        self.config_path = Path(resolved_config_path).resolve() if resolved_config_path else None
        self.raw_config = dict(config_data)
        self._shared_pulse_cards_by_id: Dict[str, Dict[str, Any]] = {}
        self._shared_pulse_cards_by_name: Dict[str, Dict[str, Any]] = {}
        pulser_config = config_data.get("pulser", config_data)

        pulse_definitions = self._build_supported_pulses(
            config=pulser_config,
            pulse_name=pulse_name,
            pulse_address=pulse_address,
            input_schema=input_schema,
            mapping=mapping,
            output_schema=output_schema,
            supported_pulses=supported_pulses,
        )
        if not pulse_definitions:
            raise ValueError("Pulser requires at least one configured pulse.")

        card = dict(agent_card or pulser_config.get("agent_card") or {})
        card.setdefault("name", name)
        card.setdefault("role", "pulser")
        card.setdefault("pit_type", "Pulser")

        super().__init__(
            name=name,
            host=host,
            port=port,
            plaza_url=plaza_url,
            agent_card=card,
            pool=pool,
        )

        self.apply_pulser_config(
            config_data or pulser_config,
            supported_pulses=supported_pulses,
            pulse_name=pulse_name,
            pulse_address=pulse_address,
            input_schema=input_schema,
            mapping=mapping,
            output_schema=output_schema,
            agent_card_overrides=card,
        )

        current_dir = os.path.dirname(os.path.abspath(__file__))
        shared_static_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "prompits", "agents", "static"))
        try:
            self.app.mount("/static", StaticFiles(directory=shared_static_dir), name="static")
        except Exception:
            # Pulser subclasses may already expose this mount.
            pass

        self.add_practice(GetPulseDataPractice())

        if self.plaza_url and auto_register:
            self.register()

    @classmethod
    def from_config(cls, config: ConfigInput, **kwargs: Any) -> "Pulser":
        return cls(config=config, **kwargs)

    @staticmethod
    def _merge_tags(*tag_groups: Any) -> List[str]:
        merged: List[str] = []
        for group in tag_groups:
            if not group:
                continue
            for tag in group:
                value = str(tag)
                if value not in merged:
                    merged.append(value)
        return merged

    def _build_supported_pulses(
        self,
        *,
        config: Dict[str, Any],
        pulse_name: Optional[str],
        pulse_address: Optional[str],
        input_schema: Optional[Dict[str, Any]],
        mapping: Optional[Dict[str, Any]],
        output_schema: Optional[Dict[str, Any]],
        supported_pulses: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        raw_pulses = supported_pulses or config.get("supported_pulses")
        if raw_pulses:
            return [self._normalize_pulse_definition(pulse) for pulse in raw_pulses if isinstance(pulse, Mapping)]

        return [
            self._normalize_pulse_definition(
                {
                    "name": pulse_name or config.get("name") or "default_pulse",
                    "pulse_address": pulse_address or config.get("pulse_address"),
                    "input_schema": input_schema if input_schema is not None else config.get("input_schema", {}),
                    "mapping": mapping if mapping is not None else config.get("mapping", {}),
                    "output_schema": output_schema if output_schema is not None else config.get("output_schema", {}),
                    "description": config.get("description", ""),
                    "tags": config.get("tags", []),
                    "cost": config.get("cost", 0),
                }
            )
        ]

    def build_register_payload(
        self,
        plaza_url: str,
        card: Optional[Dict[str, Any]] = None,
        address: Optional[str] = None,
        expires_in: int = 3600,
        pit_type: Optional[str] = None,
        pit_id: Optional[str] = None,
        api_key: Optional[str] = None,
        accepts_inbound_from_plaza: Optional[bool] = None,
    ) -> Dict[str, Any]:
        payload = super().build_register_payload(
            plaza_url=plaza_url,
            card=card,
            address=address,
            expires_in=expires_in,
            pit_type=pit_type,
            pit_id=pit_id,
            api_key=api_key,
            accepts_inbound_from_plaza=accepts_inbound_from_plaza,
        )
        supported_pulses = self.supported_pulses if isinstance(getattr(self, "supported_pulses", None), list) else []
        if supported_pulses:
            pairs = []
            for pulse in supported_pulses:
                if not isinstance(pulse, dict) or not (pulse.get("pulse_id") or pulse.get("pulse_name") or pulse.get("name")):
                    continue
                pair = {
                    "pulse_id": pulse.get("pulse_id"),
                    "pulse_name": pulse.get("pulse_name") or pulse.get("name"),
                    "pulse_address": pulse.get("pulse_address"),
                    "pulse_definition": pulse.get("pulse_definition"),
                    "input_schema": pulse.get("input_schema"),
                }
                for key in ("is_complete", "completion_status", "completion_errors"):
                    if key in pulse:
                        pair[key] = pulse.get(key)
                pair["status"] = pulse.get("completion_status") or pulse.get("status")
                pairs.append(pair)
            payload["pulse_pulser_pairs"] = pairs
        return payload

    def _normalize_pulse_definition(self, pulse: Mapping[str, Any]) -> Dict[str, Any]:
        normalized = dict(pulse)
        normalized.setdefault("name", "default_pulse")
        default_pulse_address = self.config.get("pulse_address") if hasattr(self, "config") else None
        if not default_pulse_address:
            default_pulse_address = normalized.get("pit_address") or normalized.get("pulse_pit_address") or normalized.get("shared_pulse_address")
        if default_pulse_address:
            normalized.setdefault("pulse_address", self._compact_pit_ref(default_pulse_address))
        normalized = normalize_runtime_pulse_entry(
            normalized,
            default_name=str(normalized.get("name") or "default_pulse"),
            default_description=str(normalized.get("description") or ""),
            default_pulse_address=normalized.get("pulse_address"),
        )
        normalized["input_schema"] = dict(normalized.get("input_schema") or {})
        normalized["mapping"] = dict(normalized.get("mapping") or {})
        normalized["output_schema"] = dict(normalized.get("output_schema") or {})
        normalized["tags"] = list(normalized.get("tags") or [])
        normalized["cost"] = normalized.get("cost", 0)
        return normalized

    def _compact_pit_ref(self, value: Any) -> str:
        pit_address = PitAddress.from_value(value)
        if pit_address.pit_id:
            return pit_address.to_ref(reference_plaza=self.plaza_url)
        return str(value or "")

    @staticmethod
    def _same_pit_ref(left: Any, right: Any) -> bool:
        left_address = PitAddress.from_value(left)
        right_address = PitAddress.from_value(right)
        if left_address.pit_id and right_address.pit_id:
            return left_address.pit_id == right_address.pit_id
        return str(left or "").strip() == str(right or "").strip()

    def _search_plaza_directory(self, **params: Any) -> Optional[List[Dict[str, Any]]]:
        if not self.plaza_url:
            return None
        try:
            headers = self._ensure_token_valid() or {}
            if not headers.get("Authorization"):
                return None
            response = self._plaza_get("/search", params=params, headers=headers)
            if response.status_code == 401:
                self.register()
                headers = self._ensure_token_valid() or {}
                response = self._plaza_get("/search", params=params, headers=headers)
            if response.status_code != 200:
                return None
            payload = response.json()
            return payload if isinstance(payload, list) else []
        except Exception:
            return None

    def _cache_shared_pulse_card(self, card: Mapping[str, Any]) -> None:
        if not isinstance(card, Mapping):
            return
        normalized = dict(card)
        pit_address = PitAddress.from_value(
            normalized.get("pit_address")
            or normalized.get("address")
            or normalized.get("pulse_address")
        )
        if pit_address.pit_id:
            self._shared_pulse_cards_by_id[str(pit_address.pit_id)] = normalized
        card_name = str(normalized.get("name") or "").strip()
        if card_name:
            self._shared_pulse_cards_by_name[card_name] = normalized

    def _prime_shared_pulse_cache(self) -> None:
        matches = self._search_plaza_directory(pit_type="Pulse")
        if matches is None:
            return
        self._shared_pulse_cards_by_id = {}
        self._shared_pulse_cards_by_name = {}
        for match in matches:
            if not isinstance(match, Mapping):
                continue
            card = match.get("card") if isinstance(match.get("card"), Mapping) else match
            self._cache_shared_pulse_card(card)

    def _resolve_shared_pulse_card(self, pulse_definition: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
        pulse_address = pulse_definition.get("pulse_address")
        pit_address = PitAddress.from_value(pulse_address)
        if pit_address.pit_id:
            cached = self._shared_pulse_cards_by_id.get(str(pit_address.pit_id))
            if cached:
                return dict(cached)

        pulse_name = pulse_definition.get("pulse_name") or pulse_definition.get("name")
        if pulse_name:
            cached = self._shared_pulse_cards_by_name.get(str(pulse_name))
            if cached:
                return dict(cached)
        return None

    def _enrich_pulse_definition(self, pulse_definition: Dict[str, Any]) -> Dict[str, Any]:
        normalized = dict(pulse_definition)
        shared_card = self._resolve_shared_pulse_card(normalized)
        if not isinstance(shared_card, dict):
            return normalized

        shared_meta = dict(shared_card.get("meta") or {})
        shared_pit_address = shared_card.get("pit_address")
        if shared_pit_address:
            normalized["pulse_address"] = self._compact_pit_ref(shared_pit_address)
        normalized.setdefault("pulse_name", shared_card.get("name") or normalized.get("name"))
        if not normalized.get("name") or normalized.get("name") == "default_pulse":
            normalized["name"] = str(shared_card.get("name") or "default_pulse")
        if not normalized.get("description"):
            normalized["description"] = str(shared_card.get("description") or shared_meta.get("description") or "")
        normalized["tags"] = self._merge_tags(shared_card.get("tags"), shared_meta.get("tags"), normalized.get("tags"))
        if not normalized.get("output_schema") and isinstance(shared_meta.get("output_schema"), dict):
            normalized["output_schema"] = dict(shared_meta["output_schema"])
        if not normalized.get("pulse_id"):
            normalized["pulse_id"] = shared_meta.get("pulse_id")
        shared_definition = shared_meta.get("pulse_definition")
        if isinstance(shared_definition, dict):
            normalized["pulse_definition"] = dict(shared_definition)
        return self._normalize_pulse_definition(normalized)

    def apply_pulser_config(
        self,
        config_data: Dict[str, Any],
        *,
        supported_pulses: Optional[List[Dict[str, Any]]] = None,
        pulse_name: Optional[str] = None,
        pulse_address: Optional[str] = None,
        input_schema: Optional[Dict[str, Any]] = None,
        mapping: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        agent_card_overrides: Optional[Dict[str, Any]] = None,
    ) -> None:
        raw_config = dict(config_data or {})
        pulser_config = raw_config.get("pulser", raw_config)
        self.raw_config = raw_config
        self.config = dict(pulser_config)

        pulse_definitions = self._build_supported_pulses(
            config=self.config,
            pulse_name=pulse_name,
            pulse_address=pulse_address,
            input_schema=input_schema,
            mapping=mapping,
            output_schema=output_schema,
            supported_pulses=supported_pulses,
        )
        if not pulse_definitions:
            raise ValueError("Pulser requires at least one configured pulse.")

        if self.plaza_url:
            self._prime_shared_pulse_cache()
        self.supported_pulses = [self._enrich_pulse_definition(pulse) for pulse in pulse_definitions]
        primary_pulse = self.supported_pulses[0]
        self.pulse_address = primary_pulse.get("pulse_address")
        self.input_schema = primary_pulse.get("input_schema", {})
        self.mapping = primary_pulse.get("mapping", {})
        self.output_schema = primary_pulse.get("output_schema", {})

        card = dict(self.agent_card or {})
        if agent_card_overrides:
            card.update(agent_card_overrides)

        resolved_name = raw_config.get("name") or self.config.get("name") or card.get("name") or self.name
        self.name = str(resolved_name)
        card["name"] = self.name
        card["role"] = raw_config.get("role") or self.config.get("role") or card.get("role") or "pulser"
        card["pit_type"] = "Pulser"
        card["description"] = (
            self.config.get("description")
            or raw_config.get("description")
            or card.get("description")
            or "Provides pulse data and schema mapping."
        )
        card["tags"] = self._merge_tags(raw_config.get("tags"), self.config.get("tags"), card.get("tags"), ["pulser", "pulse"])
        if raw_config.get("address"):
            card["address"] = raw_config["address"]

        meta = dict(card.get("meta") or {})
        meta["pulse_address"] = self.pulse_address
        meta["input_schema"] = self.input_schema
        meta["supported_pulses"] = self.supported_pulses
        meta["pulse_id"] = primary_pulse.get("pulse_id")
        meta["pulse_definition"] = dict(primary_pulse.get("pulse_definition") or {})
        card["meta"] = meta
        self.agent_card = card
        self.app.title = self.name
        self._refresh_pit_address()
        self._refresh_get_pulse_practice_metadata()

    def _refresh_get_pulse_practice_metadata(self) -> None:
        practice = next((entry for entry in self.practices if entry.id == "get_pulse_data"), None)
        if practice is None:
            return
        practice.bind(self)
        for practice_entry in self._resolve_callable_practice_entries(practice):
            self._upsert_practice_metadata_in_card(practice_entry)

    def resolve_pulse_definition(
        self,
        pulse_name: Optional[str] = None,
        pulse_address: Optional[str] = None,
    ) -> Dict[str, Any]:
        if pulse_name:
            for pulse in self.supported_pulses:
                if pulse.get("name") == pulse_name or pulse.get("pulse_name") == pulse_name:
                    return pulse

        if pulse_address:
            for pulse in self.supported_pulses:
                if self._same_pit_ref(pulse.get("pulse_address"), pulse_address):
                    return pulse

        return self.supported_pulses[0]

    def register(self, *, start_reconnect_on_failure: bool = True, request_retries: Optional[int] = None):
        if self.plaza_token and time.time() < (self.token_expires_at - 60):
            return
        response = super().register(
            start_reconnect_on_failure=start_reconnect_on_failure,
            request_retries=request_retries,
        )
        try:
            self.apply_pulser_config(self.raw_config or self.config, supported_pulses=self.supported_pulses)
        except Exception:
            pass
        return response

    def fetch_pulse_payload(self, pulse_name: str, input_data: Dict[str, Any], pulse_definition: Dict[str, Any]) -> Dict[str, Any]:
        return input_data

    def transform(
        self,
        input_data: Dict[str, Any],
        pulse_name: Optional[str] = None,
        pulse_address: Optional[str] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        mapping: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        pulse_definition = self.resolve_pulse_definition(pulse_name=pulse_name, pulse_address=pulse_address)
        schema = output_schema or pulse_definition.get("output_schema") or self.output_schema or {}
        mapping_rules = mapping or pulse_definition.get("mapping") or self.mapping
        properties = schema.get("properties", {})

        output_fields: List[str] = []
        for field_name in list(properties.keys()) + list(mapping_rules.keys()):
            if field_name not in output_fields:
                output_fields.append(field_name)
        transformed: Dict[str, Any] = {}
        for output_field in output_fields:
            rule = mapping_rules.get(output_field)
            if rule is None:
                continue

            value, found = self._resolve_mapping_value(rule, input_data)
            if found:
                _assign_path(transformed, output_field, value)

        return transformed

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
        if raw_payload.get("error"):
            return raw_payload

        mapping_rules = pulse_definition.get("mapping") or self.mapping
        if mapping_rules:
            return self.transform(
                raw_payload,
                pulse_name=active_name,
                pulse_address=pulse_definition.get("pulse_address"),
                output_schema=output_schema or pulse_definition.get("output_schema"),
                mapping=mapping_rules,
            )
        return raw_payload

    def _resolve_mapping_value(self, rule: Any, input_data: Dict[str, Any]) -> tuple[Any, bool]:
        if isinstance(rule, str):
            value = _resolve_path(input_data, rule)
            return value, value is not None

        if isinstance(rule, Mapping):
            item_rules = rule.get("items")
            source = rule.get("source") or rule.get("from") or rule.get("path") or rule.get("input")
            if item_rules is not None and source:
                value = _resolve_path(input_data, str(source))
                if isinstance(value, list):
                    limit = None
                    if "limit" in rule:
                        limit = _coerce_positive_limit(rule.get("limit"))
                    elif rule.get("limit_from"):
                        limit = _coerce_positive_limit(_resolve_path(input_data, str(rule.get("limit_from"))))
                    entries = value[:limit] if limit is not None else value
                    return [
                        _transform_item_mapping(entry, item_rules)
                        for entry in entries
                        if isinstance(entry, Mapping)
                    ], True
                if "default" in rule:
                    return rule["default"], True
                return None, False

            if rule.get("op") or rule.get("operation"):
                return self._resolve_mapping_operation(rule, input_data)

            if "value" in rule:
                return rule["value"], True

            if source:
                value = _resolve_path(input_data, str(source))
                if value is not None:
                    return value, True

            if "default" in rule:
                return rule["default"], True

            return None, False

        return rule, rule is not None

    def _resolve_mapping_operation(self, rule: Mapping[str, Any], input_data: Dict[str, Any]) -> tuple[Any, bool]:
        operation = str(rule.get("op") or rule.get("operation") or "").strip().lower()
        if not operation:
            if "default" in rule:
                return rule["default"], True
            return None, False

        operands = rule.get("args")
        if operands is None:
            operands = []
            if "left" in rule:
                operands.append(rule["left"])
            if "right" in rule:
                operands.append(rule["right"])
        elif not isinstance(operands, list):
            operands = [operands]

        resolved_values: List[Any] = []
        for operand in operands:
            value, found = self._resolve_mapping_operand(operand, input_data)
            if not found:
                if "default" in rule:
                    return rule["default"], True
                return None, False
            resolved_values.append(value)

        numeric_values: List[float] = []
        for value in resolved_values:
            numeric = _coerce_number(value)
            if numeric is None:
                if "default" in rule:
                    return rule["default"], True
                return None, False
            numeric_values.append(numeric)

        try:
            if operation == "abs":
                if len(numeric_values) != 1:
                    raise ValueError("abs expects exactly one operand")
                result = abs(numeric_values[0])
            elif operation == "add":
                result = sum(numeric_values)
            elif operation == "subtract":
                if not numeric_values:
                    raise ValueError("subtract expects at least one operand")
                result = numeric_values[0]
                for value in numeric_values[1:]:
                    result -= value
            elif operation == "subtract_abs":
                if not numeric_values:
                    raise ValueError("subtract_abs expects at least one operand")
                result = numeric_values[0]
                for value in numeric_values[1:]:
                    result -= abs(value)
            elif operation in {"multiply", "product"}:
                if not numeric_values:
                    raise ValueError("multiply expects at least one operand")
                result = 1.0
                for value in numeric_values:
                    result *= value
            elif operation in {"divide", "ratio"}:
                if len(numeric_values) < 2:
                    raise ValueError("divide expects at least two operands")
                result = numeric_values[0]
                for value in numeric_values[1:]:
                    if value == 0:
                        if "default" in rule:
                            return rule["default"], True
                        return None, False
                    result /= value
            else:
                raise ValueError(f"Unsupported mapping operation: {operation}")
        except (TypeError, ValueError):
            if "default" in rule:
                return rule["default"], True
            return None, False

        if "round" in rule:
            try:
                result = round(result, int(rule["round"]))
            except (TypeError, ValueError):
                if "default" in rule:
                    return rule["default"], True
                return None, False

        return result, True

    def _resolve_mapping_operand(self, operand: Any, input_data: Dict[str, Any]) -> tuple[Any, bool]:
        if isinstance(operand, Mapping) and (operand.get("op") or operand.get("operation")):
            return self._resolve_mapping_operation(operand, input_data)
        return self._resolve_mapping_value(operand, input_data)

    def receive(self, message: Message):
        if message.msg_type == "get_pulse":
            content = message.content or {}
            if not isinstance(content, dict):
                return {"error": "get_pulse content must be a JSON object"}
            return self.get_pulse_data(
                input_data=content.get("params", {}),
                pulse_name=content.get("pulse_name"),
                pulse_address=content.get("pulse_address"),
                output_schema=content.get("output_schema"),
            )
        return super().receive(message)
