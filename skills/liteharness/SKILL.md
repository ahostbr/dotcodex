---
name: liteharness
description: LiteHarness agent orchestration — spawn, name, message, and control Claude Code sessions. Headless (ConPTY) and headed (UIAutomation) modes. Use when spawning agents, checking inbox, sending messages, discovering agents, controlling terminals, or when hooks fail. Triggers on 'liteharness', 'spawn', 'check inbox', 'send a message to', 'discover agents', 'who is online', 'watch inbox', 'start liteharness', 'send-input', 'read-output'.
---

# LiteHarness — Agent Orchestration

Spawn, name, message, and programmatically control Claude Code CLI sessions. Two control modes: **headless** (ConPTY daemon) and **headed** (UIAutomation on visible terminals). All commands use `python -m liteharness.cli` or the `liteharness` console script.

## Session Startup (MANDATORY)

Every agent MUST register on activation. Choose the inbox monitor path for the current surface:

1. **Claude Code / terminal agents: start the Monitor inbox watcher:**
   ```
   Monitor({ description: "LiteHarness inbox", persistent: true, timeout_ms: 3600000, command: "python -m liteharness.hooks watch --agent-id <YOUR-AGENT-ID>" })
   ```
2. **Codex Desktop sessions: do not start `python -m liteharness.hooks watch` for the same agent ID.** Use `manual_liteharness.py start --check-now`, then `manual_liteharness.py check` and `manual_liteharness.py codex-monitor status/logs` as needed. The legacy `hooks watch` path prints to stdout and renames messages to `done/`, so it can steal messages before the Codex Desktop auto-injector fires.
3. **Register with correct info:**
   ```bash
   python -m liteharness.cli register --agent-id <YOUR-AGENT-ID> --cli claude-code --model <your-model>
   ```
   Optionally add `--name "<NAME>"` to override your generated name.

Get your agent ID from the SessionStart hook output. Use the **full UUID** for all `--agent-id` and `--from` flags.

## Agent Naming

Every agent automatically gets a **deterministic two-word name** derived from its UUID (e.g., SwiftRelay, IronWatch, PrimeFlint). Same UUID always produces the same name — no storage needed, immune to presence file clobbering.

- `liteharness discover` shows: `SwiftRelay (fa88c542) claude-code/opus — 0s ago`
- Names appear in the status line and inter-agent messages
- 50×50 adjective+noun vocabulary = 2,500 unique combinations

**To override** (optional): `--name "Recon"` on register. Uniqueness enforced — duplicates blocked (first-come-first-served). Overrides stored in `~/.liteharness/names/<UUID>`, cleaned up with stale agents.

## Messaging

### Codex Windows Stable Send (PREFERRED)

When replying through LiteHarness from Codex on Windows, prefer the stable pending-send wrapper instead of direct dynamic `send` commands:

1. Write the target/message payload to `C:\Users\Ryan\.codex\memories\liteharness\pending_liteharness_send.json`:
   ```json
   {
     "target": "<agent-id>",
     "message": "message body"
   }
   ```
2. Run the already-whitelisted stable command:
   ```powershell
   python "C:\Users\Ryan\.codex\memories\liteharness\send_pending_liteharness.py"
   ```

Why: Codex execpolicy on Windows matches command tokens, and dynamic PowerShell `manual_liteharness.py send <target> "<message>"` calls change every time. The wrapper keeps the executed command stable while the dynamic payload lives under `~/.codex/memories`, which is writable. This avoids repeated permission prompts and bypasses the `~/.liteharness` workspace-write boundary through the existing execpolicy allow rule. Durable note: `C:\Users\Ryan\.codex\memories\liteharness\codex-liteharness-permission-workaround.md`.

**Send a message:**
```bash
python -m liteharness.cli send <agent-id> "message body" --from <YOUR-AGENT-ID>
```
Always pass `--from` with YOUR full UUID. Without it, sender detection may be wrong on multi-session machines. For Codex-to-Sentinel replies on Ryan's Windows machine, use the stable pending-send wrapper above unless Ryan explicitly asks to test direct `send`.

