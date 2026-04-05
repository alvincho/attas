"""
Regression tests for Pulser Demo Configs.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_standalone_pulser_demo_configs_instantiate_expected_agents`, helping guard against
regressions as the packages evolve.
"""

import json
import os
import sys
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from attas.pulsers.openai_pulser import OpenAIPulser
from attas.pulsers.yfinance_pulser import YFinancePulser
from phemacast.pulsers.system_pulser import SystemPulser
from phemacast.pulsers.path_pulser import PathPulser


def _repo_root() -> Path:
    """Internal helper for repo root."""
    return Path(__file__).resolve().parents[2]


def _load_json(path: Path) -> dict:
    """Internal helper to load the JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def test_standalone_pulser_demo_configs_instantiate_expected_agents():
    """
    Exercise the test_standalone_pulser_demo_configs_instantiate_expected_agents
    regression scenario.
    """
    root = _repo_root()

    analyst = PathPulser(
        config=str(root / "demos" / "pulsers" / "analyst-insights" / "analyst-insights.pulser"),
        auto_register=False,
    )
    analyst_news_wire = PathPulser(
        config=str(root / "demos" / "pulsers" / "analyst-insights" / "news-wire.pulser"),
        auto_register=False,
    )
    analyst_ollama = OpenAIPulser(
        config=_load_json(root / "demos" / "pulsers" / "analyst-insights" / "ollama.pulser"),
        auto_register=False,
    )
    yfinance = YFinancePulser(
        config=_load_json(root / "demos" / "pulsers" / "yfinance" / "yfinance.pulser"),
        auto_register=False,
    )
    file_storage = SystemPulser(
        config=_load_json(root / "demos" / "pulsers" / "file-storage" / "file-storage.pulser"),
        auto_register=False,
    )
    openai = OpenAIPulser(
        config=_load_json(root / "demos" / "pulsers" / "llm" / "openai.pulser"),
        auto_register=False,
    )
    ollama = OpenAIPulser(
        config=_load_json(root / "demos" / "pulsers" / "llm" / "ollama.pulser"),
        auto_register=False,
    )

    assert analyst.name == "DemoAnalystInsightPulser"
    assert {"rating_summary", "thesis_bullets", "risk_watch", "scenario_grid"}.issubset(
        {pulse["name"] for pulse in analyst.supported_pulses}
    )

    assert analyst_news_wire.name == "DemoAnalystNewsWirePulser"
    assert any(pulse["name"] == "news_article" for pulse in analyst_news_wire.supported_pulses)

    assert analyst_ollama.name == "DemoAnalystOllamaPulser"
    assert analyst_ollama.raw_config["base_url"] == "http://localhost:11434/api/generate"
    assert analyst_ollama.raw_config["model"] == "qwen3:8b"
    assert analyst_ollama.supported_pulses[0]["name"] == "llm_chat"

    assert yfinance.name == "DemoYFinancePulser"
    assert any(pulse["name"] == "ohlc_bar_series" for pulse in yfinance.supported_pulses)

    assert file_storage.name == "DemoSystemPulser"
    assert {"bucket_create", "list_bucket", "object_save", "object_load"}.issubset(
        {pulse["name"] for pulse in file_storage.supported_pulses}
    )

    assert openai.name == "DemoOpenAIPulser"
    assert openai.raw_config["base_url"] == "https://api.openai.com/v1/chat/completions"
    assert openai.raw_config["model"] == "gpt-4o-mini"
    assert openai.supported_pulses[0]["name"] == "llm_chat"

    assert ollama.name == "DemoOllamaPulser"
    assert ollama.raw_config["base_url"] == "http://localhost:11434/api/generate"
    assert ollama.raw_config["model"] == "qwen3:8b"
    assert ollama.supported_pulses[0]["name"] == "llm_chat"
