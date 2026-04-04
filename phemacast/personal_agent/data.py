"""
Data access and persistence helpers for `phemacast.personal_agent.data`.

Phemacast assembles pulse inputs, phemas, and castrs into rendered research artifacts
and interactive tooling. Within Phemacast, the personal_agent package powers the file-
backed personal research workbench and its web UI.

Important callables in this file include `get_dashboard_snapshot` and `get_workspace`,
which capture the primary workflow implemented by the module.
"""

from __future__ import annotations

from copy import deepcopy


LOCAL_DASHBOARD_SNAPSHOT = {
    "meta": {
        "application": "Phemacast Personal Agent",
        "agent_name": "MapPhemar",
        "profile": "Personal research desk",
        "mode": "Prototype Web Terminal",
        "plaza_url": "http://127.0.0.1:8011",
        "back_href": "/",
        "back_label": "Back to Personal Agent",
        "initial_phema_name": "Diagram 1",
    },
    "settings": {
        "profile_name": "Alvin",
        "billing_plan": "Phemacast Personal Pro Annual",
        "active_storage": "Filesystem + SQLite edge cache",
        "default_file_save_backend": "filesystem",
        "default_file_save_local_directory": "~/Documents/Phemacast",
        "default_file_save_pulser_id": "",
        "default_file_save_pulser_name": "",
        "default_file_save_pulser_address": "",
        "default_file_save_bucket_name": "",
        "default_file_save_object_prefix": "personal_agent",
    },
    "browser": {
        "bookmarks": [
            {
                "id": "bookmark-nvda",
                "title": "NVDA Snapshot",
                "symbol": "NVDA",
                "interval": "1d",
                "note": "Quick watchlist entry for AI infrastructure names.",
            },
            {
                "id": "bookmark-aapl",
                "title": "AAPL Pulse Board",
                "symbol": "AAPL",
                "interval": "1d",
                "note": "Large-cap benchmark for consumer hardware and services.",
            },
            {
                "id": "bookmark-tsla",
                "title": "TSLA Event Tape",
                "symbol": "TSLA",
                "interval": "4h",
                "note": "High-volatility symbol for testing pane field selection.",
            },
        ],
    },
    "activity": [
        {
            "id": "activity-diagram",
            "title": "Updated Diagram 1",
            "detail": "Adjusted the linked diagram editor flow for browser panes.",
            "timestamp": "2026-04-02T16:45:00+08:00",
        },
        {
            "id": "activity-storage",
            "title": "Reviewed storage settings",
            "detail": "Checked local filesystem defaults and bucket selection behavior.",
            "timestamp": "2026-04-02T15:20:00+08:00",
        },
    ],
    "workspaces": [
        {
            "id": "workspace-research",
            "name": "Alvin / Personal research desk",
            "focus": "Personal research desk",
            "description": "Track symbols, preview pulses, and keep diagram panes docked to the agent.",
            "windows": [],
        },
        {
            "id": "workspace-layouts",
            "name": "Layouts Lab",
            "focus": "Saved layouts and experiments",
            "description": "Try workspace layouts, data previews, and output field selections before saving.",
            "windows": [],
        },
    ],
}


def get_dashboard_snapshot():
    """Return the dashboard snapshot."""
    return deepcopy(LOCAL_DASHBOARD_SNAPSHOT)


def get_workspace(workspace_id: str):
    """Return the workspace."""
    for workspace in LOCAL_DASHBOARD_SNAPSHOT["workspaces"]:
        if workspace["id"] == workspace_id:
            return deepcopy(workspace)
    return None


__all__ = ["get_dashboard_snapshot", "get_workspace"]