**Check inbox:** `python -m liteharness.hooks check`
**List messages:** `python -m liteharness.cli list`
**Discover agents:** `python -m liteharness.cli discover`

### Codex Inbox Watcher Safety

The standalone Codex inbox watcher must only inject into a verified target pane. Do not treat "focused Windows Terminal pane", "first pane in this Windows Terminal window", or process ancestry alone as a valid target; Windows Terminal can host several tabs/panes under the same process, and focus can belong to Sentinel or another agent.

Correct targeting flow for Codex/WT delivery:

1. Resolve the target agent ID from the SessionStart UUID or `LITEHARNESS_AGENT_ID`.
2. Prefer `liteharness.terminal_automation.find_pane_by_buffer_markers([...])` with markers such as the full agent UUID, transcript filename stem, or thread ID.
3. Store `target.json` only when the pane buffer identifies that agent/session. A good target records `capture: "agent-buffer"` and `matched_markers`.
4. Before injecting, validate the saved pane with `read_buffer(handle, pane_id)` and clear the target if the buffer no longer identifies the agent.
5. Restart the per-agent monitor after targeting-code changes:
   ```powershell
   $env:LITEHARNESS_AGENT_ID="<agent-id>"; python "C:\Users\Ryan\.codex\skills\liteharness-manual-start\scripts\manual_liteharness.py" codex-monitor restart
   ```

Use `codex-monitor status` and the per-agent watcher log to verify delivery. A correct headed delivery log names the exact WT pane, for example `injected message ... into 133230:0`; it must not say Codex Desktop when the recipient is a terminal agent.

## Spawning Agents

Spawn new Claude Code sessions. **Default is always headless PTY mode** — only use headed/terminal mode if Ryan explicitly asks for a visible terminal.

### PTY Mode (DEFAULT) — headless, full programmatic control
```bash
liteharness pty-daemon                              # start daemon first (port 7450)
liteharness spawn --pty --model haiku --name "Worker" --prompt "run the tests"
liteharness send-input <agent-id> "fix the auth bug" # send prompts
liteharness send-input <agent-id> "/compact"         # send slash commands
liteharness send-input <agent-id> "/clear"
liteharness send-input <agent-id> "/exit"
liteharness read-output <agent-id>                   # read agent's terminal output
liteharness pty-list                                 # list all PTY sessions
liteharness pty-kill <agent-id>                      # kill a session
```
The daemon auto-starts if needed. Token-authenticated — only processes that can read `~/.liteharness/pty_daemon.lock` can connect. Executable whitelist: only `claude`, `codex`, `python` can be spawned.

### Terminal Mode — visible tab, no stdin control
```bash
liteharness spawn --model opus --cwd C:/Projects/LiteSuite --name "Recon" --prompt "fix the auth bug"
```
Opens a new Windows Terminal tab. You can see the agent work but can't programmatically send it commands. Only use when Ryan explicitly asks for a visible terminal.

### Headed Mode — visible tab WITH programmatic control
```bash
liteharness spawn --model opus --name "Recon"        # spawns visible WT tab
liteharness wt-list-panes                            # find window handles + pane IDs
liteharness send-input --headed <handle:pane> "text"  # UIAutomation clipboard paste
liteharness read-output --headed <handle:pane>        # UIAutomation buffer read
liteharness wt-focus <handle> <pane-id>              # focus a pane
```
Uses Windows UIAutomation to read terminal buffers and inject keystrokes via **clipboard paste** (atomic, no race conditions). Handle:pane format is colon-separated (e.g., `35654038:2`).

