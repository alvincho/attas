"""
Pulser logic for `phemacast.practices.pulser`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the practices package connects domain
behavior to the underlying Prompits runtime.

Core types exposed here include `GetPulseDataPractice` and `PulsePractice`, which carry
the main behavior or state managed by this module.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, Optional

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from prompits.core.message import Message
from prompits.core.practice import Practice


class PulsePractice:
    """Simple provider registry used by `PhemacastSystem` for local pulse fetches."""

    def __init__(self):
        """Initialize the pulse practice."""
        self.providers: Dict[str, Callable[[Optional[Dict[str, Any]]], Any]] = {}

    def register_provider(self, key: str, provider: Callable[[Optional[Dict[str, Any]]], Any]) -> None:
        """Register the provider."""
        self.providers[key] = provider

    def fetch(self, keys: Iterable[str], context: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
        """Fetch the value."""
        payload: Dict[str, Dict[str, Any]] = {}
        for key in keys:
            provider = self.providers.get(key)
            if provider is None:
                payload[key] = {"value": None}
                continue

            result = provider(context or {})
            payload[key] = result if isinstance(result, dict) else {"value": result}
        return payload


class GetPulseDataPractice(Practice):
    """Expose `agent.get_pulse_data()` as a mounted callable practice."""

    def __init__(self):
        """Initialize the get pulse data practice."""
        super().__init__(
            name="Get Pulse Data",
            description="Fetch or transform pulse payloads for the agent's supported pulses.",
            id="get_pulse_data",
            tags=["pulser", "pulse", "data"],
            examples=["POST /get_pulse_data {'pulse_name': 'last_price', 'params': {'symbol': 'AAPL'}}"],
            inputModes=["http-post", "json"],
            outputModes=["json"],
            parameters={},
        )

    def bind(self, agent):
        """Bind the value."""
        super().bind(agent)
        supported_pulses = getattr(agent, "supported_pulses", [])
        self.parameters = {
            "pulse_name": {
                "type": "string",
                "description": "Optional pulse identifier. Defaults to the pulser's primary pulse.",
                "enum": [pulse.get("name") for pulse in supported_pulses if pulse.get("name")],
            },
            "pulse_address": {
                "type": "string",
                "description": "Optional pulse address override.",
            },
            "params": getattr(agent, "input_schema", {}) or {"type": "object"},
        }

    def mount(self, app):
        """Mount the value."""
        router = APIRouter()

        @router.post(self.path)
        async def get_pulse_data(message: Message):
            """Route handler for POST requests."""
            content = message.content or {}
            if not isinstance(content, dict):
                raise HTTPException(status_code=400, detail="Pulser content must be a JSON object.")
            return await run_in_threadpool(self.execute, **content)

        app.include_router(router)

    def execute(self, **kwargs) -> Any:
        """Handle execute for the get pulse data practice."""
        if not self.agent:
            raise RuntimeError("GetPulseDataPractice is not bound to an agent.")

        caller_context = kwargs.get("_caller")
        input_data = kwargs.get("input_data")
        if input_data is None:
            input_data = kwargs.get("params")
        if input_data is None:
            input_data = {
                key: value
                for key, value in kwargs.items()
                if key not in {"pulse_name", "pulse_address", "output_schema"}
            }

        if isinstance(input_data, dict) and isinstance(caller_context, dict):
            enriched_input = dict(input_data)
            enriched_input.setdefault("_caller", dict(caller_context))
            input_data = enriched_input

        return self.agent.get_pulse_data(
            input_data=input_data or {},
            pulse_name=kwargs.get("pulse_name"),
            pulse_address=kwargs.get("pulse_address"),
            output_schema=kwargs.get("output_schema"),
        )
