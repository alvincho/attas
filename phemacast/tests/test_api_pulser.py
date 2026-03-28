import os
import socket
import sys
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.pulsers.api_pulser import ApiPulser


class FakeHttpResponse:
    def __init__(self, payload=None):
        self._payload = payload if payload is not None else {"price": 214.37}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeHttpClient:
    def __init__(self, capture, payload=None):
        self.capture = capture
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def request(self, method, url, headers=None):
        self.capture["method"] = method
        self.capture["url"] = url
        self.capture["headers"] = dict(headers or {})
        return FakeHttpResponse(self.payload)


def test_api_pulser_resolves_api_key_from_environment(monkeypatch):
    capture = {}
    monkeypatch.setenv("DEMO_MARKET_KEY", "secret-from-env")
    monkeypatch.setattr(
        "phemacast.pulsers.api_pulser.httpx.Client",
        lambda timeout=10.0: FakeHttpClient(capture),
    )

    pulser = ApiPulser(
        config={
            "name": "EnvApiPulser",
            "description": "Resolves env-backed secrets",
            "api_key": {"env": "DEMO_MARKET_KEY"},
            "supported_pulses": [
                {
                    "name": "last_price",
                    "pulse_address": "plaza://pulse/last_price",
                    "api": {
                        "url": "https://example.test/quote/{symbol}",
                        "method": "GET",
                        "api_key_header": "x-api-key",
                    },
                    "mapping": {"last_price": "price"},
                }
            ],
        },
        auto_register=False,
    )

    payload = pulser.fetch_pulse_payload(
        "last_price",
        {"symbol": "AAPL"},
        pulser.supported_pulses[0],
    )

    assert payload == {"price": 214.37}
    assert capture["method"] == "GET"
    assert capture["url"] == "https://example.test/quote/AAPL"
    assert capture["headers"]["x-api-key"] == "secret-from-env"


def test_api_pulser_resolves_api_key_from_pulser_registry_by_id(monkeypatch):
    capture = {}
    monkeypatch.setenv("MARKET_REGISTRY_KEY", "registry-secret")
    monkeypatch.setattr(
        "phemacast.pulsers.api_pulser.httpx.Client",
        lambda timeout=10.0: FakeHttpClient(capture),
    )

    pulser = ApiPulser(
        config={
            "name": "RegistryApiPulser",
            "api_keys": [
                {"id": "market", "env": "MARKET_REGISTRY_KEY", "header": "x-api-key"},
                {"id": "news", "value": "news-secret", "header": "Authorization", "prefix": "Token "},
            ],
            "supported_pulses": [
                {
                    "name": "snapshot",
                    "pulse_address": "plaza://pulse/snapshot",
                    "api": {
                        "url": "https://example.test/snapshot/{symbol}",
                        "method": "GET",
                        "api_key_id": "market",
                    },
                }
            ],
        },
        auto_register=False,
    )

    pulser.fetch_pulse_payload("snapshot", {"symbol": "MSFT"}, pulser.supported_pulses[0])

    assert capture["headers"]["x-api-key"] == "registry-secret"


def test_api_pulser_resolves_api_key_from_pulser_registry_to_query_param(monkeypatch):
    capture = {}
    monkeypatch.setattr(
        "phemacast.pulsers.api_pulser.httpx.Client",
        lambda timeout=10.0: FakeHttpClient(capture),
    )

    pulser = ApiPulser(
        config={
            "name": "RegistryQueryParamPulser",
            "api_keys": [
                {"id": "alpha", "value": "query-secret", "param": "apikey"},
            ],
            "supported_pulses": [
                {
                    "name": "quote",
                    "pulse_address": "plaza://pulse/quote",
                    "api": {
                        "url": "https://example.test/query?function=GLOBAL_QUOTE&symbol={symbol}",
                        "method": "GET",
                        "api_key_id": "alpha",
                    },
                }
            ],
        },
        auto_register=False,
    )

    pulser.fetch_pulse_payload("quote", {"symbol": "IBM"}, pulser.supported_pulses[0])

    assert capture["url"] == "https://example.test/query?function=GLOBAL_QUOTE&symbol=IBM&apikey=query-secret"
    assert "Authorization" not in capture["headers"]


