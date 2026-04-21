---
name: vault-search
description: "Use when the user wants to find, search, or look up existing notes in the Obsidian vault. Triggers on '/vault-search', 'search my vault', 'find notes about X', 'what notes do I have on X', 'look up X in vault', or any request to query existing note content by text, tags, or backlinks."
allowed-tools: mcp__litememory__vault_search, mcp__litememory__vault_tags, mcp__litememory__vault_link, mcp__litememory__vault_read
---

Search the vault using text, tags, or link analysis.

## Steps

1. **Parse arguments from `$ARGUMENTS`**:
   - `--tag X` → use vault_tags to find notes with that tag
   - `--folder X` → restrict search to that folder
   - `--links-to X` → use vault_link to find backlinks
   - Plain text → full-text search via vault_search

2. **Execute search** using the appropriate MCP tool

3. **Display results** in a clean table or list format:
   - Path, title, relevant excerpt, tags
   - Show match context when available

4. **Offer to read**: "Want me to read any of these notes?"
