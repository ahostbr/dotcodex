---
name: daily
description: "Use when the user wants to view or add an entry to today's daily note. Triggers on '/daily', 'daily note', 'add to today', 'journal entry', 'log this for today', or any request to record something timestamped for the current day. Not for creating named notes (use 'note') or searching past notes (use 'vault-search')."
allowed-tools: mcp__litememory__vault_daily, mcp__litememory__vault_read, mcp__litememory__vault_write
---

Manage today's daily note in the Obsidian vault.

## Steps

1. **Get/create daily note** by calling vault_daily (auto-creates from template if it doesn't exist)

2. **If no arguments** (`$ARGUMENTS` is empty): Display today's note content formatted nicely

3. **If arguments provided**:
   - Read current daily note content
   - Append entry under the "## Log" heading with timestamp prefix: `- HH:MM — $ARGUMENTS`
   - Write updated content back using vault_write

4. **Show confirmation** of what was added or displayed
