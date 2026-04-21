---
name: max-subagents-parallel
description: "Use when decomposing a task into parallel subtasks with structured subagent spawning and wave-based execution. Triggers on 'max-subagents-parallel', 'max parallel', 'parallelize this', 'spawn subagents', 'parallel subagents', 'decompose and parallelize', 'spin up parallel agents', 'recursive decomposition', 'break this into parallel tasks', or any request for structured task decomposition with parallel agent execution. NOT for simple agent swarms (use max-swarm)."
---

# Maximum Parallelism Mode Activated

You are now in **MAX PARALLEL** mode for Codex. Use `update_plan`, `spawn_agent`, `send_input`, and `wait_agent` to execute a task in dependency-aware waves.

## Flag Parsing

Parse the user's input for these flags:

| Flag | Default | Effect |
|------|---------|--------|
| `--agents N` | 8 | Max subagents per wave |
| `--depth N` | 1 | Recursive decomposition depth |
| `--ensemble` | off | Multiple agents analyze the same critical question |
| `--strategy S` | recursive | `recursive`, `ensemble`, or `sweep` |

Example: `/max-subagents-parallel --agents 6 --strategy sweep --depth 2`

## Workflow

1. Parse flags and infer the user's real objective.
2. Build a full decomposition and dependency graph with `update_plan`.
3. Group independent work into waves.
4. Spawn all independent work for the current wave before waiting.
5. Advance wave by wave until the task is complete.
6. Finish with a synthesis/verification pass.

## Strategies

### `recursive`
Use the default approach:
- Decompose the task into independent subtasks.
- Spawn a mix of `explorer` and `worker` agents as appropriate.
- Synthesize after each blocking wave.

### `ensemble`
Use for high-stakes decisions:
- Give the same question to 2-3 agents with different framing.
- Compare outputs.
- Run a synthesis pass that reconciles disagreement.

### `sweep`
Use for codebase discovery:
- Maximize breadth in Wave 1.
- Give each explorer a different angle.
- Synthesize into one coherent map before implementation.

## Agent Selection

| Work Type | Agent Type |
|-----------|------------|
| Read-only exploration | `explorer` |
| Concrete implementation on a bounded scope | `worker` |
| Cross-cutting synthesis | `default` or local synthesis by the main agent |

## Agent Prompt Rules

Every spawned agent must receive:
- A concrete scope
- Its ownership boundary
- The reminder that it is not alone in the codebase
- Instructions not to revert edits made by others
- A request to list changed files in the final response when it edits code

Use prompts in this shape:

```text
You own: <files/modules/scope>

Task:
<subtask>

Constraints:
- You are not alone in the codebase. Do not revert other agents' edits.
- Stay within your assigned scope unless absolutely necessary.
- If you change files, list them in your final response.
```

## Wave Rules

- **Wave 1:** All tasks with no blockers
- **Wave 2+:** Tasks blocked only by completed prior waves
- **Final wave:** Synthesis and validation

Do not `wait_agent` early unless you are blocked on the result.

## Depth

If `--depth >= 2`, delegated agents may themselves decompose further. Only do this when the decomposition is still crisp and the added parallelism is worth the overhead.

## Iron Law

> If tasks are independent, they must run in parallel.

## Quick Reference

```text
/max-subagents-parallel Add user authentication
/max-subagents-parallel --agents 6 --strategy sweep Explore this codebase
/max-subagents-parallel --ensemble Should we use Redis or PostgreSQL?
/max-subagents-parallel --depth 2 --agents 8 Refactor the auth system
```
