"""
Regression tests for Map Phemar Agent.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_map_phemar_config_exists_for_create_agent`,
`test_demo_map_phemar_diagrams_use_current_shape_ids`,
`test_map_phemar_agent_alias_routes_respect_requested_storage_directory`, and
`test_map_phemar_agent_exposes_branch_condition_route`, helping guard against
regressions as the packages evolve.
"""

import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import phemacast.map_phemar.runtime as map_phemar_runtime
from phemacast.agents.map_phemar import MapPhemarAgent
from phemacast.map_phemar.runtime import evaluate_branch_condition
from prompits.tests.test_support import build_agent_from_config


def test_map_phemar_agent_serves_map_editor_ui_and_persists_phemas(tmp_path):
    """
    Exercise the test_map_phemar_agent_serves_map_editor_ui_and_persists_phemas
    regression scenario.
    """
    config_path = tmp_path / "map.phemar"
    pool_path = tmp_path / "pool"
    config_path.write_text(
        json.dumps(
            {
                "name": "MapPhemar",
                "type": "phemacast.agents.map_phemar.MapPhemarAgent",
                "host": "127.0.0.1",
                "port": 8142,
                "role": "phemar",
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "map_phemar_pool",
                        "description": "Local pool",
                        "root_path": str(pool_path),
                    }
                ],
                "phemar": {
                    "description": "Standalone map phemar",
                    "supported_phemas": [],
                },
            }
        ),
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))
    assert isinstance(agent, MapPhemarAgent)

    with TestClient(agent.app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "<title>MapPhemar</title>" in root.text
        assert 'id="root"' in root.text
        assert '"app_mode": "map_phemar"' in root.text
        assert '"phema_api_prefix": "/api/map-phemar/phemas"' in root.text
        assert '"map_phemar_settings_scope": "map_phemar"' in root.text
        assert '"map_phemar_storage_settings_mode": "local"' in root.text
        assert f'"default_file_save_local_directory": "{tmp_path}"' in root.text
        assert "__PHEMACAST_MAP_PHEMAR_BOOTSTRAP__" in root.text
        assert "map_phemar_app.css?v=" in root.text
        assert "map_phemar_app.jsx?v=" in root.text

        listing = client.get("/api/map-phemar/phemas")
        assert listing.status_code == 200
        assert listing.json()["phemas"] == []

        create_resp = client.post(
            "/api/map-phemar/phemas",
            json={
                "phema": {
                    "name": "Daily OHLC Diagram",
                    "input_schema": {"type": "object", "properties": {"symbol": {"type": "string"}}},
                    "output_schema": {"type": "object", "properties": {"bars": {"type": "array"}}},
                    "sections": [{"name": "Flow", "content": [{"type": "text", "text": "Diagram-backed"}]}],
                    "meta": {"map_phemar": {"version": 1, "diagram": {"nodes": [], "edges": []}}},
                }
            },
        )
        assert create_resp.status_code == 200
        saved = create_resp.json()["phema"]
        assert saved["name"] == "Daily OHLC Diagram"
        assert saved["output_schema"]["properties"]["bars"]["type"] == "array"

        detail = client.get(f"/api/map-phemar/phemas/{saved['phema_id']}")
        assert detail.status_code == 200
        assert detail.json()["phema"]["meta"]["map_phemar"]["version"] == 1

        editor = client.get(f"/phemas/editor/{saved['phema_id']}")
        assert editor.status_code == 200
        assert saved["phema_id"] in editor.text
        assert '"phema_api_prefix": "/api/map-phemar/phemas"' in editor.text

    persisted = json.loads(config_path.read_text(encoding="utf-8"))
    supported = persisted["phemar"]["supported_phemas"]
    assert len(supported) == 1
    assert supported[0]["name"] == "Daily OHLC Diagram"


def test_map_phemar_source_does_not_offer_full_local_state_reset():
    """
    Exercise the test_map_phemar_source_does_not_offer_full_local_state_reset
    regression scenario.
    """
    source = (Path(__file__).resolve().parents[1] / "map_phemar" / "static" / "map_phemar_app.jsx").read_text(encoding="utf-8")

    assert "Reset All Local State" not in source
    assert "Reload App" in source


def test_map_phemar_agent_alias_routes_respect_requested_storage_directory(tmp_path):
    """
    Exercise the
    test_map_phemar_agent_alias_routes_respect_requested_storage_directory
    regression scenario.
    """
    config_path = tmp_path / "map.phemar"
    pool_path = tmp_path / "pool"
    config_path.write_text(
        json.dumps(
            {
                "name": "MapPhemar",
                "type": "phemacast.agents.map_phemar.MapPhemarAgent",
                "host": "127.0.0.1",
                "port": 8142,
                "role": "phemar",
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "map_phemar_pool",
                        "description": "Local pool",
                        "root_path": str(pool_path),
                    }
                ],
                "phemar": {
                    "description": "Standalone map phemar",
                    "supported_phemas": [],
                },
            }
        ),
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))
    custom_directory = tmp_path / "standalone-map-phemar-location"

    with TestClient(agent.app) as client:
        create_response = client.post(
            "/api/map-phemar/phemas",
            params={"map_phemar_storage_directory": str(custom_directory)},
            json={
                "phema": {
                    "name": "Scoped Diagram",
                    "input_schema": {"type": "object"},
                    "output_schema": {"type": "object"},
                    "sections": [{"name": "Flow", "content": [{"type": "text", "text": "Scoped"}]}],
                    "meta": {"map_phemar": {"version": 1, "diagram": {"nodes": [], "edges": []}}},
                }
            },
        )

        assert create_response.status_code == 200

        scoped_listing = client.get(
            "/api/map-phemar/phemas",
            params={"map_phemar_storage_directory": str(custom_directory)},
        )
        assert scoped_listing.status_code == 200
        assert len(scoped_listing.json()["phemas"]) == 1

        default_listing = client.get("/api/map-phemar/phemas")
        assert default_listing.status_code == 200
        assert default_listing.json()["phemas"] == []


