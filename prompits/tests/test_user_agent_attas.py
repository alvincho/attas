import os
import sys
import json
import time
from unittest.mock import patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.agents.user import UserAgent
from prompits.pools.filesystem import FileSystemPool


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = b"{}"

    def json(self):
        return self._payload


def build_user_agent(**kwargs):
    plaza_urls = kwargs.pop("plaza_urls", ["http://plaza-a", "http://plaza-b"])
    return UserAgent(
        name="AttasUserAgent",
        host="127.0.0.1",
        port=8414,
        plaza_url=None,
        plaza_urls=plaza_urls,
        **kwargs,
    )


def test_user_agent_root_serves_attas_dashboard():
    agent = build_user_agent(plaza_urls=[])
    client = TestClient(agent.app)

    response = client.get("/")
    assert response.status_code == 200
    assert "Create From A Phema" in response.text
    assert "Phema Library" in response.text
    assert "Recent Runs" in response.text
    assert "Create Snapshot" in response.text
    assert "Saved Locally" in response.text
    assert "Connected Plazas" in response.text
    assert "AgentConfig Library" in response.text
    assert "Extra Castr options (JSON)" not in response.text
    assert "Extra Phema params (JSON)" not in response.text


def test_user_agent_catalog_aggregates_multi_plaza_results():
    agent = build_user_agent()

    def fake_catalog(plaza_url: str, query: str = "", party: str = ""):
        assert query == "macro"
        if plaza_url == "http://plaza-a":
            return {
                "url": plaza_url,
                "online": True,
                "authenticated": True,
                "connected_agent_id": "user-a",
                "card": {"name": "PlazaA"},
                "applications": [
                    {
                        "id": "phema-a",
                        "phema_id": "phema-a",
                        "name": "Macro Brief",
                        "description": "Macro application",
                        "owner": "MacroPhemar",
                        "plaza_url": plaza_url,
                        "host_phemar_name": "MacroPhemar",
                        "host_phemar_agent_id": "phemar-a",
                        "host_phemar_plaza_url": plaza_url,
                        "tags": ["macro"],
                    }
                ],
                "phemars": [
                    {
                        "agent_id": "phemar-a",
                        "name": "MacroPhemar",
                        "description": "Generates macro applications",
                        "plaza_url": plaza_url,
                        "address": "http://phemar-a",
                        "tags": ["macro", "phemar"],
                    }
                ],
                "castrs": [],
                "llm_pulsers": [],
                "error": "",
            }
        return {
            "url": plaza_url,
            "online": True,
            "authenticated": True,
            "connected_agent_id": "user-b",
            "card": {"name": "PlazaB"},
            "applications": [],
            "phemars": [],
            "castrs": [
                {
                    "agent_id": "castr-b",
                    "name": "PdfCastr",
                    "description": "Renders PDF output",
                    "plaza_url": plaza_url,
                    "address": "http://castr-b",
                    "media_type": "PDF",
                    "tags": ["pdf", "castr"],
                }
            ],
            "llm_pulsers": [
                {
                    "agent_id": "pulser-1",
                    "name": "OpenAIPulser",
                    "description": "Runs llm_chat inference",
                    "plaza_url": plaza_url,
                    "address": "http://openai-pulser",
                    "pulse_name": "llm_chat",
                    "pulse_names": ["llm_chat"],
                    "tags": ["llm", "openai"],
                }
            ],
            "error": "",
        }

    with patch.object(agent, "_fetch_single_plaza_catalog", side_effect=fake_catalog):
        client = TestClient(agent.app)
        response = client.get("/api/attas/catalog?q=macro")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert len(payload["plazas"]) == 2
    assert len(payload["applications"]) == 1
    assert len(payload["llm_pulsers"]) == 1
    assert payload["llm_pulsers"][0]["pulse_name"] == "llm_chat"
    assert len(payload["phemars"]) == 1
    assert len(payload["castrs"]) == 1
    assert payload["applications"][0]["name"] == "Macro Brief"
    assert payload["applications"][0]["plaza_url"] == "http://plaza-a"
    assert payload["castrs"][0]["name"] == "PdfCastr"
    assert payload["castrs"][0]["plaza_url"] == "http://plaza-b"


