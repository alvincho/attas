"""
Typed data models for `attas.pds.models`.

Attas layers finance-oriented pulse definitions, validation rules, and personal-agent
workflows on top of the shared runtimes. Within Attas, this area focuses on pulse-
directory schemas, catalog loading, runtime normalization, and validation.

Key definitions include `BasePDSResource`, `CatalogItem`, `Concept`, and
`parse_pds_resource`, which provide the main entry points used by neighboring modules
and tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union


PDS_VERSION = "0.1.0"

ResourceType = Literal[
    "pulse_definition",
    "pulse_profile",
    "pulse_mapping",
    "pulse_catalog",
]
PulseClass = Literal["fact", "analytic", "artifact"]
PulseStatus = Literal["draft", "stable", "deprecated"]
RelationType = Literal[
    "equivalent_match",
    "close_match",
    "broader_than",
    "narrower_than",
    "derived_from",
    "implements",
    "related",
]
JsonObject = Dict[str, Any]


def _split_known_fields(payload: JsonObject, known_fields: List[str]) -> JsonObject:
    """Internal helper for split known fields."""
    return {key: value for key, value in payload.items() if key not in known_fields}


@dataclass(frozen=True)
class ExternalRef:
    """Represent an external ref."""
    system: str
    ref: str
    relation: RelationType
    confidence: Optional[float] = None
    notes: Optional[str] = None
    extra_fields: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class Concept:
    """Represent a concept."""
    definition: str
    entity_types: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    dimensions: List[str] = field(default_factory=list)
    identifiers: List[str] = field(default_factory=list)
    units: JsonObject = field(default_factory=dict)
    time_semantics: JsonObject = field(default_factory=dict)
    quality_rules: List[str] = field(default_factory=list)
    extra_fields: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class PulseInterface:
    """Represent a pulse interface."""
    schema_language: str
    request_schema: JsonObject
    response_schema: JsonObject
    extra_fields: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class Interop:
    """Represent an interop."""
    aliases: List[str] = field(default_factory=list)
    external_refs: List[ExternalRef] = field(default_factory=list)
    related_pulses: List[str] = field(default_factory=list)
    extra_fields: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class Derivation:
    """Represent a derivation."""
    input_pulse_ids: List[str] = field(default_factory=list)
    method_type: Optional[str] = None
    method_ref: Optional[str] = None
    parameters_schema: JsonObject = field(default_factory=dict)
    notes: Optional[str] = None
    extra_fields: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class Governance:
    """Represent a governance."""
    owner: Optional[str] = None
    license: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    deprecated_by: Optional[str] = None
    change_notes: Optional[str] = None
    extra_fields: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class CatalogItem:
    """Represent a catalog item."""
    ref: str


@dataclass(frozen=True)
class BasePDSResource:
    """Represent a base PDS resource."""
    pds_version: str
    resource_type: ResourceType
    id: str
    version: str


@dataclass(frozen=True)
class PulseDefinition(BasePDSResource):
    """Represent a pulse definition."""
    title: str
    description: str
    pulse_class: PulseClass
    status: PulseStatus
    concept: Concept
    interface: PulseInterface
    namespace: Optional[str] = None
    name: Optional[str] = None
    interop: Optional[Interop] = None
    derivation: Optional[Derivation] = None
    governance: Optional[Governance] = None
    examples: List[Any] = field(default_factory=list)
    extensions: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class PulseProfile(BasePDSResource):
    """Represent a pulse profile."""
    base_pulse_id: str
    application: Optional[str] = None
    constraints: JsonObject = field(default_factory=dict)
    defaults: JsonObject = field(default_factory=dict)
    presentation: JsonObject = field(default_factory=dict)
    extensions: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class PulseMapping(BasePDSResource):
    """Represent a pulse mapping."""
    pulse_id: str
    source_system: str
    relation: RelationType
    source_ref: JsonObject = field(default_factory=dict)
    mapping_type: Optional[str] = None
    field_map: JsonObject = field(default_factory=dict)
    transforms: List[JsonObject] = field(default_factory=list)
    tests: List[JsonObject] = field(default_factory=list)
    coverage: Optional[str] = None
    confidence: Optional[float] = None
    notes: Optional[str] = None
    extensions: JsonObject = field(default_factory=dict)


@dataclass(frozen=True)
class PulseCatalog(BasePDSResource):
    """Represent a pulse catalog."""
    items: List[CatalogItem]
    title: Optional[str] = None
    description: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    extensions: JsonObject = field(default_factory=dict)


PDSResource = Union[PulseDefinition, PulseProfile, PulseMapping, PulseCatalog]


@dataclass(frozen=True)
class LoadedPDSResource:
    """Represent a loaded PDS resource."""
    resource: PDSResource
    raw_data: JsonObject
    source_path: Path


def _parse_external_ref(payload: JsonObject) -> ExternalRef:
    """Internal helper to parse the external ref."""
    return ExternalRef(
        system=str(payload["system"]),
        ref=str(payload["ref"]),
        relation=str(payload["relation"]),
        confidence=payload.get("confidence"),
        notes=payload.get("notes"),
        extra_fields=_split_known_fields(payload, ["system", "ref", "relation", "confidence", "notes"]),
    )


def _parse_concept(payload: JsonObject) -> Concept:
    """Internal helper to parse the concept."""
    return Concept(
        definition=str(payload["definition"]),
        entity_types=list(payload.get("entity_types") or []),
        tags=list(payload.get("tags") or []),
        dimensions=list(payload.get("dimensions") or []),
        identifiers=list(payload.get("identifiers") or []),
        units=dict(payload.get("units") or {}),
        time_semantics=dict(payload.get("time_semantics") or {}),
        quality_rules=list(payload.get("quality_rules") or []),
        extra_fields=_split_known_fields(
            payload,
            [
                "definition",
                "entity_types",
                "tags",
                "dimensions",
                "identifiers",
                "units",
                "time_semantics",
                "quality_rules",
            ],
        ),
    )


def _parse_interface(payload: JsonObject) -> PulseInterface:
    """Internal helper to parse the interface."""
    return PulseInterface(
        schema_language=str(payload["schema_language"]),
        request_schema=dict(payload.get("request_schema") or {}),
        response_schema=dict(payload.get("response_schema") or {}),
        extra_fields=_split_known_fields(payload, ["schema_language", "request_schema", "response_schema"]),
    )


def _parse_interop(payload: JsonObject) -> Interop:
    """Internal helper to parse the interop."""
    refs = [_parse_external_ref(item) for item in payload.get("external_refs") or [] if isinstance(item, dict)]
    return Interop(
        aliases=list(payload.get("aliases") or []),
        external_refs=refs,
        related_pulses=list(payload.get("related_pulses") or []),
        extra_fields=_split_known_fields(payload, ["aliases", "external_refs", "related_pulses"]),
    )


def _parse_derivation(payload: JsonObject) -> Derivation:
    """Internal helper to parse the derivation."""
    return Derivation(
        input_pulse_ids=list(payload.get("input_pulse_ids") or []),
        method_type=payload.get("method_type"),
        method_ref=payload.get("method_ref"),
        parameters_schema=dict(payload.get("parameters_schema") or {}),
        notes=payload.get("notes"),
        extra_fields=_split_known_fields(
            payload,
            ["input_pulse_ids", "method_type", "method_ref", "parameters_schema", "notes"],
        ),
    )


def _parse_governance(payload: JsonObject) -> Governance:
    """Internal helper to parse the governance."""
    return Governance(
        owner=payload.get("owner"),
        license=payload.get("license"),
        created_at=payload.get("created_at"),
        updated_at=payload.get("updated_at"),
        deprecated_by=payload.get("deprecated_by"),
        change_notes=payload.get("change_notes"),
        extra_fields=_split_known_fields(
            payload,
            ["owner", "license", "created_at", "updated_at", "deprecated_by", "change_notes"],
        ),
    )


def parse_pds_resource(payload: JsonObject) -> PDSResource:
    """Parse the PDS resource."""
    resource_type = str(payload["resource_type"])
    common = {
        "pds_version": str(payload["pds_version"]),
        "resource_type": resource_type,
        "id": str(payload["id"]),
        "version": str(payload["version"]),
    }

    if resource_type == "pulse_definition":
        return PulseDefinition(
            **common,
            namespace=payload.get("namespace"),
            name=payload.get("name"),
            title=str(payload["title"]),
            description=str(payload["description"]),
            pulse_class=str(payload["pulse_class"]),
            status=str(payload["status"]),
            concept=_parse_concept(dict(payload["concept"])),
            interface=_parse_interface(dict(payload["interface"])),
            interop=_parse_interop(dict(payload["interop"])) if isinstance(payload.get("interop"), dict) else None,
            derivation=_parse_derivation(dict(payload["derivation"])) if isinstance(payload.get("derivation"), dict) else None,
            governance=_parse_governance(dict(payload["governance"])) if isinstance(payload.get("governance"), dict) else None,
            examples=list(payload.get("examples") or []),
            extensions=dict(payload.get("extensions") or {}),
        )

    if resource_type == "pulse_profile":
        return PulseProfile(
            **common,
            base_pulse_id=str(payload["base_pulse_id"]),
            application=payload.get("application"),
            constraints=dict(payload.get("constraints") or {}),
            defaults=dict(payload.get("defaults") or {}),
            presentation=dict(payload.get("presentation") or {}),
            extensions=dict(payload.get("extensions") or {}),
        )

    if resource_type == "pulse_mapping":
        return PulseMapping(
            **common,
            pulse_id=str(payload["pulse_id"]),
            source_system=str(payload["source_system"]),
            source_ref=dict(payload.get("source_ref") or {}),
            relation=str(payload["relation"]),
            mapping_type=payload.get("mapping_type"),
            field_map=dict(payload.get("field_map") or {}),
            transforms=[dict(item) for item in payload.get("transforms") or [] if isinstance(item, dict)],
            tests=[dict(item) for item in payload.get("tests") or [] if isinstance(item, dict)],
            coverage=payload.get("coverage"),
            confidence=payload.get("confidence"),
            notes=payload.get("notes"),
            extensions=dict(payload.get("extensions") or {}),
        )

    if resource_type == "pulse_catalog":
        return PulseCatalog(
            **common,
            title=payload.get("title"),
            description=payload.get("description"),
            imports=list(payload.get("imports") or []),
            items=[CatalogItem(ref=str(item["ref"])) for item in payload.get("items") or [] if isinstance(item, dict)],
            extensions=dict(payload.get("extensions") or {}),
        )

    raise ValueError(f"Unsupported PDS resource_type '{resource_type}'")
