import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from attas.pulsers.yfinance_pulser import YFinancePulser
from prompits.agents.standby import StandbyAgent
from prompits.tests.test_support import build_agent_from_config


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def test_yfinance_pulser_maps_snapshot_into_supported_pulses(monkeypatch):
    snapshot = {
        "symbol": "AAPL",
        "last_price": 214.37,
        "previous_close": 212.80,
        "open_price": 213.10,
        "day_high": 215.00,
        "day_low": 211.95,
        "volume": 51420000,
        "average_daily_volume_10d": 58840000,
        "average_daily_volume_30d": 60250000,
        "currency": "USD",
        "market_cap": 3280000000000,
        "shares_outstanding": 15300000000,
        "float_shares": 15200000000,
        "trailing_pe": 33.1,
        "forward_pe": 29.4,
        "price_to_sales": 8.2,
        "price_to_book": 45.7,
        "gross_margin": 0.462,
        "operating_margin": 0.318,
        "profit_margin": 0.241,
        "return_on_equity": 1.52,
        "current_ratio": 1.1,
        "quick_ratio": 0.95,
        "debt_to_equity": 173.5,
        "total_cash": 67150000000,
        "total_debt": 109300000000,
        "operating_cashflow": 110500000000,
        "free_cashflow": 99500000000,
        "total_revenue": 391000000000,
        "revenue_growth": 0.061,
        "earnings_growth": 0.112,
        "trailing_eps": 6.47,
        "forward_eps": 7.28,
        "target_mean_price": 228.4,
        "target_median_price": 230.0,
        "recommendation_mean": 2.0,
        "dividend_rate": 1.0,
        "dividend_yield": 0.0047,
        "payout_ratio": 0.154,
        "fifty_two_week_low": 164.08,
        "fifty_two_week_high": 237.23,
        "fifty_day_average": 221.4,
        "two_hundred_day_average": 205.6,
        "beta": 1.21,
        "recommendation_key": "buy",
        "number_of_analyst_opinions": 41,
        "short_name": "Apple Inc.",
        "long_name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "country": "United States",
        "website": "https://www.apple.com",
        "source": "yfinance",
    }

    monkeypatch.setattr(
        YFinancePulser,
        "_load_ticker_snapshot",
        lambda self, symbol: dict(snapshot, symbol=symbol),
    )

    pulser = YFinancePulser(auto_register=False)

    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="last_price") == {
        "symbol": "AAPL",
        "last_price": 214.37,
        "currency": "USD",
        "source": "yfinance",
    }
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="previous_close") == {
        "symbol": "AAPL",
        "previous_close": 212.80,
        "currency": "USD",
        "source": "yfinance",
    }
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="open_price") == {
        "symbol": "AAPL",
        "open_price": 213.10,
        "currency": "USD",
        "source": "yfinance",
    }
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="day_high_low") == {
        "symbol": "AAPL",
        "day_high": 215.00,
        "day_low": 211.95,
        "currency": "USD",
        "source": "yfinance",
    }
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="trade_volume") == {
        "symbol": "AAPL",
        "volume": 51420000,
        "average_daily_volume_10d": 58840000,
        "average_daily_volume_30d": 60250000,
        "source": "yfinance",
    }
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="market_cap") == {
        "symbol": "AAPL",
        "market_cap": 3280000000000,
        "shares_outstanding": 15300000000,
        "float_shares": 15200000000,
        "source": "yfinance",
    }
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="valuation_multiples") == {
        "symbol": "AAPL",
        "trailing_pe": 33.1,
        "forward_pe": 29.4,
        "price_to_sales": 8.2,
        "price_to_book": 45.7,
        "source": "yfinance",
    }
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="profitability_metrics") == {
        "symbol": "AAPL",
        "gross_margin": 0.462,
        "operating_margin": 0.318,
        "profit_margin": 0.241,
        "return_on_equity": 1.52,
        "source": "yfinance",
    }
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="company_profile") == {
        "symbol": "AAPL",
        "short_name": "Apple Inc.",
        "long_name": "Apple Inc.",
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "country": "United States",
        "website": "https://www.apple.com",
        "currency": "USD",
        "source": "yfinance",
    }


def test_yfinance_pulser_returns_error_when_symbol_missing():
    pulser = YFinancePulser(auto_register=False)

    assert pulser.get_pulse_data({}, pulse_name="last_price") == {
        "error": "symbol is required"
    }


