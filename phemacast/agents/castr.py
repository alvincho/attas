import logging
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

import requests
import uvicorn
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from prompits.agents.standby import StandbyAgent
from prompits.core.message import Message
from prompits.core.practice import Practice

logger = logging.getLogger(__name__)


ConfigInput = Union[str, Path, Mapping[str, Any]]

def _read_config(config: ConfigInput) -> Dict[str, Any]:
    if isinstance(config, Mapping):
        return dict(config)
    config_path = Path(config)
    with config_path.open("r", encoding="utf-8") as fh:
        return json.load(fh)

def _merge_tags(*tag_groups: Any) -> List[str]:
    merged: List[str] = []
    for group in tag_groups:
        if not group:
            continue
        for tag in group:
            value = str(tag)
            if value and value not in merged:
                merged.append(value)
    return merged


class CastPractice(Practice):
    """Expose `agent.cast()` as a mounted callable practice."""

    def __init__(self):
        super().__init__(
            name="Cast Phema",
            description="Transforms a Phema into a specific media format.",
            id="cast_phema",
            tags=["castr", "cast", "media"],
            examples=["POST /api/cast_phema {'phema': {...}, 'format': 'pdf'}"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def bind(self, agent):
        super().bind(agent)
        self.parameters = {
            "phema": {
                "type": "object",
                "description": "Phema payload to resolve.",
            },
            "format": {
                "type": "string",
                "description": "Target media format, e.g., PDF, PPT.",
            },
            "preferences": {
                "type": "object",
                "description": "Output rendering preferences such as layout, size, theme.",
            },
        }

    def mount(self, app):
        router = APIRouter()

        @router.post(self.path)
        async def cast_phema(message: Message):
            content = message.content or {}
            if not isinstance(content, dict):
                raise HTTPException(status_code=400, detail="Cast content must be a JSON object.")
            return self.execute(**content)

        app.include_router(router)

    def execute(self, **kwargs) -> Any:
        if not self.agent:
            raise RuntimeError("CastPractice is not bound to an agent.")

        return self.agent.cast(
            phema=kwargs.get("phema", {}),
            format=kwargs.get("format", ""),
            preferences=kwargs.get("preferences")
        )

class Castr(StandbyAgent):
    """
    Standby agent specialized for casting Phema into media.
    """

    def __init__(
        self,
        config: Optional[ConfigInput] = None,
        *,
        config_path: Optional[ConfigInput] = None,
        name: str = "Castr",
        host: str = "127.0.0.1",
        port: int = 8000,
        plaza_url: Optional[str] = None,
        agent_card: Optional[Dict[str, Any]] = None,
        pool: Any = None,
        auto_register: bool = True,
    ):
        config_data = _read_config(config) if config is not None else {}
        resolved_config_path = config_path
        if resolved_config_path is None and isinstance(config, (str, Path)):
            resolved_config_path = config

        self.config_path = Path(resolved_config_path).resolve() if resolved_config_path else None
        self.raw_config = dict(config_data)
        castr_config = config_data.get("castr", config_data)

        resolved_name = str(config_data.get("name") or castr_config.get("name") or name)
        resolved_host = str(config_data.get("host") or castr_config.get("host") or host)
        resolved_port = int(config_data.get("port") or castr_config.get("port") or port)
        resolved_plaza_url = config_data.get("plaza_url") or castr_config.get("plaza_url") or plaza_url

        self.config = castr_config
        self.media_type = castr_config.get("media_type", "PDF")

        card = dict(agent_card or castr_config.get("agent_card") or {})
        card.setdefault("name", resolved_name)
        card.setdefault("role", "castr")
        card.setdefault("pit_type", "Agent")
        card.setdefault(
            "description",
            castr_config.get("description", "A Castr agent specialized in rendering Phemas into media."),
        )
        card["tags"] = _merge_tags(card.get("tags"), castr_config.get("tags"), ["castr", "media", "render"])
        
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
        try:
            self.app.mount("/static", StaticFiles(directory=static_dir), name="static")
        except:
            pass # Might already be mounted by base class if it has such logic

        # Mount the pool's root_path to serve generated media files
        if self.pool and hasattr(self.pool, "root_path"):
            abs_pool_path = os.path.abspath(self.pool.root_path)
            try:
                self.app.mount("/files", StaticFiles(directory=abs_pool_path), name="files")
            except:
                pass

        self.add_practice(CastPractice())
        self._setup_castr_routes()

        if self.plaza_url and auto_register:
            self.register()

    @classmethod
    def from_config(cls, config: ConfigInput, **kwargs: Any) -> "Castr":
        return cls(config=config, **kwargs)

    def register(self, *, start_reconnect_on_failure: bool = True, request_retries: Optional[int] = None):
        if self.plaza_token and time.time() < (self.token_expires_at - 60):
            return
        return super().register(
            start_reconnect_on_failure=start_reconnect_on_failure,
            request_retries=request_retries,
        )
        
    def _setup_castr_routes(self) -> None:
        @self.app.get("/")
        async def castr_ui(request: Request):
            return self.templates.TemplateResponse(
                "castr_ui.html",
                {
                    "request": request,
                    "agent_name": self.name,
                    "media_type": self.media_type,
                    "plaza_url": self.plaza_url or "",
                },
            )

        @self.app.get("/api/plazas/phemas")
        async def list_plaza_phemas():
            if not self.plaza_url:
                return {"status": "success", "phemas": []}
            try:
                # Use authenticated directory search to find all registered Phema agents.
                # This ensures we get agents registered by common property 'pit_type=Phema'.
                results = self.search(pit_type="Phema")
                logger.debug(f"[{self.name}] Castr search(pit_type='Phema') returned {len(results)} results from Plaza")
                phemas = []
                for res in results:
                    card = res.get("card")
                    if isinstance(card, dict):
                        # Construct a Phema-compatible object for the UI.
                        # The 'card' typically contains the full Phema definition.
                        item = dict(card)
                        item.setdefault("name", res.get("name") or item.get("name"))
                        item.setdefault("description", res.get("description") or item.get("description"))
                        item.setdefault("owner", res.get("owner") or item.get("owner"))
                        # UI often expects 'phema_id' to match the directory 'agent_id'.
                        # The 'agent_id' is the primary identifier in the Plaza directory results.
                        if "phema_id" not in item:
                            item["phema_id"] = res.get("agent_id") or res.get("id")
                        phemas.append(item)
                logger.debug(f"[{self.name}] Sending {len(phemas)} phemas to UI: {[p.get('name') for p in phemas]}")
                return {"status": "success", "phemas": phemas}
            except Exception as e:
                return {"status": "error", "message": str(e), "phemas": []}

        @self.app.get("/api/media/{filename}")
        async def get_media_file(filename: str):
            if not self.pool or not hasattr(self.pool, "root_path"):
                raise HTTPException(status_code=404, detail="Pool not configured")
            
            file_path = os.path.join(self.pool.root_path, "media", filename)
            if not os.path.exists(file_path):
                raise HTTPException(status_code=404, detail="File not found")
            
            return FileResponse(file_path)

        @self.app.post("/api/cast_phema")
        async def cast_phema_api(request: Request):
            payload = await request.json()
            if not isinstance(payload, dict):
                raise HTTPException(status_code=400, detail="Cast payload must be a JSON object.")
            return self.cast(
                phema=payload.get("phema", {}),
                format=payload.get("format", self.media_type),
                preferences=payload.get("preferences")
            )

    def cast(self, phema: Dict[str, Any], format: str, preferences: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Simulate the rendering of Phema into format.
        """
        if not format:
            format = self.media_type

        media_id = str(uuid.uuid4())
        ext = format.lower()
        filename = f"{media_id}.{ext}"
        
        # If we have a FileSystemPool, we can actually "generate" a dummy file
        relative_path = f"media/{filename}"
        url = None

        if self.pool and hasattr(self.pool, "root_path"):
            media_dir = os.path.join(self.pool.root_path, "media")
            os.makedirs(media_dir, exist_ok=True)
            file_path = os.path.join(media_dir, filename)
            
            # Create a dummy content based on format
            with open(file_path, "w") as f:
                f.write(f"Dummy {format} content for Phema: {phema.get('name', 'Untitled')}\n")
                f.write(f"Generated at: {datetime.now(timezone.utc).isoformat()}\n")
                f.write(f"Preferences: {json.dumps(preferences, indent=2)}\n")
            
            url = f"/api/media/{filename}"

        return {
            "status": "success",
            "media_id": media_id,
            "format": format,
            "message": f"Successfully rendered Phema to {format}",
            "location": relative_path,
            "url": url
        }
