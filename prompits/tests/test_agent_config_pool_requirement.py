import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.create_agent import (
    _apply_runtime_overrides,
    _resolve_config_paths,
    _resolve_config_value,
    load_agent_config,
)
from prompits.practices.plaza import PlazaPractice
from prompits.tests.test_support import build_agent_from_config


def test_load_agent_config_requires_pool_definition(tmp_path):
    cfg = tmp_path / "no_pool.agent"
    cfg.write_text(json.dumps({
        "name": "agent-no-pool",
        "host": "127.0.0.1",
        "port": 9000,
        "type": "prompits.agents.standby.StandbyAgent"
    }))

    with pytest.raises(ValueError, match="must define at least one pool"):
        load_agent_config(str(cfg))


def test_load_agent_config_accepts_pools_list(tmp_path):
    cfg = tmp_path / "with_pools.agent"
    cfg.write_text(json.dumps({
        "name": "agent-with-pools",
        "host": "127.0.0.1",
        "port": 9001,
        "type": "prompits.agents.standby.StandbyAgent",
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "agent_pool",
                "description": "test pool",
                "root_path": "tests/storage"
            }
        ]
    }))

    loaded = load_agent_config(str(cfg))
    assert loaded["pools"][0]["type"] == "FileSystemPool"


def test_load_agent_config_keeps_multiple_pools_and_first_is_primary(tmp_path):
    cfg = tmp_path / "with_many_pools.agent"
    cfg.write_text(json.dumps({
        "name": "agent-with-many-pools",
        "host": "127.0.0.1",
        "port": 9002,
        "type": "prompits.agents.standby.StandbyAgent",
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "pool_1",
                "description": "primary pool",
                "root_path": "tests/storage"
            },
            {
                "type": "FileSystemPool",
                "name": "pool_2",
                "description": "secondary pool",
                "root_path": "tests/storage"
            }
        ]
    }))

    loaded = load_agent_config(str(cfg))
    assert len(loaded["pools"]) == 2
    assert loaded["pools"][0]["name"] == "pool_1"


def test_build_agent_from_config_passes_plaza_init_files(tmp_path):
    init_dir = tmp_path / "init_files"
    init_dir.mkdir()
    (init_dir / "init_pulse_market.json").write_text(json.dumps({
        "PitType": "Pulse",
        "data": [
            {
                "name": "last_price",
                "description": "Latest traded price.",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "last_price": {"type": "number"},
                    },
                },
            }
        ]
    }))
    (init_dir / "init_pulse_news.json").write_text(json.dumps({
        "PitType": "Pulse",
        "data": [
            {
                "name": "news_article",
                "description": "Latest news item.",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "headline": {"type": "string"},
                    },
                },
            }
        ]
    }))

    pool_dir = tmp_path / "pool_storage"
    cfg = tmp_path / "plaza.agent"
    cfg.write_text(json.dumps({
        "name": "plaza",
        "host": "127.0.0.1",
        "port": 9003,
        "type": "prompits.core.plaza.PlazaAgent",
        "plaza": {
            "init_files": ["init_files"]
        },
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "plaza_pool",
                "description": "test pool",
                "root_path": str(pool_dir)
            }
        ],
        "practices": [
            {
                "type": "prompits.practices.plaza.PlazaPractice",
                "params": {}
            }
        ]
    }))

    agent = build_agent_from_config(str(cfg))
    practice = next(p for p in agent.practices if isinstance(p, PlazaPractice))

    assert practice.init_files == [str(init_dir.resolve())]
    seeded_cards = {card.get("name"): card for card in practice.agent_cards.values()}
    assert "last_price" in seeded_cards
    assert "news_article" in seeded_cards
    assert seeded_cards["last_price"]["pit_type"] == "Pulse"
    assert seeded_cards["last_price"]["pit_address"]["pit_id"]
    assert seeded_cards["last_price"]["meta"]["output_schema"]["type"] == "object"
    assert seeded_cards["news_article"]["pit_type"] == "Pulse"


