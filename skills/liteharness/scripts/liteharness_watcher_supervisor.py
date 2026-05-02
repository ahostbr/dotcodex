#!/usr/bin/env python3
"""Stdout-only LiteHarness watcher supervisor for Codex terminals."""

from __future__ import annotations

import os
import signal
import subprocess
import sys


child: subprocess.Popen[str] | None = None


def stop_child(_signum: int | None = None, _frame: object | None = None) -> None:
    if child and child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
    raise SystemExit(0)


def main() -> int:
    global child
    agent_id = os.environ.get("LITEHARNESS_AGENT_ID", "").strip()
    if not agent_id:
        print("LITEHARNESS_AGENT_ID is required.", file=sys.stderr, flush=True)
        return 2

    for name in ("SIGINT", "SIGTERM"):
        signum = getattr(signal, name, None)
        if signum is not None:
            signal.signal(signum, stop_child)

    child = subprocess.Popen(
        [sys.executable, "-m", "liteharness.hooks", "watch", "--agent-id", agent_id],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    try:
        assert child.stdout is not None
        for line in child.stdout:
            print(line, end="", flush=True)
        return child.wait()
    except KeyboardInterrupt:
        stop_child()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
