"""SQLite access for handoff records."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from handoff.models import Handoff, HandoffCreate

DEFAULT_DB = Path("data/handoffs.db")


def connect(db_path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS handoffs (
            id TEXT PRIMARY KEY,
            author_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            severity TEXT NOT NULL,
            summary TEXT NOT NULL
        )
        """
    )
    conn.commit()


def insert_handoff(conn: sqlite3.Connection, payload: HandoffCreate) -> Handoff:
    record = Handoff(
        id=str(uuid.uuid4()),
        author_id=payload.author_id,
        created_at=datetime.now(UTC),
        severity=payload.severity,
        summary=payload.summary,
    )
    conn.execute(
        """
        INSERT INTO handoffs (id, author_id, created_at, severity, summary)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            record.id,
            record.author_id,
            record.created_at.isoformat(),
            record.severity,
            record.summary,
        ),
    )
    conn.commit()
    return record


def count_handoffs(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) AS n FROM handoffs").fetchone()
    return int(row["n"])
