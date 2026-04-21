# Global Notes

Hard requirement: At the start of every Codex session, before doing substantial work, manually bootstrap LiteHarness from the current repo root by running `python "C:\Users\Ryan\.codex\skills\liteharness-manual-start\scripts\manual_liteharness.py" start --check-now`.

When collaboration or agent messaging matters, manually poll again with `python "C:\Users\Ryan\.codex\skills\liteharness-manual-start\scripts\manual_liteharness.py" check` after major tool use or when the user asks whether messages arrived.

Footnote: Also check Claude's global skills folder at `C:\Users\Ryan\.claude\skills` when a task may benefit from reusable skills or agent-specific instructions stored there.
