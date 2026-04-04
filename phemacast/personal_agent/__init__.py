"""
Public package exports for `phemacast.personal_agent`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the personal_agent package powers the file-
backed personal research workbench and its web UI.

It re-exports symbols such as `app`, `create_app`, and `MapPhemarAgent` so callers can
import the package through a stable surface.
"""

__all__ = ["app", "create_app", "MapPhemarAgent"]


def __getattr__(name):
    """Handle getattr."""
    if name in {"app", "create_app"}:
        from phemacast.personal_agent.app import app, create_app

        return app if name == "app" else create_app
    if name == "MapPhemarAgent":
        from phemacast.agents.map_phemar import MapPhemarAgent

        return MapPhemarAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
