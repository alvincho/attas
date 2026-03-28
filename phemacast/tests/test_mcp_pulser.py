import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.pulsers.mcp_pulser import MCPPulser


class FakeAsyncHttpResponse:
    def __init__(self, payload=None, *, status_code=200, headers=None, text=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = dict(headers or {})
        if text is None and payload is not None:
            text = json.dumps(payload)
        self.text = text or ""
        self.content = self.text.encode("utf-8") if self.text else b""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(self.text or f"HTTP {self.status_code}")

    def json(self):
        if self._payload is not None:
            return self._payload
        return json.loads(self.text)


class FakeAsyncHttpClient:
    def __init__(self, capture, responses, **kwargs):
        self.capture = capture
        self.responses = list(responses)
        self.kwargs = kwargs

    async def __aenter__(self):
        self.capture["client_kwargs"] = dict(self.kwargs)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None, headers=None):
        self.capture.setdefault("requests", []).append(
            {
                "url": url,
                "json": json,
                "headers": dict(headers or {}),
            }
        )
        return self.responses.pop(0)


def test_mcp_pulser_renders_connection_and_tool_arguments(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "runtime-secret")
    capture = {}

    pulser = MCPPulser(
        config={
            "name": "AlphaVantageMCPPulser",
            "api_keys": [
                {
                    "id": "alpha_vantage",
                    "env": "ALPHA_VANTAGE_API_KEY",
                }
            ],
            "mcp": {
                "transport": "http",
                "url": "https://example.test/mcp?apikey={api_key}",
                "api_key_id": "alpha_vantage",
            },
            "supported_pulses": [
                {
                    "name": "last_price",
                    "pulse_address": "plaza://pulse/last_price",
                    "mcp": {
                        "tool": "TOOL_CALL",
                        "arguments": {
                            "tool_name": "GLOBAL_QUOTE",
                            "arguments": {
                                "symbol": "{symbol}",
                            },
                        },
                    },
                    "mapping": {
                        "symbol": "Global Quote.01. symbol",
                        "last_price": "Global Quote.05. price",
                        "source": {"value": "alpha_vantage"},
                    },
                }
            ],
        },
        auto_register=False,
    )

    def fake_call(config, tool_name, arguments):
        capture["config"] = config
        capture["tool_name"] = tool_name
        capture["arguments"] = arguments
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "Global Quote": {
                                "01. symbol": "IBM",
                                "05. price": "214.37",
                            }
                        }
                    ),
                }
            ],
            "isError": False,
        }

    monkeypatch.setattr(pulser, "_call_mcp_tool_sync", fake_call)

    result = pulser.get_pulse_data({"symbol": "IBM"}, pulse_name="last_price")

    assert capture["config"]["url"] == "https://example.test/mcp?apikey=runtime-secret"
    assert capture["tool_name"] == "TOOL_CALL"
    assert capture["arguments"] == {
        "tool_name": "GLOBAL_QUOTE",
        "arguments": {"symbol": "IBM"},
    }
    assert result == {
        "symbol": "IBM",
        "last_price": "214.37",
        "source": "alpha_vantage",
    }


def test_mcp_pulser_applies_root_path_before_mapping(monkeypatch):
    pulser = MCPPulser(
        config={
            "name": "HistoricalMCPPulser",
            "mcp": {
                "transport": "http",
                "url": "https://example.test/mcp?apikey=demo",
            },
            "supported_pulses": [
                {
                    "name": "daily_ohlcv_bar",
                    "pulse_address": "013ddac1-46e1-58b6-a2fc-7373c1d21ca0",
                    "mcp": {
                        "tool": "TOOL_CALL",
                        "arguments": {
                            "tool_name": "TIME_SERIES_DAILY_ADJUSTED",
                            "arguments": {
                                "symbol": "{symbol}",
                                "outputsize": "full",
                            },
                        },
                        "root_path": "Time Series (Daily).{trade_date}",
                    },
                    "mapping": {
                        "symbol": "_input.symbol",
                        "trade_date": "_input.trade_date",
                        "open": "1. open",
                        "close": "4. close",
                    },
                }
            ],
        },
        auto_register=False,
    )

    monkeypatch.setattr(
        pulser,
        "_call_mcp_tool_sync",
        lambda *_args, **_kwargs: {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "Time Series (Daily)": {
                                "2024-12-31": {
                                    "1. open": "100.0",
                                    "4. close": "101.4",
                                }
                            }
                        }
                    ),
                }
            ],
            "isError": False,
        },
    )

    result = pulser.get_pulse_data(
        {"symbol": "IBM", "trade_date": "2024-12-31"},
        pulse_name="daily_ohlcv_bar",
    )

    assert result == {
        "symbol": "IBM",
        "trade_date": "2024-12-31",
        "open": "100.0",
        "close": "101.4",
    }


