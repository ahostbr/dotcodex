---
name: plan-w-quizmaster-sonnet
description: Autonomous planning — Opus runs the Quizmaster interrogation while a Sonnet sub-agent answers as the developer, grounded in codebase context. Produces a plan without user involvement. Triggers on 'plan-w-quizmaster-sonnet', 'sonic plan', 'autonomous plan', 'auto-plan', 'sonnet plan'.
---

# Autonomous Quizmaster Planning (Sonnet as Developer)

Run the full Quizmaster interrogation autonomously: **Opus asks the questions, a Sonnet sub-agent answers them** grounded in the actual codebase, project context, and memory. The user reviews the finished plan.

## How It Works

```
User: "sonic plan: rebuild the auth system"
  |
  v
Opus (Quizmaster) ──asks──> Sonnet Agent (Developer)
  ^                              |
  |──────────answers─────────────|
  |  (grounded in codebase,      |
  |   docs, project memory)      |
  |                              |
  [repeats until coverage met]
  |
  v
Plan generated --> User reviews
```

## Variables

| Variable | Source | Description |
|----------|--------|-------------|
| TOPIC | $1 | What to plan (user's request) |
| VARIANT | default: v7 | Quizmaster prompt variant |
| PLAN_OUTPUT | Docs/Plans/ | Output directory |

## STEP 1: Variant Selection

Ask the user which quizmaster variant to use via `request_user_input`:

```
Question: "Which quizmaster variant for this autonomous planning session?"
Options:
  - "v7 (Recommended)" — Master + sub-plan decomposition, workstream discovery, phased DAG
  - "v6" — Adaptive quizmaster with fact dependencies, unified inversion
  - "v5" — Self-evaluating meta planner
  - "small" — Lightweight, fewer questions
Default: v7
```

## STEP 2: Load the Quizmaster Prompt

Read the selected variant from `~/.codex/skills/plan-w-quizmaster/`:

| Variant | File |
|---------|------|
| v7 | `ULTIMATE_QUIZZER_PROMPT_v7.md` |
| v6 | `ULTIMATE_QUIZZER_PROMPT_v6.md` |
| v5 | `ULTIMATE_QUIZZER_PROMPT_v5.md` |
| small | `ULTIMATE_QUIZZER_PROMPT_small.md` |

Internalize the methodology. You ARE the Quizmaster now.

## STEP 3: Spawn the Sonnet Developer Agent

Spawn a **named** Sonnet agent using the Agent tool:

```
Agent(
  name: "sonnet-developer",
  model: "sonnet",
  subagent_type: "general-purpose",
  prompt: <see below>
)
```

### Sonnet Developer Prompt Template

```
You are a senior developer being interviewed about a planning task. Your job is to answer
planning questions as accurately and thoroughly as possible, grounded in what you can
actually find in the codebase.

## Your Role
- You answer questions about requirements, architecture, constraints, and implementation
- You explore the codebase to ground your answers in reality (files, patterns, dependencies)
- When you don't know something or can't find evidence, say so honestly
- When multiple approaches exist, present them with tradeoffs
- You represent the developer's perspective — practical, grounded, implementation-aware

## The Task Being Planned
{TOPIC}

## Rules
1. **Read before answering.** Use Glob, Grep, and Read to find relevant code before responding.
2. **Be specific.** Name files, functions, line numbers. Don't be vague.
3. **Flag uncertainty.** If you're missing evidence, say "I couldn't verify X" or "I need evidence for Y before treating it as settled."
4. **Think about feasibility.** If a question implies something hard, say why it's hard.
5. **Stay in character.** You're the developer being quizzed, not the planner.

## Project Context
- Working directory: {CWD}
- Check package.json, tsconfig.json, requirements.txt etc. for stack info
- Check existing docs, architecture files, and project structure
- Read CLAUDE.md and memory files for project context

I'll be asked questions by the Quizmaster. I should answer each one thoughtfully,
grounding my responses in the actual codebase.

Waiting for the first question.
```

Replace `{TOPIC}` with the user's planning topic and `{CWD}` with the current working directory.

## STEP 4: Run the Interrogation Loop

Now execute the Quizmaster methodology by asking questions to the Sonnet agent via `SendMessage`.

### The Loop

```
1. Run Reconnaissance silently (codebase scan, project DNA, domain weighting)
2. Send Workstream Discovery question to sonnet-developer
3. Read response, track facts
4. Send the Prior Question ("Why does this need to exist?")
5. Read response, track facts
6. Begin domain questioning — blockers first
   - For each round:
     a. Select 2-4 highest-value questions based on blockers and fact dependencies
     b. SendMessage to sonnet-developer with the questions
     c. Read response, update fact tracking
     d. Check stopping criterion (3 consecutive low-impact answers)
7. Run Inversion Pass when enough signal gathered
   - Send predictions to sonnet-developer, ask which are wrong
   - Follow up on wrong predictions
8. Run Final Inversion on remaining low-confidence items
9. Generate the plan
```

### Important Guidelines

- **Track facts internally** using the v7 fact tracking format (Domain, Confidence, Workstream, Resolves, Blocks)
- **Present a brief state summary** to yourself between rounds (not to the user)
- **Anti-pattern alerts** — monitor and surface to the agent if triggered
- **Max ~8-12 rounds** of questioning. Don't go forever.
- **Sonnet can explore the codebase** — give it time to read files and respond substantively
- **If Sonnet says "I don't know"** — that's a valid answer. Record it as LOW confidence and move on.

### User Progress Updates

Every 3-4 rounds, output a brief progress update to the user (they're watching):

```
**Autonomous Planning Progress**
- Round: X/~12
- Facts established: N (H: X, M: Y, L: Z)
- Key decisions resolved: [list]
- Still investigating: [list]
```

Keep it short. The user is reviewing, not participating.

## STEP 5: Generate the Plan

Follow the v7 plan format from the loaded Quizmaster prompt:

- **Master plan** (`master.md`) — orchestration, overview, acceptance criteria, DAG
- **Sub-plans** (`sub-<name>.md`) — executable tasks per workstream

Save to `Docs/Plans/<kebab-case-name>/`.

Include the Execution Workflow section (worktree, TDD, implement, debug, verify, review, finish).

## STEP 6: Present to User

```
**Autonomous Plan Complete**

Topic: <description>
Variant: <variant used>
Rounds: <N>
Facts: <total> (HIGH: X, MED: Y, LOW: Z)
Workstreams: <N>

**Files:**
- `Docs/Plans/<folder>/master.md`
- `Docs/Plans/<folder>/sub-<name>.md`
- ...

**Key Decisions Made:**
- <bullet list of 3-5 most important facts/decisions>

**Remaining Uncertainties:**
- <anything the Sonnet agent couldn't answer or was LOW confidence>

**Review the plan and let me know what to adjust.**
```

## STEP 7: User Review

The user reviews the plan. They may:
- **Approve** — proceed to execution
- **Adjust** — modify specific sections
- **Re-run** — ask you to re-interrogate specific areas (you can SendMessage to the still-running sonnet-developer)
- **Scrap** — start over with different parameters

The Sonnet agent stays alive for follow-up questions until the user is satisfied.

---

## Self-Validation

1. A plan folder exists in `Docs/Plans/`
2. Contains `master.md` + at least one `sub-*.md`
3. Plan follows v7 format with fact provenance
4. User has been presented the summary for review
