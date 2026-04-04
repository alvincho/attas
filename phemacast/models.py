"""
Typed data models for `phemacast.models`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling.

Core types exposed here include `Persona`, `Phema`, `PhemaBlock`, and `Pulse`, which
carry the main behavior or state managed by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


@dataclass
class Persona:
    """Presentation voice profile used during final casting/output rendering."""
    name: str
    tone: str = "neutral"
    style: str = "concise"


@dataclass
class PhemaBlock:
    """One templated output unit with explicit pulse-data binding requirements."""
    name: str
    template: str
    bindings: List[str]


@dataclass
class Phema:
    """Structured narrative blueprint composed of prompt, blocks, and persona defaults."""
    phema_id: str
    title: str
    prompt: str
    blocks: List[PhemaBlock]
    default_persona: Persona
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Pulse:
    """Timestamped data snapshot fetched from a named pulse source/provider."""
    key: str
    payload: Dict[str, Any]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
