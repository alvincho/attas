"""
Regression tests for Phemar.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_phemar_start_from_config_runs_health_server_in_thread`,
`test_phemar_loads_config_registers_and_advertises_generate_practice`,
`test_phemar_register_auto_registers_supported_phema_objects_with_configured_mode`, and
`test_phemar_register_skips_auto_register_when_plaza_registration_fails`, helping guard
against regressions as the packages evolve.
"""

import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.agents.phemar import Phemar
from phemacast.core.phema import Phema
from prompits.pools.filesystem import FileSystemPool


class FakeResponse:
    """Response model for fake payloads."""
    def __init__(self, payload, status_code=200):
        """Initialize the fake response."""
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")

    def json(self):
        """Handle JSON for the fake response."""
        return self._payload


def test_phemar_loads_config_registers_and_advertises_generate_practice(tmp_path):
    """
    Exercise the test_phemar_loads_config_registers_and_advertises_generate_practice
    regression scenario.
    """
    config_path = tmp_path / "phemar.json"
    config_path.write_text(
        json.dumps(
            {
                "name": "MacroPhemar",
                "host": "127.0.0.1",
                "port": 8131,
                "plaza_url": "http://127.0.0.1:8011",
                "phemar": {
                    "description": "Builds static macro briefs.",
                    "supported_phemas": [
                        {
                            "phema_id": "macro-brief",
                            "name": "Macro Brief",
                            "description": "Daily macro summary",
                            "sections": [
                                {
                                    "name": "Topline",
                                    "description": "Open the brief",
                                    "content": ["price"],
                                }
                            ],
                            "input_schema": {
                                "symbol": {"type": "string"},
                            },
                            "tags": ["macro"],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    sent_payloads = []

    def fake_post(url, json=None, timeout=5, **kwargs):
        """Handle fake post."""
        sent_payloads.append({"url": url, "payload": dict(json or {}), "timeout": timeout})
        return FakeResponse(
            {
                "status": "registered",
                "token": "phemar-token",
                "expires_in": 3600,
                "agent_id": "phemar-id-123",
                "api_key": "phemar-key-123",
            }
        )

    with patch("prompits.agents.base.requests.post", side_effect=fake_post):
        phemar = Phemar.from_config(config_path)

    assert phemar.name == "MacroPhemar"
    assert phemar.host == "127.0.0.1"
    assert phemar.port == 8131
    assert len(sent_payloads) == 2
    assert sent_payloads[0]["url"] == "http://127.0.0.1:8011/register"
    assert sent_payloads[0]["payload"]["pit_type"] == "Agent"
    assert sent_payloads[1]["url"] == "http://127.0.0.1:8011/api/directory/entries"
    assert sent_payloads[1]["payload"]["entry"]["agent_id"] == "macro-brief"
    assert sent_payloads[1]["payload"]["entry"]["pit_type"] == "Phema"
    assert sent_payloads[1]["payload"]["entry"]["card"]["phema_id"] == "macro-brief"
    assert phemar.agent_id == "phemar-id-123"

    practice_by_id = {entry["id"]: entry for entry in phemar.agent_card["practices"]}
    assert "generate_phema" in practice_by_id
    assert practice_by_id["generate_phema"]["parameters"]["phema_id"]["enum"] == ["macro-brief"]
    assert phemar.agent_card["meta"]["supported_phemas"][0]["name"] == "Macro Brief"


def test_phemar_register_auto_registers_supported_phema_objects_with_configured_mode():
    """
    Exercise the
    test_phemar_register_auto_registers_supported_phema_objects_with_configured_mode
    regression scenario.
    """
    phemar = Phemar(
        plaza_url="http://127.0.0.1:8011",
        supported_phemas=[
            {
                "phema_id": "macro-brief",
                "name": "Macro Brief",
                "sections": [{"name": "Topline", "content": []}],
                "meta": {"registration_mode": "info_only"},
            }
        ],
        auto_register=False,
    )

    class SuccessResponse:
        """Response model for success payloads."""
        status_code = 200

    def fake_register(*args, **kwargs):
        """Handle fake register."""
        phemar.plaza_token = "registered-token"
        return SuccessResponse()

    with patch("prompits.agents.standby.StandbyAgent.register", side_effect=fake_register), patch.object(
        phemar,
        "_register_phema_on_plaza",
        return_value={},
    ) as mocked_register_phema:
        phemar.register()

    assert mocked_register_phema.call_count == 1
    kwargs = mocked_register_phema.call_args.kwargs
    assert kwargs["phema_id"] == "macro-brief"
    assert kwargs["registration_mode"] == "info_only"
    assert isinstance(kwargs["phema"], Phema)
    assert kwargs["phema"].phema_id == "macro-brief"
    assert kwargs["phema"].snapshot_cache_time == 0


def test_phemar_register_skips_auto_register_when_plaza_registration_fails():
    """
    Exercise the
    test_phemar_register_skips_auto_register_when_plaza_registration_fails
    regression scenario.
    """
    phemar = Phemar(
        plaza_url="http://127.0.0.1:8011",
        supported_phemas=[
            {
                "phema_id": "macro-brief",
                "name": "Macro Brief",
                "sections": [{"name": "Topline", "content": []}],
            }
        ],
        auto_register=False,
    )

    class FailedResponse:
        """Response model for failed payloads."""
        status_code = 503

    with patch("prompits.agents.standby.StandbyAgent.register", return_value=FailedResponse()), patch.object(
        phemar,
        "_register_phema_on_plaza",
        return_value={},
    ) as mocked_register_phema:
        phemar.register()

    assert mocked_register_phema.call_count == 0


def test_phema_snapshot_cache_time_is_preserved_in_agent_metadata():
    """
    Exercise the test_phema_snapshot_cache_time_is_preserved_in_agent_metadata
    regression scenario.
    """
    phemar = Phemar(
        supported_phemas=[
            {
                "phema_id": "macro-brief",
                "name": "Macro Brief",
                "snapshot_cache_time": 900,
                "sections": [{"name": "Topline", "content": []}],
            }
        ],
        auto_register=False,
    )

    supported = phemar.agent_card["meta"]["supported_phemas"]
    assert supported[0]["snapshot_cache_time"] == 900

    practice_by_id = {entry["id"]: entry for entry in phemar.agent_card["practices"]}
    assert "input" in practice_by_id["snapshot_phema"]["parameters"]


def test_phema_preserves_output_schema_in_round_trip_and_agent_metadata():
    """
    Exercise the test_phema_preserves_output_schema_in_round_trip_and_agent_metadata
    regression scenario.
    """
    phema = Phema.from_dict(
        {
            "phema_id": "diagram-brief",
            "name": "Diagram Brief",
            "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}},
            "output_schema": {"type": "object", "properties": {"price": {"type": "number"}}},
            "sections": [{"name": "Flow", "content": []}],
            "meta": {"map_phemar": {"version": 1}},
        }
    )

    payload = phema.to_dict()
    assert payload["output_schema"]["properties"]["price"]["type"] == "number"

    phemar = Phemar(
        supported_phemas=[payload],
        auto_register=False,
    )

    supported = phemar.agent_card["meta"]["supported_phemas"]
    assert supported[0]["output_schema"]["properties"]["price"]["type"] == "number"


def test_generate_phema_fetches_matching_pulser_and_replaces_section_content():
    """
    Exercise the
    test_generate_phema_fetches_matching_pulser_and_replaces_section_content
    regression scenario.
    """
    phemar = Phemar(
        supported_phemas=[
            {
                "phema_id": "macro-brief",
                "name": "Macro Brief",
                "description": "Daily macro summary",
                "sections": [
                    {
                        "name": "Topline",
                        "description": "Open the brief",
                        "modifier": "Concise",
                        "content": [
                            "price",
                            {
                                "key": "headline",
                                "pulse_name": "news",
                                "params": {"limit": 3},
                            },
                        ],
                    }
                ],
                "input_schema": {
                    "symbol": {"type": "string"},
                },
            }
        ],
        auto_register=False,
    )

    with patch.object(
        phemar,
        "_search_directory",
        side_effect=[
            [{"card": {"pit_address": {"pit_id": "pulser-price-id", "plazas": ["http://127.0.0.1:8011"]}}}],
            [{"card": {"pit_address": {"pit_id": "pulser-news-id", "plazas": ["http://127.0.0.1:8011"]}}}],
        ],
    ), patch.object(phemar, "UsePractice") as mocked_use_practice:
        def fake_use_practice(practice_id, content=None, pit_address=None, **kwargs):
            """Handle fake use practice."""
            assert practice_id == "get_pulse_data"
            if pit_address.pit_id == "pulser-price-id":
                return {"value": 214.37, "symbol": content["params"]["symbol"]}
            if pit_address.pit_id == "pulser-news-id":
                return {"value": ["Fed holds rates"], "limit": content["params"]["limit"]}
            raise AssertionError(f"unexpected pit id {pit_address.pit_id}")

        mocked_use_practice.side_effect = fake_use_practice

        result = phemar.generate_phema(
            phema_id="macro-brief",
            params={"symbol": "AAPL"},
        )

    assert result["status"] == "success"
    assert result["phema"]["phema_id"] == "macro-brief"
    assert result["pulse_data"]["price"]["value"] == 214.37
    assert result["pulse_data"]["headline"]["value"] == ["Fed holds rates"]

    content = result["sections"][0]["content"]
    assert content[0]["pulse_name"] == "price"
    assert content[0]["result"]["data"]["symbol"] == "AAPL"
    assert content[1]["key"] == "headline"
    assert content[1]["result"]["params"]["limit"] == 3


def test_generate_phema_projects_selected_fields_for_section_display():
    """
    Exercise the test_generate_phema_projects_selected_fields_for_section_display
    regression scenario.
    """
    phemar = Phemar(
        supported_phemas=[
            {
                "phema_id": "stock-brief",
                "name": "Stock Brief",
                "sections": [
                    {
                        "name": "Price",
                        "content": [
                            {
                                "pulse_name": "last_price",
                                "pulser_id": "pulser-price-id",
                                "selected_fields": ["quote.price", "quote.currency"],
                            }
                        ],
                    }
                ],
            }
        ],
        auto_register=False,
    )

    with patch.object(phemar, "lookup_agent_info", return_value={"card": {"pit_address": {"pit_id": "pulser-price-id"}}}), patch.object(
        phemar,
        "UsePractice",
        return_value={"quote": {"price": 214.37, "currency": "USD", "volume": 1200}, "symbol": "AAPL"},
    ):
        result = phemar.generate_phema(phema_id="stock-brief", params={"symbol": "AAPL"})

    content = result["sections"][0]["content"][0]
    assert content["pulser_id"] == "pulser-price-id"
    assert content["selected_fields"] == ["quote.price", "quote.currency"]
    assert content["result"]["display_data"] == {"quote": {"price": 214.37, "currency": "USD"}}


def test_generate_phema_records_fetch_timing_and_cost_metadata():
    """
    Exercise the test_generate_phema_records_fetch_timing_and_cost_metadata
    regression scenario.
    """
    phemar = Phemar(
        supported_phemas=[
            {
                "phema_id": "stock-brief",
                "name": "Stock Brief",
                "sections": [
                    {
                        "name": "Price",
                        "content": [
                            {
                                "pulse_name": "last_price",
                                "pulser_id": "pulser-price-id",
                            }
                        ],
                    }
                ],
            }
        ],
        auto_register=False,
    )

    with patch.object(
        phemar,
        "lookup_agent_info",
        return_value={
            "card": {
                "pit_address": {"pit_id": "pulser-price-id"},
                "practices": [{"id": "get_pulse_data", "cost": 2.5}],
            }
        },
    ), patch.object(
        phemar,
        "UsePractice",
        return_value={"quote": {"price": 214.37, "currency": "USD"}},
    ):
        result = phemar.generate_phema(phema_id="stock-brief", params={"symbol": "AAPL"})

    content = result["sections"][0]["content"][0]
    fetch = content["result"]["fetch"]
    assert fetch["started_at"]
    assert fetch["ended_at"]
    assert fetch["duration_ms"] >= 0
    assert fetch["cost"] == 2.5
    assert fetch["cache_hit"] is False


def test_generate_phema_supports_inline_text_and_field_items_with_cached_fetch():
    """
    Exercise the
    test_generate_phema_supports_inline_text_and_field_items_with_cached_fetch
    regression scenario.
    """
    phemar = Phemar(
        supported_phemas=[
            {
                "phema_id": "inline-field-brief",
                "name": "Inline Field Brief",
                "sections": [
                    {
                        "name": "Summary",
                        "content": [
                            {"type": "text", "text": "Company:"},
                            {
                                "type": "pulse-field",
                                "pulse_name": "company_profile",
                                "pulser_id": "pulser-profile-id",
                                "field_path": "profile.name",
                            },
                            {"type": "text", "text": "Sector:"},
                            {
                                "type": "pulse-field",
                                "pulse_name": "company_profile",
                                "pulser_id": "pulser-profile-id",
                                "field_path": "profile.sector",
                            },
                        ],
                    }
                ],
            }
        ],
        auto_register=False,
    )

    with patch.object(
        phemar,
        "lookup_agent_info",
        return_value={"card": {"pit_address": {"pit_id": "pulser-profile-id", "plazas": ["http://127.0.0.1:8011"]}}},
    ), patch.object(
        phemar,
        "UsePractice",
        return_value={"profile": {"name": "Apple Inc.", "sector": "Technology"}},
    ) as mocked_use_practice:
        result = phemar.generate_phema(phema_id="inline-field-brief", params={"symbol": "AAPL"})

    content = result["sections"][0]["content"]
    assert content[0] == {"type": "text", "text": "Company:"}
    assert content[1]["type"] == "pulse-field"
    assert content[1]["field_path"] == "profile.name"
    assert content[1]["result"]["display_value"] == "Apple Inc."
    assert content[2] == {"type": "text", "text": "Sector:"}
    assert content[3]["type"] == "pulse-field"
    assert content[3]["field_path"] == "profile.sector"
    assert content[3]["result"]["display_value"] == "Technology"
    assert mocked_use_practice.call_count == 1


def test_save_static_phema_marks_snapshot_as_static():
    """
    Exercise the test_save_static_phema_marks_snapshot_as_static regression
    scenario.
    """
    phemar = Phemar(
        supported_phemas=[
            {
                "phema_id": "dynamic-brief",
                "name": "Dynamic Brief",
                "sections": [
                    {
                        "name": "Snapshot",
                        "content": [
                            {
                                "type": "pulse",
                                "pulse_name": "last_price",
                                "selected_fields": ["quote.price"],
                            }
                        ],
                    }
                ],
            }
        ],
        auto_register=False,
    )

    with patch.object(
        phemar,
        "generate_phema",
        return_value={
            "input_data": {"symbol": "AAPL"},
            "pulse_data": {"last_price": {"quote": {"price": 214.37}}},
            "sections": [
                {
                    "name": "Snapshot",
                    "description": "",
                    "modifier": "",
                    "content": [
                        {
                            "key": "last_price",
                            "pulse_name": "last_price",
                            "pulse_address": "plaza://pulse/last_price",
                            "result": {"data": {"quote": {"price": 214.37}}},
                        }
                    ],
                }
            ],
        },
    ):
        saved = phemar._save_static_phema(phema_id="dynamic-brief")

    assert saved["resolution_mode"] == "static"
    assert saved["meta"]["resolution_mode"] == "static"
    assert isinstance(saved["meta"]["fetches"], list)


def test_save_static_phema_extracts_fetches_and_removes_redundant_result_payload():
    """
    Exercise the
    test_save_static_phema_extracts_fetches_and_removes_redundant_result_payload
    regression scenario.
    """
    phemar = Phemar(
        plaza_url="http://127.0.0.1:8011",
        supported_phemas=[
            {
                "phema_id": "dynamic-brief",
                "name": "Dynamic Brief",
                "sections": [
                    {
                        "name": "Snapshot",
                        "content": [
                            {
                                "type": "pulse-field",
                                "pulse_name": "last_price",
                                "field_path": "quote.price",
                            }
                        ],
                    }
                ],
            }
        ],
        auto_register=False,
    )

    with patch.object(
        phemar,
        "generate_phema",
        return_value={
            "input_data": {"symbol": "AAPL"},
            "sections": [
                {
                    "name": "Snapshot",
                    "description": "",
                    "modifier": "",
                    "content": [
                        {
                            "key": "last_price:quote.price",
                            "pulse_name": "last_price",
                            "pulse_address": "plaza://pulse/last_price",
                            "pulser_id": "pulser-price-id",
                            "pulser_name": "Price Pulser",
                            "field_path": "quote.price",
                            "selected_fields": ["quote.price"],
                            "result": {
                                "params": {"symbol": "AAPL"},
                                "data": {"quote": {"price": 214.37, "currency": "USD"}},
                                "display_value": 214.37,
                                "fetch": {
                                    "started_at": "2026-01-01T00:00:00+00:00",
                                    "ended_at": "2026-01-01T00:00:01+00:00",
                                    "duration_ms": 1000,
                                    "cost": 1.25,
                                    "cache_hit": False,
                                },
                            },
                        }
                    ],
                }
            ],
        },
    ):
        saved = phemar._save_static_phema(phema_id="dynamic-brief")

    fetches = saved["meta"]["fetches"]
    assert len(fetches) == 1
    assert fetches[0]["pulse_name"] == "last_price"
    assert fetches[0]["pulse_pit_address"] == {
        "pit_id": "plaza://pulse/last_price",
        "plazas": ["http://127.0.0.1:8011"],
    }
    assert fetches[0]["pulser_pit_address"] == {
        "pit_id": "pulser-price-id",
        "plazas": ["http://127.0.0.1:8011"],
    }
    assert fetches[0]["data"] == {"quote": {"price": 214.37, "currency": "USD"}}

    value = saved["sections"][0]["content"][0]["value"]
    assert value["fetch"] == fetches[0]["id"]
    assert value["data"] == 214.37
    assert value["field_path"] == "quote.price"
    assert sorted(value.keys()) == ["data", "fetch", "field_path"]
    assert "result" not in value


def test_save_static_phema_consolidates_identical_fetches_for_multiple_fields():
    """
    Exercise the
    test_save_static_phema_consolidates_identical_fetches_for_multiple_fields
    regression scenario.
    """
    phemar = Phemar(
        plaza_url="http://127.0.0.1:8011",
        supported_phemas=[
            {
                "phema_id": "company-brief",
                "name": "Company Brief",
                "sections": [
                    {
                        "name": "Summary",
                        "content": [
                            {"type": "pulse-field", "pulse_name": "company_profile", "field_path": "industry"},
                            {"type": "pulse-field", "pulse_name": "company_profile", "field_path": "sector"},
                        ],
                    }
                ],
            }
        ],
        auto_register=False,
    )

    with patch.object(
        phemar,
        "generate_phema",
        return_value={
            "input_data": {"symbol": "AAPL"},
            "sections": [
                {
                    "name": "Summary",
                    "description": "",
                    "modifier": "",
                    "content": [
                        {
                            "key": "company_profile:industry",
                            "pulse_name": "company_profile",
                            "pulse_address": "plaza://pulse/company_profile",
                            "pulser_id": "pulser-profile-id",
                            "pulser_name": "Profile Pulser",
                            "field_path": "industry",
                            "result": {
                                "params": {"symbol": "AAPL"},
                                "data": {"industry": "INFORMATION TECHNOLOGY SERVICES", "sector": "Technology"},
                                "display_value": "INFORMATION TECHNOLOGY SERVICES",
                                "fetch": {
                                    "started_at": "2026-01-01T00:00:00+00:00",
                                    "ended_at": "2026-01-01T00:00:01+00:00",
                                    "duration_ms": 1000,
                                    "cost": 1.25,
                                    "cache_hit": False,
                                },
                            },
                        },
                        {
                            "key": "company_profile:sector",
                            "pulse_name": "company_profile",
                            "pulse_address": "plaza://pulse/company_profile",
                            "pulser_id": "pulser-profile-id",
                            "pulser_name": "Profile Pulser",
                            "field_path": "sector",
                            "result": {
                                "params": {"symbol": "AAPL"},
                                "data": {"industry": "INFORMATION TECHNOLOGY SERVICES", "sector": "Technology"},
                                "display_value": "Technology",
                                "fetch": {
                                    "started_at": "2026-01-01T00:00:00+00:00",
                                    "ended_at": "2026-01-01T00:00:01+00:00",
                                    "duration_ms": 1000,
                                    "cost": 1.25,
                                    "cache_hit": True,
                                },
                            },
                        },
                    ],
                }
            ],
        },
    ):
        saved = phemar._save_static_phema(phema_id="company-brief")

    fetches = saved["meta"]["fetches"]
    assert len(fetches) == 1
    assert fetches[0]["pulse_pit_address"] == {
        "pit_id": "plaza://pulse/company_profile",
        "plazas": ["http://127.0.0.1:8011"],
    }
    assert fetches[0]["pulser_pit_address"] == {
        "pit_id": "pulser-profile-id",
        "plazas": ["http://127.0.0.1:8011"],
    }
    first_value = saved["sections"][0]["content"][0]["value"]
    second_value = saved["sections"][0]["content"][1]["value"]
    assert first_value["fetch"] == second_value["fetch"] == fetches[0]["id"]
    assert first_value["data"] == "INFORMATION TECHNOLOGY SERVICES"
    assert second_value["data"] == "Technology"


def test_snapshot_phema_reuses_cached_snapshot_and_history(tmp_path):
    """
    Exercise the test_snapshot_phema_reuses_cached_snapshot_and_history regression
    scenario.
    """
    pool = FileSystemPool("snapshot_pool", "Snapshot pool", str(tmp_path / "pool"))
    phemar = Phemar(
        pool=pool,
        supported_phemas=[
            {
                "phema_id": "dynamic-brief",
                "name": "Dynamic Brief",
                "sections": [
                    {
                        "name": "Snapshot",
                        "content": [
                            {
                                "type": "pulse",
                                "pulse_name": "last_price",
                                "selected_fields": ["quote.price"],
                            }
                        ],
                    }
                ],
            }
        ],
        auto_register=False,
    )

    generated_payload = {
        "status": "success",
        "input_data": {"symbol": "AAPL"},
        "pulse_data": {
            "last_price": {
                "quote": {"price": 214.37},
                "fetch": {
                    "started_at": "2026-01-01T00:00:00+00:00",
                    "ended_at": "2026-01-01T00:00:01+00:00",
                    "duration_ms": 1000,
                    "cost": 0,
                    "cache_hit": False,
                },
            }
        },
        "sections": [
            {
                "name": "Snapshot",
                "description": "",
                "modifier": "",
                "content": [
                    {
                        "key": "last_price",
                        "pulse_name": "last_price",
                        "pulse_address": "plaza://pulse/last_price",
                        "result": {
                            "data": {"quote": {"price": 214.37}},
                            "fetch": {
                                "started_at": "2026-01-01T00:00:00+00:00",
                                "ended_at": "2026-01-01T00:00:01+00:00",
                                "duration_ms": 1000,
                                "cost": 0,
                                "cache_hit": False,
                            },
                        },
                    }
                ],
            }
        ],
    }

    with patch.object(phemar, "generate_phema", return_value=generated_payload) as mocked_generate:
        first = phemar.snapshot_phema(phema_id="dynamic-brief", params={"symbol": "AAPL"}, cache_time=300)
        second = phemar.snapshot_phema(phema_id="dynamic-brief", params={"symbol": "AAPL"}, cache_time=300)

    assert first["cached"] is False
    assert second["cached"] is True
    assert mocked_generate.call_count == 1
    assert first["snapshot"]["resolution_mode"] == "static"
    history = phemar._list_snapshot_history(phema_id="dynamic-brief")
    assert len(history) == 1
    assert history[0]["snapshot"]["resolution_mode"] == "static"
    assert history[0]["meta"]["source_phema_id"] == "dynamic-brief"
    snapshot_fetches = history[0]["snapshot"]["meta"]["fetches"]
    assert len(snapshot_fetches) == 1
    assert snapshot_fetches[0]["fetch"]["started_at"]
    assert snapshot_fetches[0]["fetch"]["ended_at"]
    assert snapshot_fetches[0]["fetch"]["duration_ms"] >= 0
    assert snapshot_fetches[0]["fetch"]["cost"] == 0


def test_snapshot_phema_regenerates_after_cache_expiry(tmp_path):
    """
    Exercise the test_snapshot_phema_regenerates_after_cache_expiry regression
    scenario.
    """
    pool = FileSystemPool("snapshot_expiry_pool", "Snapshot expiry pool", str(tmp_path / "pool"))
    phemar = Phemar(
        pool=pool,
        supported_phemas=[
            {
                "phema_id": "dynamic-brief",
                "name": "Dynamic Brief",
                "sections": [
                    {
                        "name": "Snapshot",
                        "content": [
                            {
                                "type": "pulse",
                                "pulse_name": "last_price",
                                "selected_fields": ["quote.price"],
                            }
                        ],
                    }
                ],
            }
        ],
        auto_register=False,
    )

    generated_payloads = [
        {
            "status": "success",
            "input_data": {"symbol": "AAPL"},
            "pulse_data": {"last_price": {"quote": {"price": 214.37}}},
            "sections": [
                {
                    "name": "Snapshot",
                    "description": "",
                    "modifier": "",
                    "content": [
                        {
                            "key": "last_price",
                            "pulse_name": "last_price",
                            "pulse_address": "plaza://pulse/last_price",
                            "result": {"data": {"quote": {"price": 214.37}}},
                        }
                    ],
                }
            ],
        },
        {
            "status": "success",
            "input_data": {"symbol": "AAPL"},
            "pulse_data": {"last_price": {"quote": {"price": 220.01}}},
            "sections": [
                {
                    "name": "Snapshot",
                    "description": "",
                    "modifier": "",
                    "content": [
                        {
                            "key": "last_price",
                            "pulse_name": "last_price",
                            "pulse_address": "plaza://pulse/last_price",
                            "result": {"data": {"quote": {"price": 220.01}}},
                        }
                    ],
                }
            ],
        },
    ]

    with patch.object(phemar, "generate_phema", side_effect=generated_payloads) as mocked_generate:
        first = phemar.snapshot_phema(phema_id="dynamic-brief", params={"symbol": "AAPL"}, cache_time=300)
        expired_row = phemar._get_snapshot_row(first["snapshot_id"])
        expired_raw = dict(expired_row)
        expired_raw["id"] = expired_row["snapshot_id"]
        expired_raw["expires_at"] = "2000-01-01T00:00:00+00:00"
        pool._Insert(phemar.PHEMA_SNAPSHOT_TABLE, expired_raw)
        second = phemar.snapshot_phema(phema_id="dynamic-brief", params={"symbol": "AAPL"}, cache_time=300)

    assert first["cached"] is False
    assert second["cached"] is False
    assert mocked_generate.call_count == 2
    history = phemar._list_snapshot_history(phema_id="dynamic-brief")
    assert len(history) == 2


def test_snapshot_phema_uses_phema_snapshot_cache_time_property(tmp_path):
    """
    Exercise the test_snapshot_phema_uses_phema_snapshot_cache_time_property
    regression scenario.
    """
    pool = FileSystemPool("snapshot_property_pool", "Snapshot property pool", str(tmp_path / "pool"))
    phemar = Phemar(
        pool=pool,
        supported_phemas=[
            {
                "phema_id": "dynamic-brief",
                "name": "Dynamic Brief",
                "snapshot_cache_time": 300,
                "sections": [
                    {
                        "name": "Snapshot",
                        "content": [
                            {
                                "type": "pulse",
                                "pulse_name": "last_price",
                            }
                        ],
                    }
                ],
            }
        ],
        auto_register=False,
    )

    generated_payload = {
        "status": "success",
        "input_data": {"symbol": "AAPL"},
        "pulse_data": {"last_price": {"quote": {"price": 214.37}}},
        "sections": [
            {
                "name": "Snapshot",
                "description": "",
                "modifier": "",
                "content": [
                    {
                        "key": "last_price",
                        "pulse_name": "last_price",
                        "pulse_address": "plaza://pulse/last_price",
                        "result": {"data": {"quote": {"price": 214.37}}},
                    }
                ],
            }
        ],
    }

    with patch.object(phemar, "generate_phema", return_value=generated_payload) as mocked_generate:
        first = phemar.snapshot_phema(phema_id="dynamic-brief", params={"symbol": "AAPL"})
        second = phemar.snapshot_phema(phema_id="dynamic-brief", params={"symbol": "AAPL"})

    assert first["cached"] is False
    assert second["cached"] is True
    assert first["cache_ttl_seconds"] == 300
    assert second["cache_ttl_seconds"] == 300
    assert mocked_generate.call_count == 1


def test_snapshot_phema_practice_accepts_input_alias():
    """
    Exercise the test_snapshot_phema_practice_accepts_input_alias regression
    scenario.
    """
    phemar = Phemar(
        supported_phemas=[
            {
                "phema_id": "dynamic-brief",
                "name": "Dynamic Brief",
                "sections": [{"name": "Snapshot", "content": []}],
            }
        ],
        auto_register=False,
    )

    practice = next(practice for practice in phemar.practices if practice.id == "snapshot_phema")

    with patch.object(
        phemar,
        "snapshot_phema",
        return_value={"status": "success", "cached": False, "snapshot_id": "snap-1", "snapshot": {}},
    ) as mocked_snapshot:
        result = practice.execute(phema_id="dynamic-brief", input={"symbol": "AAPL"})

    assert result["status"] == "success"
    kwargs = mocked_snapshot.call_args.kwargs
    assert kwargs["params"] == {"symbol": "AAPL"}
    assert kwargs["input_data"] == {"symbol": "AAPL"}


def test_phemar_start_from_config_runs_health_server_in_thread(tmp_path):
    """
    Exercise the test_phemar_start_from_config_runs_health_server_in_thread
    regression scenario.
    """
    config_path = tmp_path / "threaded_phemar.json"
    config_path.write_text(
        json.dumps(
            {
                "name": "ThreadedPhemar",
                "host": "127.0.0.1",
                "port": 8132,
                "phemar": {
                    "supported_phemas": [
                        {
                            "phema_id": "inline-phema",
                            "name": "Inline Phema",
                            "sections": [{"name": "Section", "content": []}],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    agent, server, thread = Phemar.start_from_config(config_path, auto_register=False)
    try:
        assert agent.name == "ThreadedPhemar"
        assert thread.is_alive()
    finally:
        server.should_exit = True
        thread.join(timeout=5)
