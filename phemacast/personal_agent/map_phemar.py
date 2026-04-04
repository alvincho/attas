"""
Map-Phemar helpers for `phemacast.personal_agent.map_phemar`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the personal_agent package powers the file-
backed personal research workbench and its web UI.

The file is intentionally lightweight, but its placement in the package makes it part of
the documented module surface.
"""

from phemacast.map_phemar.runtime import (
    create_embedded_map_phemar as create_map_phemar,
    get_embedded_map_phemar as get_map_phemar,
)

__all__ = ["create_map_phemar", "get_map_phemar"]
