import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.agents.castr import Castr
from fastapi.testclient import TestClient

def test_castr_list_plaza_phemas_uses_search_and_formats_results():
    # Setup Castr with a plaza_url
    castr = Castr(
        name="TestCastr",
        plaza_url="http://127.0.0.1:8011",
        auto_register=False
    )

    # Mock data returned by Plaza search (simulating Plaza directory entries)
    mock_search_results = [
        {
            "agent_id": "phema-uuid-123",
            "name": "Market Summary",
            "description": "Daily market overview",
            "owner": "MacroPhemar",
            "card": {
                "phema_id": "market-summary-template",
                "name": "Market Summary",
                "sections": [{"name": "Topline", "content": []}]
            }
        },
        {
            "agent_id": "phema-no-card-id",
            "name": "Quick Pulse",
            "card": {
                "name": "Quick Pulse",
                "sections": []
            }
        }
    ]

    # Patch the search method of Castr (inherited from BaseAgent)
    # This avoids actual network calls and verifies the interaction.
    with patch.object(castr, "search", return_value=mock_search_results) as mocked_search:
        client = TestClient(castr.app)
        
        response = client.get("/api/plazas/phemas")
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success", f"Error from Castr: {data.get('message')}"
        assert len(data["phemas"]) == 2
        
        # Test Case 1: Full card with phema_id
        phema1 = data["phemas"][0]
        assert phema1["name"] == "Market Summary"
        assert phema1["description"] == "Daily market overview"
        assert phema1["owner"] == "MacroPhemar"
        assert phema1["phema_id"] == "market-summary-template"
        assert "sections" in phema1

        # Test Case 2: Fallback to agent_id
        phema2 = data["phemas"][1]
        assert phema2["name"] == "Quick Pulse"
        assert phema2["phema_id"] == "phema-no-card-id"
        
        # Verify it called the correct search parameters
        mocked_search.assert_called_once_with(pit_type="Phema")

def test_castr_list_plaza_phemas_without_plaza_url():
    castr = Castr(
        name="NoPlazaCastr",
        plaza_url=None,
        auto_register=False
    )
    client = TestClient(castr.app)
    response = client.get("/api/plazas/phemas")
    assert response.status_code == 200
    assert response.json()["phemas"] == []
