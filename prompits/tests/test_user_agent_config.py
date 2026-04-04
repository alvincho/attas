"""
Regression tests for User Agent Config.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_user_agent_config_builds_via_create_agent_loader`, helping guard against
regressions as the packages evolve.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.agents.user import UserAgent
from prompits.tests.test_support import build_agent_from_config


def test_user_agent_config_builds_via_create_agent_loader():
    """
    Exercise the test_user_agent_config_builds_via_create_agent_loader
    regression scenario.
    """
    config_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "fixtures/configs/user.agent")
    )

    agent = build_agent_from_config(config_path)

    assert isinstance(agent, UserAgent)
    assert agent.name == "user-agent"
    assert agent.port == 8034
    assert agent.user_plaza_urls == ["http://127.0.0.1:8011"]
    assert agent.configured_applications == []
