import logging
import io
import os
import socket
import threading
import time
from unittest.mock import Mock, patch

import requests
import uvicorn

from prompits.agents.standby import StandbyAgent
from prompits.practices.llm import LLMPractice
from prompits.practices.plaza import PlazaPractice
from prompits.tests.test_support import stop_servers


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_agent_instance(agent, log_level: str = "error", timeout_sec: int = 10):
    config = uvicorn.Config(agent.app, host=agent.host, port=agent.port, log_level=log_level)
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + timeout_sec
    health_url = f"http://{agent.host}:{agent.port}/health"
    while time.time() < deadline:
        try:
            response = requests.get(health_url, timeout=0.5)
            if response.status_code == 200:
                return server, thread
        except Exception:
            pass
        time.sleep(0.2)

    raise RuntimeError(f"Timed out waiting for agent at {health_url}")


def _wait_until(predicate, timeout_sec: int = 10, interval_sec: float = 0.2):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval_sec)
    return False


def test_remote_use_practice_llm_returns_response_and_writes_debug_log():
    plaza_port = _find_free_port()
    llm_port = _find_free_port()
    caller_port = _find_free_port()
    plaza_url = f"http://127.0.0.1:{plaza_port}"

    plaza_agent = StandbyAgent(
        name="Plaza",
        host="127.0.0.1",
        port=plaza_port,
        agent_card={"name": "Plaza", "role": "coordinator", "tags": ["plaza"]},
    )
    plaza_agent.add_practice(PlazaPractice())

    llm_agent = StandbyAgent(
        name="llm-agent",
        host="127.0.0.1",
        port=llm_port,
        plaza_url=plaza_url,
        agent_card={"name": "llm-agent", "role": "llm", "tags": ["llm", "remote"]},
    )
    llm_agent.add_practice(LLMPractice())

    caller_agent = StandbyAgent(
        name="caller-agent",
        host="127.0.0.1",
        port=caller_port,
        plaza_url=plaza_url,
        agent_card={"name": "caller-agent", "role": "client", "tags": ["caller"]},
    )

    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../tests/storage/logs"))
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "use_practice_remote_llm_debug.log")

    base_logger = logging.getLogger("prompits.agents.base")
    previous_level = base_logger.level
    log_stream = io.StringIO()
    stream_handler = logging.StreamHandler(log_stream)
    stream_handler.setLevel(logging.DEBUG)
    stream_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    base_logger.addHandler(stream_handler)
    base_logger.setLevel(logging.DEBUG)

    servers = []
    try:
        servers.append(_start_agent_instance(plaza_agent))
        servers.append(_start_agent_instance(llm_agent))

        llm_agent.register()
        caller_agent.register()

        assert _wait_until(lambda: bool(llm_agent.agent_id and caller_agent.agent_id))
        assert _wait_until(lambda: caller_agent.lookup_agent_info(llm_agent.agent_id) is not None)

        fake_llm_response = Mock()
        fake_llm_response.raise_for_status.return_value = None
        fake_llm_response.json.return_value = {"response": "Remote Ollama reply"}
        real_requests_post = requests.post

        def selective_post(url, *args, **kwargs):
            if url == LLMPractice.DEFAULT_OLLAMA_URL:
                return fake_llm_response
            return real_requests_post(url, *args, **kwargs)

        with patch("prompits.practices.chat.requests.post", side_effect=selective_post) as post_mock:
            result = caller_agent.UsePractice(
                "llm",
                {"prompt": "Return a short greeting from the remote model."},
                pit_address=llm_agent.pit_address,
            )

        assert result["status"] == "success"
        assert result["response"] == "Remote Ollama reply"
        assert result["provider"] == "ollama"
        assert result["model"] == "llama3"
        assert any(call.args and call.args[0] == LLMPractice.DEFAULT_OLLAMA_URL for call in post_mock.call_args_list)

        rejected = requests.post(
            f"http://127.0.0.1:{llm_port}/use_practice/llm",
            json={
                "sender": "spoofed-caller",
                "receiver": llm_agent.agent_id,
                "content": {"prompt": "This should be rejected."},
                "msg_type": "llm",
                "caller_agent_address": {"pit_id": "spoofed-id", "plazas": [plaza_url]},
                "caller_plaza_token": "invalid-token",
            },
            timeout=5,
        )
        assert rejected.status_code == 401

        stream_handler.flush()
        log_text = log_stream.getvalue()
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write(log_text)
        assert "Verified remote caller" in log_text
        assert "failed Plaza verification" in log_text
        assert "Completed remote UsePractice 'llm'" in log_text
    finally:
        stop_servers(servers)
        base_logger.removeHandler(stream_handler)
        stream_handler.close()
        base_logger.setLevel(previous_level)