def test_api_pulser_returns_clear_error_when_registry_api_key_is_missing(monkeypatch):
    monkeypatch.delenv("FINNHUB_API_KEY", raising=False)

    pulser = ApiPulser(
        config={
            "name": "MissingRegistryApiKeyPulser",
            "api_keys": [
                {"id": "finnhub", "env": "FINNHUB_API_KEY", "param": "token"},
            ],
            "supported_pulses": [
                {
                    "name": "company_profile",
                    "pulse_address": "plaza://pulse/company_profile",
                    "api": {
                        "url": "https://finnhub.io/api/v1/stock/profile2?symbol={symbol}",
                        "method": "GET",
                        "api_key_id": "finnhub",
                    },
                }
            ],
        },
        auto_register=False,
    )

    payload = pulser.fetch_pulse_payload("company_profile", {"symbol": "IBM"}, pulser.supported_pulses[0])

    assert payload == {"error": "Missing API key value for registry 'finnhub' (FINNHUB_API_KEY)"}


def test_api_pulser_returns_clear_error_when_dns_resolution_fails(monkeypatch):
    monkeypatch.setattr(
        "phemacast.pulsers.api_pulser.httpx.Client",
        lambda timeout=10.0: (_ for _ in ()).throw(socket.gaierror(8, "nodename nor servname provided, or not known")),
    )

    pulser = ApiPulser(
        config={
            "name": "DnsFailurePulser",
            "api_keys": [
                {"id": "finnhub", "value": "demo-token", "param": "token"},
            ],
            "supported_pulses": [
                {
                    "name": "company_profile",
                    "pulse_address": "plaza://pulse/company_profile",
                    "api": {
                        "url": "https://finnhub.io/api/v1/stock/profile2?symbol={symbol}",
                        "method": "GET",
                        "api_key_id": "finnhub",
                    },
                }
            ],
        },
        auto_register=False,
    )

    payload = pulser.fetch_pulse_payload("company_profile", {"symbol": "IBM"}, pulser.supported_pulses[0])

    assert payload == {"error": "DNS resolution failed for the upstream API host. Outbound internet/DNS may be unavailable."}


def test_api_pulser_prefers_pulse_level_literal_api_key(monkeypatch):
    capture = {}
    monkeypatch.setenv("DEMO_MARKET_KEY", "secret-from-env")
    monkeypatch.setattr(
        "phemacast.pulsers.api_pulser.httpx.Client",
        lambda timeout=10.0: FakeHttpClient(capture),
    )

    pulser = ApiPulser(
        config={
            "name": "LiteralApiPulser",
            "api_key": {"env": "DEMO_MARKET_KEY"},
            "supported_pulses": [
                {
                    "name": "news",
                    "pulse_address": "plaza://pulse/news",
                    "api": {
                        "url": "https://example.test/news",
                        "method": "GET",
                        "api_key": "literal-override-key",
                    },
                }
            ],
        },
        auto_register=False,
    )

    pulser.fetch_pulse_payload("news", {}, pulser.supported_pulses[0])

    assert capture["headers"]["Authorization"] == "Bearer literal-override-key"


