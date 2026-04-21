#!/usr/bin/env python3
"""Manual LiteHarness bootstrap for Codex sessions without working hooks."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import liteharness.config as config
import liteharness.hooks as hooks
import liteharness.inbox as inbox


DEFAULT_ROOT = Path.home() / ".liteharness"


def configure_root(root: Path) -> Path:
    root = root.resolve()

    config.HARNESS_ROOT = root
    config.CONFIG_PATH = root / "config.json"

    inbox.INBOX_ROOT = root / "inbox"
    inbox.INBOX_NEW = inbox.INBOX_ROOT / "new"
    inbox.INBOX_CUR = inbox.INBOX_ROOT / "cur"
    inbox.INBOX_DONE = inbox.INBOX_ROOT / "done"
    inbox.INBOX_TMP = inbox.INBOX_ROOT / "tmp"

    hooks.LAST_CHECK_FILE = root / ".last_inbox_check"
    return root


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_project() -> str:
    return str(Path.cwd())


def ensure_agent_id(*, fresh: bool) -> str:
    # Use a Codex-specific config file to avoid clobbering other CLIs' agent IDs
    codex_cfg_path = config.get_root() / "codex_agent.json"
    codex_cfg: dict = {}
    if codex_cfg_path.exists():
        try:
            codex_cfg = json.loads(codex_cfg_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    existing = codex_cfg.get("agent_id", "")
    if fresh or not existing.startswith("codex-"):
        codex_cfg["agent_id"] = f"codex-{uuid.uuid4().hex[:12]}"
    codex_cfg["cli"] = "codex-cli-manual"

    config.ensure_root()
    codex_cfg_path.write_text(json.dumps(codex_cfg, indent=2), encoding="utf-8")
    os.environ["LITEHARNESS_AGENT_ID"] = codex_cfg["agent_id"]
    return codex_cfg["agent_id"]


def write_presence(agent_id: str) -> Path:
    agents_dir = config.get_root() / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    presence = {
        "agent_id": agent_id,
        "model": config.get_model(),
        "cli": "codex-cli-manual",
        "project": current_project(),
        "started_at": utc_now(),
        "last_seen": utc_now(),
        "pid": os.getpid(),
    }
    path = agents_dir / f"{agent_id}.json"
    path.write_text(json.dumps(presence, indent=2), encoding="utf-8")
    return path


def update_presence_heartbeat(agent_id: str) -> None:
    path = config.get_root() / "agents" / f"{agent_id}.json"
    if not path.exists():
        return
    try:
        presence = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    presence["last_seen"] = utc_now()
    try:
        path.write_text(json.dumps(presence, indent=2), encoding="utf-8")
    except OSError:
        return


def claim_messages(agent_id: str) -> list[dict]:
    claimed = []
    for message in inbox.poll(agent_id):
        if inbox.claim(message):
            claimed.append(message)
    return claimed


def print_messages(messages: list[dict]) -> None:
    print(f"[LITEHARNESS] {len(messages)} message(s) received:")
    print("")
    for msg in messages:
        sender = msg.get("from", "unknown")
        priority = msg.get("priority", "normal")
        msg_type = msg.get("type", "notification")
        body = msg.get("body", "")
        thread = msg.get("thread_id")
        project = msg.get("project")
        prefix = "[URGENT] " if priority == "urgent" else ""

        print(f"  {prefix}From: {sender} ({msg_type})")
        if project:
            print(f"  Project: {project}")
        if thread:
            print(f"  Thread: {thread}")
        print(f"  {body}")
        print("")
        print(f"  To reply, run: python scripts/manual_liteharness.py send {sender} \"your reply here\"")
        if thread:
            print(f"    Use --thread-id {thread}")
        print("")

        if msg_type == "notification":
            inbox.complete(msg)


def cmd_start(args: argparse.Namespace) -> int:
    agent_id = ensure_agent_id(fresh=args.fresh_agent)
    presence_path = write_presence(agent_id)
    print("[LITEHARNESS] Manual session started.")
    print(f"  Agent ID: {agent_id}")
    print(f"  Root: {config.get_root()}")
    print(f"  Presence: {presence_path}")
    print("")
    print("  Next commands:")
    print("    python scripts/manual_liteharness.py check")
    print("    python scripts/manual_liteharness.py discover")
    print("    python scripts/manual_liteharness.py send <agent-id> \"message\"")
    print("    python scripts/manual_liteharness.py watch")
    if args.check_now:
        print("")
        return cmd_check(args)
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    agent_id = config.get_agent_id()
    claimed = claim_messages(agent_id)
    if not claimed:
        update_presence_heartbeat(agent_id)
        print(f"[LITEHARNESS] No new messages for {agent_id}.")
        return 0
    print_messages(claimed)
    update_presence_heartbeat(agent_id)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    agent_id = config.get_agent_id()
    print(f"[LITEHARNESS] Entering watch mode for {agent_id} at {config.get_root()}...")
    seen_ids: set[str] = set()
    watcher = hooks._create_watcher(str(inbox.INBOX_NEW))

    while True:
        try:
            watcher.wait(timeout=5.0)
            claimed = []
            for message in claim_messages(agent_id):
                msg_id = message.get("id", "")
                if msg_id in seen_ids:
                    continue
                seen_ids.add(msg_id)
                claimed.append(message)
            if claimed:
                print_messages(claimed)
            update_presence_heartbeat(agent_id)
        except KeyboardInterrupt:
            print("[LITEHARNESS] Watch stopped.")
            return 0
        except Exception:
            pass
        time.sleep(2)
    return 0


def cmd_discover(args: argparse.Namespace) -> int:
    agents_dir = config.get_root() / "agents"
    if not agents_dir.exists():
        print(f"[LITEHARNESS] No agents directory at {agents_dir}. Run start first.")
        return 0

    found = []
    for path in sorted(agents_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        found.append(
            (
                data.get("agent_id", path.stem),
                data.get("cli", "unknown"),
                data.get("model", "unknown"),
                data.get("last_seen", "unknown"),
                data.get("project", ""),
            )
        )

    if not found:
        print(f"[LITEHARNESS] No registered agents under {agents_dir}.")
        return 0

    print(f"[LITEHARNESS] Active agents in {config.get_root()}:")
    for agent_id, cli, model, last_seen, project in found:
        print(f"  - {agent_id} | {cli} | {model} | last_seen={last_seen}")
        if project:
            print(f"    project={project}")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    agent_id = config.get_agent_id()
    msg_id = inbox.send(
        from_agent=agent_id,
        to_agent=args.to_agent,
        body=args.message,
        thread_id=args.thread_id,
        priority=args.priority,
        msg_type=args.message_type,
        project=current_project(),
        cli="codex-cli-manual",
        model=config.get_model(),
    )
    update_presence_heartbeat(agent_id)
    print(f"[LITEHARNESS] Sent {msg_id} to {args.to_agent}.")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    agent_id = config.get_agent_id()
    new_count = 0
    if inbox.INBOX_NEW.exists():
        new_count = len(list(inbox.INBOX_NEW.glob("*.json")))
    print("[LITEHARNESS] Status")
    print(f"  Root: {config.get_root()}")
    print(f"  Agent ID: {agent_id}")
    print(f"  Inbox new/: {new_count}")
    print(f"  Project: {current_project()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manual LiteHarness bootstrap for Codex sessions."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="LiteHarness runtime root. Defaults to .liteharness/codex-cli under the current repo.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser("start", help="Register this Codex session with LiteHarness.")
    start.add_argument(
        "--fresh-agent",
        action="store_true",
        help="Generate a new repo-local agent ID instead of reusing the saved one.",
    )
    start.add_argument(
        "--check-now",
        action="store_true",
        help="Run an immediate inbox check after registering presence.",
    )
    start.set_defaults(func=cmd_start)

    check = subparsers.add_parser("check", help="Poll the inbox once.")
    check.set_defaults(func=cmd_check)

    watch = subparsers.add_parser("watch", help="Watch the inbox continuously.")
    watch.set_defaults(func=cmd_watch)

    discover = subparsers.add_parser("discover", help="List agents registered under the current root.")
    discover.set_defaults(func=cmd_discover)

    send = subparsers.add_parser("send", help="Send a LiteHarness message.")
    send.add_argument("to_agent", help="Target agent ID or broadcast.")
    send.add_argument("message", help="Message body.")
    send.add_argument(
        "--thread-id",
        default=None,
        help="Optional thread ID for replies or grouped conversations.",
    )
    send.add_argument(
        "--priority",
        choices=["normal", "urgent"],
        default="normal",
        help="Message priority.",
    )
    send.add_argument(
        "--message-type",
        choices=["notification", "request", "reply"],
        default="notification",
        help="Semantic message type.",
    )
    send.set_defaults(func=cmd_send)

    status = subparsers.add_parser("status", help="Show the current runtime status.")
    status.set_defaults(func=cmd_status)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    configure_root(args.root)
    # Read Codex-specific agent ID (not global config which may have another CLI's ID)
    codex_cfg_path = config.get_root() / "codex_agent.json"
    if codex_cfg_path.exists():
        try:
            codex_cfg = json.loads(codex_cfg_path.read_text(encoding="utf-8"))
            agent_id = codex_cfg.get("agent_id")
            if agent_id:
                os.environ["LITEHARNESS_AGENT_ID"] = agent_id
        except (json.JSONDecodeError, OSError):
            pass
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
