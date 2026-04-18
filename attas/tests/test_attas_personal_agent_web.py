"""
Regression tests for Personal Agent Web.

Attas layers finance-oriented pulse definitions, validation rules, and personal-agent
workflows on top of the shared runtimes. These tests cover Attas-specific pulse
definitions, validation flows, and personal-agent integration points.

The pytest cases in this file document expected behavior through checks such as
`test_personal_agent_plaza_run_proxy_returns_result`,
`test_personal_agent_root_renders_dashboard_shell`,
`test_personal_agent_local_file_save_and_load_roundtrip`, and
`test_personal_agent_plaza_catalog_proxy_returns_normalized_payload`, helping guard
against regressions as the packages evolve.
"""

import os
import sys
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.personal_agent.app import app
from phemacast.personal_agent.plaza import _normalize_catalog, normalize_plaza_url


client = TestClient(app)


def test_personal_agent_root_renders_dashboard_shell():
    """
    Exercise the test_personal_agent_root_renders_dashboard_shell regression
    scenario.
    """
    response = client.get("/")

    assert response.status_code == 200
    assert "Phemacast Personal Agent" in response.text
    assert '<div id="root"></div>' in response.text
    assert "personal_agent.css?v=" in response.text
    assert "personal_agent.jsx?v=" in response.text


def test_personal_agent_dashboard_api_returns_expected_sections():
    """
    Exercise the test_personal_agent_dashboard_api_returns_expected_sections
    regression scenario.
    """
    response = client.get("/api/dashboard")

    assert response.status_code == 200
    payload = response.json()

    assert payload["meta"]["application"] == "Phemacast Personal Agent"
    assert len(payload["workspaces"]) >= 2
    assert len(payload["browser"]["bookmarks"]) >= 3


def test_personal_agent_workspace_detail_returns_404_for_unknown_workspace():
    """
    Exercise the
    test_personal_agent_workspace_detail_returns_404_for_unknown_workspace
    regression scenario.
    """
    response = client.get("/api/workspaces/unknown")

    assert response.status_code == 404


def test_personal_agent_normalize_plaza_url_strips_known_endpoint_suffixes():
    """
    Exercise the
    test_personal_agent_normalize_plaza_url_strips_known_endpoint_suffixes
    regression scenario.
    """
    assert normalize_plaza_url("127.0.0.1:8011") == "http://127.0.0.1:8011"
    assert normalize_plaza_url("http://127.0.0.1:8011/api/plazas_status") == "http://127.0.0.1:8011"
    assert normalize_plaza_url("http://127.0.0.1:8011/health") == "http://127.0.0.1:8011"
    assert normalize_plaza_url("http://127.0.0.1:8011/search?pit_type=Pulser") == "http://127.0.0.1:8011"


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
    assert payload["pulsers"][0]["name"] == "RangePulser"


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
                                        "pulse_address": "ai.attas.finance.technical.sma",
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
    assert supported_pulse["pulse_name"] == "sma"
    assert supported_pulse["test_data"]["symbol"] == "AAPL"
    assert supported_pulse["test_data"]["window"] == 20


