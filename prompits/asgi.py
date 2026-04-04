"""
ASGI application bootstrap for Prompits.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS.

It mainly publishes constants such as `agent` and `app` that are consumed elsewhere in
the codebase.
"""

import os

from prompits.create_agent import build_agent, load_agent_config


def _resolve_config_path() -> str:
    """Internal helper to resolve the config path."""
    configured = os.getenv("PROMPITS_AGENT_CONFIG")
    if configured:
        return configured
    return "prompits/examples/plaza.agent"


agent = build_agent(load_agent_config(config_path=_resolve_config_path()))
app = agent.app
