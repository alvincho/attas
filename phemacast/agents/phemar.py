"""
Phemar module for `phemacast.agents.phemar`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the agents package contains the actor roles
that build, bind, and render phemas.

Core types exposed here include `GeneratePhemaPractice`, `Phemar`, and
`SnapshotPhemaPractice`, which carry the main behavior or state managed by this module.
"""

from __future__ import annotations

import logging
import json
import os
import threading
import time
import uuid
import hashlib
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

import requests
import uvicorn
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from prompits.agents.standby import StandbyAgent
from prompits.core.init_schema import phemas_table_schema, phema_snapshots_table_schema
from prompits.core.message import Message

logger = logging.getLogger(__name__)
from prompits.core.pit import PitAddress
from prompits.core.practice import Practice

from phemacast.core.phema import Phema


ConfigInput = Union[str, Path, Mapping[str, Any]]


def _read_config(config: ConfigInput) -> Dict[str, Any]:
    """Internal helper to read the config."""
    if isinstance(config, Mapping):
        return dict(config)

    config_path = Path(config)
    with config_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _merge_tags(*tag_groups: Any) -> List[str]:
    """Internal helper to merge the tags."""
    merged: List[str] = []
    for group in tag_groups:
        if not group:
            continue
        for tag in group:
            value = str(tag)
            if value and value not in merged:
                merged.append(value)
    return merged


