"""
Financial briefing pulser for `attas.pulsers.financial_briefing_pulser`.

Attas owns finance-specific workflow decomposition on top of the shared Phemacast
pulser runtime. This pulser publishes the finance briefing workflow as workflow-seed
and step-sized pulses so MapPhemar and Personal Agent can store, edit, and execute
the same graph.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from attas.pds import derive_pulse_id
from attas.utils.report_to_phema import convert_briefing_payload
from attas.workflows.briefings import (
    assemble_finance_briefing_payload,
    build_finance_catalysts,
    build_finance_citations,
    build_finance_conflicting_evidence,
    build_finance_facts,
    build_finance_open_questions,
    build_finance_risks,
    build_finance_source_bundle,
    build_finance_summary,
    build_finance_takeaways,
    generate_notebooklm_pack,
    prepare_finance_briefing_context,
)
from phemacast.agents.pulser import ConfigInput, Pulser, _read_config


_STRING_FIELD = {"type": "string"}
_BOOLEAN_FIELD = {"type": "boolean"}
_OBJECT_FIELD = {"type": "object"}
_ARRAY_FIELD = {"type": "array"}
_SUBJECT_FIELD = {
    "anyOf": [
        {"type": "string"},
        {"type": "object"},
    ]
}
_WORKFLOW_NAME_FIELD = {
    "type": "string",
    "enum": [
        "morning_desk_briefing",
        "watchlist_check",
        "research_roundup",
    ],
}


def _schema(properties: dict[str, dict[str, Any]], *, required: list[str] | None = None) -> dict[str, Any]:
    """Return a simple JSON schema object."""
    return {
        "type": "object",
        "properties": properties,
        "required": list(required or []),
    }


def _pulse_definition(
    *,
    name: str,
    description: str,
    input_schema: dict[str, Any],
    output_schema: dict[str, Any],
    tags: list[str],
    test_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a stable pulse definition for the financial briefing pulser."""
    return {
        "name": name,
        "pulse_name": name,
        "pulse_id": derive_pulse_id({"name": name, "party": "attas"}),
        "pulse_address": f"plaza://pulse/attas_finance_{name}",
        "description": description,
        "tags": ["finance briefings", "attas", "finance", "briefing", *tags],
        "party": "attas",
        "cost": 0,
        "input_schema": input_schema,
        "output_schema": output_schema,
        "test_data": dict(test_data or {}),
    }


def _workflow_input_schema() -> dict[str, Any]:
    """Return the shared workflow entry input schema."""
    return _schema(
        {
            "workflow_name": _WORKFLOW_NAME_FIELD,
            "subject": _SUBJECT_FIELD,
            "search_results": _OBJECT_FIELD,
            "fetched_documents": _ARRAY_FIELD,
            "watchlist": _ARRAY_FIELD,
            "analysis": _OBJECT_FIELD,
            "as_of": _STRING_FIELD,
            "title": _STRING_FIELD,
            "owner": _STRING_FIELD,
            "output_dir": _STRING_FIELD,
            "include_pdf": _BOOLEAN_FIELD,
        },
        required=["workflow_name", "subject"],
    )


def _context_output_schema() -> dict[str, Any]:
    """Return the normalized context output schema."""
    return _schema(
        {
            "workflow": _STRING_FIELD,
            "workflow_label": _STRING_FIELD,
            "subject": _OBJECT_FIELD,
            "watchlist": _ARRAY_FIELD,
            "analysis": _OBJECT_FIELD,
            "as_of": _STRING_FIELD,
            "title": _STRING_FIELD,
            "owner": _STRING_FIELD,
            "search_results": _OBJECT_FIELD,
            "fetched_documents": _ARRAY_FIELD,
            "output_dir": _STRING_FIELD,
            "include_pdf": _BOOLEAN_FIELD,
        },
        required=["workflow", "subject", "watchlist", "analysis", "as_of", "owner"],
    )


