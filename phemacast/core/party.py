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
        super().__init__(name=name, description=description, address=address, meta=meta)
        self.members = members or []
