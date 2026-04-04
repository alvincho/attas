"""
Regression tests for Analyst Insight Pulser Demo.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_analyst_insight_pulser_demo_returns_coverage_error_for_unknown_symbol` and
`test_analyst_insight_pulser_demo_serves_multiple_views`, helping guard against
regressions as the packages evolve.
"""

import os
import sys
from pathlib import Path


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast.pulsers.path_pulser import PathPulser


def _demo_config_path() -> Path:
    """Internal helper to return the demo config path."""
    return (
        Path(__file__).resolve().parents[2]
        / "demos"
        / "pulsers"
        / "analyst-insights"
        / "analyst-insights.pulser"
    )


def test_analyst_insight_pulser_demo_serves_multiple_views():
    """
    Exercise the test_analyst_insight_pulser_demo_serves_multiple_views regression
    scenario.
    """
    pulser = PathPulser(config=str(_demo_config_path()), auto_register=False)

    pulse_names = {pulse["name"] for pulse in pulser.supported_pulses}
    assert {"rating_summary", "thesis_bullets", "risk_watch", "scenario_grid"}.issubset(pulse_names)

    rating = pulser.get_pulse_data({"symbol": "NVDA"}, pulse_name="rating_summary")
    thesis = pulser.get_pulse_data({"symbol": "NVDA"}, pulse_name="thesis_bullets")
    risks = pulser.get_pulse_data({"symbol": "NVDA"}, pulse_name="risk_watch")
    scenarios = pulser.get_pulse_data({"symbol": "NVDA"}, pulse_name="scenario_grid")

    assert rating["analyst"] == "North Harbor Research"
    assert rating["rating_label"] == "outperform"
    assert rating["target_price"] == 1280.0

    assert len(thesis["bullets"]) == 3
    assert thesis["confidence_score"] == 0.84

    assert len(risks["risks"]) == 3
    assert risks["risks"][0]["severity"] == "high"

    assert [entry["case"] for entry in scenarios["scenarios"]] == ["bull", "base", "bear"]
    assert scenarios["scenarios"][1]["fair_value"] == 1280.0


def test_analyst_insight_pulser_demo_returns_coverage_error_for_unknown_symbol():
    """
    Exercise the
    test_analyst_insight_pulser_demo_returns_coverage_error_for_unknown_symbol
    regression scenario.
    """
    pulser = PathPulser(config=str(_demo_config_path()), auto_register=False)

    result = pulser.get_pulse_data({"symbol": "TSLA"}, pulse_name="rating_summary")

    assert "not covered" in result["error"]
    assert result["supported_symbols"] == ["NVDA"]
