"""
Compatibility wrapper for `phemacast.core.phema`.

Phemacast builds on the framework-owned `Phema` model exposed by Prompits. This
module remains as an import-stable shim for existing Phemacast call sites.
"""

from prompits.core.phema import Phema, PhemaSection

__all__ = ["Phema", "PhemaSection"]
