import os

from prompits.create_agent import build_agent, load_agent_config


def _resolve_config_path() -> str:
    configured = os.getenv("PROMPITS_AGENT_CONFIG")
    if configured:
        return configured
    return "attas/configs/plaza.agent"


agent = build_agent(load_agent_config(config_path=_resolve_config_path()))
app = agent.app
