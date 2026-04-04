"""
System orchestration helpers for `phemacast.system`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling.

Core types exposed here include `CastrAgent`, `CreatorAgent`, `PhemacastSystem`,
`PhemarAgent`, and `PulserAgent`, which carry the main behavior or state managed by this
module.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Optional, Tuple

from prompits.core.message import Message

from phemacast.models import Persona, Phema, PhemaBlock
from phemacast.practices.pulser import PulsePractice

_BINDING_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_\.]+)\s*\}\}")


def _resolve_path(data: Dict[str, Any], path: str) -> Any:
    """Resolve dotted field paths against nested dict payloads."""
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _render_template(template: str, bindings: Dict[str, Dict[str, Any]]) -> str:
    """Render `{{binding.path}}` expressions from pulser-provided scoped values."""
    def repl(match: re.Match) -> str:
        """Handle repl."""
        expression = match.group(1)
        root = expression.split(".", 1)[0]
        scoped = bindings.get(root, {})
        path = expression.split(".", 1)[1] if "." in expression else "value"
        value = _resolve_path(scoped, path)
        return "" if value is None else str(value)

    return _BINDING_PATTERN.sub(repl, template)


class CreatorAgent:
    """Pipeline role that creates `Phema` blueprints from prompt and binding intent."""
    name = "creator"

    def create_phema(
        self,
        title: str,
        prompt: str,
        bindings: List[str],
        default_persona: Optional[Persona] = None,
    ) -> Phema:
        """Create the phema."""
        persona = default_persona or Persona(name="default")
        blocks = [
            PhemaBlock(
                name=f"{binding}_block",
                template=f"[{binding}] {{{{{binding}.value}}}}",
                bindings=[binding],
            )
            for binding in bindings
        ]

        # Add a lead block anchored to creator prompt for context.
        blocks.insert(
            0,
            PhemaBlock(
                name="summary",
                template=f"{prompt}: {{{{summary.value}}}}",
                bindings=["summary"],
            ),
        )

        return Phema(
            phema_id=f"phema-{uuid.uuid4().hex[:8]}",
            title=title,
            prompt=prompt,
            blocks=blocks,
            default_persona=persona,
        )


class PulserAgent:
    """Pipeline role that collects pulse data from registered providers."""
    name = "pulser"

    def __init__(self, practice: Optional[PulsePractice] = None):
        """Initialize the pulser agent."""
        self.practice = practice or PulsePractice()

    def register_source(self, key: str, provider):
        """Register the source."""
        self.practice.register_provider(key, provider)

    def produce(self, keys: List[str], context: Optional[Dict[str, Any]] = None) -> Dict[str, Dict[str, Any]]:
        """Produce the value."""
        return self.practice.fetch(keys, context)


class PhemarAgent:
    """Pipeline role that binds pulse data into each `PhemaBlock` template."""
    name = "phemar"

    def bind(self, phema: Phema, pulse_data: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Bind the value."""
        bound_blocks: List[Dict[str, Any]] = []
        for block in phema.blocks:
            rendered = _render_template(block.template, pulse_data)
            bound_blocks.append({"name": block.name, "rendered": rendered})
        return bound_blocks


class CastrAgent:
    """Pipeline role that converts bound blocks into viewer-facing output formats."""
    name = "castr"

    def cast(
        self,
        phema: Phema,
        bound_blocks: List[Dict[str, Any]],
        output_format: str,
        persona: Persona,
        pulse_data: Dict[str, Dict[str, Any]],
    ) -> Any:
        """Cast the value."""
        fmt = output_format.lower().strip()

        if fmt == "json":
            return {
                "title": phema.title,
                "persona": persona.__dict__,
                "blocks": bound_blocks,
                "pulse": pulse_data,
            }

        if fmt == "text":
            body = "\n".join(block["rendered"] for block in bound_blocks)
            return f"{phema.title}\nPersona: {persona.name} ({persona.tone}/{persona.style})\n\n{body}"

        if fmt == "markdown":
            lines = [
                f"# {phema.title}",
                f"- Persona: **{persona.name}**",
                f"- Tone/Style: `{persona.tone}` / `{persona.style}`",
                "",
            ]
            lines.extend(f"- {block['rendered']}" for block in bound_blocks)
            return "\n".join(lines)

        raise ValueError(f"Unsupported output format: {output_format}")


class PhemacastSystem:
    """Collaborative multi-agent pipeline built on prompits primitives."""

    def __init__(self):
        """Initialize the Phemacast system."""
        self.creator = CreatorAgent()
        self.pulser = PulserAgent()
        self.phemar = PhemarAgent()
        self.castr = CastrAgent()

        self._phemas: Dict[str, Phema] = {}
        self.trace: List[Message] = []

    def create_phema(
        self,
        title: str,
        prompt: str,
        bindings: List[str],
        default_persona: Optional[Persona] = None,
    ) -> Phema:
        """Create the phema."""
        phema = self.creator.create_phema(title, prompt, bindings, default_persona)
        self._phemas[phema.phema_id] = phema
        self.trace.append(
            Message(
                sender=self.creator.name,
                receiver=self.phemar.name,
                msg_type="phema-created",
                content={"phema_id": phema.phema_id, "title": phema.title},
            )
        )
        return phema

    def register_pulse_source(self, key: str, provider) -> None:
        """Register the pulse source."""
        self.pulser.register_source(key, provider)

    def cast(
        self,
        phema_id: str,
        viewer_format: str,
        viewer_persona: Optional[Persona] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Any, List[Message]]:
        """
        Execute the full pipeline and return final output plus message trace.

        Flow: pulser -> phemar -> castr, with trace events recorded after each
        stage for observability and testability.
        """
        if phema_id not in self._phemas:
            raise KeyError(f"Unknown phema: {phema_id}")

        phema = self._phemas[phema_id]
        persona = viewer_persona or phema.default_persona

        keys = sorted({binding for block in phema.blocks for binding in block.bindings})
        pulse = self.pulser.produce(keys, context=context)
        self.trace.append(
            Message(
                sender=self.pulser.name,
                receiver=self.phemar.name,
                msg_type="pulse-produced",
                content={"keys": keys},
            )
        )

        bound = self.phemar.bind(phema, pulse)
        self.trace.append(
            Message(
                sender=self.phemar.name,
                receiver=self.castr.name,
                msg_type="phema-bound",
                content={"phema_id": phema_id, "blocks": len(bound)},
            )
        )

        output = self.castr.cast(phema, bound, viewer_format, persona, pulse)
        self.trace.append(
            Message(
                sender=self.castr.name,
                receiver="viewer",
                msg_type="cast-ready",
                content={"format": viewer_format, "phema_id": phema_id},
            )
        )

        return output, list(self.trace)
