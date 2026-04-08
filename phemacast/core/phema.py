"""
Compatibility wrapper for `phemacast.core.phema`.

Phemacast owns the `Phema` label while building on the framework-owned
structured blueprint model exposed by Prompits. This
module remains as an import-stable shim for existing Phemacast call sites.
"""

from prompits.core.blueprint import BlueprintSection, StructuredBlueprint


PhemaSection = BlueprintSection
Phema = StructuredBlueprint

__all__ = ["Phema", "PhemaSection"]
