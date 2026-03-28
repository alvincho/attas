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


def test_path_pulser_conditionally_fetches_branch_steps(monkeypatch):
    captured = []

    def fake_post(url, json=None, timeout=30):
        captured.append({"url": url, "json": json, "timeout": timeout})
        return FakePostResponse(
            {
                "symbol": json["content"]["params"]["symbol"],
                "interval": json["content"]["params"]["interval"],
                "start_date": json["content"]["params"]["start_date"],
                "end_date": json["content"]["params"]["end_date"],
                "ohlc_series": [
                    {
                        "timestamp": "2025-01-01T00:00:00Z",
                        "open": 100.0,
                        "high": 101.0,
                        "low": 99.0,
                        "close": 100.5,
                        "volume": 1000.0,
                    },
                    {
                        "timestamp": "2025-01-02T00:00:00Z",
                        "open": 101.0,
                        "high": 102.0,
                        "low": 100.0,
                        "close": 101.5,
                        "volume": 1100.0,
                    },
                ],
                "source": "yfinance",
            }
        )

    monkeypatch.setattr("phemacast.pulsers.path_pulser.requests.post", fake_post)

    pulser = PathPulser(
        config={
            "name": "ConditionalPathPulser",
            "supported_pulses": [
                {
                    "name": "timeseries_summary",
                    "pulse_address": "plaza://pulse/timeseries_summary",
                    "steps": [
                        {
                            "name": "load_ohlc_series",
                            "type": "source",
                            "pulser_url": "http://127.0.0.1:8020",
                            "pulse_name": "ohlc_bar_series",
                            "params": {
                                "symbol": "{{_input.symbol}}",
                                "interval": "{{_input.interval}}",
                                "start_date": "{{_input.start_date}}",
                                "end_date": "{{_input.end_date}}",
                            },
                            "when": {
                                "missing": ["ohlc_series"],
                                "present": ["symbol", "interval", "start_date", "end_date"],
                            },
                        },
                        {
                            "name": "compute",
                            "type": "python",
                            "script": "\n".join(
                                [
                                    "series = (previous_output or {}).get('ohlc_series') or input_data.get('ohlc_series') or []",
                                    "result = {",
                                    "    'count': len(series),",
                                    "    'source': (previous_output or {}).get('source'),",
                                    "}",
                                ]
                            ),
                        },
                    ],
                    "result_path": "steps.compute",
                }
            ],
        },
        auto_register=False,
    )

    fetched = pulser.get_pulse_data(
        {
            "symbol": "AAPL",
            "interval": "1d",
            "start_date": "2025-01-01T00:00:00Z",
            "end_date": "2025-01-02T00:00:00Z",
        },
        pulse_name="timeseries_summary",
    )
    assert fetched == {"count": 2, "source": "yfinance"}
    assert len(captured) == 1
    assert pulser.last_fetch_debug["steps"][0]["skipped"] is False

    captured.clear()
    direct = pulser.get_pulse_data(
        {
            "interval": "1d",
            "ohlc_series": [
                {
                    "timestamp": "2025-01-01T00:00:00Z",
                    "open": 200.0,
                    "high": 201.0,
                    "low": 199.0,
                    "close": 200.5,
                    "volume": 2000.0,
                }
            ],
        },
        pulse_name="timeseries_summary",
    )
    assert direct == {"count": 1, "source": None}
    assert captured == []
    assert pulser.last_fetch_debug["steps"][0]["skipped"] is True


def test_path_pulser_includes_remote_caller_metadata_for_upstream_calls(monkeypatch):
    captured = []

    def fake_post(url, json=None, timeout=30):
        captured.append({"url": url, "json": json, "timeout": timeout})
        return FakePostResponse({"symbol": "AAPL", "last_price": 214.37})

    monkeypatch.setattr("phemacast.pulsers.path_pulser.requests.post", fake_post)

    pulser = PathPulser(
        config={
            "name": "AuthenticatedPathPulser",
            "plaza_url": "http://44.207.126.211:8000",
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
                }
            ],
        },
        auto_register=False,
    )
    pulser.agent_id = "path-pulser-id"
    pulser.plaza_url = "http://44.207.126.211:8000"
    pulser.direct_auth_token = "shared-direct-token"
    pulser._refresh_pit_address()

    monkeypatch.setattr(
        pulser,
        "_ensure_token_valid",
        lambda: {"Authorization": "Bearer plaza-token"},
    )

    result = pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="last_price_summary")

    assert result == {"symbol": "AAPL", "last_price": 214.37}
    assert captured[0]["json"]["sender"] == "path-pulser-id"
    assert captured[0]["json"]["caller_agent_address"]["pit_id"] == "path-pulser-id"
    assert captured[0]["json"]["caller_agent_address"]["plazas"] == ["http://44.207.126.211:8000"]
    assert captured[0]["json"]["caller_plaza_token"] == "plaza-token"
    assert captured[0]["json"]["caller_direct_token"] == "shared-direct-token"


def test_path_pulser_unwraps_remote_practice_results(monkeypatch):
    def fake_post(url, json=None, timeout=30):
        return FakePostResponse(
            {
                "status": "ok",
                "result": {"symbol": "AAPL", "last_price": 214.37, "currency": "USD"},
            }
        )

    monkeypatch.setattr("phemacast.pulsers.path_pulser.requests.post", fake_post)

    pulser = PathPulser(
        config={
            "name": "WrappedResponsePathPulser",
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
                }
            ],
        },
        auto_register=False,
    )

    result = pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="last_price_summary")

    assert result == {"symbol": "AAPL", "last_price": 214.37, "currency": "USD"}


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
        assert "Path Step Lab" in root.text
        assert "Open Step Lab" in root.text
        assert "Drag Step Types" in root.text
        assert "Canvas Flow" in root.text
        assert "Step Inspector" in root.text
        assert "Final Result Path" in root.text
        assert "Completion Status" in root.text
        assert "Pulse Test Data JSON" in root.text
        assert "Test Runner" in root.text
        assert "Pulse Test Runner" not in root.text
        assert "Fill in parameters from the input schema" not in root.text

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


