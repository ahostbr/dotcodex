#!/usr/bin/env python3
"""Deprecated Codex notify hook for LiteHarness.

Codex inbox delivery is stdout-only now. Start
`liteharness_watcher_supervisor.py` in an attached terminal so it can run
`python -m liteharness.hooks watch --agent-id <id>` and stream messages.
"""

from __future__ import annotations

import json
import os
import sys


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

    agent_id = os.environ.get("LITEHARNESS_AGENT_ID", "").strip()
    if agent_id:
        print(
            "LiteHarness Codex watcher is stdout-only. "
            "Run liteharness_watcher_supervisor.py attached for agent "
            f"{agent_id}.",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
