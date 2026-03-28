import json
import os
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from attas.pulsers.yfinance_pulser import DEFAULT_SUPPORTED_PULSES, YFinancePulser
from prompits.agents.standby import StandbyAgent
from prompits.tests.test_support import build_agent_from_config


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeSeries(dict):
    @property
    def index(self):
        return list(self.keys())

    @property
    def values(self):
        return list(self.values())


class _FakeLoc:
    def __init__(self, rows):
        self.rows = rows

    def __getitem__(self, key):
        return FakeSeries(self.rows[key])


class FakeStatementFrame:
    def __init__(self, rows):
        self.rows = {row: dict(values) for row, values in rows.items()}
        self.index = list(self.rows.keys())
        self.columns = list(next(iter(self.rows.values())).keys()) if self.rows else []
        self.empty = not self.rows
        self.loc = _FakeLoc(self.rows)


def test_yfinance_pulser_maps_snapshot_into_supported_pulses(monkeypatch):
    snapshot = {
        "symbol": "AAPL",
        "last_price": 214.37,
        "previous_close": 212.80,
        "open_price": 213.10,
        "market_state": "REGULAR",
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
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="market_state") == {
        "symbol": "AAPL",
        "market_state": "REGULAR",
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


def test_yfinance_pulser_exposes_ohlc_bar_series(monkeypatch):
    def fake_load_ohlc_bar_series(self, symbol, *, interval, start_date, end_date):
        return {
            "symbol": symbol,
            "interval": interval,
            "start_date": start_date,
            "end_date": end_date,
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

    monkeypatch.setattr(YFinancePulser, "_load_ohlc_bar_series", fake_load_ohlc_bar_series)

    pulser = YFinancePulser(auto_register=False)
    pulse = pulser.resolve_pulse_definition(pulse_name="ohlc_bar_series")

    assert pulse["pulse_address"] == "ai.attas.finance.price.ohlc_bar_series"
    assert pulse["input_schema"]["required"] == ["symbol", "interval", "start_date", "end_date"]

    assert pulser.get_pulse_data(
        {
            "symbol": "AAPL",
            "interval": "1d",
            "start_date": "2025-01-01T00:00:00Z",
            "end_date": "2025-01-02T00:00:00Z",
        },
        pulse_name="ohlc_bar_series",
    ) == {
        "symbol": "AAPL",
        "interval": "1d",
        "start_date": "2025-01-01T00:00:00Z",
        "end_date": "2025-01-02T00:00:00Z",
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


def test_yfinance_pulser_maps_income_statement_pulses(monkeypatch):
    def fake_income_statement_snapshot(self, symbol, period_type):
        base = {
            "symbol": symbol,
            "currency": "USD",
            "revenue": 391000000000.0,
            "revenue_year_over_year_growth_percent": 6.1,
            "gross_profit": 180700000000.0,
            "gross_margin_percent": 46.2,
            "gross_profit_year_over_year_growth_percent": 8.4,
            "operating_income": 124300000000.0,
            "operating_margin_percent": 31.8,
            "operating_income_year_over_year_growth_percent": 9.7,
            "net_income": 94680000000.0,
            "net_margin_percent": 24.2,
            "net_income_year_over_year_growth_percent": 11.2,
            "eps_basic": 6.52,
            "eps_diluted": 6.47,
            "eps_diluted_year_over_year_growth_percent": 10.9,
        }
        base["period_end"] = "2025-12-31"
        base["period_type"] = period_type
        return base

    monkeypatch.setattr(
        YFinancePulser,
        "_load_latest_income_statement_snapshot",
        fake_income_statement_snapshot,
    )

    pulser = YFinancePulser(auto_register=False)

    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="income_statement_revenue") == {
        "symbol": "AAPL",
        "period_end": "2025-12-31",
        "period_type": "annual",
        "revenue": 391000000000.0,
        "currency": "USD",
        "year_over_year_growth_percent": 6.1,
    }
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="income_statement_gross_profit") == {
        "symbol": "AAPL",
        "period_end": "2025-12-31",
        "period_type": "annual",
        "gross_profit": 180700000000.0,
        "gross_margin_percent": 46.2,
        "currency": "USD",
        "year_over_year_growth_percent": 8.4,
    }
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="income_statement_operating_income") == {
        "symbol": "AAPL",
        "period_end": "2025-12-31",
        "period_type": "annual",
        "operating_income": 124300000000.0,
        "operating_margin_percent": 31.8,
        "currency": "USD",
        "year_over_year_growth_percent": 9.7,
    }
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="income_statement_net_income") == {
        "symbol": "AAPL",
        "period_end": "2025-12-31",
        "period_type": "annual",
        "net_income": 94680000000.0,
        "net_margin_percent": 24.2,
        "currency": "USD",
        "year_over_year_growth_percent": 11.2,
    }
    assert pulser.get_pulse_data({"symbol": "AAPL"}, pulse_name="income_statement_eps") == {
        "symbol": "AAPL",
        "period_end": "2025-12-31",
        "period_type": "quarterly",
        "eps_basic": 6.52,
        "eps_diluted": 6.47,
        "currency": "USD",
        "year_over_year_growth_percent": 10.9,
    }