def test_mcp_pulser_http_transport_initializes_session_and_calls_tool(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "runtime-secret")
    capture = {}
    responses = [
        FakeAsyncHttpResponse(
            {
                "jsonrpc": "2.0",
                "id": "init-1",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {"name": "alphavantage", "version": "1.0.0"},
                },
            },
            headers={"mcp-session-id": "session-123", "content-type": "application/json"},
        ),
        FakeAsyncHttpResponse(status_code=202, headers={"content-type": "application/json"}, text=""),
        FakeAsyncHttpResponse(
            {
                "jsonrpc": "2.0",
                "id": "call-1",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "Global Quote": {
                                        "01. symbol": "IBM",
                                        "05. price": "214.37",
                                    }
                                }
                            ),
                        }
                    ],
                    "isError": False,
                },
            },
            headers={"content-type": "application/json"},
        ),
    ]

    monkeypatch.setattr(
        "phemacast.pulsers.mcp_pulser.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncHttpClient(capture, responses, **kwargs),
    )

    pulser = MCPPulser(
        config={
            "name": "AlphaVantageRemoteMCPPulser",
            "api_keys": [
                {
                    "id": "alpha_vantage",
                    "env": "ALPHA_VANTAGE_API_KEY",
                }
            ],
            "mcp": {
                "transport": "http",
                "url": "https://mcp.alphavantage.co/mcp?apikey={api_key}",
                "api_key_id": "alpha_vantage",
            },
            "supported_pulses": [
                {
                    "name": "last_price",
                    "pulse_address": "plaza://pulse/last_price",
                    "mcp": {
                        "tool": "TOOL_CALL",
                        "arguments": {
                            "tool_name": "GLOBAL_QUOTE",
                            "arguments": {
                                "symbol": "{symbol}",
                            },
                        },
                    },
                    "mapping": {
                        "symbol": "Global Quote.01. symbol",
                        "last_price": "Global Quote.05. price",
                        "source": {"value": "alpha_vantage"},
                    },
                }
            ],
        },
        auto_register=False,
    )

    result = pulser.get_pulse_data({"symbol": "IBM"}, pulse_name="last_price")

    assert capture["client_kwargs"]["headers"]["Accept"] == "application/json, text/event-stream"
    assert capture["requests"][0]["url"] == "https://mcp.alphavantage.co/mcp?apikey=runtime-secret"
    assert capture["requests"][0]["json"]["method"] == "initialize"
    assert capture["requests"][1]["json"]["method"] == "notifications/initialized"
    assert capture["requests"][1]["headers"]["mcp-session-id"] == "session-123"
    assert capture["requests"][2]["json"]["method"] == "tools/call"
    assert capture["requests"][2]["headers"]["mcp-session-id"] == "session-123"
    assert capture["requests"][2]["json"]["params"] == {
        "name": "TOOL_CALL",
        "arguments": {
            "tool_name": "GLOBAL_QUOTE",
            "arguments": {"symbol": "IBM"},
        },
    }
    assert result == {
        "symbol": "IBM",
        "last_price": "214.37",
        "source": "alpha_vantage",
    }


def test_mcp_pulser_falls_back_to_text_content_when_structured_content_is_empty(monkeypatch):
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "runtime-secret")
    capture = {}
    responses = [
        FakeAsyncHttpResponse(
            {
                "jsonrpc": "2.0",
                "id": "init-1",
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "serverInfo": {"name": "alphavantage", "version": "1.0.0"},
                },
            },
            headers={"mcp-session-id": "session-123", "content-type": "application/json"},
        ),
        FakeAsyncHttpResponse(status_code=202, headers={"content-type": "application/json"}, text=""),
        FakeAsyncHttpResponse(
            {
                "jsonrpc": "2.0",
                "id": "call-1",
                "result": {
                    "structuredContent": {},
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "Symbol": "IBM",
                                    "Name": "International Business Machines",
                                    "Sector": "TECHNOLOGY",
                                    "Industry": "INFORMATION TECHNOLOGY SERVICES",
                                    "Country": "USA",
                                    "OfficialSite": "https://www.ibm.com",
                                }
                            ),
                        }
                    ],
                    "isError": False,
                },
            },
            headers={"content-type": "application/json"},
        ),
    ]

    monkeypatch.setattr(
        "phemacast.pulsers.mcp_pulser.httpx.AsyncClient",
        lambda **kwargs: FakeAsyncHttpClient(capture, responses, **kwargs),
    )

    pulser = MCPPulser(
        config={
            "name": "AlphaVantageRemoteMCPPulser",
            "api_keys": [
                {
                    "id": "alpha_vantage",
                    "env": "ALPHA_VANTAGE_API_KEY",
                }
            ],
            "mcp": {
                "transport": "http",
                "url": "https://mcp.alphavantage.co/mcp?apikey={api_key}",
                "api_key_id": "alpha_vantage",
            },
            "supported_pulses": [
                {
                    "name": "company_profile",
                    "pulse_address": "plaza://pulse/company_profile",
                    "mcp": {
                        "tool": "TOOL_CALL",
                        "arguments": {
                            "tool_name": "COMPANY_OVERVIEW",
                            "arguments": {
                                "symbol": "{symbol}",
                            },
                        },
                    },
                    "mapping": {
                        "symbol": "Symbol",
                        "company_name": "Name",
                        "sector": "Sector",
                        "industry": "Industry",
                        "headquarters_country": "Country",
                        "website": "OfficialSite",
                    },
                }
            ],
        },
        auto_register=False,
    )

    result = pulser.get_pulse_data({"symbol": "IBM"}, pulse_name="company_profile")

    assert result == {
        "symbol": "IBM",
        "company_name": "International Business Machines",
        "sector": "TECHNOLOGY",
        "industry": "INFORMATION TECHNOLOGY SERVICES",
        "headquarters_country": "USA",
        "website": "https://www.ibm.com",
    }


