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

from attas.personal_agent.data import get_dashboard_snapshot, get_workspace


BASE_DIR = Path(__file__).resolve().parent


def get_asset_version() -> str:
    return str(
        max(
            int((BASE_DIR / "static" / "personal_agent.css").stat().st_mtime),
            int((BASE_DIR / "static" / "personal_agent.js").stat().st_mtime),
            int((BASE_DIR / "templates" / "index.html").stat().st_mtime),
        )
    )


def create_app() -> FastAPI:
    app = FastAPI(
        title="attas Personal Agent",
        description="Standalone web terminal prototype for the attas Personal Agent experience.",
        version="0.1.0",
    )

    templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    @app.get("/", include_in_schema=False)
    async def root(request: Request):
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
        return RedirectResponse(url="/", status_code=307)

    @app.get("/api/dashboard")
    async def dashboard():
        return get_dashboard_snapshot()

    @app.get("/api/workspaces/{workspace_id}")
    async def workspace_detail(workspace_id: str):
        workspace = get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(status_code=404, detail=f"Workspace '{workspace_id}' was not found.")
        return workspace

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    reload_enabled = os.environ.get("ATTAS_PERSONAL_AGENT_RELOAD", "").strip() == "1"
    uvicorn.run("attas.personal_agent.app:app", host="127.0.0.1", port=8040, reload=reload_enabled)