class GeneratePhemaPractice(Practice):
    """Expose `agent.generate_phema()` as a mounted callable practice."""

    def __init__(self):
        """Initialize the generate phema practice."""
        super().__init__(
            name="Generate Phema",
            description="Resolve a Phema blueprint into a static payload using Plaza pulser practices.",
            id="generate_phema",
            tags=["phemar", "phema", "render"],
            examples=["POST /generate_phema {'phema_id': 'macro-brief', 'params': {'ticker': 'AAPL'}}"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def bind(self, agent):
        """Bind the value."""
        super().bind(agent)
        supported = getattr(agent, "supported_phemas", [])
        self.parameters = {
            "phema_id": {
                "type": "string",
                "description": "Optional Phema id registered on Plaza or preloaded into the agent.",
                "enum": [phema.phema_id for phema in supported if phema.phema_id],
            },
            "phema_name": {
                "type": "string",
                "description": "Optional Phema name when resolving from Plaza or config.",
                "enum": [phema.name for phema in supported if phema.name],
            },
            "phema": {
                "type": "object",
                "description": "Inline Phema payload to resolve without directory lookup.",
            },
            "params": {
                "type": "object",
                "description": "Input parameters forwarded to matching pulsers.",
            },
            "input": {
                "type": "object",
                "description": "Alias for params when invoked by other agents.",
            },
        }

    def mount(self, app):
        """Mount the value."""
        router = APIRouter()

        @router.post(self.path)
        async def generate_phema(message: Message):
            """Route handler for POST requests."""
            content = message.content or {}
            if not isinstance(content, dict):
                raise HTTPException(status_code=400, detail="Phemar content must be a JSON object.")
            return self.execute(**content)

        app.include_router(router)

    def execute(self, **kwargs) -> Any:
        """Handle execute for the generate phema practice."""
        if not self.agent:
            raise RuntimeError("GeneratePhemaPractice is not bound to an agent.")

        return self.agent.generate_phema(
            phema=kwargs.get("phema"),
            phema_id=kwargs.get("phema_id"),
            phema_name=kwargs.get("phema_name"),
            params=kwargs.get("params") or kwargs.get("input"),
            input_data=kwargs.get("input_data") or kwargs.get("input"),
        )


class SnapshotPhemaPractice(Practice):
    """Expose `agent.snapshot_phema()` as a mounted callable practice."""

    def __init__(self):
        """Initialize the snapshot phema practice."""
        super().__init__(
            name="Snapshot Phema",
            description="Generate or reuse a cached static snapshot for a Phema using live Plaza pulse data.",
            id="snapshot_phema",
            tags=["phemar", "phema", "snapshot", "cache"],
            examples=["POST /snapshot_phema {'phema_id': 'macro-brief', 'params': {'ticker': 'AAPL'}, 'cache_time': 900}"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def bind(self, agent):
        """Bind the value."""
        super().bind(agent)
        supported = getattr(agent, "supported_phemas", [])
        self.parameters = {
            "phema_id": {
                "type": "string",
                "description": "Optional Phema id registered on Plaza or preloaded into the agent.",
                "enum": [phema.phema_id for phema in supported if phema.phema_id],
            },
            "phema_name": {
                "type": "string",
                "description": "Optional Phema name when resolving from Plaza or config.",
                "enum": [phema.name for phema in supported if phema.name],
            },
            "phema": {
                "type": "object",
                "description": "Inline Phema payload to snapshot without directory lookup.",
            },
            "params": {
                "type": "object",
                "description": "Input parameters forwarded to matching pulsers.",
            },
            "input": {
                "type": "object",
                "description": "Alias for params when invoked by other agents.",
            },
            "cache_time": {
                "type": "integer",
                "description": "Cache lifetime in seconds before regenerating a new static snapshot.",
            },
        }

    def mount(self, app):
        """Mount the value."""
        router = APIRouter()

        @router.post(self.path)
        async def snapshot_phema(message: Message):
            """Route handler for POST requests."""
            content = message.content or {}
            if not isinstance(content, dict):
                raise HTTPException(status_code=400, detail="Phemar content must be a JSON object.")
            return self.execute(**content)

        app.include_router(router)

    def execute(self, **kwargs) -> Any:
        """Handle execute for the snapshot phema practice."""
        if not self.agent:
            raise RuntimeError("SnapshotPhemaPractice is not bound to an agent.")

        return self.agent.snapshot_phema(
            phema=kwargs.get("phema"),
            phema_id=kwargs.get("phema_id"),
            phema_name=kwargs.get("phema_name"),
            params=kwargs.get("params") or kwargs.get("input"),
            input_data=kwargs.get("input_data") or kwargs.get("input"),
            cache_time=kwargs.get("cache_time"),
            cache_seconds=kwargs.get("cache_seconds"),
            cache_ttl_seconds=kwargs.get("cache_ttl_seconds"),
        )


class Phemar(StandbyAgent):
    """
    Standby agent specialized for turning a Phema into a static payload.

    A Phemar exposes `generate_phema`, resolves Phemas from inline payloads,
    local config, or Plaza directory entries, then fetches section pulse data
    from registered pulsers via remote `UsePractice`.
    """

    PHEMA_TABLE = "phemas"
    PHEMA_SNAPSHOT_TABLE = "phema_snapshots"

    def __init__(
        self,
        config: Optional[ConfigInput] = None,
        *,
        config_path: Optional[ConfigInput] = None,
        name: str = "Phemar",
        host: str = "127.0.0.1",
        port: int = 8000,
        plaza_url: Optional[str] = None,
        agent_card: Optional[Dict[str, Any]] = None,
        pool: Any = None,
        supported_phemas: Optional[List[Dict[str, Any]]] = None,
        auto_register: bool = True,
    ):
        """Initialize the phemar."""
        config_data = _read_config(config) if config is not None else {}
        resolved_config_path = config_path
        if resolved_config_path is None and isinstance(config, (str, Path)):
            resolved_config_path = config

        self.config_path = Path(resolved_config_path).resolve() if resolved_config_path else None
        self.raw_config = dict(config_data)
        phemar_config = config_data.get("phemar", config_data)

        resolved_name = str(config_data.get("name") or phemar_config.get("name") or name)
        resolved_host = str(config_data.get("host") or phemar_config.get("host") or host)
        resolved_port = int(config_data.get("port") or phemar_config.get("port") or port)
        resolved_plaza_url = config_data.get("plaza_url") or phemar_config.get("plaza_url") or plaza_url

        raw_supported_phemas = supported_phemas
        if raw_supported_phemas is None:
            raw_supported_phemas = phemar_config.get("supported_phemas")
        if raw_supported_phemas is None:
            raw_supported_phemas = phemar_config.get("phemas")

        self.config = phemar_config
        self.supported_phemas = self._normalize_supported_phemas(raw_supported_phemas)

        card = dict(agent_card or phemar_config.get("agent_card") or {})
        card.setdefault("name", resolved_name)
        card.setdefault("role", "phemar")
        card.setdefault("pit_type", "Agent")
        card.setdefault(
            "description",
            phemar_config.get("description", "Generates static Phemas by resolving Plaza pulse practices."),
        )
        card["tags"] = _merge_tags(card.get("tags"), phemar_config.get("tags"), ["phemar", "phema"])
        meta = dict(card.get("meta") or {})
        meta["supported_phemas"] = [self._phema_summary(phema) for phema in self.supported_phemas]
        card["meta"] = meta

        super().__init__(
            name=resolved_name,
            host=resolved_host,
            port=resolved_port,
            plaza_url=resolved_plaza_url,
            agent_card=card,
            pool=pool,
        )

        current_dir = os.path.dirname(os.path.abspath(__file__))
        templates_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "prompits", "agents", "templates"))
        static_dir = os.path.abspath(os.path.join(current_dir, "..", "..", "prompits", "agents", "static"))
        self.templates = Jinja2Templates(directory=templates_dir)
        self.app.mount("/static", StaticFiles(directory=static_dir), name="static")
        self._phema_timestamps: Dict[str, Dict[str, str]] = {}
        self._snapshot_rows: Dict[str, Dict[str, Any]] = {}
        for phema in self.supported_phemas:
            if phema.phema_id:
                now = datetime.now(timezone.utc).isoformat()
                self._phema_timestamps[phema.phema_id] = {"created_at": now, "updated_at": now}
        self._bootstrap_local_phema_store()

        self.add_practice(GeneratePhemaPractice())
        self.add_practice(SnapshotPhemaPractice())
        self._setup_phemar_routes()

        if self.plaza_url and auto_register:
            self.register()

    @classmethod
    def from_config(cls, config: ConfigInput, **kwargs: Any) -> "Phemar":
        """Build an instance from config."""
        return cls(config=config, **kwargs)

    @classmethod
    def start_from_config(
        cls,
        config: ConfigInput,
        *,
        log_level: str = "error",
        timeout_sec: int = 10,
        **kwargs: Any,
    ) -> Tuple["Phemar", uvicorn.Server, threading.Thread]:
        """Start the from config."""
        agent = cls.from_config(config, **kwargs)
        server_config = uvicorn.Config(agent.app, host=agent.host, port=agent.port, log_level=log_level)
        server = uvicorn.Server(server_config)
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()

        deadline = time.time() + timeout_sec
        health_url = f"http://{agent.host}:{agent.port}/health"
        while time.time() < deadline:
            try:
                response = requests.get(health_url, timeout=0.5)
                if response.status_code == 200:
                    return agent, server, thread
            except Exception:
                pass
            time.sleep(0.2)

        server.should_exit = True
        thread.join(timeout=1)
        raise RuntimeError(f"Timed out waiting for agent at {health_url}")

    def register(self, *, start_reconnect_on_failure: bool = True, request_retries: Optional[int] = None):
        """Register the value."""
        if self.plaza_token and time.time() < (self.token_expires_at - 60):
            return
        res = super().register(
            start_reconnect_on_failure=start_reconnect_on_failure,
            request_retries=request_retries,
        )
        registration_succeeded = bool(
            res is not None
            and getattr(res, "status_code", None) == 200
            and self.plaza_token
        )
        # Auto-register supported Phemas on startup if Plaza is configured.
        if self.plaza_url and registration_succeeded:
            logger.info(f"[{self.name}] Auto-registering {len(self.supported_phemas)} supported Phemas on Plaza...")
            for phema_cfg in self.supported_phemas:
                phema_id = getattr(phema_cfg, "phema_id", None)
                if phema_id:
                    try:
                        configured_mode = ""
                        if isinstance(getattr(phema_cfg, "meta", None), Mapping):
                            configured_mode = str(phema_cfg.meta.get("registration_mode") or "").strip().lower()
                        self._register_phema_on_plaza(
                            phema=phema_cfg,
                            phema_id=phema_id,
                            registration_mode=configured_mode or None,
                        )
                        logger.debug(f"[{self.name}] Successfully registered Phema '{phema_id}' on Plaza")
                    except Exception as e:
                        logger.error(f"[{self.name}] Failed to auto-register Phema '{phema_id}': {e}")
        return res

    def _setup_phemar_routes(self) -> None:
        """Internal helper to set up the phemar routes."""
        @self.app.get("/")
        async def phemar_ui(request: Request):
            """Route handler for GET /."""
            return self.templates.TemplateResponse(
                request=request,
                name="phema_editor.html",
                context={
                    "request": request,
                    "agent_name": self.name,
                    "initial_phema_id": "",
                    "manager_mode": True,
                    "back_href": self.plaza_url or "",
                    "back_label": "Open Plaza" if self.plaza_url else "",
                },
            )

        @self.app.get("/phemas/editor")
        async def phemar_editor(request: Request):
            """Route handler for GET /phemas/editor."""
            return self.templates.TemplateResponse(
                request=request,
                name="phema_editor.html",
                context={
                    "request": request,
                    "agent_name": self.name,
                    "initial_phema_id": "",
                    "manager_mode": True,
                    "back_href": self.plaza_url or "",
                    "back_label": "Open Plaza" if self.plaza_url else "",
                },
            )

        @self.app.get("/phemas/editor/{phema_id}")
        async def phemar_editor_existing(request: Request, phema_id: str):
            """Route handler for GET /phemas/editor/{phema_id}."""
            return self.templates.TemplateResponse(
                request=request,
                name="phema_editor.html",
                context={
                    "request": request,
                    "agent_name": self.name,
                    "initial_phema_id": phema_id,
                    "manager_mode": True,
                    "back_href": self.plaza_url or "",
                    "back_label": "Open Plaza" if self.plaza_url else "",
                },
            )

        @self.app.get("/api/config")
        async def get_phemar_config():
            """Route handler for GET /api/config."""
            return {
                "status": "success",
                "config": self._load_config_document(),
                "config_path": str(self.config_path) if self.config_path else None,
            }

        @self.app.get("/api/plazas_status")
        async def get_plaza_status(request: Request):
            """Route handler for GET /api/plazas_status."""
            pit_type = request.query_params.get("pit_type")
            params = {"pit_type": pit_type} if pit_type else None
            if not self.plaza_url:
                return {"status": "success", "plazas": []}
            try:
                response = self._plaza_get("/api/plazas_status", params=params)
                payload = response.json() if response.content else {}
                if response.status_code >= 400:
                    raise HTTPException(status_code=response.status_code, detail=payload.get("detail") or "Failed to load Plaza status")
                return payload
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Failed to load Plaza status: {exc}") from exc

        @self.app.get("/api/phemas")
        async def list_phemas(q: str = ""):
            """Route handler for GET /api/phemas."""
            return {"status": "success", "phemas": self._list_local_phemas(query=q)}

        @self.app.get("/api/local/phemas")
        async def list_local_phemas(q: str = ""):
            """Route handler for GET /api/local/phemas."""
            return {"status": "success", "phemas": self._list_local_phemas(query=q)}

        @self.app.get("/api/phemas/{phema_id}")
        async def get_phema(phema_id: str):
            """Route handler for GET /api/phemas/{phema_id}."""
            row = self._get_local_phema_row(phema_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Phema not found")
            return {"status": "success", "phema": row}

        @self.app.get("/api/plaza/phemas")
        async def list_plaza_phemas(q: str = ""):
            """Route handler for GET /api/plaza/phemas."""
            phemas, plaza_error = self._safe_list_plaza_phemas(query=q)
            return {
                "status": "success" if not plaza_error else "degraded",
                "phemas": phemas,
                "plaza_available": not bool(plaza_error),
                "plaza_error": plaza_error,
            }

        @self.app.get("/api/plaza/phemas/{phema_id}")
        async def get_plaza_phema(phema_id: str):
            """Route handler for GET /api/plaza/phemas/{phema_id}."""
            row = self._get_plaza_phema_row(phema_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Phema not found on Plaza")
            return {"status": "success", "phema": row}

        @self.app.get("/api/phema-snapshots")
        async def list_phema_snapshots(q: str = "", phema_id: str = "", limit: int = 50):
            """Route handler for GET /api/phema-snapshots."""
            return {
                "status": "success",
                "snapshots": self._list_snapshot_history(query=q, phema_id=phema_id, limit=limit),
            }

        @self.app.get("/api/phema-snapshots/{snapshot_id}")
        async def get_phema_snapshot(snapshot_id: str):
            """Route handler for GET /api/phema-snapshots/{snapshot_id}."""
            row = self._get_snapshot_row(snapshot_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Phema snapshot not found")
            return {"status": "success", "snapshot": row}

        @self.app.delete("/api/phema-snapshots/{snapshot_id}")
        async def delete_phema_snapshot(snapshot_id: str):
            """Route handler for DELETE /api/phema-snapshots/{snapshot_id}."""
            self._delete_snapshot_row(snapshot_id)
            return {"status": "success", "snapshot_id": snapshot_id}

        @self.app.get("/phema-snapshots/{snapshot_id}/view", response_class=HTMLResponse)
        async def view_phema_snapshot(snapshot_id: str):
            """Route handler for GET /phema-snapshots/{snapshot_id}/view."""
            row = self._get_snapshot_row(snapshot_id)
            if row is None:
                raise HTTPException(status_code=404, detail="Phema snapshot not found")
            pretty_json = json.dumps(row, indent=2, ensure_ascii=False, default=str)
            title = f"Snapshot {snapshot_id[:8]} | {row.get('phema_name') or 'Phema Snapshot'}"
            escaped_title = html.escape(title)
            escaped_json = html.escape(pretty_json)
            return HTMLResponse(
                content=f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escaped_title}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4f7f8;
      --panel: #ffffff;
      --border: #d6e1e4;
      --text: #16323a;
      --muted: #54707a;
      --accent: #0f766e;
      --string: #0f766e;
      --number: #1556c3;
      --boolean: #b45309;
      --key: #7c2d12;
      --null: #7c3aed;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "SFMono-Regular", "Menlo", "Consolas", monospace;
      background:
        radial-gradient(circle at top left, rgba(15,118,110,0.08), transparent 28%),
        linear-gradient(180deg, #f9fbfb, var(--bg));
      color: var(--text);
    }}
    .shell {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 24px;
    }}
    .card {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 20px;
      box-shadow: 0 20px 50px rgba(22,50,58,0.08);
      overflow: hidden;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      padding: 18px 20px;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(240,248,247,0.96));
    }}
    .title {{
      font-size: 18px;
      font-weight: 700;
      margin: 0;
    }}
    .subtle {{
      color: var(--muted);
      font-size: 13px;
    }}
    .actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
    }}
    button, a {{
      appearance: none;
      border: 1px solid rgba(15,118,110,0.18);
      background: rgba(15,118,110,0.08);
      color: var(--accent);
      border-radius: 999px;
      padding: 10px 14px;
      font: inherit;
      font-size: 13px;
      font-weight: 700;
      cursor: pointer;
      text-decoration: none;
    }}
    pre {{
      margin: 0;
      padding: 20px;
      overflow: auto;
      font-size: 13px;
      line-height: 1.65;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .json-key {{ color: var(--key); font-weight: 700; }}
    .json-string {{ color: var(--string); }}
    .json-number {{ color: var(--number); }}
    .json-boolean {{ color: var(--boolean); font-weight: 700; }}
    .json-null {{ color: var(--null); font-weight: 700; }}
  </style>
</head>
<body>
  <div class="shell">
    <div class="card">
      <div class="header">
        <div>
          <h1 class="title">{escaped_title}</h1>
          <div class="subtle">Pretty JSON viewer for snapshot history</div>
        </div>
        <div class="actions">
          <button type="button" id="copy-json-btn">Copy JSON</button>
          <a href="/api/phema-snapshots/{html.escape(snapshot_id)}" target="_blank" rel="noreferrer">Open API JSON</a>
        </div>
      </div>
      <pre id="json-viewer">{escaped_json}</pre>
    </div>
  </div>
  <script>
    const rawJson = {json.dumps(pretty_json)};
    const viewer = document.getElementById('json-viewer');
    const highlighted = rawJson.replace(
      /("(?:\\\\u[0-9a-fA-F]{{4}}|\\\\[^u]|[^\\\\"])*"(\\s*:)?|\\btrue\\b|\\bfalse\\b|\\bnull\\b|-?\\d+(?:\\.\\d+)?(?:[eE][+-]?\\d+)?)/g,
      (match) => {{
        let cls = 'json-number';
        if (/^"/.test(match)) {{
          cls = /:$/.test(match) ? 'json-key' : 'json-string';
        }} else if (/true|false/.test(match)) {{
          cls = 'json-boolean';
        }} else if (/null/.test(match)) {{
          cls = 'json-null';
        }}
        return `<span class="${{cls}}">${{match}}</span>`;
      }}
    );
    viewer.innerHTML = highlighted;
    document.getElementById('copy-json-btn').addEventListener('click', async () => {{
      try {{
        await navigator.clipboard.writeText(rawJson);
        document.getElementById('copy-json-btn').textContent = 'Copied';
        setTimeout(() => {{
          document.getElementById('copy-json-btn').textContent = 'Copy JSON';
        }}, 1200);
      }} catch (_) {{
        document.getElementById('copy-json-btn').textContent = 'Copy failed';
      }}
    }});
  </script>
