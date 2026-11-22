from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


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


def test_publish_returns_202_and_reuses_same_job():
    headers = {"Idempotency-Key": "phase1-test-key"}
    first = client.post(
        "/api/v1/publish",
        headers=headers,
        json={"destinations": ["destination-1"]},
    )
    second = client.post(
        "/api/v1/publish",
        headers=headers,
        json={"destinations": ["destination-2"]},
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]
    assert second.json()["replayed"] is True


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
