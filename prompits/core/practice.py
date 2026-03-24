"""Practice abstraction for executable/mountable agent capabilities."""

from abc import ABC, abstractmethod
from fastapi import FastAPI
from typing import Any, Callable, Optional, List, Dict, Union
from .pit import Pit

class Practice(Pit, ABC):
    """
    Base class for agent capabilities exposed as callable endpoints/functions.

    A practice is both:
    1. A capability descriptor (metadata used in discovery and cards).
    2. An executable unit (sync/async logic through `execute`).
    3. A mountable web surface (`mount`) for FastAPI routing.
    """

    def __init__(self, 
                 name: str, 
                 description: str = "",
                 id: str = "",
                 cost: Union[int, float] = 0,
                 tags: List[str] = None,
                 examples: List[Union[str, Dict]] = None,
                 inputModes: List[str] = None,
                 outputModes: List[str] = None,
                 parameters: Dict[str, Any] = None):
        self.name = name
        self.description = description
        self.id = id or name.lower().replace(" ", "-")
        self.cost = self._normalize_cost(cost)
        self.tags = tags or []
        self.examples = examples or []
        self.inputModes = inputModes or []
        self.outputModes = outputModes or []
        self.parameters = parameters or {}  # JSON Schema or simple dict for UI generation
        self.agent = None  # Reference to the agent this Practice is attached to

    @staticmethod
    def _normalize_cost(value: Any) -> Union[int, float]:
        """Coerce cost-like values into a non-negative number."""
        try:
            normalized = float(value)
        except (TypeError, ValueError):
            return 0
        if normalized < 0:
            return 0
        return int(normalized) if normalized.is_integer() else normalized

    @property
    def path(self) -> str:
        """HTTP route path derived from practice id (dash -> underscore)."""
        return f"/{self.id.replace('-', '_')}"

    def bind(self, agent):
        """Attach the practice to an agent so runtime logic can access agent state."""
        self.agent = agent

    @abstractmethod
    def mount(self, app: FastAPI):
        """Mount routes or event handlers to the agent's FastAPI app."""
        pass

    def execute(self, **kwargs) -> Any:
        """Optional executable interface for the Practice."""
        pass
