# Export shift briefing

## Status

approved

## Intent

Produce a markdown briefing for the next shift: a title, the requested period, and a bullet list of severity plus summary for every handoff in that window.

## Requirements

- REQ-HANDOFF-EXPORT-1 Export a readable briefing of handoffs inside a caller-supplied time window.

## Acceptance criteria

- AC-HANDOFF-EXPORT-1 A valid window includes every handoff in that window, in readable newest-first order.
- AC-HANDOFF-EXPORT-2 An empty window returns an empty briefing structure, not an error.

## Contract

`GET /handoffs/briefing`

Query parameters:

- `since` — required ISO-8601 timestamp
- `until` — required ISO-8601 timestamp

Success returns HTTP 200 with `Content-Type: text/markdown` and a body shaped as:

```markdown
# Shift briefing

Period: <since> to <until>

- **<severity>** <summary> (<author_id>, <created_at>)
```

When no rows match, the same title and period are returned and the bullet list is omitted. Invalid timestamps return HTTP 400.

## Out of scope

JSON export, email delivery, and the stretch UI.

## Open questions

None.

## Amendments

2026-11-19 — Initial approved contract for the hackathon sprint.
