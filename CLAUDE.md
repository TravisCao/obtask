# obtask — AI Agent Context

This file provides context for AI coding agents (Claude Code, Cursor, Copilot, etc.) working on this codebase.

## What This Is

`obtask` is a CLI tool for managing Obsidian vault task files. Each task is a Markdown file with YAML frontmatter in `_system/tasks/`. The tool provides listing, filtering, detail view, comments, and lifecycle management (done/cancel with archiving).

## Architecture

```
src/obtask/
├── __init__.py    # Version only
├── core.py        # Task dataclass, parsing, querying, file mutations
├── display.py     # Rich terminal output (table, panel, JSON)
└── cli.py         # Typer CLI commands (6 commands)
```

**Data flow:** CLI args → `core.py` (load/filter/sort/resolve/mutate) → `display.py` (render)

Three source files. No config files, no database, no network calls. Pure filesystem operations on Markdown files.

## Key Design Decisions

1. **No YAML re-serialization for writes.** Status updates and comments use regex-based string manipulation on the raw file content, preserving original formatting, comments, and field order. `python-frontmatter` is only used for reading.

2. **Atomic writes.** All file mutations write to a temp file first, then `os.replace()`. This prevents corruption on crash.

3. **Terminal state contract.** `status` command is metadata-only (never moves files). `done` and `cancel` are the only commands that archive (move files). This is intentional — don't merge them.

4. **Active-only resolve for mutations.** Mutating commands (`comment`, `status`, `done`, `cancel`) only search active tasks, never archived ones. The `show` and `list` commands can search archives.

5. **Strict vs non-strict fuzzy matching.** Read-only commands use non-strict (more aggressive fuzzy). Mutating commands use strict (only exact stem + unambiguous substring) to prevent accidental edits.

## Task File Schema

```yaml
---
type: task
status: todo | in-progress | blocked | done | cancelled
due: YYYY-MM-DD | ""  | TBD   # all treated as "no due date" except valid dates
created: YYYY-MM-DD
completed_date: YYYY-MM-DD | ""  # set by `done`, cleared by `cancel`
priority: p1 | p2 | p3 | p4     # optional, some tasks omit this
tags: [research, teaching, ...]
project: string                  # optional
blocked_reason: string           # only when blocked
---
```

## Development

```bash
# Install in development (editable)
uv tool install -e .

# Reinstall after changes
uv tool install . --force --reinstall

# Run directly without installing
uv run obtask list
```

## Testing Changes

No test suite yet. Verify manually:

```bash
obtask list                    # Should show active tasks
obtask list --json | python -m json.tool  # Valid JSON
obtask show <slug>             # Task detail panel
obtask status <slug> done      # Should be blocked with hint
```

## Common Modifications

### Adding a new filter to `list`
1. Add parameter to `list_tasks()` in `cli.py`
2. Add filter logic to `filter_tasks()` in `core.py`
3. No display changes needed — filtered tasks pass through existing render

### Adding a new command
1. Add business logic function in `core.py`
2. Add `@app.command()` function in `cli.py`
3. Use `_handle_resolve()` for query resolution
4. Use `active_only=True` for any mutating command

### Adding a new frontmatter field
1. Add field to `Task` dataclass in `core.py`
2. Parse it in `load_task()`
3. Display it in `render_task_detail()` in `display.py`
4. If it should appear in JSON: add to `render_json()`
