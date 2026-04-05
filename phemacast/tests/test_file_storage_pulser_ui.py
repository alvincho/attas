"""
Regression tests for System Pulser UI.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_system_pulser_uses_dedicated_storage_editor`, helping guard against
regressions as the packages evolve.
"""

import json
import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.tests.test_support import build_agent_from_config


def test_system_pulser_uses_dedicated_storage_editor(tmp_path, monkeypatch):
    """
    Exercise the test_system_pulser_uses_dedicated_storage_editor regression
    scenario.
    """
    pool_dir = tmp_path / "storage"
    config_path = tmp_path / "demo_file_storage.pulser"
    config_path.write_text(
        json.dumps(
            {
                "name": "DemoSystemPulser",
                "type": "phemacast.pulsers.system_pulser.SystemPulser",
                "host": "127.0.0.1",
                "port": 8127,
                "party": "System",
                "description": "Demo storage pulser",
                "tags": ["storage", "system"],
                "storage": {
                    "type": "filesystem",
                    "root_path": str(tmp_path / "content"),
                },
                "pools": [
                    {
                        "type": "FileSystemPool",
                        "name": "demo_pool",
                        "description": "test pool",
                        "root_path": str(pool_dir),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "phemacast.pulsers.system_pulser.boto3.client",
        lambda *args, **kwargs: object(),
    )

    agent = build_agent_from_config(str(config_path))

    with TestClient(agent.app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "DemoSystemPulser Storage Console" in root.text
        assert "Backend Storage" in root.text
        assert "Filesystem Root Path" in root.text
        assert "Backing S3 Bucket" in root.text
        assert "Supported Pulses" in root.text
        assert "Saved Preview" in root.text
        assert "Pulse Definition" in root.text
        assert "Pulse Test" in root.text
        assert "Test Data" in root.text
        assert 'type="file"' in root.text
        assert "Choose a local PDF, video, image, audio file, or other blob" in root.text
        assert "max-height: calc(10 * 1.65em + 32px);" in root.text
        assert "collapse-toggle" in root.text
        assert "data-collapsible" in root.text
        assert '<div id="test-runner-modal-root"></div>' in root.text

        current = client.get("/api/config")
        assert current.status_code == 200
        payload = current.json()["config"]
        bucket_create_pulse = next(pulse for pulse in payload["supported_pulses"] if pulse["name"] == "bucket_create")
        assert payload["name"] == "DemoSystemPulser"
        assert payload["storage"]["type"] == "filesystem"
        assert payload["storage"]["root_path"] == str(tmp_path / "content")
        assert bucket_create_pulse["pulse_definition"]["resource_type"] == "pulse_definition"
        assert bucket_create_pulse["test_data"]["bucket_name"] == "demo-assets"
        assert any(pulse["name"] == "list_bucket" for pulse in payload["supported_pulses"])

        tested = client.post(
            "/api/test-pulse",
            json={
                "config": payload,
                "pulse_name": "bucket_create",
                "params": {"bucket_name": "ui-test-bucket", "visibility": "public"},
                "debug": True,
            },
        )
        assert tested.status_code == 200
        tested_payload = tested.json()
        assert tested_payload["status"] == "success"
        assert tested_payload["result"]["status"] == "created"
        assert tested_payload["debug"]["pulse_definition"]["name"] == "bucket_create"
        assert tested_payload["debug"]["storage_backend"] == "filesystem"

        payload["description"] = "Updated storage pulser"
        payload["storage"] = {
            "type": "s3",
            "bucket": "demo-backend-root",
            "prefix": "workspace-a/file-storage",
            "region_name": "us-east-1",
            "endpoint_url": "https://s3.example.test",
        }

        saved = client.post("/api/config", json={"config": payload})
        assert saved.status_code == 200
        saved_payload = saved.json()["config"]
        assert saved_payload["description"] == "Updated storage pulser"
        assert saved_payload["storage"]["type"] == "s3"
        assert saved_payload["storage"]["bucket"] == "demo-backend-root"
        assert saved_payload["storage"]["prefix"] == "workspace-a/file-storage"

        reloaded = client.get("/api/config")
        assert reloaded.status_code == 200
        reloaded_payload = reloaded.json()["config"]
        assert reloaded_payload["storage"]["type"] == "s3"
        assert agent.agent_card["meta"]["storage_backend"] == "s3"
        assert agent.agent_card["meta"]["storage_bucket"] == "demo-backend-root"
