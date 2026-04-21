---
name: vault-import
description: "Use when the user wants to import an external file into the Obsidian vault. Triggers on '/vault-import', 'import this file to vault', 'add this document to my vault', 'bring this into my notes'. Requires a source file path."
allowed-tools: Read, mcp__litememory__vault_write, mcp__litememory__vault_search
---

Import external markdown files or content into the vault.

## Steps

1. **Read the source file** from `$ARGUMENTS` using the Read tool
   - The first argument is the file path to import

2. **Determine destination**:
   - If `--to` flag provided, use that vault path
   - Otherwise infer from content:
     - Looks like a transcript → `Research/`
     - Looks like a story/chronicle → `Chronicles/`
     - Looks like project docs → `Projects/`
     - Default → `Research/`

3. **Generate frontmatter**:
   ```yaml
   type: <inferred>
   title: "<extracted from first heading or filename>"
   created: <current ISO datetime>
   imported: <current ISO datetime>
   source: "<original file path>"
   tags: [imported, <inferred>]
   ```

4. **Write to vault** using vault_write with the content and frontmatter

5. **Confirm** with the imported path and word count
