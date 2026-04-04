"""
Map-Phemar helpers for `phemacast.agents.map_phemar`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the agents package contains the actor roles
that build, bind, and render phemas.

Core types exposed here include `MapPhemarAgent`, which carry the main behavior or state
managed by this module.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.routing import Mount

from phemacast.agents.phemar import Phemar
from phemacast.map_phemar.runtime import (
    MAP_PHEMAR_STATIC_DIR,
    MAP_PHEMAR_TEMPLATE_DIR,
    build_map_phemar_bootstrap,
    get_map_phemar_asset_version,
    mount_map_phemar_alias_routes,
    mount_map_phemar_plaza_proxy_routes,
)

MAP_PHEMAR_UI_ROUTE_PATHS = {"/", "/phemas/editor", "/phemas/editor/{phema_id}"}


class MapPhemarAgent(Phemar):
    """Phemar agent with a focused diagram-editor UI for building Phema graphs."""

    def _setup_phemar_routes(self) -> None:
        """Internal helper to set up the phemar routes."""
        super()._setup_phemar_routes()

        self.app.router.routes = [
            route
            for route in self.app.router.routes
            if not (
                (isinstance(route, Mount) and getattr(route, "path", "") == "/static")
                or getattr(route, "path", "") in MAP_PHEMAR_UI_ROUTE_PATHS
            )
        ]
        self.app.mount("/static", StaticFiles(directory=str(MAP_PHEMAR_STATIC_DIR)), name="static")
        self.templates = Jinja2Templates(directory=str(MAP_PHEMAR_TEMPLATE_DIR))

        @self.app.get("/", include_in_schema=False)
        async def root(request: Request):
            """Route handler for GET /."""
            return self._render_map_phemar_editor(request)

        @self.app.get("/index", include_in_schema=False)
        async def index_redirect():
            """Route handler for GET /index."""
            return RedirectResponse(url="/", status_code=307)

        @self.app.get("/phemas/editor", include_in_schema=False)
        async def phemar_editor(request: Request):
            """Route handler for GET /phemas/editor."""
            return self._render_map_phemar_editor(request)

        @self.app.get("/phemas/editor/{phema_id}", include_in_schema=False)
        async def phemar_editor_existing(request: Request, phema_id: str):
            """Route handler for GET /phemas/editor/{phema_id}."""
            return self._render_map_phemar_editor(request, phema_id=phema_id)

        mount_map_phemar_alias_routes(
            self.app,
            lambda: self,
            prefix="/api/map-phemar/phemas",
            route_name_prefix="map_phemar_agent_alias",
        )
        mount_map_phemar_plaza_proxy_routes(self.app)

    def _render_map_phemar_editor(self, request: Request, phema_id: str = ""):
        """Internal helper to render the map phemar editor."""
        requested_plaza_url = str(request.query_params.get("map_phemar_plaza_url") or "").strip()
        return self.templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "request": request,
                "page_title": self.name or "MapPhemar",
                "initial_payload": self._build_map_phemar_bootstrap(
                    phema_id=phema_id,
                    plaza_url=requested_plaza_url or self.plaza_url or "",
                ),
                "asset_version": get_map_phemar_asset_version(),
                "static_route_name": "static",
            },
        )

    def _build_map_phemar_bootstrap(self, phema_id: str = "", plaza_url: str = "") -> dict:
        """Internal helper to build the map phemar bootstrap."""
        storage_directory = str(getattr(self, "_map_phemar_storage_directory", "") or "").strip()
        if not storage_directory:
            pool_root_path = str(getattr(self.pool, "root_path", "") or "").strip()
            if pool_root_path:
                storage_directory = str(Path(pool_root_path).expanduser().resolve().parent)
        storage_label = storage_directory or getattr(self.pool, "name", "") or "Local pool"
        return build_map_phemar_bootstrap(
            agent_name=self.name,
            plaza_url=plaza_url or self.plaza_url or "",
            storage_label=storage_label,
            phema_id=phema_id,
            phema_api_prefix="/api/map-phemar/phemas",
            settings_scope="map_phemar",
            storage_settings_mode="local",
            default_file_save_local_directory=storage_directory,
        )
