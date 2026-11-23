from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.recommendation import precision_at_10
from app.recertification import recertification_due
from app.connectors.router import get_connector


def test_precision_at_10():
    recommendations = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"]
    relevant = {"a", "c", "z"}
    assert precision_at_10(recommendations, relevant) == 0.2


def test_recertification_due_when_old_or_never_tested():
    now = datetime.now(timezone.utc)
    assert recertification_due(None, now, 30) is True
    assert recertification_due(now - timedelta(days=31), now, 30) is True
    assert recertification_due(now - timedelta(days=29), now, 30) is False


def test_three_connectors_return_exact_metrics_shape():
    expected = {"views", "likes", "comments", "shares", "saves",
                "watch_time_s", "clicks"}
    for key in ("discourse", "lemmy", "ghost"):
        result = get_connector(key).fetch_metrics(
            f"{key}-post-1",
            {"instance_url": f"http://mock-platforms:8080/{key}"},
            "2026-11-01T00:00:00Z",
        )
        assert set(result) == expected
        assert all(isinstance(value, (int, float)) for value in result.values())


def test_outstanding_catalogue_contains_150_rows():
    path = Path(__file__).resolve().parents[1] / "data" / "catalogue-150.csv"
    assert path.is_file()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 151


def test_recommendations_endpoint_returns_ranked_results():
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/recommendations",
        headers={"Idempotency-Key": "rec-endpoint-test-key"},
        json={
            "title": "Scaling AI SaaS Infrastructure",
            "body": "An in-depth guide on deploying models and handling scale.",
            "tags": ["ai", "saas", "infrastructure"],
            "language": "en",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "recommendations" in body
    assert isinstance(body["recommendations"], list)

