import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.create_agent import load_agent_config, _resolve_config_paths, _resolve_config_value
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
    (init_dir / "init_pulse.json").write_text(json.dumps({
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
    seeded = [card for card in practice.agent_cards.values() if card.get("name") == "last_price"]
    assert len(seeded) == 1
    assert seeded[0]["pit_type"] == "Pulse"
    assert seeded[0]["pit_address"]["pit_id"]
    assert seeded[0]["meta"]["output_schema"]["type"] == "object"


def test_resolve_config_paths_falls_back_to_workspace_relative_paths(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    config_dir = workspace / "attas" / "configs"
    init_file = workspace / "attas" / "init_pits" / "init_pulse.json"
    init_file.parent.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    init_file.write_text("[]")

    monkeypatch.chdir(workspace)
    resolved = _resolve_config_paths(["attas/init_pits/init_pulse.json"], str(config_dir))

    assert resolved == [str(init_file.resolve())]


def test_resolve_config_value_supports_env_references(monkeypatch):
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_key")

    assert _resolve_config_value({"env": "SUPABASE_PUBLISHABLE_KEY"}) == "sb_publishable_test_key"
    assert _resolve_config_value("env:SUPABASE_PUBLISHABLE_KEY") == "sb_publishable_test_key"
    assert _resolve_config_value("${SUPABASE_PUBLISHABLE_KEY}") == "sb_publishable_test_key"
