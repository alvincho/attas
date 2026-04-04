"""
Regression tests for API Pulser UI.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_api_pulser_has_dedicated_ui_and_saves_config_file` and
`test_api_pulser_ui_shows_baseagent_plaza_connection_status`, helping guard against
regressions as the packages evolve.
"""

import json
import os
import sys
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.tests.test_support import build_agent_from_config


class FakeHttpResponse:
    """Response model for fake HTTP payloads."""
    def raise_for_status(self):
        """Return the raise for the status."""
        return None

    def json(self):
        """Handle JSON for the fake HTTP response."""
        return {"data": {"quote": {"price": 214.37}}}


class FakeResponse:
    """Response model for fake payloads."""
    def __init__(self, payload, status_code=200):
        """Initialize the fake response."""
        self._payload = payload
        self.status_code = status_code
        self.content = json.dumps(payload).encode("utf-8")

    def json(self):
        """Handle JSON for the fake response."""
        return self._payload


class FakeHttpClient:
    """Represent a fake HTTP client."""
    def __enter__(self):
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type, exc, tb):
        """Exit the context manager."""
        return False

    def request(self, method, url, headers=None):
        """Request the value."""
        return FakeHttpResponse()


def test_api_pulser_has_dedicated_ui_and_saves_config_file(tmp_path, monkeypatch):
    """
    Exercise the test_api_pulser_has_dedicated_ui_and_saves_config_file regression
    scenario.
    """
    pool_dir = tmp_path / "storage"
    config_path = tmp_path / "demo_api_pulser.config"
    monkeypatch.setenv("UPDATED_PULSE_KEY", "updated-pulse-key")
    monkeypatch.setenv("UPDATED_MARKET_KEY", "updated-market-key")
    monkeypatch.setattr(
        "phemacast.pulsers.api_pulser.httpx.Client",
        lambda timeout=10.0: FakeHttpClient(),
    )
    config_path.write_text(
        json.dumps(
            {
                "name": "DemoApiPulser",
                "type": "phemacast.pulsers.api_pulser.APIsPulser",
                "host": "127.0.0.1",
                "port": 8124,
                "description": "Demo pulser",
                "tags": ["finance", "market-data"],
                "api_key": {"env": "DEMO_API_KEY"},
                "api_keys": [
                    {"id": "market", "env": "MARKET_API_KEY", "header": "x-api-key"},
                    {"id": "news", "value": "news-secret", "prefix": "Token "},
                ],
                "supported_pulses": [
                    {
                        "name": "last_price",
                        "description": "Latest traded price",
                        "pulse_address": "plaza://pulse/last_price",
                        "api": {
                            "url": "https://example.test/quote/{symbol}",
                            "method": "GET",
                            "root_path": "data.quote",
                            "headers": {"x-api-key": "demo"},
                            "api_key": {"env": "PULSE_LEVEL_KEY"},
                            "api_key_header": "x-api-key",
                            "api_key_id": "market",
                            "api_key_param": "apikey",
                        },
                        "input_schema": {
                            "type": "object",
                            "properties": {"symbol": {"type": "string"}},
                            "required": ["symbol"],
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {"last_price": {"type": "number"}},
                        },
                        "mapping": {"last_price": "price"},
                        "test_data": {"symbol": "AAPL"},
                    }
                ],
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "demo_pool",
                        "description": "test pool",
                        "root_path": str(pool_dir),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))
    assert agent.config_path == config_path.resolve()
    assert agent.supported_pulses[0]["name"] == "last_price"

    with TestClient(agent.app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "DemoApiPulser Config" in root.text
        assert "Search Supported Pulses" in root.text
        assert "Filter" in root.text
        assert "Sort" in root.text
        assert "Name A-Z" in root.text
        assert "Has Test Data" in root.text
        assert "APIsPulser Details" in root.text
        assert "Pulse Details" in root.text
        assert "Test Data" in root.text
        assert '<div id="test-runner-modal-root"></div>' in root.text
        assert '<div id="config-preview" class="json-tree-shell"></div>' in root.text
        assert "Pulse Test Data JSON" in root.text
        assert "API Key Query Param" in root.text
        assert 'id="pulser-details-content" class="collapsible-content collapsed"' in root.text
        assert 'id="pulse-details-content" class="collapsible-content collapsed"' in root.text
        assert '<div id="test-runner-result" class="json-tree-shell result"></div>' in root.text
        assert '<div id="test-last-params" class="json-tree-shell compact"></div>' in root.text

        current = client.get("/api/config")
        assert current.status_code == 200
        payload = current.json()["config"]
        assert payload["name"] == "DemoApiPulser"
        assert payload["api_key"]["env"] == "DEMO_API_KEY"
        assert payload["api_keys"][0]["id"] == "market"
        assert payload["supported_pulses"][0]["test_data"]["symbol"] == "AAPL"

        invalid_payload = json.loads(json.dumps(payload))
        invalid_payload["supported_pulses"][0]["test_data"] = {}
        invalid_save = client.post("/api/config", json={"config": invalid_payload})
        assert invalid_save.status_code == 400
        assert "at least one set of test parameters" in invalid_save.json()["detail"]

        payload["description"] = "Updated pulser"
        payload["api_key"] = "literal-top-level-key"
        payload["api_keys"][0]["env"] = "UPDATED_MARKET_KEY"
        payload["api_keys"][0]["param"] = "apikey"
        payload["supported_pulses"][0]["test_data"] = {"symbol": "MSFT", "window": "1d"}
        payload["supported_pulses"][0]["api"]["api_key"] = {"env": "UPDATED_PULSE_KEY"}
        payload["supported_pulses"][0]["api"]["api_key_id"] = "market"
        payload["supported_pulses"][0]["api"]["api_key_param"] = "apikey"
        payload["supported_pulses"].append(
            {
                "name": "trade_volume",
                "description": "Share volume",
                "pulse_address": "plaza://pulse/trade_volume",
                "api": {
                    "url": "https://example.test/volume/{symbol}",
                    "method": "GET",
                    "root_path": "data",
                    "headers": {},
                    "api_key_id": "news",
                },
                "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}},
                "output_schema": {"type": "object", "properties": {"volume": {"type": "number"}}},
                "mapping": {"volume": "volume"},
                "test_data": {"symbol": "NVDA"},
            }
        )

        saved = client.post("/api/config", json={"config": payload})
        assert saved.status_code == 200
        saved_payload = saved.json()["config"]
        assert saved_payload["description"] == "Updated pulser"
        assert saved_payload["api_key"] == "literal-top-level-key"
        assert saved_payload["api_keys"][0]["env"] == "UPDATED_MARKET_KEY"
        assert len(saved_payload["supported_pulses"]) == 2

        tested = client.post(
            "/api/test-pulse",
            json={
                "config": payload,
                "pulse_name": "last_price",
                "params": {"symbol": "AAPL"},
                "debug": True,
            },
        )
        assert tested.status_code == 200
        tested_payload = tested.json()
        assert tested_payload["status"] == "success"
        assert tested_payload["result"]["last_price"] == 214.37
        assert tested_payload["debug"]["pulse_definition"]["name"] == "last_price"
        assert tested_payload["debug"]["fetch"]["request"]["method"] == "GET"
        assert tested_payload["debug"]["raw_payload"]["price"] == 214.37

    written = json.loads(config_path.read_text(encoding="utf-8"))
    assert written["description"] == "Updated pulser"
    assert written["api_key"] == "literal-top-level-key"
    assert written["api_keys"][0]["env"] == "UPDATED_MARKET_KEY"
    assert written["api_keys"][0]["param"] == "apikey"
    assert written["supported_pulses"][0]["api"]["api_key"]["env"] == "UPDATED_PULSE_KEY"
    assert written["supported_pulses"][0]["api"]["api_key_id"] == "market"
    assert written["supported_pulses"][0]["api"]["api_key_param"] == "apikey"
    assert written["supported_pulses"][0]["test_data"]["symbol"] == "MSFT"
    assert written["supported_pulses"][1]["name"] == "trade_volume"
    assert written["supported_pulses"][1]["api"]["api_key_id"] == "news"
    assert agent.supported_pulses[1]["test_data"]["symbol"] == "NVDA"


def test_api_pulser_ui_shows_baseagent_plaza_connection_status(tmp_path, monkeypatch):
    """
    Exercise the test_api_pulser_ui_shows_baseagent_plaza_connection_status
    regression scenario.
    """
    config_path = tmp_path / "connected_api_pulser.config"
    pool_dir = tmp_path / "storage"
    monkeypatch.setattr(
        "phemacast.pulsers.api_pulser.httpx.Client",
        lambda timeout=10.0: FakeHttpClient(),
    )
    config_path.write_text(
        json.dumps(
            {
                "name": "ConnectedApiPulser",
                "type": "phemacast.pulsers.api_pulser.APIsPulser",
                "host": "127.0.0.1",
                "port": 8125,
                "plaza_url": "http://127.0.0.1:8011",
                "supported_pulses": [
                    {
                        "name": "last_price",
                        "pulse_address": "plaza://pulse/last_price",
                        "api": {
                            "url": "https://example.test/quote/{symbol}",
                            "method": "GET",
                        },
                        "mapping": {"last_price": "price"},
                    }
                ],
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "demo_pool",
                        "description": "test pool",
                        "root_path": str(pool_dir),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))
    agent.agent_id = "pulser-123"
    agent.last_plaza_heartbeat_at = time.time() - 5

    def fake_plaza_get(path, **kwargs):
        """Handle fake Plaza get."""
        if path == "/health":
            return FakeResponse({"status": "ok"}, 200)
        if path == "/search":
            return FakeResponse(
                [
                    {
                        "agent_id": "pulser-123",
                        "name": "ConnectedApiPulser",
                        "last_active": time.time() - 4,
                    }
                ],
                200,
            )
        raise AssertionError(f"Unexpected path: {path}")

    with (
        patch.object(agent, "_ensure_token_valid", return_value={"Authorization": "Bearer token"}),
        patch.object(agent, "_plaza_get", side_effect=fake_plaza_get),
    ):
        with TestClient(agent.app) as client:
            root = client.get("/")
            assert root.status_code == 200
            assert 'src="/static/agent_connection.js' in root.text
            assert 'class="hero agent-sticky-header"' in root.text
            assert "mountStickyHeader" in root.text
            assert 'id="agent-plaza-pill"' in root.text
            assert 'id="agent-plaza-note"' in root.text

            response = client.get("/api/plaza_connection_status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["plaza_url"] == "http://127.0.0.1:8011"
    assert payload["agent_id"] == "pulser-123"
    assert payload["online"] is True
    assert payload["authenticated"] is True
    assert payload["connection_status"] == "connected"
