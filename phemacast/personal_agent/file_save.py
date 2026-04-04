"""
File persistence helpers for `phemacast.personal_agent.file_save`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the personal_agent package powers the file-
backed personal research workbench and its web UI.

Important callables in this file include `load_json_file`, `save_json_file`, and
`list_json_files`, which capture the primary workflow implemented by the module.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_SAVE_DIR = BASE_DIR / "storage" / "saved_files"


def _resolve_save_directory(directory: str | None = None) -> Path:
    """Internal helper to resolve the save directory."""
    raw = str(directory or "").strip()
    target = Path(raw).expanduser() if raw else DEFAULT_SAVE_DIR
    return target.resolve()


def _slugify_file_stem(value: str) -> str:
    """Internal helper for slugify file stem."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
    return slug[:72] or "saved-result"


def _default_file_name(title: str | None = None) -> str:
    """Internal helper to return the default file name."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{_slugify_file_stem(title or 'saved-result')}-{timestamp}.json"


def _normalize_file_name(file_name: str | None = None, title: str | None = None) -> str:
    """Internal helper to normalize the file name."""
    candidate = Path(str(file_name or "").strip()).name
    if not candidate:
        candidate = _default_file_name(title)
    stem = _slugify_file_stem(Path(candidate).stem)
    suffix = Path(candidate).suffix.lower() or ".json"
    if suffix != ".json":
        suffix = ".json"
    return f"{stem}{suffix}"


def _json_file_record(path: Path, base_directory: Path) -> dict:
    """Internal helper for JSON file record."""
    stat = path.stat()
    try:
        relative_path = str(path.relative_to(base_directory))
    except ValueError:
        relative_path = path.name
    return {
        "directory": str(base_directory),
        "file_name": path.name,
        "relative_path": relative_path,
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
    }


def _string_sort_key(value: str) -> str:
    """Internal helper to return the string sort key."""
    return str(value or "").lower()


def save_json_file(
    content: Any,
    *,
    directory: str | None = None,
    file_name: str | None = None,
    title: str | None = None,
) -> dict:
    """Save the JSON file."""
    target_dir = _resolve_save_directory(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = _normalize_file_name(file_name=file_name, title=title)
    target_path = target_dir / target_name
    serialized = json.dumps(content, indent=2, ensure_ascii=False)
    target_path.write_text(f"{serialized}\n", encoding="utf-8")
    return {
        "status": "saved",
        "directory": str(target_dir),
        "file_name": target_path.name,
        "path": str(target_path),
        "size_bytes": len(serialized.encode("utf-8")),
    }


def load_json_file(
    *,
    directory: str | None = None,
    file_name: str | None = None,
    title: str | None = None,
) -> dict:
    """Load the JSON file."""
    target_dir = _resolve_save_directory(directory)
    target_name = _normalize_file_name(file_name=file_name, title=title)
    target_path = target_dir / target_name
    if not target_path.is_file():
        raise FileNotFoundError(f"File '{target_name}' was not found in '{target_dir}'.")
    raw = target_path.read_text(encoding="utf-8")
    return {
        "status": "loaded",
        "directory": str(target_dir),
        "file_name": target_path.name,
        "path": str(target_path),
        "size_bytes": target_path.stat().st_size,
        "content": json.loads(raw),
    }


def list_json_files(
    *,
    directory: str | None = None,
    recursive: bool = False,
) -> list[dict]:
    """List the JSON files."""
    target_dir = _resolve_save_directory(directory)
    if not target_dir.exists():
        return []
    if not target_dir.is_dir():
        raise NotADirectoryError(f"'{target_dir}' is not a directory.")
    pattern = "**/*.json" if recursive else "*.json"
    files = [
        _json_file_record(path, target_dir)
        for path in target_dir.glob(pattern)
        if path.is_file()
    ]
    files.sort(key=lambda entry: _string_sort_key(entry.get("relative_path") or entry.get("file_name") or ""))
    return files


__all__ = ["DEFAULT_SAVE_DIR", "list_json_files", "load_json_file", "save_json_file"]
