"""Base abstraction for every conceptual unit in Prompits."""

from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Dict, List
import requests
import uuid


@dataclass
class PitAddress:
    """Stable address identity for any Pit."""

    pit_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plazas: List[str] = field(default_factory=list)

    def register_plaza(self, plaza_url: str):
        if not plaza_url:
            return
        normalized = plaza_url.rstrip("/")
        if normalized not in self.plazas:
            self.plazas.append(normalized)

    def to_ref(self, reference_plaza: str | None = None) -> str:
        normalized_reference = str(reference_plaza).rstrip("/") if reference_plaza else ""
        plazas = [str(item).rstrip("/") for item in self.plazas if item]
        if normalized_reference and normalized_reference in plazas:
            return str(self.pit_id)
        if plazas:
            return f"{self.pit_id}@{plazas[0]}"
        return str(self.pit_id)

    def matches(self, other: Any) -> bool:
        candidate = self.from_value(other)
        if self.pit_id and candidate.pit_id:
            return str(self.pit_id) == str(candidate.pit_id)
        return self.to_ref() == candidate.to_ref()

    def to_dict(self) -> Dict[str, Any]:
        return {"pit_id": self.pit_id, "plazas": list(self.plazas)}

    @classmethod
    def from_value(cls, value: Any) -> "PitAddress":
        if isinstance(value, PitAddress):
            return value
        if isinstance(value, dict):
            pit_id = str(value.get("pit_id") or value.get("agent_id") or uuid.uuid4())
            plazas = [str(p).rstrip("/") for p in (value.get("plazas") or []) if p]
            return cls(pit_id=pit_id, plazas=plazas)
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return cls(pit_id="", plazas=[])
            if raw.startswith("{") and raw.endswith("}"):
                try:
                    import json

                    return cls.from_value(json.loads(raw))
                except Exception:
                    return cls(pit_id="", plazas=[])
            if "@" in raw:
                pit_id, plaza = raw.split("@", 1)
                try:
                    uuid.UUID(str(pit_id))
                    plazas = [plaza.rstrip("/")] if plaza else []
                    return cls(pit_id=str(pit_id), plazas=plazas)
                except ValueError:
                    return cls(pit_id="", plazas=[])
            try:
                uuid.UUID(raw)
                return cls(pit_id=raw)
            except ValueError:
                return cls(pit_id="", plazas=[])
        return cls(pit_id="", plazas=[])


class Pit(ABC):
    """
    Root metadata carrier for framework components.

    A `Pit` defines shared identity metadata: `name`, `description`,
    an address (`PitAddress`), and optional `meta`.
    """

    def __init__(self, name: str, description: str, address: PitAddress | None = None, meta: Dict[str, Any] | None = None):
        self.name = name
        self.description = description
        self.address = address or PitAddress()
        self.meta = meta or {}

    def build_register_payload(
        self,
        plaza_url: str,
        card: Dict[str, Any] | None = None,
        address: str | None = None,
        expires_in: int = 3600,
        pit_type: str | None = None,
        pit_id: str | None = None,
        api_key: str | None = None,
        accepts_inbound_from_plaza: bool | None = None,
    ) -> Dict[str, Any]:
        if not plaza_url:
            raise ValueError("plaza_url is required")

        normalized_plaza = plaza_url.rstrip("/")
        self.address.register_plaza(normalized_plaza)
        if pit_id:
            self.address.pit_id = str(pit_id)

        payload_card = dict(card or {})
        payload_card.setdefault("name", self.name)
        payload_card["pit_address"] = self.address.to_dict()
        payload_meta = payload_card.get("meta")
        if not isinstance(payload_meta, dict):
            payload_meta = {}
        payload_card["meta"] = payload_meta
        if accepts_inbound_from_plaza is not None:
            normalized_accepts = bool(accepts_inbound_from_plaza)
            payload_card["accepts_inbound_from_plaza"] = normalized_accepts
            payload_card["accepts_direct_call"] = normalized_accepts
            payload_meta["accepts_inbound_from_plaza"] = normalized_accepts
            payload_meta["accepts_direct_call"] = normalized_accepts
            payload_card.setdefault(
                "connectivity_mode",
                "plaza-forward" if normalized_accepts else "outbound-only",
            )
            payload_meta.setdefault(
                "connectivity_mode",
                payload_card["connectivity_mode"],
            )

        payload: Dict[str, Any] = {
            "agent_name": self.name,
            "address": address or payload_card.get("address", ""),
            "expires_in": int(expires_in),
            "card": payload_card,
        }
        if accepts_inbound_from_plaza is not None:
            payload["accepts_inbound_from_plaza"] = bool(accepts_inbound_from_plaza)
            payload["accepts_direct_call"] = bool(accepts_inbound_from_plaza)
        if pit_type:
            payload["pit_type"] = pit_type
        if pit_id and api_key:
            payload["agent_id"] = str(pit_id)
            payload["api_key"] = str(api_key)
        return payload

    def register(
        self,
        plaza_url: str,
        card: Dict[str, Any] | None = None,
        address: str | None = None,
        expires_in: int = 3600,
        pit_type: str | None = None,
        pit_id: str | None = None,
        api_key: str | None = None,
        accepts_inbound_from_plaza: bool | None = None,
        timeout: int = 5,
    ) -> requests.Response:
        payload = self.build_register_payload(
            plaza_url=plaza_url,
            card=card,
            address=address,
            expires_in=expires_in,
            pit_type=pit_type,
            pit_id=pit_id,
            api_key=api_key,
            accepts_inbound_from_plaza=accepts_inbound_from_plaza,
        )
        return requests.post(f"{plaza_url.rstrip('/')}/register", json=payload, timeout=timeout)
