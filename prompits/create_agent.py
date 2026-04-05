"""
Agent creation helpers and entry points for Prompits.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS.

Key definitions include `AgentNameFilter`, `create_agent_from_config`, `build_agent`,
and `load_agent_config`, which provide the main entry points used by neighboring modules
and tests.
"""

import argparse
import copy
import sys
import os
import socket

# Automatically add the project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
import json
import uvicorn
import requests
import importlib
import inspect
try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional local convenience
    load_dotenv = None
from prompits.agents.standby import StandbyAgent
from prompits.core.message import Message

if load_dotenv is not None:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    load_dotenv(os.path.join(project_root, ".env"))
    load_dotenv()

class AgentNameFilter(logging.Filter):
    """Represent an agent name filter."""
    def filter(self, record):
        """Handle filter for the agent name filter."""
        if not hasattr(record, 'agent_name'):
            record.agent_name = 'Main'
        return True

logging.basicConfig(
    level=logging.INFO,
    format='[%(agent_name)s] %(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
for handler in logging.root.handlers:
    handler.addFilter(AgentNameFilter())

logger = logging.getLogger(__name__)

REMOVED_LEGACY_PRACTICE_TYPES = {
    "prompits.practices.chat.ChatPractice",
    "prompits.practices.llm.LLMPractice",
}


def _coerce_path_list(value):
    """Internal helper to coerce the path list."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item]
    if isinstance(value, dict):
        collected = []
        for key in ("init_files", "files", "paths"):
            collected.extend(_coerce_path_list(value.get(key)))
        for key in ("init_dir", "init_folder", "directory", "folder", "path"):
            collected.extend(_coerce_path_list(value.get(key)))
        return collected
    return []


def _resolve_config_paths(paths, config_dir):
    """Internal helper to resolve the config paths."""
    resolved = []
    seen = set()
    for path in _coerce_path_list(paths):
        expanded = os.path.expanduser(path)
        normalized = expanded if os.path.isabs(expanded) or not config_dir else os.path.join(config_dir, expanded)
        absolute = os.path.abspath(normalized)
        if (
            not os.path.isabs(expanded)
            and config_dir
            and not os.path.exists(absolute)
        ):
            workspace_relative = os.path.abspath(expanded)
            if os.path.exists(workspace_relative):
                absolute = workspace_relative
        if absolute not in seen:
            seen.add(absolute)
            resolved.append(absolute)
    return resolved


def _extract_plaza_practice_params(config):
    """Internal helper to extract the Plaza practice params."""
    raw_config = config.get("raw_config") or {}
    config_dir = config.get("config_dir")
    collected_sources = []

    candidate_sections = [raw_config]
    properties = raw_config.get("properties")
    if isinstance(properties, dict):
        candidate_sections.append(properties)
        plaza_properties = properties.get("plaza")
        if isinstance(plaza_properties, dict):
            candidate_sections.append(plaza_properties)

    for key in ("plaza", "plaza_properties"):
        candidate = raw_config.get(key)
        if isinstance(candidate, dict):
            candidate_sections.append(candidate)

    seen_sources = set()
    for section in candidate_sections:
        if not isinstance(section, dict):
            continue
        for key in ("init_files", "initial_data", "init_dir", "init_folder", "init_path"):
            for source in _resolve_config_paths(section.get(key), config_dir):
                if source not in seen_sources:
                    seen_sources.add(source)
                    collected_sources.append(source)

    return {"init_files": collected_sources} if collected_sources else {}


def resolve_practice_params(config, practice_info):
    """Resolve the practice params."""
    practice_params = dict(practice_info.get("params", {}) or {})
    practice_type = practice_info.get("type", "")
    config_dir = config.get("config_dir")

    init_sources = []
    for key in ("init_files", "initial_data", "init_dir", "init_folder", "init_path"):
        init_sources.extend(_resolve_config_paths(practice_params.get(key), config_dir))

    if "PlazaPractice" in practice_type:
        extracted = _extract_plaza_practice_params(config)
        for source in extracted.get("init_files", []):
            if source not in init_sources:
                init_sources.append(source)
        if config_dir and "config_dir" not in practice_params:
            practice_params["config_dir"] = str(config_dir)

    if init_sources:
        practice_params["init_files"] = init_sources
        practice_params.pop("initial_data", None)

    return practice_params


def _extract_remote_use_practice_settings(raw_config):
    """Internal helper to extract remote practice policy and audit settings."""
    if not isinstance(raw_config, dict):
        return {}

    extracted = {}
    for key in ("remote_use_practice_policy", "remote_use_practice_audit"):
        value = raw_config.get(key)
        if isinstance(value, dict):
            extracted[key] = copy.deepcopy(value)
    return extracted


def instantiate_practice_from_config(config, practice_info):
    """Return the instantiate practice from config."""
    practice_type = practice_info.get("type")
    if not practice_type:
        return None
    if practice_type in REMOVED_LEGACY_PRACTICE_TYPES:
        raise ValueError(
            f"{practice_type} has been removed. Use a dedicated LLM pulser config instead."
        )

    module_name, class_name = practice_type.rsplit(".", 1)
    module = importlib.import_module(module_name)
    practice_cls = getattr(module, class_name)
    practice_params = resolve_practice_params(config, practice_info)
    return practice_cls(**practice_params)

def _resolve_config_value(value):
    """Internal helper to resolve the config value."""
    if isinstance(value, dict):
        env_name = value.get("env") or value.get("name")
        fallback = value.get("value", value.get("fallback"))
        if env_name:
            resolved = os.getenv(str(env_name))
            if resolved not in (None, ""):
                return resolved
            return None if fallback is None else str(fallback)
        if "value" in value:
            return None if fallback is None else str(fallback)
        return None

    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed.startswith("env:"):
            return os.getenv(trimmed[4:].strip())
        if trimmed.startswith("${") and trimmed.endswith("}"):
            return os.getenv(trimmed[2:-1].strip())
        return value

    return value

def _instantiate_pool(pool_config: dict, default_name: str):
    """Internal helper for instantiate pool."""
    pool_type = pool_config.get("type")
    pool_name = pool_config.get("name", default_name)
    pool_desc = pool_config.get("description", "Agent Storage")

    if pool_type == "FileSystemPool":
        from prompits.pools.filesystem import FileSystemPool
        root_path = pool_config.get("root_path", "./data")
        return FileSystemPool(pool_name, pool_desc, root_path)
    if pool_type == "SQLitePool":
        from prompits.pools.sqlite import SQLitePool
        db_path = pool_config.get("db_path", "agent.db")
        return SQLitePool(pool_name, pool_desc, db_path)
    if pool_type == "PostgresPool":
        from prompits.pools.postgres import PostgresPool
        dsn = _resolve_config_value(
            pool_config.get("dsn")
            or pool_config.get("conninfo")
            or pool_config.get("database_url")
        )
        schema = _resolve_config_value(pool_config.get("schema") or pool_config.get("schema_name")) or "public"
        sslmode = _resolve_config_value(pool_config.get("sslmode")) or ""
        return PostgresPool(
            pool_name,
            pool_desc,
            dsn=dsn or "",
            schema=schema or "public",
            sslmode=sslmode,
        )
    if pool_type == "SupabasePool":
        from prompits.pools.supabase import SupabasePool
        url = _resolve_config_value(pool_config.get("url"))
        key = _resolve_config_value(pool_config.get("key"))
        return SupabasePool(pool_name, url, key, pool_desc)
    raise ValueError(f"Unsupported pool type: {pool_type}")


def _coerce_optional_bool(value):
    """Internal helper to coerce the optional bool."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    lowered = str(value).strip().lower()
    if lowered in {"1", "true", "yes", "y", "on"}:
        return True
    if lowered in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _normalize_config_path(value):
    """Internal helper to normalize the config path."""
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    return os.path.realpath(os.path.abspath(os.path.expanduser(candidate)))


def _should_apply_process_network_overrides(config):
    """Return whether the value should apply process network overrides."""
    if not isinstance(config, dict):
        return True

    env_config_path = _normalize_config_path(os.getenv("PROMPITS_AGENT_CONFIG"))
    if not env_config_path:
        return True

    current_config_path = _normalize_config_path(config.get("config_path"))
    if not current_config_path:
        return True

    return env_config_path == current_config_path


def _config_prefers_ephemeral_identity(config_data):
    """Internal helper to return the config prefers ephemeral identity."""
    if not isinstance(config_data, dict):
        return False
    agent_type = str(config_data.get("type") or "").strip()
    if agent_type.endswith("ADSWorkerAgent"):
        return True
    agent_card = config_data.get("agent_card") if isinstance(config_data.get("agent_card"), dict) else {}
    meta = agent_card.get("meta") if isinstance(agent_card.get("meta"), dict) else {}
    configured = agent_card.get("reuse_plaza_identity")
    if configured is None:
        configured = meta.get("reuse_plaza_identity")
    coerced = _coerce_optional_bool(configured)
    return coerced is False


def _find_free_port(bind_host):
    """Internal helper to find the free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((str(bind_host or "127.0.0.1"), 0))
        return int(sock.getsockname()[1])


def _port_is_available(bind_host, port):
    """Return whether the port is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((str(bind_host or "127.0.0.1"), int(port)))
            return True
    except OSError:
        return False

def load_agent_config(config_path=None, name=None, role=None, tags_str=None):
    # Values from CLI/Args
    """Load the agent config."""
    current_name = name
    current_role = role
    current_tags_str = tags_str
    
    # Defaults
    host = "127.0.0.1"
    port = 8000
    plaza_url = None

    config_data = {}
    if config_path:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file {config_path} not found.")
        
        with open(config_path, 'r') as f:
            config_data = json.load(f)
            current_name = current_name or config_data.get("name")
            current_role = current_role or config_data.get("role")
            
            # New fields for HTTP
            host = config_data.get("host", host)
            port = config_data.get("port", port)
            plaza_url = config_data.get("plaza_url", plaza_url)
            
            if current_tags_str is None:
                config_tags = config_data.get("tags", [])
                current_tags_str = ",".join(config_tags) if isinstance(config_tags, list) else str(config_tags)

        pools_list = config_data.get("pools")
        has_pools_list = isinstance(pools_list, list) and len(pools_list) > 0
        if not has_pools_list:
            raise ValueError("Agent config must define at least one pool via non-empty 'pools'.")

    if not config_data.get("host"):
        config_data["host"] = host
    if config_data.get("port") in (None, "", 0):
        config_data["port"] = _find_free_port(str(config_data.get("host") or host))
    elif (
        _config_prefers_ephemeral_identity(config_data)
        and not os.getenv("PROMPITS_PORT")
        and not os.getenv("PORT")
        and not _port_is_available(str(config_data.get("host") or host), config_data.get("port"))
    ):
        requested_port = int(config_data.get("port"))
        config_data["port"] = _find_free_port(str(config_data.get("host") or host))
        logger.warning(
            "Configured port %s is already in use for %s. Remapping to free port %s.",
            requested_port,
            str(config_data.get("name") or current_name or "agent"),
            config_data["port"],
        )

    if not current_name:
        raise ValueError("Agent name is required.")
    
    current_role = current_role or "generic"
    current_tags_str = current_tags_str or ""
    tags = [t.strip() for t in current_tags_str.split(",") if t.strip()]
    host = config_data.get("host", host)
    port = int(config_data.get("port", port))
    plaza_url = config_data.get("plaza_url", plaza_url)

    return {
        "name": current_name,
        "role": current_role,
        "tags": tags,
        "host": host,
        "port": port,
        "plaza_url": plaza_url,
        "pools": config_data.get("pools", []) if config_path else [],
        "practices": config_data.get("practices", []) if config_path else [],
        "config_path": os.path.abspath(config_path) if config_path else None,
        "config_dir": os.path.dirname(os.path.abspath(config_path)) if config_path else None,
        "raw_config": config_data if config_path else {},
        # Default type if not in config
        "type": config_data.get("type", "prompits.agents.standby.StandbyAgent") if config_path else "prompits.agents.standby.StandbyAgent"
    }

def create_agent_from_config(config):
    """Create the agent from config."""
    raw_config = config.get("raw_config") or {}
    agent_card = dict(raw_config.get("agent_card") or {})
    agent_card_meta = agent_card.get("meta")
    if not isinstance(agent_card_meta, dict):
        agent_card_meta = {}
    else:
        agent_card_meta = dict(agent_card_meta)

    for setting_name, setting_value in _extract_remote_use_practice_settings(raw_config).items():
        agent_card_meta.setdefault(setting_name, setting_value)

    if agent_card_meta:
        agent_card["meta"] = agent_card_meta

    agent_card.update({
        "name": config["name"],
        "role": config["role"],
        "tags": config["tags"],
        "host": config["host"],
        "port": config["port"],
        "address": f"http://{config['host']}:{config['port']}"
    })
    if "accepts_inbound_from_plaza" in raw_config:
        agent_card["accepts_inbound_from_plaza"] = raw_config.get("accepts_inbound_from_plaza")
    if "connectivity_mode" in raw_config:
        agent_card["connectivity_mode"] = raw_config.get("connectivity_mode")
    
    agent_type_str = config["type"]
    try:
        module_name, class_name = agent_type_str.rsplit(".", 1)
        module = importlib.import_module(module_name)
        agent_cls = getattr(module, class_name)
    except (ValueError, ImportError, AttributeError) as e:
        logger.error(f"Failed to load agent class '{agent_type_str}': {e}")
        # Fallback to StandbyAgent if loading fails? Or raise?
        raise e

    # Pool Initialization (multi-pool capable; first pool is used for agent credential persistence)
    pools = []
    for idx, pool_config in enumerate(config.get("pools", [])):
        if not isinstance(pool_config, dict):
            continue
        try:
            default_name = f"{config['name']}_pool_{idx}"
            pool = _instantiate_pool(pool_config, default_name=default_name)
            pools.append(pool)
            logger.info(f"Initialized pool[{idx}]: {pool_config.get('name', default_name)} ({pool_config.get('type')})")
        except Exception as e:
            logger.error(f"Failed to initialize pool[{idx}]: {e}")

    primary_pool = pools[0] if pools else None
    init_signature = inspect.signature(agent_cls.__init__)
    accepts_kwargs = any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD
        for parameter in init_signature.parameters.values()
    )
    supports_config = "config" in init_signature.parameters or accepts_kwargs
    supports_config_path = "config_path" in init_signature.parameters or accepts_kwargs

    # Handle specific initialization for Plaza vs Generic Agents
    # Ideally, we'd standardize this, but for now we adapt.
    if "PlazaAgent" in class_name:
         plaza_kwargs = {
            "host": config["host"],
            "port": config["port"],
            "pool": primary_pool,
         }
         if supports_config:
            plaza_kwargs["config"] = config.get("raw_config")
         if supports_config_path and config.get("config_path"):
            plaza_kwargs["config_path"] = config["config_path"]
         return agent_cls(**plaza_kwargs)
    else:
         agent_kwargs = {
            "name": config["name"],
            "host": config["host"],
            "port": config["port"],
            "plaza_url": config["plaza_url"],
            "agent_card": agent_card,
            "pool": primary_pool,
        }
         if supports_config:
            agent_kwargs["config"] = config.get("config_path") or config.get("raw_config")
         if supports_config_path and config.get("config_path"):
            agent_kwargs["config_path"] = config["config_path"]
         return agent_cls(**agent_kwargs)


