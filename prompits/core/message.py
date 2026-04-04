"""
Message utilities for `prompits.core.message`.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. Within Prompits, the core package defines the
shared abstractions that the rest of the runtime builds on.

Core types exposed here include `Message`, which carry the main behavior or state
managed by this module.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Dict, Optional

class Message(BaseModel):
    """
    Canonical envelope for agent-to-agent and agent-to-practice communication.

    The framework routes messages primarily by `msg_type`, while `content`
    carries structured payloads understood by individual practices.
    """

    sender: str
    receiver: str
    content: Any
    msg_type: str = "message"
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        """Represent a config."""
        arbitrary_types_allowed = True

    def __repr__(self) -> str:
        """Return a debug-friendly representation of the instance."""
        return f"Message(type={self.msg_type}, from={self.sender}, to={self.receiver}, content={self.content})"
