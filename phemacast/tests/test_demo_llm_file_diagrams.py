"""
Regression tests for Demo LLM File Diagrams.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_demo_llm_file_diagrams_execute_against_prompted_news_pulser`, helping guard
against regressions as the packages evolve.
"""

import json
import os
import sys
from pathlib import Path

import pytest


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.map_phemar.executor import execute_map_phema
from phemacast.pulsers.path_pulser import PathPulser


class FakeResponse:
    """Response model for fake payloads."""
    def __init__(self, payload, status_code=200):
        """Initialize the fake response."""
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")

    def json(self):
        """Handle JSON for the fake response."""
        return self._payload


def _repo_root() -> Path:
    """Internal helper for repo root."""
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict:
    """Internal helper to load the JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def _fake_prompted_news_upstream(url, json=None, timeout=30):
    """Internal helper for fake prompted news upstream."""
    pulse_name = json["content"]["pulse_name"]
    params = json["content"]["params"]

    if pulse_name == "news_article":
        symbol = params["symbol"]
        count = int(params.get("number_of_articles") or 2)
        articles = [
            {
                "headline": "Nvidia expands sovereign AI pipeline with new Gulf cloud project",
                "published_at": "2026-04-02T07:10:00Z",
                "publisher": "SignalWire Markets",
                "summary": "A new sovereign AI buildout points to another quarter of strong accelerator and networking demand.",
                "url": "https://example.test/news/nvda-sovereign-ai-pipeline",
                "sentiment_label": "positive"
            },
            {
                "headline": "Export-control debate reopens questions on geographic mix durability",
                "published_at": "2026-04-01T23:45:00Z",
                "publisher": "Policy Desk",
                "summary": "Policy commentary highlights a potential risk to regional mix and visibility.",
                "url": "https://example.test/news/nvda-export-control-risk",
                "sentiment_label": "mixed"
            }
        ]
        return FakeResponse(
            {
                "symbol": symbol,
                "number_of_articles": min(count, len(articles)),
                "articles": articles[:count],
                "source": "demo_news_wire"
            }
        )

    if pulse_name == "llm_chat":
        prompt = params["prompt"]
        if "Prompt Profile: desk_brief" in prompt:
            payload = {
                "stance": "outperform",
                "confidence_label": "high",
                "desk_note": "The news flow supports a still-constructive demand setup with policy risk worth monitoring rather than thesis-breaking today.",
                "key_points": [
                    "Sovereign AI demand adds another data point supporting durable accelerator demand.",
                    "Networking attach remains part of the system value story.",
                    "Policy noise is the main near-term watch item."
                ],
                "citations": [
                    "Nvidia expands sovereign AI pipeline with new Gulf cloud project",
                    "Export-control debate reopens questions on geographic mix durability"
                ]
            }
        elif "Prompt Profile: monitoring_points" in prompt:
            payload = {
                "changed_view": "Demand remains constructive, but policy risk moves higher on the watchlist.",
                "monitor_now": [
                    "Management comments on regional backlog composition.",
                    "Any update to export-control scope or compliance process."
                ],
                "risk_flags": [
                    "Geographic mix could become less durable if controls tighten.",
                    "Investor expectations may already discount a clean demand runway."
                ],
                "citations": [
                    "Nvidia expands sovereign AI pipeline with new Gulf cloud project",
                    "Export-control debate reopens questions on geographic mix durability"
                ]
            }
        elif "Prompt Profile: client_note" in prompt:
            payload = {
                "subject_line": "NVDA news check: demand still solid, policy risk stays in focus",
                "client_note": "Today's coverage keeps the demand story constructive while reminding us that policy headlines can still affect the near-term debate.",
                "action_items": [
                    "Watch management commentary on regional demand mix.",
                    "Track whether policy headlines change order visibility."
                ],
                "citations": [
                    "Nvidia expands sovereign AI pipeline with new Gulf cloud project",
                    "Export-control debate reopens questions on geographic mix durability"
                ]
            }
        else:
            raise AssertionError(f"Unexpected prompt profile inside prompt: {prompt}")

        return FakeResponse(
            {
                "response": json_module.dumps(payload),
                "model": params.get("model") or "qwen3:8b",
                "provider": "ollama"
            }
        )

    raise AssertionError(f"Unexpected source call: {url} -> {pulse_name}")


json_module = json


@pytest.mark.parametrize(
    ("filename", "pulse_name", "step_title"),
    [
        ("analyst-news-desk-brief-diagram.json", "news_desk_brief", "News Desk Brief"),
        ("analyst-news-monitoring-points-diagram.json", "news_monitoring_points", "Monitoring Points"),
        ("analyst-news-client-note-diagram.json", "news_client_note", "Client Note")
    ],
)
def test_demo_llm_file_diagrams_execute_against_prompted_news_pulser(monkeypatch, filename: str, pulse_name: str, step_title: str):
    """
    Exercise the test_demo_llm_file_diagrams_execute_against_prompted_news_pulser
    regression scenario.
    """
    root = _repo_root()
    phema = _load_json(root / "demos" / "files" / "diagrams" / filename)
    pulser = PathPulser(
        config=str(root / "demos" / "pulsers" / "analyst-insights" / "analyst-news-ollama.pulser"),
        auto_register=False,
    )
    monkeypatch.setattr("phemacast.pulsers.path_pulser.requests.post", _fake_prompted_news_upstream)
    calls = []

    def fake_map_post(url, json=None, timeout=None):
        """Handle fake map post."""
        assert url == "http://127.0.0.1:8266/api/pulsers/test"
        assert isinstance(json, dict)
        calls.append(json["pulse_name"])
        assert json["pulser_name"] == "DemoAnalystPromptedNewsPulser"
        assert json["pulse_name"] == pulse_name
        return FakeResponse(
            {
                "status": "success",
                "result": pulser.get_pulse_data(dict(json["input"]), pulse_name=pulse_name)
            }
        )

    input_data = {
        "symbol": "NVDA",
        "number_of_articles": 2,
        "model": "qwen3:8b"
    }
    result = execute_map_phema(
        phema,
        input_data=input_data,
        request_post=fake_map_post,
    )
    expected_output = pulser.get_pulse_data(dict(input_data), pulse_name=pulse_name)

    assert calls == [pulse_name]
    assert result["status"] == "success"
    assert result["output"] == expected_output
    assert [step["title"] for step in result["steps"]] == ["Input", step_title, "Output"]
