import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from prompits.tests.test_support import build_agent_from_config

@pytest.fixture(scope="module")
def setup_plaza_and_user():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../attas/configs'))
    plaza_cfg = os.path.join(base_dir, "plaza.agent")
    agent = build_agent_from_config(plaza_cfg)
    with TestClient(agent.app) as client:
        yield client

@pytest.mark.asyncio
async def test_user_agent_dashboard(setup_plaza_and_user):
    client = setup_plaza_and_user

    # 1. Verify Plaza-hosted UI root loads
    resp = client.get("/")
    assert resp.status_code == 200, "Plaza UI HTML failed to load."
    assert "Neural Registry" in resp.text, "Plaza UI HTML missing core templates."
    assert "Plaza <span>Map</span>" in resp.text, "Plaza map page heading missing from Plaza UI."
    assert 'data-page="map"' in resp.text, "Map navigation entry missing from Plaza UI."
    assert 'data-draggable="true"' in resp.text, "Map agent nodes are not draggable in Plaza UI."
    assert "Schema &amp; Pulse" in resp.text, "Editor workspace heading missing from Plaza UI."
    assert '<option value="Agent">Agent</option>' in resp.text, "Type filter is missing the grouped Agent option."
    assert '<option value="Pulser">Pulser</option>' not in resp.text, "Pulser should be grouped under Agent in the monitor filter."
    print("Plaza root UI loaded successfully.")
    
    # 2. Verify Plaza-hosted status endpoint exposes registry entries without UserAgent mediation
    resp = client.get("/api/plazas_status")
    assert resp.status_code == 200, "Plaza status endpoint returned error."
    
    data = resp.json()
    assert data.get("status") == "success", "Status payload missing success param."
    plazas = data.get("plazas", [])
    assert len(plazas) > 0, "No plazas found attached."
    
    plaza_obj = plazas[0]
    assert plaza_obj.get("online") is True, "Plaza was not recognized as online."
    
    # Ensure Plaza and its seeded schemas are present in the Plaza directory
    agents = plaza_obj.get("agents", [])
    agents_names = [a.get("name") if isinstance(a, dict) else a[0] for a in agents]
    assert "Plaza" in agents_names, "Plaza failed to self-register in its own directory."
    assert any(name.startswith("Schema:") for name in agents_names), "Built-in Schema entries missing from Plaza directory."
    plaza_agent = next(a for a in agents if isinstance(a, dict) and a.get("name") == "Plaza")
    plaza_practices = (plaza_agent.get("card") or {}).get("practices", [])
    search_practice = next((p for p in plaza_practices if p.get("id") == "search"), None)
    assert search_practice is not None, "Plaza search practice missing from agent card."
    assert search_practice.get("cost") == 0, "Practice cost should default to 0."
    print("Plaza status endpoint exposed self-registered and built-in registry entries successfully.")

    # 3. Verify type filter passthrough to Plaza search
    filtered = client.get("/api/plazas_status?pit_type=Schema")
    assert filtered.status_code == 200, "Type-filtered Plaza status endpoint returned error."
    filtered_data = filtered.json()
    filtered_agents = filtered_data.get("plazas", [])[0].get("agents", [])
    assert len(filtered_agents) > 0, "Schema filter should include registered Schema pits."
    assert all((a.get("pit_type") == "Schema") for a in filtered_agents if isinstance(a, dict))