def test_yfinance_pulser_extracts_income_statement_snapshot_from_frames(monkeypatch):
    annual_frame = FakeStatementFrame(
        {
            "Total Revenue": {
                date(2024, 12, 31): 400.0,
                date(2023, 12, 31): 360.0,
            },
            "Gross Profit": {
                date(2024, 12, 31): 160.0,
                date(2023, 12, 31): 140.0,
            },
            "Operating Income": {
                date(2024, 12, 31): 120.0,
                date(2023, 12, 31): 100.0,
            },
            "Net Income": {
                date(2024, 12, 31): 95.0,
                date(2023, 12, 31): 80.0,
            },
        }
    )
    quarterly_frame = FakeStatementFrame(
        {
            "Basic EPS": {
                date(2024, 12, 31): 2.35,
                date(2024, 9, 30): 2.20,
                date(2024, 6, 30): 2.10,
                date(2024, 3, 31): 2.00,
                date(2023, 12, 31): 2.05,
            },
            "Diluted EPS": {
                date(2024, 12, 31): 2.30,
                date(2024, 9, 30): 2.15,
                date(2024, 6, 30): 2.05,
                date(2024, 3, 31): 1.95,
                date(2023, 12, 31): 2.00,
            },
        }
    )

    class FakeYFinanceModule:
        @staticmethod
        def Ticker(_symbol):
            return object()

    monkeypatch.setattr("attas.pulsers.yfinance_pulser.yf", FakeYFinanceModule)
    monkeypatch.setattr(
        YFinancePulser,
        "_get_income_statement_frame",
        lambda self, ticker, symbol, period_type: quarterly_frame if period_type == "quarterly" else annual_frame,
    )
    monkeypatch.setattr(
        YFinancePulser,
        "_get_ticker_info",
        lambda self, ticker, symbol: {"financialCurrency": "USD"},
    )

    pulser = YFinancePulser(auto_register=False)

    annual = pulser._load_latest_income_statement_snapshot("AAPL", period_type="annual")
    assert annual["period_end"] == "2024-12-31"
    assert annual["period_type"] == "annual"
    assert annual["revenue"] == 400.0
    assert annual["gross_profit"] == 160.0
    assert annual["gross_margin_percent"] == 40.0
    assert round(annual["revenue_year_over_year_growth_percent"], 4) == 11.1111
    assert round(annual["operating_income_year_over_year_growth_percent"], 4) == 20.0
    assert annual["currency"] == "USD"

    quarterly = pulser._load_latest_income_statement_snapshot("AAPL", period_type="quarterly")
    assert quarterly["period_end"] == "2024-12-31"
    assert quarterly["period_type"] == "quarterly"
    assert quarterly["eps_basic"] == 2.35
    assert quarterly["eps_diluted"] == 2.3
    assert round(quarterly["eps_diluted_year_over_year_growth_percent"], 4) == 15.0
    assert quarterly["currency"] == "USD"


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
    assert len(agent.supported_pulses) == len(DEFAULT_SUPPORTED_PULSES)
    assert sent_payloads[0]["url"] == "http://127.0.0.1:8011/register"
    assert sent_payloads[0]["payload"]["pit_type"] == "Pulser"
    assert len(sent_payloads[0]["payload"]["pulse_pulser_pairs"]) == len(DEFAULT_SUPPORTED_PULSES)

    practice_by_id = {entry["id"]: entry for entry in agent.agent_card["practices"]}
    assert "get_pulse_data" in practice_by_id

    last_price_pulse = next(pulse for pulse in agent.supported_pulses if pulse["name"] == "last_price")
    income_statement_revenue = next(
        pulse for pulse in agent.supported_pulses if pulse["name"] == "income_statement_revenue"
    )
    revenue_pair = next(
        entry for entry in sent_payloads[0]["payload"]["pulse_pulser_pairs"]
        if entry["pulse_name"] == "income_statement_revenue"
    )
    assert last_price_pulse["mapping"]["last_price"] == "last_price"
    assert last_price_pulse["output_schema"]["properties"]["last_price"]["type"] == "number"
    assert income_statement_revenue["pulse_address"] == "ffcb1f67-ddbc-5706-903f-73915f91f04a"
    assert revenue_pair["pulse_id"] == "urn:plaza:pulse:income.statement.revenue"
    assert any(pulse["name"] == "market_state" for pulse in agent.supported_pulses)
    assert any(pulse["name"] == "income_statement_eps" for pulse in agent.supported_pulses)
    assert any(pulse["name"] == "valuation_multiples" for pulse in agent.supported_pulses)