def test_api_pulser_root_path_supports_templates_and_keeps_input(monkeypatch):
    capture = {}
    payload = {
        "Time Series (Daily)": {
            "2024-12-31": {
                "1. open": "100.0",
                "2. high": "102.0",
                "3. low": "99.5",
                "4. close": "101.4",
                "5. adjusted close": "101.2",
                "6. volume": "123456",
            }
        }
    }
    monkeypatch.setattr(
        "phemacast.pulsers.api_pulser.httpx.Client",
        lambda timeout=10.0: FakeHttpClient(capture, payload),
    )

    pulser = ApiPulser(
        config={
            "name": "HistoricalApiPulser",
            "supported_pulses": [
                {
                    "name": "daily_ohlcv_bar",
                    "pulse_address": "013ddac1-46e1-58b6-a2fc-7373c1d21ca0",
                    "api": {
                        "url": "https://example.test/query?function=TIME_SERIES_DAILY_ADJUSTED&symbol={symbol}",
                        "method": "GET",
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

    payload = pulser.get_pulse_data({"symbol": "IBM", "trade_date": "2024-12-31"}, pulse_name="daily_ohlcv_bar")

    assert payload == {
        "symbol": "IBM",
        "trade_date": "2024-12-31",
        "open": "100.0",
        "close": "101.4",
    }


def test_api_pulser_supports_arithmetic_mapping_after_root_path(monkeypatch):
    capture = {}
    payload = {
        "annualReports": [
            {
                "fiscalDateEnding": "2024-12-31",
                "reportedCurrency": "USD",
                "operatingCashflow": "1000",
                "capitalExpenditures": "-200",
            }
        ]
    }
    monkeypatch.setattr(
        "phemacast.pulsers.api_pulser.httpx.Client",
        lambda timeout=10.0: FakeHttpClient(capture, payload),
    )

    pulser = ApiPulser(
        config={
            "name": "FinancialStatementApiPulser",
            "supported_pulses": [
                {
                    "name": "cash_flow_free_cash_flow",
                    "pulse_address": "3856dcb9-8be9-56d3-bd78-38f4865586f9",
                    "api": {
                        "url": "https://example.test/query?function=CASH_FLOW&symbol={symbol}",
                        "method": "GET",
                        "root_path": "annualReports.0",
                    },
                    "mapping": {
                        "symbol": "_input.symbol",
                        "period_end": "fiscalDateEnding",
                        "period_type": {"value": "annual"},
                        "free_cash_flow": {
                            "op": "subtract_abs",
                            "args": ["operatingCashflow", "capitalExpenditures"],
                        },
                        "currency": "reportedCurrency",
                    },
                }
            ],
        },
        auto_register=False,
    )

    result = pulser.get_pulse_data({"symbol": "IBM"}, pulse_name="cash_flow_free_cash_flow")

    assert result == {
        "symbol": "IBM",
        "period_end": "2024-12-31",
        "period_type": "annual",
        "free_cash_flow": 800.0,
        "currency": "USD",
    }


def test_api_pulser_supports_collection_mapping_from_dict_payload(monkeypatch):
    capture = {}
    payload = {
        "feed": [
            {
                "title": "IBM wins new contract",
                "time_published": "2026-03-23T01:00:00Z",
                "source": "Newswire",
                "summary": "A large enterprise contract.",
                "url": "https://example.test/ibm-1",
                "overall_sentiment_label": "Positive",
            },
            {
                "title": "IBM expands cloud offering",
                "time_published": "2026-03-23T00:00:00Z",
                "source": "MarketWatch",
                "summary": "Cloud offering update.",
                "url": "https://example.test/ibm-2",
                "overall_sentiment_label": "Neutral",
            },
        ]
    }
    monkeypatch.setattr(
        "phemacast.pulsers.api_pulser.httpx.Client",
        lambda timeout=10.0: FakeHttpClient(capture, payload),
    )

    pulser = ApiPulser(
        config={
            "name": "NewsCollectionPulser",
            "supported_pulses": [
                {
                    "name": "news_article",
                    "pulse_address": "plaza://pulse/news_article",
                    "api": {
                        "url": "https://example.test/news?symbol={symbol}&limit={number_of_articles}",
                        "method": "GET",
                    },
                    "mapping": {
                        "symbol": "_input.symbol",
                        "number_of_articles": "_input.number_of_articles",
                        "articles": {
                            "source": "feed",
                            "items": {
                                "headline": "title",
                                "published_at": "time_published",
                                "publisher": "source",
                                "summary": "summary",
                                "url": "url",
                                "sentiment_label": "overall_sentiment_label",
                            },
                        },
                    },
                }
            ],
        },
        auto_register=False,
    )

    result = pulser.get_pulse_data({"symbol": "IBM", "number_of_articles": 2}, pulse_name="news_article")

    assert result["symbol"] == "IBM"
    assert result["number_of_articles"] == 2
    assert len(result["articles"]) == 2
    assert result["articles"][0]["headline"] == "IBM wins new contract"


def test_api_pulser_supports_collection_mapping_from_list_payload(monkeypatch):
    capture = {}
    payload = [
        {
            "headline": "Apple launches new service",
            "datetime": "2026-03-23T01:00:00Z",
            "source": "Reuters",
            "summary": "Service launch summary.",
            "url": "https://example.test/aapl-1",
        },
        {
            "headline": "Apple supplier ramps production",
            "datetime": "2026-03-23T00:00:00Z",
            "source": "Bloomberg",
            "summary": "Supply chain update.",
            "url": "https://example.test/aapl-2",
        },
    ]
    monkeypatch.setattr(
        "phemacast.pulsers.api_pulser.httpx.Client",
        lambda timeout=10.0: FakeHttpClient(capture, payload),
    )

    pulser = ApiPulser(
        config={
            "name": "ListNewsCollectionPulser",
            "supported_pulses": [
                {
                    "name": "news_article",
                    "pulse_address": "plaza://pulse/news_article",
                    "api": {
                        "url": "https://example.test/company-news?symbol={symbol}",
                        "method": "GET",
                    },
                    "mapping": {
                        "symbol": "_input.symbol",
                        "number_of_articles": "_input.number_of_articles",
                        "articles": {
                            "source": "items",
                            "items": {
                                "headline": "headline",
                                "published_at": "datetime",
                                "publisher": "source",
                                "summary": "summary",
                                "url": "url",
                            },
                        },
                    },
                }
            ],
        },
        auto_register=False,
    )

    result = pulser.get_pulse_data({"symbol": "AAPL", "number_of_articles": 2}, pulse_name="news_article")

    assert result["symbol"] == "AAPL"
    assert result["number_of_articles"] == 2
    assert len(result["articles"]) == 2
    assert result["articles"][0]["publisher"] == "Reuters"


def test_api_pulser_collection_mapping_respects_requested_article_limit(monkeypatch):
    capture = {}
    payload = {
        "feed": [
            {
                "title": f"Headline {index}",
                "time_published": f"2026-03-23T{index:02d}:00:00Z",
                "source": "Example News",
                "summary": f"Summary {index}",
                "url": f"https://example.test/{index}",
            }
            for index in range(50)
        ]
    }
    monkeypatch.setattr(
        "phemacast.pulsers.api_pulser.httpx.Client",
        lambda timeout=10.0: FakeHttpClient(capture, payload),
    )

    pulser = ApiPulser(
        config={
            "name": "LimitedNewsCollectionPulser",
            "supported_pulses": [
                {
                    "name": "news_article",
                    "pulse_address": "plaza://pulse/news_article",
                    "output_schema": {
                        "type": "object",
                        "properties": {
                            "symbol": {"type": "string"},
                            "number_of_articles": {"type": "integer"},
                            "articles": {"type": "array"},
                        },
                    },
                    "api": {
                        "url": "https://example.test/news?symbol={symbol}&limit={number_of_articles}",
                        "method": "GET",
                    },
                    "mapping": {
                        "symbol": "_input.symbol",
                        "number_of_articles": "_input.number_of_articles",
                        "articles": {
                            "source": "feed",
                            "limit_from": "_input.number_of_articles",
                            "items": {
                                "headline": "title",
                                "published_at": "time_published",
                                "publisher": "source",
                                "summary": "summary",
                                "url": "url",
                            },
                        },
                    },
                }
            ],
        },
        auto_register=False,
    )

    result = pulser.get_pulse_data({"symbol": "IBM", "number_of_articles": 10}, pulse_name="news_article")

    assert result["number_of_articles"] == 10
    assert len(result["articles"]) == 10
    assert result["articles"][0]["headline"] == "Headline 0"
    assert result["articles"][-1]["headline"] == "Headline 9"


def test_alpha_vantage_config_uses_registry_query_param_and_defines_multiple_pulses():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "alpha_vantage.pulser"

    pulser = ApiPulser(config=str(config_path), auto_register=False)

    assert pulser.config["api_keys"][0]["id"] == "alpha_vantage"
    assert pulser.config["api_keys"][0]["param"] == "apikey"
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
    assert all("apikey=demo" not in pulse["api"]["url"] for pulse in pulser.supported_pulses)
    assert all("output_schema" not in pulse for pulse in pulser.config["supported_pulses"])
    assert all(len(str(pulse["pulse_address"])) == 36 for pulse in pulser.config["supported_pulses"])


def test_alpha_vantage_overview_config_exposes_grouped_overview_metrics():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "alpha_vantage.pulser"

    pulser = ApiPulser(config=str(config_path), auto_register=False)
    overview_pulses = [
        pulse for pulse in pulser.config["supported_pulses"]
        if "function=OVERVIEW" in pulse.get("api", {}).get("url", "")
    ]

    overview_names = {pulse["name"] for pulse in overview_pulses}
    assert {
        "market_cap",
        "valuation_multiples",
        "profitability_metrics",
        "revenue_and_growth",
        "eps_metrics",
        "dividend_profile",
        "beta_and_volatility",
    } <= overview_names

    mapped_fields = {
        str(rule)
        for pulse in overview_pulses
        for rule in (pulse.get("mapping") or {}).values()
        if isinstance(rule, str)
    }
    assert {
        "MarketCapitalization",
        "SharesOutstanding",
        "TrailingPE",
        "ForwardPE",
        "PEGRatio",
        "PriceToSalesRatioTTM",
        "PriceToBookRatio",
        "EVToRevenue",
        "EVToEBITDA",
        "OperatingMarginTTM",
        "ProfitMargin",
        "ReturnOnAssetsTTM",
        "ReturnOnEquityTTM",
        "RevenueTTM",
        "QuarterlyRevenueGrowthYOY",
        "QuarterlyEarningsGrowthYOY",
        "DilutedEPSTTM",
        "AnalystTargetPrice",
        "DividendPerShare",
        "DividendYield",
        "ExDividendDate",
        "Beta",
    } <= mapped_fields


def test_alpha_vantage_config_exposes_all_shared_financial_statement_pulses():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "alpha_vantage.pulser"

    pulser = ApiPulser(config=str(config_path), auto_register=False)
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


def test_finnhub_config_uses_registry_query_param_and_defines_shared_pulses():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "finnhub.pulser"

    pulser = ApiPulser(config=str(config_path), auto_register=False)

    assert pulser.config["api_keys"][0]["id"] == "finnhub"
    assert pulser.config["api_keys"][0]["param"] == "token"
    assert len(pulser.supported_pulses) >= 10
    assert any(pulse["name"] == "news_article" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "earnings_event" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "market_cap" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "valuation_multiples" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "profitability_metrics" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "beta_and_volatility" for pulse in pulser.supported_pulses)
    assert all("output_schema" not in pulse for pulse in pulser.config["supported_pulses"])
    assert all(len(str(pulse["pulse_address"])) == 36 for pulse in pulser.config["supported_pulses"])


def test_finnhub_config_exposes_grouped_profile_and_metric_fields():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "finnhub.pulser"

    pulser = ApiPulser(config=str(config_path), auto_register=False)
    grouped_pulses = [
        pulse for pulse in pulser.config["supported_pulses"]
        if pulse["name"] in {"market_cap", "valuation_multiples", "profitability_metrics", "beta_and_volatility"}
    ]

    grouped_names = {pulse["name"] for pulse in grouped_pulses}
    assert {"market_cap", "valuation_multiples", "profitability_metrics", "beta_and_volatility"} <= grouped_names

    mapped_fields = {
        str(rule)
        for pulse in grouped_pulses
        for rule in (pulse.get("mapping") or {}).values()
        if isinstance(rule, str)
    }
    assert {
        "marketCapitalization",
        "shareOutstanding",
        "metric.peBasicExclExtraTTM",
        "metric.grossMarginAnnual",
        "metric.operatingMarginAnnual",
        "metric.netMarginAnnual",
        "metric.roeTTM",
        "metric.roaTTM",
        "metric.beta",
    } <= mapped_fields


def test_marketstack_config_uses_registry_query_param_and_defines_shared_pulses():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "market_stack.pulser"

    pulser = ApiPulser(config=str(config_path), auto_register=False)

    assert pulser.config["api_keys"][0]["id"] == "marketstack"
    assert pulser.config["api_keys"][0]["param"] == "access_key"
    assert len(pulser.supported_pulses) >= 10
    assert any(pulse["name"] == "company_profile" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "corporate_action_event" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "bid_ask_quote" for pulse in pulser.supported_pulses)
    assert any(pulse["name"] == "business_description" for pulse in pulser.supported_pulses)
    assert all("output_schema" not in pulse for pulse in pulser.config["supported_pulses"])
    assert all(len(str(pulse["pulse_address"])) == 36 for pulse in pulser.config["supported_pulses"])


def test_marketstack_config_exposes_intraday_quote_and_tickerinfo_fields():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "market_stack.pulser"

    pulser = ApiPulser(config=str(config_path), auto_register=False)
    grouped_pulses = [
        pulse for pulse in pulser.config["supported_pulses"]
        if pulse["name"] in {"bid_ask_quote", "business_description"}
    ]

    grouped_names = {pulse["name"] for pulse in grouped_pulses}
    assert {"bid_ask_quote", "business_description"} <= grouped_names

    mapped_fields = {
        str(rule)
        for pulse in grouped_pulses
        for rule in (pulse.get("mapping") or {}).values()
        if isinstance(rule, str)
    }
    assert {
        "bid_price",
        "bid_size",
        "ask_price",
        "ask_size",
        "mid",
        "date",
        "about",
    } <= mapped_fields
