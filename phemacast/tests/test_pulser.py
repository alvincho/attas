import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.agents.pulser import Pulser
from prompits.core.pit import PitAddress


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


def test_pulser_loads_config_and_maps_input_to_output_schema(tmp_path):
    config_path = tmp_path / "pulser.json"
    config_path.write_text(
        json.dumps(
            {
                "pulse_address": "plaza://pulse/last_price",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "ticker": {"type": "string"},
                        "quote": {
                            "type": "object",
                            "properties": {"price": {"type": "number"}},
                        },
                    },
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "last_price": {"type": "number"},
                        "source": {"type": "string"},
                    },
                },
                "mapping": {
                    "symbol": "ticker",
                    "last_price": "quote.price",
                    "source": {"value": "config"},
                },
            }
        ),
        encoding="utf-8",
    )

    pulser = Pulser.from_config(config_path)

    assert pulser.pulse_address == "plaza://pulse/last_price"
    assert pulser.input_schema["properties"]["ticker"]["type"] == "string"

    result = pulser.transform(
        {
            "ticker": "AAPL",
            "quote": {"price": 214.37, "currency": "USD"},
        }
    )

    assert result == {
        "symbol": "AAPL",
        "last_price": 214.37,
        "source": "config",
    }


def test_pulser_get_pulse_data_preserves_fetch_errors():
    class ErrorPulser(Pulser):
        def fetch_pulse_payload(self, pulse_name, input_data, pulse_definition):
            return {"error": "upstream failed"}

    pulser = ErrorPulser(
        name="ErrorPulser",
        pulse_name="last_price",
        pulse_address="plaza://pulse/last_price",
        input_schema={"type": "object", "properties": {"symbol": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"last_price": {"type": "number"}}},
        mapping={"last_price": "price"},
        auto_register=False,
    )

    result = pulser.get_pulse_data({"symbol": "IBM"}, pulse_name="last_price")

    assert result == {"error": "upstream failed"}


def test_pulser_registers_on_plaza_and_advertises_pulse_practice():
    sent_payloads = []

    def fake_post(url, json=None, timeout=5, **kwargs):
        sent_payloads.append({"url": url, "payload": dict(json or {}), "timeout": timeout})
        return FakeResponse(
            {
                "status": "registered",
                "token": "token-123",
                "expires_in": 3600,
                "agent_id": "pulser-id-123",
                "api_key": "pulser-key-123",
            }
        )

    with patch("prompits.agents.base.requests.post", side_effect=fake_post), patch(
        "prompits.agents.base.requests.get",
        return_value=FakeResponse([], status_code=200),
    ):
        pulser = Pulser(
            name="ConfigPulser",
            host="127.0.0.1",
            port=8120,
            plaza_url="http://127.0.0.1:8011",
            pulse_name="last_price",
            pulse_address="plaza://pulse/last_price",
            input_schema={
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
            },
            mapping={"symbol": "ticker"},
        )

    register_calls = [entry for entry in sent_payloads if entry["url"] == "http://127.0.0.1:8011/register"]
    assert len(register_calls) == 1
    assert register_calls[0]["payload"]["pit_type"] == "Pulser"
    assert len(register_calls[0]["payload"]["pulse_pulser_pairs"]) == 1
    assert register_calls[0]["payload"]["pulse_pulser_pairs"][0]["pulse_id"] == "urn:plaza:pulse:last.price"
    assert register_calls[0]["payload"]["pulse_pulser_pairs"][0]["pulse_name"] == "last_price"
    assert register_calls[0]["payload"]["pulse_pulser_pairs"][0]["pulse_address"] == "plaza://pulse/last_price"

    supported_pulses = pulser.agent_card["meta"]["supported_pulses"]
    assert pulser.agent_card["pit_type"] == "Pulser"
    assert pulser.agent_card["meta"]["pulse_address"] == "plaza://pulse/last_price"
    assert pulser.agent_card["meta"]["pulse_id"] == "urn:plaza:pulse:last.price"
    assert pulser.agent_card["meta"]["input_schema"]["properties"]["ticker"]["type"] == "string"
    assert supported_pulses[0]["pulse_id"] == "urn:plaza:pulse:last.price"
    assert supported_pulses[0]["pulse_definition"]["resource_type"] == "pulse_definition"
    assert supported_pulses[0]["pulse_address"] == "plaza://pulse/last_price"
    assert supported_pulses[0]["input_schema"]["properties"]["ticker"]["type"] == "string"

    practice_by_id = {entry["id"]: entry for entry in pulser.agent_card["practices"]}
    assert "get_pulse_data" in practice_by_id
    assert practice_by_id["get_pulse_data"]["parameters"]["params"]["properties"]["ticker"]["type"] == "string"
    assert pulser.agent_id == "pulser-id-123"