def test_path_pulser_editor_hydrates_file_backed_test_data_for_runner(tmp_path):
    config_dir = tmp_path / "configs"
    data_dir = tmp_path / "data"
    pool_dir = tmp_path / "storage"
    config_dir.mkdir()
    data_dir.mkdir()

    sample_data = {
        "symbol": "IBM",
        "interval": "1d",
        "timestamp": "2025-01-20T00:00:00Z",
        "window": 20,
    }
    (data_dir / "sample_ta.json").write_text(json.dumps(sample_data), encoding="utf-8")

    config_path = config_dir / "enum_test.pulser"
    config_path.write_text(
        json.dumps(
            {
                "name": "EnumTestPulser",
                "type": "phemacast.pulsers.path_pulser.PathPulser",
                "host": "127.0.0.1",
                "port": 8131,
                "description": "Path pulser with file-backed test samples",
                "supported_pulses": [
                    {
                        "name": "sma",
                        "description": "Simple Moving Average",
                        "pulse_address": "plaza://pulse/sma",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "interval": {"type": "string", "enum": ["1m", "5m", "1d"]},
                                "timestamp": {"type": "string", "format": "date-time"},
                                "window": {"type": "integer"},
                            },
                            "required": ["interval", "timestamp", "window"],
                            "additionalProperties": False,
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "values": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "timestamp": {"type": "string"},
                                            "value": {"type": "number"},
                                        },
                                        "required": ["timestamp", "value"],
                                        "additionalProperties": False,
                                    },
                                }
                            },
                            "required": ["values"],
                            "additionalProperties": False,
                        },
                        "steps": [
                            {
                                "name": "compute",
                                "type": "python",
                                "script": "result = {'values': [{'timestamp': input_data['timestamp'], 'value': float(input_data['window'])}]}",
                            }
                        ],
                        "result_path": "steps.compute",
                        "test_data_path": "../data/sample_ta.json",
                    }
                ],
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "enum_test_pool",
                        "description": "test pool",
                        "root_path": str(pool_dir),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))

    with TestClient(agent.app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "test-runner-title" in root.text
        assert "Pulse Test Runner" not in root.text
        assert "Fill in parameters from the input schema" not in root.text
        assert "Choose…" in root.text
        assert "Open Step Lab" in root.text
        assert "Drag Step Types" in root.text
        assert "Canvas Flow" in root.text
        assert "Step Inspector" in root.text

        current = client.get("/api/config")
        assert current.status_code == 200
        payload = current.json()["config"]
        pulse = payload["supported_pulses"][0]
        assert pulse["test_data_path"] == "../data/sample_ta.json"
        assert pulse["resolved_test_data"] == sample_data

        saved = client.post("/api/config", json={"config": payload})
        assert saved.status_code == 200

    written = json.loads(config_path.read_text(encoding="utf-8"))
    written_pulse = written["supported_pulses"][0]
    assert "resolved_test_data" not in written_pulse
    assert "resolved_test_data_error" not in written_pulse
    assert written_pulse["test_data_path"] == "../data/sample_ta.json"


def test_path_pulser_loads_relative_script_and_test_data_files(tmp_path):
    config_dir = tmp_path / "configs"
    script_dir = tmp_path / "scripts"
    data_dir = tmp_path / "data"
    pool_dir = tmp_path / "storage"
    config_dir.mkdir()
    script_dir.mkdir()
    data_dir.mkdir()

    script_path = script_dir / "compute_metric.py"
    script_path.write_text(
        "\n".join(
            [
                "def build_value():",
                "    return float(input_data.get('base', 0)) + 7.0",
                "",
                "result = {'value': build_value()}",
            ]
        ),
        encoding="utf-8",
    )

    test_data_path = data_dir / "sample_metric.json"
    test_data_path.write_text(json.dumps({"base": 5}), encoding="utf-8")

    config_path = config_dir / "relative_files.pulser"
    config_path.write_text(
        json.dumps(
            {
                "name": "RelativeFilePathPulser",
                "type": "phemacast.pulsers.path_pulser.PathPulser",
                "host": "127.0.0.1",
                "port": 8128,
                "description": "Demo path pulser with relative support files",
                "tags": ["path", "relative-files"],
                "supported_pulses": [
                    {
                        "name": "scripted_metric",
                        "pulse_address": "plaza://pulse/scripted_metric",
                        "output_schema": {
                            "type": "object",
                            "properties": {"value": {"type": "number"}},
                            "required": ["value"],
                            "additionalProperties": False,
                        },
                        "steps": [
                            {
                                "name": "compute",
                                "type": "python",
                                "script_path": "../scripts/compute_metric.py",
                            }
                        ],
                        "result_path": "steps.compute",
                        "test_data_path": "../data/sample_metric.json",
                    }
                ],
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "relative_files_pool",
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
    assert agent.supported_pulses[0]["completion_status"] == "complete"
    assert agent.get_pulse_data({"base": 12}, pulse_name="scripted_metric") == {"value": 19.0}
