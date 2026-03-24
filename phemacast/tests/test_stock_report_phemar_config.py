import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.tests.test_support import build_agent_from_config


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def test_stock_report_phemar_config_loads_via_shared_agent_factory():
    config_path = Path(__file__).resolve().parents[2] / "attas" / "configs" / "stock_report.phemar"
    sent_payloads = []

    def fake_post(url, json=None, timeout=5, **kwargs):
        sent_payloads.append({"url": url, "payload": dict(json or {}), "timeout": timeout})
        return FakeResponse(
            {
                "status": "registered",
                "token": "stock-report-token",
                "expires_in": 3600,
                "agent_id": "stock-report-phemar-id",
                "api_key": "stock-report-phemar-key",
            }
        )

    with patch("prompits.agents.base.requests.post", side_effect=fake_post):
        agent = build_agent_from_config(str(config_path))

    assert agent.name == "StockReportPhemar"
    assert agent.port == 8026
    assert agent.agent_id == "stock-report-phemar-id"
    assert sent_payloads[0]["url"] == "http://127.0.0.1:8011/register"
    assert sent_payloads[0]["payload"]["pit_type"] == "Agent"

    practice_by_id = {entry["id"]: entry for entry in agent.agent_card["practices"]}
    assert "generate_phema" in practice_by_id
    assert "snapshot_phema" in practice_by_id

    supported_phemas = agent.agent_card["meta"]["supported_phemas"]
    assert supported_phemas
    assert supported_phemas[0]["phema_id"]
    assert supported_phemas[0]["name"]
    assert isinstance(supported_phemas[0]["sections"], list)
