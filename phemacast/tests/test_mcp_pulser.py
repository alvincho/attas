"""
Regression tests for MCP Pulser.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_mcp_pulser_renders_connection_and_tool_arguments`,
`test_alpha_vantage_api_and_mcp_configs_keep_supported_pulse_names_in_sync`,
`test_alpha_vantage_mcp_config_exposes_all_shared_financial_statement_pulses`, and
`test_alpha_vantage_mcp_config_uses_tool_call_wrapper_and_shared_pulses`, helping guard
against regressions as the packages evolve.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.pulsers.mcp_pulser import MCPPulser


class FakeAsyncHttpResponse:
    """Response model for fake async HTTP payloads."""
    def __init__(self, payload=None, *, status_code=200, headers=None, text=None):
        """Initialize the fake async HTTP response."""
        self._payload = payload
        self.status_code = status_code
        self.headers = dict(headers or {})
        if text is None and payload is not None:
            text = json.dumps(payload)
        self.text = text or ""
        self.content = self.text.encode("utf-8") if self.text else b""

    def raise_for_status(self):
        """Return the raise for the status."""
        if self.status_code >= 400:
            raise Exception(self.text or f"HTTP {self.status_code}")

    def json(self):
        """Handle JSON for the fake async HTTP response."""
        if self._payload is not None:
            return self._payload
        return json.loads(self.text)


class FakeAsyncHttpClient:
    """Represent a fake async HTTP client."""
    def __init__(self, capture, responses, **kwargs):
        """Initialize the fake async HTTP client."""
        self.capture = capture
        self.responses = list(responses)
        self.kwargs = kwargs

    async def __aenter__(self):
        """Handle aenter for the fake async HTTP client."""
        self.capture["client_kwargs"] = dict(self.kwargs)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Handle aexit for the fake async HTTP client."""
        return False

    async def post(self, url, json=None, headers=None):
        """Post the value."""
        self.capture.setdefault("requests", []).append(
            {
                "url": url,
                "json": json,
                "headers": dict(headers or {}),
            }
        )
        return self.responses.pop(0)


def test_mcp_pulser_renders_connection_and_tool_arguments(monkeypatch):
    """
    Exercise the test_mcp_pulser_renders_connection_and_tool_arguments regression
    scenario.
    """
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
        """Handle fake call."""
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
    """
    Exercise the test_mcp_pulser_applies_root_path_before_mapping regression
    scenario.
    """
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
    """
    Exercise the test_mcp_pulser_http_transport_initializes_session_and_calls_tool
    regression scenario.
    """
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
    """
    Exercise the
    test_mcp_pulser_falls_back_to_text_content_when_structured_content_is_empty
    regression scenario.
    """
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
    """
    Exercise the
    test_mcp_pulser_returns_clear_error_when_registry_api_key_is_missing regression
    scenario.
    """
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