def test_pulser_register_batches_multiple_pulse_pairs_in_single_request():
    sent_payloads = []

    def fake_post(url, json=None, timeout=5, **kwargs):
        sent_payloads.append({"url": url, "payload": dict(json or {}), "timeout": timeout})
        return FakeResponse(
            {
                "status": "registered",
                "token": "token-123",
                "expires_in": 3600,
                "agent_id": "pulser-id-123",
                "api_key": "pulser-key-123",
            }
        )

    with patch("prompits.agents.base.requests.post", side_effect=fake_post), patch(
        "prompits.agents.base.requests.get",
        return_value=FakeResponse([], status_code=200),
    ):
        Pulser(
            name="BatchPulser",
            host="127.0.0.1",
            port=8121,
            plaza_url="http://127.0.0.1:8011",
            supported_pulses=[
                {
                    "name": "last_price",
                    "pulse_address": "plaza://pulse/last_price",
                    "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}},
                },
                {
                    "name": "trade_volume",
                    "pulse_address": "plaza://pulse/trade_volume",
                    "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}, "trade_date": {"type": "string"}}},
                },
            ],
        )

    register_calls = [entry for entry in sent_payloads if entry["url"] == "http://127.0.0.1:8011/register"]
    assert len(register_calls) == 1
    assert len(register_calls[0]["payload"]["pulse_pulser_pairs"]) == 2
    assert {entry["pulse_id"] for entry in register_calls[0]["payload"]["pulse_pulser_pairs"]} == {
        "urn:plaza:pulse:last.price",
        "urn:plaza:pulse:trade.volume",
    }
    assert {entry["pulse_name"] for entry in register_calls[0]["payload"]["pulse_pulser_pairs"]} == {"last_price", "trade_volume"}


def test_pulser_reregister_reuses_single_heartbeat_thread():
    sent_payloads = []
    heartbeat_threads = []

    class FakeHeartbeatThread:
        def __init__(self, target=None, daemon=None, name=None, **kwargs):
            self.target = target
            self.daemon = daemon
            self.name = name
            self.kwargs = kwargs
            self.started = 0
            self._alive = False
            heartbeat_threads.append(self)

        def start(self):
            self.started += 1
            self._alive = True

        def is_alive(self):
            return self._alive

    def fake_post(url, json=None, timeout=5, **kwargs):
        sent_payloads.append({"url": url, "payload": dict(json or {}), "timeout": timeout})
        return FakeResponse(
            {
                "status": "registered",
                "token": f"token-{len(sent_payloads)}",
                "expires_in": 3600,
                "agent_id": "pulser-id-123",
                "api_key": "pulser-key-123",
            }
        )

    with patch("prompits.agents.base.requests.post", side_effect=fake_post), patch(
        "prompits.agents.base.requests.get",
        return_value=FakeResponse([], status_code=200),
    ), patch(
        "prompits.agents.base.threading.Thread",
        side_effect=lambda *args, **kwargs: FakeHeartbeatThread(*args, **kwargs),
    ):
        pulser = Pulser(
            name="ConfigPulser",
            host="127.0.0.1",
            port=8120,
            plaza_url="http://127.0.0.1:8011",
            pulse_name="last_price",
            pulse_address="plaza://pulse/last_price",
            input_schema={
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
            },
            mapping={"symbol": "ticker"},
        )
        first_thread = pulser._heartbeat_thread

        pulser.plaza_token = None
        pulser.token_expires_at = 0
        pulser.register()

    register_calls = [entry for entry in sent_payloads if entry["url"] == "http://127.0.0.1:8011/register"]
    assert len(register_calls) == 2
    assert len(heartbeat_threads) == 1
    assert heartbeat_threads[0].started == 1
    assert pulser._heartbeat_thread is first_thread


