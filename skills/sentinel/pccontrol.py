"""Sentinel Desktop Control — Win32 mouse/keyboard/window automation via PowerShell.

Ported from Kuroryuu k_pccontrol. No armed flag — Sentinel is trusted.
Usage from Claude Code Bash tool:
    python ~/.claude/skills/sentinel/pccontrol.py click 500 300
    python ~/.claude/skills/sentinel/pccontrol.py doubleclick 500 300
    python ~/.claude/skills/sentinel/pccontrol.py rightclick 500 300
    python ~/.claude/skills/sentinel/pccontrol.py type "Hello World"
    python ~/.claude/skills/sentinel/pccontrol.py keypress Enter
    python ~/.claude/skills/sentinel/pccontrol.py keypress ctrl+c
    python ~/.claude/skills/sentinel/pccontrol.py launch notepad.exe
    python ~/.claude/skills/sentinel/pccontrol.py windows
    python ~/.claude/skills/sentinel/pccontrol.py status
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Optional


def _run_ps(script: str, timeout: int = 10) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True, timeout=timeout,
    )


def click(x: int, y: int) -> str:
    ps = f'''
Add-Type @"
using System; using System.Runtime.InteropServices;
public class M {{
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")] public static extern void mouse_event(int f, int dx, int dy, int d, int e);
}}
"@
[M]::SetCursorPos({x},{y}); Start-Sleep -Milliseconds 50
[M]::mouse_event(0x02,0,0,0,0); [M]::mouse_event(0x04,0,0,0,0)
'''
    r = _run_ps(ps)
    return f"clicked ({x},{y})" if r.returncode == 0 else f"ERROR: {r.stderr}"


def doubleclick(x: int, y: int) -> str:
    ps = f'''
Add-Type @"
using System; using System.Runtime.InteropServices;
public class M {{
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")] public static extern void mouse_event(int f, int dx, int dy, int d, int e);
}}
"@
[M]::SetCursorPos({x},{y}); Start-Sleep -Milliseconds 50
[M]::mouse_event(0x02,0,0,0,0); [M]::mouse_event(0x04,0,0,0,0)
Start-Sleep -Milliseconds 50
[M]::mouse_event(0x02,0,0,0,0); [M]::mouse_event(0x04,0,0,0,0)
'''
    r = _run_ps(ps)
    return f"double-clicked ({x},{y})" if r.returncode == 0 else f"ERROR: {r.stderr}"


def rightclick(x: int, y: int) -> str:
    ps = f'''
Add-Type @"
using System; using System.Runtime.InteropServices;
public class M {{
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")] public static extern void mouse_event(int f, int dx, int dy, int d, int e);
}}
"@
[M]::SetCursorPos({x},{y}); Start-Sleep -Milliseconds 50
[M]::mouse_event(0x08,0,0,0,0); [M]::mouse_event(0x10,0,0,0,0)
'''
    r = _run_ps(ps)
    return f"right-clicked ({x},{y})" if r.returncode == 0 else f"ERROR: {r.stderr}"


def type_text(text: str) -> str:
    escaped = text
    for char in ['+', '^', '%', '~', '(', ')', '{', '}', '[', ']']:
        escaped = escaped.replace(char, '{' + char + '}')
    escaped = escaped.replace('"', '`"')
    ps = f'''
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("{escaped}")
'''
    r = _run_ps(ps)
    return f"typed {len(text)} chars" if r.returncode == 0 else f"ERROR: {r.stderr}"


KEY_MAP = {
    "enter": "{ENTER}", "return": "{ENTER}", "tab": "{TAB}",
    "escape": "{ESC}", "esc": "{ESC}", "backspace": "{BACKSPACE}",
    "delete": "{DELETE}", "del": "{DELETE}", "insert": "{INSERT}",
    "home": "{HOME}", "end": "{END}",
    "pageup": "{PGUP}", "pgup": "{PGUP}", "pagedown": "{PGDN}", "pgdn": "{PGDN}",
    "up": "{UP}", "down": "{DOWN}", "left": "{LEFT}", "right": "{RIGHT}",
    "space": " ",
    "f1": "{F1}", "f2": "{F2}", "f3": "{F3}", "f4": "{F4}",
    "f5": "{F5}", "f6": "{F6}", "f7": "{F7}", "f8": "{F8}",
    "f9": "{F9}", "f10": "{F10}", "f11": "{F11}", "f12": "{F12}",
    "ctrl+a": "^a", "ctrl+c": "^c", "ctrl+v": "^v", "ctrl+x": "^x",
    "ctrl+z": "^z", "ctrl+y": "^y", "ctrl+s": "^s",
    "alt+f4": "%{F4}", "alt+tab": "%{TAB}",
}


def keypress(key: str) -> str:
    sendkey = KEY_MAP.get(key.lower().strip())
    if not sendkey:
        sendkey = key if len(key) == 1 else None
    if not sendkey:
        return f"ERROR: unknown key '{key}'. Available: {', '.join(sorted(KEY_MAP.keys()))}"
    ps = f'''
Add-Type -AssemblyName System.Windows.Forms
[System.Windows.Forms.SendKeys]::SendWait("{sendkey}")
'''
    r = _run_ps(ps)
    return f"pressed {key}" if r.returncode == 0 else f"ERROR: {r.stderr}"


def launch(path: str) -> str:
    escaped = path.replace("'", "''")
    r = _run_ps(f"Start-Process -FilePath '{escaped}'", timeout=30)
    return f"launched {path}" if r.returncode == 0 else f"ERROR: {r.stderr}"


def get_windows() -> str:
    ps = '''
Get-Process | Where-Object {$_.MainWindowTitle -ne ""} | ForEach-Object {
    [PSCustomObject]@{
        Process = $_.ProcessName
        Title = $_.MainWindowTitle
        PID = $_.Id
        Handle = $_.MainWindowHandle
    }
} | ConvertTo-Json -Compress
'''
    r = _run_ps(ps)
    if r.returncode != 0:
        return f"ERROR: {r.stderr}"
    out = r.stdout.strip()
    if not out:
        return "No windows found"
    windows = json.loads(out)
    if isinstance(windows, dict):
        windows = [windows]
    lines = [f"  {w.get('Process','?'):20s} | {w.get('Title','')[:60]}" for w in windows]
    return f"{len(windows)} windows:\n" + "\n".join(lines)


def status() -> str:
    try:
        r = _run_ps('Add-Type -AssemblyName System.Windows.Forms; Write-Output "ready"', timeout=5)
        if r.returncode == 0 and "ready" in r.stdout:
            return "OK: PowerShell + System.Windows.Forms ready"
        return f"ERROR: PowerShell test failed: {r.stderr}"
    except Exception as e:
        return f"ERROR: {e}"


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: pccontrol.py <action> [args...]")
        print("Actions: click, doubleclick, rightclick, type, keypress, launch, windows, status")
        sys.exit(1)

    action = args[0].lower()

    if action == "click" and len(args) >= 3:
        print(click(int(args[1]), int(args[2])))
    elif action == "doubleclick" and len(args) >= 3:
        print(doubleclick(int(args[1]), int(args[2])))
    elif action == "rightclick" and len(args) >= 3:
        print(rightclick(int(args[1]), int(args[2])))
    elif action == "type" and len(args) >= 2:
        print(type_text(" ".join(args[1:])))
    elif action == "keypress" and len(args) >= 2:
        print(keypress(args[1]))
    elif action == "launch" and len(args) >= 2:
        print(launch(args[1]))
    elif action == "windows":
        print(get_windows())
    elif action == "status":
        print(status())
    else:
        print(f"Unknown action or missing args: {action}")
        sys.exit(1)


if __name__ == "__main__":
    main()
