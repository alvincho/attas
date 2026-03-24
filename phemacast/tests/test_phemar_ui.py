import json
import os
import sys
from unittest.mock import patch

import requests
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.agents.phemar import Phemar


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.content = json.dumps(payload).encode("utf-8")

    def json(self):
        return self._payload


def test_phemar_mounts_editor_ui_and_persists_local_phemas(tmp_path):
    config_path = tmp_path / "stock_report.phemar"
    config_path.write_text(
        json.dumps(
            {
                "name": "UiPhemar",
                "type": "phemacast.agents.phemar.Phemar",
                "host": "127.0.0.1",
                "port": 8136,
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "ui_phemar_pool",
                        "description": "UI phemar pool",
                        "root_path": str(tmp_path / "pool"),
                    }
                ],
                "phemar": {
                    "description": "UI-enabled phemar",
                    "supported_phemas": [
                        {
                            "phema_id": "macro-brief",
                            "name": "Macro Brief",
                            "description": "Daily macro summary",
                            "sections": [
                                {
                                    "name": "Topline",
                                    "content": ["last_price"],
                                }
                            ],
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    agent = Phemar.from_config(config_path, auto_register=False)

    with TestClient(agent.app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "Phema Manager" in root.text
        assert "Search Phemas" in root.text
        assert "Current Tasks" in root.text
        assert "Selected Phema" in root.text
        assert "Search Snapshots" in root.text
        assert "Generate Snapshot" in root.text
        assert "Save As" in root.text
        assert "Idle" in root.text
        assert "Input Schema" in root.text
        assert "Available Pulsers" in root.text
        assert "Active Only" in root.text
        assert "Get Sample" in root.text
        assert "Selected Content" in root.text
        assert "Returned Fields To Display" in root.text
        assert "Plaza Mode" in root.text
        assert "Update Plaza" in root.text
        assert "Not Registered" in root.text
        assert "Collapse All" in root.text
        assert "Expand All" in root.text
        assert "snapshot_phema" not in root.text
        assert 'id="manager-detail-panel" class="manager-detail-panel" hidden' in root.text
        assert 'id="phema-meta-grid" class="meta-grid" hidden' in root.text
        assert 'id="phema-workspace" class="workspace" hidden' in root.text

        listing = client.get("/api/phemas")
        assert listing.status_code == 200
        phemas = listing.json()["phemas"]
        assert len(phemas) == 1
        assert phemas[0]["name"] == "Macro Brief"

        manager = client.get("/api/phemar/manager")
        assert manager.status_code == 200
        assert manager.json()["local_phemas"][0]["name"] == "Macro Brief"

        create_resp = client.post(
            "/api/phemas",
            json={
                "phema": {
                    "name": "Stock Report",
                    "description": "Editable stock report",
                    "owner": "attas",
                    "tags": ["stocks", "report"],
                    "input_schema": {"symbol": {"type": "string"}},
                    "sections": [
                        {
                            "name": "Price Action",
                            "description": "Latest market snapshot",
                            "modifier": "Keep numbers raw",
                            "content": [
                                {
                                    "type": "pulse",
                                    "pulse_name": "last_price",
                                    "pulse_address": "plaza://pulse/last_price",
                                }
                            ],
                        }
                    ],
                }
            },
        )
        assert create_resp.status_code == 200
        saved = create_resp.json()["phema"]
        assert saved["name"] == "Stock Report"
        assert saved["phema_id"]
        assert saved["resolution_mode"] == "dynamic"

        loaded = client.get(f"/api/phemas/{saved['phema_id']}")
        assert loaded.status_code == 200
        assert loaded.json()["phema"]["sections"][0]["name"] == "Price Action"
        assert loaded.json()["phema"]["resolution_mode"] == "dynamic"

        with patch.object(
            agent,
            "generate_phema",
            return_value={
                "status": "success",
                "input_data": {"symbol": "AAPL"},
                "pulse_data": {"last_price": {"quote": {"price": 214.37}}},
                "sections": [
                    {
                        "name": "Price Action",
                        "description": "Latest market snapshot",
                        "modifier": "Keep numbers raw",
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
        ) as mocked_generate:
            snapshot = client.post(
                "/api/phemas/snapshot",
                json={"phema_id": saved["phema_id"], "params": {"symbol": "AAPL"}, "cache_time": 300},
            )
            assert snapshot.status_code == 200
            snapshot_payload = snapshot.json()
            assert snapshot_payload["cached"] is False
            snapshot_id = snapshot_payload["snapshot_id"]

            snapshot_listing = client.get(f"/api/phema-snapshots?phema_id={saved['phema_id']}")
            assert snapshot_listing.status_code == 200
            assert snapshot_listing.json()["snapshots"][0]["snapshot_id"] == snapshot_id

            snapshot_search = client.get(f"/api/phema-snapshots?phema_id={saved['phema_id']}&q=AAPL")
            assert snapshot_search.status_code == 200
            assert snapshot_search.json()["snapshots"][0]["snapshot_id"] == snapshot_id

            snapshot_detail = client.get(f"/api/phema-snapshots/{snapshot_id}")
            assert snapshot_detail.status_code == 200
            assert snapshot_detail.json()["snapshot"]["snapshot"]["resolution_mode"] == "static"

            snapshot_view = client.get(f"/phema-snapshots/{snapshot_id}/view")
            assert snapshot_view.status_code == 200
            assert "Pretty JSON viewer for snapshot history" in snapshot_view.text
            assert snapshot_id[:8] in snapshot_view.text

            delete_snapshot = client.delete(f"/api/phema-snapshots/{snapshot_id}")
            assert delete_snapshot.status_code == 200

            deleted_listing = client.get(f"/api/phema-snapshots?phema_id={saved['phema_id']}")
            assert deleted_listing.status_code == 200
            assert deleted_listing.json()["snapshots"] == []

            retaken_snapshot = client.post(
                "/api/phemas/snapshot",
                json={"phema_id": saved["phema_id"], "params": {"symbol": "AAPL"}, "cache_time": 0},
            )
            assert retaken_snapshot.status_code == 200
            assert retaken_snapshot.json()["cached"] is False

            second_snapshot = client.post(
                "/api/phemas/snapshot",
                json={"phema_id": saved["phema_id"], "params": {"symbol": "AAPL"}, "cache_time": 300},
            )
            assert second_snapshot.status_code == 200
            assert second_snapshot.json()["cached"] is True
            assert mocked_generate.call_count == 2

    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    supported = persisted["phemar"]["supported_phemas"]
    assert {entry["name"] for entry in supported} == {"Macro Brief", "Stock Report"}


def test_phemar_enforces_owner_checks_for_plaza_edit_and_deregister(tmp_path):
    config_path = tmp_path / "owner_guard.phemar"
    config_path.write_text(
        json.dumps(
            {
                "name": "OwnerGuardPhemar",
                "type": "phemacast.agents.phemar.Phemar",
                "host": "127.0.0.1",
                "port": 8137,
                "plaza_url": "http://127.0.0.1:8011",
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "owner_guard_pool",
                        "description": "Owner guard pool",
                        "root_path": str(tmp_path / "pool"),
                    }
                ],
                "phemar": {
                    "supported_phemas": [
                        {
                            "phema_id": "owned-local",
                            "name": "Owned Local",
                            "owner": "OwnerGuardPhemar",
                            "sections": [{"name": "Section", "content": []}],
                        },
                        {
                            "phema_id": "owned-remote",
                            "name": "Owned Remote Draft",
                            "owner": "OwnerGuardPhemar",
                            "sections": [{"name": "Remote Draft", "content": []}],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    agent = Phemar.from_config(config_path, auto_register=False)
    owned_remote = {
        "agent_id": "owned-remote",
        "owner": "OwnerGuardPhemar",
        "registration_mode": "info_only",
        "card": {
            "agent_id": "owned-remote",
            "name": "Owned Remote",
            "owner": "OwnerGuardPhemar",
            "pit_type": "Phema",
            "sections": [{"name": "Owned", "content": []}],
            "meta": {
                "registration_mode": "info_only",
                "downloadable": False,
                "host_phemar_name": "OwnerGuardPhemar",
            },
        },
    }
    foreign_remote = {
        "agent_id": "foreign-remote",
        "owner": "AnotherPhemar",
        "card": {
            "agent_id": "foreign-remote",
            "name": "Foreign Remote",
            "owner": "AnotherPhemar",
            "pit_type": "Phema",
            "sections": [{"name": "Foreign", "content": []}],
            "meta": {},
        },
    }

    def fake_search_directory(**params):
        if params.get("agent_id") == "owned-remote":
            return [owned_remote]
        if params.get("agent_id") == "foreign-remote":
            return [foreign_remote]
        if params.get("pit_type") == "Phema":
            return [owned_remote, foreign_remote]
        return []

    with patch.object(agent, "_search_directory", side_effect=fake_search_directory), patch.object(
        agent,
        "_plaza_post",
        return_value=FakeResponse({"status": "success", "phema": owned_remote["card"]}),
    ) as mocked_post, patch.object(
        agent,
        "_plaza_request",
        return_value=FakeResponse({"status": "success"}),
    ) as mocked_delete:
        with TestClient(agent.app) as client:
            plaza_list = client.get("/api/plaza/phemas")
            assert plaza_list.status_code == 200
            plaza_rows = {entry["phema_id"]: entry for entry in plaza_list.json()["phemas"]}
            assert plaza_rows["owned-remote"]["editable"] is True
            assert plaza_rows["foreign-remote"]["editable"] is False

            manager = client.get("/api/phemar/manager")
            assert manager.status_code == 200
            local_rows = {entry["phema_id"]: entry for entry in manager.json()["local_phemas"]}
            assert local_rows["owned-local"]["plaza_registered"] is False
            assert local_rows["owned-remote"]["plaza_registered"] is True
            assert local_rows["owned-remote"]["plaza_phema_id"] == "owned-remote"
            assert local_rows["owned-remote"]["plaza_registration_mode"] == "info_only"
            assert local_rows["owned-remote"]["plaza_downloadable"] is False

            forbidden_update = client.post(
                "/api/plaza/phemas/register",
                json={"phema": {"phema_id": "foreign-remote", "name": "Foreign Remote", "sections": []}},
            )
            assert forbidden_update.status_code == 403

            allowed_update = client.post(
                "/api/plaza/phemas/register",
                json={
                    "phema": {
                        "phema_id": "owned-remote",
                        "name": "Owned Remote",
                        "sections": [{"name": "Owned", "content": ["secret"]}],
                    },
                    "registration_mode": "info_only",
                },
            )
            assert allowed_update.status_code == 200
            assert mocked_post.called
            sent_payload = mocked_post.call_args.kwargs["json"]["phema"]
            assert sent_payload["meta"]["registration_mode"] == "info_only"
            assert sent_payload["sections"] == []
            assert sent_payload["input_schema"] == {}

            forbidden_delete = client.delete("/api/plaza/phemas/foreign-remote")
            assert forbidden_delete.status_code == 403

            allowed_delete = client.delete("/api/plaza/phemas/owned-remote")
            assert allowed_delete.status_code == 200
            assert mocked_delete.called


def test_phemar_runs_pulser_test_via_use_practice(tmp_path):
    config_path = tmp_path / "pulser_proxy.phemar"
    config_path.write_text(
        json.dumps(
            {
                "name": "PulserProxyPhemar",
                "type": "phemacast.agents.phemar.Phemar",
                "host": "127.0.0.1",
                "port": 8138,
                "plaza_url": "http://127.0.0.1:8011",
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "pulser_proxy_pool",
                        "description": "Pulser proxy pool",
                        "root_path": str(tmp_path / "pool"),
                    }
                ],
                "phemar": {
                    "supported_phemas": [
                        {
                            "phema_id": "proxy-phema",
                            "name": "Proxy Phema",
                            "sections": [{"name": "Section", "content": []}],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    agent = Phemar.from_config(config_path, auto_register=False)

    resolved_pulser = {
        "agent_id": "pulser-1",
        "name": "PricePulser",
        "card": {
            "agent_id": "pulser-1",
            "name": "PricePulser",
            "pit_type": "Pulser",
            "pit_address": {"pit_id": "pulser-1", "plazas": ["http://127.0.0.1:8011"]},
            "address": "http://127.0.0.1:8025",
        },
    }

    with patch.object(agent, "lookup_agent_info", return_value=resolved_pulser), patch.object(
        agent,
        "UsePractice",
        return_value={"quote": {"price": 214.37}},
    ) as mocked_use_practice:
        with TestClient(agent.app) as client:
            response = client.post(
                "/api/pulsers/test",
                json={
                    "pulser_id": "pulser-1",
                    "pulse_name": "last_price",
                    "pulse_address": "plaza://pulse/last_price",
                    "input": {"symbol": "AAPL"},
                },
            )

    assert response.status_code == 200
    assert response.json()["result"]["quote"]["price"] == 214.37
    assert mocked_use_practice.call_args.args[0] == "get_pulse_data"
    assert mocked_use_practice.call_args.kwargs["content"] == {
        "pulse_name": "last_price",
        "pulse_address": "plaza://pulse/last_price",
        "params": {"symbol": "AAPL"},
        "output_schema": {},
    }
    assert mocked_use_practice.call_args.kwargs["pit_address"].pit_id == "pulser-1"


def test_phemar_manager_survives_plaza_timeout(tmp_path):
    config_path = tmp_path / "timeout_guard.phemar"
    config_path.write_text(
        json.dumps(
            {
                "name": "TimeoutGuardPhemar",
                "type": "phemacast.agents.phemar.Phemar",
                "host": "127.0.0.1",
                "port": 8139,
                "plaza_url": "http://127.0.0.1:8011",
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "timeout_guard_pool",
                        "description": "Timeout guard pool",
                        "root_path": str(tmp_path / "pool"),
                    }
                ],
                "phemar": {
                    "supported_phemas": [
                        {
                            "phema_id": "local-timeout-phema",
                            "name": "Local Timeout Phema",
                            "owner": "TimeoutGuardPhemar",
                            "sections": [{"name": "Section", "content": []}],
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    agent = Phemar.from_config(config_path, auto_register=False)

    with patch.object(
        agent,
        "_search_directory",
        side_effect=requests.ReadTimeout("HTTPConnectionPool(host='127.0.0.1', port=8011): Read timed out. (read timeout=30)"),
    ):
        with TestClient(agent.app) as client:
            manager = client.get("/api/phemar/manager")
            assert manager.status_code == 200
            payload = manager.json()
            assert payload["status"] == "success"
            assert payload["plaza_available"] is False
            assert "Read timed out" in payload["plaza_error"]
            assert payload["plaza_phemas"] == []
            assert payload["local_phemas"][0]["name"] == "Local Timeout Phema"
            assert payload["local_phemas"][0]["plaza_registered"] is False
            assert payload["local_phemas"][0]["plaza_lookup_failed"] is True

            plaza_list = client.get("/api/plaza/phemas")
            assert plaza_list.status_code == 200
            plaza_payload = plaza_list.json()
            assert plaza_payload["status"] == "degraded"
            assert plaza_payload["plaza_available"] is False
            assert "Read timed out" in plaza_payload["plaza_error"]
            assert plaza_payload["phemas"] == []
