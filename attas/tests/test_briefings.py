"""
Regression tests for Finance Briefings.

Attas owns finance-specific workflow packaging on top of the shared runtimes. These
tests cover the shipped briefing payload contract, NotebookLM export pack, and the
finance-specific report bridge used for publication-ready outputs.
"""

import json
import os
import sys
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from attas.utils.report_to_phema import convert_briefing_payload
from attas.workflows.briefings import (
    BRIEFING_PAYLOAD_TYPE,
    BRIEFING_PAYLOAD_VERSION,
    NOTEBOOKLM_IMPORT_MODE,
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
    morning_desk_briefing,
    prepare_finance_briefing_context,
    research_roundup,
    watchlist_check,
)
from phemacast.pulsers.system_pulser import SystemPulser
from prompits.tests.test_support import build_agent_from_config


ROOT = Path(__file__).resolve().parents[2]


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


def test_finance_briefing_workflows_are_callable_and_share_stable_payload_shape():
    """
    Exercise the
    test_finance_briefing_workflows_are_callable_and_share_stable_payload_shape
    regression scenario.
    """
    search_results, fetched_documents, watchlist = _normalized_research_inputs()

    builders = [
        ("morning_desk_briefing", morning_desk_briefing, "NVDA"),
        ("watchlist_check", watchlist_check, "AI Leaders Watchlist"),
        ("research_roundup", research_roundup, "AI Infrastructure"),
    ]

    for workflow_name, builder, subject in builders:
        payload = builder(
            subject=subject,
            search_results=search_results,
            fetched_documents=fetched_documents,
            watchlist=watchlist,
            as_of="2026-04-04T08:00:00Z",
        )

        assert payload["payload_type"] == BRIEFING_PAYLOAD_TYPE
        assert payload["payload_version"] == BRIEFING_PAYLOAD_VERSION
        assert payload["workflow"] == workflow_name
        assert payload["summary"]["stance"] == "mixed"
        assert len(payload["facts"]) >= 2
        assert len(payload["inferred_takeaways"]) >= 2
        assert len(payload["risks"]) >= 1
        assert len(payload["catalysts"]) >= 1
        assert len(payload["conflicting_evidence"]) == 1
        assert len(payload["open_questions"]) >= 1
        assert len(payload["citations"]) == 2
        assert payload["publication"]["channel_text"]
        assert "## Facts" in payload["publication"]["notion_markdown"]
        assert payload["meta"]["notebooklm_import_mode"] == NOTEBOOKLM_IMPORT_MODE


def test_finance_briefing_step_functions_chain_into_the_stable_payload_contract():
    """
    Exercise the
    test_finance_briefing_step_functions_chain_into_the_stable_payload_contract
    regression scenario.
    """
    search_results, fetched_documents, watchlist = _normalized_research_inputs()
    context = prepare_finance_briefing_context(
        workflow_name="morning_desk_briefing",
        subject="NVDA",
        search_results=search_results,
        fetched_documents=fetched_documents,
        watchlist=watchlist,
        as_of="2026-04-04T08:00:00Z",
    )
    source_bundle = build_finance_source_bundle(
        search_results=context["search_results"],
        fetched_documents=context["fetched_documents"],
    )
    citation_bundle = build_finance_citations(sources=source_bundle["sources"])
    fact_bundle = build_finance_facts(sources=source_bundle["sources"], analysis=context["analysis"])
    risk_bundle = build_finance_risks(sources=source_bundle["sources"], analysis=context["analysis"])
    catalyst_bundle = build_finance_catalysts(sources=source_bundle["sources"], analysis=context["analysis"])
    conflict_bundle = build_finance_conflicting_evidence(sources=source_bundle["sources"], analysis=context["analysis"])
    takeaway_bundle = build_finance_takeaways(
        workflow=context["workflow"],
        subject=context["subject"],
        sources=source_bundle["sources"],
        risks=risk_bundle["risks"],
        catalysts=catalyst_bundle["catalysts"],
        analysis=context["analysis"],
    )
    question_bundle = build_finance_open_questions(
        subject=context["subject"],
        risks=risk_bundle["risks"],
        catalysts=catalyst_bundle["catalysts"],
        conflicting_evidence=conflict_bundle["conflicting_evidence"],
        analysis=context["analysis"],
    )
    summary_bundle = build_finance_summary(
        workflow=context["workflow"],
        subject=context["subject"],
        watchlist=context["watchlist"],
        sources=source_bundle["sources"],
        risks=risk_bundle["risks"],
        catalysts=catalyst_bundle["catalysts"],
        inferred_takeaways=takeaway_bundle["inferred_takeaways"],
    )
    assembled = assemble_finance_briefing_payload(
        workflow=context["workflow"],
        workflow_label=context["workflow_label"],
        subject=context["subject"],
        watchlist=context["watchlist"],
        as_of=context["as_of"],
        title=context["title"],
        owner=context["owner"],
        sources=source_bundle["sources"],
        citations=citation_bundle["citations"],
        facts=fact_bundle["facts"],
        risks=risk_bundle["risks"],
        catalysts=catalyst_bundle["catalysts"],
        inferred_takeaways=takeaway_bundle["inferred_takeaways"],
        conflicting_evidence=conflict_bundle["conflicting_evidence"],
        open_questions=question_bundle["open_questions"],
        summary=summary_bundle["summary"],
    )
    payload = assembled["briefing_payload"]

    assert payload["payload_type"] == BRIEFING_PAYLOAD_TYPE
    assert payload["workflow"] == "morning_desk_briefing"
    assert payload["summary"]["headline"]
    assert payload["publication"]["notion_markdown"].startswith("# Morning Desk Briefing")
    assert len(payload["citations"]) == 2
    assert len(payload["facts"]) >= 2
    assert len(payload["risks"]) >= 1
    assert len(payload["catalysts"]) >= 1
    assert len(payload["open_questions"]) >= 1


