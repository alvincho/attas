"""
Map castr implementation for the Castrs area.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the castrs package converts bound phema
output into concrete artifact formats.

Core types exposed here include `MapCastr`, which carry the main behavior or state
managed by this module.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional

import requests

from phemacast.agents.castr import Castr
from phemacast.map_phemar.executor import execute_map_phema


def _first_mapping_value(mapping: Mapping[str, Any], *keys: str) -> Any:
    """Internal helper to return the first mapping value."""
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return None


class MapCastr(Castr):
    """Execute a diagram-backed Phema produced by MapPhemar and persist the result as JSON."""

    def __init__(
        self,
        config: Any = None,
        *,
        config_path: Any = None,
        name: str = "MapCastr",
        host: str = "127.0.0.1",
        port: int = 8000,
        plaza_url: Optional[str] = None,
        agent_card: Optional[Dict[str, Any]] = None,
        pool: Any = None,
        auto_register: bool = True,
        request_post: Optional[Callable[..., Any]] = None,
        timeout_sec: float = 30.0,
    ):
        """Initialize the map castr."""
        super().__init__(
            config=config,
            config_path=config_path,
            name=name,
            host=host,
            port=port,
            plaza_url=plaza_url,
            agent_card=agent_card,
            pool=pool,
            auto_register=auto_register,
        )
        self.media_type = str(self.config.get("media_type") or "JSON")
        self.request_post = request_post or requests.post
        try:
            self.timeout_sec = max(float(self.config.get("timeout_sec") or timeout_sec), 0.1)
        except (TypeError, ValueError):
            self.timeout_sec = max(float(timeout_sec), 0.1)

    def cast(
        self,
        phema: Dict[str, Any],
        format: str,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Cast the value."""
        if not isinstance(phema, Mapping):
            raise ValueError("MapCastr requires a Phema JSON object.")

        normalized_preferences = dict(preferences or {}) if isinstance(preferences, Mapping) else {}
        input_data = _first_mapping_value(normalized_preferences, "input", "initial_input", "params")
        extra_parameters = _first_mapping_value(normalized_preferences, "extra_parameters", "extra_params")
        node_parameters = _first_mapping_value(normalized_preferences, "node_parameters", "node_params")
        plaza_override = str(_first_mapping_value(normalized_preferences, "plaza_url", "plazaUrl") or "").strip()

        execution = execute_map_phema(
            dict(phema),
            input_data=input_data,
            extra_parameters=extra_parameters if isinstance(extra_parameters, Mapping) else {},
            node_parameters=node_parameters if isinstance(node_parameters, Mapping) else {},
            plaza_url=plaza_override or self.plaza_url or "",
            request_post=self.request_post,
            timeout_sec=self.timeout_sec,
        )

        target_format = str(format or self.media_type or "JSON").strip().upper() or "JSON"
        media_id = str(uuid.uuid4())
        filename = f"{media_id}.json"
        location = ""
        url = ""
        artifact = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "phema_id": execution.get("phema_id") or str(phema.get("phema_id") or phema.get("id") or ""),
            "phema_name": execution.get("phema_name") or str(phema.get("name") or "Untitled Map Phema"),
            "preferences": normalized_preferences,
            "execution": execution,
        }

        if self.pool and hasattr(self.pool, "root_path"):
            media_dir = os.path.join(self.pool.root_path, "media")
            os.makedirs(media_dir, exist_ok=True)
            file_path = os.path.join(media_dir, filename)
            with open(file_path, "w", encoding="utf-8") as fh:
                json.dump(artifact, fh, ensure_ascii=True, indent=2)
            location = f"media/{filename}"
            url = f"/api/media/{filename}"

        return {
            "status": "success",
            "media_id": media_id,
            "format": target_format,
            "message": f"Successfully executed MapPhemar Phema: {execution.get('phema_name') or phema.get('name') or 'Untitled'}",
            "location": location,
            "url": url,
            "result": execution.get("output"),
            "steps": execution.get("steps") or [],
            "execution": execution,
        }


__all__ = ["MapCastr"]
