"""HTTP routes."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from handoff.models import Handoff, HandoffCreate
from handoff.store import connect, init_db, insert_handoff, query_handoffs

router = APIRouter()
SEVERITIES = {"info", "warning", "critical"}
DEFAULT_LIMIT = 20


def get_conn(request: Request):
    path: Path = request.app.state.db_path
    conn = connect(path)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


def parse_instant(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid time parameter") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/handoffs", status_code=201)
def create_handoff(
    payload: HandoffCreate,
    conn: Annotated[sqlite3.Connection, Depends(get_conn)],
) -> Handoff:
    return insert_handoff(conn, payload)


@router.get("/handoffs")
def list_handoffs(
    conn: Annotated[sqlite3.Connection, Depends(get_conn)],
    limit: int = DEFAULT_LIMIT,
    severity: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[Handoff]:
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="invalid limit")
    if severity is not None and severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail="invalid severity")
    since_at = parse_instant(since) if since is not None else None
    until_at = parse_instant(until) if until is not None else None
    if since_at is not None and until_at is not None and since_at > until_at:
        raise HTTPException(status_code=400, detail="invalid time window")
    return query_handoffs(
        conn,
        limit=limit,
        severity=severity,
        since=since_at,
        until=until_at,
    )


@router.get("/handoffs/briefing", status_code=501)
def export_briefing() -> None:
    raise HTTPException(status_code=501, detail="not implemented")
