import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.pulsers.path_pulser import PathPulser
from prompits.tests.test_support import build_agent_from_config


class FakePostResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")

    def json(self):
        return self._payload


def test_path_pulser_combines_multiple_upstream_pulsers(monkeypatch):
    captured = []

    def fake_post(url, json=None, timeout=30):
        captured.append({"url": url, "json": json, "timeout": timeout})
        pulse_name = json["content"]["pulse_name"]
        params = json["content"]["params"]
        if pulse_name == "last_price":
            return FakePostResponse({"symbol": params["symbol"], "last_price": 214.37, "currency": "USD"})
        if pulse_name == "company_profile":
            return FakePostResponse({"symbol": params["symbol"], "company_name": "Apple Inc.", "sector": "Technology"})
        raise AssertionError(f"Unexpected pulse_name: {pulse_name}")

    monkeypatch.setattr("phemacast.pulsers.path_pulser.requests.post", fake_post)

    pulser = PathPulser(
        config={
            "name": "PathComposer",
            "supported_pulses": [
                {
                    "name": "stock_snapshot",
                    "pulse_address": "plaza://pulse/stock_snapshot",
                    "steps": [
                        {
                            "name": "market_data",
                            "type": "source",
                            "pulser_url": "http://127.0.0.1:8020",
                            "pulse_name": "last_price",
                            "params": {"symbol": "{{_input.symbol}}"},
                        },
                        {
                            "name": "profile_data",
                            "type": "source",
                            "pulser_url": "http://127.0.0.1:8021",
                            "pulse_name": "company_profile",
                            "params": {"symbol": "{{_input.symbol}}"},
                        },
                        {
                            "name": "compose",
                            "type": "python",
                            "sources": [
                                {
                                    "name": "price",
                                    "pulser_url": "http://127.0.0.1:8020",
                                    "pulse_name": "last_price",
                                    "params": {"symbol": "{{_input.symbol}}"},
                                },
                                {
                                    "name": "profile",
                                    "pulser_url": "http://127.0.0.1:8021",
                                    "pulse_name": "company_profile",
                                    "params": {"symbol": "{{_input.symbol}}"},
                                },
                            ],
                            "script": "\n".join(
                                [
                                    "result = {",
                                    "    'symbol': input_data.get('symbol'),",
                                    "    'last_price': sources['price']['last_price'],",
                                    "    'currency': sources['price']['currency'],",
                                    "    'company_name': sources['profile']['company_name'],",
                                    "    'sector': sources['profile']['sector'],",
                                    "}",
                                ]
                            ),
                        },
                    ],
                    "result_path": "steps.compose",
                    "test_data": {"symbol": "AAPL"},
                }
            ],
        },
        auto_register=False,
    )
    captured.clear()

    result = pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="stock_snapshot")

    assert result == {
        "symbol": "AAPL",
        "last_price": 214.37,
        "currency": "USD",
        "company_name": "Apple Inc.",
        "sector": "Technology",
    }
    assert len(captured) == 4
    assert captured[0]["url"] == "http://127.0.0.1:8020/use_practice/get_pulse_data"
    assert captured[1]["url"] == "http://127.0.0.1:8021/use_practice/get_pulse_data"
    assert captured[2]["json"]["content"]["params"] == {"symbol": "AAPL"}


def test_path_pulser_applies_mapping_to_composed_result(monkeypatch):
    def fake_post(url, json=None, timeout=30):
        pulse_name = json["content"]["pulse_name"]
        if pulse_name == "last_price":
            return FakePostResponse({"symbol": "MSFT", "last_price": 401.25, "currency": "USD"})
        raise AssertionError(f"Unexpected pulse_name: {pulse_name}")

    monkeypatch.setattr("phemacast.pulsers.path_pulser.requests.post", fake_post)

    pulser = PathPulser(
        config={
            "name": "MappedPathPulser",
            "supported_pulses": [
                {
                    "name": "last_price_summary",
                    "pulse_address": "plaza://pulse/last_price_summary",
                    "steps": [
                        {
                            "name": "price",
                            "type": "source",
                            "pulser_url": "http://127.0.0.1:8020",
                            "pulse_name": "last_price",
                            "params": {"symbol": "{{_input.symbol}}"},
                        }
                    ],
                    "result_path": "steps.price",
                    "mapping": {
                        "symbol": "result.symbol",
                        "summary.last_price": "result.last_price",
                        "summary.currency": "result.currency",
                    },
                }
            ],
        },
        auto_register=False,
    )

    result = pulser.get_pulse_data({"symbol": "MSFT"}, pulse_name="last_price_summary")

    assert result == {
        "symbol": "MSFT",
        "summary": {
            "last_price": 401.25,
            "currency": "USD",
        },
    }


