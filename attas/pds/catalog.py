"""
Catalog loading and lookup helpers for `attas.pds.catalog`.

Attas layers finance-oriented pulse definitions, validation rules, and personal-agent
workflows on top of the shared runtimes. Within Attas, this area focuses on pulse-
directory schemas, catalog loading, runtime normalization, and validation.

Key definitions include `InvalidPDSResource`, `PDSCatalogBundle`, `PDSResourceIndex`,
`build_pds_resource_index`, and `load_catalog_bundle`, which provide the main entry
points used by neighboring modules and tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from attas.pds.models import (
    LoadedPDSResource,
    PulseCatalog,
    PulseDefinition,
    PulseMapping,
    PulseProfile,
)
from attas.pds.validator import PDSDiagnostic, PDSValidationError, load_validated_pds_resource


@dataclass(frozen=True)
class InvalidPDSResource:
    """Represent an invalid PDS resource."""
    resource_id: str
    source_path: Path
    diagnostics: List[PDSDiagnostic]


@dataclass
class PDSResourceIndex:
    """Represent a PDS resource index."""
    resources_by_id: Dict[str, LoadedPDSResource] = field(default_factory=dict)
    invalid_by_id: Dict[str, InvalidPDSResource] = field(default_factory=dict)
    diagnostics: List[PDSDiagnostic] = field(default_factory=list)


@dataclass
class PDSCatalogBundle:
    """Represent a PDS catalog bundle."""
    catalog: LoadedPDSResource
    definitions: Dict[str, LoadedPDSResource] = field(default_factory=dict)
    profiles: Dict[str, LoadedPDSResource] = field(default_factory=dict)
    mappings: Dict[str, LoadedPDSResource] = field(default_factory=dict)
    catalogs: Dict[str, LoadedPDSResource] = field(default_factory=dict)
    imports: Dict[str, LoadedPDSResource] = field(default_factory=dict)
    unresolved_refs: List[str] = field(default_factory=list)
    unresolved_imports: List[str] = field(default_factory=list)
    invalid_refs: List[str] = field(default_factory=list)
    diagnostics: List[PDSDiagnostic] = field(default_factory=list)

    @property
    def resolved_resources_by_id(self) -> Dict[str, LoadedPDSResource]:
        """Return the resolved resources by ID."""
        grouped: Dict[str, LoadedPDSResource] = {}
        grouped.update(self.definitions)
        grouped.update(self.profiles)
        grouped.update(self.mappings)
        grouped.update(self.catalogs)
        return grouped


def _candidate_json_files(directory: Path) -> List[Path]:
    """Internal helper for candidate JSON files."""
    return sorted(path for path in directory.glob("*.json") if path.is_file())


def _read_resource_id(path: Path) -> Optional[str]:
    """Internal helper to read the resource ID."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return None
    if isinstance(payload, dict) and isinstance(payload.get("id"), str):
        return str(payload["id"])
    return None


def build_pds_resource_index(search_directories: Iterable[Path | str]) -> PDSResourceIndex:
    """Build the PDS resource index."""
    index = PDSResourceIndex()
    seen_paths: Set[Path] = set()
    for directory_value in search_directories:
        directory = Path(directory_value).resolve()
        if not directory.exists():
            index.diagnostics.append(
                PDSDiagnostic(
                    code="missing_search_directory",
                    message=f"Search directory does not exist: {directory}",
                    json_path="$",
                    file_path=str(directory),
                )
            )
            continue
        for resource_path in _candidate_json_files(directory):
            if resource_path in seen_paths:
                continue
            seen_paths.add(resource_path)
            try:
                loaded = load_validated_pds_resource(resource_path)
            except PDSValidationError as exc:
                resource_id = _read_resource_id(resource_path)
                if resource_id:
                    index.invalid_by_id[resource_id] = InvalidPDSResource(
                        resource_id=resource_id,
                        source_path=resource_path,
                        diagnostics=list(exc.diagnostics),
                    )
                index.diagnostics.extend(exc.diagnostics)
                continue
            existing = index.resources_by_id.get(loaded.resource.id)
            if existing is not None:
                index.diagnostics.append(
                    PDSDiagnostic(
                        code="duplicate_resource_id",
                        message=f"Duplicate PDS resource id '{loaded.resource.id}' encountered",
                        json_path="$.id",
                        file_path=str(resource_path),
                        ref=loaded.resource.id,
                    )
                )
                continue
            index.resources_by_id[loaded.resource.id] = loaded
    return index


