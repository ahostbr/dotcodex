#!/usr/bin/env python3
"""Deprecated compatibility wrapper for the stdout-only Codex watcher."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    agent_id = os.environ.get("LITEHARNESS_AGENT_ID", "").strip()
    if not agent_id:
        print("LITEHARNESS_AGENT_ID is required.", file=sys.stderr, flush=True)
        return 2
    return subprocess.call(
        [sys.executable, "-m", "liteharness.hooks", "watch", "--agent-id", agent_id],
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )


if __name__ == "__main__":
    raise SystemExit(main())
