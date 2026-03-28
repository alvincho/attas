import logging
import os
from typing import Any, Dict, Optional
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from prompits.agents.base import BaseAgent
from prompits.core.message import Message
from prompits.core.pool import Pool
from prompits.practices.plaza import PlazaPractice

logger = logging.getLogger(__name__)

class UserAgent(BaseAgent):
    """
    Browser-facing agent with UI endpoints for Plaza discovery and messaging.

    `UserAgent` adds template/static serving and convenience API routes on top
    of `BaseAgent` so users can inspect plazas and send messages from a web UI.
    """

    def __init__(self, name: str, host: str = "127.0.0.1", port: int = 8000, plaza_url: Optional[str] = None, agent_card: Dict[str, Any] = None, pool: Optional[Pool] = None):
        super().__init__(name, host, port, plaza_url, agent_card, pool)
        
        # Determine the directory of the current file to set up templates and static files correctly
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_dir = os.path.join(current_dir, "templates")
        static_dir = os.path.join(current_dir, "static")
        
        # Ensure directories exist
        os.makedirs(template_dir, exist_ok=True)
        os.makedirs(static_dir, exist_ok=True)
        
        self.templates = Jinja2Templates(directory=template_dir)
        self.app.mount("/static", StaticFiles(directory=static_dir), name="static")
        
        self.setup_user_agent_routes()

    def setup_user_agent_routes(self):
        """Mount HTML pages and UI-facing JSON APIs used by the frontend."""
        supported_pit_types = sorted(PlazaPractice.SUPPORTED_PIT_TYPES)

        @self.app.get("/")
        async def index(request: Request):
            return self.templates.TemplateResponse(
                "plazas.html",
                {"request": request, "agent_name": self.name, "supported_pit_types": supported_pit_types},
            )

        @self.app.get("/plazas")
        async def plazas(request: Request):
            return self.templates.TemplateResponse(
                "plazas.html",
                {"request": request, "agent_name": self.name, "supported_pit_types": supported_pit_types},
            )

        @self.app.get("/api/plazas_status")
        async def plazas_status(request: Request):
            def _plazas_status_sync() -> Dict[str, Any]:
                if not self.plaza_url:
                    return {"status": "success", "plazas": []}

                plazas_data = []
                url = self.plaza_url
                status = {"url": url, "online": False, "agents": [], "card": None}

                pit_type = request.query_params.get("pit_type")
                search_params = {"include_activity": "true"}
                if pit_type:
                    search_params["pit_type"] = pit_type

                try:
                    headers = self._ensure_token_valid()
                    if not headers:
                        self.logger.warning(f"Could not secure valid token for Plaza status check. Attempting re-register.")
                        self.register()
                        headers = self._ensure_token_valid() or {}

                    health_resp = self._plaza_get("/health")
                    if health_resp.status_code == 200:
                        status["online"] = True

                        try:
                            card_resp = self._plaza_get("/.well-known/agent-card")
                            if card_resp.status_code == 200:
                                status["card"] = card_resp.json()
                        except Exception:
                            pass

                        try:
                            if not headers.get("Authorization"):
                                self.logger.warning(f"No valid Plaza Authorization header; skipping /search.")
                                status["agents"] = []
                                plazas_data.append(status)
                                return {"status": "success", "plazas": plazas_data}

                            search_resp = self._plaza_get("/search", params=search_params, headers=headers)
                            if search_resp.status_code == 200:
                                raw_agents = search_resp.json()
                                normalized_agents = []
                                for agent in raw_agents:
                                    if isinstance(agent, dict):
                                        normalized_agents.append(agent)
                                    elif isinstance(agent, (list, tuple)) and len(agent) == 2:
                                        normalized_agents.append({"name": agent[0], "card": agent[1]})
                                if not any((a.get("name") == self.name) for a in normalized_agents):
                                    self.logger.warning(f"Missing from Plaza directory. Re-registering and retrying /search once.")
                                    self.register()
                                    retry_headers = self._ensure_token_valid() or {}
                                    if retry_headers.get("Authorization"):
                                        retry_resp = self._plaza_get("/search", params=search_params, headers=retry_headers)
                                        if retry_resp.status_code == 200:
                                            raw_agents = retry_resp.json()
                                            normalized_agents = []
                                            for agent in raw_agents:
                                                if isinstance(agent, dict):
                                                    normalized_agents.append(agent)
                                                elif isinstance(agent, (list, tuple)) and len(agent) == 2:
                                                    normalized_agents.append({"name": agent[0], "card": agent[1]})
                                status["agents"] = normalized_agents
                            elif search_resp.status_code in (401, 403):
                                self.logger.warning(f"/search unauthorized ({search_resp.status_code}). Triggering register and retry.")
                                self.register()
                                retry_headers = self._ensure_token_valid() or {}
                                if retry_headers.get("Authorization"):
                                    retry_resp = self._plaza_get("/search", params=search_params, headers=retry_headers)
                                    if retry_resp.status_code == 200:
                                        raw_agents = retry_resp.json()
                                        normalized_agents = []
                                        for agent in raw_agents:
                                            if isinstance(agent, dict):
                                                normalized_agents.append(agent)
                                            elif isinstance(agent, (list, tuple)) and len(agent) == 2:
                                                normalized_agents.append({"name": agent[0], "card": agent[1]})
                                        status["agents"] = normalized_agents
                                    else:
                                        status["agents"] = []
                                else:
                                    status["agents"] = []
                            else:
                                status["agents"] = []
                        except Exception as e:
                            self.logger.warning(f"Failed to fetch agents from Plaza at {url}: {e}")
                            status["agents"] = []
                except Exception as e:
                    self.logger.warning(f"Failed to fetch status for Plaza at {url}: {e}")

                plazas_data.append(status)
                return {"status": "success", "plazas": plazas_data}

            return await run_in_threadpool(_plazas_status_sync)

        @self.app.post("/api/send_message")
        async def api_send_message(request: Request):
            try:
                data = await request.json()
                receiver = data.get("receiver")
                content = data.get("content")
                msg_type = data.get("msg_type", "message")
                
                if not receiver or not content:
                    return {"status": "error", "message": "Missing receiver or content"}

                result = await run_in_threadpool(self.send, receiver, content, msg_type)
                if result:
                    return {"status": "success", "message": f"Message sent to {receiver}", "data": result if isinstance(result, dict) else None}
                else:
                    return {"status": "error", "message": f"Failed to send message to {receiver}"}
            except Exception as e:
                self.logger.error(f"API send_message failed: {e}")
                return {"status": "error", "message": str(e)}

    def receive(self, message: Message):
        """Handle incoming messages (required by BaseAgent)."""
        self.logger.info(f"Received message: {message}")

    def run(self):
        """Legacy run method."""
        import uvicorn
        uvicorn.run(self.app, host=self.host, port=self.port)