</body>
</html>"""
            )

        @self.app.get("/api/phemar/manager")
        async def get_manager_context(q_local: str = "", q_plaza: str = ""):
            """Route handler for GET /api/phemar/manager."""
            plaza_phemas, plaza_error = self._safe_list_plaza_phemas(query=q_plaza)
            return {
                "status": "success",
                "owner_name": self.name,
                "owner_agent_id": self.agent_id or "",
                "local_phemas": self._list_local_phemas(
                    query=q_local,
                    plaza_rows=plaza_phemas,
                    plaza_lookup_failed=bool(plaza_error),
                ),
                "plaza_phemas": plaza_phemas,
                "plaza_available": not bool(plaza_error),
                "plaza_error": plaza_error,
            }

        @self.app.post("/api/phemas")
        async def save_phema(request: Request):
            """Route handler for POST /api/phemas."""
            payload = await request.json()
            phema_payload = payload.get("phema") if isinstance(payload, dict) and isinstance(payload.get("phema"), dict) else payload
            if not isinstance(phema_payload, dict):
                raise HTTPException(status_code=400, detail="Phema payload must be a JSON object.")
            return {"status": "success", "phema": self._save_local_phema(phema_payload)}

        @self.app.delete("/api/phemas/{phema_id}")
        async def delete_phema(phema_id: str):
            """Route handler for DELETE /api/phemas/{phema_id}."""
            self._delete_local_phema(phema_id)
            return {"status": "success", "phema_id": phema_id}

        @self.app.post("/api/plaza/phemas/register")
        async def register_phema_on_plaza(request: Request):
            """Route handler for POST /api/plaza/phemas/register."""
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Plaza registration payload must be a JSON object.")
            saved = self._register_phema_on_plaza(
                phema=payload.get("phema"),
                phema_id=payload.get("phema_id"),
                registration_mode=payload.get("registration_mode"),
            )
            return {"status": "success", "phema": saved}

        @self.app.delete("/api/plaza/phemas/{phema_id}")
        async def deregister_phema_from_plaza(phema_id: str):
            """Route handler for DELETE /api/plaza/phemas/{phema_id}."""
            self._deregister_phema_from_plaza(phema_id)
            return {"status": "success", "phema_id": phema_id}

        @self.app.post("/api/pulsers/test")
        async def run_pulser_test(request: Request):
            """Route handler for POST /api/pulsers/test."""
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Pulser test payload must be a JSON object.")
            practice_id = str(payload.get("practice_id") or "get_pulse_data").strip() or "get_pulse_data"
            definition = {
                "pulser_id": payload.get("pulser_id"),
                "pulser_name": payload.get("pulser_name"),
                "pulser_address": payload.get("pulser_address"),
                "pulse_name": payload.get("pulse_name"),
                "pulse_address": payload.get("pulse_address"),
            }
            target = self._resolve_target_pit_address(definition)
            if not target:
                raise HTTPException(status_code=404, detail="Selected pulser could not be resolved")
            try:
                result = self.UsePractice(
                    practice_id,
                    content={
                        "pulse_name": payload.get("pulse_name"),
                        "pulse_address": payload.get("pulse_address"),
                        "params": dict(payload.get("input") or {}),
                        "output_schema": dict(payload.get("output_schema") or {}),
                    },
                    pit_address=target,
                )
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=str(exc)) from exc
            return {"status": "success", "result": result}

        @self.app.post("/api/generate-phema")
        async def generate_phema_api(request: Request):
            """Route handler for POST /api/generate-phema."""
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Generate payload must be a JSON object.")
            return self.generate_phema(
                phema=payload.get("phema"),
                phema_id=payload.get("phema_id"),
                phema_name=payload.get("phema_name"),
                params=payload.get("params") or payload.get("input"),
                input_data=payload.get("input_data") or payload.get("input"),
            )

        @self.app.post("/api/phemas/snapshot")
        async def snapshot_phema_api(request: Request):
            """Route handler for POST /api/phemas/snapshot."""
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Snapshot payload must be a JSON object.")
            return self.snapshot_phema(
                phema=payload.get("phema"),
                phema_id=payload.get("phema_id"),
                phema_name=payload.get("phema_name"),
                params=payload.get("params") or payload.get("input"),
                input_data=payload.get("input_data") or payload.get("input"),
                cache_time=payload.get("cache_time"),
                cache_seconds=payload.get("cache_seconds"),
                cache_ttl_seconds=payload.get("cache_ttl_seconds"),
            )

        @self.app.post("/api/phemas/static")
        async def save_static_phema(request: Request):
            """Route handler for POST /api/phemas/static."""
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Static Phema payload must be a JSON object.")
            saved = self._save_static_phema(
                phema=payload.get("phema"),
                phema_id=payload.get("phema_id"),
                phema_name=payload.get("phema_name"),
                params=payload.get("params") or payload.get("input"),
                input_data=payload.get("input_data") or payload.get("input"),
                name=payload.get("name"),
                owner=payload.get("owner"),
                description=payload.get("description"),
                tags=payload.get("tags"),
                meta=payload.get("meta"),
            )
            return {"status": "success", "phema": saved}

    @staticmethod
    def _normalize_supported_phemas(raw_supported_phemas: Any) -> List[Phema]:
        """Internal helper to normalize the supported phemas."""
        if not raw_supported_phemas:
            return []

        normalized: List[Phema] = []
        for entry in raw_supported_phemas:
            if isinstance(entry, Phema):
                normalized.append(entry)
                continue
            if isinstance(entry, Mapping):
                normalized.append(Phema.from_dict(dict(entry)))
        return normalized

    @staticmethod
    def _phema_summary(phema: Phema) -> Dict[str, Any]:
        """Internal helper to return the phema summary."""
        return {
            "phema_id": phema.phema_id,
            "name": phema.name,
            "address": phema.resolved_address,
            "tags": list(phema.tags),
            "input_schema": dict(phema.input_schema),
            "output_schema": dict(getattr(phema, "output_schema", {}) or {}),
            "sections": [section.to_dict() for section in phema.sections],
            "snapshot_cache_time": int(getattr(phema, "snapshot_cache_time", 0) or 0),
        }

    def _refresh_supported_phema_metadata(self) -> None:
        """Internal helper for refresh supported phema metadata."""
        meta = dict(self.agent_card.get("meta") or {})
        meta["supported_phemas"] = [self._phema_summary(phema) for phema in self.supported_phemas]
        self.agent_card["meta"] = meta

        for practice in self.practices:
            if isinstance(practice, (GeneratePhemaPractice, SnapshotPhemaPractice)):
                practice.bind(self)
                for entry in self._resolve_callable_practice_entries(practice):
                    self._upsert_practice_metadata_in_card(entry)
                    self._persist_practice_to_pool(entry, is_deleted=False)

    def _ensure_local_phema_table(self) -> None:
        """Internal helper to ensure the local phema table exists."""
        if not self.pool:
            return
        if self.pool._TableExists(self.PHEMA_TABLE):
            return
        self.pool._CreateTable(self.PHEMA_TABLE, phemas_table_schema())

    def _ensure_snapshot_table(self) -> None:
        """Internal helper to ensure the snapshot table exists."""
        if not self.pool:
            return
        if self.pool._TableExists(self.PHEMA_SNAPSHOT_TABLE):
            return
        self.pool._CreateTable(self.PHEMA_SNAPSHOT_TABLE, phema_snapshots_table_schema())

    @staticmethod
    def _parse_snapshot_cache_seconds(*values: Any) -> int:
        """Internal helper to parse the snapshot cache seconds."""
        for value in values:
            if value is None or value == "":
                continue
            try:
                normalized = int(float(value))
            except (TypeError, ValueError):
                continue
            return max(normalized, 0)
        return 0

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        """Internal helper to parse the datetime."""
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str) and value:
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    @staticmethod
    def _snapshot_params_hash(params: Dict[str, Any]) -> str:
        """Internal helper to return the snapshot params hash."""
        serialized = json.dumps(params or {}, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _load_snapshot_rows(self) -> List[Dict[str, Any]]:
        """Internal helper to load the snapshot rows."""
        if self.pool:
            self._ensure_snapshot_table()
            rows = self.pool._GetTableData(self.PHEMA_SNAPSHOT_TABLE) or []
            return [dict(row) for row in rows if isinstance(row, dict)]
        return [dict(row) for row in self._snapshot_rows.values()]

    def _normalize_snapshot_row(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Internal helper to normalize the snapshot row."""
        if not isinstance(row, dict):
            return None
        snapshot_id = str(row.get("id") or "").strip()
        if not snapshot_id:
            return None
        snapshot_payload = row.get("snapshot") if isinstance(row.get("snapshot"), dict) else {}
        return {
            "snapshot_id": snapshot_id,
            "id": snapshot_id,
            "phema_id": str(row.get("phema_id") or ""),
            "phema_name": str(row.get("phema_name") or ""),
            "params_hash": str(row.get("params_hash") or ""),
            "params": dict(row.get("params") or {}),
            "tags": [str(tag) for tag in (row.get("tags") or []) if str(tag).strip()],
            "snapshot": snapshot_payload,
            "cache_ttl_seconds": self._parse_snapshot_cache_seconds(row.get("cache_ttl_seconds")),
            "expires_at": row.get("expires_at"),
            "meta": dict(row.get("meta") or {}),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "resolution_mode": str(
                row.get("resolution_mode")
                or snapshot_payload.get("resolution_mode")
                or (snapshot_payload.get("meta") or {}).get("resolution_mode")
                or ""
            ),
        }

    def _persist_snapshot_row(self, row: Dict[str, Any]) -> None:
        """Internal helper to persist the snapshot row."""
        if self.pool:
            self._ensure_snapshot_table()
            persisted = self.pool._Insert(self.PHEMA_SNAPSHOT_TABLE, row)
            if persisted is False:
                raise HTTPException(status_code=500, detail="Failed to persist Phema snapshot in local pool")
        self._snapshot_rows[str(row.get("id") or "")] = dict(row)

    def _get_snapshot_row(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Internal helper to return the snapshot row."""
        if not snapshot_id:
            return None
        if self.pool:
            self._ensure_snapshot_table()
            rows = self.pool._GetTableData(self.PHEMA_SNAPSHOT_TABLE, {"id": snapshot_id}) or []
            if rows:
                return self._normalize_snapshot_row(rows[-1])
        row = self._snapshot_rows.get(snapshot_id)
        return self._normalize_snapshot_row(row) if row else None

    def _list_snapshot_history(
        self,
        *,
        query: str = "",
        phema_id: str = "",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Internal helper to list the snapshot history."""
        rows = [self._normalize_snapshot_row(row) for row in self._load_snapshot_rows()]
        rows = [row for row in rows if row]
        normalized_phema_id = str(phema_id or "").strip()
        if normalized_phema_id:
            rows = [row for row in rows if row.get("phema_id") == normalized_phema_id]
        lowered = str(query or "").strip().lower()
        if lowered:
            rows = [
                row for row in rows
                if lowered in " ".join(
                    [
                        str(row.get("phema_name") or ""),
                        str(row.get("phema_id") or ""),
                        " ".join(str(tag) for tag in (row.get("tags") or [])),
                        json.dumps(row.get("params") or {}, sort_keys=True),
                        json.dumps(row.get("meta") or {}, sort_keys=True),
                        json.dumps(row.get("snapshot") or {}, sort_keys=True),
                    ]
                ).lower()
            ]
        rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        return rows[: max(int(limit), 0)]

    def _is_snapshot_fresh(self, row: Dict[str, Any], cache_ttl_seconds: int, now: Optional[datetime] = None) -> bool:
        """Return whether the value is a snapshot fresh."""
        if cache_ttl_seconds <= 0:
            return False
        current_time = now or datetime.now(timezone.utc)
        expires_at = self._parse_datetime(row.get("expires_at"))
        if expires_at is not None:
            return expires_at > current_time
        created_at = self._parse_datetime(row.get("created_at"))
        if created_at is None:
            return False
        return (current_time - created_at).total_seconds() < float(cache_ttl_seconds)

    def _find_cached_snapshot(
        self,
        *,
        phema_id: str,
        params_hash: str,
        cache_ttl_seconds: int,
    ) -> Optional[Dict[str, Any]]:
        """Internal helper to find the cached snapshot."""
        if cache_ttl_seconds <= 0:
            return None
        current_time = datetime.now(timezone.utc)
        candidates = self._list_snapshot_history(phema_id=phema_id, limit=500)
        for row in candidates:
            if row.get("params_hash") != params_hash:
                continue
            if self._is_snapshot_fresh(row, cache_ttl_seconds, now=current_time):
                return row
        return None

    def _normalize_phema_row(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Internal helper to normalize the phema row."""
        if not isinstance(row, dict):
            return None
        phema_id = str(row.get("id") or row.get("phema_id") or row.get("agent_id") or "").strip()
        if not phema_id:
            return None
        meta = dict(row.get("meta") or {})
        sections = list(row.get("sections") or [])
        resolution_mode = Phema.infer_resolution_mode(
            sections=sections,
            meta=meta,
            explicit_mode=row.get("resolution_mode"),
        )
        meta["resolution_mode"] = resolution_mode
        return {
            "id": phema_id,
            "phema_id": phema_id,
            "name": str(row.get("name") or "").strip(),
            "description": str(row.get("description") or ""),
            "owner": str(row.get("owner") or ""),
            "address": str(row.get("address") or ""),
            "tags": list(row.get("tags") or []),
            "input_schema": dict(row.get("input_schema") or {}),
            "output_schema": dict(row.get("output_schema") or {}),
            "sections": sections,
            "resolution_mode": resolution_mode,
            "meta": meta,
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }

    def _delete_pool_row(self, table_name: str, row_id: str) -> None:
        """Internal helper to delete the pool row."""
        if not self.pool or not row_id:
            return

        tables = getattr(self.pool, "tables", None)
        if isinstance(tables, dict):
            table = tables.get(table_name)
            if isinstance(table, dict):
                table.pop(row_id, None)
                return

        root_path = getattr(self.pool, "root_path", None)
        if isinstance(root_path, str) and root_path:
            safe_id = self.pool._safe_item_id(row_id) if hasattr(self.pool, "_safe_item_id") else row_id
            file_path = os.path.join(root_path, table_name, f"{safe_id}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
            return

        conn = getattr(self.pool, "conn", None)
        cursor = getattr(self.pool, "cursor", None)
        if conn is not None and cursor is not None:
            cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (row_id,))
            conn.commit()
            return

        supabase = getattr(self.pool, "supabase", None)
        if supabase is not None:
            supabase.table(table_name).delete().eq("id", row_id).execute()

    def _delete_snapshot_row(self, snapshot_id: str) -> None:
        """Internal helper to delete the snapshot row."""
        if not snapshot_id:
            raise HTTPException(status_code=400, detail="snapshot_id is required")
        existing = self._get_snapshot_row(snapshot_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Phema snapshot not found")
        self._delete_pool_row(self.PHEMA_SNAPSHOT_TABLE, snapshot_id)
        self._snapshot_rows.pop(snapshot_id, None)

    def _bootstrap_local_phema_store(self) -> None:
        """Internal helper for bootstrap local phema store."""
        if not self.pool:
            return
        try:
            self._ensure_local_phema_table()
            existing_rows = self.pool._GetTableData(self.PHEMA_TABLE) or []
            existing_ids = set()
            for row in existing_rows:
                normalized = self._normalize_phema_row(row)
                if not normalized:
                    continue
                existing_ids.add(normalized["phema_id"])
                created_at = normalized.get("created_at") or datetime.now(timezone.utc).isoformat()
                updated_at = normalized.get("updated_at") or created_at
                self._phema_timestamps[normalized["phema_id"]] = {
                    "created_at": created_at,
                    "updated_at": updated_at,
                }

            for phema in self.supported_phemas:
                if not phema.phema_id or phema.phema_id in existing_ids:
                    continue
                row = self._row_for_phema(phema)
                self.pool._Insert(self.PHEMA_TABLE, row)

            reloaded = self.pool._GetTableData(self.PHEMA_TABLE) or []
            loaded_phemas: List[Phema] = []
            for row in reloaded:
                normalized = self._normalize_phema_row(row)
                if not normalized:
                    continue
                loaded_phemas.append(Phema.from_dict(normalized))
                created_at = normalized.get("created_at") or datetime.now(timezone.utc).isoformat()
                updated_at = normalized.get("updated_at") or created_at
                self._phema_timestamps[normalized["phema_id"]] = {
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            if loaded_phemas:
                self.supported_phemas = loaded_phemas
        except Exception:
            return

    def _synthesize_runtime_config(self) -> Dict[str, Any]:
        """Internal helper to return the synthesize runtime config."""
        return {
            "name": self.agent_card.get("name", self.name),
            "type": "phemacast.agents.phemar.Phemar",
            "host": self.host,
            "port": self.port,
            "plaza_url": self.plaza_url,
            "role": self.agent_card.get("role", "phemar"),
            "description": self.agent_card.get("description", ""),
            "tags": list(self.agent_card.get("tags") or []),
            "phemar": {
                "description": self.config.get("description", self.agent_card.get("description", "")),
                "tags": list(self.config.get("tags") or self.agent_card.get("tags") or []),
                "supported_phemas": [phema.to_dict() for phema in self.supported_phemas],
            },
            "pools": list(self.raw_config.get("pools") or []),
            "practices": list(self.raw_config.get("practices") or []),
        }

    def _normalize_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to normalize the config document."""
        document = dict(config or {})
        document.setdefault("name", self.agent_card.get("name", self.name))
        document.setdefault("type", "phemacast.agents.phemar.Phemar")
        document.setdefault("host", self.host)
        document.setdefault("port", self.port)
        if self.plaza_url and "plaza_url" not in document:
            document["plaza_url"] = self.plaza_url
        document.setdefault("role", "phemar")
        document.setdefault("description", self.agent_card.get("description", ""))
        document["tags"] = list(document.get("tags") or self.agent_card.get("tags") or [])

        nested = dict(document.get("phemar") or {})
        nested.setdefault("description", self.config.get("description", document.get("description", "")))
        nested["tags"] = list(nested.get("tags") or self.config.get("tags") or document.get("tags") or [])
        raw_supported = (
            nested.get("supported_phemas")
            or nested.get("phemas")
            or document.get("supported_phemas")
            or document.get("phemas")
            or [phema.to_dict() for phema in self.supported_phemas]
        )
        nested["supported_phemas"] = [
            self._serialize_config_phema(entry)
            for entry in raw_supported
            if isinstance(entry, (Phema, Mapping))
        ]
        nested.pop("phemas", None)
        document["phemar"] = nested
        document.pop("supported_phemas", None)
        document.pop("phemas", None)

        if "pools" in self.raw_config and "pools" not in document:
            document["pools"] = self.raw_config["pools"]
        if "practices" in self.raw_config and "practices" not in document:
            document["practices"] = self.raw_config["practices"]
        return document

    def _load_config_document(self) -> Dict[str, Any]:
        """Internal helper to load the config document."""
        if self.config_path and self.config_path.exists():
            with self.config_path.open("r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            self.raw_config = dict(loaded)
            return self._normalize_config_document(loaded)
        return self._normalize_config_document(self.raw_config or self._synthesize_runtime_config())

    def _save_config_document(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to save the config document."""
        normalized = self._normalize_config_document(config)
        if self.config_path:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(json.dumps(normalized, indent=4), encoding="utf-8")
        self.raw_config = dict(normalized)
        self.config = dict(normalized.get("phemar") or normalized)
        self.supported_phemas = self._normalize_supported_phemas(self.config.get("supported_phemas"))
        self._refresh_supported_phema_metadata()
        return normalized

    @staticmethod
    def _serialize_config_phema(entry: Any) -> Dict[str, Any]:
        """Internal helper to serialize the config phema."""
        if isinstance(entry, Phema):
            return entry.to_dict()
        return Phema.from_dict(dict(entry)).to_dict()

    @staticmethod
    def _new_phema_id(name: str) -> str:
        """Internal helper for new phema ID."""
        normalized_name = str(name or "").strip().lower() or f"phema-{uuid.uuid4().hex[:8]}"
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"phemar-phema:{normalized_name}"))

    def _row_for_phema(self, phema: Phema) -> Dict[str, Any]:
        """Internal helper to return the row for the phema."""
        row = phema.to_dict()
        timestamps = self._phema_timestamps.get(phema.phema_id, {})
        now = datetime.now(timezone.utc).isoformat()
        row["created_at"] = timestamps.get("created_at", now)
        row["updated_at"] = timestamps.get("updated_at", row["created_at"])
        return row

    def _sync_supported_phemas_from_local_rows(self, rows: List[Dict[str, Any]]) -> None:
        """Internal helper to synchronize the supported phemas from local rows."""
        loaded: List[Phema] = []
        for row in rows:
            normalized = self._normalize_phema_row(row)
            if not normalized:
                continue
            loaded.append(Phema.from_dict(normalized))
        self.supported_phemas = loaded
        self._refresh_supported_phema_metadata()

    def _list_local_phemas(
        self,
        query: str = "",
        *,
        plaza_rows: Optional[List[Dict[str, Any]]] = None,
        plaza_lookup_failed: bool = False,
    ) -> List[Dict[str, Any]]:
        """Internal helper to list the local phemas."""
        rows: List[Dict[str, Any]] = []
        if self.pool:
            self._ensure_local_phema_table()
            rows = self.pool._GetTableData(self.PHEMA_TABLE) or []
            normalized_rows = [self._normalize_phema_row(row) for row in rows]
            normalized_rows = [row for row in normalized_rows if row]
        else:
            normalized_rows = [self._row_for_phema(phema) for phema in self.supported_phemas]

        lowered = str(query or "").strip().lower()
        if lowered:
            normalized_rows = [
                row for row in normalized_rows
                if lowered in " ".join(
                    [
                        str(row.get("name") or ""),
                        str(row.get("description") or ""),
                        str(row.get("owner") or ""),
                        str(row.get("address") or ""),
                        " ".join(str(tag) for tag in (row.get("tags") or [])),
                        json.dumps(row.get("meta") or {}, sort_keys=True),
                    ]
                ).lower()
            ]

        normalized_rows = self._annotate_local_phemas_with_plaza_status(
            normalized_rows,
            plaza_rows=plaza_rows,
            plaza_lookup_failed=plaza_lookup_failed,
        )
        normalized_rows.sort(key=lambda row: str(row.get("updated_at") or row.get("name") or ""), reverse=True)
        return normalized_rows

    def _annotate_local_phemas_with_plaza_status(
        self,
        rows: List[Dict[str, Any]],
        *,
        plaza_rows: Optional[List[Dict[str, Any]]] = None,
        plaza_lookup_failed: bool = False,
    ) -> List[Dict[str, Any]]:
        """Internal helper to return the annotate local phemas with Plaza status."""
        if not rows:
            return []

        annotated = [dict(row) for row in rows]
        if plaza_rows is None and self.plaza_url and not plaza_lookup_failed:
            try:
                plaza_rows = self._list_plaza_phemas()
            except requests.RequestException as exc:
                plaza_lookup_failed = True
                plaza_rows = []
                for row in annotated:
                    row["plaza_error"] = str(exc)

        if not self.plaza_url or plaza_lookup_failed:
            for row in annotated:
                row["source"] = "local"
                row["editable"] = True
                row["plaza_registered"] = False
                row["plaza_phema_id"] = ""
                row["plaza_address"] = ""
                row["plaza_editable"] = False
                row["plaza_lookup_failed"] = bool(plaza_lookup_failed)
                row["plaza_registration_mode"] = ""
                row["plaza_hosted_on_plaza"] = False
                row["plaza_downloadable"] = False
                row["plaza_host_phemar_name"] = ""
            return annotated

        plaza_rows = plaza_rows or []
        by_id = {
            str(row.get("phema_id") or "").strip(): row
            for row in plaza_rows
            if str(row.get("phema_id") or "").strip()
        }
        by_name = {
            str(row.get("name") or "").strip().lower(): row
            for row in plaza_rows
            if str(row.get("name") or "").strip()
        }

        for row in annotated:
            local_id = str(row.get("phema_id") or "").strip()
            local_name = str(row.get("name") or "").strip().lower()
            plaza_match = by_id.get(local_id) or by_name.get(local_name)
            row["source"] = "local"
            row["editable"] = True
            row["plaza_registered"] = bool(plaza_match)
            row["plaza_phema_id"] = str((plaza_match or {}).get("phema_id") or "")
            row["plaza_address"] = str((plaza_match or {}).get("address") or "")
            row["plaza_editable"] = bool((plaza_match or {}).get("editable"))
            row["plaza_lookup_failed"] = False
            row["plaza_registration_mode"] = str((plaza_match or {}).get("registration_mode") or "")
            row["plaza_hosted_on_plaza"] = bool((plaza_match or {}).get("hosted_on_plaza"))
            row["plaza_downloadable"] = bool((plaza_match or {}).get("downloadable"))
            row["plaza_host_phemar_name"] = str((plaza_match or {}).get("host_phemar_name") or "")
        return annotated

    def _safe_list_plaza_phemas(self, query: str = "") -> Tuple[List[Dict[str, Any]], str]:
        """Internal helper for safe list Plaza phemas."""
        try:
            return self._list_plaza_phemas(query=query), ""
        except requests.RequestException as exc:
            return [], str(exc)
        except Exception as exc:
            return [], str(exc)

    def _get_local_phema(self, phema_id: str) -> Optional[Phema]:
        """Internal helper to return the local phema."""
        row = self._get_local_phema_row(phema_id)
        if row:
            return Phema.from_dict(row)
        for phema in self.supported_phemas:
            if phema.phema_id == phema_id:
                return phema
        return None

    def _get_local_phema_row(self, phema_id: str) -> Optional[Dict[str, Any]]:
        """Internal helper to return the local phema row."""
        if self.pool and phema_id:
            self._ensure_local_phema_table()
            rows = self.pool._GetTableData(self.PHEMA_TABLE, {"id": phema_id}) or []
            if rows:
                return self._normalize_phema_row(rows[-1])
        for phema in self.supported_phemas:
            if phema.phema_id == phema_id:
                return self._row_for_phema(phema)
        return None

    def _persist_supported_phemas(self) -> None:
        """Internal helper to persist the supported phemas."""
        config = self._load_config_document()
        nested = dict(config.get("phemar") or {})
        nested["supported_phemas"] = [phema.to_dict() for phema in self.supported_phemas]
        config["phemar"] = nested
        self._save_config_document(config)

    def _save_local_phema(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Internal helper to save the local phema."""
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="Phema payload must be an object.")

        normalized_payload = dict(payload)
        normalized_payload["meta"] = dict(normalized_payload.get("meta") or {})
        normalized_payload["meta"]["resolution_mode"] = Phema.infer_resolution_mode(
            sections=normalized_payload.get("sections") if isinstance(normalized_payload.get("sections"), list) else [],
            meta=normalized_payload["meta"],
            explicit_mode=normalized_payload.get("resolution_mode"),
        )
        existing_id = str(
            normalized_payload.get("phema_id")
            or normalized_payload.get("id")
            or normalized_payload.get("agent_id")
            or ""
        ).strip()
        existing = self._get_local_phema_row(existing_id) if existing_id else None

        if not existing_id:
            generated_id = self._new_phema_id(str(normalized_payload.get("name") or ""))
            normalized_payload["phema_id"] = generated_id
            existing_id = generated_id
        elif existing is not None:
            normalized_payload.setdefault("address", existing.get("address", ""))

        phema = Phema.from_dict(normalized_payload)
        if not phema.name:
            raise HTTPException(status_code=400, detail="Phema name is required.")
        if not phema.phema_id:
            phema.address.pit_id = existing_id or self._new_phema_id(phema.name)

        replaced = False
        for index, current in enumerate(self.supported_phemas):
            if current.phema_id == phema.phema_id:
                self.supported_phemas[index] = phema
                replaced = True
                break
        if not replaced:
            self.supported_phemas.append(phema)

        now = datetime.now(timezone.utc).isoformat()
        created_at = (existing or {}).get("created_at", now)
        self._phema_timestamps[phema.phema_id] = {"created_at": created_at, "updated_at": now}
        if self.pool:
            self._ensure_local_phema_table()
            row = self._row_for_phema(phema)
            persisted = self.pool._Insert(self.PHEMA_TABLE, row)
            if persisted is False:
                raise HTTPException(status_code=500, detail="Failed to persist Phema in local pool")
        self._persist_supported_phemas()
        if self.pool:
            rows = self.pool._GetTableData(self.PHEMA_TABLE) or []
            self._sync_supported_phemas_from_local_rows(rows)
        return self._row_for_phema(phema)

    def _delete_local_phema(self, phema_id: str) -> None:
        """Internal helper to delete the local phema."""
        if not phema_id:
            raise HTTPException(status_code=404, detail="Phema not found")
        remaining = [phema for phema in self.supported_phemas if phema.phema_id != phema_id]
        if len(remaining) == len(self.supported_phemas):
            raise HTTPException(status_code=404, detail="Phema not found")
        self.supported_phemas = remaining
        self._phema_timestamps.pop(phema_id, None)
        if self.pool:
            self._delete_pool_row(self.PHEMA_TABLE, phema_id)
        self._persist_supported_phemas()
        self._refresh_supported_phema_metadata()

    def _plaza_owner_values(self) -> set[str]:
        """Internal helper to return the Plaza owner values."""
        values = {self.name}
        if self.agent_id:
            values.add(str(self.agent_id))
        card_name = str(self.agent_card.get("name") or "").strip()
        if card_name:
            values.add(card_name)
        return {value for value in values if value}

    def _can_edit_plaza_phema(self, row: Mapping[str, Any]) -> bool:
        """Return whether the value can edit Plaza phema."""
        owner = str(row.get("owner") or (row.get("card") or {}).get("owner") or "").strip()
        return bool(owner and owner in self._plaza_owner_values())

    def _normalize_plaza_phema_row(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Internal helper to normalize the Plaza phema row."""
        if not isinstance(row, dict):
            return None
        card = row.get("card") if isinstance(row.get("card"), dict) else {}
        payload = card if card else row
        try:
            phema = Phema.from_dict(payload)
        except Exception:
            return None
        normalized = self._row_for_phema(phema)
        row_meta = row.get("meta") if isinstance(row.get("meta"), dict) else {}
        card_meta = card.get("meta") if isinstance(card.get("meta"), dict) else {}
        combined_meta = {**card_meta, **row_meta}
        registration_mode = str(
            row.get("registration_mode")
            or combined_meta.get("registration_mode")
            or "hosted"
        ).strip().lower() or "hosted"
        if registration_mode not in {"hosted", "info_only"}:
            registration_mode = "hosted"
        normalized["owner"] = str(row.get("owner") or card.get("owner") or normalized.get("owner") or "")
        normalized["editable"] = self._can_edit_plaza_phema(row)
        normalized["source"] = "plaza"
        normalized["plaza_url"] = self.plaza_url or ""
        normalized["registration_mode"] = registration_mode
        normalized["hosted_on_plaza"] = registration_mode == "hosted"
        normalized["downloadable"] = bool(combined_meta.get("downloadable")) if "downloadable" in combined_meta else registration_mode == "hosted"
        normalized["host_phemar_name"] = str(combined_meta.get("host_phemar_name") or combined_meta.get("registered_by_phemar") or "")
        normalized["host_phemar_agent_id"] = str(combined_meta.get("host_phemar_agent_id") or combined_meta.get("registered_by_agent_id") or "")
        normalized["host_phemar_pit_address"] = combined_meta.get("host_phemar_pit_address") if isinstance(combined_meta.get("host_phemar_pit_address"), dict) else {}
        normalized["phema_pit_address"] = combined_meta.get("phema_pit_address") if isinstance(combined_meta.get("phema_pit_address"), dict) else {}
        normalized["access_practice_id"] = str(combined_meta.get("access_practice_id") or "generate_phema")
        return normalized

    def _list_plaza_phemas(self, query: str = "") -> List[Dict[str, Any]]:
        """Internal helper to list the Plaza phemas."""
        rows = self._search_directory(pit_type="Phema")
        normalized_rows = [self._normalize_plaza_phema_row(row) for row in rows]
        normalized_rows = [row for row in normalized_rows if row]
        lowered = str(query or "").strip().lower()
        if lowered:
            normalized_rows = [
                row for row in normalized_rows
                if lowered in " ".join(
                    [
                        str(row.get("name") or ""),
                        str(row.get("description") or ""),
                        str(row.get("owner") or ""),
                        str(row.get("address") or ""),
                        " ".join(str(tag) for tag in (row.get("tags") or [])),
                        json.dumps(row.get("meta") or {}, sort_keys=True),
                    ]
                ).lower()
            ]
        normalized_rows.sort(key=lambda row: str(row.get("updated_at") or row.get("name") or ""), reverse=True)
        return normalized_rows

    def _get_plaza_phema_row(self, phema_id: str) -> Optional[Dict[str, Any]]:
        """Internal helper to return the Plaza phema row."""
        if not phema_id:
            return None
        matches = self._search_directory(agent_id=phema_id, pit_type="Phema")
        if not matches:
            matches = self._search_directory(name=phema_id, pit_type="Phema")
        for row in matches:
            normalized = self._normalize_plaza_phema_row(row)
            if normalized and normalized.get("phema_id") == phema_id:
                return normalized
        return self._normalize_plaza_phema_row(matches[0]) if matches else None

    def _register_phema_on_plaza(
        self,
        *,
        phema: Any = None,
        phema_id: Optional[str] = None,
        registration_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Internal helper to register the phema on Plaza."""
        if not self.plaza_url:
            raise HTTPException(status_code=400, detail="Plaza URL is not configured for this Phemar")

        resolved_phema = self._resolve_phema(phema=phema, phema_id=phema_id)
        existing = self._get_plaza_phema_row(resolved_phema.phema_id)
        if existing and not existing.get("editable"):
            raise HTTPException(status_code=403, detail="Only the owner Phemar can edit this Plaza Phema")

        normalized_mode = str(registration_mode or "hosted").strip().lower() or "hosted"
        if normalized_mode not in {"hosted", "info_only"}:
            raise HTTPException(status_code=400, detail="registration_mode must be 'info_only' or 'hosted'")

        payload = resolved_phema.to_dict()
        payload["owner"] = self.name
        payload["resolution_mode"] = resolved_phema.resolution_mode
        payload["meta"] = {
            **dict(payload.get("meta") or {}),
            "resolution_mode": resolved_phema.resolution_mode,
            "registration_mode": normalized_mode,
            "hosted_on_plaza": normalized_mode == "hosted",
            "downloadable": normalized_mode == "hosted",
            "registered_by_phemar": self.name,
            "registered_by_agent_id": self.agent_id or "",
            "host_phemar_name": self.name,
            "host_phemar_agent_id": self.agent_id or "",
            "host_phemar_pit_address": self.pit_address.to_dict() if getattr(self, "pit_address", None) else {},
            "phema_pit_address": resolved_phema.address.to_dict() if getattr(resolved_phema, "address", None) else {},
            "access_practice_id": "generate_phema",
        }
        if normalized_mode == "info_only":
            payload["sections"] = []
            payload["input_schema"] = {}

        response = self._plaza_post("/api/phemas", json={"phema": payload})
        response_content = getattr(response, "content", None)
        data = response.json() if response_content or not hasattr(response, "content") else {}
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=data.get("detail") or "Failed to register Phema on Plaza")
        saved = data.get("phema") if isinstance(data, dict) else data
        normalized = self._normalize_plaza_phema_row(saved if isinstance(saved, dict) else payload)
        return normalized or payload

    def _deregister_phema_from_plaza(self, phema_id: str) -> None:
        """Internal helper for deregister phema from Plaza."""
        if not self.plaza_url:
            raise HTTPException(status_code=400, detail="Plaza URL is not configured for this Phemar")
        existing = self._get_plaza_phema_row(phema_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="Phema not found on Plaza")
        if not existing.get("editable"):
            raise HTTPException(status_code=403, detail="Only the owner Phemar can de-register this Plaza Phema")

        response = self._plaza_request("delete", f"/api/phemas/{phema_id}")
        data = response.json() if response.content else {}
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=data.get("detail") or "Failed to de-register Phema from Plaza")

    def _save_static_phema(
        self,
        *,
        phema: Any = None,
        phema_id: Optional[str] = None,
        phema_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        input_data: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
        owner: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Internal helper to save the static phema."""
        source_phema = self._resolve_phema(phema=phema, phema_id=phema_id, phema_name=phema_name)
        generated = self.generate_phema(
            phema=source_phema,
            params=params,
            input_data=input_data,
        )
        snapshot_phema = self._build_static_snapshot_phema(
            source_phema=source_phema,
            generated=generated,
            snapshot_id=self._new_phema_id(f"{source_phema.name} static snapshot {uuid.uuid4().hex}"),
            name=name,
            owner=owner,
            description=description,
            tags=tags,
            meta=meta,
        )

        return self._save_local_phema(snapshot_phema.to_dict())

    def _build_static_snapshot_phema(
        self,
        *,
        source_phema: Phema,
        generated: Dict[str, Any],
        snapshot_id: str,
        name: Optional[str] = None,
        owner: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[Any]] = None,
        meta: Optional[Dict[str, Any]] = None,
    ) -> Phema:
        """Internal helper to build the static snapshot phema."""
        snapshot_time = datetime.now(timezone.utc).isoformat()
        fetch_catalog: List[Dict[str, Any]] = []
        fetch_id_by_signature: Dict[str, str] = {}

        def _pit_address_dict(value: Any = None, *, fallback_id: Any = None) -> Dict[str, Any]:
            """Internal helper for pit address dict."""
            candidate = value if value not in (None, "") else fallback_id
            pit_address = PitAddress.from_value(candidate)
            if not pit_address.pit_id and candidate not in (None, ""):
                pit_address = PitAddress(pit_id=str(candidate), plazas=[])
            if not pit_address.pit_id and fallback_id not in (None, ""):
                pit_address = PitAddress(pit_id=str(fallback_id), plazas=[])
            if self.plaza_url:
                pit_address.register_plaza(self.plaza_url)
            return pit_address.to_dict() if pit_address.pit_id else {}

        def _register_fetch(entry: Dict[str, Any]) -> str:
            """Internal helper to register the fetch."""
            fetch_payload = dict(entry.get("result") or {}) if isinstance(entry.get("result"), dict) else {}
            fetch_meta = dict(fetch_payload.get("fetch") or {}) if isinstance(fetch_payload.get("fetch"), dict) else {}
            fetch_record = {
                "pulse_name": entry.get("pulse_name"),
                "pulse_pit_address": _pit_address_dict(entry.get("pulse_address")),
                "pulser_name": entry.get("pulser_name"),
                "pulser_pit_address": _pit_address_dict(fallback_id=entry.get("pulser_id")),
                "params": dict(fetch_payload.get("params") or {}),
                "fetch": fetch_meta,
                "data": fetch_payload.get("data"),
            }
            signature = json.dumps(
                {
                    "pulse_name": fetch_record.get("pulse_name"),
                    "pulse_pit_address": fetch_record.get("pulse_pit_address"),
                    "pulser_name": fetch_record.get("pulser_name"),
                    "pulser_pit_address": fetch_record.get("pulser_pit_address"),
                    "params": fetch_record.get("params"),
                },
                sort_keys=True,
                default=str,
            )
            existing_id = fetch_id_by_signature.get(signature)
            if existing_id:
                return existing_id
            fetch_id = str(uuid.uuid4())
            fetch_id_by_signature[signature] = fetch_id
            fetch_catalog.append(
                {
                    "id": fetch_id,
                    **fetch_record,
                }
            )
            return fetch_id

        def _extract_snapshot_value(entry: Dict[str, Any]) -> Any:
            """Internal helper to extract the snapshot value."""
            result_payload = dict(entry.get("result") or {}) if isinstance(entry.get("result"), dict) else {}
            if entry.get("field_path"):
                return result_payload.get("display_value")
            if result_payload.get("display_data") is not None:
                return result_payload.get("display_data")
            return result_payload.get("data")

        static_sections: List[Dict[str, Any]] = []
        for section in generated.get("sections", []):
            content_items: List[Any] = []
            for entry in section.get("content", []):
                if isinstance(entry, dict) and isinstance(entry.get("result"), dict):
                    fetch_id = _register_fetch(entry)
                    content_items.append(
                        {
                            "name": str(entry.get("key") or entry.get("pulse_name") or "Snapshot"),
                            "static": True,
                            "value": {
                                "field_path": entry.get("field_path"),
                                "fetch": fetch_id,
                                "data": _extract_snapshot_value(entry),
                            },
                        }
                    )
                else:
                    content_items.append(entry)
            static_sections.append(
                {
                    "name": section.get("name", ""),
                    "description": section.get("description", ""),
                    "modifier": section.get("modifier", ""),
                    "content": content_items,
                }
            )

        merged_meta = dict(source_phema.meta)
        if isinstance(meta, dict):
            merged_meta.update(meta)
        merged_meta.update(
            {
                "source_phema_id": source_phema.phema_id,
                "source_phema_name": source_phema.name,
                "source_phema_address": source_phema.resolved_address,
                "static_snapshot": True,
                "snapshot_generated_at": snapshot_time,
                "snapshot_input": generated.get("input_data", {}),
                "fetches": fetch_catalog,
            }
        )

        merged_tags = [str(tag) for tag in (tags or source_phema.tags) if str(tag).strip()]
        if "static" not in merged_tags:
            merged_tags.append("static")
        if "snapshot" not in merged_tags:
            merged_tags.append("snapshot")

        return Phema.from_dict(
            {
                "phema_id": str(snapshot_id or ""),
                "name": str(name or f"{source_phema.name} Static Snapshot").strip(),
                "description": str(description or source_phema.description or "Static snapshot generated from pulse data.").strip(),
                "owner": str(owner or source_phema.owner or self.name).strip(),
                "tags": merged_tags,
                "input_schema": dict(source_phema.input_schema),
                "output_schema": dict(getattr(source_phema, "output_schema", {}) or {}),
                "sections": static_sections,
                "meta": merged_meta,
                "resolution_mode": "static",
            }
        )

    def snapshot_phema(
        self,
        *,
        phema: Any = None,
        phema_id: Optional[str] = None,
        phema_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        input_data: Optional[Dict[str, Any]] = None,
        cache_time: Optional[Any] = None,
        cache_seconds: Optional[Any] = None,
        cache_ttl_seconds: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Return the snapshot phema."""
        source_phema = self._resolve_phema(phema=phema, phema_id=phema_id, phema_name=phema_name)
        runtime_params = dict(params or input_data or {})
        resolved_cache_ttl = self._parse_snapshot_cache_seconds(
            cache_ttl_seconds,
            cache_seconds,
            cache_time,
            source_phema.meta.get("snapshot_cache_time"),
            source_phema.meta.get("snapshot_cache_seconds"),
            source_phema.meta.get("cache_time"),
        )
        params_hash = self._snapshot_params_hash(runtime_params)
        cached = self._find_cached_snapshot(
            phema_id=source_phema.phema_id,
            params_hash=params_hash,
            cache_ttl_seconds=resolved_cache_ttl,
        )
        if cached:
            return {
                "status": "success",
                "snapshot_id": cached["snapshot_id"],
                "cached": True,
                "cache_ttl_seconds": resolved_cache_ttl,
                "snapshot": cached["snapshot"],
                "history": cached,
            }

        generated = self.generate_phema(
            phema=source_phema,
            params=runtime_params,
            input_data=runtime_params,
        )
        snapshot_id = str(uuid.uuid4())
        snapshot_phema = self._build_static_snapshot_phema(
            source_phema=source_phema,
            generated=generated,
            snapshot_id=snapshot_id,
        )
        created_dt = datetime.now(timezone.utc)
        created_at = created_dt.isoformat()
        expires_at = None
        if resolved_cache_ttl > 0:
            expires_at = datetime.fromtimestamp(
                created_dt.timestamp() + resolved_cache_ttl,
                tz=timezone.utc,
            ).isoformat()
        row = {
            "id": snapshot_id,
            "phema_id": source_phema.phema_id,
            "phema_name": source_phema.name,
            "params_hash": params_hash,
            "params": runtime_params,
            "tags": list(snapshot_phema.tags),
            "snapshot": snapshot_phema.to_dict(),
            "resolution_mode": snapshot_phema.resolution_mode,
            "cache_ttl_seconds": resolved_cache_ttl,
            "expires_at": expires_at,
            "meta": {
                "source_phema_id": source_phema.phema_id,
                "source_phema_name": source_phema.name,
                "source_phema_address": source_phema.resolved_address,
                "cache_ttl_seconds": resolved_cache_ttl,
            },
            "created_at": created_at,
            "updated_at": created_at,
        }
        self._persist_snapshot_row(row)
        normalized = self._normalize_snapshot_row(row) or row
        return {
            "status": "success",
            "snapshot_id": snapshot_id,
            "cached": False,
            "cache_ttl_seconds": resolved_cache_ttl,
            "snapshot": snapshot_phema.to_dict(),
            "history": normalized,
        }

    @staticmethod
    def _resolve_path(data: Any, path: str) -> Any:
        """Internal helper to resolve the path."""
        current = data
        remaining = str(path or "").strip()
        if not remaining:
            return current

        while remaining:
            if isinstance(current, Mapping):
                if remaining in current:
                    return current[remaining]
                matched = False
                for key in sorted(current.keys(), key=lambda value: len(str(value)), reverse=True):
                    key_text = str(key)
                    prefix = f"{key_text}."
                    if remaining.startswith(prefix):
                        current = current[key]
                        remaining = remaining[len(prefix):]
                        matched = True
                        break
                if matched:
                    continue
                return None

            if isinstance(current, list):
                part, separator, rest = remaining.partition(".")
                if not part.isdigit():
                    return None
                index = int(part)
                if index < 0 or index >= len(current):
                    return None
                current = current[index]
                if not separator:
                    return current
                remaining = rest
                continue

            return None

        return current

    @staticmethod
    def _assign_path(data: Dict[str, Any], path: str, value: Any) -> None:
        """Internal helper to return the assign path."""
        current = data
        parts = [part for part in str(path or "").split(".") if part]
        if not parts:
            return
        for part in parts[:-1]:
            node = current.get(part)
            if not isinstance(node, dict):
                node = {}
                current[part] = node
            current = node
        current[parts[-1]] = value

    def _project_selected_fields(self, payload: Any, selected_fields: List[str]) -> Any:
        """Internal helper for project selected fields."""
        if not selected_fields:
            return payload
        if not isinstance(payload, (dict, list)):
            return payload
        projected: Dict[str, Any] = {}
        for field_path in selected_fields:
            value = self._resolve_path(payload, field_path)
            if value is not None:
                self._assign_path(projected, field_path, value)
        return projected or {}

    def _normalize_content_item(self, item: Any) -> Dict[str, Any]:
        """Internal helper to normalize the content item."""
        if isinstance(item, str):
            pit_address = PitAddress.from_value(item)
            if pit_address.pit_id:
                return {"pulse_address": pit_address.to_ref(reference_plaza=self.plaza_url), "params": {}}
            if item.startswith("plaza://pulse/"):
                pulse_name = item.rsplit("/", 1)[-1]
                return {"pulse_name": pulse_name, "pulse_address": item, "params": {}}
            return {"pulse_name": item, "params": {}}

        if isinstance(item, Mapping):
            normalized = dict(item)
            item_type = str(normalized.get("type") or "").strip().lower()
            if item_type == "text":
                text_value = str(normalized.get("text") or "")
                return {
                    "type": "text",
                    "static": True,
                    "value": text_value,
                    "text": text_value,
                }
            pulse_name = normalized.get("pulse_name") or normalized.get("pulse") or normalized.get("name")
            pulse_address = normalized.get("pulse_address") or normalized.get("address")
            pulse_pit_address = PitAddress.from_value(pulse_address) if pulse_address else None
            if pulse_pit_address and pulse_pit_address.pit_id:
                pulse_address = pulse_pit_address.to_ref(reference_plaza=self.plaza_url)
            if pulse_address and not pulse_name and str(pulse_address).startswith("plaza://pulse/"):
                pulse_name = str(pulse_address).rsplit("/", 1)[-1]
            normalized["pulse_name"] = pulse_name
            normalized["pulse_address"] = pulse_address
            normalized["pulser_id"] = normalized.get("pulser_id")
            normalized["pulser_name"] = normalized.get("pulser_name")
            normalized["params"] = dict(normalized.get("params") or {})
            normalized["type"] = "pulse-field" if item_type == "pulse-field" or normalized.get("field_path") else "pulse"
            normalized["field_path"] = str(normalized.get("field_path") or "").strip()
            normalized["selected_fields"] = [str(field) for field in (normalized.get("selected_fields") or []) if str(field).strip()]
            if normalized["type"] == "pulse-field" and not normalized["selected_fields"] and normalized["field_path"]:
                normalized["selected_fields"] = [normalized["field_path"]]
            return normalized

        return {"static": True, "value": item}

    def _resolve_phema(
        self,
        *,
        phema: Any = None,
        phema_id: Optional[str] = None,
        phema_name: Optional[str] = None,
    ) -> Phema:
        """Internal helper to resolve the phema."""
        if isinstance(phema, Phema):
            return phema
        if isinstance(phema, Mapping):
            return Phema.from_dict(dict(phema))

        for configured in self.supported_phemas:
            if phema_id and configured.phema_id == phema_id:
                return configured
            if phema_name and configured.name == phema_name:
                return configured

        if phema_id and self.plaza_url:
            info = self.lookup_agent_info(phema_id)
            if info and str(info.get("pit_type") or info.get("type") or info.get("card", {}).get("pit_type")) == "Phema":
                return Phema.from_dict(info.get("card") or {})

        if phema_name and self.plaza_url:
            matches = self._search_directory(name=phema_name, pit_type="Phema")
            if matches:
                return Phema.from_dict(matches[0].get("card") or {})

        raise ValueError("Phema is required. Provide `phema`, `phema_id`, or `phema_name`.")

    def _search_directory(self, **params: Any) -> List[Dict[str, Any]]:
        """Internal helper to search the directory."""
        if not self.plaza_url:
            return []

        headers = self._ensure_token_valid() or {}
        if not headers.get("Authorization"):
            self.register()
            headers = self._ensure_token_valid() or {}
        if not headers.get("Authorization"):
            return []

        response = self._plaza_get("/search", params=params, headers=headers)
        if response.status_code == 401:
            self.register()
            headers = self._ensure_token_valid() or {}
            response = self._plaza_get("/search", params=params, headers=headers)
        if response.status_code != 200:
            return []
        payload = response.json()
        return payload if isinstance(payload, list) else []

    def _resolve_target_pit_address(self, definition: Mapping[str, Any]) -> Optional[PitAddress]:
        """Internal helper to resolve the target pit address."""
        explicit_address = definition.get("pit_address")
        if isinstance(explicit_address, Mapping):
            return self._coerce_pit_address(explicit_address)

        pulser_id = definition.get("pulser_id")
        if pulser_id:
            info = self.lookup_agent_info(str(pulser_id))
            if info:
                return self._coerce_pit_address((info.get("card") or {}).get("pit_address"))
            if self.plaza_url:
                return PitAddress(pit_id=str(pulser_id), plazas=[str(self.plaza_url).rstrip("/")])

        pulser_name = str(definition.get("pulser_name") or "").strip()
        pulser_address = str(definition.get("pulser_address") or "").strip()
        if pulser_name or pulser_address:
            candidates = self._search_directory(name=pulser_name or None, pit_type="Pulser")
            for candidate in candidates:
                card = candidate.get("card") if isinstance(candidate.get("card"), dict) else {}
                candidate_address = str(card.get("address") or candidate.get("address") or "").strip()
                if pulser_address and candidate_address and candidate_address != pulser_address:
                    continue
                pit_address = self._coerce_pit_address(card.get("pit_address"))
                if pit_address:
                    return pit_address

        pulse_name = definition.get("pulse_name")
        pulse_address = definition.get("pulse_address")
        results = self._search_directory(
            pit_type="Pulser",
            practice="get_pulse_data",
            pulse_name=pulse_name,
            pulse_address=pulse_address,
        )
        if not results:
            return None
        return self._coerce_pit_address((results[0].get("card") or {}).get("pit_address"))

    def _resolve_pulser_fetch_cost(self, definition: Mapping[str, Any], target: Optional[PitAddress]) -> float:
        """Internal helper to resolve the pulser fetch cost."""
        pulser_id = str((definition.get("pulser_id") or (target.pit_id if target else "") or "")).strip()
        if not pulser_id:
            return 0
        try:
            info = self.lookup_agent_info(pulser_id)
        except Exception:
            info = None
        card = info.get("card") if isinstance(info, dict) and isinstance(info.get("card"), dict) else {}
        practices = card.get("practices") if isinstance(card.get("practices"), list) else []
        for practice in practices:
            if not isinstance(practice, dict):
                continue
            if str(practice.get("id") or "").strip() != "get_pulse_data":
                continue
            try:
                return float(practice.get("cost") or 0)
            except (TypeError, ValueError):
                return 0
        return 0

    @staticmethod
    def _build_content_fetch_cache_key(definition: Mapping[str, Any], merged_params: Mapping[str, Any]) -> str:
        """Internal helper to build the content fetch cache key."""
        return json.dumps(
            {
                "pulse_name": definition.get("pulse_name"),
                "pulse_address": definition.get("pulse_address"),
                "pulser_id": definition.get("pulser_id"),
                "pulser_name": definition.get("pulser_name"),
                "params": dict(merged_params or {}),
            },
            sort_keys=True,
            default=str,
        )

    def _fetch_pulse_content(
        self,
        definition: Mapping[str, Any],
        params: Dict[str, Any],
        cache: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Internal helper to fetch the pulse content."""
        pulse_name = definition.get("pulse_name")
        pulse_address = definition.get("pulse_address")
        merged_params = dict(params or {})
        merged_params.update(dict(definition.get("params") or {}))
        cache_key = self._build_content_fetch_cache_key(definition, merged_params)
        if cache is not None and cache_key in cache:
            cached_result = dict(cache[cache_key])
            cached_fetch = dict(cached_result.get("fetch") or {})
            cached_fetch["cache_hit"] = True
            cached_result["fetch"] = cached_fetch
            return cached_result

        target = self._resolve_target_pit_address(definition)
        if not target:
            result = {
                "status": "missing-pulser",
                "pulse_name": pulse_name,
                "pulse_address": pulse_address,
                "params": merged_params,
                "pulser_id": definition.get("pulser_id"),
                "pulser_name": definition.get("pulser_name"),
                "fetch": {
                    "started_at": None,
                    "ended_at": None,
                    "duration_ms": 0,
                    "cost": 0,
                    "cache_hit": False,
                },
            }
            if cache is not None:
                cache[cache_key] = dict(result)
            return result

        started_dt = datetime.now(timezone.utc)
        started_perf = time.perf_counter()
        fetch_cost = self._resolve_pulser_fetch_cost(definition, target)
        try:
            data = self.UsePractice(
                "get_pulse_data",
                content={
                    "pulse_name": pulse_name,
                    "pulse_address": pulse_address,
                    "params": merged_params,
                },
                pit_address=target,
            )
            ended_dt = datetime.now(timezone.utc)
            duration_ms = max((time.perf_counter() - started_perf) * 1000.0, 0.0)
            result = {
                "status": "ok",
                "pulse_name": pulse_name,
                "pulse_address": pulse_address,
                "params": merged_params,
                "pulser_id": definition.get("pulser_id"),
                "pulser_name": definition.get("pulser_name"),
                "data": data,
                "fetch": {
                    "started_at": started_dt.isoformat(),
                    "ended_at": ended_dt.isoformat(),
                    "duration_ms": duration_ms,
                    "cost": fetch_cost,
                    "cache_hit": False,
                },
            }
            if cache is not None:
                cache[cache_key] = dict(result)
            return result
        except Exception as exc:
            ended_dt = datetime.now(timezone.utc)
            duration_ms = max((time.perf_counter() - started_perf) * 1000.0, 0.0)
            result = {
                "status": "error",
                "pulse_name": pulse_name,
                "pulse_address": pulse_address,
                "params": merged_params,
                "pulser_id": definition.get("pulser_id"),
                "pulser_name": definition.get("pulser_name"),
                "error": str(exc),
                "fetch": {
                    "started_at": started_dt.isoformat(),
                    "ended_at": ended_dt.isoformat(),
                    "duration_ms": duration_ms,
                    "cost": fetch_cost,
                    "cache_hit": False,
                },
            }
            if cache is not None:
                cache[cache_key] = dict(result)
            return result

    def _fetch_content_item(
        self,
        definition: Mapping[str, Any],
        params: Dict[str, Any],
        cache: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Internal helper to fetch the content item."""
        if definition.get("static"):
            return {
                "status": "ok",
                "type": definition.get("type") or "static",
                "value": definition.get("value"),
                "text": definition.get("text"),
            }
        base_result = self._fetch_pulse_content(definition, params, cache=cache)
        selected_fields = [str(field) for field in (definition.get("selected_fields") or []) if str(field).strip()]
        field_path = str(definition.get("field_path") or "").strip()
        data = base_result.get("data")
        display_data = self._project_selected_fields(data, selected_fields) if base_result.get("status") == "ok" else None
        display_value = self._resolve_path(data, field_path) if field_path and base_result.get("status") == "ok" else None
        return {
            **base_result,
            "type": definition.get("type") or "pulse",
            "selected_fields": selected_fields,
            "field_path": field_path,
            "display_data": display_data,
            "display_value": display_value,
        }

    def generate_phema(
        self,
        *,
        phema: Any = None,
        phema_id: Optional[str] = None,
        phema_name: Optional[str] = None,
        params: Optional[Dict[str, Any]] = None,
        input_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate the phema."""
        resolved_phema = self._resolve_phema(phema=phema, phema_id=phema_id, phema_name=phema_name)
        runtime_params = dict(params or input_data or {})

        rendered_sections: List[Dict[str, Any]] = []
        pulse_data: Dict[str, Any] = {}
        fetch_cache: Dict[str, Dict[str, Any]] = {}

        for section in resolved_phema.sections:
            resolved_content: List[Any] = []
            for index, item in enumerate(section.content):
                definition = self._normalize_content_item(item)
                result = self._fetch_content_item(definition, runtime_params, cache=fetch_cache)
                if definition.get("type") == "text":
                    resolved_content.append(
                        {
                            "type": "text",
                            "text": str(definition.get("text") or definition.get("value") or ""),
                        }
                    )
                    continue
                if definition.get("static"):
                    resolved_content.append(result.get("value"))
                    continue

                content_key = (
                    str(definition.get("key") or "")
                    or str(definition.get("name") or "")
                    or str(definition.get("pulse_name") or "")
                    or str(definition.get("pulse_address") or "")
                    or f"{section.name}:{index}"
                )
                if definition.get("field_path"):
                    content_key = f"{content_key}:{definition.get('field_path')}"
                pulse_data[content_key] = result.get("data") if result.get("status") == "ok" else result
                resolved_content.append(
                    {
                        "type": definition.get("type") or "pulse",
                        "key": content_key,
                        "pulse_name": definition.get("pulse_name"),
                        "pulse_address": definition.get("pulse_address"),
                        "pulser_id": definition.get("pulser_id"),
                        "pulser_name": definition.get("pulser_name"),
                        "field_path": definition.get("field_path"),
                        "selected_fields": [str(field) for field in (definition.get("selected_fields") or []) if str(field).strip()],
                        "result": result,
                    }
                )

            rendered_sections.append(
                {
                    "name": section.name,
                    "description": section.description,
                    "modifier": section.modifier,
                    "content": resolved_content,
                }
            )

        return {
            "status": "success",
            "phema": resolved_phema.to_dict(),
            "input_data": runtime_params,
            "sections": rendered_sections,
            "pulse_data": pulse_data,
        }