def _source_bundle_schema() -> dict[str, Any]:
    """Return the source-bundle output schema."""
    return _schema({"sources": _ARRAY_FIELD}, required=["sources"])


def _citation_bundle_schema() -> dict[str, Any]:
    """Return the citation-bundle output schema."""
    return _schema({"citations": _ARRAY_FIELD}, required=["citations"])


def _entry_list_schema(name: str) -> dict[str, Any]:
    """Return a list-output schema for normalized entry bundles."""
    return _schema({name: _ARRAY_FIELD}, required=[name])


def _summary_schema() -> dict[str, Any]:
    """Return the summary output schema."""
    return _schema({"summary": _OBJECT_FIELD}, required=["summary"])


def _briefing_payload_schema() -> dict[str, Any]:
    """Return the assembled briefing payload schema."""
    return _schema({"briefing_payload": _OBJECT_FIELD}, required=["briefing_payload"])


def _briefing_phema_schema() -> dict[str, Any]:
    """Return the report-Phema output schema."""
    return _schema({"briefing_phema": _OBJECT_FIELD}, required=["briefing_phema"])


def _notebooklm_pack_schema() -> dict[str, Any]:
    """Return the NotebookLM export output schema."""
    return _schema({"notebooklm_pack": _OBJECT_FIELD}, required=["notebooklm_pack"])


def _sample_sources() -> list[dict[str, Any]]:
    """Return sample normalized finance sources."""
    return [
        {
            "id": "doc-1",
            "title": "Nvidia expands sovereign AI pipeline with new Gulf cloud project",
            "url": "https://example.test/news/nvda-sovereign-ai-pipeline",
            "source_domain": "example.test",
            "snippet": "A new sovereign AI buildout points to another quarter of strong accelerator and networking demand.",
            "text": "Management said the new sovereign AI project should support another quarter of strong accelerator demand.",
            "published_at": "2026-04-02T07:10:00Z",
            "citation": {
                "id": "doc-1",
                "title": "Nvidia expands sovereign AI pipeline with new Gulf cloud project",
                "url": "https://example.test/news/nvda-sovereign-ai-pipeline",
                "source_domain": "example.test",
                "published_at": "2026-04-02T07:10:00Z",
            },
            "citation_id": "doc-1",
            "source_kinds": ["search", "document"],
            "classification": {
                "tone": "positive",
                "risk_flags": [],
                "catalyst_flags": ["product"],
            },
        },
        {
            "id": "doc-2",
            "title": "Export-control debate reopens questions on geographic mix durability",
            "url": "https://example.test/news/nvda-export-control-risk",
            "source_domain": "example.test",
            "snippet": "Policy commentary highlights a potential risk to regional mix and visibility.",
            "text": "Policy coverage said tighter export controls could become a meaningful risk to regional mix and visibility.",
            "published_at": "2026-04-01T23:45:00Z",
            "citation": {
                "id": "doc-2",
                "title": "Export-control debate reopens questions on geographic mix durability",
                "url": "https://example.test/news/nvda-export-control-risk",
                "source_domain": "example.test",
                "published_at": "2026-04-01T23:45:00Z",
            },
            "citation_id": "doc-2",
            "source_kinds": ["search", "document"],
            "classification": {
                "tone": "negative",
                "risk_flags": ["export control", "risk"],
                "catalyst_flags": ["policy"],
            },
        },
    ]


