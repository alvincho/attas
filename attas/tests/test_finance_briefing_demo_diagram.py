"""
Regression tests for the finance briefing workflow demo diagrams.

Attas owns the finance-specific workflow pack and can publish runnable demo artifacts
on top of shared Phemacast execution.
"""

import json
import os
import sys
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from attas.pulsers.financial_briefing_pulser import FinancialBriefingPulser
from phemacast.map_phemar.executor import execute_map_phema


ROOT = Path(__file__).resolve().parents[2]


class FakeResponse:
    """Response model for fake map execution payloads."""

    def __init__(self, payload, status_code=200):
        """Initialize the fake response."""
        self._payload = payload
        self.status_code = status_code

    def json(self):
        """Return the JSON payload."""
        return self._payload


def _load_json(path: Path) -> dict:
    """Load a JSON fixture."""
    return json.loads(path.read_text(encoding="utf-8"))


def _normalized_research_inputs():
    """Return sample normalized search/fetch inputs from the Thread 3 shape."""
    search_results = {
        "query": "NVDA sovereign AI demand",
        "number_of_sources": 2,
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
    }
    fetched_documents = [
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
    ]
    watchlist = [
        {"symbol": "NVDA", "position": "core long", "thesis": "AI accelerator demand remains durable."},
        {"symbol": "AMD", "position": "tracking", "thesis": "Competitive response is worth monitoring."},
    ]
    return search_results, fetched_documents, watchlist


def _runtime_demo_pulser() -> FinancialBriefingPulser:
    """Create the Attas-owned finance briefing pulser used by the diagrams."""
    return FinancialBriefingPulser(
        config=str(ROOT / "demos" / "pulsers" / "finance-briefings" / "finance-briefings.pulser"),
        auto_register=False,
    )


def test_finance_briefing_demo_pulser_exposes_step_pulses():
    """
    Exercise the
    test_finance_briefing_demo_pulser_exposes_step_pulses regression scenario.
    """
    pulser = _runtime_demo_pulser()

    assert pulser.name == "DemoFinancialBriefingPulser"
    assert {
        "prepare_finance_briefing_context",
        "build_finance_source_bundle",
        "build_finance_citations",
        "build_finance_facts",
        "build_finance_risks",
        "build_finance_catalysts",
        "build_finance_conflicting_evidence",
        "build_finance_takeaways",
        "build_finance_open_questions",
        "build_finance_summary",
        "assemble_finance_briefing_payload",
        "briefing_to_phema",
        "notebooklm_export_pack",
    }.issubset({pulse["name"] for pulse in pulser.supported_pulses})
    assert all("finance briefings" in (pulse.get("tags") or []) for pulse in pulser.supported_pulses)


def test_finance_briefing_demo_diagrams_execute_against_demo_workflow_pulser(tmp_path):
    """
    Exercise the
    test_finance_briefing_demo_diagrams_execute_against_demo_workflow_pulser
    regression scenario.
    """
    search_results, fetched_documents, watchlist = _normalized_research_inputs()
    pulser = _runtime_demo_pulser()
    cases = [
        (
            "finance-morning-desk-briefing-notebooklm-diagram.json",
            "Prepare Morning Context",
            "prepare_finance_briefing_context",
            "morning_desk_briefing",
        ),
        (
            "finance-watchlist-check-notebooklm-diagram.json",
            "Prepare Watchlist Context",
            "prepare_finance_briefing_context",
            "watchlist_check",
        ),
        (
            "finance-research-roundup-notebooklm-diagram.json",
            "Prepare Research Context",
            "prepare_finance_briefing_context",
            "research_roundup",
        ),
    ]

    expected_pulse_sequence = [
        "build_finance_source_bundle",
        "build_finance_citations",
        "build_finance_facts",
        "build_finance_risks",
        "build_finance_catalysts",
        "build_finance_conflicting_evidence",
        "build_finance_takeaways",
        "build_finance_open_questions",
        "build_finance_summary",
        "assemble_finance_briefing_payload",
        "briefing_to_phema",
        "notebooklm_export_pack",
    ]
    expected_step_suffix = [
        "Build Sources",
        "Build Citations",
        "Build Facts",
        "Build Risks",
        "Build Catalysts",
        "Build Conflicts",
        "Build Takeaways",
        "Build Open Questions",
        "Build Summary",
        "Assemble Briefing",
        "Report Phema",
        "NotebookLM Pack",
        "Output",
    ]

    for filename, prepare_title, prepare_pulse_name, workflow_name in cases:
        phema = _load_json(ROOT / "demos" / "files" / "diagrams" / filename)
        calls = []

        def fake_map_post(url, json=None, timeout=None):
            """Handle fake map post."""
            assert url == "http://127.0.0.1:8266/api/pulsers/test"
            assert isinstance(json, dict)
            assert json["pulser_name"] == "DemoFinancialBriefingPulser"
            calls.append(json["pulse_name"])
            return FakeResponse(
                {
                    "status": "success",
                    "result": pulser.get_pulse_data(dict(json["input"]), pulse_name=json["pulse_name"]),
                }
            )

        result = execute_map_phema(
            phema,
            input_data={
                "subject": "NVDA",
                "search_results": search_results,
                "fetched_documents": fetched_documents,
                "watchlist": watchlist,
                "as_of": "2026-04-04T08:00:00Z",
                "output_dir": str(tmp_path / f"{workflow_name}-notebooklm"),
                "include_pdf": False,
            },
            request_post=fake_map_post,
        )

        assert calls == [prepare_pulse_name, *expected_pulse_sequence]
        assert result["status"] == "success"
        assert [step["title"] for step in result["steps"]] == [
            "Input",
            prepare_title,
            *expected_step_suffix,
        ]
        assert result["output"]["briefing_payload"]["payload_type"] == "attas.finance_briefing"
        assert result["output"]["briefing_payload"]["workflow"] == workflow_name
        assert result["output"]["briefing_phema"]["resolution_mode"] == "static"
        assert result["output"]["notebooklm_pack"]["status"] == "ready"
        assert Path(result["output"]["notebooklm_pack"]["directory"]).exists()
        assert Path(result["output"]["notebooklm_pack"]["artifacts"]["markdown"]["path"]).exists()
