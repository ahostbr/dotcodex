#!/usr/bin/env python3
"""Keep the LiteHarness inbox watcher alive on Windows."""

from __future__ import annotations

import atexit
import json
import os
import subprocess
import sys
import time
from pathlib import Path


STATE_ROOT = Path.home() / ".codex" / "memories" / "liteharness"
HARNESS_ROOT = Path.home() / ".liteharness"
AGENT_CONFIG_PATH = HARNESS_ROOT / "codex_agent.json"
WATCHER_PATH = Path(__file__).with_name("liteharness_inbox_watcher.py")
RESTART_DELAY_SEC = 2.0
PROCESS_AGENT_ID: str | None = None


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
    }
    supervisor_heartbeat_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")


def watcher_launcher() -> str:
    python_exe = Path(sys.executable)
    if python_exe.name.lower() == "python.exe":
        pythonw = python_exe.with_name("pythonw.exe")
        if pythonw.exists():
            return str(pythonw)
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
    creationflags = 0
    for name in ("CREATE_NEW_PROCESS_GROUP", "DETACHED_PROCESS", "CREATE_NO_WINDOW"):
        creationflags |= getattr(subprocess, name, 0)

    launcher = watcher_launcher()
    append_log(f"starting watcher via {launcher}")
    env = os.environ.copy()
    agent_id = current_agent_id()
    if agent_id:
        env["LITEHARNESS_AGENT_ID"] = agent_id
    return subprocess.Popen(
        [launcher, str(WATCHER_PATH)],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
        cwd=str(WATCHER_PATH.parent),
    )


def main() -> int:
    write_pid_file()
    atexit.register(remove_pid_file)
    append_log("supervisor started")

    watcher: subprocess.Popen[bytes] | None = None

    while True:
        try:
            if watcher is None or watcher.poll() is not None:
                if watcher is not None:
                    append_log(f"watcher exited with code {watcher.returncode}; restarting")
                    time.sleep(RESTART_DELAY_SEC)
                watcher = launch_watcher()
            write_heartbeat(watcher_pid=watcher.pid if watcher else None)
            time.sleep(5.0)
        except Exception as exc:
            append_log(f"supervisor loop failed: {exc!r}")
            write_heartbeat(watcher_pid=watcher.pid if watcher else None, last_error=repr(exc))
            time.sleep(RESTART_DELAY_SEC)


if __name__ == "__main__":
    raise SystemExit(main())
