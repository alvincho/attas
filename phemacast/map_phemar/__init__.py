"""
Public package exports for `phemacast.map_phemar`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the map_phemar package supports map-oriented
phema execution and its UI/runtime helpers.

It re-exports symbols such as `MAP_PHEMAR_STATIC_DIR`, `MAP_PHEMAR_SHARED_STATIC_DIR`,
`MAP_PHEMAR_TEMPLATE_DIR`, `MapExecutionError`, and `PlazaPaneRunRequest` so callers can
import the package through a stable surface.
"""

from phemacast.map_phemar.runtime import (
    MAP_PHEMAR_STATIC_DIR,
    MAP_PHEMAR_SHARED_STATIC_DIR,
    MAP_PHEMAR_TEMPLATE_DIR,
    PlazaPaneRunRequest,
    build_map_phemar_bootstrap,
    create_embedded_map_phemar,
    get_embedded_map_phemar,
    get_map_phemar_service,
    get_map_phemar_asset_version,
    mount_map_phemar_alias_routes,
    mount_map_phemar_ui_alias_routes,
    mount_map_phemar_plaza_proxy_routes,
)
from phemacast.map_phemar.executor import MapExecutionError, execute_map_phema

__all__ = [
    "MAP_PHEMAR_STATIC_DIR",
    "MAP_PHEMAR_SHARED_STATIC_DIR",
    "MAP_PHEMAR_TEMPLATE_DIR",
    "MapExecutionError",
    "PlazaPaneRunRequest",
    "build_map_phemar_bootstrap",
    "create_embedded_map_phemar",
    "execute_map_phema",
    "get_embedded_map_phemar",
    "get_map_phemar_service",
    "get_map_phemar_asset_version",
    "mount_map_phemar_alias_routes",
    "mount_map_phemar_ui_alias_routes",
    "mount_map_phemar_plaza_proxy_routes",
]
