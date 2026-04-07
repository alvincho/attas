"""
Local stack bootstrap CLI for Prompits.

This module provides a one-command way to bring up the Prompits local desk stack
without manual multi-terminal choreography.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import requests

from prompits.core.process_utils import background_popen_kwargs, pid_is_running, terminate_pid


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
STACK_STATE_ROOT = Path(tempfile.gettempdir()) / "prompits-local"


@dataclass(frozen=True)
class ServiceSpec:
    """Static definition for one locally managed service."""

    name: str
    config_path: str
    url: str
    expected_agent: str


def _stack_specs(stack_name: str) -> List[ServiceSpec]:
    """Return the service list for one named local stack."""
    normalized = str(stack_name or "").strip().lower()
    if normalized in {"desk", "alpha"}:
        return [
            ServiceSpec(
                name="plaza",
                config_path="prompits/examples/plaza.agent",
                url="http://127.0.0.1:8211",
                expected_agent="Plaza",
            ),
            ServiceSpec(
                name="worker",
                config_path="prompits/examples/worker.agent",
                url="http://127.0.0.1:8212",
                expected_agent="worker-a",
            ),
            ServiceSpec(
                name="user",
                config_path="prompits/examples/user.agent",
                url="http://127.0.0.1:8214",
                expected_agent="user-ui",
            ),
        ]
    raise ValueError(f"Unsupported stack '{stack_name}'. Supported stacks: desk")


class LocalStackManager:
    """Manage a small background local stack for Prompits development."""

    def __init__(self, stack_name: str):
        """Initialize the stack manager."""
        self.stack_name = str(stack_name or "").strip().lower() or "desk"
        self.services = _stack_specs(self.stack_name)
        workspace_hash = hashlib.sha1(str(WORKSPACE_ROOT).encode("utf-8")).hexdigest()[:12]
        self.state_dir = STACK_STATE_ROOT / workspace_hash / self.stack_name
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "state.json"

    def _read_state(self) -> Dict[str, Any]:
        """Read the current stack state from disk."""
        if not self.state_file.exists():
            return {"stack": self.stack_name, "services": {}}
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception:
            return {"stack": self.stack_name, "services": {}}
        if not isinstance(payload, dict):
            return {"stack": self.stack_name, "services": {}}
        services = payload.get("services")
        if not isinstance(services, dict):
            payload["services"] = {}
        return payload

    def _write_state(self, state: Dict[str, Any]):
        """Persist stack state to disk."""
        payload = dict(state or {})
        payload["stack"] = self.stack_name
        payload.setdefault("services", {})
        self.state_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def _pid_is_running(pid: int) -> bool:
        """Return whether a process ID is still alive."""
        return pid_is_running(pid)

    @staticmethod
    def _now() -> str:
        """Return the current UTC time in ISO format."""
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    def _probe_service(self, spec: ServiceSpec) -> Dict[str, Any]:
        """Probe one service health endpoint."""
        probe = {
            "healthy": False,
            "agent": "",
            "matches_expected_agent": False,
            "status_code": 0,
            "error": "",
        }
        try:
            response = requests.get(f"{spec.url}/health", timeout=0.5)
            probe["status_code"] = int(response.status_code)
            if response.status_code != 200:
                return probe
            payload = response.json() if response.content else {}
            probe["healthy"] = True
            probe["agent"] = str(payload.get("agent") or "")
            probe["matches_expected_agent"] = probe["agent"] == spec.expected_agent
            return probe
        except Exception as exc:
            probe["error"] = str(exc)
            return probe

    def _wait_for_service(self, spec: ServiceSpec, *, timeout_sec: float = 20.0) -> Dict[str, Any]:
        """Wait until one service reports a healthy endpoint."""
        deadline = time.time() + max(float(timeout_sec), 0.5)
        last_probe: Dict[str, Any] = {}
        while time.time() < deadline:
            probe = self._probe_service(spec)
            last_probe = probe
            if probe.get("healthy") and probe.get("matches_expected_agent"):
                return probe
            time.sleep(0.25)
        return last_probe

    def _stop_pid(self, pid: int):
        """Stop one managed process."""
        terminate_pid(pid, timeout_sec=5.0)

    def _service_log_path(self, service_name: str) -> Path:
        """Return the managed log path for one service."""
        return self.state_dir / f"{service_name}.log"

    def _runtime_config_path(self, service_name: str) -> Path:
        """Return the generated runtime config path for one service."""
        return self.state_dir / f"{service_name}.agent"

    def _build_runtime_config(self, spec: ServiceSpec) -> Path:
        """Write a temporary runtime config that keeps local bootstrap state out of the repo."""
        source_path = WORKSPACE_ROOT / spec.config_path
        payload = json.loads(source_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid config payload for {spec.name}: expected object")

        pools = payload.get("pools")
        if isinstance(pools, list):
            runtime_pool_root = self.state_dir / "storage" / spec.name
            runtime_pool_root.mkdir(parents=True, exist_ok=True)
            for index, pool in enumerate(pools):
                if not isinstance(pool, dict):
                    continue
                pool_type = str(pool.get("type") or "").strip()
                pool_name = str(pool.get("name") or f"pool-{index}").strip() or f"pool-{index}"
                safe_pool_name = pool_name.replace("/", "-")
                if pool_type == "FileSystemPool":
                    pool["root_path"] = str(runtime_pool_root / safe_pool_name)
                elif pool_type == "SQLitePool":
                    pool["db_path"] = str(runtime_pool_root / f"{safe_pool_name}.sqlite")

        runtime_config_path = self._runtime_config_path(spec.name)
        runtime_config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return runtime_config_path

    def _launch_service(self, spec: ServiceSpec) -> Dict[str, Any]:
        """Launch one background service."""
        log_path = self._service_log_path(spec.name)
        runtime_config_path = self._build_runtime_config(spec)
        command = [sys.executable, "-m", "prompits.create_agent", "--config", str(runtime_config_path)]
        with log_path.open("ab") as handle:
            process = subprocess.Popen(
                command,
                cwd=str(WORKSPACE_ROOT),
                stdout=handle,
                stderr=subprocess.STDOUT,
                **background_popen_kwargs(),
            )
        probe = self._wait_for_service(spec)
        if not (probe.get("healthy") and probe.get("matches_expected_agent")):
            self._stop_pid(process.pid)
            error_text = probe.get("error") or f"unexpected health response from {spec.url}"
            raise RuntimeError(f"{spec.name} did not become healthy: {error_text}")
        return {
            "pid": int(process.pid),
            "url": spec.url,
            "config_path": str(runtime_config_path),
            "source_config_path": spec.config_path,
            "log_path": str(log_path),
            "started_at": self._now(),
            "managed": True,
        }

    def status(self) -> List[Dict[str, Any]]:
        """Return current per-service status entries."""
        state = self._read_state()
        service_state = state.get("services") if isinstance(state.get("services"), dict) else {}
        statuses: List[Dict[str, Any]] = []
        for spec in self.services:
            current = service_state.get(spec.name) if isinstance(service_state.get(spec.name), dict) else {}
            pid = int(current.get("pid") or 0)
            probe = self._probe_service(spec)
            statuses.append(
                {
                    "name": spec.name,
                    "pid": pid,
                    "managed": bool(current.get("managed", False)),
                    "pid_running": self._pid_is_running(pid),
                    "healthy": bool(probe.get("healthy") and probe.get("matches_expected_agent")),
                    "agent": probe.get("agent") or "",
                    "url": spec.url,
                    "config_path": current.get("config_path") or str(self._runtime_config_path(spec.name)),
                    "source_config_path": current.get("source_config_path") or spec.config_path,
                    "log_path": current.get("log_path") or str(self._service_log_path(spec.name)),
                    "started_at": current.get("started_at") or "",
                    "external": bool(probe.get("healthy") and probe.get("matches_expected_agent") and not current.get("managed")),
                }
            )
        return statuses

    def up(self) -> List[Dict[str, Any]]:
        """Bring the stack up in dependency order."""
        state = self._read_state()
        services_state = state.get("services") if isinstance(state.get("services"), dict) else {}
        state["services"] = services_state
        started_now: List[int] = []

        try:
            for spec in self.services:
                current = services_state.get(spec.name) if isinstance(services_state.get(spec.name), dict) else {}
                pid = int(current.get("pid") or 0)
                probe = self._probe_service(spec)
                managed_running = bool(current.get("managed")) and self._pid_is_running(pid)
                if managed_running and probe.get("healthy") and probe.get("matches_expected_agent"):
                    continue
                if managed_running and not (probe.get("healthy") and probe.get("matches_expected_agent")):
                    self._stop_pid(pid)
                if probe.get("healthy") and probe.get("matches_expected_agent"):
                    services_state[spec.name] = {
                        "pid": 0,
                        "url": spec.url,
                        "config_path": str(self._runtime_config_path(spec.name)),
                        "source_config_path": spec.config_path,
                        "log_path": str(self._service_log_path(spec.name)),
                        "started_at": current.get("started_at") or self._now(),
                        "managed": False,
                    }
                    continue
                launch_info = self._launch_service(spec)
                services_state[spec.name] = launch_info
                started_now.append(int(launch_info["pid"]))
                self._write_state(state)
        except Exception:
            for pid in reversed(started_now):
                self._stop_pid(pid)
            raise

        self._write_state(state)
        return self.status()

    def down(self) -> List[Dict[str, Any]]:
        """Stop managed services for this stack."""
        state = self._read_state()
        services_state = state.get("services") if isinstance(state.get("services"), dict) else {}
        for spec in reversed(self.services):
            current = services_state.get(spec.name) if isinstance(services_state.get(spec.name), dict) else {}
            if not current.get("managed"):
                continue
            pid = int(current.get("pid") or 0)
            self._stop_pid(pid)
        state["services"] = {}
        self._write_state(state)
        return self.status()


def _print_status(manager: LocalStackManager, statuses: List[Dict[str, Any]]):
    """Print stack status in a compact human-readable format."""
    print(f"stack={manager.stack_name} state_dir={manager.state_dir}")
    for entry in statuses:
        mode = "external" if entry.get("external") else ("managed" if entry.get("managed") else "unmanaged")
        health = "healthy" if entry.get("healthy") else "down"
        pid_text = str(entry.get("pid") or "-")
        print(
            f"{entry['name']}: {health} mode={mode} pid={pid_text} url={entry['url']} "
            f"agent={entry.get('agent') or '-'} log={entry['log_path']}"
        )


def main():
    """Run the Prompits local stack CLI."""
    parser = argparse.ArgumentParser(description="Manage the Prompits local desk stack.")
    subparsers = parser.add_subparsers(dest="command")

    for command_name in ("up", "status", "down"):
        command_parser = subparsers.add_parser(command_name)
        command_parser.add_argument("stack", nargs="?", default="desk", help="Stack name. Defaults to 'desk'.")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    manager = LocalStackManager(args.stack)

    if args.command == "up":
        statuses = manager.up()
        _print_status(manager, statuses)
        print("ui=http://127.0.0.1:8214/")
        return
    if args.command == "status":
        _print_status(manager, manager.status())
        return
    if args.command == "down":
        _print_status(manager, manager.down())
        return

    raise ValueError(f"Unsupported command '{args.command}'")


if __name__ == "__main__":
    main()
