"""
Regression tests for OpenAI Pulser UI.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_openai_pulser_uses_shared_editor_template`, helping guard against regressions as
the packages evolve.
"""

import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.tests.test_support import build_agent_from_config


class FakeLLMResponse:
    """Response model for fake LLM payloads."""
    def raise_for_status(self):
        """Return the raise for the status."""
        return None

    def json(self):
        """Handle JSON for the fake LLM response."""
        return {
            "choices": [
                {
                    "message": {
                        "content": "Hello from OpenAI.",
                    }
                }
            ]
        }


class FakeModelListResponse:
    """Response model for fake model list payloads."""
    def raise_for_status(self):
        """Return the raise for the status."""
        return None

    def json(self):
        """Handle JSON for the fake model list response."""
        return {
            "data": [
                {"id": "gpt-4o-mini"},
                {"id": "gpt-4o"},
            ]
        }


def test_openai_pulser_uses_shared_editor_template(tmp_path, monkeypatch):
    """
    Exercise the test_openai_pulser_uses_shared_editor_template regression scenario.
    """
    pool_dir = tmp_path / "storage"
    config_path = tmp_path / "demo_openai.pulser"
    config_path.write_text(
        json.dumps(
            {
                "name": "DemoOpenAIPulser",
                "type": "attas.pulsers.openai_pulser.OpenAIPulser",
                "host": "127.0.0.1",
                "port": 8126,
                "description": "Demo OpenAI pulser",
                "tags": ["llm", "openai"],
                "api_key": "demo-key",
                "model": "gpt-4o-mini",
                "base_url": "https://api.openai.com/v1/chat/completions",
                "supported_pulses": [
                    {
                        "name": "llm_chat",
                        "description": "Shared editor chat pulse",
                        "pulse_address": "plaza://pulse/llm_chat",
                        "input_schema": {
                            "type": "object",
                            "properties": {
                                "prompt": {"type": "string"},
                                "model": {"type": "string"},
                            },
                            "required": ["prompt"],
                        },
                        "output_schema": {
                            "type": "object",
                            "properties": {
                                "response": {"type": "string"},
                                "model": {"type": "string"},
                                "provider": {"type": "string"},
                            },
                        },
                        "mapping": {
                            "response": "response",
                            "model": "model",
                            "provider": "provider",
                        },
                        "test_data": {
                            "prompt": "Say hello.",
                            "model": "gpt-4o-mini",
                        },
                    }
                ],
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
        "attas.pulsers.openai_pulser.requests.post",
        lambda url, headers=None, json=None, timeout=240: FakeLLMResponse(),
    )
    monkeypatch.setattr(
        "attas.pulsers.openai_pulser.requests.get",
        lambda url, headers=None, timeout=5: FakeModelListResponse(),
    )

    agent = build_agent_from_config(str(config_path))

    with TestClient(agent.app) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "DemoOpenAIPulser Config" in root.text
        assert "Search Supported Pulses" in root.text
        assert "APIsPulser Details" in root.text
        assert "Pulse Details" in root.text
        assert "Model Tools" in root.text
        assert "Load Models" in root.text
        assert "Model Info" in root.text
        assert '<div id="config-preview" class="json-tree-shell"></div>' in root.text
        assert '<div class="json-tree-shell compact" id="openai-model-info-output"></div>' in root.text

        models = client.get("/list_models", params={"provider": "openai"})
        assert models.status_code == 200
        models_payload = models.json()
        assert models_payload["status"] == "success"
        assert "gpt-4o-mini" in models_payload["models"]

        current = client.get("/api/config")
        assert current.status_code == 200
        payload = current.json()["config"]
        assert payload["name"] == "DemoOpenAIPulser"
        assert payload["supported_pulses"][0]["api"]["url"] == "https://api.openai.com/v1/chat/completions"
        assert payload["supported_pulses"][0]["test_data"]["model"] == "gpt-4o-mini"

        invalid_payload = json.loads(json.dumps(payload))
        invalid_payload["supported_pulses"][0]["test_data"] = {}
        invalid_save = client.post("/api/config", json={"config": invalid_payload})
        assert invalid_save.status_code == 400
        assert "at least one set of test parameters" in invalid_save.json()["detail"]

        tested = client.post(
            "/api/test-pulse",
            json={
                "config": payload,
                "pulse_name": "llm_chat",
                "params": {"prompt": "Say hello.", "model": "gpt-4o-mini"},
                "debug": True,
            },
        )
        assert tested.status_code == 200
        tested_payload = tested.json()
        assert tested_payload["status"] == "success"
        assert tested_payload["result"]["response"] == "Hello from OpenAI."
        assert tested_payload["result"]["provider"] == "openai"
        assert tested_payload["debug"]["pulse_definition"]["name"] == "llm_chat"
        assert tested_payload["debug"]["fetch"]["base_url"] == "https://api.openai.com/v1/chat/completions"