def test_get_pulse_data_practice_executes_agent_mapping():
    pulser = Pulser(
        pulse_address="plaza://pulse/open_price",
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "open_price": {"type": "number"},
                "provider": {"type": "string"},
            },
        },
        mapping={
            "symbol": "request.symbol",
            "open_price": {"source": "response.open"},
            "provider": {"default": "unknown"},
        },
    )

    practice = next(practice for practice in pulser.practices if practice.id == "get_pulse_data")
    result = practice.execute(
        params={
            "request": {"symbol": "MSFT"},
            "response": {"open": 401.25},
        }
    )

    assert result == {
        "symbol": "MSFT",
        "open_price": 401.25,
        "provider": "unknown",
    }


def test_pulser_transform_supports_dotted_keys_and_list_indexes():
    pulser = Pulser(
        pulse_address="plaza://pulse/last_price",
        output_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "last_price": {"type": "number"},
                "headline": {"type": "string"},
            },
        },
        mapping={
            "symbol": "Global Quote.01. symbol",
            "last_price": "Global Quote.05. price",
            "headline": "feed.0.title",
        },
    )

    result = pulser.transform(
        {
            "Global Quote": {
                "01. symbol": "IBM",
                "05. price": "249.12",
            },
            "feed": [
                {"title": "IBM wins new contract"},
            ],
        }
    )

    assert result == {
        "symbol": "IBM",
        "last_price": "249.12",
        "headline": "IBM wins new contract",
    }


def test_pulser_transform_supports_arithmetic_operations():
    pulser = Pulser(
        pulse_address="plaza://pulse/financial_statement_metrics",
        output_schema={
            "type": "object",
            "properties": {
                "free_cash_flow": {"type": "number"},
                "current_ratio": {"type": "number"},
                "quick_ratio": {"type": "number"},
                "debt_to_equity": {"type": "number"},
            },
        },
        mapping={
            "free_cash_flow": {
                "op": "subtract_abs",
                "args": ["operatingCashflow", "capitalExpenditures"],
            },
            "current_ratio": {
                "op": "divide",
                "args": ["totalCurrentAssets", "totalCurrentLiabilities"],
            },
            "quick_ratio": {
                "op": "divide",
                "args": [
                    {
                        "op": "subtract",
                        "args": ["totalCurrentAssets", "inventory"],
                    },
                    "totalCurrentLiabilities",
                ],
            },
            "debt_to_equity": {
                "op": "divide",
                "args": ["shortLongTermDebtTotal", "totalShareholderEquity"],
                "round": 4,
            },
        },
    )

    result = pulser.transform(
        {
            "operatingCashflow": "1000",
            "capitalExpenditures": "-200",
            "totalCurrentAssets": "600",
            "totalCurrentLiabilities": "300",
            "inventory": "150",
            "shortLongTermDebtTotal": "400",
            "totalShareholderEquity": "1000",
        }
    )

    assert result == {
        "free_cash_flow": 800.0,
        "current_ratio": 2.0,
        "quick_ratio": 1.5,
        "debt_to_equity": 0.4,
    }


def test_pulser_transform_supports_mapping_lists_of_objects():
    pulser = Pulser(
        pulse_address="plaza://pulse/news_article",
        output_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "number_of_articles": {"type": "integer"},
                "articles": {"type": "array"},
            },
        },
        mapping={
            "symbol": "_input.symbol",
            "number_of_articles": "_input.number_of_articles",
            "articles": {
                "source": "feed",
                "items": {
                    "headline": "title",
                    "published_at": "time_published",
                    "publisher": "source",
                },
            },
        },
    )

    result = pulser.transform(
        {
            "_input": {"symbol": "IBM", "number_of_articles": 2},
            "feed": [
                {"title": "IBM wins new contract", "time_published": "2026-03-23T01:00:00Z", "source": "Newswire"},
                {"title": "IBM expands cloud offering", "time_published": "2026-03-23T00:00:00Z", "source": "MarketWatch"},
            ],
        }
    )

    assert result == {
        "symbol": "IBM",
        "number_of_articles": 2,
        "articles": [
            {
                "headline": "IBM wins new contract",
                "published_at": "2026-03-23T01:00:00Z",
                "publisher": "Newswire",
            },
            {
                "headline": "IBM expands cloud offering",
                "published_at": "2026-03-23T00:00:00Z",
                "publisher": "MarketWatch",
            },
        ],
    }


