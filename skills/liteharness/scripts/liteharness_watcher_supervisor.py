#!/usr/bin/env python3
"""Keep the LiteHarness inbox watcher alive on Windows.

The supervisor owns the watcher as an attached child process. Running this
script directly should stream watcher stdout back to the caller, and stopping
the supervisor should also stop the watcher.
"""

from __future__ import annotations

import atexit
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path


STATE_ROOT = Path.home() / ".codex" / "memories" / "liteharness"
HARNESS_ROOT = Path.home() / ".liteharness"
AGENT_CONFIG_PATH = HARNESS_ROOT / "codex_agent.json"
WATCHER_PATH = Path(__file__).with_name("liteharness_inbox_watcher.py")
RESTART_DELAY_SEC = 2.0
PROCESS_AGENT_ID: str | None = None
STOP_REQUESTED = threading.Event()
WATCHER_PROCESS: subprocess.Popen[bytes] | None = None
HEARTBEAT_INTERVAL_SEC = 5.0


def agent_slug(agent_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in agent_id)


def valid_agent_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    agent_id = value.strip()
    return agent_id if agent_id else None


def state_path(agent_id: str | None, suffix: str) -> Path:
    slug = agent_slug(agent_id or "unknown")
    return STATE_ROOT / f"codex_inbox_{slug}_{suffix}"


def supervisor_pid_path() -> Path:
    return state_path(current_agent_id(), "supervisor.pid")


def supervisor_heartbeat_path() -> Path:
    return state_path(current_agent_id(), "supervisor.heartbeat.json")


def log_path() -> Path:
    return state_path(current_agent_id(), "watcher.log")


def append_log(message: str) -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with log_path().open("a", encoding="utf-8") as handle:
        handle.write(f"[{timestamp}] {message}\n")


def emit(message: str) -> None:
    append_log(message)
    print(f"[LiteHarness watcher supervisor] {message}", flush=True)


def write_pid_file() -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {"pid": os.getpid(), "started_at": time.time()}
    supervisor_pid_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")


def remove_pid_file() -> None:
    try:
        path = supervisor_pid_path()
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("pid") == os.getpid():
                path.unlink()
    except (OSError, json.JSONDecodeError):
        pass


def write_heartbeat(*, watcher_pid: int | None = None, last_error: str | None = None) -> None:
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "pid": os.getpid(),
        "agent_id": current_agent_id(),
        "updated_at": time.time(),
        "watcher_pid": watcher_pid,
        "last_error": last_error,
        "process_model": "attached",
    }
    supervisor_heartbeat_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")


def watcher_launcher() -> str:
    return sys.executable


def resolve_agent_id() -> str | None:
    env_agent_id = valid_agent_id(os.environ.get("LITEHARNESS_AGENT_ID"))
    if env_agent_id:
        return env_agent_id
    if not AGENT_CONFIG_PATH.exists():
        return None
    try:
        data = json.loads(AGENT_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return valid_agent_id(data.get("agent_id"))


def current_agent_id() -> str | None:
    global PROCESS_AGENT_ID
    if PROCESS_AGENT_ID is None:
        PROCESS_AGENT_ID = resolve_agent_id()
    return PROCESS_AGENT_ID


def launch_watcher() -> subprocess.Popen[bytes]:
    launcher = watcher_launcher()
    emit(f"starting attached watcher via {launcher}")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    agent_id = current_agent_id()
    if agent_id:
        env["LITEHARNESS_AGENT_ID"] = agent_id
    return subprocess.Popen(
        [launcher, str(WATCHER_PATH), "--print"],
        env=env,
        stdin=subprocess.DEVNULL,
        cwd=str(WATCHER_PATH.parent),
    )


def current_watcher_pid() -> int | None:
    watcher = WATCHER_PROCESS
    return watcher.pid if watcher is not None else None


def heartbeat_loop() -> None:
    while not STOP_REQUESTED.wait(HEARTBEAT_INTERVAL_SEC):
        try:
            write_heartbeat(watcher_pid=current_watcher_pid())
        except Exception as exc:
            append_log(f"heartbeat write failed: {exc!r}")


def terminate_watcher() -> None:
    watcher = WATCHER_PROCESS
    if watcher is None:
        return
    if watcher.returncode is not None:
        return
    try:
        watcher.terminate()
        watcher.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        watcher.kill()
        try:
            watcher.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            append_log(f"watcher pid {watcher.pid} did not exit after kill")
    except OSError:
        pass


def request_stop(_signum: int | None = None, _frame: object | None = None) -> None:
    STOP_REQUESTED.set()
    terminate_watcher()


def main() -> int:
    global WATCHER_PROCESS
    write_pid_file()
    atexit.register(remove_pid_file)
    atexit.register(terminate_watcher)
    for signum in ("SIGINT", "SIGTERM"):
        signal_value = getattr(signal, signum, None)
        if signal_value is not None:
            signal.signal(signal_value, request_stop)
    emit("supervisor started with attached watcher model")
    heartbeat = threading.Thread(target=heartbeat_loop, name="liteharness-heartbeat", daemon=True)
    heartbeat.start()

    while not STOP_REQUESTED.is_set():
        try:
            WATCHER_PROCESS = launch_watcher()
            write_heartbeat(watcher_pid=current_watcher_pid())
            return_code = WATCHER_PROCESS.wait()
            if STOP_REQUESTED.is_set():
                break
            emit(f"watcher exited with code {return_code}; restarting")
            time.sleep(RESTART_DELAY_SEC)
        except Exception as exc:
            emit(f"supervisor loop failed: {exc!r}")
            write_heartbeat(watcher_pid=current_watcher_pid(), last_error=repr(exc))
            time.sleep(RESTART_DELAY_SEC)
    emit("supervisor stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
