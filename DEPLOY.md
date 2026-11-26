# Deploy

## Deployment target

Local machine only. One process listens on `http://127.0.0.1:8000`. SQLite data lives in `data/handoffs.db`, created on first request. No hosted environment and no credentials.

## Workflow

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn handoff.main:app --host 127.0.0.1 --port 8000
```

`scripts/run.sh` starts the same server with reload when the script is executable.

## Verification

These are the checks to run after the process is up. They are the local smoke path for this sprint.

- `GET /health` returns `{"status":"ok"}`.
- `POST /handoffs` with `author_id`, `severity` (`info`, `warning`, or `critical`), and `summary` returns 201 and an `id`.
- `GET /handoffs` returns newest first. `GET /handoffs?severity=warning` keeps only that severity.
- `GET /handoffs/briefing?since=<iso>&until=<iso>` returns `text/markdown`.
- `.venv/bin/pytest -q` passes before the process is considered ready.

## Rollback

Stop the uvicorn process. To drop stored notes, delete `data/handoffs.db` and start again. There is no remote release to roll back.

## Linked acceptance criteria

- AC-HANDOFF-CREATE-1 — create persists an id
- AC-HANDOFF-LIST-1 — default recent list
- AC-HANDOFF-LIST-2 — severity filter
- AC-HANDOFF-EXPORT-1 — briefing for a valid window

Alpha ran pytest before considering the service ready.
