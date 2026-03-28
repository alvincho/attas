import os
import sys

from fastapi.testclient import TestClient


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from attas.personal_agent.app import app


client = TestClient(app)


def test_personal_agent_root_renders_dashboard_shell():
    response = client.get("/")

    assert response.status_code == 200
    assert "attas Personal Agent" in response.text
    assert "New Workspace" in response.text
    assert "New Browser Window" in response.text
    assert "Settings" in response.text
    assert "Front Page" in response.text
    assert "Workspace Dock" in response.text
    assert "personal_agent.js?v=" in response.text


def test_personal_agent_dashboard_api_returns_expected_sections():
    response = client.get("/api/dashboard")

    assert response.status_code == 200
    payload = response.json()

    assert payload["meta"]["application"] == "attas Personal Agent"
    assert len(payload["watchlist"]) >= 4
    assert len(payload["providers"]) >= 3
    assert len(payload["workspaces"]) >= 2
    assert len(payload["browser"]["bookmarks"]) >= 3


def test_personal_agent_workspace_detail_returns_404_for_unknown_workspace():
    response = client.get("/api/workspaces/unknown")

    assert response.status_code == 404