def test_user_agent_catalog_enriches_application_with_host_phemar_address():
    agent = build_user_agent(plaza_urls=["http://plaza-a"])

    def fake_search(plaza_url, **kwargs):
        if kwargs.get("pit_type") == "Phema":
            return [
                {
                    "agent_id": "app-1",
                    "name": "Equity Brief",
                    "description": "Daily equity application",
                    "owner": "EquityPhemar",
                    "pit_type": "Phema",
                    "card": {
                        "phema_id": "app-1",
                        "name": "Equity Brief",
                        "description": "Daily equity application",
                    },
                    "meta": {
                        "host_phemar_name": "EquityPhemar",
                        "host_phemar_agent_id": "phemar-a",
                    },
                }
            ]
        if kwargs.get("role") == "phemar":
            return [
                {
                    "agent_id": "phemar-a",
                    "name": "EquityPhemar",
                    "description": "Generates equity applications",
                    "role": "phemar",
                    "card": {
                        "name": "EquityPhemar",
                        "role": "phemar",
                        "address": "http://phemar-a",
                    },
                }
            ]
        return []

    def fake_plaza_get(path, **kwargs):
        if path == "/health":
            return FakeResponse({}, 200)
        if path == "/.well-known/agent-card":
            return FakeResponse({"name": "PlazaA"}, 200)
        raise AssertionError(f"Unexpected path: {path}")

    with (
        patch.object(agent, "_plaza_get", side_effect=fake_plaza_get),
        patch.object(agent, "_ensure_plaza_session", return_value={"token": "token", "agent_id": "user-a"}),
        patch.object(agent, "_search_plaza", side_effect=fake_search),
    ):
        payload = agent._fetch_single_plaza_catalog("http://plaza-a")

    assert payload["applications"][0]["host_phemar_address"] == "http://phemar-a"
    assert payload["applications"][0]["host_phemar_agent_id"] == "phemar-a"


def test_user_agent_catalog_marks_stale_plaza_connection_disconnected():
    agent = build_user_agent(plaza_urls=["http://plaza-a"])
    stale_last_active = time.time() - 180

    def fake_search(plaza_url, **kwargs):
        if kwargs.get("agent_id") == "user-a":
            return [
                {
                    "agent_id": "user-a",
                    "name": "AttasUserAgent",
                    "description": "User agent registration row",
                    "role": "generic",
                    "last_active": stale_last_active,
                    "card": {
                        "name": "AttasUserAgent",
                        "role": "generic",
                        "address": "http://user-agent",
                    },
                }
            ]
        return []

    def fake_plaza_get(path, **kwargs):
        if path == "/health":
            return FakeResponse({}, 200)
        if path == "/.well-known/agent-card":
            return FakeResponse({"name": "PlazaA"}, 200)
        raise AssertionError(f"Unexpected path: {path}")

    with (
        patch.object(agent, "_plaza_get", side_effect=fake_plaza_get),
        patch.object(agent, "_ensure_plaza_session", return_value={"token": "token", "agent_id": "user-a"}),
        patch.object(agent, "_search_plaza", side_effect=fake_search),
    ):
        payload = agent._fetch_single_plaza_catalog("http://plaza-a")

    assert payload["authenticated"] is True
    assert payload["connected_agent_id"] == "user-a"
    assert payload["connected_agent_name"] == "AttasUserAgent"
    assert payload["connected_last_active"] == stale_last_active
    assert payload["connection_status"] == "disconnected"


