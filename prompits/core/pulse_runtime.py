"""
Generic pulse runtime helpers for `prompits.core`.

Prompits uses these helpers to normalize pulse metadata for Plaza directory records
and runtime practice payloads without depending on application-specific packages.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping, Optional


JsonObject = Dict[str, Any]
PULSE_RUNTIME_VERSION = "0.1.0"


def _slugify(value: Any) -> str:
    """Internal helper to slugify."""
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", ".", text)
    text = re.sub(r"\.+", ".", text).strip(".")
    return text or "pulse"


def _titleize(name: str) -> str:
    """Internal helper to titleize."""
    return str(name or "Pulse").replace("_", " ").replace(".", " ").strip().title() or "Pulse"


def derive_pulse_id(
    payload: Mapping[str, Any] | None = None,
    *,
    default_name: Optional[str] = None,
    default_pulse_address: Optional[str] = None,
) -> str:
    """Derive a stable pulse identifier from a runtime payload."""
    payload = payload or {}
    nested = payload.get("pulse_definition")
    if isinstance(nested, Mapping) and nested.get("id"):
        return str(nested["id"])
    for key in ("pulse_id", "resource_id"):
        if payload.get(key):
            return str(payload[key])
    if payload.get("resource_type") == "pulse_definition" and payload.get("id"):
        return str(payload["id"])

    pulse_address = str(payload.get("pulse_address") or default_pulse_address or "").strip()
    if pulse_address:
        if pulse_address.startswith("plaza://pulse/"):
            suffix = pulse_address.split("plaza://pulse/", 1)[1]
            return f"urn:plaza:pulse:{_slugify(suffix)}"
        return f"urn:plaza:pulse:{_slugify(pulse_address)}"

    pulse_name = str(payload.get("pulse_name") or payload.get("name") or default_name or "").strip()
    return f"urn:plaza:pulse:{_slugify(pulse_name)}"


def build_pulse_definition(
    payload: Mapping[str, Any] | None = None,
    *,
    default_name: Optional[str] = None,
    default_description: Optional[str] = None,
    default_pulse_address: Optional[str] = None,
) -> JsonObject:
    """Build a generic pulse definition from a runtime payload."""
    payload = payload or {}
    if payload.get("pulse_definition") and isinstance(payload.get("pulse_definition"), Mapping):
        payload = dict(payload["pulse_definition"])
    else:
        payload = dict(payload)

    pulse_id = derive_pulse_id(payload, default_name=default_name, default_pulse_address=default_pulse_address)
    pulse_name = str(payload.get("name") or payload.get("pulse_name") or default_name or "default_pulse").strip() or "default_pulse"
    description = str(payload.get("description") or default_description or _titleize(pulse_name)).strip()
    concept = dict(payload.get("concept") or {})
    if not concept.get("definition"):
        concept["definition"] = description or _titleize(pulse_name)

    interface = dict(payload.get("interface") or {})
    request_schema = dict(payload.get("input_schema") or interface.get("request_schema") or {})
    response_schema = dict(payload.get("output_schema") or interface.get("response_schema") or {})
    interface.setdefault("schema_language", "json-schema-2020-12")
    interface["request_schema"] = request_schema
    interface["response_schema"] = response_schema

    definition: JsonObject = {
        "pds_version": str(payload.get("pds_version") or PULSE_RUNTIME_VERSION),
        "resource_type": "pulse_definition",
        "id": pulse_id,
        "version": str(payload.get("version") or "1.0.0"),
        "name": pulse_name,
        "title": str(payload.get("title") or _titleize(pulse_name)),
        "description": description,
        "pulse_class": str(payload.get("pulse_class") or "fact"),
        "status": str(payload.get("status") or "stable"),
        "concept": concept,
        "interface": interface,
    }

    for key in ("namespace", "interop", "derivation", "governance", "examples", "extensions"):
        value = payload.get(key)
        if value not in (None, "", [], {}):
            definition[key] = value

    return definition


def normalize_runtime_pulse_entry(
    payload: Mapping[str, Any] | None = None,
    *,
    default_name: Optional[str] = None,
    default_description: Optional[str] = None,
    default_pulse_address: Optional[str] = None,
) -> JsonObject:
    """Normalize a runtime pulse record."""
    runtime = dict(payload or {})
    definition = build_pulse_definition(
        runtime,
        default_name=default_name,
        default_description=default_description,
        default_pulse_address=default_pulse_address,
    )
    interface = dict(definition.get("interface") or {})
    request_schema = dict(runtime.get("input_schema") or interface.get("request_schema") or {})
    response_schema = dict(runtime.get("output_schema") or interface.get("response_schema") or {})
    pulse_name = str(runtime.get("pulse_name") or runtime.get("name") or definition.get("name") or default_name or "").strip()

    runtime["pulse_definition"] = definition
    runtime["pulse_id"] = definition["id"]
    runtime["name"] = str(runtime.get("name") or definition.get("name") or pulse_name or default_name or "default_pulse")
    runtime["pulse_name"] = pulse_name or runtime["name"]
    runtime["title"] = str(runtime.get("title") or definition.get("title") or _titleize(runtime["name"]))
    runtime["description"] = str(runtime.get("description") or definition.get("description") or default_description or "")
    runtime["pulse_address"] = runtime.get("pulse_address") or default_pulse_address or ""
    runtime["input_schema"] = request_schema
    runtime["output_schema"] = response_schema
    runtime["interface"] = interface
    runtime["concept"] = dict(definition.get("concept") or {})
    runtime["resource_type"] = "pulse_definition"
    runtime["pds_version"] = definition.get("pds_version", PULSE_RUNTIME_VERSION)
    runtime["status"] = runtime.get("status") or definition.get("status")
    runtime["pulse_class"] = runtime.get("pulse_class") or definition.get("pulse_class")
    return runtime


def normalize_pulse_pair_entry(
    payload: Mapping[str, Any] | None = None,
    *,
    pulser_id: str,
    pulser_name: str,
    pulser_address: str,
    default_name: Optional[str] = None,
    default_description: Optional[str] = None,
    default_pulse_address: Optional[str] = None,
) -> JsonObject:
    """Normalize a pulse-pulser directory row."""
    runtime = normalize_runtime_pulse_entry(
        payload,
        default_name=default_name,
        default_description=default_description,
        default_pulse_address=default_pulse_address,
    )
    pulse_definition = dict(runtime.get("pulse_definition") or {})
    sample_parameters = runtime.get("test_data")
    if not isinstance(sample_parameters, Mapping) or not sample_parameters:
        nested_sample_parameters = pulse_definition.get("test_data")
        if isinstance(nested_sample_parameters, Mapping) and nested_sample_parameters:
            sample_parameters = nested_sample_parameters
    if isinstance(sample_parameters, Mapping) and sample_parameters:
        pulse_definition["test_data"] = dict(sample_parameters)
    test_data_path = runtime.get("test_data_path") or pulse_definition.get("test_data_path")
    if str(test_data_path or "").strip():
        pulse_definition["test_data_path"] = str(test_data_path)
    row: JsonObject = {
        "pulse_id": runtime["pulse_id"],
        "pulse_name": runtime.get("pulse_name") or runtime.get("name"),
        "pulse_address": runtime.get("pulse_address") or default_pulse_address or "",
        "pulse_definition": pulse_definition,
        "input_schema": dict(runtime.get("input_schema") or {}),
        "pulser_id": pulser_id,
        "pulser_name": pulser_name,
        "pulser_address": pulser_address,
    }
    for key in ("is_complete", "completion_status", "completion_errors", "status"):
        if key in runtime:
            row[key] = runtime[key]
    return row


__all__ = [
    "PULSE_RUNTIME_VERSION",
    "JsonObject",
    "build_pulse_definition",
    "derive_pulse_id",
    "normalize_pulse_pair_entry",
    "normalize_runtime_pulse_entry",
]
