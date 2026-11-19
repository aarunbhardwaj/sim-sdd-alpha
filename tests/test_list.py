from pathlib import Path

from fastapi.testclient import TestClient

from handoff.main import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(tmp_path / "handoffs.db"))


def _create(client: TestClient, summary: str, severity: str = "info") -> str:
    response = client.post(
        "/handoffs",
        json={"author_id": "alex", "severity": severity, "summary": summary},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_ac_handoff_list_1_default_list_is_newest_first(tmp_path: Path) -> None:
    client = _client(tmp_path)
    first = _create(client, "first")
    second = _create(client, "second")
    third = _create(client, "third")
    response = client.get("/handoffs")
    assert response.status_code == 200
    ids = [row["id"] for row in response.json()]
    assert ids == [third, second, first]
    limited = client.get("/handoffs", params={"limit": 2})
    assert [row["id"] for row in limited.json()] == [third, second]


def test_ac_handoff_list_2_severity_filter(tmp_path: Path) -> None:
    client = _client(tmp_path)
    _create(client, "quiet", "info")
    warning = _create(client, "watch the deploy", "warning")
    response = client.get("/handoffs", params={"severity": "warning"})
    assert response.status_code == 200
    rows = response.json()
    assert [row["id"] for row in rows] == [warning]
    assert rows[0]["severity"] == "warning"


def test_ac_handoff_list_3_invalid_time_is_400(tmp_path: Path) -> None:
    client = _client(tmp_path)
    bad = client.get("/handoffs", params={"since": "yesterday"})
    assert bad.status_code == 400
    inverted = client.get(
        "/handoffs",
        params={"since": "2026-11-19T12:00:00Z", "until": "2026-11-19T01:00:00Z"},
    )
    assert inverted.status_code == 400
