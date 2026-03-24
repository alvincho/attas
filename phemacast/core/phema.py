from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from prompits.core.pit import Pit, PitAddress


@dataclass
class PhemaSection:
    """Composable section used to structure a `Phema` blueprint."""

    name: str
    description: str = ""
    modifier: str = ""
    content: List[Any] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any] | "PhemaSection") -> "PhemaSection":
        if isinstance(payload, cls):
            return payload
        if not isinstance(payload, dict):
            raise ValueError("Phema sections must be objects.")
        content = payload.get("content") or []
        if not isinstance(content, list):
            raise ValueError("Phema section content must be a list.")
        return cls(
            name=str(payload.get("name") or "").strip(),
            description=str(payload.get("description") or ""),
            modifier=str(payload.get("modifier") or ""),
            content=list(content),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "modifier": self.modifier,
            "content": list(self.content),
        }


class Phema(Pit):
    """Plaza-registrable blueprint describing a structured content narrative."""

    PIT_TYPE = "Phema"

    def __init__(
        self,
        name: str,
        description: str = "",
        sections: Optional[List[Dict[str, Any] | PhemaSection]] = None,
        input_schema: Optional[Dict[str, Any]] = None,
        owner: str = "",
        phema_id: Optional[str] = None,
        address: Optional[str] = None,
        tags: Optional[List[str]] = None,
        meta: Optional[Dict[str, Any]] = None,
        resolution_mode: Optional[str] = None,
        snapshot_cache_time: Optional[Any] = None,
    ):
        pit_address = PitAddress()
        if phema_id:
            pit_address.pit_id = str(phema_id)
        normalized_meta = dict(meta or {})
        normalized_sections = [PhemaSection.from_dict(section) for section in (sections or [])]
        resolved_mode = self.infer_resolution_mode(
            sections=[section.to_dict() for section in normalized_sections],
            meta=normalized_meta,
            explicit_mode=resolution_mode,
        )
        resolved_snapshot_cache_time = self._normalize_snapshot_cache_time(
            snapshot_cache_time,
            normalized_meta.get("snapshot_cache_time"),
            normalized_meta.get("snapshot_cache_seconds"),
            normalized_meta.get("cache_time"),
        )
        normalized_meta["resolution_mode"] = resolved_mode
        if resolved_snapshot_cache_time > 0:
            normalized_meta["snapshot_cache_time"] = resolved_snapshot_cache_time
        else:
            normalized_meta.pop("snapshot_cache_time", None)
        super().__init__(name=name, description=description, address=pit_address, meta=normalized_meta)
        self.owner = owner or ""
        self.tags = [str(tag) for tag in (tags or []) if str(tag).strip()]
        self.sections = normalized_sections
        self.input_schema = dict(input_schema or {})
        self.directory_address = str(address or "").strip()
        self.resolution_mode = resolved_mode
        self.snapshot_cache_time = resolved_snapshot_cache_time

    @property
    def phema_id(self) -> str:
        return str(self.address.pit_id)

    @property
    def resolved_address(self) -> str:
        return self.directory_address or f"plaza://phema/{self.phema_id}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.phema_id,
            "phema_id": self.phema_id,
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "address": self.resolved_address,
            "pit_type": self.PIT_TYPE,
            "pit_address": self.address.to_dict(),
            "tags": list(self.tags),
            "input_schema": dict(self.input_schema),
            "sections": [section.to_dict() for section in self.sections],
            "resolution_mode": self.resolution_mode,
            "snapshot_cache_time": self.snapshot_cache_time,
            "meta": dict(self.meta),
        }

    def to_card(
        self,
        plaza_url: str = "",
        *,
        include_details: bool = True,
        extra_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if plaza_url:
            self.address.register_plaza(plaza_url)
        card_meta = {
            **dict(self.meta),
            "tags": list(self.tags),
        }
        if include_details:
            card_meta["input_schema"] = dict(self.input_schema)
            card_meta["sections"] = [section.to_dict() for section in self.sections]
        if extra_meta:
            card_meta.update(dict(extra_meta))
        return {
            "name": self.name,
            "description": self.description,
            "owner": self.owner,
            "address": self.resolved_address,
            "pit_type": self.PIT_TYPE,
            "agent_id": self.phema_id,
            "resolution_mode": self.resolution_mode,
            "snapshot_cache_time": self.snapshot_cache_time,
            "tags": list(self.tags),
            "pit_address": self.address.to_dict(),
            "meta": card_meta,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Phema":
        if not isinstance(payload, dict):
            raise ValueError("Phema payload must be an object.")

        raw_meta = payload.get("meta") or {}
        if not isinstance(raw_meta, dict):
            raise ValueError("Phema meta must be an object.")

        sections = payload.get("sections")
        if sections is None:
            sections = raw_meta.get("sections") or []
        if not isinstance(sections, list):
            raise ValueError("Phema sections must be a list.")

        tags = payload.get("tags")
        if tags is None:
            tags = raw_meta.get("tags") or []
        if not isinstance(tags, list):
            raise ValueError("Phema tags must be a list.")

        input_schema = payload.get("input_schema")
        if input_schema is None:
            input_schema = raw_meta.get("input_schema") or {}
        if not isinstance(input_schema, dict):
            raise ValueError("Phema input_schema must be an object.")

        meta = dict(raw_meta)
        meta.pop("sections", None)
        meta.pop("tags", None)
        meta.pop("input_schema", None)

        pit_address = PitAddress.from_value(payload.get("pit_address"))
        phema_id = (
            payload.get("phema_id")
            or payload.get("id")
            or payload.get("agent_id")
            or pit_address.pit_id
        )

        phema = cls(
            name=str(payload.get("name") or "").strip(),
            description=str(payload.get("description") or ""),
            sections=sections,
            input_schema=input_schema,
            owner=str(payload.get("owner") or ""),
            phema_id=str(phema_id or ""),
            address=str(payload.get("address") or ""),
            tags=[str(tag) for tag in tags if str(tag).strip()],
            meta=meta,
            resolution_mode=str(payload.get("resolution_mode") or raw_meta.get("resolution_mode") or ""),
            snapshot_cache_time=payload.get("snapshot_cache_time"),
        )
        phema.address = pit_address
        if phema_id:
            phema.address.pit_id = str(phema_id)
        return phema

    @staticmethod
    def _normalize_snapshot_cache_time(*values: Any) -> int:
        for value in values:
            if value is None or value == "":
                continue
            try:
                normalized = int(float(value))
            except (TypeError, ValueError):
                continue
            return max(normalized, 0)
        return 0

    @staticmethod
    def _content_item_has_unbound_pulse(item: Any) -> bool:
        if not isinstance(item, dict):
            return False
        if item.get("static") is True:
            return False
        item_type = str(item.get("type") or "").strip().lower()
        return item_type in {"pulse", "pulse-field"} or bool(item.get("pulse_name")) or bool(item.get("pulse_address"))

    @classmethod
    def infer_resolution_mode(
        cls,
        *,
        sections: Optional[List[Dict[str, Any]]] = None,
        meta: Optional[Dict[str, Any]] = None,
        explicit_mode: Optional[str] = None,
    ) -> str:
        normalized_explicit = str(explicit_mode or "").strip().lower()
        if normalized_explicit in {"static", "dynamic"}:
            return normalized_explicit
        normalized_meta = dict(meta or {})
        if normalized_meta.get("static_snapshot") is True:
            return "static"
        normalized_meta_mode = str(normalized_meta.get("resolution_mode") or "").strip().lower()
        if normalized_meta_mode in {"static", "dynamic"}:
            return normalized_meta_mode

        for section in sections or []:
            if not isinstance(section, dict):
                continue
            content = section.get("content") if isinstance(section.get("content"), list) else []
            if any(cls._content_item_has_unbound_pulse(item) for item in content):
                return "dynamic"
        return "static"
