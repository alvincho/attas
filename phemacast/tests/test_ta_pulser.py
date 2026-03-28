import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.pulsers.path_pulser import PathPulser


class FakePostResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")

    def json(self):
        return self._payload


def test_ta_pulser_config_exposes_seeded_indicator_catalog():
    root = Path(__file__).resolve().parents[2]
    config_path = root / "attas" / "configs" / "ta.pulser"
    seed_path = root / "attas" / "init_pits" / "init_pulse_technical_analysis.json"
    test_data_path = root / "attas" / "examples" / "pulses" / "technical_analysis_test_data.json"

    pulser = PathPulser(config=str(config_path), auto_register=False)

    with seed_path.open("r", encoding="utf-8") as fh:
        seeded_pulses = json.load(fh)["data"]
    with test_data_path.open("r", encoding="utf-8") as fh:
        payload = json.load(fh)

    assert len(pulser.supported_pulses) == len(seeded_pulses)
    assert {pulse["name"] for pulse in pulser.supported_pulses} == {pulse["name"] for pulse in seeded_pulses}
    assert all(pulse["completion_status"] == "complete" for pulse in pulser.supported_pulses)

    sma_pulse = next(pulse for pulse in pulser.supported_pulses if pulse["name"] == "sma")
    assert sma_pulse["pulse_id"] == "ai.attas.finance.technical.sma"
    assert sma_pulse["pulse_address"] == "ai.attas.finance.technical.sma"
    assert sma_pulse["output_schema"]["properties"]["values"]["type"] == "array"
    assert "start_date" in sma_pulse["input_schema"]["properties"]
    assert "end_date" in sma_pulse["input_schema"]["properties"]
    assert "ohlc_series" not in sma_pulse["input_schema"]["required"]
    assert sma_pulse["steps"][0]["name"] == "load_ohlc_series"

    sma_result = pulser.get_pulse_data(dict(payload), pulse_name="sma")
    assert len(sma_result["values"]) == 141
    assert sma_result["values"][0]["timestamp"] == "2025-01-20T00:00:00Z"
    assert sma_result["values"][-1]["timestamp"] == payload["timestamp"]
    assert sma_result["values"][-1]["value"] == pytest.approx(196.97250000000116)

    macd_histogram = pulser.get_pulse_data(dict(payload), pulse_name="macd_histogram")
    assert len(macd_histogram["values"]) == 127
    assert macd_histogram["values"][0]["timestamp"] == "2025-02-03T00:00:00Z"
    assert macd_histogram["values"][-1]["value"] == pytest.approx(-0.22301471726332078)

    mfi = pulser.get_pulse_data(dict(payload), pulse_name="mfi")
    assert len(mfi["values"]) == 146
    assert mfi["values"][0]["timestamp"] == "2025-01-15T00:00:00Z"
    assert mfi["values"][-1]["value"] == pytest.approx(93.07996192477944)

    adx = pulser.get_pulse_data(dict(payload), pulse_name="adx")
    assert len(adx["values"]) == 133
    assert adx["values"][0]["timestamp"] == "2025-01-28T00:00:00Z"
    assert adx["values"][-1]["value"] == pytest.approx(20.677955530927488)

    obv = pulser.get_pulse_data(dict(payload), pulse_name="obv")
    assert len(obv["values"]) == len(payload["ohlc_series"])
    assert obv["values"][0]["timestamp"] == "2025-01-01T00:00:00Z"
    assert obv["values"][0]["value"] == pytest.approx(0.0)
    assert obv["values"][-1]["value"] == pytest.approx(315634610.0)

    chaikin_oscillator = pulser.get_pulse_data(dict(payload), pulse_name="chaikin_oscillator")
    assert len(chaikin_oscillator["values"]) == 151
    assert chaikin_oscillator["values"][0]["timestamp"] == "2025-01-10T00:00:00Z"
    assert chaikin_oscillator["values"][-1]["value"] == pytest.approx(-180517.23973703012)

    with TestClient(pulser.app) as client:
        current = client.get("/api/config")
        assert current.status_code == 200
        editor_config = current.json()["config"]
        assert len(editor_config["supported_pulses"]) == len(seeded_pulses)
        assert all(isinstance(pulse.get("resolved_test_data"), dict) for pulse in editor_config["supported_pulses"])
        sma_editor_pulse = next(pulse for pulse in editor_config["supported_pulses"] if pulse["name"] == "sma")
        assert sma_editor_pulse["test_data_path"] == "../examples/pulses/technical_analysis_test_data.json"
        assert sma_editor_pulse["resolved_test_data"]["start_date"] == payload["start_date"]
        assert sma_editor_pulse["resolved_test_data"]["end_date"] == payload["end_date"]
        assert sma_editor_pulse["resolved_test_data"]["interval"] == payload["interval"]
        assert sma_editor_pulse["resolved_test_data"]["timestamp"] == payload["timestamp"]


def test_ta_pulser_fetches_ohlc_series_from_upstream_when_date_range_is_provided(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    config_path = root / "attas" / "configs" / "ta.pulser"
    test_data_path = root / "attas" / "examples" / "pulses" / "technical_analysis_test_data.json"

    payload = json.loads(test_data_path.read_text(encoding="utf-8"))
    captured = []

    def fake_post(url, json=None, timeout=30):
        captured.append({"url": url, "json": json, "timeout": timeout})
        assert json["content"]["pulse_name"] == "ohlc_bar_series"
        return FakePostResponse(
            {
                "symbol": payload["symbol"],
                "interval": payload["interval"],
                "start_date": payload["start_date"],
                "end_date": payload["end_date"],
                "ohlc_series": payload["ohlc_series"],
                "source": "yfinance",
            }
        )

    monkeypatch.setattr("phemacast.pulsers.path_pulser.requests.post", fake_post)

    pulser = PathPulser(config=str(config_path), auto_register=False)
    result = pulser.get_pulse_data(
        {
            "symbol": payload["symbol"],
            "interval": payload["interval"],
            "start_date": payload["start_date"],
            "end_date": payload["end_date"],
            "window": 20,
        },
        pulse_name="sma",
    )

    assert len(captured) == 1
    assert captured[0]["url"] == "http://127.0.0.1:8020/use_practice/get_pulse_data"
    assert result["values"][0]["timestamp"] == "2025-01-20T00:00:00Z"
    assert result["values"][-1]["timestamp"] == payload["timestamp"]
    assert result["values"][-1]["value"] == pytest.approx(196.97250000000116)
