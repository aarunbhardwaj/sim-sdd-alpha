# List and filter handoffs

## Status

approved

## Intent

The next teammate lists recent handoffs, newest first, and can narrow the list by severity or by a time window before reading a briefing.

## Requirements

- REQ-HANDOFF-LIST-1 Query stored handoffs newest-first with an optional time window and optional severity filter.

## Acceptance criteria

- AC-HANDOFF-LIST-1 The default list returns recent entries up to a documented limit, newest first.
- AC-HANDOFF-LIST-2 Filtering by severity returns only matching rows.
- AC-HANDOFF-LIST-3 Invalid time parameters return a clear client error and do not respond with HTTP 500.

## Contract

`GET /handoffs`

Query parameters, all optional:

- `limit` — integer from 1 to 100. Default 20.
- `severity` — `info`, `warning`, or `critical`.
- `since` — inclusive ISO-8601 timestamp.
- `until` — inclusive ISO-8601 timestamp.

Results are ordered by `created_at` descending, then `id` descending. A bad timestamp, an inverted window (`since` after `until`), or an unknown severity returns HTTP 400.

## Out of scope

Pagination cursors, full-text search, and briefing export.

## Open questions

None.

## Amendments

2026-11-19 — Initial approved contract for the hackathon sprint.
