"""
Regression tests for User UI.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_user_agent_dashboard`, helping guard against regressions as the packages evolve.
"""

import sys
import os
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from prompits.tests.test_support import build_agent_from_config

@pytest.fixture(scope="module")
def setup_plaza_and_user():
    """Set up the Plaza and user."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'fixtures/configs'))
    plaza_cfg = os.path.join(base_dir, "plaza.agent")
    agent = build_agent_from_config(plaza_cfg)
    with TestClient(agent.app) as client:
        yield client

@pytest.mark.asyncio
async def test_user_agent_dashboard(setup_plaza_and_user):
    """Exercise the test_user_agent_dashboard regression scenario."""
    client = setup_plaza_and_user

    # 1. Verify Plaza-hosted UI root loads
    resp = client.get("/")
    assert resp.status_code == 200, "Plaza UI HTML failed to load."
    assert "Plaza Registry" in resp.text, "Plaza UI HTML missing core templates."
    assert 'class="logo-icon"' not in resp.text, "Legacy sidebar logo should be removed from Plaza UI."
    assert 'class="sidebar-wordmark">attas</h3>' in resp.text, "Sidebar wordmark should render as a single readable attas label."
    assert "Plaza <span>Map</span>" in resp.text, "Plaza map page heading missing from Plaza UI."
    assert 'data-page="map"' in resp.text, "Map navigation entry missing from Plaza UI."
    assert 'data-admin-nav="1"' in resp.text, "Admin-only sidebar markers should be present in Plaza UI."
    assert 'data-page="profile"' in resp.text, "Profile navigation entry missing from Plaza UI."
    assert "Account <span>Profile</span>" in resp.text, "Profile page heading missing from Plaza UI."
    assert 'data-draggable="true"' in resp.text, "Map agent nodes are not draggable in Plaza UI."
    assert "Schema &amp; Pulse" in resp.text, "Editor workspace heading missing from Plaza UI."
    assert "Refresh Registry" in resp.text, "Monitor refresh action should use the updated Registry label."
    assert '<option value="Agent">Agent</option>' in resp.text, "Type filter is missing the Agent option."
    assert '<option value="AgentConfig">AgentConfig</option>' in resp.text, "Type filter is missing the AgentConfig option."
    assert '<option value="Pulser">Pulser</option>' in resp.text, "Type filter is missing the Pulser option."
    assert "function syncTypeFilterOptions()" in resp.text, "Type filter should repopulate itself from live registry kinds."
    assert "function syncRoleBasedUi()" in resp.text, "Role-based sidebar hiding should be present in Plaza UI."
    assert "function matchesMonitorTypeFilter(" in resp.text, "Agent filter should support grouped runtime PIT matching."
    assert "const AGENT_RUNTIME_TYPES = new Set(['Agent', 'Pulser', 'Phemar', 'Castr'])" in resp.text, "Agent grouping should include Phemar but exclude non-runtime types like Phema."
    assert "Refreshing..." in resp.text, "Registry refresh busy label should be present in Plaza UI."
    assert "plaza.ui.currentUser" in resp.text, "Current signed-in user should be cached for browser refresh recovery."
    assert "plaza.ui.plazasCache" in resp.text, "Last Plaza registry snapshot should be cached for browser refresh recovery."
    assert "plaza.ui.mapLayouts" in resp.text, "Map node positions should be cached across browser refreshes."
    assert "function persistRegistryCache()" in resp.text, "Registry cache persistence helper should be present in Plaza UI."
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