**Python API for headed mode:**
```python
from liteharness.terminal_automation import (
    find_pane_by_buffer_markers,
    find_pane_by_title,
    list_panes,
    read_buffer,
    send_input,
)

# Find a pane
panes = list_panes()  # returns all WT windows with panes and shells
handle, pane_id = find_pane_by_title("Recon")  # convenience finder
target = find_pane_by_buffer_markers(["<full-agent-uuid>", "<thread-or-transcript-marker>"])

# Read and write
output = read_buffer(handle, pane_id)  # terminal buffer text
send_input(handle, pane_id, "/compact")  # auto-appends {ENTER}
send_input(handle, pane_id, "^c", auto_enter=False)  # Ctrl+C, no Enter
```

### Spawn Options
| Flag | Description |
|------|-------------|
| `--model <name>` | opus, opus-1m, opus-200k, sonnet, haiku, or full model ID |
| `--cwd <path>` | Working directory |
| `--worktree` | Create a git worktree before spawning |
| `--permission-mode <mode>` | default, plan, auto, bypassPermissions (default), acceptEdits |
| `--prompt <text>` | Initial prompt |
| `--name <name>` | Agent name override |
| `--new-window` | New WT window instead of tab |
| `--pty` | Headless ConPTY mode |
| `--args <extra>` | Additional CLI arguments |

All spawned agents default to `bypassPermissions` and receive bootstrap instructions to self-register and start their inbox monitor.

## Agent Lifecycle — /clear vs /exit

**Prefer `/clear` over `/exit` when reassigning an agent to a new task.**

- **`/clear`** — Resets the Claude Code session inside the same terminal tab. The agent gets a fresh context, a new session ID, and a new auto-generated name. The terminal stays open — just send the next prompt or task directly into it. No tab churn, no need to spawn a new terminal.
- **`/exit`** — Kills the Claude Code process AND closes the terminal tab. Only use this when you're truly done with that terminal and don't need it anymore.

**Pattern for task rotation:**
1. Agent finishes task, reports back
2. Send `/clear` via UIAutomation or PTY (`liteharness send-input <id> "/clear"`)
3. Wait for the session to reset (agent gets new ID, re-registers)
4. Send the next task prompt into the same terminal
5. The agent picks up the new work in a clean context

This is more efficient than spawning a new terminal for every task. One terminal tab can handle an entire chain of tasks sequentially.

## UIAutomation Rules

- Default timeout is **60 seconds** — NEVER lower it. Only increase for very long messages.
- `send_input()` auto-appends `{ENTER}` — text is submitted automatically.
- Text is injected via **clipboard paste** (Ctrl+V), not keystroke-by-keystroke. This is atomic and prevents race conditions when multiple agents type simultaneously.
- Previous clipboard content is saved and restored after paste.
- Special keys (`{ENTER}`, `{TAB}`, `^c`, `%x`) use SendKeys directly — they bypass clipboard.
- Treat only `*TermControl*` elements as terminal panes. Generic `ControlType.Pane` elements are layout containers and can shift pane numbering.
- For agent routing, prefer buffer-marker matching over focus, pane title, shell name, or process ancestry. Focus is a UI state, not identity.
- If a saved headed target does not validate with `read_buffer()` against the intended agent markers, clear it and leave the message in the inbox instead of injecting.

## PTY Daemon

The ConPTY daemon (`pty_daemon.py`) runs headlessly (`CREATE_NO_WINDOW`) and auto-starts via `ensure_daemon()`. Key behaviors:
- **Headless by default** — no visible terminal window, fully invisible background process
- **Auto-shutdown** — kills itself after 2 hours idle with no active sessions
- **Token race protection** — `ensure_daemon()` checks if port 7450 is in use before spawning a new daemon
- **Prompt delivery** — initial prompt sent via stdin 8s after spawn (Claude Code needs time to init)
- **Per-session send queue** — FIFO queue with single consumer thread serializes concurrent writes to the same PTY

