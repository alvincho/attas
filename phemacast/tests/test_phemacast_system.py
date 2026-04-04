"""
Regression tests for Phemacast System.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. These tests protect the Phemacast pipeline, demo flows, UI
helpers, and pulser integrations.

The pytest cases in this file document expected behavior through checks such as
`test_multi_agent_collaboration_and_markdown_cast` and
`test_viewer_selects_json_format_and_persona_override`, helping guard against
regressions as the packages evolve.
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from phemacast import Persona, PhemacastSystem


def test_multi_agent_collaboration_and_markdown_cast():
    """
    Exercise the test_multi_agent_collaboration_and_markdown_cast regression
    scenario.
    """
    system = PhemacastSystem()

    system.register_pulse_source("summary", lambda ctx: {"value": f"Brief for {ctx['symbol']}"})
    system.register_pulse_source("price", lambda ctx: {"value": 70123.12, "currency": "USD"})

    phema = system.create_phema(
        title="BTC Snapshot",
        prompt="Creator briefing",
        bindings=["price"],
        default_persona=Persona(name="creator-default", tone="neutral", style="compact"),
    )

    output, trace = system.cast(
        phema_id=phema.phema_id,
        viewer_format="markdown",
        context={"symbol": "BTC"},
    )

    assert "# BTC Snapshot" in output
    assert "Brief for BTC" in output
    assert "70123.12" in output
    assert len(trace) >= 4
    assert trace[-1].msg_type == "cast-ready"


def test_viewer_selects_json_format_and_persona_override():
    """
    Exercise the test_viewer_selects_json_format_and_persona_override regression
    scenario.
    """
    system = PhemacastSystem()

    system.register_pulse_source("summary", lambda ctx: {"value": "Daily outlook"})
    system.register_pulse_source("volume", lambda ctx: {"value": 123456})

    phema = system.create_phema(
        title="Market Pulse",
        prompt="Creator output",
        bindings=["volume"],
    )

    output, _ = system.cast(
        phema_id=phema.phema_id,
        viewer_format="json",
        viewer_persona=Persona(name="viewer", tone="direct", style="bullet"),
    )

    assert output["title"] == "Market Pulse"
    assert output["persona"]["name"] == "viewer"
    assert output["pulse"]["volume"]["value"] == 123456
    assert any(block["name"] == "summary" for block in output["blocks"])
