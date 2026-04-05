"""
Coordinator and boss-agent logic for `prompits.teamwork.boss`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the teamwork package models
cooperative agent workflows and their supporting runtime pieces.

Core types exposed here include `TeamBossAgent`, which carry the main behavior or state
managed by this module.
"""

from __future__ import annotations

from typing import Any, Dict

from prompits.dispatcher.boss import DispatcherBossAgent
from prompits.teamwork.runtime import normalize_teamwork_config


class TeamBossAgent(DispatcherBossAgent):
    """Agent implementation for team boss workflows."""
    def __init__(
        self,
        name: str = "TeamBoss",
        host: str = "127.0.0.1",
        port: int = 8065,
        plaza_url: str | None = None,
        agent_card: Dict[str, Any] | None = None,
        pool: Any = None,
        config: Any = None,
        config_path: Any = None,
        manager_address: str = "",
        manager_party: str = "",
        auto_register: bool | None = None,
    ):
        """Initialize the team boss agent."""
        normalized_config = normalize_teamwork_config(config_path or config, role="boss")
        card = dict(agent_card or normalized_config.get("agent_card") or {})
        card.setdefault("name", str(normalized_config.get("name") or name))
        card["role"] = str(normalized_config.get("role") or card.get("role") or "boss")
        card["description"] = str(
            normalized_config.get("description")
            or card.get("description")
            or "Teamwork boss UI for issuing and monitoring manager jobs."
        )

        super().__init__(
            name=str(normalized_config.get("name") or name),
            host=host,
            port=port,
            plaza_url=plaza_url,
            agent_card=card,
            pool=pool,
            config=normalized_config,
            config_path=None,
            dispatcher_address=str(manager_address or normalized_config.get("dispatcher_address") or "").strip(),
            dispatcher_party=str(
                manager_party or normalized_config.get("dispatcher_party") or normalized_config.get("party") or ""
            ).strip(),
            auto_register=auto_register,
        )

        self.manager_address = self.dispatcher_address
        self.manager_party = self.dispatcher_party


__all__ = ["TeamBossAgent"]