def test_yfinance_pulser_agent_config_loads_via_shared_agent_factory():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "yfinance.pulser"
    sent_payloads = []

    def fake_post(url, json=None, timeout=5, **kwargs):
        sent_payloads.append({"url": url, "payload": dict(json or {}), "timeout": timeout})
        return FakeResponse(
            {
                "status": "registered",
                "token": "yfinance-token",
                "expires_in": 3600,
                "agent_id": "yfinance-pulser-id",
                "api_key": "yfinance-pulser-key",
            }
        )

    with patch("prompits.agents.base.requests.post", side_effect=fake_post), patch(
        "prompits.agents.base.requests.get",
        return_value=FakeResponse([], status_code=200),
    ):
        agent = build_agent_from_config(str(config_path))

    assert agent.name == "YFinancePulser"
    assert isinstance(agent, StandbyAgent)
    assert agent.port == 8020
    assert agent.agent_id == "yfinance-pulser-id"
    assert len(agent.supported_pulses) == 18
    assert sent_payloads[0]["url"] == "http://127.0.0.1:8011/register"
    assert sent_payloads[0]["payload"]["pit_type"] == "Pulser"
    assert len(sent_payloads[0]["payload"]["pulse_pulser_pairs"]) == 18

    practice_by_id = {entry["id"]: entry for entry in agent.agent_card["practices"]}
    assert "get_pulse_data" in practice_by_id

    last_price_pulse = next(pulse for pulse in agent.supported_pulses if pulse["name"] == "last_price")
    assert last_price_pulse["mapping"]["last_price"] == "last_price"
    assert last_price_pulse["output_schema"]["properties"]["last_price"]["type"] == "number"
    assert any(pulse["name"] == "valuation_multiples" for pulse in agent.supported_pulses)


def test_yfinance_config_declares_supported_pulses():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "yfinance.pulser"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert "supported_pulses" in config
    assert len(config["supported_pulses"]) == 18
    assert any(pulse["name"] == "last_price" for pulse in config["supported_pulses"])


def test_yfinance_config_declares_supported_pulses():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "yfinance.pulser"
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert "supported_pulses" in payload
    assert len(payload["supported_pulses"]) == 18
    assert payload["supported_pulses"][0]["name"] == "last_price"


def test_yfinance_pulser_has_dedicated_ui_and_test_endpoint(tmp_path, monkeypatch):
    pool_dir = tmp_path / "storage"
    config_path = tmp_path / "demo_yfinance.agent"
    config_path.write_text(
        json.dumps(
            {
                "name": "DemoYFinancePulser",
                "type": "attas.pulsers.yfinance_pulser.YFinancePulser",
                "host": "127.0.0.1",
                "port": 8125,
                "description": "Demo yfinance pulser",
                "tags": ["finance", "market-data"],
                "supported_pulses": [
                    {
                        "name": "last_price",
                        "description": "Latest traded price",
                        "pulse_address": "plaza://pulse/last_price",
                        "input_schema": {
                            "type": "object",
                            "properties": {"symbol": {"type": "string"}},
                            "required": ["symbol"],
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "symbol": {"type": "string"},
                                "last_price": {"type": "number"},
                                "currency": {"type": "string"},
                            },
                        },
                        "mapping": {
                            "symbol": "symbol",
                            "last_price": "last_price",
                            "currency": "currency",
                        },
                        "test_data": {"symbol": "MSFT"},
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

    monkeypatch.setattr(
        YFinancePulser,
        "_load_ticker_snapshot",
        lambda self, symbol: {
            "symbol": symbol,
            "last_price": 401.25,
            "currency": "USD",
            "source": "yfinance",
        },
    )

    agent = build_agent_from_config(str(config_path))

    with TestClient(agent.app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "DemoYFinancePulser Config" in root.text
        assert "Search Supported Pulses" in root.text
        assert "APIPulser Details" in root.text
        assert "Pulse Details" in root.text
        assert "Pulse Test Data JSON" in root.text
        assert "Test Runner" in root.text
        assert "Quick Quote Presets" in root.text
        assert "Yahoo Finance" in root.text
        assert '<div id="config-preview" class="json-tree-shell"></div>' in root.text
        assert '<div id="test-runner-result" class="json-tree-shell result"></div>' in root.text
        assert '<div id="test-last-params" class="json-tree-shell compact"></div>' in root.text

        current = client.get("/api/config")
        assert current.status_code == 200
        payload = current.json()["config"]
        assert payload["name"] == "DemoYFinancePulser"
        assert payload["supported_pulses"][0]["test_data"]["symbol"] == "MSFT"

        payload["description"] = "Updated yfinance pulser"
        payload["supported_pulses"][0]["test_data"] = {"symbol": "NVDA"}

        saved = client.post("/api/config", json={"config": payload})
        assert saved.status_code == 200
        saved_payload = saved.json()["config"]
        assert saved_payload["description"] == "Updated yfinance pulser"
        assert saved_payload["supported_pulses"][0]["test_data"]["symbol"] == "NVDA"

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
        assert tested_payload["result"]["last_price"] == 401.25
        assert tested_payload["result"]["symbol"] == "AAPL"
        assert tested_payload["debug"]["pulse_definition"]["name"] == "last_price"
        assert tested_payload["debug"]["raw_payload"]["currency"] == "USD"
        assert tested_payload["debug"]["fetch"]["provider"] == "yfinance"

    written = json.loads(config_path.read_text(encoding="utf-8"))
    assert written["description"] == "Updated yfinance pulser"
    assert written["supported_pulses"][0]["test_data"]["symbol"] == "NVDA"
