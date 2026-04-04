"""
Party module for `phemacast.core.party`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the core package defines the domain models
that describe pulses, phemas, and participating parties.

Core types exposed here include `Party`, which carry the main behavior or state managed
by this module.
"""

from typing import Any, Dict, List, Optional
from prompits.core.pit import Pit, PitAddress

class Party(Pit):
    """
    A Party represents a namespace grouping applications, pulses, phemas, and casts.
    It can be registered on a Plaza to allow agents to narrow their search to specific parties.
    """
    def __init__(
        self,
        name: str,
        description: str = "",
        address: Optional[PitAddress] = None,
        meta: Optional[Dict[str, Any]] = None,
        members: Optional[List[str]] = None
    ):
        """Initialize the party."""
        super().__init__(name=name, description=description, address=address, meta=meta)
        self.members = members or []