def _sample_workflow_input() -> dict[str, Any]:
    """Return sample workflow entry input for editor-side previews."""
    return {
        "subject": "NVDA",
        "search_results": {
            "query": "NVDA sovereign AI demand",
            "sources": [
                {
                    "id": "doc-1",
                    "title": "Nvidia expands sovereign AI pipeline with new Gulf cloud project",
                    "url": "https://example.test/news/nvda-sovereign-ai-pipeline",
                    "source_domain": "example.test",
                    "snippet": "A new sovereign AI buildout points to another quarter of strong accelerator and networking demand.",
                    "published_at": "2026-04-02T07:10:00Z",
                    "citation": {
                        "id": "doc-1",
                        "title": "Nvidia expands sovereign AI pipeline with new Gulf cloud project",
                        "url": "https://example.test/news/nvda-sovereign-ai-pipeline",
                        "source_domain": "example.test",
                        "published_at": "2026-04-02T07:10:00Z",
                    },
                },
                {
                    "id": "doc-2",
                    "title": "Export-control debate reopens questions on geographic mix durability",
                    "url": "https://example.test/news/nvda-export-control-risk",
                    "source_domain": "example.test",
                    "snippet": "Policy commentary highlights a potential risk to regional mix and visibility.",
                    "published_at": "2026-04-01T23:45:00Z",
                    "citation": {
                        "id": "doc-2",
                        "title": "Export-control debate reopens questions on geographic mix durability",
                        "url": "https://example.test/news/nvda-export-control-risk",
                        "source_domain": "example.test",
                        "published_at": "2026-04-01T23:45:00Z",
                    },
                },
            ],
        },
        "fetched_documents": [
            {
                "id": "doc-1",
                "title": "Nvidia expands sovereign AI pipeline with new Gulf cloud project",
                "url": "https://example.test/news/nvda-sovereign-ai-pipeline",
                "source_domain": "example.test",
                "text": "Management said the new sovereign AI project should support another quarter of strong accelerator demand.",
                "citation": {
                    "id": "doc-1",
                    "title": "Nvidia expands sovereign AI pipeline with new Gulf cloud project",
                    "url": "https://example.test/news/nvda-sovereign-ai-pipeline",
                    "source_domain": "example.test",
                    "published_at": "2026-04-02T07:10:00Z",
                },
            },
            {
                "id": "doc-2",
                "title": "Export-control debate reopens questions on geographic mix durability",
                "url": "https://example.test/news/nvda-export-control-risk",
                "source_domain": "example.test",
                "text": "Policy coverage said tighter export controls could become a meaningful risk to regional mix and visibility.",
                "citation": {
                    "id": "doc-2",
                    "title": "Export-control debate reopens questions on geographic mix durability",
                    "url": "https://example.test/news/nvda-export-control-risk",
                    "source_domain": "example.test",
                    "published_at": "2026-04-01T23:45:00Z",
                },
            },
        ],
        "watchlist": [
            {"symbol": "NVDA", "position": "core long", "thesis": "AI accelerator demand remains durable."},
            {"symbol": "AMD", "position": "tracking", "thesis": "Competitive response is worth monitoring."},
        ],
        "analysis": {},
        "as_of": "2026-04-04T08:00:00Z",
        "output_dir": "/tmp/notebooklm-pack",
        "include_pdf": False,
    }


