import argparse
import sys
import os

# Automatically add the project root (attas directory) to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
import json
import uvicorn
import requests
import importlib
import inspect
from prompits.agents.standby import StandbyAgent
from prompits.core.message import Message

class AgentNameFilter(logging.Filter):
    def filter(self, record):
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


def _coerce_path_list(value):
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

    if init_sources:
        practice_params["init_files"] = init_sources
        practice_params.pop("initial_data", None)

    return practice_params


def instantiate_practice_from_config(config, practice_info):
    practice_type = practice_info.get("type")
    if not practice_type:
        return None

    module_name, class_name = practice_type.rsplit(".", 1)
    module = importlib.import_module(module_name)
    practice_cls = getattr(module, class_name)
    practice_params = resolve_practice_params(config, practice_info)
    return practice_cls(**practice_params)

def _resolve_config_value(value):
    if isinstance(value, dict):
        env_name = value.get("env") or value.get("name")
        if env_name:
            return os.getenv(str(env_name))
        if "value" in value:
            literal = value.get("value")
            return None if literal is None else str(literal)
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
    if pool_type == "SupabasePool":
        from prompits.pools.supabase import SupabasePool
        url = _resolve_config_value(pool_config.get("url"))
        key = _resolve_config_value(pool_config.get("key"))
        return SupabasePool(pool_name, url, key, pool_desc)
    raise ValueError(f"Unsupported pool type: {pool_type}")

def load_agent_config(config_path=None, name=None, role=None, tags_str=None):
    # Values from CLI/Args
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

    if not current_name:
        raise ValueError("Agent name is required.")
    
    current_role = current_role or "generic"
    current_tags_str = current_tags_str or ""
    tags = [t.strip() for t in current_tags_str.split(",") if t.strip()]

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
    raw_config = config.get("raw_config") or {}
    agent_card = dict(raw_config.get("agent_card") or {})
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
         # Updated PlazaAgent now accepts pool
         return agent_cls(host=config["host"], port=config["port"], pool=primary_pool)
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

def main():
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

        agent = create_agent_from_config(config)
        
        # Load Dynamic Practices from config
        practices_config = config.get("practices", [])
        for practice_info in practices_config:
            try:
                practice_instance = instantiate_practice_from_config(config, practice_info)
                if practice_instance is None:
                    continue
                agent.add_practice(practice_instance)
                print(f"Added custom practice: {practice_info.get('type')}")
            except Exception as e:
                print(f"Error loading practice {practice_info}: {e}")

        print(f"Starting agent {agent.name} on {agent.host}:{agent.port}...")
        
        # Run uvicorn (blocks until Ctrl-C)
        uvicorn.run(agent.app, host=agent.host, port=agent.port)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