def _append_resolved_resource(bundle: PDSCatalogBundle, loaded: LoadedPDSResource) -> None:
    """Internal helper to append the resolved resource."""
    resource = loaded.resource
    if isinstance(resource, PulseDefinition):
        bundle.definitions[resource.id] = loaded
    elif isinstance(resource, PulseProfile):
        bundle.profiles[resource.id] = loaded
    elif isinstance(resource, PulseMapping):
        bundle.mappings[resource.id] = loaded
    elif isinstance(resource, PulseCatalog):
        bundle.catalogs[resource.id] = loaded


def load_catalog_bundle(
    catalog_path: Path | str,
    *,
    search_directories: Optional[Iterable[Path | str]] = None,
    resolve_imports: bool = True,
) -> PDSCatalogBundle:
    """Load the catalog bundle."""
    loaded_catalog = load_validated_pds_resource(catalog_path)
    if not isinstance(loaded_catalog.resource, PulseCatalog):
        raise TypeError(f"{loaded_catalog.source_path} is not a pulse_catalog")

    directories = list(search_directories or [loaded_catalog.source_path.parent])
    index = build_pds_resource_index(directories)
    bundle = PDSCatalogBundle(catalog=loaded_catalog, diagnostics=list(index.diagnostics))

    seen_refs: Set[str] = set()
    for item in loaded_catalog.resource.items:
        ref = item.ref
        if ref in seen_refs:
            continue
        seen_refs.add(ref)
        resolved = index.resources_by_id.get(ref)
        if resolved is not None:
            _append_resolved_resource(bundle, resolved)
            continue
        if ref in index.invalid_by_id:
            bundle.invalid_refs.append(ref)
            bundle.diagnostics.extend(index.invalid_by_id[ref].diagnostics)
            bundle.diagnostics.append(
                PDSDiagnostic(
                    code="invalid_catalog_ref",
                    message=f"Catalog item ref '{ref}' resolves to an invalid PDS resource",
                    json_path="$.items",
                    file_path=str(loaded_catalog.source_path),
                    ref=ref,
                )
            )
            continue
        bundle.unresolved_refs.append(ref)
        bundle.diagnostics.append(
            PDSDiagnostic(
                code="unresolved_catalog_ref",
                message=f"Catalog item ref '{ref}' could not be resolved",
                json_path="$.items",
                file_path=str(loaded_catalog.source_path),
                ref=ref,
            )
        )

    if resolve_imports:
        seen_imports: Set[str] = set()
        for ref in loaded_catalog.resource.imports:
            if ref in seen_imports:
                continue
            seen_imports.add(ref)
            resolved = index.resources_by_id.get(ref)
            if resolved is None:
                bundle.unresolved_imports.append(ref)
                bundle.diagnostics.append(
                    PDSDiagnostic(
                        code="unresolved_catalog_import",
                        message=f"Catalog import '{ref}' could not be resolved",
                        json_path="$.imports",
                        file_path=str(loaded_catalog.source_path),
                        ref=ref,
                    )
                )
                continue
            if not isinstance(resolved.resource, PulseCatalog):
                bundle.diagnostics.append(
                    PDSDiagnostic(
                        code="invalid_catalog_import",
                        message=f"Catalog import '{ref}' resolved to '{resolved.resource.resource_type}', expected 'pulse_catalog'",
                        json_path="$.imports",
                        file_path=str(loaded_catalog.source_path),
                        ref=ref,
                    )
                )
                continue
            bundle.imports[ref] = resolved

    return bundle


def resolve_catalog_by_id(
    catalog_id: str,
    directory: Path | str,
    *,
    resolve_imports: bool = True,
) -> PDSCatalogBundle:
    """Resolve the catalog by ID."""
    index = build_pds_resource_index([directory])
    loaded = index.resources_by_id.get(catalog_id)
    if loaded is None:
        raise KeyError(f"PDS catalog '{catalog_id}' was not found in {Path(directory).resolve()}")
    if not isinstance(loaded.resource, PulseCatalog):
        raise TypeError(f"PDS resource '{catalog_id}' is not a pulse_catalog")
    return load_catalog_bundle(
        loaded.source_path,
        search_directories=[Path(directory).resolve()],
        resolve_imports=resolve_imports,
    )
