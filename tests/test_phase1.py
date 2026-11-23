import json
import logging
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.logging import current_correlation_id, current_job_id, IncuBrixJsonFormatter


engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


Base.metadata.create_all(bind=engine)
app.dependency_overrides[get_db] = override_db

from app.models import Destination

with TestingSessionLocal() as session:
    for name in ["destination-1", "destination-A", "destination-B", "discourse"]:
        session.add(
            Destination(
                id=name,
                name=name,
                url=f"https://example.com/{name}",
                platform_key="discourse",
                surface="topic",
                connector_key="discourse",
                frequency_cap="weekly",
                self_promo_allowed=True,
                link_policy="allowed",
                disclosure_required=False,
                level="L3",
            )
        )
    session.commit()

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root_describes_running_service():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "IncuBrix"
    assert response.json()["docs"] == "/docs"


def test_ready_in_simulation_mode():
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["simulation_mode"] is True


def test_publish_requires_idempotency_key():
    response = client.post("/api/v1/publish", json={"destinations": []})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_publish_short_idempotency_key_rejected():
    response = client.post(
        "/api/v1/publish",
        headers={"Idempotency-Key": "short"},
        json={"destinations": []},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_INVALID"


def test_publish_returns_202_and_reuses_same_job():
    headers = {"Idempotency-Key": "phase1-test-key-valid"}
    first = client.post(
        "/api/v1/publish",
        headers=headers,
        json={"destinations": ["destination-1"]},
    )
    second = client.post(
        "/api/v1/publish",
        headers=headers,
        json={"destinations": ["destination-1"]},
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]
    assert second.json()["replayed"] is True


def test_publish_reused_idempotency_key_with_different_body_returns_409():
    headers = {"Idempotency-Key": "phase1-diff-body-key"}
    first = client.post(
        "/api/v1/publish",
        headers=headers,
        json={"destinations": ["destination-A"]},
    )
    assert first.status_code == 202
    second = client.post(
        "/api/v1/publish",
        headers=headers,
        json={"destinations": ["destination-B"]},
    )
    assert second.status_code == 409
    body = second.json()
    assert body["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert body["error"]["retryable"] is False


def test_validation_error_returns_request_invalid_structure():
    response = client.post(
        "/api/v1/publish",
        headers={"Idempotency-Key": "phase1-invalid-payload"},
        json={"destinations": 12345},
    )
    assert response.status_code == 400
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "REQUEST_INVALID"
    assert body["error"]["retryable"] is False
    assert "details" in body["error"]


def test_unhandled_exception_returns_internal_error_without_traceback():
    no_raise_client = TestClient(app, raise_server_exceptions=False)

    @app.get("/api/v1/test-fault", include_in_schema=False)
    def fault_endpoint():
        raise RuntimeError("Secret internal database connection string leaked!")

    response = no_raise_client.get("/api/v1/test-fault")
    assert response.status_code == 500
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["retryable"] is False
    assert "Secret internal database connection string leaked!" not in json.dumps(body)


def test_job_status_shape():
    response = client.post(
        "/api/v1/publish",
        headers={"Idempotency-Key": "job-status-key"},
        json={"destinations": ["destination-1"]},
    )
    job_id = response.json()["job_id"]
    status = client.get(f"/api/v1/jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] in {"queued", "running", "succeeded", "failed"}
    assert 0 <= body["progress"] <= 100
    assert "result_links" in body


def test_correlation_id_context_and_json_logging():
    formatter = IncuBrixJsonFormatter()
    secret_val = "secret-" + "token-" + "value"
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg=f"Processing job with Authorization: Bearer {secret_val}",
        args=(),
        exc_info=None,
    )
    t_corr = current_correlation_id.set("corr-12345")
    t_job = current_job_id.set("job-67890")
    try:
        formatted = json.loads(formatter.format(record))
        assert formatted["correlation_id"] == "corr-12345"
        assert formatted["job_id"] == "job-67890"
        assert secret_val not in formatted["message"]
        assert "[REDACTED]" in formatted["message"]
    finally:
        current_correlation_id.reset(t_corr)
        current_job_id.reset(t_job)
