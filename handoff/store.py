"""SQLite access. Query methods are stubs until their tasks."""

from __future__ import annotations

import sqlite3
from pathlib import Path

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