def _apply_runtime_overrides(config):
    """Internal helper for apply runtime overrides."""
    if not isinstance(config, dict):
        return config

    plaza_url = str(os.getenv("PROMPITS_PLAZA_URL") or "").strip().rstrip("/")
    if plaza_url:
        config["plaza_url"] = plaza_url

    if _should_apply_process_network_overrides(config):
        bind_host = str(os.getenv("PROMPITS_BIND_HOST") or "").strip()
        if bind_host:
            config["host"] = bind_host

        bind_port = str(os.getenv("PROMPITS_PORT") or os.getenv("PORT") or "").strip()
        if bind_port:
            try:
                config["port"] = int(bind_port)
            except ValueError as exc:
                raise ValueError(f"Invalid port override: {bind_port}") from exc

    return config


def build_agent(config):
    """Build the agent."""
    resolved_config = _apply_runtime_overrides(dict(config))
    agent = create_agent_from_config(resolved_config)

    public_url = str(os.getenv("PROMPITS_PUBLIC_URL") or "").strip().rstrip("/")
    if public_url and _should_apply_process_network_overrides(resolved_config):
        agent.agent_card["address"] = public_url
    else:
        agent.agent_card["address"] = f"http://{agent.host}:{agent.port}"

    if hasattr(agent, "_refresh_pit_address"):
        agent._refresh_pit_address()

    practices_config = resolved_config.get("practices", [])
    begin_batch = getattr(agent, "_begin_practice_persistence_batch", None)
    end_batch = getattr(agent, "_end_practice_persistence_batch", None)
    if callable(begin_batch):
        begin_batch()
    try:
        for practice_info in practices_config:
            practice_instance = instantiate_practice_from_config(resolved_config, practice_info)
            if practice_instance is None:
                continue
            agent.add_practice(practice_instance)
    finally:
        if callable(end_batch):
            end_batch()

    return agent

