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


def _normalize_suffix(value: str | None, default: str = ".json") -> str:
    """Internal helper to normalize a file suffix."""
    candidate = str(value or default or "").strip().lower() or default
    if not candidate.startswith("."):
        candidate = f".{candidate}"
    return candidate


def _default_file_name(title: str | None = None, *, suffix: str = ".json") -> str:
    """Internal helper to return the default file name."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{_slugify_file_stem(title or 'saved-result')}-{timestamp}{_normalize_suffix(suffix)}"


def _normalize_file_name(
    file_name: str | None = None,
    title: str | None = None,
    *,
    default_suffix: str = ".json",
    allowed_suffixes: set[str] | None = None,
) -> str:
    """Internal helper to normalize the file name."""
    candidate = Path(str(file_name or "").strip()).name
    if not candidate:
        candidate = _default_file_name(title, suffix=default_suffix)
    normalized_default_suffix = _normalize_suffix(default_suffix)
    normalized_allowed_suffixes = {
        _normalize_suffix(item, normalized_default_suffix)
        for item in (allowed_suffixes or {normalized_default_suffix})
    }
    if not normalized_allowed_suffixes:
        normalized_allowed_suffixes = {normalized_default_suffix}
    stem = _slugify_file_stem(Path(candidate).stem)
    suffix = Path(candidate).suffix.lower() or normalized_default_suffix
    if suffix not in normalized_allowed_suffixes:
        suffix = normalized_default_suffix
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


def _save_text_payload(
    content: str,
    *,
    directory: str | None = None,
    file_name: str | None = None,
    title: str | None = None,
    default_suffix: str = ".txt",
    allowed_suffixes: set[str] | None = None,
) -> dict:
    """Internal helper to persist a UTF-8 text file."""
    target_dir = _resolve_save_directory(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = _normalize_file_name(
        file_name=file_name,
        title=title,
        default_suffix=default_suffix,
        allowed_suffixes=allowed_suffixes,
    )
    target_path = target_dir / target_name
    serialized = f"{str(content)}\n"
    target_path.write_text(serialized, encoding="utf-8")
    return {
        "status": "saved",
        "directory": str(target_dir),
        "file_name": target_path.name,
        "path": str(target_path),
        "size_bytes": len(serialized.encode("utf-8")),
    }


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
    target_name = _normalize_file_name(
        file_name=file_name,
        title=title,
        default_suffix=".json",
        allowed_suffixes={".json"},
    )
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
    target_name = _normalize_file_name(
        file_name=file_name,
        title=title,
        default_suffix=".json",
        allowed_suffixes={".json"},
    )
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


def save_text_file(
    content: Any,
    *,
    directory: str | None = None,
    file_name: str | None = None,
    title: str | None = None,
    suffix: str = ".txt",
) -> dict:
    """Save a UTF-8 text file."""
    normalized_suffix = _normalize_suffix(suffix, ".txt")
    return _save_text_payload(
        str(content or ""),
        directory=directory,
        file_name=file_name,
        title=title,
        default_suffix=normalized_suffix,
        allowed_suffixes={normalized_suffix},
    )


def save_markdown_file(
    content: Any,
    *,
    directory: str | None = None,
    file_name: str | None = None,
    title: str | None = None,
) -> dict:
    """Save a Markdown file."""
    return _save_text_payload(
        str(content or ""),
        directory=directory,
        file_name=file_name,
        title=title,
        default_suffix=".md",
        allowed_suffixes={".md", ".markdown"},
    )


def save_bytes_file(
    content: bytes | bytearray,
    *,
    directory: str | None = None,
    file_name: str | None = None,
    title: str | None = None,
    suffix: str = ".bin",
) -> dict:
    """Save a binary file."""
    payload = bytes(content or b"")
    target_dir = _resolve_save_directory(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    normalized_suffix = _normalize_suffix(suffix, ".bin")
    target_name = _normalize_file_name(
        file_name=file_name,
        title=title,
        default_suffix=normalized_suffix,
        allowed_suffixes={normalized_suffix},
    )
    target_path = target_dir / target_name
    target_path.write_bytes(payload)
    return {
        "status": "saved",
        "directory": str(target_dir),
        "file_name": target_path.name,
        "path": str(target_path),
        "size_bytes": len(payload),
    }


__all__ = [
    "DEFAULT_SAVE_DIR",
    "list_json_files",
    "load_json_file",
    "save_bytes_file",
    "save_json_file",
    "save_markdown_file",
    "save_text_file",
]
