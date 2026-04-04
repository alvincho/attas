"""
Regression tests for Analyst Prompted News Pulser Demo.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_prompted_news_pulser_turns_upstream_news_into_multiple_views` and
`test_seeded_news_wire_demo_returns_articles`, helping guard against regressions as the
packages evolve.
"""

import json
import os
import sys
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.pulsers.path_pulser import PathPulser


class FakePostResponse:
    """Response model for fake post payloads."""
    def __init__(self, payload, status_code=200):
        """Initialize the fake post response."""
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)
        self.content = self.text.encode("utf-8")

    def json(self):
        """Handle JSON for the fake post response."""
        return self._payload


def _demo_root() -> Path:
    """Internal helper for demo root."""
    return Path(__file__).resolve().parents[2] / "demos" / "pulsers" / "analyst-insights"


def test_seeded_news_wire_demo_returns_articles():
    """Exercise the test_seeded_news_wire_demo_returns_articles regression scenario."""
    pulser = PathPulser(config=str(_demo_root() / "news-wire.pulser"), auto_register=False)

    result = pulser.get_pulse_data({"symbol": "NVDA", "number_of_articles": 2}, pulse_name="news_article")

    assert result["symbol"] == "NVDA"
    assert result["source"] == "demo_news_wire"
    assert result["number_of_articles"] == 2
    assert len(result["articles"]) == 2
    assert result["articles"][0]["headline"] == "Nvidia expands sovereign AI pipeline with new Gulf cloud project"


def test_prompted_news_pulser_turns_upstream_news_into_multiple_views(monkeypatch):
    """
    Exercise the test_prompted_news_pulser_turns_upstream_news_into_multiple_views
    regression scenario.
    """
    def fake_post(url, json=None, timeout=30):
        """Handle fake post."""
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
                    "sentiment_label": "positive",
                },
                {
                    "headline": "Export-control debate reopens questions on geographic mix durability",
                    "published_at": "2026-04-01T23:45:00Z",
                    "publisher": "Policy Desk",
                    "summary": "Policy commentary highlights a potential risk to regional mix and visibility.",
                    "url": "https://example.test/news/nvda-export-control-risk",
                    "sentiment_label": "mixed",
                },
            ]
            return FakePostResponse(
                {
                    "symbol": symbol,
                    "number_of_articles": min(count, len(articles)),
                    "articles": articles[:count],
                    "source": "demo_news_wire",
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
                    ],
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
                    ],
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
                    ],
                }
            else:
                raise AssertionError(f"Unexpected prompt profile inside prompt: {prompt}")

            return FakePostResponse(
                {
                    "response": json_module.dumps(payload),
                    "model": params.get("model") or "qwen3:8b",
                    "provider": "ollama",
                }
            )

        raise AssertionError(f"Unexpected source call: {url} -> {pulse_name}")

    json_module = json
    monkeypatch.setattr("phemacast.pulsers.path_pulser.requests.post", fake_post)

    pulser = PathPulser(config=str(_demo_root() / "analyst-news-ollama.pulser"), auto_register=False)

    desk = pulser.get_pulse_data({"symbol": "NVDA", "number_of_articles": 2}, pulse_name="news_desk_brief")
    monitoring = pulser.get_pulse_data({"symbol": "NVDA", "number_of_articles": 2}, pulse_name="news_monitoring_points")
    client_note = pulser.get_pulse_data({"symbol": "NVDA", "number_of_articles": 2}, pulse_name="news_client_note")

    assert desk["prompt_profile"] == "desk_brief"
    assert desk["provider"] == "ollama"
    assert desk["stance"] == "outperform"
    assert len(desk["key_points"]) == 3

    assert monitoring["prompt_profile"] == "monitoring_points"
    assert monitoring["changed_view"].startswith("Demand remains constructive")
    assert len(monitoring["monitor_now"]) == 2
    assert len(monitoring["risk_flags"]) == 2

    assert client_note["prompt_profile"] == "client_note"
    assert client_note["subject_line"] == "NVDA news check: demand still solid, policy risk stays in focus"
    assert len(client_note["action_items"]) == 2
