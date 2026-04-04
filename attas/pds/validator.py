"""
Validation and normalization helpers for `attas.pds.validator`.

Attas layers finance-oriented pulse definitions, validation rules, and personal-agent
workflows on top of the shared runtimes. Within Attas, this area focuses on pulse-
directory schemas, catalog loading, runtime normalization, and validation.

Key definitions include `PDSDiagnostic`, `PDSValidationError`, `load_pds_json`,
`load_pds_schema`, and `load_validated_pds_resource`, which provide the main entry
points used by neighboring modules and tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from attas.pds.models import JsonObject, LoadedPDSResource, PDSResource, parse_pds_resource


@dataclass(frozen=True)
class PDSDiagnostic:
    """Represent a PDS diagnostic."""
    code: str
    message: str
    json_path: str
    file_path: Optional[str] = None
    ref: Optional[str] = None


class PDSValidationError(ValueError):
    """Exception raised for PDS validation failures."""
    def __init__(self, message: str, diagnostics: List[PDSDiagnostic]):
        """Initialize the PDS validation error."""
        super().__init__(message)
        self.diagnostics = diagnostics


def _schema_file_path() -> Path:
    """Internal helper to return the schema file path."""
    return Path(__file__).resolve().parents[1] / "schemas" / "pds.schema.json"


@lru_cache(maxsize=1)
def load_pds_schema() -> JsonObject:
    """Load the PDS schema."""
    with _schema_file_path().open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _select_schema_branch(schema: JsonObject, data: Any) -> JsonObject:
    """Internal helper for select schema branch."""
    if isinstance(data, dict):
        resource_type = data.get("resource_type")
        branch = schema.get("$defs", {}).get(str(resource_type))
        if isinstance(branch, dict):
            scoped_branch = dict(branch)
            scoped_branch["$defs"] = dict(schema.get("$defs") or {})
            if "$schema" in schema:
                scoped_branch["$schema"] = schema["$schema"]
            return scoped_branch
    return schema


def _format_error_path(error: ValidationError) -> str:
    """Internal helper to format the error path."""
    parts = ["$"]
    for part in error.absolute_path:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            parts.append(f".{part}")
    return "".join(parts)


def _flatten_errors(error: ValidationError) -> List[ValidationError]:
    """Internal helper for flatten errors."""
    if not error.context:
        return [error]
    flattened: List[ValidationError] = []
    for child in error.context:
        flattened.extend(_flatten_errors(child))
    return flattened


def _sort_key(error: ValidationError) -> tuple[int, str, str]:
    """Internal helper to return the sort key."""
    path_text = _format_error_path(error)
    return (len(list(error.absolute_path)), path_text, error.message)


def validate_pds_data(data: Any, *, file_path: Optional[Path] = None) -> None:
    """Validate the PDS data."""
    schema = load_pds_schema()
    validator = Draft202012Validator(_select_schema_branch(schema, data))
    raw_errors = list(validator.iter_errors(data))
    if not raw_errors:
        return

    leaf_errors: List[ValidationError] = []
    for error in raw_errors:
        leaf_errors.extend(_flatten_errors(error))
    unique_errors = sorted({(err.message, tuple(err.absolute_path), err.validator): err for err in leaf_errors}.values(), key=_sort_key)

    diagnostics = [
        PDSDiagnostic(
            code="schema_validation_error",
            message=error.message,
            json_path=_format_error_path(error),
            file_path=str(file_path) if file_path else None,
        )
        for error in unique_errors
    ]
    source = f" in {file_path}" if file_path else ""
    raise PDSValidationError(f"PDS validation failed{source}", diagnostics)


def load_pds_json(path: Path | str) -> JsonObject:
    """Load the PDS JSON."""
    json_path = Path(path)
    with json_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise PDSValidationError(
            f"PDS resource at {json_path} must be a JSON object",
            [PDSDiagnostic(code="invalid_json_type", message="Top-level JSON value must be an object", json_path="$", file_path=str(json_path))],
        )
    return payload


def parse_validated_pds_data(data: Dict[str, Any]) -> PDSResource:
    """Parse the validated PDS data."""
    validate_pds_data(data)
    return parse_pds_resource(data)


def load_validated_pds_resource(path: Path | str) -> LoadedPDSResource:
    """Load the validated PDS resource."""
    resource_path = Path(path).resolve()
    payload = load_pds_json(resource_path)
    validate_pds_data(payload, file_path=resource_path)
    return LoadedPDSResource(
        resource=parse_pds_resource(payload),
        raw_data=payload,
        source_path=resource_path,
    )