def _default_supported_pulses() -> list[dict[str, Any]]:
    """Return the default supported pulses for the finance workflow pack."""
    workflow_input = _workflow_input_schema()
    context_output = _context_output_schema()
    sources = _sample_sources()
    briefing_payload = assemble_finance_briefing_payload(
        workflow="morning_desk_briefing",
        workflow_label="Morning Desk Briefing",
        subject={"label": "NVDA", "symbols": ["NVDA"]},
        watchlist=[{"symbol": "NVDA", "position": "core long", "thesis": "AI accelerator demand remains durable."}],
        as_of="2026-04-04T08:00:00Z",
        owner="attas.workflows.briefings",
        sources=sources,
        citations=[entry["citation"] for entry in sources],
        facts=[{"statement": "Demand signals remain constructive.", "citation_ids": ["doc-1"]}],
        risks=[{"statement": "Policy headlines remain active.", "severity": "medium", "citation_ids": ["doc-2"]}],
        catalysts=[{"statement": "A sovereign AI project expands the pipeline.", "direction": "positive", "timing": "reported", "citation_ids": ["doc-1"]}],
        inferred_takeaways=[{"statement": "The setup is mixed.", "basis": "Tone splits across positive demand and policy risk.", "citation_ids": ["doc-1", "doc-2"]}],
        conflicting_evidence=[{"bullish": "Demand remains strong.", "bearish": "Policy risk is active.", "why_it_matters": "Conviction depends on whether policy stays manageable.", "citation_ids": ["doc-1", "doc-2"]}],
        open_questions=[{"question": "Which catalyst will reset the tape?", "why_it_matters": "It affects sizing and publication timing.", "citation_ids": ["doc-1"]}],
        summary={
            "stance": "mixed",
            "headline": "NVDA morning desk briefing: mixed setup",
            "channel_text": "NVDA morning desk briefing: mixed setup. Takeaway: The setup is mixed.",
        },
    )["briefing_payload"]
    return [
        _pulse_definition(
            name="prepare_finance_briefing_context",
            description="Normalize workflow inputs for a finance briefing graph selected by workflow_name.",
            input_schema=workflow_input,
            output_schema=context_output,
            tags=["workflow", "context"],
            test_data={
                **_sample_workflow_input(),
                "workflow_name": "morning_desk_briefing",
            },
        ),
        _pulse_definition(
            name="build_finance_source_bundle",
            description="Merge normalized MCP search and fetch outputs into the finance source bundle.",
            input_schema=_schema({"search_results": _OBJECT_FIELD, "fetched_documents": _ARRAY_FIELD}),
            output_schema=_source_bundle_schema(),
            tags=["sources", "normalization"],
            test_data={"search_results": _sample_workflow_input()["search_results"], "fetched_documents": _sample_workflow_input()["fetched_documents"]},
        ),
        _pulse_definition(
            name="build_finance_citations",
            description="Deduplicate normalized citations from the finance source bundle.",
            input_schema=_schema({"sources": _ARRAY_FIELD}, required=["sources"]),
            output_schema=_citation_bundle_schema(),
            tags=["sources", "citations"],
            test_data={"sources": sources},
        ),
        _pulse_definition(
            name="build_finance_facts",
            description="Build finance-specific fact entries from sources and explicit analyst notes.",
            input_schema=_schema({"sources": _ARRAY_FIELD, "analysis": _OBJECT_FIELD}),
            output_schema=_entry_list_schema("facts"),
            tags=["facts"],
            test_data={"sources": sources, "analysis": {}},
        ),
        _pulse_definition(
            name="build_finance_risks",
            description="Build finance-specific risk entries from normalized sources and analyst notes.",
            input_schema=_schema({"sources": _ARRAY_FIELD, "analysis": _OBJECT_FIELD}),
            output_schema=_entry_list_schema("risks"),
            tags=["risks"],
            test_data={"sources": sources, "analysis": {}},
        ),
        _pulse_definition(
            name="build_finance_catalysts",
            description="Build finance-specific catalyst entries from normalized sources and analyst notes.",
            input_schema=_schema({"sources": _ARRAY_FIELD, "analysis": _OBJECT_FIELD}),
            output_schema=_entry_list_schema("catalysts"),
            tags=["catalysts"],
            test_data={"sources": sources, "analysis": {}},
        ),
        _pulse_definition(
            name="build_finance_conflicting_evidence",
            description="Build conflicting evidence entries for the current finance briefing setup.",
            input_schema=_schema({"sources": _ARRAY_FIELD, "analysis": _OBJECT_FIELD}),
            output_schema=_entry_list_schema("conflicting_evidence"),
            tags=["conflicts"],
            test_data={"sources": sources, "analysis": {}},
        ),
        _pulse_definition(
            name="build_finance_takeaways",
            description="Build inferred takeaways from sources, risks, catalysts, and workflow context.",
            input_schema=_schema(
                {
                    "workflow": _STRING_FIELD,
                    "subject": _OBJECT_FIELD,
                    "sources": _ARRAY_FIELD,
                    "risks": _ARRAY_FIELD,
                    "catalysts": _ARRAY_FIELD,
                    "analysis": _OBJECT_FIELD,
                },
                required=["workflow", "subject"],
            ),
            output_schema=_entry_list_schema("inferred_takeaways"),
            tags=["takeaways"],
            test_data={
                "workflow": "morning_desk_briefing",
                "subject": {"label": "NVDA", "symbols": ["NVDA"]},
                "sources": sources,
                "risks": [{"statement": "Policy risk remains active.", "severity": "medium", "citation_ids": ["doc-2"]}],
                "catalysts": [{"statement": "A sovereign AI project expands the pipeline.", "direction": "positive", "timing": "reported", "citation_ids": ["doc-1"]}],
                "analysis": {},
            },
        ),
        _pulse_definition(
            name="build_finance_open_questions",
            description="Build open questions from risks, catalysts, conflicting evidence, and subject context.",
            input_schema=_schema(
                {
                    "subject": _OBJECT_FIELD,
                    "risks": _ARRAY_FIELD,
                    "catalysts": _ARRAY_FIELD,
                    "conflicting_evidence": _ARRAY_FIELD,
                    "analysis": _OBJECT_FIELD,
                },
                required=["subject"],
            ),
            output_schema=_entry_list_schema("open_questions"),
            tags=["questions"],
            test_data={
                "subject": {"label": "NVDA", "symbols": ["NVDA"]},
                "risks": [{"statement": "Policy risk remains active.", "severity": "medium", "citation_ids": ["doc-2"]}],
                "catalysts": [{"statement": "A sovereign AI project expands the pipeline.", "direction": "positive", "timing": "reported", "citation_ids": ["doc-1"]}],
                "conflicting_evidence": [{"bullish": "Demand remains strong.", "bearish": "Policy risk is active.", "why_it_matters": "Conviction depends on policy staying manageable.", "citation_ids": ["doc-1", "doc-2"]}],
                "analysis": {},
            },
        ),
        _pulse_definition(
            name="build_finance_summary",
            description="Build the stance, headline, and channel text for the finance briefing.",
            input_schema=_schema(
                {
                    "workflow": _STRING_FIELD,
                    "subject": _OBJECT_FIELD,
                    "watchlist": _ARRAY_FIELD,
                    "sources": _ARRAY_FIELD,
                    "risks": _ARRAY_FIELD,
                    "catalysts": _ARRAY_FIELD,
                    "inferred_takeaways": _ARRAY_FIELD,
                },
                required=["workflow", "subject"],
            ),
            output_schema=_summary_schema(),
            tags=["summary"],
            test_data={
                "workflow": "morning_desk_briefing",
                "subject": {"label": "NVDA", "symbols": ["NVDA"]},
                "watchlist": [{"symbol": "NVDA"}],
                "sources": sources,
                "risks": [{"statement": "Policy risk remains active.", "severity": "medium", "citation_ids": ["doc-2"]}],
                "catalysts": [{"statement": "A sovereign AI project expands the pipeline.", "direction": "positive", "timing": "reported", "citation_ids": ["doc-1"]}],
                "inferred_takeaways": [{"statement": "The setup is mixed.", "basis": "Tone splits across demand and policy risk.", "citation_ids": ["doc-1", "doc-2"]}],
            },
        ),
        _pulse_definition(
            name="assemble_finance_briefing_payload",
            description="Assemble the stable attas.finance_briefing payload from workflow context and step outputs.",
            input_schema=_schema(
                {
                    "workflow": _STRING_FIELD,
                    "workflow_label": _STRING_FIELD,
                    "subject": _OBJECT_FIELD,
                    "watchlist": _ARRAY_FIELD,
                    "as_of": _STRING_FIELD,
                    "title": _STRING_FIELD,
                    "owner": _STRING_FIELD,
                    "sources": _ARRAY_FIELD,
                    "citations": _ARRAY_FIELD,
                    "facts": _ARRAY_FIELD,
                    "risks": _ARRAY_FIELD,
                    "catalysts": _ARRAY_FIELD,
                    "inferred_takeaways": _ARRAY_FIELD,
                    "conflicting_evidence": _ARRAY_FIELD,
                    "open_questions": _ARRAY_FIELD,
                    "summary": _OBJECT_FIELD,
                },
                required=["workflow", "workflow_label", "subject", "watchlist", "as_of", "owner", "summary"],
            ),
            output_schema=_briefing_payload_schema(),
            tags=["assembly", "payload"],
            test_data={
                "workflow": "morning_desk_briefing",
                "workflow_label": "Morning Desk Briefing",
                "subject": {"label": "NVDA", "symbols": ["NVDA"]},
                "watchlist": [{"symbol": "NVDA", "position": "core long", "thesis": "AI accelerator demand remains durable."}],
                "as_of": "2026-04-04T08:00:00Z",
                "owner": "attas.workflows.briefings",
                "sources": sources,
                "citations": [entry["citation"] for entry in sources],
                "facts": [{"statement": "Demand signals remain constructive.", "citation_ids": ["doc-1"]}],
                "risks": [{"statement": "Policy headlines remain active.", "severity": "medium", "citation_ids": ["doc-2"]}],
                "catalysts": [{"statement": "A sovereign AI project expands the pipeline.", "direction": "positive", "timing": "reported", "citation_ids": ["doc-1"]}],
                "inferred_takeaways": [{"statement": "The setup is mixed.", "basis": "Tone splits across demand and policy risk.", "citation_ids": ["doc-1", "doc-2"]}],
                "conflicting_evidence": [{"bullish": "Demand remains strong.", "bearish": "Policy risk is active.", "why_it_matters": "Conviction depends on policy staying manageable.", "citation_ids": ["doc-1", "doc-2"]}],
                "open_questions": [{"question": "Which catalyst will reset the tape?", "why_it_matters": "It affects sizing and publication timing.", "citation_ids": ["doc-1"]}],
                "summary": {
                    "stance": "mixed",
                    "headline": "NVDA morning desk briefing: mixed setup",
                    "channel_text": "NVDA morning desk briefing: mixed setup. Takeaway: The setup is mixed.",
                },
            },
        ),
        _pulse_definition(
            name="briefing_to_phema",
            description="Convert a finance briefing payload into a report-style static Phema.",
            input_schema=_schema({"briefing_payload": _OBJECT_FIELD}, required=["briefing_payload"]),
            output_schema=_briefing_phema_schema(),
            tags=["publication", "phema"],
            test_data={"briefing_payload": briefing_payload},
        ),
        _pulse_definition(
            name="notebooklm_export_pack",
            description="Generate the NotebookLM-ready export pack from the assembled finance briefing payload.",
            input_schema=_schema(
                {
                    "briefing_payload": _OBJECT_FIELD,
                    "output_dir": _STRING_FIELD,
                    "include_pdf": _BOOLEAN_FIELD,
                },
                required=["briefing_payload"],
            ),
            output_schema=_notebooklm_pack_schema(),
            tags=["publication", "notebooklm", "export"],
            test_data={"briefing_payload": briefing_payload, "output_dir": "/tmp/notebooklm-pack", "include_pdf": False},
        ),
    ]


