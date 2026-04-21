---
name: max-swarm
description: Use when the user explicitly wants to spawn multiple coding agents working on independent files or modules simultaneously. Triggers on 'max-swarm', 'swarm this', 'swarm it', 'spawn a swarm', 'coding swarm', 'spin up agents', 'one agent per file', 'throw agents at this', or any request to fan out work across many parallel coding agents. NOT for structured decomposition (use max-subagents-parallel).
---

# /max-swarm - Parallel Codex Agent Swarm

Spawn multiple Codex subagents in parallel to work on a task. Only use this skill when the user has explicitly asked for a swarm, parallel agents, or delegated multi-agent work.

## Flags

Parse the user's input for flags:

| Flag | Effect |
|------|--------|
| `--unattended` | Use `worker` agents and give them ownership of concrete write scopes |
| `--read-only` | Use `explorer` agents for analysis-only work |

**Examples:**
- `/max-swarm "document codebase"` → Default worker swarm
- `/max-swarm --unattended "refactor auth"` → Worker swarm with broader implementation latitude
- `/max-swarm --read-only "explore the codebase"` → Explorer-only swarm

## When Invoked

The user provides a task description. You will:
1. Decompose it into 2-5 independent subtasks
2. Spawn a Codex subagent for each subtask
3. Report which agent owns which slice

## Step 1: Task Decomposition

Analyze the task and decompose into **2-5 independent subtasks** that can be worked on in parallel.

Consider:
- What parts of the codebase need attention?
- What can be done independently without blocking?
- What's the optimal breakdown for parallel work?

**Examples:**
- "Document codebase" → Gateway docs, Desktop docs, MCP tools docs, AI harness docs
- "Review feature X" → Store review, Component review, Hook review, API review
- "Add tests" → Unit tests, Integration tests, E2E tests

## Step 2: Spawn Agents in Parallel

For each subtask, use `spawn_agent` with:
- `agent_type: explorer` for `--read-only`
- `agent_type: worker` otherwise
- `fork_context: true`
- Clear ownership of files/modules for every worker
- A reminder that the worker is not alone in the codebase and must not revert other agents' edits

Use prompts in this shape:

```text
You own: <files/modules/scope>

Task:
<subtask>

Constraints:
- You are not alone in the codebase. Do not revert edits made by others.
- Work only within your assigned scope unless absolutely necessary.
- If you make code changes, list the files you changed in your final response.
```

Spawn all independent subtasks first. Only call `wait_agent` once you are genuinely blocked on the results or ready to synthesize.

## Step 3: Report Results

After spawning, provide a summary:

```
## Swarm Deployed

| Agent | Task | Session ID |
|-------|------|------------|
| Worker/Explorer | Document Gateway | abc123 |
| Worker/Explorer | Document Desktop | def456 |
| Worker/Explorer | Document MCP | ghi789 |

**Status:** All agents launched
```

## Rules

1. **ALWAYS decompose** - Never spawn just 1 agent unless the task truly has only one independent slice
2. **ALWAYS parallelize independent work** - Launch all non-blocked subtasks before waiting
3. **Assign ownership** - Each worker must own a clear file/module scope
4. **Target 3-5 agents** - Sweet spot for most tasks
5. **Focused subtasks** - Each agent should have a clear, bounded scope

## Example Invocations

**User:** `/max-swarm "Write comprehensive documentation for Kuroryuu"`

**Response:**
```
Decomposing into parallel subtasks...

Spawning swarm of 4 Codex agents:

1. Gateway Architecture Documentation
2. Desktop Application Documentation
3. MCP Tools Documentation
4. AI Harness Documentation

[Spawn 4 agents in parallel with `spawn_agent`...]

## Swarm Deployed

| Agent | Task | Session ID |
|-------|------|------------|
| Worker | Gateway docs | a1b2c3 |
| Worker | Desktop docs | d4e5f6 |
| Worker | MCP tools docs | g7h8i9 |
| Worker | AI harness docs | j0k1l2 |

Wait for results only when blocked or ready to synthesize.
```

## Agent Mapping

| Scenario | Agent type |
|----------|------------|
| Read-only exploration | `explorer` |
| Coding on disjoint files/modules | `worker` |
| Mixed analysis + implementation | `worker` for code, `explorer` for sidecar analysis |
