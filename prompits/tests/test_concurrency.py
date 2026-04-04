"""
Regression tests for Concurrency.

Prompits provides the core HTTP-native agent runtime, Plaza coordination layer, and
pool/practice infrastructure for FinMAS. These tests lock down Prompits runtime
behavior, Plaza features, and storage integrations.

The pytest cases in this file document expected behavior through checks such as
`test_plaza_register_requests_run_concurrently`,
`test_plaza_status_api_requests_run_concurrently`, and
`test_remote_use_practice_requests_run_concurrently`, helping guard against regressions
as the packages evolve.
"""

import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
import uvicorn

from prompits.agents.standby import StandbyAgent
from prompits.core.plaza import PlazaAgent
from prompits.core.practice import Practice
from prompits.practices.plaza import PlazaPractice
from prompits.tests.test_support import stop_servers


def _find_free_port() -> int:
    """Internal helper to find the free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_agent_instance(agent, log_level: str = "error", timeout_sec: int = 10):
    """Internal helper to start the agent instance."""
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
    """Internal helper for wait until."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval_sec)
    return False


class SlowPractice(Practice):
    """Practice implementation for slow workflows."""
    def __init__(self):
        """Initialize the slow practice."""
        super().__init__(
            name="SlowPractice",
            description="Sleep for a short interval and report timing metadata.",
            id="slow-practice",
        )

    def mount(self, app):
        """Mount the value."""
        return None

    def execute(self, delay: float = 1.0, value=None, **kwargs):
        """Handle execute for the slow practice."""
        started_at = time.monotonic()
        time.sleep(delay)
        ended_at = time.monotonic()
        return {
            "status": "success",
            "value": value,
            "started_at": started_at,
            "ended_at": ended_at,
        }


def test_remote_use_practice_requests_run_concurrently():
    """
    Exercise the test_remote_use_practice_requests_run_concurrently regression
    scenario.
    """
    plaza_port = _find_free_port()
    worker_port = _find_free_port()
    caller_port = _find_free_port()
    plaza_url = f"http://127.0.0.1:{plaza_port}"

    plaza_agent = StandbyAgent(
        name="Plaza",
        host="127.0.0.1",
        port=plaza_port,
        agent_card={"name": "Plaza", "role": "coordinator", "tags": ["plaza"]},
    )
    plaza_agent.add_practice(PlazaPractice())

    worker_agent = StandbyAgent(
        name="slow-worker",
        host="127.0.0.1",
        port=worker_port,
        plaza_url=plaza_url,
        agent_card={"name": "slow-worker", "role": "worker", "tags": ["slow"]},
    )
    worker_agent.add_practice(SlowPractice())

    caller_agent = StandbyAgent(
        name="slow-caller",
        host="127.0.0.1",
        port=caller_port,
        plaza_url=plaza_url,
        agent_card={"name": "slow-caller", "role": "client", "tags": ["caller"]},
    )

    servers = []
    try:
        servers.append(_start_agent_instance(plaza_agent))
        servers.append(_start_agent_instance(worker_agent))

        worker_agent.register()
        caller_agent.register()

        assert _wait_until(lambda: bool(worker_agent.agent_id and caller_agent.agent_id))
        assert _wait_until(lambda: caller_agent.lookup_agent_info(worker_agent.agent_id) is not None)

        def invoke(value: int):
            """Invoke the value."""
            return caller_agent.UsePractice(
                "slow-practice",
                {"delay": 1.0, "value": value},
                pit_address=worker_agent.pit_address,
                timeout=10,
            )

        started_at = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_one = executor.submit(invoke, 1)
            future_two = executor.submit(invoke, 2)
            result_one = future_one.result()
            result_two = future_two.result()
        elapsed = time.monotonic() - started_at

        assert {result_one["value"], result_two["value"]} == {1, 2}
        assert max(result_one["started_at"], result_two["started_at"]) < min(result_one["ended_at"], result_two["ended_at"])
        assert elapsed < 1.8
    finally:
        stop_servers(servers)


