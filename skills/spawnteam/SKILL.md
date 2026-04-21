---
name: spawnteam
description: Use when the user explicitly wants a collaborative multi-agent team for a task. Triggers on 'spawn team', 'spawnteam', 'create a team', 'team up', 'spawn agents for', 'collaborative agents', 'multi-agent team', 'agent team', 'set up a team', 'spin up a team', 'get a team working on', 'thinker-debate', 'prd-workflow', 'security-audit team', 'code-review team', or 'feature-dev team'. NOT for single-agent delegation (use spawn_agent directly), NOT for file-level swarms (use /max-swarm), NOT for wave planning (use /max-subagents-parallel).
---

# Spawn Codex Agent Team

Create and orchestrate a Codex agent team using `update_plan`, `spawn_agent`, `send_input`, and `wait_agent`.

## Input Parsing

Parse:
- `--template <name>` for a preset team shape
- `--count N` for teammate count
- `--model <model>` for default teammate model
- `--dry-run` to show the team plan only
- Plain text as the task description

## Core Rule

Only use this skill when the user explicitly wants a team. If they only want a few parallel workers on disjoint scopes, use `/max-swarm` instead.

## Workflow

1. Analyze the task and explore the codebase as needed.
2. Decompose it into 2-6 roles.
3. Build a team plan with `update_plan`.
4. If `--dry-run`, stop after presenting the plan.
5. Spawn teammates with `spawn_agent`.
6. Route clarifications with `send_input` when needed.
7. Use `wait_agent` for checkpoints and synthesis.

## Team Composition

Common patterns:

| Template | Suggested Roles |
|----------|-----------------|
| `code-review` | security reviewer, performance reviewer, test reviewer |
| `feature-dev` | architect, backend implementer, frontend implementer, reviewer |
| `research` | breadth researcher, depth researcher, critical researcher |
| `debug` | data investigator, code investigator, system investigator |
| `thinker-debate` | two contrasting analysts |

## Spawning Rules

- Use `worker` agents for implementation roles.
- Use `explorer` agents for read-only research/review roles.
- Give every teammate a clear role and scope.
- Remind each worker it is not alone in the codebase and must not revert other agents' edits.

Use prompts in this shape:

```text
Role: <role name>
Scope: <files/modules/concerns>

Task:
<assigned task>

Constraints:
- You are part of a larger Codex team.
- Do not revert edits made by other teammates.
- Stay within your scope unless you have to coordinate a handoff.
- If you edit files, list them in your final response.
```

## Reporting

After spawning, present:
- Team name
- Teammate list
- Role ownership
- Which agent is doing what
- When you plan to wait for the first checkpoint

## Coordination

- Use `send_input` to redirect or refine work without restarting the whole team.
- Use `wait_agent` when a checkpoint is needed.
- Synthesize the final result yourself unless a dedicated synthesis teammate is clearly warranted.
