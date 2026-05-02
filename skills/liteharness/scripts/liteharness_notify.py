#!/usr/bin/env python3
"""Codex notify hook bootstrap for the LiteHarness inbox watcher."""

from __future__ import annotations

import json
import os
import base64
import signal
import subprocess
import sys
import time
from pathlib import Path

from liteharness import desktop_automation
from liteharness import terminal_automation


HARNESS_ROOT = Path.home() / ".liteharness"
AGENT_CONFIG_PATH = HARNESS_ROOT / "codex_agent.json"
SESSION_STATE_DIR = HARNESS_ROOT / "codex_sessions"
STATE_ROOT = Path.home() / ".codex" / "memories" / "liteharness"
WATCHER_PATH = Path(__file__).with_name("liteharness_watcher_supervisor.py")
MAX_HEARTBEAT_AGE_SEC = 20


def agent_slug(agent_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in agent_id)


def valid_agent_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    agent_id = value.strip()
    return agent_id if agent_id else None


def state_path(agent_id: str, suffix: str) -> Path:
    return STATE_ROOT / f"codex_inbox_{agent_slug(agent_id)}_{suffix}"


def supervisor_pid_path(agent_id: str) -> Path:
    return state_path(agent_id, "supervisor.pid")


def supervisor_heartbeat_path(agent_id: str) -> Path:
    return state_path(agent_id, "supervisor.heartbeat.json")


def target_path(agent_id: str) -> Path:
    return state_path(agent_id, "target.json")