### Security
- **Bearer token** — generated at startup, stored in lock file, required on every request
- **Executable whitelist** — only `claude`, `codex`, `python` allowed
- **Shell metachar block** — `; & |` and `$` rejected in executable/flags (prompts exempt)
- **Agent ID validation** — alphanumeric/dash/underscore only, max 128 chars
- **CWD validation** — must be an existing directory (path traversal blocked)
- **Max 20 sessions** — prevents resource exhaustion
- **64KB recv cap** — prevents memory DoS
- **8KB input cap** — prevents stdin injection overflow
- **Dangerous control chars blocked** — null bytes, Ctrl+Z stripped
- **Error sanitization** — no file paths or PIDs leaked in responses

## Architecture

| Path | Purpose |
|------|---------|
| `~/.liteharness/` | Runtime root (global, shared across all CLIs) |
| `~/.liteharness/inbox/{new,cur,done,tmp}/` | Maildir-style message inbox |
| `~/.liteharness/agents/<id>.json` | Agent presence files (heartbeat, model, CLI) |
| `~/.liteharness/names/<id>` | Name overrides (plain text, immune to clobbering) |
| `~/.liteharness/pty_daemon.lock` | PTY daemon token + port (auto-created) |
| `~/.liteharness/config.json` | Global config |
| `C:/Projects/LiteSuite/packages/liteharness/` | Package source |

## Hook Integration

Claude Code hooks in `~/.claude/settings.json` auto-handle:
- `SessionStart` → `python -m liteharness.hooks register` (presence + identity block)
- `SessionStart` → `python -m liteharness.hooks check` (initial inbox check)
- `PostToolUse` → `python -m liteharness.hooks check` (throttled inbox polling)

If hooks aren't firing, use this skill's manual commands as fallback.

## Polymathic Agent Spawning (MANDATORY)

**All read-only agents (scouts, investigators, researchers) MUST be spawned as polymathic agents.** Include a cognitive architecture prompt to ensure full coherence with the 5-tier harness system.

### For Agent() sub-agents (ephemeral):
```
Agent({ subagent_type: "polymathic-feynman", prompt: "Investigate X..." })
Agent({ subagent_type: "polymathic-carmack", prompt: "Trace the system path for Y..." })
```

### For terminal spawns (persistent):
Include the polymathic cognitive architecture in the `--prompt` flag. Match the polymath to the task:

| Task Type | Polymath | Why |
|-----------|----------|-----|
| Investigation / debugging | `polymathic-feynman` | First-principles, freshman test, cargo cult detection |
| Systems tracing / performance | `polymathic-carmack` | Constraint-first, find the real bottleneck |
| Architecture analysis | `polymathic-shannon` | Strip to invariant skeleton, find hidden structure |
| Code review / taste | `polymathic-linus` | Structural elegance, good taste, BS detection |
| Cross-domain synthesis | `polymathic-lovelace` | "What else has this structure?" pattern transfer |

**Why this matters:** Generic agents produce shallow findings. Polymathic agents apply structural thinking — they catch what generalists miss. Every agent in the harness system operates through a cognitive lens. Spawning without one breaks coherence.

## Dispatch Table

| User says | Action |
|-----------|--------|
| "check inbox" / "any messages?" | `python -m liteharness.hooks check` |
| "send X to agent Y" | Codex on Windows: write `pending_liteharness_send.json`, then run `python "C:\Users\Ryan\.codex\memories\liteharness\send_pending_liteharness.py"` |
| "who is online" / "discover agents" | `python -m liteharness.cli discover` |
| "spawn an agent" | `liteharness spawn --pty --model <model> --name <name> --prompt <task>` (ALWAYS headless PTY by default) |
| "send /compact to Recon" | `liteharness send-input <id> "/compact"` (PTY) or `--headed` (UIAutomation) |
| "what's Recon doing?" | `liteharness read-output <id>` (PTY) or `--headed <handle:pane>` |
| "reassign that agent" | Send `/clear` via UIAutomation or PTY, then send new prompt — reuses the terminal tab |
| "kill that agent" | `liteharness pty-kill <id>` (PTY) or `liteharness send-input <id> "/exit"` (closes tab — only when truly done) |
| "list terminals" | `liteharness wt-list-panes` |
| "start liteharness" | `python -m liteharness.hooks register` |