def test_yfinance_config_declares_supported_pulses():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "yfinance.pulser"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert "supported_pulses" in config
    assert len(config["supported_pulses"]) == len(DEFAULT_SUPPORTED_PULSES)
    assert [pulse["name"] for pulse in config["supported_pulses"]] == [
        pulse["name"] for pulse in DEFAULT_SUPPORTED_PULSES
    ]
    assert any(pulse["name"] == "income_statement_revenue" for pulse in config["supported_pulses"])
    assert any(pulse["name"] == "income_statement_eps" for pulse in config["supported_pulses"])
    assert any(pulse["name"] == "market_state" for pulse in config["supported_pulses"])


def test_yfinance_supported_pulses_cover_snapshot_fields(monkeypatch):
    monkeypatch.setattr(
        YFinancePulser,
        "_get_ticker_fast_info",
        lambda self, ticker, symbol: {
            "currency": "USD",
            "exchange": "NMS",
            "marketState": "REGULAR",
            "lastPrice": 214.37,
            "previousClose": 212.80,
            "open": 213.10,
            "dayHigh": 215.00,
            "dayLow": 211.95,
            "lastVolume": 51420000,
            "threeMonthAverageVolume": 60250000,
            "tenDayAverageVolume": 58840000,
            "marketCap": 3280000000000,
            "yearLow": 164.08,
            "yearHigh": 237.23,
        },
    )
    monkeypatch.setattr(
        YFinancePulser,
        "_get_ticker_info",
        lambda self, ticker, symbol: {
            "bid": 214.30,
            "ask": 214.45,
            "bidSize": 8,
            "askSize": 9,
            "sharesOutstanding": 15300000000,
            "floatShares": 15200000000,
            "trailingPE": 33.1,
            "forwardPE": 29.4,
            "pegRatio": 2.1,
            "priceToSalesTrailing12Months": 8.2,
            "priceToBook": 45.7,
            "enterpriseToRevenue": 7.5,
            "enterpriseToEbitda": 24.3,
            "grossMargins": 0.462,
            "operatingMargins": 0.318,
            "ebitdaMargins": 0.336,
            "profitMargins": 0.241,
            "returnOnAssets": 0.287,
            "returnOnEquity": 1.52,
            "currentRatio": 1.1,
            "quickRatio": 0.95,
            "debtToEquity": 173.5,
            "totalCash": 67150000000,
            "totalDebt": 109300000000,
            "operatingCashflow": 110500000000,
            "freeCashflow": 99500000000,
            "ebitda": 131500000000,
            "enterpriseValue": 3350000000000,
            "totalRevenue": 391000000000,
            "revenueGrowth": 0.061,
            "earningsGrowth": 0.112,
            "earningsQuarterlyGrowth": 0.098,
            "trailingEps": 6.47,
            "forwardEps": 7.28,
            "targetHighPrice": 250.0,
            "targetLowPrice": 190.0,
            "targetMeanPrice": 228.4,
            "targetMedianPrice": 230.0,
            "recommendationMean": 2.0,
            "recommendationKey": "buy",
            "numberOfAnalystOpinions": 41,
            "dividendRate": 1.0,
            "dividendYield": 0.0047,
            "payoutRatio": 0.154,
            "fiveYearAvgDividendYield": 0.0062,
            "exDividendDate": 1707436800,
            "fiftyDayAverage": 221.4,
            "twoHundredDayAverage": 205.6,
            "beta": 1.21,
            "52WeekChange": 0.152,
            "SandP52WeekChange": 0.103,
            "shortName": "Apple Inc.",
            "longName": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "country": "United States",
            "website": "https://www.apple.com",
        },
    )

    pulser = YFinancePulser(auto_register=False)
    snapshot = pulser._load_ticker_snapshot("AAPL")
    mapped_fields = {
        str(rule)
        for pulse in pulser.supported_pulses
        for rule in (pulse.get("mapping") or {}).values()
        if isinstance(rule, str)
    }

    uncovered = sorted(set(snapshot) - mapped_fields - {"symbol", "source"})

    assert uncovered == []


def test_yfinance_config_keeps_first_pulse_stable():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "yfinance.pulser"
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert "supported_pulses" in payload
    assert len(payload["supported_pulses"]) == len(DEFAULT_SUPPORTED_PULSES)
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