def test_map_phemar_agent_ui_respects_requested_plaza_url(tmp_path):
    """
    Exercise the test_map_phemar_agent_ui_respects_requested_plaza_url regression
    scenario.
    """
    config_path = tmp_path / "map.phemar"
    pool_path = tmp_path / "pool"
    config_path.write_text(
        json.dumps(
            {
                "name": "MapPhemar",
                "type": "phemacast.agents.map_phemar.MapPhemarAgent",
                "host": "127.0.0.1",
                "port": 8142,
                "role": "phemar",
                "plaza_url": "http://127.0.0.1:8011",
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "map_phemar_pool",
                        "description": "Local pool",
                        "root_path": str(pool_path),
                    }
                ],
                "phemar": {
                    "description": "Standalone map phemar",
                    "supported_phemas": [],
                },
            }
        ),
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))
    assert isinstance(agent, MapPhemarAgent)

    with TestClient(agent.app) as client:
        root = client.get("/", params={"map_phemar_plaza_url": "http://127.0.0.1:9123"})
        assert root.status_code == 200
        assert '"plaza_url": "http://127.0.0.1:9123"' in root.text


def test_map_phemar_config_exists_for_create_agent():
    """
    Exercise the test_map_phemar_config_exists_for_create_agent regression scenario.
    """
    config_path = Path(__file__).resolve().parents[2] / "phemacast" / "configs" / "map.phemar"
    payload = json.loads(config_path.read_text(encoding="utf-8"))

    assert payload["name"] == "MapPhemar"
    assert payload["type"] == "phemacast.agents.map_phemar.MapPhemarAgent"
    assert payload["pools"][0]["type"] == "FileSystemPool"


def test_map_phemar_branch_condition_evaluator_supports_python_boolean_expressions():
    """
    Exercise the
    test_map_phemar_branch_condition_evaluator_supports_python_boolean_expressions
    regression scenario.
    """
    assert evaluate_branch_condition("input_data.get('price', 0) > 100 and payload.get('enabled', False)", {"price": 125, "enabled": True}) is True
    assert evaluate_branch_condition("branch_input.get('price', 0) > 100 and data.get('enabled', False)", {"price": 90, "enabled": True}) is False


def test_map_phemar_agent_exposes_branch_condition_route(tmp_path):
    """
    Exercise the test_map_phemar_agent_exposes_branch_condition_route regression
    scenario.
    """
    config_path = tmp_path / "map.phemar"
    pool_path = tmp_path / "pool"
    config_path.write_text(
        json.dumps(
            {
                "name": "MapPhemar",
                "type": "phemacast.agents.map_phemar.MapPhemarAgent",
                "host": "127.0.0.1",
                "port": 8142,
                "role": "phemar",
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "map_phemar_pool",
                        "description": "Local pool",
                        "root_path": str(pool_path),
                    }
                ],
                "phemar": {
                    "description": "Standalone map phemar",
                    "supported_phemas": [],
                },
            }
        ),
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))

    with TestClient(agent.app) as client:
        response = client.post(
            "/api/plaza/branch/evaluate",
            json={"expression": "input_data.get('count', 0) >= 2", "input": {"count": 3}},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "success", "result": True}