def read_pid(agent_id: str) -> int | None:
    path = supervisor_pid_path(agent_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
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


def heartbeat_is_fresh(agent_id: str) -> bool:
    data = read_heartbeat(agent_id)
    updated_at = data.get("updated_at")
    if not isinstance(updated_at, (int, float)):
        return False
    return (time.time() - float(updated_at)) <= MAX_HEARTBEAT_AGE_SEC


def read_heartbeat(agent_id: str) -> dict:
    path = supervisor_heartbeat_path(agent_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def read_agent_id() -> str | None:
    env_agent_id = valid_agent_id(os.environ.get("LITEHARNESS_AGENT_ID"))
    if env_agent_id:
        return env_agent_id

    session_agent_id = read_session_agent_id()
    if session_agent_id:
        return session_agent_id

    if AGENT_CONFIG_PATH.exists():
        try:
            data = json.loads(AGENT_CONFIG_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        agent_id = valid_agent_id(data.get("agent_id"))
        if agent_id:
            return agent_id

    return None


def read_session_agent_id() -> str | None:
    for env_name in ("CODEX_THREAD_ID", "WT_SESSION"):
        session_key = os.environ.get(env_name, "").strip()
        if not session_key:
            continue
        safe_key = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in session_key)
        session_path = SESSION_STATE_DIR / f"{safe_key}.json"
        if not session_path.exists():
            continue
        try:
            data = json.loads(session_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        agent_id = valid_agent_id(data.get("agent_id"))
        if agent_id:
            return agent_id
    return None


def sync_legacy_agent_config(agent_id: str) -> None:
    # Session-keyed Codex agents must not fight over this legacy singleton.
    # Watchers are launched with LITEHARNESS_AGENT_ID, and session identity is
    # persisted under codex_sessions; rewriting codex_agent.json here can
    # retarget unrelated background watchers in concurrent sessions.
    if os.environ.get("CODEX_THREAD_ID") or os.environ.get("WT_SESSION"):
        return
    try:
        HARNESS_ROOT.mkdir(parents=True, exist_ok=True)
        payload = {
            "agent_id": agent_id,
            "last_session_key": os.environ.get("CODEX_THREAD_ID") or os.environ.get("WT_SESSION"),
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cli": "codex-cli-manual",
            "surface": "terminal",
        }
        AGENT_CONFIG_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        pass


def read_agent_presence(agent_id: str) -> dict:
    path = HARNESS_ROOT / "agents" / f"{agent_id}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def agent_buffer_markers(agent_id: str) -> list[str]:
    markers = [agent_id]
    presence = read_agent_presence(agent_id)
    transcript_path = str(presence.get("transcript_path") or "")
    if transcript_path:
        markers.append(Path(transcript_path).stem)
    thread_id = str(presence.get("thread_id") or "")
    if thread_id:
        markers.append(thread_id)
    return [marker for marker in dict.fromkeys(markers) if marker]


def target_agent_id(agent_id: str) -> str | None:
    path = target_path(agent_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    agent_id = data.get("agent_id")
    return agent_id if isinstance(agent_id, str) and agent_id else None


def stop_pid(pid: int | None) -> None:
    if not isinstance(pid, int) or pid <= 0 or not pid_is_alive(pid):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass


def legacy_hooks_watch_pids(agent_id: str) -> list[int]:
    """Find old hook watch consumers that can steal inbox messages for this agent."""
    if os.name != "nt" or not agent_id:
        return []
    script = r"""
$ErrorActionPreference = 'SilentlyContinue'
$agentId = [string]$env:LITEHARNESS_AGENT_ID
$currentPid = [int]$env:LITEHARNESS_CURRENT_PID
$rows = Get-CimInstance Win32_Process | Where-Object {
  $_.ProcessId -ne $currentPid -and
  $_.CommandLine -and
  $_.CommandLine -match '(?i)(^|\s)-m\s+liteharness\.hooks(\s|$)' -and
  $_.CommandLine -match '(?i)\bwatch\b' -and
  $_.CommandLine -like '*--agent-id*' -and
  $_.CommandLine -like "*$agentId*"
} | Select-Object -ExpandProperty ProcessId
$rows | ConvertTo-Json -Compress
"""
    env = os.environ.copy()
    env["LITEHARNESS_AGENT_ID"] = agent_id
    env["LITEHARNESS_CURRENT_PID"] = str(os.getpid())
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        raw = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    values = raw if isinstance(raw, list) else [raw]
    return [pid for pid in values if isinstance(pid, int) and pid > 0 and pid != os.getpid()]


def stop_legacy_hooks_watchers(agent_id: str) -> int:
    stopped = 0
    for pid in legacy_hooks_watch_pids(agent_id):
        stop_pid(pid)
        stopped += 1
    return stopped


def capture_focused_target(agent_id: str) -> None:
    if os.environ.get("LITESUITE_BRIDGE_TOKEN"):
        return
    presence = read_agent_presence(agent_id)
    presence_wt_session = presence.get("wt_session")
    surface = presence.get("surface")
    is_terminal_agent = surface == "terminal"
    if surface == "desktop":
        capture_codex_desktop_target(agent_id)
        return
    if is_terminal_agent:
        if presence_wt_session and not os.environ.get("WT_SESSION"):
            os.environ["WT_SESSION"] = str(presence_wt_session)
        if capture_target_by_agent_buffer(agent_id):
            return
        if capture_target_by_process_ancestry(agent_id):
            if validate_target_buffer(agent_id):
                return
            try:
                target_path(agent_id).unlink(missing_ok=True)
            except OSError:
                pass
            return
        return
    if not os.environ.get("WT_SESSION"):
        capture_codex_desktop_target(agent_id)
        return
    if capture_target_by_process_ancestry(agent_id):
        return

    try:
        windows = terminal_automation.list_panes()
    except Exception:
        # Do not fall back to "whatever Windows Terminal pane is focused".
        # That can tag Sentinel's pane as this Codex agent and paste future
        # inbox messages into the wrong terminal. If ancestry mapping fails,
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
                "agent_id": agent_id,
            }
            target_path(agent_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return
    return


def capture_target_by_agent_buffer(agent_id: str) -> bool:
    markers = agent_buffer_markers(agent_id)
    try:
        data = terminal_automation._run_ps_script(
            "find_pane_by_buffer_markers.ps1",
            args={"markers": markers, "sampleChars": 2_000_000},
            timeout=8,
        )
    except Exception:
        return False
    candidates = data.get("candidates", []) if isinstance(data, dict) else []
    if not isinstance(candidates, list):
        candidates = []
    presence = read_agent_presence(agent_id)
    project_name = Path(str(presence.get("project") or "")).name.lower()
    if project_name:
        project_candidates = [
            candidate for candidate in candidates
            if project_name in str(candidate.get("window_title") or "").lower()
        ]
        if project_candidates:
            candidates = project_candidates
    target = None
    if candidates:
        target = sorted(
            candidates,
            key=lambda candidate: (
                int(candidate.get("score") or 0),
                1 if candidate.get("focused") else 0,
            ),
            reverse=True,
        )[0]
    elif isinstance(data, dict):
        target = data.get("match")
    if not isinstance(target, dict):
        return False
    window_handle = target.get("window_handle")
    pane_id = target.get("pane_id")
    if not isinstance(window_handle, int) or not isinstance(pane_id, int):
        return False
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    presence = read_agent_presence(agent_id)
    payload = {
        "window_handle": window_handle,
        "pane_id": pane_id,
        "window_title": target.get("window_title", ""),
        "pane_title": target.get("pane_title", ""),
        "wt_session": os.environ.get("WT_SESSION") or presence.get("wt_session"),
        "captured_at": time.time(),
        "mode": "windows-terminal-headed",
        "agent_id": agent_id,
        "capture": "agent-buffer",
        "matched_markers": target.get("matched_markers", []),
        "score": target.get("score"),
    }
    target_path(agent_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return True


def validate_target_buffer(agent_id: str) -> bool:
    path = target_path(agent_id)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if data.get("mode") != "windows-terminal-headed":
        return True
    window_handle = data.get("window_handle")
    pane_id = data.get("pane_id")
    if not isinstance(window_handle, int) or not isinstance(pane_id, int):
        return False
    try:
        buffer = terminal_automation.read_buffer(window_handle, pane_id) or ""
    except Exception:
        return False
    for marker in agent_buffer_markers(agent_id):
        if marker.lower() in buffer.lower():
            data["capture_validated_at"] = time.time()
            try:
                path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except OSError:
                pass
            return True
    return False


def capture_target_by_process_ancestry(agent_id: str) -> bool:
    presence = read_agent_presence(agent_id)
    target_pid = presence.get("pid")
    if not isinstance(target_pid, int) or target_pid <= 0:
        return False
    script = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$targetPid = [int]$env:LITEHARNESS_TARGET_PID
$seen = @{}
$ancestors = @{}
$currentPid = $targetPid
while ($currentPid -and -not $seen.ContainsKey($currentPid)) {
  $seen[$currentPid] = $true
  $row = Get-CimInstance Win32_Process -Filter "ProcessId=$currentPid"
  if (-not $row) { break }
  $ancestors[[int]$row.ProcessId] = $true
  $currentPid = [int]$row.ParentProcessId
}
$root = [System.Windows.Automation.AutomationElement]::RootElement
$condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty, 'CASCADIA_HOSTING_WINDOW_CLASS')
$windows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $condition)
foreach ($window in $windows) {
  $current = $window.Current
  $windowPid = [int]$current.ProcessId
  if (-not $ancestors.ContainsKey($windowPid)) { continue }
  $desc = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
  $panes = @()
  $paneId = 0
  foreach ($child in $desc) {
    try {
      $c = $child.Current
      $className = [string]$c.ClassName
      $controlType = $c.ControlType.ProgrammaticName
      if ($controlType -eq 'ControlType.Pane' -or $className -like '*TermControl*') {
        $panes += [pscustomobject]@{ id = $paneId; title = [string]$c.Name; class_name = $className; focused = [bool]$c.HasKeyboardFocus }
        $paneId += 1
      }
    } catch {}
  }
  $selected = $panes | Where-Object { $_.focused -and $_.class_name -like '*TermControl*' } | Select-Object -First 1
  if (-not $selected) {
    $selected = $panes | Where-Object { $_.class_name -like '*TermControl*' } | Select-Object -First 1
  }
  if ($selected) {
    [pscustomobject]@{
      window_handle = [int]$current.NativeWindowHandle
      pane_id = [int]$selected.id
      window_title = [string]$current.Name
      pane_title = [string]$selected.title
    } | ConvertTo-Json -Compress
    exit 0
  }
}
"""
    env = os.environ.copy()
    env["LITEHARNESS_TARGET_PID"] = str(target_pid)
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if result.returncode != 0 or not result.stdout.strip():
        return False
    try:
        target = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False
    if not isinstance(target, dict):
        return False
    window_handle = target.get("window_handle")
    pane_id = target.get("pane_id")
    if not isinstance(window_handle, int) or not isinstance(pane_id, int):
        return False
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "window_handle": window_handle,
        "pane_id": pane_id,
        "window_title": target.get("window_title", ""),
        "pane_title": target.get("pane_title", ""),
        "wt_session": os.environ.get("WT_SESSION") or presence.get("wt_session"),
        "captured_at": time.time(),
        "mode": "windows-terminal-headed",
        "agent_id": agent_id,
        "capture": "process-ancestry",
        "process_pid": target_pid,
    }
    target_path(agent_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return True


def capture_codex_desktop_target(agent_id: str) -> None:
    """Capture Codex Desktop when this session is not running in Windows Terminal."""
    try:
        windows = desktop_automation.list_codex_windows()
    except Exception:
        return
    if len(windows) != 1:
        return
    window = windows[0]
    handle = window.get("handle")
    if not isinstance(handle, int):
        return
    STATE_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "window_handle": handle,
        "window_title": window.get("title", ""),
        "surface": "desktop",
        "mode": "codex-desktop",
        "capture": "codex-desktop-window",
        "captured_at": time.time(),
        "agent_id": agent_id,
    }
    target_path(agent_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def capture_focused_target_simple(agent_id: str) -> None:
    """Fallback target capture that avoids CIM/process enumeration."""
    script = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$condition = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty, 'CASCADIA_HOSTING_WINDOW_CLASS')
$windows = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $condition)
$out = @()
foreach ($window in $windows) {
  $current = $window.Current
  $desc = $window.FindAll([System.Windows.Automation.TreeScope]::Descendants, [System.Windows.Automation.Condition]::TrueCondition)
  $panes = @()
  $paneId = 0
  foreach ($child in $desc) {
    try {
      $c = $child.Current
      if ($c.ClassName -like '*TermControl*' -or $c.ControlType.ProgrammaticName -eq 'ControlType.Pane') {
        $panes += [pscustomobject]@{ id = $paneId; title = [string]$c.Name; class_name = [string]$c.ClassName; focused = [bool]$c.HasKeyboardFocus }
        $paneId += 1
      }
    } catch {}
  }
  $out += [pscustomobject]@{ handle = [int]$current.NativeWindowHandle; title = [string]$current.Name; panes = $panes }
}
$out | ConvertTo-Json -Depth 6 -Compress
"""
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return
    if result.returncode != 0 or not result.stdout.strip():
        return
    try:
        windows = json.loads(result.stdout)
    except json.JSONDecodeError:
        return
    if isinstance(windows, dict):
        windows = [windows]
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
                "agent_id": agent_id,
                "capture": "uia-fallback-no-cim",
            }
            target_path(agent_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return


def refresh_existing_target_agent(agent_id: str) -> None:
    """Keep the headed target identity aligned even when capture cannot run."""
    path = target_path(agent_id)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(data, dict):
        return
    presence = read_agent_presence(agent_id)
    presence_wt_session = presence.get("wt_session")
    if presence.get("surface") == "terminal" and data.get("mode") == "codex-desktop":
        try:
            path.unlink()
        except OSError:
            pass
        return
    if data.get("mode") == "codex-desktop":
        data["agent_id"] = agent_id
        data["target_refreshed_at"] = time.time()
        try:
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError:
            pass
        return
    target_wt_session = data.get("wt_session")
    current_wt_session = os.environ.get("WT_SESSION") or presence_wt_session
    if current_wt_session and not target_wt_session and data.get("mode") != "windows-terminal-headed":
        try:
            path.unlink()
        except OSError:
            pass
        return
    if target_wt_session and current_wt_session and target_wt_session != current_wt_session:
        try:
            path.unlink()
        except OSError:
            pass
        return
    data["agent_id"] = agent_id
    data["target_refreshed_at"] = time.time()
    try:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


def ensure_watcher_running(agent_id: str, *, force_restart: bool = False) -> None:
    existing_pid = read_pid(agent_id)
    heartbeat = read_heartbeat(agent_id)
    watcher_pid = heartbeat.get("watcher_pid")
    saved_target_agent = target_agent_id(agent_id)
    if existing_pid and pid_is_alive(existing_pid) and heartbeat_is_fresh(agent_id) and not force_restart:
        if saved_target_agent in (None, agent_id):
            return

        if isinstance(watcher_pid, int) and watcher_pid != existing_pid:
            stop_pid(watcher_pid)
        stop_pid(existing_pid)

        deadline = time.time() + 5.0
        while time.time() < deadline:
            supervisor_alive = pid_is_alive(existing_pid)
            watcher_alive = isinstance(watcher_pid, int) and pid_is_alive(watcher_pid)
            if not supervisor_alive and not watcher_alive:
                break
            time.sleep(0.25)

    env = os.environ.copy()
    env["LITEHARNESS_AGENT_ID"] = agent_id
    env["PYTHONUNBUFFERED"] = "1"

    subprocess.Popen(
        [sys.executable, str(WATCHER_PATH)],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=None if sys.stdout.isatty() else subprocess.DEVNULL,
        stderr=None if sys.stderr.isatty() else subprocess.DEVNULL,
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

    agent_id = read_agent_id()
    if not agent_id:
        return 0

    previous_target_agent = target_agent_id(agent_id)
    force_restart = previous_target_agent is not None and previous_target_agent != agent_id
    sync_legacy_agent_config(agent_id)
    stop_legacy_hooks_watchers(agent_id)
    ensure_watcher_running(agent_id, force_restart=force_restart)
    capture_focused_target(agent_id)
    refresh_existing_target_agent(agent_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