def main():
    """Run the main entry point."""
    parser = argparse.ArgumentParser(description="Create and Run a Distributed Agent.")
    parser.add_argument("--name", help="Name of the agent")
    parser.add_argument("--role", help="Role of the agent")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--config", help="Path to a JSON configuration file")
    parser.add_argument("--debug", action="store_true", help="Enable DEBUG level logging")

    # CLI Client Args
    parser.add_argument("--send-to", help="Target URL to send a message to")
    parser.add_argument("--message", help="Message content")
    parser.add_argument("--sender", default="CLI", help="Sender name for the message")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("--- DEBUG logging enabled ---")

    # If no arguments were passed, print help and exit
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    # Client Mode: Send Message
    if args.send_to and args.message:
        msg = Message(
            sender=args.sender,
            receiver=args.send_to, # Using URL as receiver for direct comms
            content=args.message,
            msg_type="message" # or command? let's stick to message for general use
        )
        try:
            # Use Pydantic json serialization
            import json
            payload = json.loads(msg.json())
            print(f"Sending to {args.send_to}...")
            response = requests.post(f"{args.send_to}/mailbox", json=payload, timeout=5)
            if response.status_code == 200:
                print(f"Success: {response.json()}")
            else:
                print(f"Failed: Status {response.status_code}, {response.text}")
        except Exception as e:
            print(f"Error sending message: {e}")
        return

    # Agent Mode
    try:
        config = load_agent_config(args.config, args.name, args.role, args.tags)
        print(f"--- Loaded Config for: {config['name']} ---")
        print(f"Config: {config}")

        agent = build_agent(config)

        print(f"Starting agent {agent.name} on {agent.host}:{agent.port}...")
        
        # Run uvicorn (blocks until Ctrl-C)
        uvicorn.run(agent.app, host=agent.host, port=agent.port)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
