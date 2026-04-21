---
name: max-parallel
description: "Codex alias for structured parallel decomposition. Use when the user wants a task decomposed into dependent waves of parallel subagent work. Triggers on 'max parallel', 'parallelize this', 'spawn subagents', 'decompose and parallelize', 'break this into parallel tasks', or 'recursive decomposition'. NOT for simple swarms (use /max-swarm)."
---

# Maximum Parallelism Mode Activated

This is the Codex-adapted version of the Claude `max-parallel` skill. In Codex, implement this workflow with `update_plan`, `spawn_agent`, `send_input`, and `wait_agent`, following the same wave-based decomposition model as [`max-subagents-parallel`](C:\Users\Ryan\.codex\skills\max-subagents-parallel\SKILL.md).

## Workflow

1. Parse flags such as `--agents`, `--depth`, `--ensemble`, and `--strategy`.
2. Build a full task decomposition and dependency graph with `update_plan`.
3. Group work into parallel waves.
4. Use `spawn_agent` for independent Wave 1 tasks, preferring `explorer` for analysis and `worker` for implementation.
5. Progress wave by wave, waiting only when blocked.
6. Finish with a synthesis pass that merges results and checks completeness.

## Notes

- Prefer `max-subagents-parallel` when available; it already encodes the native Codex workflow.
- Use `max-swarm` instead when the work is simple fan-out across disjoint files/modules and does not need recursive wave planning.
