"""
Regression tests for Personal Agent Web.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_personal_agent_plaza_run_proxy_returns_result`,
`test_personal_agent_doc_renderer_supports_relative_markdown_images`,
`test_personal_agent_root_renders_react_shell`, and
`test_personal_agent_user_guide_page_renders_html_doc`, helping guard against
regressions as the packages evolve.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.agents.map_phemar import MapPhemarAgent
from phemacast.personal_agent.app import app
from phemacast.personal_agent.doc_pages import render_markdown
from phemacast.personal_agent.map_phemar import get_map_phemar
from phemacast.personal_agent.plaza import BossProxyError, _normalize_catalog, normalize_plaza_url


client = TestClient(app)


def test_personal_agent_root_renders_react_shell():
    """Exercise the test_personal_agent_root_renders_react_shell regression scenario."""
    response = client.get("/")

    assert response.status_code == 200
    assert "Phemacast Personal Agent" in response.text
    assert 'id="root"' in response.text
    assert "personal_agent.css?v=" in response.text
    assert "personal_agent.jsx?v=" in response.text
    assert "react.development.js" in response.text
    assert "__PHEMACAST_PERSONAL_AGENT_BOOTSTRAP__" in response.text


def test_personal_agent_source_keeps_map_phemar_return_handling_localized():
    """
    Exercise the
    test_personal_agent_source_keeps_map_phemar_return_handling_localized regression
    scenario.
    """
    source = (Path(__file__).resolve().parents[1] / "personal_agent" / "static" / "personal_agent.jsx").read_text(encoding="utf-8")

    assert source.index("function preferredCompatiblePulser(") < source.index("function resolveMindMapNodeExecution(")
    assert "Reset All Local State" not in source
    assert "Reload App" in source


def test_personal_agent_user_guide_page_renders_html_doc():
    """
    Exercise the test_personal_agent_user_guide_page_renders_html_doc regression
    scenario.
    """
    response = client.get("/docs/personal-agent/user-guide")

    assert response.status_code == 200
    assert "Phemacast Personal Agent User Guide" in response.text
    assert "Open Personal Agent" in response.text
    assert "Common Workflows" in response.text
    assert "Main Workspace Shell" in response.text
    assert "Use The Full MapPhemar Editor" in response.text


def test_personal_agent_doc_renderer_supports_relative_markdown_images():
    """
    Exercise the test_personal_agent_doc_renderer_supports_relative_markdown_images
    regression scenario.
    """
    source_path = Path(__file__).resolve().parents[1] / "personal_agent" / "docs" / "user_guide.md"

    html = render_markdown(
        '![Storage Settings](./images/sample-guide-image.svg "Storage settings example")',
        source_path=source_path,
    )

    assert '<figure class="doc-image">' in html
    assert 'src="/docs-static/personal-agent/images/sample-guide-image.svg"' in html
    assert 'alt="Storage Settings"' in html
    assert "Storage settings example" in html


def test_personal_agent_doc_static_image_assets_are_served():
    """
    Exercise the test_personal_agent_doc_static_image_assets_are_served regression
    scenario.
    """
    response = client.get("/docs-static/personal-agent/images/sample-guide-image.svg")

    assert response.status_code == 200
    assert "<svg" in response.text


def test_personal_agent_dashboard_api_returns_expected_sections():
    """
    Exercise the test_personal_agent_dashboard_api_returns_expected_sections
    regression scenario.
    """
    response = client.get("/api/dashboard")

    assert response.status_code == 200
    payload = response.json()

    assert payload["meta"]["application"] == "Phemacast Personal Agent"
    assert payload["settings"]["billing_plan"] == "Phemacast Personal Pro Annual"
    assert len(payload["workspaces"]) >= 2
    assert len(payload["activity"]) >= 2
    assert len(payload["browser"]["bookmarks"]) >= 3


def test_personal_agent_channels_catalog_exposes_first_b2b_lanes():
    """
    Exercise the
    test_personal_agent_channels_catalog_exposes_first_b2b_lanes regression
    scenario.
    """
    response = client.get("/api/channels/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert [entry["kind"] for entry in payload["channels"]] == ["slack", "teams", "email"]


def test_personal_agent_managed_work_monitor_proxy_enriches_destinations():
    """
    Exercise the
    test_personal_agent_managed_work_monitor_proxy_enriches_destinations regression
    scenario.
    """
    with patch("phemacast.personal_agent.app.fetch_managed_work_monitor", new=AsyncMock(return_value={
        "status": "success",
        "manager_assignment": {"manager_address": "http://127.0.0.1:8170", "manager_name": "Desk Boss"},
        "summary": {"jobs": {"queued": 1, "completed": 1}},
        "workers": [{"worker_id": "worker-1", "status": "online"}],
        "tickets": [
            {
                "ticket": {"id": "ticket-1", "title": "Morning Desk Briefing"},
                "work_item": {
                    "required_capability": "publish briefing",
                    "metadata": {"publication": {"notion_markdown": "# Morning Desk Briefing"}},
                },
                "manager_assignment": {"manager_address": "http://127.0.0.1:8170"},
                "worker_assignment": {"worker_id": "worker-1", "status": "completed"},
                "execution_state": {"status": "completed"},
                "result_summary": {
                    "status": "completed",
                    "summary": {
                        "publication": {
                            "notion_title": "Morning Desk Briefing",
                            "channel_text": "Desk note: growth tone remains constructive.",
                        },
                        "notebooklm": {
                            "directory": "/tmp/notebooklm-pack",
                        },
                        "channel_deliveries": [
                            {"kind": "slack", "status": "delivered", "recipient": "#desk-briefings"},
                        ],
                    },
                },
            }
        ],
        "schedules": [],
    })):
        response = client.get(
            "/api/managed-work/monitor",
            params={"boss_url": "http://127.0.0.1:8170"},
        )

    assert response.status_code == 200
    payload = response.json()
    ticket = payload["tickets"][0]
    assert [entry["kind"] for entry in payload["channel_catalog"]] == ["slack", "teams", "email"]
    assert ticket["destination_status"]["notion"]["title"] == "Morning Desk Briefing"
    assert ticket["destination_status"]["notebooklm"]["status"] == "exported"
    assert ticket["destination_status"]["channels"][0]["status"] == "delivered"
    assert ticket["destination_status"]["channels"][0]["recipient"] == "#desk-briefings"


def test_personal_agent_managed_job_detail_falls_back_to_ticket_detail():
    """
    Exercise the
    test_personal_agent_managed_job_detail_falls_back_to_ticket_detail regression
    scenario.
    """
    with patch(
        "phemacast.personal_agent.app.fetch_boss_job_detail",
        new=AsyncMock(side_effect=BossProxyError("Job detail unavailable.", status_code=404)),
    ), patch(
        "phemacast.personal_agent.app.fetch_managed_work_ticket_detail",
        new=AsyncMock(return_value={
            "status": "success",
            "ticket": {
                "ticket": {"id": "ticket-1", "title": "Morning Desk Briefing"},
                "work_item": {"required_capability": "publish briefing", "metadata": {}},
                "manager_assignment": {"manager_address": "http://127.0.0.1:8170"},
                "worker_assignment": {"worker_id": "worker-1", "status": "completed"},
                "execution_state": {"status": "completed"},
                "result_summary": {"status": "completed", "summary": {"rows": 1}},
            },
            "raw_records": [{"status": "stored"}],
        }),
    ):
        response = client.get(
            "/api/jobs/ticket-1",
            params={"boss_url": "http://127.0.0.1:8170", "manager_address": "http://127.0.0.1:8170"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["detail_source"] == "managed_ticket_detail"
    assert payload["managed_ticket"]["ticket"]["id"] == "ticket-1"
    assert payload["raw_records"][0]["status"] == "stored"


def test_personal_agent_managed_schedule_control_proxies_issue_action():
    """
    Exercise the
    test_personal_agent_managed_schedule_control_proxies_issue_action regression
    scenario.
    """
    with patch(
        "phemacast.personal_agent.app.run_managed_work_schedule_control",
        new=AsyncMock(return_value={"status": "success", "control": {"action": "issue"}}),
    ):
        response = client.post(
            "/api/managed-work/schedules/schedule-1/control",
            params={"boss_url": "http://127.0.0.1:8170"},
            json={"action": "issue"},
        )

    assert response.status_code == 200
    assert response.json()["control"]["action"] == "issue"


def test_personal_agent_workspace_detail_returns_404_for_unknown_workspace():
    """
    Exercise the
    test_personal_agent_workspace_detail_returns_404_for_unknown_workspace
    regression scenario.
    """
    response = client.get("/api/workspaces/unknown")

    assert response.status_code == 404


def test_personal_agent_source_exposes_managed_work_pane_sections():
    """
    Exercise the
    test_personal_agent_source_exposes_managed_work_pane_sections regression
    scenario.
    """
    source = (Path(__file__).resolve().parents[1] / "personal_agent" / "static" / "personal_agent.jsx").read_text(encoding="utf-8")

    assert 'id: "managed_work"' in source
    assert "Managed Work" in source
    assert "operator-summary-strip" in source
    assert "renderOperatorConsole()" not in source


def test_personal_agent_source_exposes_plaza_access_settings():
    """
    Exercise the
    test_personal_agent_source_exposes_plaza_access_settings regression
    scenario.
    """
    source = (Path(__file__).resolve().parents[1] / "personal_agent" / "static" / "personal_agent.jsx").read_text(encoding="utf-8")

    assert 'id: "plaza_access"' in source
    assert "Plaza Access" in source
    assert "/api/plaza/auth/signin" in source
    assert "/api/plaza/agent-keys" in source


def test_personal_agent_normalize_plaza_url_strips_known_endpoint_suffixes():
    """
    Exercise the
    test_personal_agent_normalize_plaza_url_strips_known_endpoint_suffixes
    regression scenario.
    """
    assert normalize_plaza_url("127.0.0.1:8011") == "http://127.0.0.1:8011"
    assert normalize_plaza_url("http://127.0.0.1:8011/api/plazas_status") == "http://127.0.0.1:8011"
    assert normalize_plaza_url("http://127.0.0.1:8011/health") == "http://127.0.0.1:8011"


def test_personal_agent_plaza_catalog_proxy_returns_normalized_payload():
    """
    Exercise the test_personal_agent_plaza_catalog_proxy_returns_normalized_payload
    regression scenario.
    """
    with patch("phemacast.personal_agent.app.fetch_plaza_catalog", new=AsyncMock(return_value={
        "status": "success",
        "connected": True,
        "plaza_url": "http://127.0.0.1:8011",
        "pulsers": [{"agent_id": "pulser-1", "name": "RangePulser"}],
        "pulser_count": 1,
        "pulse_count": 4,
        "plazas": [{"name": "Plaza", "url": "http://127.0.0.1:8011", "online": True}],
    })):
        response = client.get("/api/plaza/catalog", params={"plaza_url": "http://127.0.0.1:8011"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["connected"] is True
    assert payload["pulser_count"] == 1


def test_personal_agent_plaza_auth_config_proxy_returns_payload():
    """
    Exercise the
    test_personal_agent_plaza_auth_config_proxy_returns_payload regression
    scenario.
    """
    with patch("phemacast.personal_agent.app.fetch_plaza_auth_config", new=AsyncMock(return_value={
        "status": "success",
        "auth_enabled": True,
        "oauth_providers": ["google", "github"],
    })):
        response = client.get("/api/plaza/auth/config", params={"plaza_url": "http://127.0.0.1:8011"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["auth_enabled"] is True
    assert payload["oauth_providers"] == ["google", "github"]


def test_personal_agent_plaza_auth_signup_proxy_returns_user():
    """
    Exercise the
    test_personal_agent_plaza_auth_signup_proxy_returns_user regression
    scenario.
    """
    with patch("phemacast.personal_agent.app.run_plaza_auth_signup", new=AsyncMock(return_value={
        "status": "success",
        "user": {"id": "user-1", "username": "desk-user"},
        "message": "Account created.",
    })):
        response = client.post(
            "/api/plaza/auth/signup",
            params={"plaza_url": "http://127.0.0.1:8011"},
            json={"username": "desk-user", "password": "pw", "display_name": "Desk User"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["id"] == "user-1"
    assert payload["message"] == "Account created."


def test_personal_agent_plaza_auth_me_proxy_forwards_authorization():
    """
    Exercise the
    test_personal_agent_plaza_auth_me_proxy_forwards_authorization regression
    scenario.
    """

    async def fake_fetch(plaza_url, authorization=""):
        assert plaza_url == "http://127.0.0.1:8011"
        assert authorization == "Bearer personal-agent-token"
        return {
            "status": "success",
            "user": {"id": "user-1", "username": "desk-user"},
        }

    with patch("phemacast.personal_agent.app.fetch_plaza_auth_me", new=AsyncMock(side_effect=fake_fetch)):
        response = client.get(
            "/api/plaza/auth/me",
            params={"plaza_url": "http://127.0.0.1:8011"},
            headers={"Authorization": "Bearer personal-agent-token"},
        )

    assert response.status_code == 200
    assert response.json()["user"]["username"] == "desk-user"


def test_personal_agent_plaza_agent_key_proxy_forwards_authorization_and_payload():
    """
    Exercise the
    test_personal_agent_plaza_agent_key_proxy_forwards_authorization_and_payload
    regression scenario.
    """

    async def fake_create(plaza_url, payload, authorization=""):
        assert plaza_url == "http://127.0.0.1:8011"
        assert payload == {"name": "Desk Launcher"}
        assert authorization == "Bearer personal-agent-token"
        return {
            "status": "success",
            "agent_key": {"id": "key-1", "name": "Desk Launcher", "secret": "plaza_secret"},
        }

    with patch("phemacast.personal_agent.app.create_plaza_agent_key", new=AsyncMock(side_effect=fake_create)):
        response = client.post(
            "/api/plaza/agent-keys",
            params={"plaza_url": "http://127.0.0.1:8011"},
            headers={"Authorization": "Bearer personal-agent-token"},
            json={"name": "Desk Launcher"},
        )

    assert response.status_code == 200
    assert response.json()["agent_key"]["id"] == "key-1"


def test_personal_agent_catalog_preserves_supported_pulse_sample_parameters():
    """
    Exercise the
    test_personal_agent_catalog_preserves_supported_pulse_sample_parameters
    regression scenario.
    """
    payload = _normalize_catalog(
        {
            "plazas": [
                {
                    "url": "http://127.0.0.1:8011",
                    "online": True,
                    "card": {"name": "Plaza"},
                    "agents": [
                        {
                            "agent_id": "pulser-1",
                            "name": "TechnicalAnalysisPulser",
                            "pit_type": "Pulser",
                            "card": {
                                "name": "TechnicalAnalysisPulser",
                                "pit_type": "Pulser",
                                "practices": [{"id": "get_pulse_data", "name": "Get Pulse Data"}],
                            },
                            "meta": {
                                "supported_pulses": [
                                    {
                                        "name": "sma",
                                        "pulse_name": "sma",
                                        "pulse_address": "ai.demo.finance.technical.sma",
                                        "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}},
                                        "pulse_definition": {"test_data": {"symbol": "AAPL", "window": 20}},
                                    }
                                ]
                            },
                        }
                    ],
                }
            ]
        },
        "http://127.0.0.1:8011",
    )

    supported_pulse = payload["pulsers"][0]["supported_pulses"][0]
    catalog_pulse = payload["pulses"][0]
    assert supported_pulse["pulse_name"] == "sma"
    assert supported_pulse["test_data"]["symbol"] == "AAPL"
    assert supported_pulse["test_data"]["window"] == 20
    assert catalog_pulse["pulse_name"] == "sma"
    assert catalog_pulse["test_data"]["window"] == 20


def test_personal_agent_catalog_reads_supported_pulses_from_card_meta_when_agent_meta_is_empty():
    """
    Exercise the
    test_personal_agent_catalog_reads_supported_pulses_from_card_meta_when_agent_meta_is_empty
    regression scenario.
    """
    payload = _normalize_catalog(
        {
            "plazas": [
                {
                    "url": "http://127.0.0.1:8011",
                    "online": True,
                    "card": {"name": "Plaza"},
                    "agents": [
                        {
                            "agent_id": "pulser-1",
                            "name": "SystemPulser",
                            "pit_type": "Pulser",
                            "card": {
                                "name": "SystemPulser",
                                "pit_type": "Pulser",
                                "practices": [{"id": "get_pulse_data", "name": "Get Pulse Data"}],
                                "meta": {
                                    "supported_pulses": [
                                        {"pulse_name": "object_save", "pulse_address": "plaza://pulse/object_save"},
                                        {"pulse_name": "object_load", "pulse_address": "plaza://pulse/object_load"},
                                    ]
                                },
                            },
                            "meta": {},
                        }
                    ],
                }
            ]
        },
        "http://127.0.0.1:8011",
    )

    assert payload["pulser_count"] == 1
    assert payload["pulsers"][0]["name"] == "SystemPulser"
    assert payload["pulsers"][0]["party"] == ""
    assert {pulse["pulse_name"] for pulse in payload["pulsers"][0]["supported_pulses"]} == {"object_load", "object_save"}
    assert {pulse["pulse_name"] for pulse in payload["pulses"]} == {"object_load", "object_save"}


def test_personal_agent_catalog_preserves_pulser_party_metadata():
    """
    Exercise the test_personal_agent_catalog_preserves_pulser_party_metadata
    regression scenario.
    """
    payload = _normalize_catalog(
        {
            "plazas": [
                {
                    "url": "http://127.0.0.1:8011",
                    "online": True,
                    "card": {"name": "Plaza"},
                    "agents": [
                        {
                            "agent_id": "pulser-1",
                            "name": "SystemPulser",
                            "pit_type": "Pulser",
                            "party": "System",
                            "card": {
                                "name": "SystemPulser",
                                "pit_type": "Pulser",
                                "party": "System",
                                "practices": [{"id": "get_pulse_data", "name": "Get Pulse Data"}],
                                "meta": {
                                    "party": "System",
                                    "supported_pulses": [
                                        {"pulse_name": "object_save", "pulse_address": "plaza://pulse/object_save"},
                                        {"pulse_name": "object_load", "pulse_address": "plaza://pulse/object_load"},
                                    ]
                                },
                            },
                            "meta": {"party": "System"},
                        }
                    ],
                }
            ]
        },
        "http://127.0.0.1:8011",
    )

    assert payload["pulsers"][0]["party"] == "System"


def test_personal_agent_catalog_consolidates_duplicate_pulse_names_into_one_shared_entry():
    """
    Exercise the test_personal_agent_catalog_consolidates_duplicate_pulse_names_into
    _one_shared_entry regression scenario.
    """
    payload = _normalize_catalog(
        {
            "plazas": [
                {
                    "url": "http://127.0.0.1:8011",
                    "online": True,
                    "card": {"name": "Plaza"},
                    "agents": [
                        {
                            "agent_id": "pulser-1",
                            "name": "FundamentalsPulser",
                            "pit_type": "Pulser",
                            "card": {
                                "name": "FundamentalsPulser",
                                "pit_type": "Pulser",
                                "practices": [{"id": "get_pulse_data", "name": "Get Pulse Data"}],
                            },
                            "meta": {
                                "supported_pulses": [
                                    {
                                        "pulse_name": "company_profile",
                                        "pulse_address": "ai.demo.finance.fundamentals.company_profile",
                                        "description": "Rich shared company profile description from Plaza.",
                                    }
                                ]
                            },
                        },
                        {
                            "agent_id": "pulser-2",
                            "name": "ScreeningPulser",
                            "pit_type": "Pulser",
                            "card": {
                                "name": "ScreeningPulser",
                                "pit_type": "Pulser",
                                "practices": [{"id": "get_pulse_data", "name": "Get Pulse Data"}],
                            },
                            "meta": {
                                "supported_pulses": [
                                    {
                                        "pulse_name": "company_profile",
                                        "pulse_address": "ai.demo.finance.screening.company_profile",
                                        "description": "Short description.",
                                    }
                                ]
                            },
                        },
                    ],
                }
            ]
        },
        "http://127.0.0.1:8011",
    )

    shared_company_profile = [pulse for pulse in payload["pulses"] if pulse["pulse_name"] == "company_profile"]
    assert len(shared_company_profile) == 1
    assert shared_company_profile[0]["description"] == "Rich shared company profile description from Plaza."


def test_personal_agent_plaza_run_proxy_returns_result():
    """
    Exercise the test_personal_agent_plaza_run_proxy_returns_result regression
    scenario.
    """
    with patch("phemacast.personal_agent.app.run_plaza_pulser_test", new=AsyncMock(return_value={
        "status": "success",
        "result": {"range": 52},
    })):
        response = client.post(
            "/api/plaza/panes/run",
            json={
                "plaza_url": "http://127.0.0.1:8011",
                "pulser_id": "pulser-1",
                "practice_id": "get_pulse_data",
                "pulse_name": "fifty_two_week_range",
                "input": {"symbol": "NVDA"},
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["result"]["range"] == 52


def test_personal_agent_local_file_save_route_writes_json(tmp_path):
    """
    Exercise the test_personal_agent_local_file_save_route_writes_json regression
    scenario.
    """
    response = client.post(
        "/api/files/save/local",
        json={
            "directory": str(tmp_path / "exports"),
            "title": "Range Snapshot",
            "content": {"range": 52},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    saved_file = payload["file"]
    target_path = Path(saved_file["path"])
    assert target_path.exists()
    assert target_path.parent == (tmp_path / "exports").resolve()
    assert target_path.suffix == ".json"
    assert json.loads(target_path.read_text(encoding="utf-8")) == {"range": 52}


def test_personal_agent_local_file_load_route_reads_json(tmp_path):
    """
    Exercise the test_personal_agent_local_file_load_route_reads_json regression
    scenario.
    """
    target_dir = tmp_path / "exports"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "workspace-layouts.json"
    target_path.write_text('{"snapshots":[{"id":"ws-1","name":"Crypto Overnight"}]}\n', encoding="utf-8")

    response = client.post(
        "/api/files/load/local",
        json={
            "directory": str(target_dir),
            "file_name": "workspace-layouts.json",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["file"]["file_name"] == "workspace-layouts.json"
    assert payload["file"]["content"]["snapshots"][0]["name"] == "Crypto Overnight"


def test_personal_agent_map_phemar_routes_persist_diagram_phema(tmp_path):
    """
    Exercise the test_personal_agent_map_phemar_routes_persist_diagram_phema
    regression scenario.
    """
    env = {
        "PHEMACAST_MAP_PHEMAR_CONFIG_PATH": str(tmp_path / "map_phemar.phemar"),
        "PHEMACAST_MAP_PHEMAR_POOL_PATH": str(tmp_path / "pool"),
    }
    with patch.dict(os.environ, env, clear=False):
        create_response = client.post(
            "/api/map-phemar/phemas",
            json={
                "phema": {
                    "name": "Daily OHLC Diagram",
                    "description": "Diagram-backed Phema managed by MapPhemar.",
                    "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}},
                    "output_schema": {"type": "object", "properties": {"bars": {"type": "array"}}},
                    "sections": [{"name": "Flow", "content": [{"type": "text", "text": "Diagram-backed"}]}],
                    "resolution_mode": "dynamic",
                    "meta": {
                        "map_phemar": {
                            "version": 1,
                            "diagram": {
                                "nodes": [
                                    {"id": "mind-boundary-input", "role": "input", "type": "pill", "title": "Input"},
                                    {"id": "node-1", "type": "rounded", "title": "Fetch OHLC", "pulseName": "ohlc_bar_series"},
                                    {"id": "mind-boundary-output", "role": "output", "type": "pill", "title": "Output"},
                                ],
                                "edges": [
                                    {"id": "edge-1", "from": "mind-boundary-input", "to": "node-1", "mappingText": "{}"},
                                    {"id": "edge-2", "from": "node-1", "to": "mind-boundary-output", "mappingText": "{}"},
                                ],
                            },
                        }
                    },
                }
            },
        )

        assert create_response.status_code == 200
        saved = create_response.json()["phema"]
        assert saved["phema_id"]
        assert saved["output_schema"]["properties"]["bars"]["type"] == "array"
        assert saved["meta"]["map_phemar"]["diagram"]["nodes"][1]["title"] == "Fetch OHLC"

        listing = client.get("/api/map-phemar/phemas")
        assert listing.status_code == 200
        phemas = listing.json()["phemas"]
        assert len(phemas) == 1
        assert phemas[0]["name"] == "Daily OHLC Diagram"
        assert phemas[0]["output_schema"]["properties"]["bars"]["type"] == "array"

        detail = client.get(f"/api/map-phemar/phemas/{saved['phema_id']}")
        assert detail.status_code == 200
        loaded = detail.json()["phema"]
        assert loaded["meta"]["map_phemar"]["diagram"]["edges"][1]["to"] == "mind-boundary-output"


def test_personal_agent_map_phemar_routes_respect_requested_storage_directory(tmp_path):
    """
    Exercise the
    test_personal_agent_map_phemar_routes_respect_requested_storage_directory
    regression scenario.
    """
    env = {
        "PHEMACAST_MAP_PHEMAR_CONFIG_PATH": str(tmp_path / "default-map_phemar.phemar"),
        "PHEMACAST_MAP_PHEMAR_POOL_PATH": str(tmp_path / "default-pool"),
    }
    custom_directory = tmp_path / "personal-agent-location"
    with patch.dict(os.environ, env, clear=False):
        create_response = client.post(
            "/api/map-phemar/phemas",
            params={"map_phemar_storage_directory": str(custom_directory)},
            json={
                "phema": {
                    "name": "Scoped Diagram",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "sections": [{"name": "Flow", "content": [{"type": "text", "text": "Scoped"}]}],
                    "meta": {"map_phemar": {"version": 1, "diagram": {"nodes": [], "edges": []}}},
                }
            },
        )

        assert create_response.status_code == 200

        scoped_listing = client.get(
            "/api/map-phemar/phemas",
            params={"map_phemar_storage_directory": str(custom_directory)},
        )
        assert scoped_listing.status_code == 200
        assert len(scoped_listing.json()["phemas"]) == 1

        default_listing = client.get("/api/map-phemar/phemas")
        assert default_listing.status_code == 200
        assert default_listing.json()["phemas"] == []


def test_personal_agent_embeds_map_phemar_owner_ui_under_shared_routes(tmp_path):
    """
    Exercise the test_personal_agent_embeds_map_phemar_owner_ui_under_shared_routes
    regression scenario.
    """
    env = {
        "PHEMACAST_MAP_PHEMAR_CONFIG_PATH": str(tmp_path / "map_phemar.phemar"),
        "PHEMACAST_MAP_PHEMAR_POOL_PATH": str(tmp_path / "pool"),
    }
    with patch.dict(os.environ, env, clear=False):
        create_response = client.post(
            "/api/phemas",
            json={
                "phema": {
                    "name": "Owner Diagram",
                    "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}},
                    "output_schema": {"type": "object", "properties": {"bars": {"type": "array"}}},
                    "sections": [{"name": "Flow", "content": [{"type": "text", "text": "Diagram-backed"}]}],
                    "meta": {"map_phemar": {"version": 1, "diagram": {"nodes": [], "edges": []}}},
                }
            },
        )

        assert create_response.status_code == 200
        saved = create_response.json()["phema"]

        owner_root = client.get("/map-phemar")
        assert owner_root.status_code == 200
        assert '"app_mode": "map_phemar"' in owner_root.text
        assert '"phema_api_prefix": "/api/map-phemar/phemas"' in owner_root.text
        assert '"map_phemar_settings_scope": "personal_agent"' in owner_root.text
        assert '"map_phemar_storage_settings_mode": "inherited"' in owner_root.text
        assert "Back to Personal Agent" in owner_root.text

        owner_root_inherited_plaza = client.get(
            "/map-phemar",
            params={"map_phemar_plaza_url": "http://127.0.0.1:9555"},
        )
        assert owner_root_inherited_plaza.status_code == 200
        assert '"plaza_url": "http://127.0.0.1:9555"' in owner_root_inherited_plaza.text

        owner_editor = client.get(f"/map-phemar/phemas/editor/{saved['phema_id']}")
        assert owner_editor.status_code == 200
        assert saved["phema_id"] in owner_editor.text
        assert '"phema_api_prefix": "/api/map-phemar/phemas"' in owner_editor.text


def test_personal_agent_embedded_map_phemar_uses_shared_map_phemar_agent(tmp_path):
    """
    Exercise the
    test_personal_agent_embedded_map_phemar_uses_shared_map_phemar_agent regression
    scenario.
    """
    env = {
        "PHEMACAST_MAP_PHEMAR_CONFIG_PATH": str(tmp_path / "map_phemar.phemar"),
        "PHEMACAST_MAP_PHEMAR_POOL_PATH": str(tmp_path / "pool"),
    }
    with patch.dict(os.environ, env, clear=False):
        service = get_map_phemar()

    assert isinstance(service, MapPhemarAgent)
