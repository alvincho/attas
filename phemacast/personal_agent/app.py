"""
Application entry point for `phemacast.personal_agent.app`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the personal_agent package powers the file-
backed personal research workbench and its web UI.

Important callables in this file include `create_app` and `get_asset_version`, which
capture the primary workflow implemented by the module.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

if __package__ in (None, ""):
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

from phemacast.map_phemar.runtime import (
    get_embedded_map_phemar,
    get_map_phemar_asset_version,
    MAP_PHEMAR_STATIC_DIR,
    mount_map_phemar_alias_routes,
    mount_map_phemar_ui_alias_routes,
    mount_map_phemar_plaza_proxy_routes,
)
from phemacast.personal_agent.data import get_dashboard_snapshot, get_workspace
from phemacast.personal_agent.doc_pages import DOC_PAGES, load_doc_page
from phemacast.personal_agent.layout_files import list_layout_files, save_layout_file
from phemacast.personal_agent.plaza import fetch_plaza_catalog, run_plaza_pulser_test


BASE_DIR = Path(__file__).resolve().parent

def get_asset_version() -> str:
    """Return the asset version."""
    return get_map_phemar_asset_version()


def create_app() -> FastAPI:
    """Create the app."""
    app = FastAPI(
        title="Phemacast Personal Agent",
        description="React-based personal agent prototype for browsing pulses, layouts, and mind maps.",
        version="0.1.0",
    )

    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
    app.mount("/docs-static/personal-agent", StaticFiles(directory=str(BASE_DIR / "docs")), name="personal_agent_docs_static")
    app.mount("/map-phemar-static", StaticFiles(directory=str(MAP_PHEMAR_STATIC_DIR)), name="map_phemar_static")

    @app.get("/", include_in_schema=False)
    async def root(request: Request):
        """Route handler for GET /."""
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "request": request,
                "initial_payload": get_dashboard_snapshot(),
                "asset_version": get_asset_version(),
            },
        )

    @app.get("/index", include_in_schema=False)
    async def index_redirect():
        """Route handler for GET /index."""
        return RedirectResponse(url="/", status_code=307)

    @app.get("/docs/personal-agent/{doc_slug}", include_in_schema=False)
    async def personal_agent_doc_page(request: Request, doc_slug: str):
        """Route handler for GET /docs/personal-agent/{doc_slug}."""
        try:
            page = load_doc_page(doc_slug)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return templates.TemplateResponse(
            request=request,
            name="doc_page.html",
            context={
                "request": request,
                "page_title": page["title"],
                "doc_title": page["title"],
                "doc_eyebrow": page["eyebrow"],
                "doc_summary": page["summary"],
                "doc_content_html": page["content_html"],
                "back_href": "/",
                "related_docs": {
                    "user_guide": f"/docs/personal-agent/{DOC_PAGES['user-guide'].slug}",
                    "current_features": f"/docs/personal-agent/{DOC_PAGES['current-features'].slug}",
                    "readme": f"/docs/personal-agent/{DOC_PAGES['readme'].slug}",
                },
                "asset_version": get_asset_version(),
            },
        )

    @app.get("/api/dashboard")
    async def dashboard():
        """Route handler for GET /api/dashboard."""
        return get_dashboard_snapshot()

    @app.get("/api/workspaces/{workspace_id}")
    async def workspace_detail(workspace_id: str):
        """Route handler for GET /api/workspaces/{workspace_id}."""
        workspace = get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' was not found.")
        return workspace

    mount_map_phemar_alias_routes(app, get_embedded_map_phemar, route_name_prefix="personal_agent_map_phemas")
    mount_map_phemar_alias_routes(
        app,
        get_embedded_map_phemar,
        prefix="/api/phemas",
        route_name_prefix="embedded_map_phemas",
    )
    mount_map_phemar_ui_alias_routes(
        app,
        get_embedded_map_phemar,
        prefix="/map-phemar",
        phema_api_prefix="/api/map-phemar/phemas",
        back_href="/",
        back_label="Back to Personal Agent",
        static_route_name="map_phemar_static",
    )
    mount_map_phemar_plaza_proxy_routes(
        app,
        fetch_catalog=lambda plaza_url: fetch_plaza_catalog(plaza_url),
        run_pulser=lambda plaza_url, payload: run_plaza_pulser_test(plaza_url, payload),
    )

    @app.get("/api/layout-files/{layout_kind}")
    async def list_layout_documents(layout_kind: str):
        """Route handler for GET /api/layout-files/{layout_kind}."""
        try:
            return {"status": "success", "layouts": list_layout_files(layout_kind)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/layout-files/{layout_kind}")
    async def save_layout_document(layout_kind: str, request: Request):
        """Route handler for POST /api/layout-files/{layout_kind}."""
        payload = await request.json()
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Layout payload must be a JSON object.")
        try:
            layout = save_layout_file(layout_kind, payload)
            return {"status": "success", "layout": layout, "layouts": list_layout_files(layout_kind)}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/health")
    async def health():
        """Route handler for GET /health."""
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    reload_enabled = os.environ.get("PHEMACAST_PERSONAL_AGENT_RELOAD", "").strip() == "1"
    uvicorn.run("phemacast.personal_agent.app:app", host="127.0.0.1", port=8041, reload=reload_enabled)