def test_plaza_register_requests_run_concurrently():
    """
    Exercise the test_plaza_register_requests_run_concurrently regression scenario.
    """
    plaza_port = _find_free_port()
    plaza_url = f"http://127.0.0.1:{plaza_port}"

    plaza_agent = StandbyAgent(
        name="Plaza",
        host="127.0.0.1",
        port=plaza_port,
        agent_card={"name": "Plaza", "role": "coordinator", "tags": ["plaza"]},
    )
    plaza_practice = PlazaPractice()
    intervals = []
    intervals_lock = threading.Lock()
    original_upsert = plaza_practice.state.upsert_directory_entry

    def slow_upsert(*args, **kwargs):
        """Handle slow upsert."""
        agent_name = kwargs.get("agent_name")
        if agent_name is None and len(args) > 1:
            agent_name = args[1]
        started_at = time.monotonic()
        try:
            time.sleep(1.0)
            return original_upsert(*args, **kwargs)
        finally:
            ended_at = time.monotonic()
            if agent_name in {"alpha", "beta"}:
                with intervals_lock:
                    intervals.append((agent_name, started_at, ended_at))

    plaza_practice.state.upsert_directory_entry = slow_upsert
    plaza_agent.add_practice(plaza_practice)

    servers = []
    try:
        servers.append(_start_agent_instance(plaza_agent))

        def register_agent(name: str, port: int):
            """Register the agent."""
            response = requests.post(
                f"{plaza_url}/register",
                json={
                    "agent_name": name,
                    "address": f"http://127.0.0.1:{port}",
                    "expires_in": 3600,
                },
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

        started_at = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_one = executor.submit(register_agent, "alpha", _find_free_port())
            future_two = executor.submit(register_agent, "beta", _find_free_port())
            result_one = future_one.result()
            result_two = future_two.result()
        elapsed = time.monotonic() - started_at

        assert result_one["status"] == "registered"
        assert result_two["status"] == "registered"
        assert len(intervals) == 2
        assert {intervals[0][0], intervals[1][0]} == {"alpha", "beta"}
        assert max(intervals[0][1], intervals[1][1]) < min(intervals[0][2], intervals[1][2])
        assert elapsed < 1.8
    finally:
        stop_servers(servers)


def test_plaza_status_api_requests_run_concurrently():
    """
    Exercise the test_plaza_status_api_requests_run_concurrently regression
    scenario.
    """
    plaza_port = _find_free_port()
    plaza_agent = PlazaAgent(host="127.0.0.1", port=plaza_port)
    plaza_practice = PlazaPractice()
    intervals = []
    intervals_lock = threading.Lock()
    original_search_entries = plaza_practice.state.search_entries

    def slow_search_entries(*args, **kwargs):
        """Handle slow search entries."""
        started_at = time.monotonic()
        try:
            time.sleep(1.0)
            return original_search_entries(*args, **kwargs)
        finally:
            ended_at = time.monotonic()
            with intervals_lock:
                intervals.append((started_at, ended_at))

    plaza_practice.state.search_entries = slow_search_entries
    plaza_agent.add_practice(plaza_practice)

    servers = []
    try:
        servers.append(_start_agent_instance(plaza_agent))

        def fetch_status():
            """Fetch the status."""
            response = requests.get(
                f"http://127.0.0.1:{plaza_port}/api/plazas_status",
                timeout=10,
            )
            response.raise_for_status()
            return response.json()

        started_at = time.monotonic()
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_one = executor.submit(fetch_status)
            future_two = executor.submit(fetch_status)
            result_one = future_one.result()
            result_two = future_two.result()
        elapsed = time.monotonic() - started_at

        assert result_one["status"] == "success"
        assert result_two["status"] == "success"
        assert len(intervals) == 2
        assert max(intervals[0][0], intervals[1][0]) < min(intervals[0][1], intervals[1][1])
        assert elapsed < 1.8
    finally:
        stop_servers(servers)