def test_build_agent_from_config_registers_sibling_agent_configs_to_plaza_directory(tmp_path):
    pool_dir = tmp_path / "pool_storage"
    cfg = tmp_path / "plaza.agent"
    cfg.write_text(json.dumps({
        "name": "plaza",
        "host": "127.0.0.1",
        "port": 9003,
        "type": "prompits.core.plaza.PlazaAgent",
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "plaza_pool",
                "description": "test pool",
                "root_path": str(pool_dir)
            }
        ],
        "practices": [
            {
                "type": "prompits.practices.plaza.PlazaPractice",
                "params": {}
            }
        ]
    }))
    (tmp_path / "worker.agent").write_text(json.dumps({
        "name": "worker-a",
        "uuid": "runtime-worker-uuid",
        "host": "127.0.0.1",
        "port": 9004,
        "plaza_url": "http://127.0.0.1:9003",
        "type": "prompits.agents.standby.StandbyAgent",
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "worker_pool",
                "description": "worker pool",
                "root_path": "worker_storage"
            }
        ]
    }))
    (tmp_path / "user.agent").write_text(json.dumps({
        "name": "user-ui",
        "host": "127.0.0.1",
        "port": 9005,
        "plaza_url": "http://127.0.0.1:9003",
        "type": "prompits.agents.user.UserAgent",
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "user_pool",
                "description": "user pool",
                "root_path": "user_storage"
            }
        ],
        "agent_card": {
            "name": "user-ui",
            "description": "Dashboard agent",
            "uuid": "runtime-user-card-uuid",
            "address": "http://127.0.0.1:9005"
        }
    }))

    agent = build_agent_from_config(str(cfg))
    practice = next(p for p in agent.practices if isinstance(p, PlazaPractice))

    agent_config_cards = {
        card.get("name"): card
        for card in practice.agent_cards.values()
        if card.get("pit_type") == "AgentConfig"
    }
    assert practice.config_dir == str(tmp_path.resolve())
    assert set(agent_config_cards) == {"plaza", "user-ui", "worker-a"}

    directory_rows = agent.pool._GetTableData(PlazaPractice.DIRECTORY_TABLE) or []
    agent_config_rows = {
        row["name"]: row
        for row in directory_rows
        if row.get("type") == "AgentConfig"
    }
    assert set(agent_config_rows) == {"plaza", "user-ui", "worker-a"}
    assert agent_config_rows["worker-a"]["id"] == "agent-config:worker-a"
    assert agent_config_rows["user-ui"]["id"] == "agent-config:user-ui"
    assert "uuid" not in agent_config_rows["worker-a"]["meta"]["config"]
    assert "host" not in agent_config_rows["worker-a"]["meta"]["config"]
    assert "port" not in agent_config_rows["worker-a"]["meta"]["config"]
    assert "plaza_url" not in agent_config_rows["worker-a"]["meta"]["config"]
    assert "uuid" not in agent_config_rows["user-ui"]["meta"]["config"]["agent_card"]
    assert "address" not in agent_config_rows["user-ui"]["meta"]["config"]["agent_card"]


def test_resolve_config_paths_falls_back_to_workspace_relative_paths(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    config_dir = workspace / "attas" / "configs"
    init_dir = workspace / "attas" / "init_pits"
    init_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    (init_dir / "init_pulse_market.json").write_text("[]")

    monkeypatch.chdir(workspace)
    resolved = _resolve_config_paths(["attas/init_pits"], str(config_dir))

    assert resolved == [str(init_dir.resolve())]


def test_resolve_config_value_supports_env_references(monkeypatch):
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_key")

    assert _resolve_config_value({"env": "SUPABASE_PUBLISHABLE_KEY"}) == "sb_publishable_test_key"
    assert _resolve_config_value("env:SUPABASE_PUBLISHABLE_KEY") == "sb_publishable_test_key"
    assert _resolve_config_value("${SUPABASE_PUBLISHABLE_KEY}") == "sb_publishable_test_key"


def test_resolve_config_value_supports_env_fallback_literal(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)

    assert _resolve_config_value({
        "env": "SUPABASE_URL",
        "value": "https://fallback-project.supabase.co",
    }) == "https://fallback-project.supabase.co"

    monkeypatch.setenv("SUPABASE_URL", "https://env-project.supabase.co")
    assert _resolve_config_value({
        "env": "SUPABASE_URL",
        "value": "https://fallback-project.supabase.co",
    }) == "https://env-project.supabase.co"


def test_runtime_overrides_support_plaza_url(monkeypatch):
    monkeypatch.setenv("PROMPITS_PLAZA_URL", "http://127.0.0.1:8000/")

    overridden = _apply_runtime_overrides({
        "name": "test-pulser",
        "host": "127.0.0.1",
        "port": 8020,
        "plaza_url": "http://127.0.0.1:8011",
    })

    assert overridden["plaza_url"] == "http://127.0.0.1:8000"
