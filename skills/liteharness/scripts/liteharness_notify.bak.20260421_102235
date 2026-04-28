#!/usr/bin/env python3
"""Codex notify hook bootstrap for the LiteHarness inbox watcher."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from liteharness import terminal_automation


STATE_ROOT = Path.home() / ".codex" / "memories" / "liteharness"
PID_PATH = STATE_ROOT / "codex_inbox_supervisor.pid"
HEARTBEAT_PATH = STATE_ROOT / "codex_inbox_supervisor.heartbeat.json"
WATCHER_PATH = Path(__file__).with_name("liteharness_watcher_supervisor.py")
TARGET_PATH = STATE_ROOT / "codex_inbox_target.json"
MAX_HEARTBEAT_AGE_SEC = 20


def read_pid() -> int | None:
    if not PID_PATH.exists():
        return None
    try:
        data = json.loads(PID_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    pid = data.get("pid")
    return pid if isinstance(pid, int) and pid > 0 else None


def pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        check=False,
        capture_output=True,
        text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output = (result.stdout or "").strip()
    if not output or output.startswith("INFO:"):
        return False
    return str(pid) in output


def heartbeat_is_fresh() -> bool:
    if not HEARTBEAT_PATH.exists():
        return False
    try:
        data = json.loads(HEARTBEAT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    updated_at = data.get("updated_at")
    if not isinstance(updated_at, (int, float)):
        return False
    return (time.time() - float(updated_at)) <= MAX_HEARTBEAT_AGE_SEC


def capture_focused_target() -> None:
    if os.environ.get("LITESUITE_BRIDGE_TOKEN"):
        return
    if not os.environ.get("WT_SESSION"):
        return

    try:
        windows = terminal_automation.list_panes()
    except Exception:
        return
    for window in windows:
        for pane in window.get("panes", []):
            if not pane.get("focused"):
                continue
            if pane.get("class_name") != "TermControl":
                continue
            STATE_ROOT.mkdir(parents=True, exist_ok=True)
            payload = {
                "window_handle": int(window["handle"]),
                "pane_id": int(pane["id"]),
                "window_title": window.get("title", ""),
                "pane_title": pane.get("title", ""),
                "wt_session": os.environ.get("WT_SESSION"),
                "captured_at": time.time(),
                "mode": "windows-terminal-headed",
            }
            TARGET_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return


def ensure_watcher_running() -> None:
    existing_pid = read_pid()
    if existing_pid and pid_is_alive(existing_pid) and heartbeat_is_fresh():
        return

    launcher = sys.executable
    python_exe = Path(sys.executable)
    if python_exe.name.lower() == "python.exe":
        pythonw = python_exe.with_name("pythonw.exe")
        if pythonw.exists():
            launcher = str(pythonw)

    creationflags = 0
    for name in ("CREATE_NEW_PROCESS_GROUP", "DETACHED_PROCESS", "CREATE_NO_WINDOW"):
        creationflags |= getattr(subprocess, name, 0)

    subprocess.Popen(
        [launcher, str(WATCHER_PATH)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
        cwd=str(WATCHER_PATH.parent),
    )


def main() -> int:
    if len(sys.argv) > 1:
        try:
            payload = json.loads(sys.argv[-1])
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            event_type = payload.get("type")
            if event_type and event_type != "agent-turn-complete":
                return 0

    ensure_watcher_running()
    capture_focused_target()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