def test_path_pulser_marks_unfinished_when_final_step_does_not_match_output_schema(monkeypatch):
    def fake_post(url, json=None, timeout=30):
        return FakePostResponse({"symbol": "AAPL", "last_price": 214.37})

    monkeypatch.setattr("phemacast.pulsers.path_pulser.requests.post", fake_post)

    pulser = PathPulser(
        config={
            "name": "IncompletePathPulser",
            "supported_pulses": [
                {
                    "name": "stock_snapshot",
                    "pulse_address": "plaza://pulse/stock_snapshot",
                    "output_schema": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "last_price": {"type": "number"},
                            "currency": {"type": "string"},
                        },
                        "required": ["symbol", "last_price", "currency"],
                    },
                    "steps": [
                        {
                            "name": "quote",
                            "type": "source",
                            "pulser_url": "http://127.0.0.1:8020",
                            "pulse_name": "last_price",
                            "params": {"symbol": "{{_input.symbol}}"},
                        }
                    ],
                    "result_path": "steps.quote",
                    "test_data": {"symbol": "AAPL"},
                }
            ],
        },
        auto_register=False,
    )

    pulse = pulser.supported_pulses[0]
    assert pulse["is_complete"] is False
    assert pulse["completion_status"] == "unfinished"
    assert any("currency" in error for error in pulse["completion_errors"])

    payload = pulser.build_register_payload("http://127.0.0.1:8011")
    assert payload["pulse_pulser_pairs"][0]["is_complete"] is False
    assert payload["pulse_pulser_pairs"][0]["status"] == "unfinished"


def test_path_pulser_has_config_ui_and_test_endpoint(tmp_path, monkeypatch):
    pool_dir = tmp_path / "storage"
    config_path = tmp_path / "demo_path.pulser"
    config_path.write_text(
        json.dumps(
            {
                "name": "DemoPathPulser",
                "type": "phemacast.pulsers.path_pulser.PathPulser",
                "host": "127.0.0.1",
                "port": 8127,
                "description": "Demo path pulser",
                "tags": ["path", "composition"],
                "supported_pulses": [
                    {
                        "name": "stock_snapshot",
                        "description": "Compose multiple source pulses",
                        "pulse_address": "plaza://pulse/stock_snapshot",
                        "steps": [
                            {
                                "name": "compose",
                                "type": "python",
                                "sources": [
                                    {
                                        "name": "price",
                                        "pulser_url": "http://127.0.0.1:8020",
                                        "pulse_name": "last_price",
                                        "params": {"symbol": "{{_input.symbol}}"},
                                    }
                                ],
                                "script": "result = {'symbol': input_data.get('symbol'), 'last_price': sources['price']['last_price']}",
                            }
                        ],
                        "result_path": "steps.compose",
                        "test_data": {"symbol": "NVDA"},
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

    def fake_post(url, json=None, timeout=30):
        return FakePostResponse({"symbol": json["content"]["params"]["symbol"], "last_price": 133.7, "currency": "USD"})

    monkeypatch.setattr("phemacast.pulsers.path_pulser.requests.post", fake_post)

    agent = build_agent_from_config(str(config_path))

    with TestClient(agent.app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "DemoPathPulser Config" in root.text
        assert "Search Supported Pulses" in root.text
        assert "Path Editor" in root.text
        assert "Final Result Path" in root.text
        assert "Completion Status" in root.text
        assert "Pulse Test Data JSON" in root.text
        assert "Test Runner" in root.text

        current = client.get("/api/config")
        assert current.status_code == 200
        payload = current.json()["config"]
        assert payload["name"] == "DemoPathPulser"
        assert payload["supported_pulses"][0]["test_data"]["symbol"] == "NVDA"
        assert payload["supported_pulses"][0]["steps"][0]["name"] == "compose"

        payload["description"] = "Updated path pulser"
        payload["supported_pulses"][0]["result_path"] = "steps.compose"
        payload["supported_pulses"][0]["test_data"] = {"symbol": "AAPL"}

        saved = client.post("/api/config", json={"config": payload})
        assert saved.status_code == 200
        saved_payload = saved.json()["config"]
        assert saved_payload["description"] == "Updated path pulser"
        assert saved_payload["supported_pulses"][0]["test_data"]["symbol"] == "AAPL"

        tested = client.post(
            "/api/test-pulse",
            json={
                "config": payload,
                "pulse_name": "stock_snapshot",
                "params": {"symbol": "AAPL"},
                "debug": True,
            },
        )
        assert tested.status_code == 200
        tested_payload = tested.json()
        assert tested_payload["status"] == "success"
        assert tested_payload["result"]["last_price"] == 133.7
        assert tested_payload["result"]["symbol"] == "AAPL"
        assert tested_payload["debug"]["pulse_definition"]["name"] == "stock_snapshot"
        assert tested_payload["debug"]["raw_payload"]["result"]["last_price"] == 133.7

    written = json.loads(config_path.read_text(encoding="utf-8"))
    assert written["description"] == "Updated path pulser"
    assert written["supported_pulses"][0]["test_data"]["symbol"] == "AAPL"
