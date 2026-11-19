# Implementation plan — Shift Handoff Log

## Summary

A single-process FastAPI service stores shift handoff notes in SQLite and exposes create, list/filter, and markdown briefing export on localhost. Teammates record end-of-shift state; the next person reads a short briefing. The client is HTTP (curl or a later stretch UI). Persistence is one SQLite file at `data/handoffs.db`.

```text
Client → FastAPI → SQLite (data/handoffs.db)
```

## Plan items

- Document endpoints and validation rules for create, list, and export (REQ-HANDOFF-CREATE-1, REQ-HANDOFF-CREATE-2, REQ-HANDOFF-LIST-1, REQ-HANDOFF-EXPORT-1).
- Persist a handoff with a stable id, author, UTC timestamp, severity, and bounded summary (REQ-HANDOFF-CREATE-1).
- Reject missing fields and invalid severity without writing a partial row (REQ-HANDOFF-CREATE-2, AC-HANDOFF-CREATE-2, AC-HANDOFF-CREATE-3).
- List newest-first with a documented limit and optional severity and time filters; invalid times return 400 (REQ-HANDOFF-LIST-1, AC-HANDOFF-LIST-1, AC-HANDOFF-LIST-2, AC-HANDOFF-LIST-3).
- Export a markdown briefing for a time window, including an empty briefing when the window has no rows (REQ-HANDOFF-EXPORT-1, AC-HANDOFF-EXPORT-1, AC-HANDOFF-EXPORT-2).
- Verify each acceptance criterion with pytest against the HTTP API.

## Traceability

| Plan item | REQ |
|-----------|-----|
| Store handoff | REQ-HANDOFF-CREATE-1 |
| Validate input | REQ-HANDOFF-CREATE-2 |
| Query handoffs | REQ-HANDOFF-LIST-1 |
| Briefing export | REQ-HANDOFF-EXPORT-1 |

## Backlog order

1. Task 0 — Foundation (specs, EVAL, skeleton) on `main`
2. Task 1 — Create (`handoff/task1-create`)
3. Task 2 — List (`handoff/task2-list`)
4. Task 3 — Export (`handoff/task3-export`)
5. Task 4 — UI stretch (`handoff/task4-ui`) if time remains

## Branch policy

Feature work uses `handoff/task{N}-{slug}` from latest `main`. One task, one branch, one pull request. `main` receives Task 0 docs and stubs only.