def test_map_phemar_agent_exposes_local_directory_picker_route(tmp_path, monkeypatch):
    """
    Exercise the test_map_phemar_agent_exposes_local_directory_picker_route
    regression scenario.
    """
    config_path = tmp_path / "map.phemar"
    pool_path = tmp_path / "pool"
    config_path.write_text(
        json.dumps(
            {
                "name": "MapPhemar",
                "type": "phemacast.agents.map_phemar.MapPhemarAgent",
                "host": "127.0.0.1",
                "port": 8142,
                "role": "phemar",
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "map_phemar_pool",
                        "description": "Local pool",
                        "root_path": str(pool_path),
                    }
                ],
                "phemar": {
                    "description": "Standalone map phemar",
                    "supported_phemas": [],
                },
            }
        ),
        encoding="utf-8",
    )

    requested_initial_directory: list[str] = []

    def fake_select_local_directory(initial_directory: str = "") -> str:
        """Handle fake select local directory."""
        requested_initial_directory.append(initial_directory)
        return str(tmp_path / "chosen-storage-folder")

    monkeypatch.setattr(map_phemar_runtime, "select_local_directory", fake_select_local_directory)

    agent = build_agent_from_config(str(config_path))

    with TestClient(agent.app) as client:
        response = client.get(
            "/api/system/select-directory",
            params={"initial_directory": str(tmp_path / "seed-folder")},
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "success",
        "directory": str(tmp_path / "chosen-storage-folder"),
    }
    assert requested_initial_directory == [str(tmp_path / "seed-folder")]


def test_map_phemar_agent_exposes_local_json_file_routes(tmp_path):
    """
    Exercise the test_map_phemar_agent_exposes_local_json_file_routes regression
    scenario.
    """
    config_path = tmp_path / "map.phemar"
    pool_path = tmp_path / "pool"
    config_path.write_text(
        json.dumps(
            {
                "name": "MapPhemar",
                "type": "phemacast.agents.map_phemar.MapPhemarAgent",
                "host": "127.0.0.1",
                "port": 8142,
                "role": "phemar",
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "map_phemar_pool",
                        "description": "Local pool",
                        "root_path": str(pool_path),
                    }
                ],
                "phemar": {
                    "description": "Standalone map phemar",
                    "supported_phemas": [],
                },
            }
        ),
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))
    target_directory = tmp_path / "direct-json-phemas"

    with TestClient(agent.app) as client:
        save_response = client.post(
            "/api/files/save/local",
            json={
                "directory": str(target_directory),
                "file_name": "diagram-one.json",
                "content": {
                    "phema_id": "phema-1",
                    "name": "Diagram One",
                    "meta": {"map_phemar": {"diagram": {"nodes": [], "edges": []}}},
                },
            },
        )

        assert save_response.status_code == 200
        saved = save_response.json()["file"]
        assert Path(saved["path"]).is_file()

        list_response = client.post(
            "/api/files/list/local",
            json={"directory": str(target_directory)},
        )

        assert list_response.status_code == 200
        files = list_response.json()["files"]
        assert len(files) == 1
        assert files[0]["file_name"] == "diagram-one.json"

        load_response = client.post(
            "/api/files/load/local",
            json={
                "directory": str(target_directory),
                "file_name": "diagram-one.json",
            },
        )

        assert load_response.status_code == 200
        assert load_response.json()["file"]["content"]["name"] == "Diagram One"


def test_demo_map_phemar_diagrams_use_current_shape_ids():
    """
    Exercise the test_demo_map_phemar_diagrams_use_current_shape_ids regression
    scenario.
    """
    diagrams_root = Path(__file__).resolve().parents[2] / "demos" / "files" / "diagrams"
    supported_shape_ids = {"rectangle", "pill", "branch"}
    diagram_files = sorted(diagrams_root.glob("*.json")) + sorted((diagrams_root / "map_phemar" / "pool" / "phemas").glob("*.json"))
    diagram_files.append(diagrams_root / "map_phemar" / "map_phemar.phemar")

    for path in diagram_files:
        if path.name == "_schema.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        diagrams = []
        meta_diagram = (((payload.get("meta") or {}).get("map_phemar") or {}).get("diagram"))
        if isinstance(meta_diagram, dict):
            diagrams.append(meta_diagram)
        supported_phemas = (((payload.get("phemar") or {}).get("supported_phemas")) or [])
        for phema in supported_phemas:
            nested = (((phema.get("meta") or {}).get("map_phemar") or {}).get("diagram"))
            if isinstance(nested, dict):
                diagrams.append(nested)

        for diagram in diagrams:
            node_types = {str(node.get("type") or "").strip() for node in (diagram.get("nodes") or [])}
            assert node_types <= supported_shape_ids, f"{path} contains unsupported node types: {sorted(node_types - supported_shape_ids)}"
