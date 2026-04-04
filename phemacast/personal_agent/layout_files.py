"""
Layout and filesystem helpers for `phemacast.personal_agent.layout_files`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the personal_agent package powers the file-
backed personal research workbench and its web UI.

Important callables in this file include `save_layout_file`, `normalize_layout_kind`,
and `list_layout_files`, which capture the primary workflow implemented by the module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_LAYOUTS_DIR = BASE_DIR / "storage" / "layouts"
VALID_LAYOUT_KINDS = {"browser", "mind_map", "workspace"}


def _resolve_layout_root() -> Path:
    """Internal helper to resolve the layout root."""
    configured = os.environ.get("PHEMACAST_PERSONAL_AGENT_LAYOUTS_PATH") or str(DEFAULT_LAYOUTS_DIR)
    return Path(configured).expanduser().resolve()


def normalize_layout_kind(kind: str) -> str:
    """Normalize the layout kind."""
    normalized = str(kind or "").strip().lower()
    if normalized not in VALID_LAYOUT_KINDS:
        raise ValueError(f"Unsupported layout kind '{kind}'.")
    return normalized


def _layout_dir(kind: str) -> Path:
    """Internal helper for layout dir."""
    directory = _resolve_layout_root() / normalize_layout_kind(kind)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _slugify(value: str) -> str:
    """Internal helper for slugify."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug[:72] or "layout"


def _stable_layout_id(name: str, current_id: str | None = None) -> str:
    """Internal helper for stable layout ID."""
    explicit = _slugify(str(current_id or ""))
    if explicit and explicit != "layout":
      return explicit
    normalized_name = str(name or "").strip() or "layout"
    digest = hashlib.sha1(normalized_name.encode("utf-8")).hexdigest()[:8]
    return f"{_slugify(normalized_name)}-{digest}"


def _layout_saved_at(value: str | None = None) -> str:
    """Internal helper for layout saved at."""
    return str(value or datetime.now(timezone.utc).isoformat())


def _layout_file_path(kind: str, name: str, current_id: str | None = None) -> Path:
    """Internal helper to return the layout file path."""
    layout_id = _stable_layout_id(name, current_id)
    return _layout_dir(kind) / f"{layout_id}.json"


def _normalize_layout_document(kind: str, payload: dict, source_path: Path | None = None) -> dict:
    """Internal helper to normalize the layout document."""
    name = str(payload.get("name") or "").strip()
    if not name:
        raise ValueError("Layout name is required.")
    normalized_kind = normalize_layout_kind(kind)
    layout_id = _stable_layout_id(name, payload.get("id"))
    document = dict(payload)
    document["id"] = layout_id
    document["kind"] = normalized_kind
    document["name"] = name
    document["savedAt"] = _layout_saved_at(document.get("savedAt"))
    if source_path is not None:
        document["fileName"] = source_path.name
        document["path"] = str(source_path.resolve())
    return document


def list_layout_files(kind: str) -> list[dict]:
    """List the layout files."""
    normalized_kind = normalize_layout_kind(kind)
    entries: list[dict] = []
    for path in sorted(_layout_dir(normalized_kind).glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        try:
            entries.append(_normalize_layout_document(normalized_kind, payload, source_path=path))
        except ValueError:
            continue
    return sorted(entries, key=lambda entry: (str(entry.get("savedAt") or ""), str(entry.get("name") or "")), reverse=True)


def save_layout_file(kind: str, payload: dict) -> dict:
    """Save the layout file."""
    if not isinstance(payload, dict):
        raise ValueError("Layout payload must be a JSON object.")
    normalized_kind = normalize_layout_kind(kind)
    document = _normalize_layout_document(normalized_kind, payload)
    path = _layout_file_path(normalized_kind, document["name"], document["id"])
    serialized = dict(document)
    serialized.pop("fileName", None)
    serialized.pop("path", None)
    path.write_text(json.dumps(serialized, indent=2, ensure_ascii=False), encoding="utf-8")
    return _normalize_layout_document(normalized_kind, serialized, source_path=path)
