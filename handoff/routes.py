"""HTTP routes."""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response

from handoff.models import Handoff, HandoffCreate
from handoff.store import connect, init_db, insert_handoff

router = APIRouter()


def get_conn(request: Request):
    path: Path = request.app.state.db_path
    conn = connect(path)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/handoffs", status_code=201)
def create_handoff(
    payload: HandoffCreate,
    conn: Annotated[object, Depends(get_conn)],
) -> Handoff:
    return insert_handoff(conn, payload)


@router.get("/handoffs", status_code=501)
def list_handoffs() -> None:
    raise HTTPException(status_code=501, detail="not implemented")


@router.get("/handoffs/briefing", status_code=501)
def export_briefing() -> Response:
    raise HTTPException(status_code=501, detail="not implemented")
