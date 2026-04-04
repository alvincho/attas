"""
Regression tests for Agent Config Pool Requirement.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_build_agent_from_config_passes_plaza_init_files`,
`test_build_agent_from_config_registers_sibling_agent_configs_to_plaza_directory`,
`test_register_keeps_runtime_agent_address_when_plaza_env_leaks_from_parent_process`,
and `test_runtime_overrides_apply_bind_settings_for_matching_agent_config`, helping
guard against regressions as the packages evolve.
"""

import json
import os
import socket
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from prompits.create_agent import (
    _apply_runtime_overrides,
    _resolve_config_paths,
    _resolve_config_value,
    build_agent,
    load_agent_config,
)
from prompits.core.plaza import PlazaAgent
from prompits.pools.filesystem import FileSystemPool
from prompits.practices.plaza import PlazaPractice
from prompits.tests.test_support import build_agent_from_config


def test_load_agent_config_requires_pool_definition(tmp_path):
    """
    Exercise the test_load_agent_config_requires_pool_definition regression
    scenario.
    """
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
    """Exercise the test_load_agent_config_accepts_pools_list regression scenario."""
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


def test_load_agent_config_assigns_free_port_when_missing(tmp_path):
    """
    Exercise the test_load_agent_config_assigns_free_port_when_missing regression
    scenario.
    """
    cfg = tmp_path / "with_dynamic_port.agent"
    cfg.write_text(json.dumps({
        "name": "agent-dynamic-port",
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
    assert isinstance(loaded["port"], int)
    assert loaded["port"] > 0


def test_load_agent_config_remaps_busy_port_for_ads_worker(tmp_path, monkeypatch):
    """
    Exercise the test_load_agent_config_remaps_busy_port_for_ads_worker regression
    scenario.
    """
    monkeypatch.delenv("PROMPITS_PORT", raising=False)
    monkeypatch.delenv("PORT", raising=False)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        busy_port = int(listener.getsockname()[1])

        cfg = tmp_path / "worker_busy_port.agent"
        cfg.write_text(json.dumps({
            "name": "ads-worker-port-remap",
            "host": "127.0.0.1",
            "port": busy_port,
            "type": "ads.agents.ADSWorkerAgent",
            "pools": [
                {
                    "type": "SQLitePool",
                    "name": "worker_pool",
                    "description": "test pool",
                    "db_path": str(tmp_path / "worker.sqlite")
                }
            ]
        }))

        loaded = load_agent_config(str(cfg))

    assert isinstance(loaded["port"], int)
    assert loaded["port"] > 0
    assert loaded["port"] != busy_port


def test_load_agent_config_keeps_multiple_pools_and_first_is_primary(tmp_path):
    """
    Exercise the test_load_agent_config_keeps_multiple_pools_and_first_is_primary
    regression scenario.
    """
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
    """
    Exercise the test_build_agent_from_config_passes_plaza_init_files regression
    scenario.
    """
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
    """
    Exercise the
    test_build_agent_from_config_registers_sibling_agent_configs_to_plaza_directory
    regression scenario.
    """
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


def test_plaza_bootstrap_keeps_agent_configs_in_memory_when_directory_insert_fails(tmp_path):
    """
    Exercise the
    test_plaza_bootstrap_keeps_agent_configs_in_memory_when_directory_insert_fails
    regression scenario.
    """
    class FailingAgentConfigInsertPool(FileSystemPool):
        """Represent a failing agent config insert pool."""
        def _Insert(self, table_name, data):
            """Internal helper for insert."""
            if table_name == PlazaPractice.DIRECTORY_TABLE and data.get("type") == "AgentConfig":
                return False
            return super()._Insert(table_name, data)

    (tmp_path / "worker.agent").write_text(json.dumps({
        "name": "worker-a",
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

    pool = FailingAgentConfigInsertPool("plaza_pool", "test pool", str(tmp_path / "pool_storage"))
    agent = PlazaAgent(host="127.0.0.1", port=9003, pool=pool)
    practice = PlazaPractice(config_dir=str(tmp_path))

    agent.add_practice(practice)

    agent_config_cards = {
        card.get("name"): card
        for card in practice.agent_cards.values()
        if card.get("pit_type") == "AgentConfig"
    }
    assert "worker-a" in agent_config_cards
    assert agent_config_cards["worker-a"]["meta"]["config_id"] == "agent-config:worker-a"

    directory_rows = pool._GetTableData(PlazaPractice.DIRECTORY_TABLE) or []
    assert not any(row.get("type") == "AgentConfig" for row in directory_rows)


def test_resolve_config_paths_falls_back_to_workspace_relative_paths(tmp_path, monkeypatch):
    """
    Exercise the test_resolve_config_paths_falls_back_to_workspace_relative_paths
    regression scenario.
    """
    workspace = tmp_path / "workspace"
    config_dir = workspace / "prompits" / "configs"
    init_dir = workspace / "prompits" / "init_pits"
    init_dir.mkdir(parents=True)
    config_dir.mkdir(parents=True)
    (init_dir / "init_pulse_market.json").write_text("[]")

    monkeypatch.chdir(workspace)
    resolved = _resolve_config_paths(["prompits/init_pits"], str(config_dir))

    assert resolved == [str(init_dir.resolve())]


def test_resolve_config_value_supports_env_references(monkeypatch):
    """
    Exercise the test_resolve_config_value_supports_env_references regression
    scenario.
    """
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_key")

    assert _resolve_config_value({"env": "SUPABASE_PUBLISHABLE_KEY"}) == "sb_publishable_test_key"
    assert _resolve_config_value("env:SUPABASE_PUBLISHABLE_KEY") == "sb_publishable_test_key"
    assert _resolve_config_value("${SUPABASE_PUBLISHABLE_KEY}") == "sb_publishable_test_key"


def test_resolve_config_value_supports_env_fallback_literal(monkeypatch):
    """
    Exercise the test_resolve_config_value_supports_env_fallback_literal regression
    scenario.
    """
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
    """Exercise the test_runtime_overrides_support_plaza_url regression scenario."""
    monkeypatch.setenv("PROMPITS_PLAZA_URL", "http://127.0.0.1:8000/")

    overridden = _apply_runtime_overrides({
        "name": "test-pulser",
        "host": "127.0.0.1",
        "port": 8020,
        "plaza_url": "http://127.0.0.1:8011",
    })

    assert overridden["plaza_url"] == "http://127.0.0.1:8000"


def test_runtime_overrides_apply_bind_settings_for_matching_agent_config(tmp_path, monkeypatch):
    """
    Exercise the
    test_runtime_overrides_apply_bind_settings_for_matching_agent_config regression
    scenario.
    """
    cfg = tmp_path / "plaza.agent"
    cfg.write_text(json.dumps({
        "name": "plaza",
        "host": "127.0.0.1",
        "port": 9000,
        "type": "prompits.agents.standby.StandbyAgent",
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "plaza_pool",
                "description": "test pool",
                "root_path": str(tmp_path / "plaza-pool"),
            }
        ]
    }))

    monkeypatch.setenv("PROMPITS_AGENT_CONFIG", str(cfg))
    monkeypatch.setenv("PROMPITS_BIND_HOST", "0.0.0.0")
    monkeypatch.setenv("PROMPITS_PORT", "8011")
    monkeypatch.setenv("PROMPITS_PUBLIC_URL", "http://127.0.0.1:8011")

    loaded = load_agent_config(str(cfg))
    overridden = _apply_runtime_overrides(dict(loaded))
    agent = build_agent(loaded)

    assert overridden["host"] == "0.0.0.0"
    assert overridden["port"] == 8011
    assert agent.host == "0.0.0.0"
    assert agent.port == 8011
    assert agent.agent_card["address"] == "http://127.0.0.1:8011"


def test_runtime_overrides_ignore_bind_settings_for_other_agent_config(tmp_path, monkeypatch):
    """
    Exercise the test_runtime_overrides_ignore_bind_settings_for_other_agent_config
    regression scenario.
    """
    plaza_cfg = tmp_path / "plaza.agent"
    plaza_cfg.write_text(json.dumps({
        "name": "plaza",
        "host": "127.0.0.1",
        "port": 8011,
        "type": "prompits.agents.standby.StandbyAgent",
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "plaza_pool",
                "description": "test pool",
                "root_path": str(tmp_path / "plaza-pool"),
            }
        ]
    }))

    worker_cfg = tmp_path / "worker.agent"
    worker_cfg.write_text(json.dumps({
        "name": "worker",
        "host": "127.0.0.1",
        "port": 8020,
        "type": "prompits.agents.standby.StandbyAgent",
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "worker_pool",
                "description": "test pool",
                "root_path": str(tmp_path / "worker-pool"),
            }
        ]
    }))

    monkeypatch.setenv("PROMPITS_AGENT_CONFIG", str(plaza_cfg))
    monkeypatch.setenv("PROMPITS_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("PROMPITS_PORT", "8011")
    monkeypatch.setenv("PROMPITS_PUBLIC_URL", "http://127.0.0.1:8011")

    loaded = load_agent_config(str(worker_cfg))
    overridden = _apply_runtime_overrides(dict(loaded))
    agent = build_agent(loaded)

    assert overridden["host"] == "127.0.0.1"
    assert overridden["port"] == 8020
    assert agent.host == "127.0.0.1"
    assert agent.port == 8020
    assert agent.agent_card["address"] == "http://127.0.0.1:8020"


def test_register_keeps_runtime_agent_address_when_plaza_env_leaks_from_parent_process(tmp_path, monkeypatch):
    """
    Exercise the test_register_keeps_runtime_agent_address_when_plaza_env_leaks_from
    _parent_process regression scenario.
    """
    plaza_cfg = tmp_path / "plaza.agent"
    plaza_cfg.write_text(json.dumps({
        "name": "plaza",
        "host": "127.0.0.1",
        "port": 8011,
        "type": "prompits.agents.standby.StandbyAgent",
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "plaza_pool",
                "description": "test pool",
                "root_path": str(tmp_path / "plaza-pool"),
            }
        ]
    }))

    worker_cfg = tmp_path / "worker.agent"
    worker_cfg.write_text(json.dumps({
        "name": "worker",
        "host": "127.0.0.1",
        "port": 8020,
        "plaza_url": "http://127.0.0.1:8011",
        "type": "prompits.agents.standby.StandbyAgent",
        "pools": [
            {
                "type": "FileSystemPool",
                "name": "worker_pool",
                "description": "test pool",
                "root_path": str(tmp_path / "worker-pool"),
            }
        ]
    }))

    monkeypatch.setenv("PROMPITS_AGENT_CONFIG", str(plaza_cfg))
    monkeypatch.setenv("PROMPITS_BIND_HOST", "127.0.0.1")
    monkeypatch.setenv("PROMPITS_PORT", "8011")
    monkeypatch.setenv("PROMPITS_PUBLIC_URL", "http://127.0.0.1:8011")

    loaded = load_agent_config(str(worker_cfg))
    agent = build_agent(loaded)
    captured: dict[str, object] = {}

    class DummyResponse:
        """Response model for dummy payloads."""
        status_code = 200
        text = '{"status":"registered"}'

        @staticmethod
        def json():
            """Handle JSON for the dummy response."""
            return {
                "status": "registered",
                "token": "token-worker",
                "expires_in": 3600,
                "agent_id": "worker-id",
                "api_key": "worker-key",
            }

    def fake_plaza_post(path, json=None, **kwargs):
        """Handle fake Plaza post."""
        captured["path"] = path
        captured["payload"] = dict(json or {})
        return DummyResponse()

    monkeypatch.setattr(agent, "_plaza_post", fake_plaza_post)
    monkeypatch.setattr(agent, "_start_heartbeat_thread", lambda: True)

    response = agent.register()

    assert response.status_code == 200
    assert captured["path"] == "/register"
    assert captured["payload"]["address"] == "http://127.0.0.1:8020"
    assert captured["payload"]["card"]["address"] == "http://127.0.0.1:8020"
