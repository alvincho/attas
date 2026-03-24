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
        arbitrary_types_allowed = True

    def __repr__(self) -> str:
        return f"Message(type={self.msg_type}, from={self.sender}, to={self.receiver}, content={self.content})"
