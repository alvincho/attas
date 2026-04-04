"""
Regression tests for Demo File Diagrams.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_demo_file_diagrams_execute_against_reference_ta_pulser`, helping guard against
regressions as the packages evolve.
"""

import json
import os
import sys
from pathlib import Path

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.map_phemar.executor import execute_map_phema
from phemacast.pulsers.path_pulser import PathPulser


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


def _load_json(path: Path) -> dict:
    """Internal helper to load the JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("filename", "indicator_name"),
    [
        ("ohlc-to-sma-20-diagram.json", "sma"),
        ("ohlc-to-ema-50-diagram.json", "ema"),
        ("ohlc-to-macd-histogram-diagram.json", "macd_histogram"),
        ("ohlc-to-bollinger-bandwidth-diagram.json", "bollinger_bandwidth"),
        ("ohlc-to-adx-14-diagram.json", "adx"),
        ("ohlc-to-obv-diagram.json", "obv"),
    ],
)
def test_demo_file_diagrams_execute_against_reference_ta_pulser(filename: str, indicator_name: str):
    """
    Exercise the test_demo_file_diagrams_execute_against_reference_ta_pulser
    regression scenario.
    """
    root = _repo_root()
    fixture = _load_json(root / "attas" / "examples" / "pulses" / "technical_analysis_test_data.json")
    phema = _load_json(root / "demos" / "files" / "diagrams" / filename)
    ta_pulser = PathPulser(config=str(root / "attas" / "configs" / "ta.pulser"), auto_register=False)
    calls = []
    captured_indicator_input = {}

    def fake_post(url, json=None, timeout=None):
        """Handle fake post."""
        assert url == "http://127.0.0.1:8011/api/pulsers/test"
        assert isinstance(json, dict)
        pulse_name = json["pulse_name"]
        calls.append(pulse_name)

        if pulse_name == "ohlc_bar_series":
            assert json["pulser_name"] == "YFinancePulser"
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

        assert pulse_name == indicator_name
        assert json["pulser_name"] == "TechnicalAnalysisPulser"
        captured_indicator_input.clear()
        captured_indicator_input.update(dict(json["input"]))
        return FakeResponse(
            {
                "status": "success",
                "result": ta_pulser.get_pulse_data(dict(json["input"]), pulse_name=indicator_name),
            }
        )

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

    indicator_title = next(
        node["title"]
        for node in phema["meta"]["map_phemar"]["diagram"]["nodes"]
        if node.get("pulseName") == indicator_name
    )
    expected_output = ta_pulser.get_pulse_data(dict(captured_indicator_input), pulse_name=indicator_name)

    assert calls == ["ohlc_bar_series", indicator_name]
    assert captured_indicator_input["ohlc_series"] == fixture["ohlc_series"]
    assert result["status"] == "success"
    assert result["output"] == expected_output
    assert [step["title"] for step in result["steps"]] == ["Input", "OHLC Bars", indicator_title, "Output"]
