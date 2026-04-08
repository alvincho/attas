"""Tests for personal-agent dashboard seed data."""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from phemacast.personal_agent import data


def test_dashboard_snapshot_uses_env_plaza_override(monkeypatch):
    """Demo launchers should be able to override the seeded Plaza URL for the UI."""
    monkeypatch.setenv("PHEMACAST_PERSONAL_AGENT_PLAZA_URL", "http://127.0.0.1:8241")

    snapshot = data.get_dashboard_snapshot()

    assert snapshot["meta"]["plaza_url"] == "http://127.0.0.1:8241"
