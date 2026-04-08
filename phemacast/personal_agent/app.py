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
from typing import Any, Dict

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
from phemacast.personal_agent.plaza import (
    BossProxyError,
    PlazaProxyError,
    fetch_boss_job_detail,
    fetch_managed_work_monitor,
    fetch_managed_work_schedule_history,
    fetch_managed_work_schedules,
    fetch_managed_work_ticket_detail,
    fetch_managed_work_tickets,
    fetch_plaza_agent_keys,
    fetch_plaza_auth_config,
    fetch_plaza_auth_me,
    fetch_plaza_catalog,
    create_plaza_agent_key,
    delete_plaza_agent_key,
    run_managed_work_schedule_control,
    run_plaza_auth_refresh,
    run_plaza_auth_signin,
    run_plaza_auth_signout,
    run_plaza_auth_signup,
    run_plaza_pulser_test,
    update_plaza_agent_key,
)
from prompits.channels import build_delivery_snapshot, default_b2b_channels
from prompits.teamwork.runtime import managed_ticket_from_job_row


BASE_DIR = Path(__file__).resolve().parent


def _decorate_managed_ticket(ticket: Any) -> Dict[str, Any]:
    """Attach generic destination status to one managed ticket payload."""
    normalized = dict(ticket or {}) if isinstance(ticket, dict) else {}
    work_item = normalized.get("work_item") if isinstance(normalized.get("work_item"), dict) else {}
    result_summary = normalized.get("result_summary") if isinstance(normalized.get("result_summary"), dict) else {}
    normalized["destination_status"] = build_delivery_snapshot(
        result_summary,
        metadata=work_item.get("metadata"),
    )
    return normalized


def _decorate_managed_ticket_list(entries: Any) -> list[Dict[str, Any]]:
    """Attach destination state to each ticket in a list."""
    return [_decorate_managed_ticket(entry) for entry in (entries or []) if isinstance(entry, dict)]


def _channel_catalog_payload() -> Dict[str, Any]:
    """Return the generic B2B channel lane catalog."""
    return {"status": "success", "channels": default_b2b_channels()}


def _decorate_job_detail(payload: Any, *, manager_address: str = "") -> Dict[str, Any]:
    """Attach the managed-ticket projection to a raw job detail payload."""
    normalized = dict(payload or {}) if isinstance(payload, dict) else {}
    job = normalized.get("job") if isinstance(normalized.get("job"), dict) else {}
    if job:
        normalized["managed_ticket"] = _decorate_managed_ticket(
            managed_ticket_from_job_row(
                job,
                manager_address=manager_address,
            )
        )
    normalized["channel_catalog"] = default_b2b_channels()
    return normalized


def get_asset_version() -> str:
    """Return the asset version."""
    return get_map_phemar_asset_version()