def test_pulser_transform_includes_mapping_keys_not_present_in_output_schema():
    pulser = Pulser(
        pulse_address="plaza://pulse/news_article",
        output_schema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "headline": {"type": "string"},
            },
        },
        mapping={
            "symbol": "_input.symbol",
            "number_of_articles": "_input.number_of_articles",
            "articles": {
                "source": "items",
                "items": {
                    "headline": "headline",
                    "published_at": "datetime",
                },
            },
        },
    )

    result = pulser.transform(
        {
            "_input": {"symbol": "AAPL", "number_of_articles": 2},
            "items": [
                {"headline": "A", "datetime": "2026-03-23T01:00:00Z"},
                {"headline": "B", "datetime": "2026-03-23T00:00:00Z"},
            ],
        }
    )

    assert result == {
        "symbol": "AAPL",
        "number_of_articles": 2,
        "articles": [
            {"headline": "A", "published_at": "2026-03-23T01:00:00Z"},
            {"headline": "B", "published_at": "2026-03-23T00:00:00Z"},
        ],
    }


def test_pulser_resolves_shared_plaza_pulse_schema_from_pit_address(monkeypatch):
    shared_pulse_id = "11111111-1111-1111-1111-111111111111"
    shared_pulse_address = PitAddress(pit_id=shared_pulse_id, plazas=["http://127.0.0.1:8011"])

    monkeypatch.setattr(
        Pulser,
        "_resolve_shared_pulse_card",
        lambda self, pulse_definition: {
            "name": "last_price",
            "description": "Canonical shared pulse",
            "tags": ["price", "market-data"],
            "pit_address": shared_pulse_address.to_dict(),
            "meta": {
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "last_price": {"type": "number"},
                    },
                }
            },
        },
    )

    pulser = Pulser(
        plaza_url="http://127.0.0.1:8011",
        supported_pulses=[
                {
                    "pulse_address": shared_pulse_id,
                    "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}},
                    "mapping": {"symbol": "symbol", "last_price": "price"},
                }
            ],
            auto_register=False,
        )

    assert pulser.supported_pulses[0]["pulse_address"] == shared_pulse_id
    assert pulser.supported_pulses[0]["name"] == "last_price"
    assert pulser.supported_pulses[0]["output_schema"]["properties"]["last_price"]["type"] == "number"


def test_pulser_register_prefetches_shared_pulse_catalog_once():
    search_calls = []

    def fake_post(url, json=None, timeout=5, **kwargs):
        return FakeResponse(
            {
                "status": "registered",
                "token": "token-123",
                "expires_in": 3600,
                "agent_id": "pulser-id-123",
                "api_key": "pulser-key-123",
            }
        )

    def fake_get(url, params=None, headers=None, timeout=5, **kwargs):
        search_calls.append({"url": url, "params": dict(params or {}), "timeout": timeout})
        return FakeResponse(
            [
                {
                    "pit_type": "Pulse",
                    "card": {
                        "name": "last_price",
                        "pit_address": {"pit_id": "pulse-1", "plazas": ["http://127.0.0.1:8011"]},
                        "meta": {
                            "output_schema": {
                                "type": "object",
                                "properties": {"last_price": {"type": "number"}},
                            }
                        },
                    },
                },
                {
                    "pit_type": "Pulse",
                    "card": {
                        "name": "trade_volume",
                        "pit_address": {"pit_id": "pulse-2", "plazas": ["http://127.0.0.1:8011"]},
                        "meta": {
                            "output_schema": {
                                "type": "object",
                                "properties": {"trade_volume": {"type": "number"}},
                            }
                        },
                    },
                },
            ]
        )

    with patch("prompits.agents.base.requests.post", side_effect=fake_post), patch(
        "prompits.agents.base.requests.get",
        side_effect=fake_get,
    ):
        pulser = Pulser(
            name="BatchPulser",
            host="127.0.0.1",
            port=8121,
            plaza_url="http://127.0.0.1:8011",
            supported_pulses=[
                {
                    "name": "last_price",
                    "pulse_address": "pulse-1",
                    "mapping": {"last_price": "price"},
                },
                {
                    "name": "trade_volume",
                    "pulse_address": "pulse-2",
                    "mapping": {"trade_volume": "volume"},
                },
            ],
        )

    assert len(search_calls) == 1
    assert search_calls[0]["url"] == "http://127.0.0.1:8011/search"
    assert search_calls[0]["params"]["pit_type"] == "Pulse"
    assert pulser.supported_pulses[0]["output_schema"]["properties"]["last_price"]["type"] == "number"
    assert pulser.supported_pulses[1]["output_schema"]["properties"]["trade_volume"]["type"] == "number"
