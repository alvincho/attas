"""
Public package exports for `phemacast.castrs`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the castrs package converts bound phema
output into concrete artifact formats.

It re-exports symbols such as `MapCastr` so callers can import the package through a
stable surface.
"""

from phemacast.castrs.map_castr import MapCastr

__all__ = [
    "MapCastr",
]
