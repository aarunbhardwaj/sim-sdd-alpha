# Demo

## Purpose

Show a local Shift Handoff Log: create a warning, list recent notes and a severity filter, then export a markdown briefing for a short window. Traceability is the merged create pull request and its Spec trailers.

## Approved acceptance criteria to demonstrate

- AC-HANDOFF-CREATE-1 — valid payload persisted with id
- AC-HANDOFF-LIST-1 — default recent list
- AC-HANDOFF-LIST-2 — severity filter
- AC-HANDOFF-EXPORT-1 — window export content

## Demo notes

Start the API with the command in DEPLOY.md. Use curl against `http://127.0.0.1:8000`. Create one `warning` handoff, list without a filter, list with `severity=warning`, then request `/handoffs/briefing` for a window that covers the new row. Open the merged create pull request and show the Spec trailers on the implementation commit.

Alpha confirmed the create flow against the spec.
