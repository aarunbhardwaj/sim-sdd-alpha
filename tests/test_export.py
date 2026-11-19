from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from handoff.main import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "handoffs.db"))


def test_ac_handoff_export_1_window_includes_rows_newest_first(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post(
        "/handoffs",
        json={"author_id": "alex", "severity": "info", "summary": "older note"},
    )
    client.post(
        "/handoffs",
        json={"author_id": "sam", "severity": "critical", "summary": "newer note"},
    )
    now = datetime.now(UTC)
    response = client.get(
        "/handoffs/briefing",
        params={
            "since": (now - timedelta(minutes=5)).isoformat(),
            "until": (now + timedelta(minutes=5)).isoformat(),
        },
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    body = response.text
    assert body.startswith("# Shift briefing")
    newer = body.index("newer note")
    older = body.index("older note")
    assert newer < older
    assert "**critical**" in body
    assert "**info**" in body


def test_ac_handoff_export_2_empty_window_is_not_an_error(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post(
        "/handoffs",
        json={"author_id": "alex", "severity": "info", "summary": "today"},
    )
    response = client.get(
        "/handoffs/briefing",
        params={"since": "2000-01-01T00:00:00Z", "until": "2000-01-02T00:00:00Z"},
    )
    assert response.status_code == 200
    body = response.text
    assert "# Shift briefing" in body
    assert "Period:" in body
    assert "today" not in body
    assert body.count("- **") == 0
