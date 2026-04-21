---
name: note
description: "Use when the user wants to create or update a specific named note in the Obsidian vault. Triggers on '/note', 'create a note about X', 'write a note', 'save a note', 'add to my notes on X'. Not for daily journal entries (use 'daily') or searching existing notes (use 'vault-search')."
allowed-tools: mcp__litememory__vault_write, mcp__litememory__vault_read, mcp__litememory__vault_search
---

Create or update a note in the Obsidian vault at `C:\Users\Ryan\Documents\Obsidian Vault`.

## Vault Structure

| Folder | Purpose | Frontmatter `type` |
|--------|---------|---------------------|
| **Projects/** | Project notes, specs, architecture decisions | `project` |
| **Research/** | Technical research, videos, articles, tutorials | `research` |
| **Ideas/** | Brainstorms, concepts, "what if" notes | `idea` |
| **Chronicles/** | Origin stories, milestones, journey narrative | `chronicle` |
| **Daily/** | Daily journal notes (use `/daily` instead) | `daily` |
| **Sessions/** | Auto-captured session summaries (auto-managed) | `session` |

### Known projects
LiteSpeak, LiteMemory, Kuroryuu, SOTS, Terminal OS, The Ecosystem

## Steps

1. **Parse arguments from `$ARGUMENTS`**:
   - If it contains a `/`, treat as an explicit path (e.g. `Projects/LiteMemory`)
   - If it matches or references a known project name → `Projects/<name>`
   - If it references the current working project (check cwd) → `Projects/<project>`
   - Otherwise infer folder from keywords:
     - "research", "learn", "study", "article", "video" → `Research/`
     - "idea", "brainstorm", "what if", "concept" → `Ideas/`
     - Default → `Ideas/`

2. **Check if note exists** using vault_read:
   - If exists, read it and **append** the new content under the appropriate section (or ask user if unclear)
   - If not exists, create new from template structure below

3. **Generate frontmatter** (for new notes):
   ```yaml
   ---
   type: <from folder table above>
   title: "<title>"
   created: <current ISO datetime>
   updated: <current ISO datetime>
   status: active
   tags:
     - <type>
     - <additional inferred tags>
   ---
   ```

4. **Generate body**:
   - If user provided content after the title, write it under an appropriate heading
   - If no content, use the skeleton for that note type:
     - **Projects**: `## Overview`, `## Current Status`, `## Key Decisions`, `## Links`
     - **Research**: `## Summary`, `## Notes`, `## Sources`, `## Links`
     - **Ideas**: `## Concept`, `## Details`, `## Links`
   - Use `[[wikilinks]]` to connect to related notes (e.g. `[[LiteSpeak]]`, `[[Kuroryuu]]`)

5. **Write note** using vault_write to the determined path

6. **Confirm** with the full path and a brief summary of what was written
