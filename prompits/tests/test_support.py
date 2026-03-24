import importlib
import os
import sys
import threading
import time
from typing import List, Tuple

import requests
import uvicorn


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


def build_agent_from_config(config_path: str):
    from prompits.create_agent import load_agent_config, create_agent_from_config, instantiate_practice_from_config

    config = load_agent_config(config_path)
    agent = create_agent_from_config(config)

    practices_config = config.get("practices", [])
    for practice_info in practices_config:
        practice_instance = instantiate_practice_from_config(config, practice_info)
        if practice_instance is None:
            continue
        agent.add_practice(practice_instance)

    return agent


def start_agent_thread(config_path: str, log_level: str = "error", timeout_sec: int = 10):
    agent = build_agent_from_config(config_path)
    config = uvicorn.Config(agent.app, host=agent.host, port=agent.port, log_level=log_level)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + timeout_sec
    health_url = f"http://{agent.host}:{agent.port}/health"
    while time.time() < deadline:
        try:
            resp = requests.get(health_url, timeout=0.5)
            if resp.status_code == 200:
                return agent, server, thread
        except Exception:
            pass
        time.sleep(0.2)

    raise RuntimeError(f"Timed out waiting for agent at {health_url}")


def stop_servers(servers: List[Tuple[uvicorn.Server, threading.Thread]], join_timeout: float = 5):
    for server, _ in servers:
        server.should_exit = True
    for _, thread in servers:
        thread.join(timeout=join_timeout)
