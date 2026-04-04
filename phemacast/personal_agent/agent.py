"""
Agent implementation for `phemacast.personal_agent.agent`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the personal_agent package powers the file-
backed personal research workbench and its web UI.

The file is intentionally lightweight, but its placement in the package makes it part of
the documented module surface.
"""

from phemacast.agents.map_phemar import MapPhemarAgent

__all__ = ["MapPhemarAgent"]
