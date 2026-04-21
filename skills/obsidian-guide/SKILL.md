---
name: obsidian-guide
description: "Use when the user asks questions about how their Obsidian vault works, its structure, conventions, or available commands. Triggers on 'how does my vault work', 'vault help', 'what folders are in my vault', 'how should I organize notes'. Not for performing vault actions — only for guidance about the vault system."
allowed-tools: mcp__litememory__vault_search, mcp__litememory__vault_list, mcp__litememory__vault_tags, mcp__litememory__vault_recent, mcp__litememory__vault_read
---

# Obsidian Vault Guide

You have access to Ryan's Obsidian vault — his second brain. Use the LiteMemory MCP tools to read, search, and write notes.

## Vault Structure

The vault at `C:\Users\Ryan\Documents\Obsidian Vault` is organized as:

| Folder | Purpose |
|--------|---------|
| **Chronicles/** | Origin stories, milestones, the journey narrative |
| **Daily/** | Daily journal notes (YYYY-MM-DD.md format) |
| **Ideas/** | Brainstorms, concepts, "what if" notes |
| **Projects/** | Project notes, specs, architecture decisions |
| **Research/** | Technical research, videos, articles, tutorials |
| **Sessions/** | Auto-captured Claude Code session summaries |
| **System/** | Vault config, internal documentation |
| **Templates/** | Note templates (daily, project, research, idea, session) |

## Key Commands

- `/note [title]` — Create or update a note
- `/daily [entry]` — Open or add to today's daily note
- `/vault-search [query]` — Search the vault by content, tags, or links
- `/vault-import [path]` — Import an external file into the vault

## Conventions

### Frontmatter
Every note should have YAML frontmatter:
```yaml
---
type: project|daily|research|idea|session|chronicle
title: "Note Title"
created: YYYY-MM-DDTHH:mm:ss
updated: YYYY-MM-DDTHH:mm:ss
tags: [tag1, tag2]
---
```

### Linking
- Use `[[wikilinks]]` to connect notes (e.g. `[[Kuroryuu]]`, `[[The Full Story]]`)
- Use `#tags` for categorization
- Cross-reference projects with `[[Project Name]]`

### Templates
Available in Templates/ folder:
- `daily.md` — Daily journal note
- `project.md` — Project documentation
- `research.md` — Research/learning note
- `idea.md` — Brainstorm/concept note
- `session.md` — Session summary

## When to Use the Vault

- **Before starting work**: Search vault for existing context on the topic
- **During work**: Log important decisions to the daily note
- **After work**: Session summaries are auto-captured by the Stop hook
- **When researching**: Save findings to Research/ with proper tags
- **When brainstorming**: Capture ideas in Ideas/ before they're lost