def test_mcp_pulser_http_transport_supports_configurable_initialize_params(monkeypatch):
    """
    Exercise the
    test_mcp_pulser_http_transport_supports_configurable_initialize_params
    regression scenario.
    """
    capture = {}
    responses = [
        FakeAsyncHttpResponse(
            {
                "jsonrpc": "2.0",
                "id": "init-1",
                "result": {
                    "protocolVersion": "2024-10-07",
                    "capabilities": {},
                    "serverInfo": {"name": "search", "version": "1.0.0"},
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
                    "structuredContent": {"status": "ok"},
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
            "name": "ConfigurableRemoteMCPPulser",
            "mcp": {
                "transport": "http",
                "url": "https://example.test/mcp",
                "protocol_version": "2024-10-07",
                "client_info": {
                    "name": "finmas-web-search",
                    "version": "2.0.0",
                },
                "capabilities": {
                    "tools": {"listChanged": True},
                },
            },
            "supported_pulses": [
                {
                    "name": "ping",
                    "pulse_address": "plaza://pulse/ping",
                    "mcp": {
                        "tool": "search",
                        "arguments": {"query": "{query}"},
                    },
                    "mapping": {
                        "query": "_input.query",
                    },
                }
            ],
        },
        auto_register=False,
    )

    result = pulser.get_pulse_data({"query": "inflation"}, pulse_name="ping")

    assert capture["requests"][0]["json"]["params"] == {
        "protocolVersion": "2024-10-07",
        "capabilities": {
            "tools": {"listChanged": True},
        },
        "clientInfo": {
            "name": "finmas-web-search",
            "version": "2.0.0",
        },
    }
    assert result == {"query": "inflation"}


def test_mcp_pulser_normalizes_search_results_into_stable_research_sources(monkeypatch):
    """
    Exercise the
    test_mcp_pulser_normalizes_search_results_into_stable_research_sources
    regression scenario.
    """
    pulser = MCPPulser(
        config={
            "name": "WebSearchMCPPulser",
            "supported_pulses": [
                {
                    "name": "research_sources",
                    "pulse_address": "plaza://pulse/research_sources",
                    "mcp": {
                        "tool": "search",
                        "arguments": {"query": "{query}"},
                        "response_normalization": {"kind": "research_sources"},
                    },
                    "mapping": {
                        "query": "_input.query",
                        "number_of_sources": "_input.number_of_sources",
                        "sources": {
                            "source": "sources",
                            "limit_from": "_input.number_of_sources",
                            "items": {
                                "id": "id",
                                "title": "title",
                                "url": "url",
                                "source_domain": "source_domain",
                                "snippet": "snippet",
                                "published_at": "published_at",
                                "citation.id": "citation.id",
                                "citation.title": "citation.title",
                                "citation.url": "citation.url",
                                "citation.source_domain": "citation.source_domain",
                                "citation.published_at": "citation.published_at",
                            },
                        },
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
            "structuredContent": {
                "results": [
                    {
                        "id": "doc-1",
                        "title": "NVIDIA launches new chips",
                        "url": "https://www.example.com/nvidia-chips",
                        "text": "NVIDIA launched a new family of AI chips built for data centers.",
                        "metadata": {
                            "published_at": "2026-04-01T12:00:00Z",
                        },
                    }
                ]
            },
            "isError": False,
        },
    )

    result = pulser.get_pulse_data(
        {"query": "NVIDIA AI chips", "number_of_sources": 1},
        pulse_name="research_sources",
    )

    assert result == {
        "query": "NVIDIA AI chips",
        "number_of_sources": 1,
        "sources": [
            {
                "id": "doc-1",
                "title": "NVIDIA launches new chips",
                "url": "https://www.example.com/nvidia-chips",
                "source_domain": "example.com",
                "snippet": "NVIDIA launched a new family of AI chips built for data centers.",
                "published_at": "2026-04-01T12:00:00Z",
                "citation": {
                    "id": "doc-1",
                    "title": "NVIDIA launches new chips",
                    "url": "https://www.example.com/nvidia-chips",
                    "source_domain": "example.com",
                    "published_at": "2026-04-01T12:00:00Z",
                },
            }
        ],
    }


def test_mcp_pulser_normalizes_fetch_documents_into_stable_research_source_shape(monkeypatch):
    """
    Exercise the
    test_mcp_pulser_normalizes_fetch_documents_into_stable_research_source_shape
    regression scenario.
    """
    pulser = MCPPulser(
        config={
            "name": "WebFetchMCPPulser",
            "supported_pulses": [
                {
                    "name": "research_source_document",
                    "pulse_address": "plaza://pulse/research_source_document",
                    "mcp": {
                        "tool": "fetch",
                        "arguments": {"id": "{id}"},
                        "response_normalization": {"kind": "research_sources"},
                    },
                    "mapping": {
                        "query": "_input.query",
                        "id": "id",
                        "title": "title",
                        "url": "url",
                        "source_domain": "source_domain",
                        "snippet": "snippet",
                        "published_at": "published_at",
                        "text": "text",
                        "citation.id": "citation.id",
                        "citation.title": "citation.title",
                        "citation.url": "citation.url",
                        "citation.source_domain": "citation.source_domain",
                        "citation.published_at": "citation.published_at",
                        "citation.locator": "citation.locator",
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
            "structuredContent": {
                "id": "doc-2",
                "title": "Acme earnings call",
                "url": "https://research.example.net/acme-q1",
                "text": "Acme said revenue grew 20% and margins improved materially.",
                "metadata": {
                    "excerpt": "Revenue grew 20% and margins improved materially.",
                    "publishedAt": "2026-03-31T08:30:00Z",
                    "locator": {"paragraph": 3},
                },
            },
            "isError": False,
        },
    )

    result = pulser.get_pulse_data(
        {"id": "doc-2", "query": "Acme earnings"},
        pulse_name="research_source_document",
    )

    assert result == {
        "query": "Acme earnings",
        "id": "doc-2",
        "title": "Acme earnings call",
        "url": "https://research.example.net/acme-q1",
        "source_domain": "research.example.net",
        "snippet": "Revenue grew 20% and margins improved materially.",
        "published_at": "2026-03-31T08:30:00Z",
        "text": "Acme said revenue grew 20% and margins improved materially.",
        "citation": {
            "id": "doc-2",
            "title": "Acme earnings call",
            "url": "https://research.example.net/acme-q1",
            "source_domain": "research.example.net",
            "published_at": "2026-03-31T08:30:00Z",
            "locator": {"paragraph": 3},
        },
    }


def test_web_search_mcp_config_uses_generic_search_tool_and_research_normalization():
    """
    Exercise the
    test_web_search_mcp_config_uses_generic_search_tool_and_research_normalization
    regression scenario.
    """
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "web_search_mcp.pulser"

    pulser = MCPPulser(config=str(config_path), auto_register=False)
    pulse = pulser.config["supported_pulses"][0]

    assert pulser.config["mcp"]["transport"] == "http"
    assert pulser.config["mcp"]["url"] == "env:WEB_SEARCH_MCP_URL"
    assert pulser.config["mcp"]["headers"]["Authorization"] == "env:WEB_SEARCH_MCP_AUTHORIZATION"
    assert pulse["name"] == "research_sources"
    assert pulse["mcp"]["tool"] == "search"
    assert pulse["mcp"]["response_normalization"]["kind"] == "research_sources"
    assert pulse["mapping"]["sources"]["source"] == "sources"
    assert pulse["mapping"]["sources"]["limit_from"] == "_input.number_of_sources"


def test_web_fetch_mcp_config_uses_generic_fetch_tool_and_research_normalization():
    """
    Exercise the
    test_web_fetch_mcp_config_uses_generic_fetch_tool_and_research_normalization
    regression scenario.
    """
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "web_fetch_mcp.pulser"

    pulser = MCPPulser(config=str(config_path), auto_register=False)
    pulse = pulser.config["supported_pulses"][0]

    assert pulser.config["mcp"]["transport"] == "http"
    assert pulser.config["mcp"]["url"] == "env:WEB_FETCH_MCP_URL"
    assert pulser.config["mcp"]["headers"]["Authorization"] == "env:WEB_FETCH_MCP_AUTHORIZATION"
    assert pulse["name"] == "research_source_document"
    assert pulse["mcp"]["tool"] == "fetch"
    assert pulse["mcp"]["response_normalization"]["kind"] == "research_sources"
    assert pulse["mcp"]["arguments"] == {"id": "{id}"}


def test_notion_mcp_config_exposes_search_create_and_update_pulses():
    """
    Exercise the
    test_notion_mcp_config_exposes_search_create_and_update_pulses
    regression scenario.
    """
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "notion_mcp.pulser"

    pulser = MCPPulser(config=str(config_path), auto_register=False)
    pulse_tools = {
        pulse["name"]: pulse["mcp"]["tool"]
        for pulse in pulser.config["supported_pulses"]
    }
    search_pages = next(pulse for pulse in pulser.config["supported_pulses"] if pulse["name"] == "search_pages")
    create_pages = next(pulse for pulse in pulser.config["supported_pulses"] if pulse["name"] == "create_pages")
    update_page = next(pulse for pulse in pulser.config["supported_pulses"] if pulse["name"] == "update_page")

    assert pulser.config["mcp"]["transport"] == "http"
    assert pulser.config["mcp"]["url"] == "https://mcp.notion.com/mcp"
    assert pulser.config["mcp"]["headers"]["Authorization"] == "env:NOTION_MCP_AUTHORIZATION"
    assert pulse_tools == {
        "search_pages": "notion-search",
        "fetch_page": "notion-fetch",
        "create_pages": "notion-create-pages",
        "update_page": "notion-update-page",
    }
    assert search_pages["mcp"]["response_normalization"]["kind"] == "research_sources"
    assert create_pages["mcp"]["arguments"] == {
        "parent": "{parent}",
        "pages": "{pages}",
    }
    assert update_page["mcp"]["arguments"] == {
        "page_id": "{page_id}",
        "content": "{content}",
        "properties": "{properties}",
    }


def test_alpha_vantage_mcp_config_uses_tool_call_wrapper_and_shared_pulses():
    """
    Exercise the
    test_alpha_vantage_mcp_config_uses_tool_call_wrapper_and_shared_pulses
    regression scenario.
    """
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
    """
    Exercise the
    test_alpha_vantage_mcp_config_exposes_all_shared_financial_statement_pulses
    regression scenario.
    """
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
    """
    Exercise the
    test_alpha_vantage_api_and_mcp_configs_keep_supported_pulse_names_in_sync
    regression scenario.
    """
    api_config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "alpha_vantage.pulser"
    mcp_config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "alpha_vantage_mcp.pulser"

    api_config = json.loads(api_config_path.read_text(encoding="utf-8"))
    mcp_config = json.loads(mcp_config_path.read_text(encoding="utf-8"))

    assert [pulse["name"] for pulse in api_config["supported_pulses"]] == [
        pulse["name"] for pulse in mcp_config["supported_pulses"]
    ]
