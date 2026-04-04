"""
Regression tests for Public Clone Configs.

Attas layers finance-oriented pulse definitions, validation rules, and personal-agent
workflows on top of the shared runtimes. These tests cover Attas-specific pulse
definitions, validation flows, and personal-agent integration points.

The pytest cases in this file document expected behavior through checks such as
`test_public_clone_friendly_attas_configs_build_via_shared_loader`,
`test_public_clone_file_storage_pulser_uses_local_filesystem_backend`, and
`test_public_clone_attas_user_agent_hides_unfinished_components`, helping guard
against regressions as the packages evolve.
"""

import os
import sys
from pathlib import Path

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.pulsers.file_storage_pulser import FileStoragePulser
from prompits.agents.standby import StandbyAgent
from prompits.agents.user import UserAgent
from prompits.tests.test_support import build_agent_from_config


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("config_relpath", "expected_type", "expected_name", "expected_port"),
    [
        ("attas/configs/alice.agent", StandbyAgent, "alice", 8012),
        ("attas/configs/bob.agent", StandbyAgent, "bob2", 8013),
        ("attas/configs/user.agent", UserAgent, "UserAgent", 8014),
        ("attas/configs/attas.user.agent", UserAgent, "attas-user", 8034),
        ("attas/configs/file_storage.pulser", FileStoragePulser, "FileStoragePulser", 8067),
    ],
)
def test_public_clone_friendly_attas_configs_build_via_shared_loader(
    config_relpath, expected_type, expected_name, expected_port
):
    """
    Exercise the
    test_public_clone_friendly_attas_configs_build_via_shared_loader regression
    scenario.
    """
    config_path = ROOT / config_relpath

    agent = build_agent_from_config(str(config_path))

    assert isinstance(agent, expected_type)
    assert agent.name == expected_name
    assert agent.port == expected_port


def test_public_clone_file_storage_pulser_uses_local_filesystem_backend():
    """
    Exercise the
    test_public_clone_file_storage_pulser_uses_local_filesystem_backend
    regression scenario.
    """
    config_path = ROOT / "attas" / "configs" / "file_storage.pulser"

    agent = build_agent_from_config(str(config_path))

    assert isinstance(agent, FileStoragePulser)
    assert agent.backend.backend_type == "filesystem"
    assert agent.storage_config["root_path"] == "tests/storage/file_storage_pulser/content"


def test_public_clone_attas_user_agent_hides_unfinished_components():
    """
    Exercise the
    test_public_clone_attas_user_agent_hides_unfinished_components regression
    scenario.
    """
    config_path = ROOT / "attas" / "configs" / "attas.user.agent"

    agent = build_agent_from_config(str(config_path))

    assert isinstance(agent, UserAgent)
    assert agent.configured_applications == []
