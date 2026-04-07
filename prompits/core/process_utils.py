"""Cross-platform subprocess helpers for background services."""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from typing import Any


def background_popen_kwargs() -> dict[str, Any]:
    """Return Popen kwargs for launching a managed background process."""
    if os.name == "nt":
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        return {"creationflags": flags} if flags else {}
    return {"start_new_session": True}


def pid_is_running(pid: int) -> bool:
    """Return whether a process ID appears to still be alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def terminate_pid(pid: int, *, timeout_sec: float = 5.0):
    """Terminate one managed process by PID."""
    if pid <= 0 or not pid_is_running(pid):
        return
    _request_shutdown(pid)
    if _wait_for_pid_exit(pid, timeout_sec=timeout_sec):
        return
    _force_kill(pid)
    _wait_for_pid_exit(pid, timeout_sec=2.0)


def terminate_process(process: subprocess.Popen[Any], *, timeout_sec: float = 5.0):
    """Terminate one managed subprocess and any children it owns."""
    if process.poll() is not None:
        return
    pid = int(process.pid or 0)
    if pid <= 0:
        with contextlib.suppress(Exception):
            process.terminate()
        return
    _request_shutdown(pid, process=process)
    if _wait_for_process_exit(process, timeout_sec=timeout_sec):
        return
    _force_kill(pid, process=process)
    _wait_for_process_exit(process, timeout_sec=2.0)


def _request_shutdown(pid: int, *, process: subprocess.Popen[Any] | None = None):
    """Ask a process to stop cleanly when the platform supports it."""
    if os.name == "nt":
        ctrl_break = getattr(signal, "CTRL_BREAK_EVENT", None)
        if ctrl_break is not None:
            with contextlib.suppress(Exception):
                if process is not None:
                    process.send_signal(ctrl_break)
                else:
                    os.kill(pid, ctrl_break)
                return
        with contextlib.suppress(Exception):
            if process is not None:
                process.terminate()
            else:
                os.kill(pid, signal.SIGTERM)
        return

    with contextlib.suppress(Exception):
        if hasattr(os, "killpg"):
            os.killpg(pid, signal.SIGTERM)
        elif process is not None:
            process.terminate()
        else:
            os.kill(pid, signal.SIGTERM)


def _force_kill(pid: int, *, process: subprocess.Popen[Any] | None = None):
    """Force-kill a process tree."""
    if os.name == "nt":
        with contextlib.suppress(Exception):
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return
        with contextlib.suppress(Exception):
            if process is not None:
                process.kill()
            else:
                os.kill(pid, signal.SIGTERM)
        return

    with contextlib.suppress(Exception):
        if hasattr(os, "killpg"):
            os.killpg(pid, getattr(signal, "SIGKILL", signal.SIGTERM))
        elif process is not None:
            process.kill()
        else:
            os.kill(pid, getattr(signal, "SIGKILL", signal.SIGTERM))


def _wait_for_pid_exit(pid: int, *, timeout_sec: float) -> bool:
    """Wait until a PID disappears."""
    deadline = time.time() + max(float(timeout_sec), 0.0)
    while time.time() < deadline:
        if not pid_is_running(pid):
            return True
        time.sleep(0.1)
    return not pid_is_running(pid)


def _wait_for_process_exit(process: subprocess.Popen[Any], *, timeout_sec: float) -> bool:
    """Wait until a subprocess exits."""
    deadline = time.time() + max(float(timeout_sec), 0.0)
    while time.time() < deadline:
        if process.poll() is not None:
            return True
        time.sleep(0.1)
    return process.poll() is not None