def test_mcp_pulser_returns_clear_error_when_registry_api_key_is_missing(monkeypatch):
    monkeypatch.delenv("ALPHA_VANTAGE_API_KEY", raising=False)

    pulser = MCPPulser(
        config={
            "name": "MissingRegistryMCPPulser",
            "api_keys": [
                {"id": "alpha_vantage", "env": "ALPHA_VANTAGE_API_KEY"},
            ],
            "mcp": {
                "transport": "http",
                "url": "https://mcp.alphavantage.co/mcp?apikey={api_key}",
                "api_key_id": "alpha_vantage",
            },
            "supported_pulses": [
                {
                    "name": "company_profile",
                    "pulse_address": "plaza://pulse/company_profile",
                    "mcp": {
                        "tool": "TOOL_CALL",
                        "arguments": {
                            "tool_name": "COMPANY_OVERVIEW",
                            "arguments": {"symbol": "{symbol}"},
                        },
                    },
                }
            ],
        },
        auto_register=False,
    )

    payload = pulser.fetch_pulse_payload("company_profile", {"symbol": "IBM"}, pulser.supported_pulses[0])

    assert payload == {"error": "Missing API key value for registry 'alpha_vantage' (ALPHA_VANTAGE_API_KEY)"}


def test_alpha_vantage_mcp_config_uses_tool_call_wrapper_and_shared_pulses():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "alpha_vantage_mcp.pulser"

    pulser = MCPPulser(config=str(config_path), auto_register=False)

    assert pulser.config["mcp"]["transport"] == "http"
    assert pulser.config["mcp"]["url"] == "https://mcp.alphavantage.co/mcp?apikey={api_key}"
    assert pulser.config["api_keys"][0]["id"] == "alpha_vantage"
    assert len(pulser.supported_pulses) >= 10
    assert any(pulse["name"] == "news_article" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "income_statement_revenue" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "cash_flow_free_cash_flow" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "balance_sheet_strength" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "market_cap" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "valuation_multiples" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "profitability_metrics" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "revenue_and_growth" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "eps_metrics" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "dividend_profile" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "beta_and_volatility" for pulse in pulser.supported_pulses)
    assert all("api" not in pulse for pulse in pulser.config["supported_pulses"])
    assert all(pulse["mcp"]["tool"] == "TOOL_CALL" for pulse in pulser.config["supported_pulses"])
    assert all("output_schema" not in pulse for pulse in pulser.config["supported_pulses"])
    assert all(len(str(pulse["pulse_address"])) == 36 for pulse in pulser.config["supported_pulses"])

    company_profile = next(pulse for pulse in pulser.config["supported_pulses"] if pulse["name"] == "company_profile")
    assert company_profile["mcp"]["arguments"]["tool_name"] == "COMPANY_OVERVIEW"


def test_alpha_vantage_mcp_config_exposes_all_shared_financial_statement_pulses():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "alpha_vantage_mcp.pulser"

    pulser = MCPPulser(config=str(config_path), auto_register=False)
    statement_names = {
        pulse["name"]
        for pulse in pulser.config["supported_pulses"]
        if pulse["name"].startswith(("income_statement_", "balance_sheet_", "cash_flow_"))
    }

    assert {
        "income_statement_revenue",
        "income_statement_gross_profit",
        "income_statement_operating_income",
        "income_statement_net_income",
        "income_statement_eps",
        "balance_sheet_cash",
        "balance_sheet_total_assets",
        "balance_sheet_total_debt",
        "balance_sheet_shareholder_equity",
        "balance_sheet_strength",
        "cash_flow_operating_cash_flow",
        "cash_flow_capex",
        "cash_flow_free_cash_flow",
    } <= statement_names


def test_alpha_vantage_api_and_mcp_configs_keep_supported_pulse_names_in_sync():
    api_config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "alpha_vantage.pulser"
    mcp_config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "alpha_vantage_mcp.pulser"

    api_config = json.loads(api_config_path.read_text(encoding="utf-8"))
    mcp_config = json.loads(mcp_config_path.read_text(encoding="utf-8"))

    assert [pulse["name"] for pulse in api_config["supported_pulses"]] == [
        pulse["name"] for pulse in mcp_config["supported_pulses"]
    ]