def _coerce_json_object(payload: Any, *, detail: str) -> Dict[str, Any]:
    """Return a request JSON object or raise a 400 error."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail=detail)
    return payload


def _proxy_authorization_header(request: Request) -> str:
    """Return the inbound Authorization header for Plaza proxy routes."""
    return str(request.headers.get("authorization") or "").strip()


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

    @app.get("/api/channels/catalog")
    async def channel_catalog():
        """Route handler for GET /api/channels/catalog."""
        return _channel_catalog_payload()

    @app.get("/api/workspaces/{workspace_id}")
    async def workspace_detail(workspace_id: str):
        """Route handler for GET /api/workspaces/{workspace_id}."""
        workspace = get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' was not found.")
        return workspace

    @app.get("/api/plaza/auth/config")
    async def plaza_auth_config(plaza_url: str = ""):
        """Route handler for GET /api/plaza/auth/config."""
        try:
            return await fetch_plaza_auth_config(plaza_url)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PlazaProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.post("/api/plaza/auth/signup")
    async def plaza_auth_signup(request: Request, plaza_url: str = ""):
        """Route handler for POST /api/plaza/auth/signup."""
        payload = _coerce_json_object(
            await request.json(),
            detail="Plaza sign-up payload must be a JSON object.",
        )
        try:
            return await run_plaza_auth_signup(plaza_url, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PlazaProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.post("/api/plaza/auth/signin")
    async def plaza_auth_signin(request: Request, plaza_url: str = ""):
        """Route handler for POST /api/plaza/auth/signin."""
        payload = _coerce_json_object(
            await request.json(),
            detail="Plaza sign-in payload must be a JSON object.",
        )
        try:
            return await run_plaza_auth_signin(plaza_url, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PlazaProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.get("/api/plaza/auth/me")
    async def plaza_auth_me(request: Request, plaza_url: str = ""):
        """Route handler for GET /api/plaza/auth/me."""
        try:
            return await fetch_plaza_auth_me(plaza_url, authorization=_proxy_authorization_header(request))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PlazaProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.post("/api/plaza/auth/refresh")
    async def plaza_auth_refresh(request: Request, plaza_url: str = ""):
        """Route handler for POST /api/plaza/auth/refresh."""
        payload = _coerce_json_object(
            await request.json(),
            detail="Plaza refresh payload must be a JSON object.",
        )
        try:
            return await run_plaza_auth_refresh(plaza_url, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PlazaProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.post("/api/plaza/auth/signout")
    async def plaza_auth_signout(request: Request, plaza_url: str = ""):
        """Route handler for POST /api/plaza/auth/signout."""
        try:
            return await run_plaza_auth_signout(plaza_url, authorization=_proxy_authorization_header(request))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PlazaProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.get("/api/plaza/agent-keys")
    async def plaza_agent_keys(request: Request, plaza_url: str = ""):
        """Route handler for GET /api/plaza/agent-keys."""
        try:
            return await fetch_plaza_agent_keys(plaza_url, authorization=_proxy_authorization_header(request))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PlazaProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.post("/api/plaza/agent-keys")
    async def plaza_create_agent_key(request: Request, plaza_url: str = ""):
        """Route handler for POST /api/plaza/agent-keys."""
        payload = _coerce_json_object(
            await request.json(),
            detail="Plaza agent-key payload must be a JSON object.",
        )
        try:
            return await create_plaza_agent_key(
                plaza_url,
                payload,
                authorization=_proxy_authorization_header(request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PlazaProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.patch("/api/plaza/agent-keys/{key_id}")
    async def plaza_update_agent_key(key_id: str, request: Request, plaza_url: str = ""):
        """Route handler for PATCH /api/plaza/agent-keys/{key_id}."""
        payload = _coerce_json_object(
            await request.json(),
            detail="Plaza agent-key update payload must be a JSON object.",
        )
        try:
            return await update_plaza_agent_key(
                plaza_url,
                key_id,
                payload,
                authorization=_proxy_authorization_header(request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PlazaProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.delete("/api/plaza/agent-keys/{key_id}")
    async def plaza_delete_agent_key(key_id: str, request: Request, plaza_url: str = ""):
        """Route handler for DELETE /api/plaza/agent-keys/{key_id}."""
        try:
            return await delete_plaza_agent_key(
                plaza_url,
                key_id,
                authorization=_proxy_authorization_header(request),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except PlazaProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.get("/api/managed-work/monitor")
    async def managed_work_monitor(
        boss_url: str = "",
        manager_address: str = "",
        party: str = "",
        ticket_limit: int = 20,
        schedule_limit: int = 20,
        preview_limit: int = 500,
    ):
        """Route handler for GET /api/managed-work/monitor."""
        try:
            payload = await fetch_managed_work_monitor(
                boss_url,
                manager_address=manager_address,
                party=party,
                ticket_limit=ticket_limit,
                schedule_limit=schedule_limit,
                preview_limit=preview_limit,
            )
        except BossProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        payload["tickets"] = _decorate_managed_ticket_list(payload.get("tickets"))
        payload["channel_catalog"] = default_b2b_channels()
        return payload

    @app.get("/api/managed-work/tickets")
    async def managed_work_tickets(
        boss_url: str = "",
        manager_address: str = "",
        party: str = "",
        status: str = "",
        capability: str = "",
        search: str = "",
        limit: int = 100,
        preview_limit: int = 500,
    ):
        """Route handler for GET /api/managed-work/tickets."""
        try:
            payload = await fetch_managed_work_tickets(
                boss_url,
                manager_address=manager_address,
                party=party,
                status=status,
                capability=capability,
                search=search,
                limit=limit,
                preview_limit=preview_limit,
            )
        except BossProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        payload["tickets"] = _decorate_managed_ticket_list(payload.get("tickets"))
        payload["channel_catalog"] = default_b2b_channels()
        return payload

    @app.get("/api/managed-work/tickets/{ticket_id}")
    async def managed_work_ticket_detail(
        ticket_id: str,
        boss_url: str = "",
        manager_address: str = "",
        party: str = "",
    ):
        """Route handler for GET /api/managed-work/tickets/{ticket_id}."""
        try:
            payload = await fetch_managed_work_ticket_detail(
                boss_url,
                ticket_id,
                manager_address=manager_address,
                party=party,
            )
        except BossProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        payload["ticket"] = _decorate_managed_ticket(payload.get("ticket"))
        payload["channel_catalog"] = default_b2b_channels()
        return payload

    @app.get("/api/managed-work/schedules")
    async def managed_work_schedules(
        boss_url: str = "",
        manager_address: str = "",
        status: str = "",
        search: str = "",
        limit: int = 100,
    ):
        """Route handler for GET /api/managed-work/schedules."""
        try:
            payload = await fetch_managed_work_schedules(
                boss_url,
                manager_address=manager_address,
                status=status,
                search=search,
                limit=limit,
            )
        except BossProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        payload["channel_catalog"] = default_b2b_channels()
        return payload

    @app.get("/api/managed-work/schedules/{schedule_id}/history")
    async def managed_work_schedule_history(schedule_id: str, boss_url: str = "", limit: int = 20):
        """Route handler for GET /api/managed-work/schedules/{schedule_id}/history."""
        try:
            payload = await fetch_managed_work_schedule_history(
                boss_url,
                schedule_id,
                limit=limit,
            )
        except BossProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        payload["tickets"] = _decorate_managed_ticket_list(payload.get("tickets"))
        payload["channel_catalog"] = default_b2b_channels()
        return payload

    @app.post("/api/managed-work/schedules/{schedule_id}/control")
    async def managed_work_schedule_control(schedule_id: str, request: Request, boss_url: str = ""):
        """Route handler for POST /api/managed-work/schedules/{schedule_id}/control."""
        payload = await request.json()
        action = str((payload or {}).get("action") or "").strip().lower()
        try:
            return await run_managed_work_schedule_control(
                boss_url,
                schedule_id,
                action=action,
            )
        except BossProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    @app.get("/api/jobs/{job_id}")
    async def managed_job_detail(
        job_id: str,
        boss_url: str = "",
        dispatcher_address: str = "",
        manager_address: str = "",
        party: str = "",
    ):
        """Route handler for GET /api/jobs/{job_id}."""
        effective_dispatcher_address = dispatcher_address or manager_address
        try:
            payload = await fetch_boss_job_detail(
                boss_url,
                job_id,
                dispatcher_address=effective_dispatcher_address,
            )
            return _decorate_job_detail(payload, manager_address=effective_dispatcher_address)
        except BossProxyError as exc:
            if exc.status_code != 404:
                raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        try:
            fallback = await fetch_managed_work_ticket_detail(
                boss_url,
                job_id,
                manager_address=manager_address,
                party=party,
            )
        except BossProxyError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        return {
            "status": "success",
            "detail_source": "managed_ticket_detail",
            "managed_ticket": _decorate_managed_ticket(fallback.get("ticket")),
            "raw_records": fallback.get("raw_records", []),
            "latest_heartbeat": fallback.get("latest_heartbeat", {}),
            "channel_catalog": default_b2b_channels(),
        }

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
