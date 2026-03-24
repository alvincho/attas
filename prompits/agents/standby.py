import logging
import time
from typing import Dict, Any
from prompits.agents.base import BaseAgent
from prompits.core.message import Message

logger = logging.getLogger(__name__)

class StandbyAgent(BaseAgent):
    """
    Generic worker-style agent.

    This concrete agent consumes incoming `Message` envelopes and dispatches
    them to practices by `msg_type`, with optional simple command handling.
    """

    def __init__(self, name: str, host: str = "127.0.0.1", port: int = 8000, plaza_url: str = None, agent_card: Dict[str, Any] = None, pool: Any = None):
        super().__init__(name, host, port, plaza_url, agent_card, pool=pool)
        self.logger.info(f"Standing by for tasks at {self.host}:{self.port}...")

    def receive(self, message: Message):
        """Handle incoming messages."""
        self.logger.info(f"Message Received via A2A Protocol:")
        self.logger.info(f"    - Type: {message.msg_type}")
        self.logger.info(f"    - From: {message.sender}")
        self.logger.info(f"    - Content: {message.content}")
        
        # Logic for Demo Trigger
        if message.msg_type == "command":
            return self.handle_command(message.content)
            
        # Generic Practice Routing
        for practice in self.practices:
            if practice.id == message.msg_type:
                self.logger.info(f"Routing message to practice: {practice.name}")
                # For our simple framework, we'll try to execute the practice with content
                # Practices might need to be updated to handle this, but for now we'll 
                # check if there's a specific 'receive' handler or just use execute
                if hasattr(practice, "handle_message"):
                    return practice.handle_message(message)
                else:
                    # Fallback to execute if it's a dict
                    if isinstance(message.content, dict):
                        return practice.execute(**message.content)
                    return practice.execute(content=message.content)
        
        return None

    def handle_command(self, content: str):
        if "find" in content.lower() and "send" in content.lower():
            # Example: "find analyst and send 'hello'"
            parts = content.split(" ")
            target_role = "analyst" # simpler parsing for demo
            
            self.logger.info(f"Executing command: Search for '{target_role}'...")
            results = self.search(target_role)
            
            if results:
                target_agent = results[0]
                target_addr = target_agent['card']['address']
                target_name = target_agent['name']
                
                self.logger.info(f"Found {target_name} at {target_addr}. Sending task...")
                self.send(target_addr, "Can you analyze the sentiment for $BTC?")
            else:
                self.logger.warning(f"No agent found for role '{target_role}'.")

    def run(self):
        # BaseAgent uses uvicorn now
        pass
