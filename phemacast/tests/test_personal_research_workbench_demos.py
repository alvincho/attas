"""
Regression tests for Personal Research Workbench Demos.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_seeded_ohlc_to_rsi_map_executes_demo_flow`,
`test_demo_map_phemar_api_lists_seeded_diagram`, and
`test_demo_technical_analysis_pulser_matches_reference_rsi_output`, helping guard
against regressions as the packages evolve.
"""

import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.agents.map_phemar import MapPhemarAgent
from phemacast.map_phemar.executor import execute_map_phema
from phemacast.pulsers.path_pulser import PathPulser
from prompits.tests.test_support import build_agent_from_config


class FakeResponse:
    """Response model for fake payloads."""
    def __init__(self, payload, status_code=200):
        """Initialize the fake response."""
        self._payload = payload
        self.status_code = status_code

    def json(self):
        """Handle JSON for the fake response."""
        return self._payload


def _repo_root() -> Path:
    """Internal helper for repo root."""
    return Path(__file__).resolve().parents[2]


def _demo_root() -> Path:
    """Internal helper for demo root."""
    return _repo_root() / "demos" / "personal-research-workbench"


def _load_json(path: Path) -> dict:
    """Internal helper to load the JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def test_demo_technical_analysis_pulser_matches_reference_rsi_output():
    """
    Exercise the test_demo_technical_analysis_pulser_matches_reference_rsi_output
    regression scenario.
    """
    root = _repo_root()
    demo_pulser = PathPulser(config=str(_demo_root() / "technical-analysis.pulser"), auto_register=False)
    reference_pulser = PathPulser(config=str(root / "attas" / "configs" / "ta.pulser"), auto_register=False)
    payload = _load_json(root / "attas" / "examples" / "pulses" / "technical_analysis_test_data.json")

    demo_rsi = next(pulse for pulse in demo_pulser.supported_pulses if pulse["name"] == "rsi")
    assert demo_pulser.name == "DemoTechnicalAnalysisPulser"
    assert demo_rsi["steps"][0]["pulser_url"] == "http://127.0.0.1:8243"

    demo_result = demo_pulser.get_pulse_data(dict(payload), pulse_name="rsi")
    reference_result = reference_pulser.get_pulse_data(dict(payload), pulse_name="rsi")

    assert demo_result == reference_result
    assert demo_result["values"][0]["timestamp"] == "2025-01-15T00:00:00Z"
    assert demo_result["values"][-1]["timestamp"] == payload["timestamp"]


def test_seeded_ohlc_to_rsi_map_executes_demo_flow():
    """
    Exercise the test_seeded_ohlc_to_rsi_map_executes_demo_flow regression scenario.
    """
    fixture = _load_json(_repo_root() / "attas" / "examples" / "pulses" / "technical_analysis_test_data.json")
    phema = _load_json(_demo_root() / "map_phemar_pool" / "phemas" / "demo-ohlc-to-rsi-diagram.json")
    ta_pulser = PathPulser(config=str(_demo_root() / "technical-analysis.pulser"), auto_register=False)
    calls = []

    def fake_post(url, json=None, timeout=None):
        """Handle fake post."""
        assert url == "http://127.0.0.1:8241/api/pulsers/test"
        assert isinstance(json, dict)
        calls.append(json["pulse_name"])

        if json["pulse_name"] == "ohlc_bar_series":
            assert json["pulser_name"] == "DemoYFinancePulser"
            assert json["input"] == {
                "symbol": fixture["symbol"],
                "interval": fixture["interval"],
                "start_date": fixture["start_date"],
                "end_date": fixture["end_date"],
            }
            return FakeResponse(
                {
                    "status": "success",
                    "result": {
                        "symbol": fixture["symbol"],
                        "interval": fixture["interval"],
                        "start_date": fixture["start_date"],
                        "end_date": fixture["end_date"],
                        "ohlc_series": fixture["ohlc_series"],
                        "source": "fixture",
                    },
                }
            )

        if json["pulse_name"] == "rsi":
            assert json["pulser_name"] == "DemoTechnicalAnalysisPulser"
            assert json["input"]["window"] == 14
            assert json["input"]["price_field"] == "close"
            assert json["input"]["ohlc_series"] == fixture["ohlc_series"]
            return FakeResponse(
                {
                    "status": "success",
                    "result": ta_pulser.get_pulse_data(dict(json["input"]), pulse_name="rsi"),
                }
            )

        raise AssertionError(f"Unexpected pulse_name: {json['pulse_name']}")

    result = execute_map_phema(
        phema,
        input_data={
            "symbol": fixture["symbol"],
            "interval": fixture["interval"],
            "start_date": fixture["start_date"],
            "end_date": fixture["end_date"],
        },
        request_post=fake_post,
    )

    expected_output = ta_pulser.get_pulse_data(
        {
            "symbol": fixture["symbol"],
            "interval": fixture["interval"],
            "start_date": fixture["start_date"],
            "end_date": fixture["end_date"],
            "ohlc_series": fixture["ohlc_series"],
            "window": 14,
            "price_field": "close",
        },
        pulse_name="rsi",
    )

    assert calls == ["ohlc_bar_series", "rsi"]
    assert result["status"] == "success"
    assert result["output"] == expected_output
    assert [step["title"] for step in result["steps"]] == ["Input", "OHLC Bars", "RSI 14", "Output"]


def test_demo_map_phemar_api_lists_seeded_diagram():
    """
    Exercise the test_demo_map_phemar_api_lists_seeded_diagram regression scenario.
    """
    agent = build_agent_from_config(str(_demo_root() / "map_phemar.phemar"))
    assert isinstance(agent, MapPhemarAgent)

    with TestClient(agent.app) as client:
        listing = client.get("/api/phemas")
        assert listing.status_code == 200
        phemas = listing.json()["phemas"]
        assert any(phema["phema_id"] == "demo-ohlc-to-rsi-diagram" for phema in phemas)

        detail = client.get("/api/phemas/demo-ohlc-to-rsi-diagram")
        assert detail.status_code == 200
        saved = detail.json()["phema"]
        assert saved["name"] == "OHLC To RSI Diagram"
        nodes = saved["meta"]["map_phemar"]["diagram"]["nodes"]
        assert [node["title"] for node in nodes if node.get("title")] == ["Input", "OHLC Bars", "RSI 14", "Output"]