def test_notebooklm_pack_writes_markdown_url_bundle_and_optional_pdf(tmp_path):
    """
    Exercise the
    test_notebooklm_pack_writes_markdown_url_bundle_and_optional_pdf regression
    scenario.
    """
    search_results, fetched_documents, watchlist = _normalized_research_inputs()
    payload = morning_desk_briefing(
        subject="NVDA",
        search_results=search_results,
        fetched_documents=fetched_documents,
        watchlist=watchlist,
        as_of="2026-04-04T08:00:00Z",
    )

    pack = generate_notebooklm_pack(payload, output_dir=tmp_path, include_pdf=True)

    assert pack["status"] == "ready"
    assert pack["mode"] == NOTEBOOKLM_IMPORT_MODE
    assert Path(pack["directory"]).exists()
    assert json.loads(Path(pack["artifacts"]["json"]["path"]).read_text(encoding="utf-8"))["workflow"] == "morning_desk_briefing"
    assert Path(pack["artifacts"]["markdown"]["path"]).read_text(encoding="utf-8").startswith("# Morning Desk Briefing")
    assert Path(pack["artifacts"]["source_urls"]["path"]).read_text(encoding="utf-8").splitlines() == [
        "https://example.test/news/nvda-sovereign-ai-pipeline",
        "https://example.test/news/nvda-export-control-risk",
    ]
    pdf_artifact = pack["artifacts"]["pdf"]
    if pdf_artifact["status"] == "saved":
        assert Path(pdf_artifact["path"]).suffix == ".pdf"
        assert Path(pdf_artifact["path"]).exists()
    else:
        assert pdf_artifact["reason"] == "fpdf not installed" or pdf_artifact["reason"].startswith("pdf render failed:")


def test_convert_briefing_payload_returns_static_phema_sections():
    """
    Exercise the
    test_convert_briefing_payload_returns_static_phema_sections regression
    scenario.
    """
    search_results, fetched_documents, watchlist = _normalized_research_inputs()
    payload = research_roundup(
        subject="AI Infrastructure",
        search_results=search_results,
        fetched_documents=fetched_documents,
        watchlist=watchlist,
        as_of="2026-04-04T08:00:00Z",
    )

    phema_payload = convert_briefing_payload(payload)

    assert phema_payload["resolution_mode"] == "static"
    assert phema_payload["meta"]["source_format"] == "finance_briefing"
    assert phema_payload["meta"]["generated_by"] == "attas.utils.report_to_phema"
    assert [section["name"] for section in phema_payload["sections"]] == [
        "Summary",
        "Facts",
        "Takeaways",
        "Risks",
        "Catalysts",
        "Conflicting Evidence",
        "Open Questions",
        "Citations",
    ]


def test_notebooklm_export_config_loads_via_generic_system_pulser(tmp_path):
    """
    Exercise the
    test_notebooklm_export_config_loads_via_generic_system_pulser regression
    scenario.
    """
    source_config_path = ROOT / "attas" / "configs" / "notebooklm_export.pulser"
    config = json.loads(source_config_path.read_text(encoding="utf-8"))
    config["pools"][0]["root_path"] = str(tmp_path / "pool")
    config["storage"]["root_path"] = str(tmp_path / "content")
    runtime_config_path = tmp_path / "notebooklm_export.pulser"
    runtime_config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    agent = build_agent_from_config(str(runtime_config_path))

    assert isinstance(agent, SystemPulser)
    assert agent.name == "NotebookLMExportPulser"
    assert agent.storage_config["root_path"] == str(tmp_path / "content")