def _coerce_bool(value: Any) -> bool:
    """Return a predictable boolean from common map-input values."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"", "0", "false", "no", "off"}:
            return False
        if normalized in {"1", "true", "yes", "on"}:
            return True
    return bool(value)


class FinancialBriefingPulser(Pulser):
    """Expose Attas finance briefing workflow steps as pulse-addressable building blocks."""

    def __init__(
        self,
        config: ConfigInput | None = None,
        *,
        config_path: ConfigInput | None = None,
        supported_pulses: list[dict[str, Any]] | None = None,
        auto_register: bool = True,
        **kwargs: Any,
    ):
        """Initialize the financial briefing pulser."""
        config_data = _read_config(config) if config is not None else {}
        resolved_config_path = config_path
        if resolved_config_path is None and isinstance(config, (str, Path)):
            resolved_config_path = config

        raw_config = dict(config_data or {})
        name = str(kwargs.pop("name", raw_config.get("name") or "FinancialBriefingPulser"))
        host = str(kwargs.pop("host", raw_config.get("host") or "127.0.0.1"))
        port = int(kwargs.pop("port", raw_config.get("port") or 8271))
        plaza_url = kwargs.pop("plaza_url", raw_config.get("plaza_url") or raw_config.get("plazaUrl"))
        incoming_agent_card = kwargs.pop("agent_card", None)
        agent_card = dict(raw_config.get("agent_card") or {})
        if isinstance(incoming_agent_card, Mapping):
            agent_card.update(dict(incoming_agent_card))
        agent_card.setdefault("name", name)
        agent_card.setdefault("role", "pulser")
        agent_card.setdefault("pit_type", "Pulser")
        agent_card.setdefault(
            "description",
            "Attas finance briefing step pulser for MapPhemar and Personal Agent workflow editing.",
        )

        super().__init__(
            config=raw_config,
            config_path=resolved_config_path,
            name=name,
            host=host,
            port=port,
            plaza_url=plaza_url,
            agent_card=agent_card,
            supported_pulses=supported_pulses or _default_supported_pulses(),
            auto_register=auto_register,
            **kwargs,
        )

    def fetch_pulse_payload(
        self,
        pulse_name: str,
        input_data: dict[str, Any],
        pulse_definition: dict[str, Any],
    ) -> dict[str, Any]:
        """Dispatch the requested finance workflow pulse."""
        del pulse_definition
        payload = dict(input_data or {})
        try:
            if pulse_name == "prepare_finance_briefing_context":
                return prepare_finance_briefing_context(**payload)
            if pulse_name == "build_finance_source_bundle":
                return build_finance_source_bundle(**payload)
            if pulse_name == "build_finance_citations":
                return build_finance_citations(**payload)
            if pulse_name == "build_finance_facts":
                return build_finance_facts(**payload)
            if pulse_name == "build_finance_risks":
                return build_finance_risks(**payload)
            if pulse_name == "build_finance_catalysts":
                return build_finance_catalysts(**payload)
            if pulse_name == "build_finance_conflicting_evidence":
                return build_finance_conflicting_evidence(**payload)
            if pulse_name == "build_finance_takeaways":
                return build_finance_takeaways(**payload)
            if pulse_name == "build_finance_open_questions":
                return build_finance_open_questions(**payload)
            if pulse_name == "build_finance_summary":
                return build_finance_summary(**payload)
            if pulse_name == "assemble_finance_briefing_payload":
                return assemble_finance_briefing_payload(**payload)
            if pulse_name == "briefing_to_phema":
                return {"briefing_phema": convert_briefing_payload(payload.get("briefing_payload") or {})}
            if pulse_name == "notebooklm_export_pack":
                return {
                    "notebooklm_pack": generate_notebooklm_pack(
                        payload.get("briefing_payload") or {},
                        output_dir=payload.get("output_dir") or None,
                        include_pdf=_coerce_bool(payload.get("include_pdf")),
                    )
                }
        except Exception as exc:
            return {
                "error": str(exc),
                "pulse_name": pulse_name,
            }

        return {
            "error": f"Unsupported pulse '{pulse_name}'.",
            "pulse_name": pulse_name,
        }


__all__ = [
    "FinancialBriefingPulser",
]
