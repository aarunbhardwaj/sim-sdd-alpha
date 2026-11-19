from pathlib import Path

from fastapi.testclient import TestClient

from handoff.main import create_app
from handoff.store import connect, count_handoffs, init_db


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "handoffs.db"))


def test_ac_handoff_create_1_valid_payload_returns_id(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/handoffs",
        json={"author_id": "alex", "severity": "warning", "summary": "Deploy pending"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["author_id"] == "alex"
    assert body["severity"] == "warning"
    assert body["summary"] == "Deploy pending"
    assert body["created_at"]


def test_ac_handoff_create_2_missing_fields_are_rejected(tmp_path: Path) -> None:
    db = tmp_path / "handoffs.db"
    client = TestClient(create_app(db))
    response = client.post("/handoffs", json={"author_id": "alex"})
    assert response.status_code == 400
    conn = connect(db)
    init_db(conn)
    assert count_handoffs(conn) == 0
    conn.close()


def test_ac_handoff_create_3_invalid_severity_is_rejected(tmp_path: Path) -> None:
    db = tmp_path / "handoffs.db"
    client = TestClient(create_app(db))
    response = client.post(
        "/handoffs",
        json={"author_id": "alex", "severity": "urgent", "summary": "Nope"},
    )
    assert response.status_code == 400
    conn = connect(db)
    init_db(conn)
    assert count_handoffs(conn) == 0
    conn.close()
