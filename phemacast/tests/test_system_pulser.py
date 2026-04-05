"""
Regression tests for System Pulser.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_system_pulser_reads_local_text_files`,
`test_system_pulser_reads_remote_json_payloads`, and
`test_system_pulser_supports_file_storage_operations`, helping guard against
regressions as the packages evolve.
"""

import json
import os
import sys
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.pulsers.system_pulser import SystemPulser
from prompits.tests.test_support import build_agent_from_config


ROOT = Path(__file__).resolve().parents[2]


class FakeResponse:
    """Response model for fake URL payloads."""

    def __init__(self, payload: bytes, *, status_code: int = 200, headers: dict | None = None):
        """Initialize the fake response."""
        self.content = payload
        self.status_code = status_code
        self.headers = headers or {}


def test_system_pulser_reads_local_text_files(tmp_path):
    """
    Exercise the test_system_pulser_reads_local_text_files regression scenario.
    """
    source_path = tmp_path / "hello.txt"
    source_path.write_text("hello system pulser", encoding="utf-8")

    pulser = SystemPulser(auto_register=False)

    result = pulser.get_pulse_data({"local_path": str(source_path)}, pulse_name="file")

    assert result == {"format": "text", "content": "hello system pulser"}


def test_system_pulser_reads_remote_json_payloads(monkeypatch):
    """
    Exercise the test_system_pulser_reads_remote_json_payloads regression scenario.
    """

    def fake_get(url, timeout=30):
        """Handle fake get."""
        assert url == "https://example.test/report.json"
        assert timeout == 30.0
        return FakeResponse(
            json.dumps({"symbol": "AAPL", "status": "ok"}).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

    monkeypatch.setattr("phemacast.pulsers.system_pulser.requests.get", fake_get)

    pulser = SystemPulser(auto_register=False)

    result = pulser.get_pulse_data({"url": "https://example.test/report.json"}, pulse_name="file")

    assert result == {
        "format": "json",
        "content": {"symbol": "AAPL", "status": "ok"},
    }


def test_system_pulser_builds_from_config_with_system_party_defaults(tmp_path):
    """
    Exercise the
    test_system_pulser_builds_from_config_with_system_party_defaults regression
    scenario.
    """
    local_file = tmp_path / "relative-note.md"
    local_file.write_text("# Relative\n\nWorks from config dir.", encoding="utf-8")

    config_path = tmp_path / "system.pulser"
    config_path.write_text(
        json.dumps(
            {
                "name": "ConfigSystemPulser",
                "type": "phemacast.pulsers.system_pulser.SystemPulser",
                "host": "127.0.0.1",
                "port": 8128,
                "party": "System",
                "description": "Demo system pulser",
                "storage": {
                    "type": "filesystem",
                    "root_path": str(tmp_path / "content"),
                },
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "system_pulser_pool",
                        "description": "test pool",
                        "root_path": str(tmp_path / "agent_pool"),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    agent = build_agent_from_config(str(config_path))
    result = agent.get_pulse_data({"local_path": "relative-note.md"}, pulse_name="file")
    supported_pulses = agent.agent_card["meta"]["supported_pulses"]
    file_pulse = next(pulse for pulse in supported_pulses if pulse["name"] == "file")

    assert isinstance(agent, SystemPulser)
    assert agent.name == "ConfigSystemPulser"
    assert agent.port == 8128
    assert agent.agent_card["party"] == "System"
    assert agent.backend.backend_type == "filesystem"
    assert agent.storage_config["root_path"] == str(tmp_path / "content")
    assert file_pulse["party"] == "System"
    assert file_pulse["output_schema"]["required"] == ["format", "content"]
    assert any(pulse["name"] == "bucket_create" for pulse in supported_pulses)
    assert any(pulse["name"] == "object_load" for pulse in supported_pulses)
    assert result == {
        "format": "text",
        "content": "# Relative\n\nWorks from config dir.",
    }


def test_system_pulser_supports_file_storage_operations(tmp_path):
    """
    Exercise the test_system_pulser_supports_file_storage_operations regression
    scenario.
    """
    pulser = SystemPulser(
        config={
            "storage": {
                "type": "filesystem",
                "root_path": str(tmp_path / "content"),
            }
        },
        auto_register=False,
    )

    created = pulser.get_pulse_data(
        {
            "bucket_name": "system-assets",
            "visibility": "public",
            "_caller": {"agent_id": "agent-a", "agent_name": "Agent A"},
        },
        pulse_name="bucket_create",
    )
    saved = pulser.get_pulse_data(
        {
            "bucket_name": "system-assets",
            "object_key": "docs/sample.json",
            "data": {"status": "ok", "source": "system"},
            "_caller": {"agent_id": "agent-a", "agent_name": "Agent A"},
        },
        pulse_name="object_save",
    )
    loaded = pulser.get_pulse_data(
        {
            "bucket_name": "system-assets",
            "object_key": "docs/sample.json",
            "response_format": "json",
            "_caller": {"agent_id": "agent-b", "agent_name": "Agent B"},
        },
        pulse_name="object_load",
    )

    assert created["status"] == "created"
    assert created["storage_backend"] == "filesystem"
    assert saved["status"] == "saved"
    assert saved["payload_format"] == "json"
    assert loaded["data"] == {"source": "system", "status": "ok"}


def test_build_agent_from_shipped_phemacast_system_config():
    """
    Exercise the
    test_build_agent_from_shipped_phemacast_system_config regression scenario.
    """
    config_path = ROOT / "phemacast" / "configs" / "system.pulser"

    agent = build_agent_from_config(str(config_path))

    assert isinstance(agent, SystemPulser)
    assert agent.name == "SystemPulser"
    assert agent.port == 8068
    assert agent.agent_card["party"] == "System"
    assert agent.backend.backend_type == "filesystem"
    assert agent.storage_config["root_path"] == "tests/storage/system_pulser/content"
    assert any(pulse["name"] == "file" for pulse in agent.supported_pulses)
    assert any(pulse["name"] == "bucket_create" for pulse in agent.supported_pulses)
