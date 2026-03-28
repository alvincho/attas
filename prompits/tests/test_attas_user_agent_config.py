import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.agents.user import UserAgent
from prompits.tests.test_support import build_agent_from_config


def test_attas_user_agent_config_builds_via_create_agent_loader():
    config_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../attas/configs/attas.user.agent")
    )

    agent = build_agent_from_config(config_path)

    assert isinstance(agent, UserAgent)
    assert agent.name == "attas-user"
    assert agent.port == 8034
    assert agent.user_plaza_urls == ["http://127.0.0.1:8011"]
    assert len(agent.configured_applications) == 1
    assert agent.configured_applications[0]["name"] == "Stock Report"
