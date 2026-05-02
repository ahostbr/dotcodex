---
name: liteharness-manual-start
description: Manual LiteHarness session bootstrap and inbox management for Codex, especially on Windows when native CLI hooks are unavailable or unreliable. Use when Codex needs to start LiteHarness at session start, poll for new messages after tool use, watch the inbox, discover active agents, or send LiteHarness messages without depending on automatic hook execution.
---

# LiteHarness Manual Start

Use the bundled wrapper to run LiteHarness manually from Codex.

The wrapper defaults to the global runtime at `~/.liteharness`, which is shared across all CLIs (Claude Code, Codex, Copilot, etc.) for cross-CLI messaging.

## Workflow

1. Start LiteHarness for the current repo:

```bash
python scripts/manual_liteharness.py start
```

2. Replace `PostToolUse` checks by polling manually whenever collaboration matters:

```bash
python scripts/manual_liteharness.py check
```

3. Discover active agents or send a message when needed:

```bash
python scripts/manual_liteharness.py discover
python scripts/manual_liteharness.py send <agent-id> "message"
```

4. Use stdout watch mode only when a long-running foreground process is acceptable. For Codex terminal sessions, prefer the attached supervisor:

```bash
$env:LITEHARNESS_AGENT_ID="<agent-id>"
python "C:\Users\Ryan\.codex\skills\liteharness\scripts\liteharness_watcher_supervisor.py"
```

## Operational Notes

- Prefer `start` once near the beginning of a session.
- Prefer `check` after major tool use, after waiting on subagents, or whenever the user asks whether messages arrived.
- The default root is `~/.liteharness` (global, shared across CLIs). Override only if you need a repo-local runtime:

```bash
python scripts/manual_liteharness.py start --root ".liteharness/codex-cli"
```

- `start` reuses the saved agent ID for the current Codex thread or Windows Terminal session by default, using `CODEX_THREAD_ID`/`WT_SESSION` to persist per-session state.
- This stable identity is required so other agents can reply after compaction, watcher restarts, or repeated manual bootstrap calls.
- Use `--fresh-agent` only when you intentionally want to rotate to a new identity inside the same session.
- If `check` reports no messages, continue normally. This skill is a manual fallback for hookless environments, not a blocker.
- Codex watcher implementation changes must be tested by running `liteharness_watcher_supervisor.py` directly with `LITEHARNESS_AGENT_ID` set, sending the agent a LiteHarness message, and confirming the message prints to stdout. Do not use UIAutomation, clipboard paste, SendKeys, or pane injection in the Codex watcher path.

## Script

`scripts/manual_liteharness.py` supports:

- `start`
- `check`
- `watch`
- `discover`
- `send`
- `status`

Run `python scripts/manual_liteharness.py --help` for flags.
