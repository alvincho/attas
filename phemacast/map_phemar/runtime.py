"""
Runtime helpers for `phemacast.map_phemar.runtime`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the map_phemar package supports map-oriented
phema execution and its UI/runtime helpers.

Key definitions include `DirectorySelectionCancelled`, `BranchConditionEvaluateRequest`,
`PlazaPaneRunRequest`, `create_embedded_map_phemar`, and `build_map_phemar_bootstrap`,
which provide the main entry points used by neighboring modules and tests.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from prompits.pools.filesystem import FileSystemPool

from phemacast.personal_agent.file_save import list_json_files, load_json_file, save_json_file
from phemacast.personal_agent.plaza import PlazaProxyError, fetch_plaza_catalog, run_plaza_pulser_test


MAP_PHEMAR_BASE_DIR = Path(__file__).resolve().parent
PERSONAL_AGENT_UI_BASE_DIR = Path(__file__).resolve().parents[1] / "personal_agent"
MAP_PHEMAR_STATIC_DIR = MAP_PHEMAR_BASE_DIR / "static"
MAP_PHEMAR_TEMPLATE_DIR = MAP_PHEMAR_BASE_DIR / "templates"
MAP_PHEMAR_SHARED_STATIC_DIR = MAP_PHEMAR_STATIC_DIR
DEFAULT_STORAGE_DIR = Path(__file__).resolve().parents[1] / "storage"
MAP_PHEMAR_STORAGE_DIRECTORY_PARAM = "map_phemar_storage_directory"
MAP_PHEMAR_SETTINGS_SCOPE_PARAM = "map_phemar_settings_scope"
MAP_PHEMAR_STORAGE_SETTINGS_MODE_PARAM = "map_phemar_storage_settings_mode"
MAP_PHEMAR_PREFERENCE_STORAGE_KEY_PARAM = "map_phemar_preference_storage_key"
MAP_PHEMAR_PLAZA_URL_PARAM = "map_phemar_plaza_url"
_BRANCH_SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
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
}


class PlazaPaneRunRequest(BaseModel):
    """Request model for Plaza pane run payloads."""
    plaza_url: str
    pulser_id: str | None = None
    pulser_name: str | None = None
    pulser_address: str | None = None
    practice_id: str | None = None
    pulse_name: str | None = None
    pulse_address: str | None = None
    output_schema: dict | None = None
    input: dict | list | str | int | float | bool | None = None


class BranchConditionEvaluateRequest(BaseModel):
    """Request model for branch condition evaluate payloads."""
    expression: str
    input: dict | list | str | int | float | bool | None = None


class DirectorySelectionCancelled(Exception):
    """Raised when a user closes the native folder picker without choosing a directory."""


def evaluate_branch_condition(expression: str, input_payload: Any) -> bool:
    """Handle evaluate branch condition."""
    expression_text = str(expression or "").strip()
    if not expression_text:
        raise ValueError("Branch condition expression is required.")
    if "__" in expression_text:
        raise ValueError("Branch condition expression may not use double-underscore names.")

    scope = {
        "input_data": input_payload,
        "payload": input_payload,
        "data": input_payload,
        "branch_input": input_payload,
    }
    try:
        compiled = compile(expression_text, "<map_phemar_branch>", "eval")
        result = eval(compiled, {"__builtins__": _BRANCH_SAFE_BUILTINS}, scope)
    except Exception as exc:
        raise ValueError(f"Invalid branch condition: {exc}") from exc
    return bool(result)


_cached_embedded_services: dict[tuple[str, str, str, str], Any] = {}


def _existing_directory_or_parent(value: str) -> Path | None:
    """Internal helper for existing directory or parent."""
    candidate_text = str(value or "").strip()
    if not candidate_text:
        return None
    candidate = Path(candidate_text).expanduser()
    if candidate.is_dir():
        return candidate
    parent = candidate.parent
    return parent if parent and parent.exists() and parent.is_dir() else None


def _apple_script_string(value: str) -> str:
    """Internal helper for apple script string."""
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def select_local_directory(initial_directory: str = "") -> str:
    """Handle select local directory."""
    start_directory = _existing_directory_or_parent(initial_directory)

    if sys.platform == "darwin":
        choose_line = 'set chosenFolder to choose folder with prompt "Select a folder for MapPhemar storage"'
        if start_directory:
            choose_line += f" default location POSIX file {_apple_script_string(str(start_directory))}"
        result = subprocess.run(
            [
                "osascript",
                "-e",
                choose_line,
                "-e",
                "POSIX path of chosenFolder",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            error_text = " ".join(
                part.strip() for part in [result.stderr or "", result.stdout or ""] if part.strip()
            ).lower()
            if "user canceled" in error_text or "user cancelled" in error_text:
                raise DirectorySelectionCancelled()
            raise ValueError("Unable to open the local folder picker.")
        selected = str(result.stdout or "").strip()
        if not selected:
            raise DirectorySelectionCancelled()
        return selected

    try:
        import tkinter as tk
        from tkinter import filedialog
    except Exception as exc:
        raise ValueError("Local folder picker is unavailable on this system.") from exc

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        selected = filedialog.askdirectory(
            initialdir=str(start_directory or ""),
            title="Select a folder for MapPhemar storage",
            parent=root,
        )
    finally:
        root.destroy()
    selected_text = str(selected or "").strip()
    if not selected_text:
        raise DirectorySelectionCancelled()
    return selected_text


def get_map_phemar_asset_version() -> str:
    """Return the map phemar asset version."""
    candidates = [
        MAP_PHEMAR_STATIC_DIR / "map_phemar_app.css",
        MAP_PHEMAR_STATIC_DIR / "map_phemar_app.jsx",
        MAP_PHEMAR_STATIC_DIR / "map_phemar.css",
        MAP_PHEMAR_STATIC_DIR / "map_phemar_shared.js",
        MAP_PHEMAR_TEMPLATE_DIR / "index.html",
        PERSONAL_AGENT_UI_BASE_DIR / "static" / "personal_agent.css",
        PERSONAL_AGENT_UI_BASE_DIR / "static" / "personal_agent.jsx",
        PERSONAL_AGENT_UI_BASE_DIR / "templates" / "index.html",
    ]
    mtimes = [int(path.stat().st_mtime) for path in candidates if path.exists()]
    return str(max(mtimes)) if mtimes else "dev"


def build_map_phemar_bootstrap(
    *,
    agent_name: str,
    plaza_url: str = "",
    storage_label: str = "",
    phema_id: str = "",
    phema_api_prefix: str = "/api/map-phemar/phemas",
    back_href: str = "",
    back_label: str = "",
    settings_scope: str = "map_phemar",
    storage_settings_mode: str = "local",
    default_file_save_local_directory: str = "",
    preference_storage_key: str = "",
) -> dict:
    """Build the map phemar bootstrap."""
    return {
        "meta": {
            "app_mode": "map_phemar",
            "mode": "Diagram-backed Phema editor",
            "profile": "Phema mapping desk",
            "plaza_url": plaza_url or "",
            "agent_name": agent_name or "MapPhemar",
            "back_href": back_href or plaza_url or "",
            "back_label": back_label or ("Open Plaza" if plaza_url else ""),
            "phema_api_prefix": phema_api_prefix or "/api/map-phemar/phemas",
            "initial_phema_id": str(phema_id or ""),
            "map_phemar_settings_scope": str(settings_scope or "map_phemar"),
            "map_phemar_storage_settings_mode": str(storage_settings_mode or "local"),
            "map_phemar_preference_storage_key": str(preference_storage_key or ""),
        },
        "settings": {
            "profile_name": agent_name or "MapPhemar",
            "billing_plan": "Phemacast Phemar",
            "active_storage": storage_label or "Local pool",
            "default_file_save_backend": "filesystem",
            "default_file_save_local_directory": str(default_file_save_local_directory or ""),
        },
        "workspaces": [
            {
                "id": "map-phemar-workspace",
                "name": "MapPhemar",
                "focus": "Diagram editor",
                "description": "Build, save, and run diagram-backed Phemas.",
            }
        ],
    }


def _default_storage_paths() -> Tuple[Path, Path]:
    """Internal helper to return the default storage paths."""
    config_path = Path(
        os.environ.get("PHEMACAST_MAP_PHEMAR_CONFIG_PATH")
        or (DEFAULT_STORAGE_DIR / "map_phemar.phemar")
    ).expanduser()
    pool_path = Path(
        os.environ.get("PHEMACAST_MAP_PHEMAR_POOL_PATH")
        or (DEFAULT_STORAGE_DIR / "map_phemar_pool")
    ).expanduser()
    return config_path.resolve(), pool_path.resolve()


def _storage_paths_for_directory(storage_directory: str | Path) -> Tuple[Path, Path]:
    """Internal helper for storage paths for the directory."""
    root_directory = Path(storage_directory).expanduser().resolve()
    storage_root = root_directory / "map_phemar"
    return (storage_root / "map_phemar.phemar").resolve(), (storage_root / "pool").resolve()


def _storage_directory_for_paths(config_path: Path, pool_path: Path) -> Path:
    """Internal helper to return the storage directory for the paths."""
    if pool_path.name == "pool" and pool_path.parent.name == "map_phemar":
        return pool_path.parent.parent.resolve()
    if pool_path.name == "map_phemar_pool":
        return pool_path.parent.resolve()
    if config_path.name == "map_phemar.phemar" and config_path.parent.name == "map_phemar":
        return config_path.parent.parent.resolve()
    return pool_path.parent.resolve()


def _request_map_phemar_storage_directory(request: Request | None) -> str:
    """Internal helper to request the map phemar storage directory."""
    if request is None:
        return ""
    return str(request.query_params.get(MAP_PHEMAR_STORAGE_DIRECTORY_PARAM) or "").strip()


def _request_map_phemar_settings_scope(request: Request | None) -> str:
    """Internal helper to request the map phemar settings scope."""
    if request is None:
        return ""
    return str(request.query_params.get(MAP_PHEMAR_SETTINGS_SCOPE_PARAM) or "").strip()


def _request_map_phemar_storage_settings_mode(request: Request | None) -> str:
    """Internal helper to request the map phemar storage settings mode."""
    if request is None:
        return ""
    return str(request.query_params.get(MAP_PHEMAR_STORAGE_SETTINGS_MODE_PARAM) or "").strip()


def _request_map_phemar_preference_storage_key(request: Request | None) -> str:
    """Internal helper to request the map phemar preference storage key."""
    if request is None:
        return ""
    return str(request.query_params.get(MAP_PHEMAR_PREFERENCE_STORAGE_KEY_PARAM) or "").strip()


def _request_map_phemar_plaza_url(request: Request | None) -> str:
    """Internal helper to request the map phemar Plaza URL."""
    if request is None:
        return ""
    return str(request.query_params.get(MAP_PHEMAR_PLAZA_URL_PARAM) or "").strip()


def create_embedded_map_phemar(
    *,
    config_path: Path | None = None,
    pool_path: Path | None = None,
    storage_directory: str | Path | None = None,
    agent_name: str = "MapPhemar",
    plaza_url: str = "",
):
    """Create the embedded map phemar."""
    from phemacast.agents.map_phemar import MapPhemarAgent

    if storage_directory is not None and str(storage_directory).strip():
        config_path, pool_path = _storage_paths_for_directory(str(storage_directory))
    elif config_path is None or pool_path is None:
        config_path, pool_path = _default_storage_paths()
    resolved_storage_directory = _storage_directory_for_paths(config_path, pool_path)
    pool = FileSystemPool(
        "map_phemar_pool",
        "Local pool for diagram-backed Phemas managed through the MapPhemar editor.",
        str(pool_path),
    )
    config = {
        "name": agent_name or "MapPhemar",
        "type": "phemacast.agents.map_phemar.MapPhemarAgent",
        "host": "127.0.0.1",
        "port": 0,
        "role": "phemar",
        "tags": ["diagram", "phema", "phemar", "workflow", "map-phemar"],
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "map_phemar_pool",
                "description": "Local pool for diagram-backed Phemas managed through the MapPhemar editor.",
                "root_path": str(pool_path),
            }
        ],
        "phemar": {
            "description": "MapPhemar is a diagram-first Phemar agent that edits, saves, and serves diagram-backed Phemas on Plaza.",
            "tags": ["diagram", "workflow", "map-phemar"],
            "supported_phemas": [],
        },
    }
    if plaza_url:
        config["plaza_url"] = plaza_url
    service = MapPhemarAgent(config=config, config_path=config_path, pool=pool, auto_register=False)
    service._map_phemar_storage_directory = str(resolved_storage_directory)
    return service


def get_map_phemar_service(
    *,
    storage_directory: str | Path | None = None,
    config_path: Path | None = None,
    pool_path: Path | None = None,
    agent_name: str = "MapPhemar",
    plaza_url: str = "",
):
    """Return the map phemar service."""
    if storage_directory is not None and str(storage_directory).strip():
        config_path, pool_path = _storage_paths_for_directory(str(storage_directory))
    elif config_path is None or pool_path is None:
        config_path, pool_path = _default_storage_paths()

    cache_key = (str(config_path), str(pool_path), str(agent_name or "MapPhemar"), str(plaza_url or ""))
    cached = _cached_embedded_services.get(cache_key)
    if cached is None:
        cached = create_embedded_map_phemar(
            config_path=config_path,
            pool_path=pool_path,
            agent_name=agent_name,
            plaza_url=plaza_url,
        )
        _cached_embedded_services[cache_key] = cached
    return cached


def get_embedded_map_phemar():
    """Return the embedded map phemar."""
    return get_map_phemar_service()


def resolve_map_phemar_service_for_request(
    service_resolver: Callable[[], Any],
    request: Request | None = None,
):
    """Resolve the map phemar service for the request."""
    base_service = service_resolver()
    requested_directory = _request_map_phemar_storage_directory(request)
    requested_plaza_url = _request_map_phemar_plaza_url(request)
    if not requested_directory and not requested_plaza_url:
        return base_service
    base_directory = str(getattr(base_service, "_map_phemar_storage_directory", "") or "").strip()
    requested_directory_matches_base = (
        not requested_directory
        or (
            base_directory
            and Path(base_directory).expanduser().resolve() == Path(requested_directory).expanduser().resolve()
        )
    )
    requested_plaza_matches_base = not requested_plaza_url or requested_plaza_url == (getattr(base_service, "plaza_url", "") or "")
    if requested_directory_matches_base and requested_plaza_matches_base:
        return base_service
    return get_map_phemar_service(
        storage_directory=requested_directory or base_directory or None,
        agent_name=getattr(base_service, "name", "") or "MapPhemar",
        plaza_url=requested_plaza_url or getattr(base_service, "plaza_url", "") or "",
    )


def _extract_phema_payload(payload: Any) -> dict:
    """Internal helper to extract the phema payload."""
    phema_payload = payload.get("phema") if isinstance(payload, dict) and isinstance(payload.get("phema"), dict) else payload
    if not isinstance(phema_payload, dict):
        raise HTTPException(status_code=400, detail="Phema payload must be a JSON object.")
    return phema_payload


def mount_map_phemar_alias_routes(
    app: FastAPI,
    service_resolver: Callable[[], Any],
    *,
    prefix: str = "/api/map-phemar/phemas",
    route_name_prefix: str = "",
) -> None:
    """Mount the map phemar alias routes."""
    route_key = route_name_prefix or prefix.strip("/").replace("/", "_") or "map_phemar_phemas"

    @app.get(prefix, name=f"{route_key}_list")
    async def list_map_phemas(request: Request, q: str = ""):
        """Route handler for GET requests."""
        service = resolve_map_phemar_service_for_request(service_resolver, request)
        return {"status": "success", "phemas": service._list_local_phemas(query=q)}

    @app.get(f"{prefix}/{{phema_id}}", name=f"{route_key}_detail")
    async def map_phema_detail(request: Request, phema_id: str):
        """Route handler for GET requests."""
        service = resolve_map_phemar_service_for_request(service_resolver, request)
        phema = service._get_local_phema_row(phema_id)
        if not phema:
            raise HTTPException(status_code=404, detail=f"Phema '{phema_id}' was not found.")
        return {"status": "success", "phema": phema}

    @app.post(prefix, name=f"{route_key}_save")
    async def save_map_phema(request: Request):
        """Route handler for POST requests."""
        payload = await request.json()
        service = resolve_map_phemar_service_for_request(service_resolver, request)
        return {"status": "success", "phema": service._save_local_phema(_extract_phema_payload(payload))}

    @app.delete(f"{prefix}/{{phema_id}}", name=f"{route_key}_delete")
    async def delete_map_phema(request: Request, phema_id: str):
        """Route handler for DELETE requests."""
        service = resolve_map_phemar_service_for_request(service_resolver, request)
        service._delete_local_phema(phema_id)
        return {"status": "success", "phema_id": phema_id}


def mount_map_phemar_ui_alias_routes(
    app: FastAPI,
    service_resolver: Callable[[], Any],
    *,
    prefix: str = "/map-phemar",
    phema_api_prefix: str = "/api/map-phemar/phemas",
    back_href: str = "",
    back_label: str = "",
    static_route_name: str = "static",
) -> None:
    """Mount the map phemar UI alias routes."""
    templates = Jinja2Templates(directory=str(MAP_PHEMAR_TEMPLATE_DIR))
    route_key = prefix.strip("/").replace("/", "_") or "map_phemar"
    normalized_prefix = prefix.rstrip("/") or "/map-phemar"

    def render_editor(request: Request, phema_id: str = ""):
        """Render the editor."""
        service = resolve_map_phemar_service_for_request(service_resolver, request)
        storage_directory = str(
            _request_map_phemar_storage_directory(request)
            or getattr(service, "_map_phemar_storage_directory", "")
            or ""
        ).strip()
        settings_scope = _request_map_phemar_settings_scope(request) or "personal_agent"
        storage_settings_mode = _request_map_phemar_storage_settings_mode(request) or (
            "inherited" if settings_scope == "personal_agent" else "local"
        )
        preference_storage_key = _request_map_phemar_preference_storage_key(request)
        storage_label = storage_directory or getattr(getattr(service, "pool", None), "name", "") or "Local pool"
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "request": request,
                "page_title": getattr(service, "name", "") or "MapPhemar",
                "initial_payload": build_map_phemar_bootstrap(
                    agent_name=getattr(service, "name", "") or "MapPhemar",
                    plaza_url=getattr(service, "plaza_url", "") or "",
                    storage_label=storage_label,
                    phema_id=phema_id,
                    phema_api_prefix=phema_api_prefix,
                    back_href=back_href,
                    back_label=back_label,
                    settings_scope=settings_scope,
                    storage_settings_mode=storage_settings_mode,
                    default_file_save_local_directory=storage_directory,
                    preference_storage_key=preference_storage_key,
                ),
                "asset_version": get_map_phemar_asset_version(),
                "static_route_name": static_route_name,
            },
        )

    @app.get(normalized_prefix, include_in_schema=False, name=f"{route_key}_root")
    async def map_phemar_alias_root(request: Request):
        """Route handler for GET requests."""
        return render_editor(request)

    @app.get(f"{normalized_prefix}/", include_in_schema=False, name=f"{route_key}_root_slash")
    async def map_phemar_alias_root_slash():
        """Route handler for GET requests."""
        return RedirectResponse(url=normalized_prefix, status_code=307)

    @app.get(f"{normalized_prefix}/index", include_in_schema=False, name=f"{route_key}_index")
    async def map_phemar_alias_index():
        """Route handler for GET requests."""
        return RedirectResponse(url=normalized_prefix, status_code=307)

    @app.get(f"{normalized_prefix}/phemas/editor", include_in_schema=False, name=f"{route_key}_editor")
    async def map_phemar_alias_editor(request: Request):
        """Route handler for GET requests."""
        return render_editor(request)

    @app.get(
        f"{normalized_prefix}/phemas/editor/{{phema_id}}",
        include_in_schema=False,
        name=f"{route_key}_editor_existing",
    )
    async def map_phemar_alias_editor_existing(request: Request, phema_id: str):
        """Route handler for GET requests."""
        return render_editor(request, phema_id=phema_id)


def mount_map_phemar_plaza_proxy_routes(
    app: FastAPI,
    *,
    fetch_catalog: Callable[[str], Any] | None = None,
    run_pulser: Callable[[str, dict], Any] | None = None,
) -> None:
    """Mount the map phemar Plaza proxy routes."""
    fetch_catalog_impl = fetch_catalog or fetch_plaza_catalog
    run_pulser_impl = run_pulser or run_plaza_pulser_test

    @app.get("/api/plaza/catalog")
    async def plaza_catalog(plaza_url: str):
        """Route handler for GET /api/plaza/catalog."""
        try:
            return await fetch_catalog_impl(plaza_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PlazaProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.post("/api/plaza/panes/run")
    async def plaza_pane_run(request: PlazaPaneRunRequest):
        """Route handler for POST /api/plaza/panes/run."""
        payload = request.model_dump()
        plaza_url = payload.pop("plaza_url")
        try:
            return await run_pulser_impl(plaza_url, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PlazaProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.post("/api/plaza/branch/evaluate")
    async def plaza_branch_evaluate(request: BranchConditionEvaluateRequest):
        """Route handler for POST /api/plaza/branch/evaluate."""
        try:
            result = evaluate_branch_condition(request.expression, request.input)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "success", "result": result}

    @app.get("/api/system/select-directory")
    async def system_select_directory(initial_directory: str = ""):
        """Route handler for GET /api/system/select-directory."""
        try:
            directory = select_local_directory(initial_directory)
        except DirectorySelectionCancelled:
            return {"status": "cancelled", "directory": ""}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "success", "directory": directory}

    @app.post("/api/files/save/local")
    async def save_local_file(request: Request):
        """Route handler for POST /api/files/save/local."""
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="File save payload must be a JSON object.")
        try:
            saved = save_json_file(
                payload.get("content"),
                directory=payload.get("directory"),
                file_name=payload.get("file_name"),
                title=payload.get("title"),
            )
            return {"status": "success", "file": saved}
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/files/load/local")
    async def load_local_file(request: Request):
        """Route handler for POST /api/files/load/local."""
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="File load payload must be a JSON object.")
        try:
            loaded = load_json_file(
                directory=payload.get("directory"),
                file_name=payload.get("file_name"),
                title=payload.get("title"),
            )
            return {"status": "success", "file": loaded}
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/files/list/local")
    async def list_local_files(request: Request):
        """Route handler for POST /api/files/list/local."""
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="File list payload must be a JSON object.")
        try:
            files = list_json_files(
                directory=payload.get("directory"),
                recursive=bool(payload.get("recursive")),
            )
            return {"status": "success", "files": files}
        except (NotADirectoryError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
