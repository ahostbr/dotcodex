# Claude Skills Sync 2026-04-03

Imported into `C:\Users\Ryan\.codex\skills`:

- `conversation-lookup`
- `taste`
- `mockup`
- `release-litesuite`
- `video-download`
- `video-lens`

Why these were imported:

- They add distinct capability not already covered well enough by the active Codex skill set.
- They do not depend on Claude-only orchestration primitives in a way that blocks normal Codex usage.
- Their path assumptions could be adapted cleanly.

Left Claude-only on purpose:

- `ao`: overlaps with `ao-ask`, `ao-answer`, `ao-browse`, `ao-search`
- `arch_old`: historical reference only
- `dream_`: memory-maintenance workflow, not a general Codex skill import
- `gen-image-or-video`: tightly coupled to request_user_input-first flow and local generation scripts
- `library`: useful, but its catalog/index workflow needs a dedicated Codex-native refresh pass before import
- `max-parallel`: superseded by `max-subagents-parallel`
- `plan-w-quizmaster-sonnet`: wrapper around existing quizmaster planning
- `playwright-e2e-screenshots`: mostly covered by `webapp-testing`
- `scout`: proactive sub-agent behavior pattern, not a normal end-user skill
- `self-improve`: meta-training workflow for Claude-side skills
- `spawnteam`: overlaps with existing agent spawning/orchestration patterns
- `stitch-pipeline`: depends on Stitch MCP/tooling not currently exposed here
- `train`: Claude-side training loop with hardcoded `.claude` paths
- `vault`: overlaps with split vault skills already in Codex
- `watch`: depends on Claude background watcher/task notification semantics not available here

Needs future reconsideration if Codex-native support is added:

- `library`
- `stitch-pipeline`
- `watch`
- `gen-image-or-video`