def test_user_agent_lists_remote_snapshots_for_selected_application():
    agent = build_user_agent()
    application = {
        "id": "app-1",
        "phema_id": "app-1",
        "name": "Equity Brief",
        "plaza_url": "http://plaza-a",
        "host_phemar_name": "EquityPhemar",
        "host_phemar_agent_id": "phemar-a",
        "host_phemar_plaza_url": "http://plaza-a",
    }
    phemar = {
        "agent_id": "phemar-a",
        "name": "EquityPhemar",
        "plaza_url": "http://plaza-a",
        "address": "http://phemar-a",
    }
    snapshots = [
        {
            "snapshot_id": "snap-1",
            "phema_id": "app-1",
            "params_hash": "hash-1",
            "params": {"symbol": "AAPL"},
            "snapshot": {"name": "Equity Brief"},
        }
    ]

    with (
        patch.object(agent, "_resolve_application_selection", return_value=application),
        patch.object(agent, "_resolve_agent_selection", return_value=phemar),
        patch.object(agent, "_fetch_remote_snapshot_history", return_value=snapshots),
    ):
        client = TestClient(agent.app)
        response = client.get("/api/attas/snapshots?application_id=app-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["application"]["name"] == "Equity Brief"
    assert payload["phemar"]["name"] == "EquityPhemar"
    assert payload["snapshots"][0]["snapshot_id"] == "snap-1"
    assert payload["snapshots"][0]["params"] == {"symbol": "AAPL"}


def test_user_agent_lists_remote_snapshots_using_host_address_fallback():
    agent = build_user_agent()
    application = {
        "id": "app-1",
        "phema_id": "app-1",
        "name": "Equity Brief",
        "plaza_url": "http://plaza-a",
        "host_phemar_name": "EquityPhemar",
        "host_phemar_agent_id": "phemar-a",
        "host_phemar_plaza_url": "http://plaza-a",
        "host_phemar_address": "http://phemar-a",
    }
    snapshots = [
        {
            "snapshot_id": "snap-1",
            "phema_id": "app-1",
            "params_hash": "hash-1",
            "params": {"symbol": "AAPL"},
            "snapshot": {"name": "Equity Brief"},
        }
    ]

    def fake_fetch_snapshot_history(*, phemar, phema_id, limit, query=""):
        assert phemar["address"] == "http://phemar-a"
        assert phemar["agent_id"] == "phemar-a"
        assert phema_id == "app-1"
        return snapshots

    with (
        patch.object(agent, "_resolve_application_selection", return_value=application),
        patch.object(agent, "_resolve_agent_selection", return_value=None),
        patch.object(agent, "_fetch_remote_snapshot_history", side_effect=fake_fetch_snapshot_history),
    ):
        client = TestClient(agent.app)
        response = client.get("/api/attas/snapshots?application_id=app-1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["phemar"]["address"] == "http://phemar-a"
    assert payload["snapshots"][0]["snapshot_id"] == "snap-1"


def test_user_agent_generate_runs_snapshot_and_cast_chain():
    agent = build_user_agent()
    application = {
        "id": "app-1",
        "phema_id": "app-1",
        "name": "Equity Brief",
        "description": "Daily equity application",
        "plaza_url": "http://plaza-a",
        "host_phemar_name": "EquityPhemar",
        "host_phemar_agent_id": "phemar-a",
        "host_phemar_plaza_url": "http://plaza-a",
    }
    phemar = {
        "agent_id": "phemar-a",
        "name": "EquityPhemar",
        "plaza_url": "http://plaza-a",
        "address": "http://phemar-a",
    }
    castr = {
        "agent_id": "castr-b",
        "name": "PdfCastr",
        "plaza_url": "http://plaza-b",
        "address": "http://castr-b",
        "media_type": "PDF",
    }
    calls = []

    def fake_invoke(*, plaza_url, agent, practice_id, content, timeout=120):
        calls.append(
            {
                "plaza_url": plaza_url,
                "agent_name": agent.get("name"),
                "practice_id": practice_id,
                "content": content,
            }
        )
        if practice_id == "snapshot_phema":
            assert plaza_url == "http://plaza-a"
            assert agent["name"] == "EquityPhemar"
            assert content["phema_id"] == "app-1"
            assert content["params"] == {"symbol": "AAPL"}
            return {
                "status": "success",
                "snapshot_id": "snap-1",
                "snapshot": {
                    "name": "Equity Brief",
                    "sections": [
                        {"name": "Summary", "content": ["Fresh snapshot content"]},
                    ],
                },
            }
        assert plaza_url == "http://plaza-b"
        assert agent["name"] == "PdfCastr"
        assert content["phema"]["name"] == "Equity Brief"
        assert content["format"] == "PDF"
        return {
            "status": "success",
            "message": "Rendered PDF",
            "url": "/api/media/equity-brief.pdf",
        }

    with (
        patch.object(agent, "_resolve_application_selection", return_value=application),
        patch.object(agent, "_resolve_agent_selection", side_effect=lambda role, **_: phemar if role == "phemar" else castr),
        patch.object(agent, "_invoke_remote_practice_on_agent", side_effect=fake_invoke),
    ):
        client = TestClient(agent.app)
        response = client.post(
            "/api/attas/generate",
            json={
                "application_id": "app-1",
                "params": {"symbol": "AAPL"},
                "preferences": {"audience": "Desk"},
                "castr_agent_id": "castr-b",
                "castr_plaza_url": "http://plaza-b",
                "format": "PDF",
                "cache_time": 120,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["application"]["name"] == "Equity Brief"
    assert payload["phemar"]["name"] == "EquityPhemar"
    assert payload["castr"]["name"] == "PdfCastr"
    assert payload["cast"]["public_url"] == "http://castr-b/api/media/equity-brief.pdf"
    assert [entry["practice_id"] for entry in calls] == ["snapshot_phema", "cast_phema"]


def test_user_agent_generate_can_create_snapshot_without_castr():
    agent = build_user_agent()
    application = {
        "id": "app-1",
        "phema_id": "app-1",
        "name": "Equity Brief",
        "description": "Daily equity application",
        "plaza_url": "http://plaza-a",
        "host_phemar_name": "EquityPhemar",
        "host_phemar_agent_id": "phemar-a",
        "host_phemar_plaza_url": "http://plaza-a",
        "host_phemar_address": "http://phemar-a",
    }
    phemar = {
        "agent_id": "phemar-a",
        "name": "EquityPhemar",
        "plaza_url": "http://plaza-a",
        "address": "http://phemar-a",
    }

    def fake_invoke(*, plaza_url, agent, practice_id, content, timeout=120):
        assert practice_id == "snapshot_phema"
        assert plaza_url == "http://plaza-a"
        assert content["phema_id"] == "app-1"
        assert content["params"] == {"symbol": "AAPL"}
        return {
            "status": "success",
            "snapshot_id": "snap-1",
            "cached": False,
            "snapshot": {
                "name": "Equity Brief",
                "sections": [{"name": "Summary", "content": ["Fresh snapshot content"]}],
            },
            "history": {
                "snapshot_id": "snap-1",
                "phema_id": "app-1",
                "params": {"symbol": "AAPL"},
            },
        }

    with (
        patch.object(agent, "_resolve_application_selection", return_value=application),
        patch.object(agent, "_resolve_agent_selection", side_effect=lambda role, **_: phemar if role == "phemar" else None),
        patch.object(agent, "_invoke_remote_practice_on_agent", side_effect=fake_invoke),
    ):
        client = TestClient(agent.app)
        response = client.post(
            "/api/attas/generate",
            json={
                "application_id": "app-1",
                "params": {"symbol": "AAPL"},
                "cache_time": 120,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["snapshot_source"] == "generated"
    assert payload["snapshot"]["snapshot_id"] == "snap-1"
    assert payload["cast"] is None


def test_user_agent_generate_can_cast_existing_snapshot_without_new_snapshot_call():
    agent = build_user_agent()
    application = {
        "id": "app-1",
        "phema_id": "app-1",
        "name": "Equity Brief",
        "description": "Daily equity application",
        "plaza_url": "http://plaza-a",
        "host_phemar_name": "EquityPhemar",
        "host_phemar_agent_id": "phemar-a",
        "host_phemar_plaza_url": "http://plaza-a",
    }
    phemar = {
        "agent_id": "phemar-a",
        "name": "EquityPhemar",
        "plaza_url": "http://plaza-a",
        "address": "http://phemar-a",
    }
    castr = {
        "agent_id": "castr-b",
        "name": "PdfCastr",
        "plaza_url": "http://plaza-b",
        "address": "http://castr-b",
        "media_type": "PDF",
    }
    existing_snapshot = {
        "snapshot_id": "snap-77",
        "id": "snap-77",
        "phema_id": "app-1",
        "params": {"symbol": "MSFT"},
        "snapshot": {
            "name": "Equity Brief",
            "sections": [{"name": "Summary", "content": ["Existing snapshot"]}],
        },
    }
    calls = []

    def fake_invoke(*, plaza_url, agent, practice_id, content, timeout=120):
        calls.append(practice_id)
        assert practice_id == "cast_phema"
        assert plaza_url == "http://plaza-b"
        assert agent["name"] == "PdfCastr"
        assert content["phema"]["name"] == "Equity Brief"
        return {
            "status": "success",
            "message": "Rendered PDF",
            "url": "/api/media/equity-brief.pdf",
        }

    with (
        patch.object(agent, "_resolve_application_selection", return_value=application),
        patch.object(agent, "_resolve_agent_selection", side_effect=lambda role, **_: phemar if role == "phemar" else castr),
        patch.object(agent, "_fetch_remote_snapshot", return_value=existing_snapshot),
        patch.object(agent, "_invoke_remote_practice_on_agent", side_effect=fake_invoke),
    ):
        client = TestClient(agent.app)
        response = client.post(
            "/api/attas/generate",
            json={
                "application_id": "app-1",
                "snapshot_id": "snap-77",
                "castr_agent_id": "castr-b",
                "castr_plaza_url": "http://plaza-b",
                "format": "PDF",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["snapshot_source"] == "existing"
    assert payload["snapshot"]["snapshot_id"] == "snap-77"
    assert payload["snapshot"]["history"]["params"] == {"symbol": "MSFT"}
    assert payload["cast"]["public_url"] == "http://castr-b/api/media/equity-brief.pdf"
    assert calls == ["cast_phema"]


def test_user_agent_generate_can_run_llm_precast_before_cast():
    agent = build_user_agent()
    application = {
        "id": "app-1",
        "phema_id": "app-1",
        "name": "Equity Brief",
        "description": "Daily equity application",
        "plaza_url": "http://plaza-a",
        "host_phemar_name": "EquityPhemar",
        "host_phemar_agent_id": "phemar-a",
        "host_phemar_plaza_url": "http://plaza-a",
    }
    phemar = {
        "agent_id": "phemar-a",
        "name": "EquityPhemar",
        "plaza_url": "http://plaza-a",
        "address": "http://phemar-a",
    }
    castr = {
        "agent_id": "castr-b",
        "name": "PdfCastr",
        "plaza_url": "http://plaza-b",
        "address": "http://castr-b",
        "media_type": "PDF",
    }
    llm = {
        "agent_id": "llm-1",
        "name": "OpenAIPulser",
        "plaza_url": "http://plaza-b",
        "address": "http://pulser-b",
        "practice_id": "get_pulse_data",
        "pulse_name": "llm_chat",
    }
    existing_snapshot = {
        "snapshot_id": "snap-77",
        "id": "snap-77",
        "phema_id": "app-1",
        "params": {"symbol": "MSFT"},
        "snapshot": {
            "name": "Equity Brief",
            "description": "Original snapshot",
            "sections": [{"name": "Summary", "content": ["Existing snapshot"]}],
        },
    }
    calls = []

    def fake_invoke(*, plaza_url, agent, practice_id, content, timeout=120):
        calls.append(practice_id)
        if practice_id == "get_pulse_data":
            assert plaza_url == "http://plaza-b"
            assert agent["name"] == "OpenAIPulser"
            assert content["pulse_name"] == "llm_chat"
            assert "Confident" in content["input_data"]["prompt"]
            assert "Investor update" in content["input_data"]["prompt"]
            return {
                "status": "success",
                "response": json.dumps(
                    {
                        "name": "Boardroom Brief",
                        "description": "Investor-facing version of the same snapshot.",
                        "sections": [
                            {
                                "name": "Highlights",
                                "description": "Curated by the LLM pulser",
                                "modifier": "Lean into catalysts",
                                "content": ["MSFT setup looks constructive", "Keep the readout concise"],
                            }
                        ],
                        "script_summary": "Reframed for investor-facing delivery.",
                    }
                ),
            }

        assert practice_id == "cast_phema"
        assert plaza_url == "http://plaza-b"
        assert agent["name"] == "PdfCastr"
        assert content["phema"]["name"] == "Boardroom Brief"
        assert content["phema"]["llm_personalization"]["tone"] == "Confident"
        assert content["preferences"]["theme"] == "Investor update"
        return {
            "status": "success",
            "message": "Rendered PDF",
            "url": "/api/media/boardroom-brief.pdf",
        }

    with (
        patch.object(agent, "_resolve_application_selection", return_value=application),
        patch.object(agent, "_resolve_agent_selection", side_effect=lambda role, **_: phemar if role == "phemar" else castr),
        patch.object(agent, "_resolve_llm_preprocessor", return_value=llm) as mocked_resolve_llm,
        patch.object(agent, "_fetch_remote_snapshot", return_value=existing_snapshot),
        patch.object(agent, "_invoke_remote_practice_on_agent", side_effect=fake_invoke),
    ):
        client = TestClient(agent.app)
        response = client.post(
            "/api/attas/generate",
            json={
                "application_id": "app-1",
                "snapshot_id": "snap-77",
                "castr_agent_id": "castr-b",
                "castr_plaza_url": "http://plaza-b",
                "llm_agent_id": "llm-1",
                "llm_plaza_url": "http://plaza-b",
                "format": "PDF",
                "use_llm_preprocessor": True,
                "personalization": {
                    "tone": "Confident",
                    "style": "Investor update",
                    "modifier": "Focus on catalysts",
                    "audience": "PMs",
                    "language": "en",
                },
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["llm"]["name"] == "OpenAIPulser"
    assert payload["temporary_script"]["name"] == "Boardroom Brief"
    assert payload["temporary_script"]["llm_script_summary"] == "Reframed for investor-facing delivery."
    assert payload["cast"]["public_url"] == "http://castr-b/api/media/boardroom-brief.pdf"
    assert calls == ["get_pulse_data", "cast_phema"]
    mocked_resolve_llm.assert_called_once()
    assert mocked_resolve_llm.call_args.kwargs["llm_agent_id"] == "llm-1"
    assert mocked_resolve_llm.call_args.kwargs["llm_plaza_url"] == "http://plaza-b"


def test_user_agent_resolves_chat_practice_llm_fallback():
    agent = build_user_agent()
    application = {
        "id": "app-1",
        "phema_id": "app-1",
        "name": "Equity Brief",
        "plaza_url": "http://plaza-a",
    }
    phemar = {"plaza_url": "http://plaza-a"}
    castr = {"plaza_url": "http://plaza-b"}

    llm_chat_row = {
        "agent_id": "pulser-1",
        "name": "OpenAIPulser",
        "role": "pulser",
        "description": "LLM pulser",
        "card": {
            "name": "OpenAIPulser",
            "role": "pulser",
            "address": "http://openai-pulser",
            "tags": ["llm", "openai"],
            "practices": [{"id": "chat-practice"}],
        },
    }

    def fake_search(plaza_url, **params):
        if params.get("practice") == "llm":
            return []
        if params.get("role") == "llm":
            return []
        if params.get("practice") == "chat-practice" and plaza_url == "http://plaza-b":
            return [llm_chat_row]
        return []

    with patch.object(agent, "_search_plaza", side_effect=fake_search):
        resolved = agent._resolve_llm_preprocessor(
            selected_application=application,
            resolved_phemar=phemar,
            selected_castr=castr,
        )

    assert resolved is not None
    assert resolved["name"] == "OpenAIPulser"
    assert resolved["practice_id"] == "chat-practice"


def test_user_agent_can_save_result_locally_and_serve_artifact(tmp_path):
    pool = FileSystemPool(name="attas-user-test", description="attas user test pool", root_path=str(tmp_path))
    agent = build_user_agent(plaza_urls=[], pool=pool)
    client = TestClient(agent.app)

    result = {
        "status": "success",
        "application": {
            "id": "app-1",
            "phema_id": "app-1",
            "name": "Equity Brief",
            "description": "Daily market summary",
        },
        "snapshot": {
            "status": "success",
            "snapshot_id": "snap-1",
            "snapshot": {
                "name": "Equity Brief",
                "description": "A simple saved snapshot",
                "sections": [
                    {"name": "Summary", "content": ["Fresh snapshot content"]},
                ],
            },
        },
        "castr": {
            "agent_id": "castr-b",
            "name": "PdfCastr",
            "media_type": "PDF",
        },
        "cast": {
            "format": "PDF",
            "message": "Rendered PDF",
            "public_url": "http://castr-b/api/media/equity-brief.pdf",
            "location": "/api/media/equity-brief.pdf",
        },
    }

    class FakeResponse:
        content = b"%PDF-1.4 test artifact"

        def raise_for_status(self):
            return None

    with patch("prompits.agents.user.requests.get", return_value=FakeResponse()):
        response = client.post(
            "/api/attas/saved_results",
            json={
                "title": "Daily Brief",
                "result": result,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"

    saved = payload["saved_result"]
    assert saved["title"] == "Daily Brief"
    assert saved["application_name"] == "Equity Brief"
    assert saved["castr_name"] == "PdfCastr"
    assert saved["format"] == "PDF"
    assert saved["public_artifact_url"] == "http://castr-b/api/media/equity-brief.pdf"
    assert saved["local_artifact_url"].startswith("/api/attas/saved_artifacts/")

    local_artifact = tmp_path / "saved_outputs" / saved["local_artifact_name"]
    assert local_artifact.exists()
    assert local_artifact.read_bytes() == b"%PDF-1.4 test artifact"

    list_response = client.get("/api/attas/saved_results")
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert list_payload["status"] == "success"
    assert len(list_payload["results"]) == 1
    assert list_payload["results"][0]["title"] == "Daily Brief"

    artifact_response = client.get(saved["local_artifact_url"])
    assert artifact_response.status_code == 200
    assert artifact_response.content == b"%PDF-1.4 test artifact"