def test_personal_agent_catalog_dedupes_duplicate_pulser_names():
    """
    Exercise the test_personal_agent_catalog_dedupes_duplicate_pulser_names
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
                            "agent_id": "pulser-local-rich",
                            "name": "ConnectedApiPulser",
                            "pit_type": "Pulser",
                            "card": {
                                "name": "ConnectedApiPulser",
                                "address": "http://127.0.0.1:8125",
                                "pit_type": "Pulser",
                                "practices": [{"id": "get_pulse_data", "name": "Get Pulse Data"}],
                            },
                            "meta": {
                                "supported_pulses": [
                                    {"pulse_name": "quote", "pulse_address": "plaza://pulse/quote"},
                                    {"pulse_name": "profile", "pulse_address": "plaza://pulse/profile"},
                                ]
                            },
                        },
                        {
                            "agent_id": "pulser-local-thin",
                            "name": "ConnectedApiPulser",
                            "pit_type": "Pulser",
                            "card": {
                                "name": "ConnectedApiPulser",
                                "address": "http://127.0.0.1:8125",
                                "pit_type": "Pulser",
                                "practices": [{"id": "get_pulse_data", "name": "Get Pulse Data"}],
                            },
                            "meta": {
                                "supported_pulses": [
                                    {"pulse_name": "quote", "pulse_address": "plaza://pulse/quote"},
                                ]
                            },
                        },
                        {
                            "agent_id": "pulser-remote",
                            "name": "ConnectedApiPulser",
                            "pit_type": "Pulser",
                            "card": {
                                "name": "ConnectedApiPulser",
                                "address": "http://44.207.126.211:8125",
                                "pit_type": "Pulser",
                                "practices": [{"id": "get_pulse_data", "name": "Get Pulse Data"}],
                            },
                            "meta": {
                                "supported_pulses": [
                                    {"pulse_name": "quote", "pulse_address": "plaza://pulse/quote"},
                                ]
                            },
                        },
                    ],
                }
            ]
        },
        "http://127.0.0.1:8011",
    )

    assert payload["pulser_count"] == 1
    assert payload["pulsers"][0]["name"] == "ConnectedApiPulser"
    assert payload["pulsers"][0]["address"] == "http://127.0.0.1:8125"
    assert payload["pulsers"][0]["pulse_count"] == 2


def test_personal_agent_catalog_prefers_fresh_unique_pulser_over_stale_duplicate_count():
    """
    Exercise the test_personal_agent_catalog_prefers_fresh_unique_pulser_over_stale_
    duplicate_count regression scenario.
    """
    stale_supported_pulses = []
    for pulse_name in [
        "security_master_lookup",
        "daily_price_history",
        "company_fundamentals",
        "financial_statements",
        "company_news",
        "raw_collection_payload",
    ]:
        stale_supported_pulses.extend(
            [{"pulse_name": pulse_name, "pulse_address": f"plaza://pulse/{pulse_name}"}] * 5
        )

    payload = _normalize_catalog(
        {
            "plazas": [
                {
                    "url": "http://127.0.0.1:8011",
                    "online": True,
                    "card": {"name": "Plaza"},
                    "agents": [
                        {
                            "agent_id": "ads-stale",
                            "name": "ADSPulser",
                            "pit_type": "Pulser",
                            "last_active": 10,
                            "card": {
                                "name": "ADSPulser",
                                "address": "http://127.0.0.1:8062",
                                "pit_type": "Pulser",
                                "practices": [{"id": "get_pulse_data", "name": "Get Pulse Data"}],
                            },
                            "meta": {
                                "supported_pulses": stale_supported_pulses,
                            },
                        },
                        {
                            "agent_id": "ads-fresh",
                            "name": "ADSPulser",
                            "pit_type": "Pulser",
                            "last_active": 20,
                            "card": {
                                "name": "ADSPulser",
                                "address": "http://127.0.0.1:8062",
                                "pit_type": "Pulser",
                                "practices": [{"id": "get_pulse_data", "name": "Get Pulse Data"}],
                            },
                            "meta": {
                                "supported_pulses": [
                                    {"pulse_name": "security_master_lookup", "pulse_address": "plaza://pulse/security_master_lookup"},
                                    {"pulse_name": "daily_price_history", "pulse_address": "plaza://pulse/daily_price_history"},
                                    {"pulse_name": "company_profile", "pulse_address": "plaza://pulse/company_profile"},
                                    {"pulse_name": "financial_statements", "pulse_address": "plaza://pulse/financial_statements"},
                                    {"pulse_name": "news_article", "pulse_address": "plaza://pulse/news_article"},
                                    {"pulse_name": "raw_collection_payload", "pulse_address": "plaza://pulse/raw_collection_payload"},
                                    {"pulse_name": "sec_companyfact", "pulse_address": "plaza://pulse/sec_companyfact"},
                                    {"pulse_name": "sec_submission", "pulse_address": "plaza://pulse/sec_submission"},
                                ]
                            },
                        },
                    ],
                }
            ]
        },
        "http://127.0.0.1:8011",
    )

    assert payload["pulser_count"] == 1
    assert payload["pulsers"][0]["agent_id"] == "ads-fresh"
    assert payload["pulsers"][0]["pulse_count"] == 8
    assert len(payload["pulsers"][0]["supported_pulses"]) == 8


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


def test_personal_agent_local_file_save_and_load_roundtrip(tmp_path):
    """
    Exercise the test_personal_agent_local_file_save_and_load_roundtrip regression
    scenario.
    """
    save_response = client.post(
        "/api/files/save/local",
        json={
            "directory": str(tmp_path),
            "file_name": "workspace-state.json",
            "title": "workspace-state",
            "content": {"activeWorkspaceId": "workspace-1", "workspaces": [{"id": "workspace-1"}]},
        },
    )

    assert save_response.status_code == 200
    saved_payload = save_response.json()
    assert saved_payload["file"]["file_name"] == "workspace-state.json"

    load_response = client.post(
        "/api/files/load/local",
        json={
            "directory": str(tmp_path),
            "file_name": "workspace-state.json",
        },
    )

    assert load_response.status_code == 200
    loaded_payload = load_response.json()
    assert loaded_payload["file"]["content"]["activeWorkspaceId"] == "workspace-1"
    assert loaded_payload["file"]["content"]["workspaces"][0]["id"] == "workspace-1"
