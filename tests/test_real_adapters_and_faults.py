from datetime import datetime, timezone, timedelta
from typing import Any
from uuid import uuid4
import httpx
import pytest
from starlette.testclient import TestClient

from app.connectors.devto import DevToConnector
from app.connectors.discourse import DiscourseConnector
from app.connectors.ghost import GhostConnector
from app.connectors.lemmy import LemmyConnector
from app.connectors.webhook import WebhookConnector
from app.connectors.errors import ConnectorError
from app.database import SessionLocal
from app.mock_platforms import app as mock_app, posts as mock_posts
from app.models import AlertTicket, Destination, Job, Publication
from app.pipeline import run_publish_pipeline
from app.certification import CertificationHarness
from app.recertification import run_recertification_scheduler
from app.worker import run_scheduled_publications_tick, publish_pipeline_task


@pytest.fixture
def mock_transport():
    tc = TestClient(mock_app)
    def handler(request: httpx.Request) -> httpx.Response:
        content = request.read()
        resp = tc.request(
            method=request.method,
            url=str(request.url),
            headers=dict(request.headers),
            content=content,
        )
        return httpx.Response(
            status_code=resp.status_code,
            headers=dict(resp.headers),
            content=resp.content,
        )
    return httpx.MockTransport(handler)


# ========================================================
# 1. Mock Platform Fault Injection Tests
# ========================================================
def test_mock_platform_429_fault(mock_transport):
    client = httpx.Client(transport=mock_transport, base_url="http://testserver")
    resp = client.post("/discourse/t", json={"title": "Test", "raw": "Body"}, headers={"X-Mock-Fault": "429"})
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "30"
    assert resp.json()["error"] == "rate_limit_exceeded"


def test_mock_platform_401_fault(mock_transport):
    client = httpx.Client(transport=mock_transport, base_url="http://testserver")
    resp = client.post("/discourse/t", json={"title": "Test"}, headers={"X-Mock-Fault": "401"})
    assert resp.status_code == 401
    assert resp.json()["error"] == "unauthorized"


def test_mock_platform_422_fault(mock_transport):
    client = httpx.Client(transport=mock_transport, base_url="http://testserver")
    resp = client.post("/discourse/t", json={"title": "Test"}, headers={"X-Mock-Fault": "422"})
    assert resp.status_code == 422
    assert resp.json()["error"] == "unprocessable_entity"


def test_mock_platform_500_fault(mock_transport):
    client = httpx.Client(transport=mock_transport, base_url="http://testserver")
    resp = client.post("/discourse/t", json={"title": "Test"}, headers={"X-Mock-Fault": "500"})
    assert resp.status_code == 500
    assert resp.json()["error"] == "internal_error"


def test_mock_platform_timeout_after_create_reconciliation(mock_transport):
    client = httpx.Client(transport=mock_transport, base_url="http://testserver")
    marker = f"recon-marker-{uuid4()}"
    resp = client.post(
        "/discourse/posts.json",
        json={"title": "Timeout Test", "raw": f"<!-- incubrix_marker:{marker} -->\nContent"},
        headers={"X-Mock-Fault": "timeout_after_create"},
    )
    assert resp.status_code == 504

    # Search for marker on platform: post was indeed created!
    search_resp = client.get(f"/discourse/search.json?q={marker}")
    assert search_resp.status_code == 200
    matched = search_resp.json().get("posts", [])
    assert len(matched) >= 1
    assert "Timeout Test" in matched[0]["title"]


def test_mock_platform_quota_fault(mock_transport):
    client = httpx.Client(transport=mock_transport, base_url="http://testserver")
    resp = client.post("/discourse/t", json={"title": "Test"}, headers={"X-Mock-Fault": "quota"})
    assert resp.status_code == 429
    assert resp.json()["error"] == "quota_exhausted"


def test_mock_platform_rename_field_fault(mock_transport):
    client = httpx.Client(transport=mock_transport, base_url="http://testserver")
    resp = client.post("/discourse/t", json={"title": "Test"}, headers={"X-Mock-Fault": "rename_field"})
    assert resp.status_code == 200
    data = resp.json()
    assert "platform_post_id" not in data
    assert "legacy_identifier" in data


# ========================================================
# 2. Real HTTPX Adapters through MockTransport
# ========================================================
def test_real_httpx_discourse_adapter(mock_transport):
    connector = DiscourseConnector(transport=mock_transport)
    connection = {"instance_url": "http://testserver/discourse", "api_key": "disc-key", "api_username": "user1"}
    destination = {"url": "http://testserver/discourse", "connector_key": "discourse"}
    rendition = {"title": "Real Discourse Post", "body": "Real body content"}

    # Publish
    pub = connector.publish(rendition, destination, connection, f"disc-key-{uuid4()}")
    assert pub["status"] == "published"
    assert "platform_post_id" in pub
    pid = pub["platform_post_id"]

    # Status
    st = connector.get_status(pid, connection)
    assert st["status"] == "published"

    # Delete
    del_res = connector.delete(pid, connection)
    assert del_res["deleted"] is True

    # Post should now be not_found
    st_deleted = connector.get_status(pid, connection)
    assert st_deleted["status"] == "not_found"


def test_real_httpx_lemmy_adapter(mock_transport):
    connector = LemmyConnector(transport=mock_transport)
    connection = {"instance_url": "http://testserver/lemmy", "jwt": "mock-jwt-token"}
    destination = {"url": "http://testserver/lemmy", "connector_key": "lemmy"}
    rendition = {"title": "Real Lemmy Post", "body": "Lemmy body"}

    # Publish
    pub = connector.publish(rendition, destination, connection, f"lemmy-key-{uuid4()}")
    assert pub["status"] == "published"
    assert "platform_post_id" in pub
    pid = pub["platform_post_id"]

    # Status
    st = connector.get_status(pid, connection)
    assert st["status"] == "published"

    # Delete
    del_res = connector.delete(pid, connection)
    assert del_res["deleted"] is True


def test_real_httpx_ghost_adapter(mock_transport):
    connector = GhostConnector(transport=mock_transport)
    # Admin API key: 24 hex char ID : 64 hex char secret
    key_id = "63489e27c8a14d003b578c2e"
    secret = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"
    connection = {"instance_url": "http://testserver/ghost", "admin_api_key": f"{key_id}:{secret}"}
    destination = {"url": "http://testserver/ghost", "connector_key": "ghost"}
    rendition = {"title": "Real Ghost Post", "body": "Ghost body paragraph"}

    # Publish
    pub = connector.publish(rendition, destination, connection, f"ghost-key-{uuid4()}")
    assert pub["status"] == "published"
    assert "platform_post_id" in pub
    pid = pub["platform_post_id"]

    # Status
    st = connector.get_status(pid, connection)
    assert st["status"] == "published"

    # Delete
    del_res = connector.delete(pid, connection)
    assert del_res["deleted"] is True


def test_real_httpx_devto_adapter(mock_transport):
    connector = DevToConnector(transport=mock_transport)
    connection = {"instance_url": "http://testserver/devto", "api_key": "devto-key"}
    destination = {"url": "http://testserver/devto", "connector_key": "devto"}
    rendition = {"title": "Real DevTo Post", "body": "DevTo markdown body"}

    # Publish
    pub = connector.publish(rendition, destination, connection, f"devto-key-{uuid4()}")
    assert pub["status"] == "published"
    assert "platform_post_id" in pub
    pid = pub["platform_post_id"]

    # Status
    st = connector.get_status(pid, connection)
    assert st["status"] == "published"

    # Delete (unpublish semantics)
    del_res = connector.delete(pid, connection)
    assert del_res["deleted"] is False
    assert del_res["unpublished"] is True


def test_real_httpx_webhook_adapter(mock_transport):
    connector = WebhookConnector(transport=mock_transport)
    connection = {"target_url": "http://testserver/webhook/inbox", "webhook_secret": "wh-secret"}
    destination = {"url": "http://testserver/webhook/inbox", "connector_key": "webhook"}
    rendition = {"title": "Webhook Title", "body": "Webhook payload"}

    # Publish
    pub = connector.publish(rendition, destination, connection, f"wh-key-{uuid4()}")
    assert pub["status"] == "published"
    assert "platform_post_id" in pub


# ========================================================
# 3. Pipeline: 429 Wait and 5 Consecutive 503s Stop
# ========================================================
def test_pipeline_429_wait_and_retry(monkeypatch):
    class FlakyRateLimitConnector:
        def __init__(self):
            self.attempts = 0

        def validate(self, rendition, dest, conn):
            return {"ok": True, "violations": []}

        def publish(self, rendition, dest, conn, key):
            self.attempts += 1
            if self.attempts == 1:
                raise ConnectorError(
                    code="PLATFORM_RATE_LIMIT",
                    message="Rate limit exceeded",
                    retryable=True,
                    status_code=429,
                    details={"retry_after": 25},
                )
            return {"platform_post_id": "rl-post-1", "live_url": "http://example.com/rl-1", "status": "published"}

    from app.connectors.registry import get_registry
    registry = get_registry()
    flaky = FlakyRateLimitConnector()
    monkeypatch.setattr(registry, "get_connector", lambda key: flaky)

    with SessionLocal() as db:
        dest_id = f"flaky-rl-dest-{uuid4()}"
        dest = Destination(
            id=dest_id,
            name="Flaky RL Dest",
            url="http://example.com",
            platform_key="discourse",
            surface="topic",
            connector_key="discourse",
            frequency_cap="monthly",
            self_promo_allowed=True,
            link_policy="allowed",
            disclosure_required=False,
            automation_allowed=True,
            level="L3",
        )
        db.merge(dest)
        job = Job(
            idempotency_key=f"pipe-rl-test-key-{uuid4()}",
            status="queued",
            payload={"destinations": [dest_id], "title": "RL Test", "body": "Content"},
        )
        db.add(job)
        db.commit()

        slept = []
        finished_job = run_publish_pipeline(job.id, db, sleep_fn=lambda s: slept.append(s))
        assert finished_job.status == "succeeded"
        assert len(slept) == 1
        assert slept[0] == 25
        assert any("Rate limited (429)" in str(w) for w in finished_job.payload.get("warnings", []))


def test_pipeline_stop_after_5_consecutive_503s(monkeypatch):
    class FiveOhThreeConnector:
        def __init__(self):
            self.attempts = 0

        def validate(self, rendition, dest, conn):
            return {"ok": True, "violations": []}

        def publish(self, rendition, dest, conn, key):
            self.attempts += 1
            raise ConnectorError(
                code="PLATFORM_UNAVAILABLE",
                message="Service Unavailable 503",
                retryable=True,
                status_code=503,
            )

    from app.connectors.registry import get_registry
    registry = get_registry()
    connector_503 = FiveOhThreeConnector()
    monkeypatch.setattr(registry, "get_connector", lambda key: connector_503)

    with SessionLocal() as db:
        dest_id = f"five-oh-three-dest-{uuid4()}"
        dest = Destination(
            id=dest_id,
            name="503 Dest",
            url="http://example.com",
            platform_key="discourse",
            surface="topic",
            connector_key="discourse",
            frequency_cap="monthly",
            self_promo_allowed=True,
            link_policy="allowed",
            disclosure_required=False,
            automation_allowed=True,
            level="L3",
        )
        db.merge(dest)
        job = Job(
            idempotency_key=f"pipe-503-test-key-{uuid4()}",
            status="queued",
            payload={"destinations": [dest_id], "title": "503 Test", "body": "Content"},
        )
        db.add(job)
        db.commit()

        slept = []
        finished_job = run_publish_pipeline(job.id, db, sleep_fn=lambda s: slept.append(s))
        assert finished_job.status == "failed"
        assert connector_503.attempts == 5
        assert any("Stopped retrying after 5 consecutive 503" in str(w) for w in finished_job.payload.get("warnings", []))


# ========================================================
# 4. Celery Worker Task & Scheduler Tick
# ========================================================
def test_worker_and_scheduler_tick():
    with SessionLocal() as db:
        dest_id = f"worker-test-dest-{uuid4()}"
        dest = Destination(
            id=dest_id,
            name="Worker Dest",
            url="http://example.com",
            platform_key="discourse",
            surface="topic",
            connector_key="discourse",
            frequency_cap="monthly",
            self_promo_allowed=True,
            link_policy="allowed",
            disclosure_required=False,
            automation_allowed=True,
            level="L3",
        )
        db.merge(dest)
        job = Job(
            idempotency_key=f"worker-task-test-key-{uuid4()}",
            status="queued",
            payload={"destinations": [dest_id], "title": "Worker Task", "body": "Body content"},
        )
        db.add(job)
        db.commit()

        # Run publish pipeline task directly through worker logic
        res = publish_pipeline_task(job.id)
        assert res["status"] == "succeeded"

        # Now test scheduled tick with a due publication
        now = datetime.now(timezone.utc)
        past_due = now - timedelta(hours=1)
        sched_pub = Publication(
            job_id=job.id,
            destination_id=dest_id,
            status="scheduled",
            scheduled_for=past_due,
        )
        db.add(sched_pub)
        db.commit()

        tick_res = run_scheduled_publications_tick(db)
        assert tick_res["due_count"] >= 1
        assert sched_pub.id in tick_res["executed"]


# ========================================================
# 5. Certification & Recertification Scheduler Demotion
# ========================================================
def test_certification_verified_deletion(mock_transport, monkeypatch):
    connector = DiscourseConnector(transport=mock_transport)
    from app.connectors.registry import get_registry
    registry = get_registry()
    monkeypatch.setitem(registry._instances, "discourse", connector)

    harness = CertificationHarness(run_type="mock")
    destination = {
        "id": f"cert-del-dest-{uuid4()}",
        "name": "Cert Discourse",
        "connector_key": "discourse",
        "url": "http://testserver/discourse",
        "surface": "topic",
        "level": "L3",
    }
    rendition = {"title": "Cert Post", "body": "Content"}
    connection = {"instance_url": "http://testserver/discourse"}

    result = harness.run(destination, rendition, connection)
    assert result["passed"] is True
    assert result["delete_verified"] is True
    assert result["level"] == "L3"


def test_recertification_scheduler_automatic_demotion(monkeypatch):
    with SessionLocal() as db:
        old_time = datetime.now(timezone.utc) - timedelta(days=45)
        dest_id = f"failing-recert-dest-{uuid4()}"
        dest_obj = Destination(
            id=dest_id,
            name="Failing Recert Dest",
            url="http://testserver/discourse",
            platform_key="discourse",
            surface="topic",
            connector_key="discourse",
            level="L3",
            last_certified_at=old_time,
            status="active",
            excluded=False,
        )
        failing_dest = db.merge(dest_obj)
        db.commit()

        # Force failure by overriding connector
        class DemotingConnector:
            def validate(self, *args):
                return {"ok": False, "violations": [{"code": "DEST_SPEC_VIOLATION", "message": "Failed spec"}]}
            def publish(self, *args):
                return {}

        from app.connectors.registry import get_registry
        monkeypatch.setitem(get_registry()._instances, "discourse", DemotingConnector())

        sched_res = run_recertification_scheduler(db, interval_days=30, run_type="mock")
        assert sched_res["demoted"] >= 1

        db.refresh(failing_dest)
        assert failing_dest.level == "L0"
        assert failing_dest.status == "demoted"
        assert failing_dest.excluded is True

        # Check alert ticket was created
        alert = db.query(AlertTicket).filter(AlertTicket.destination_id == dest_id).first()
        assert alert is not None
        assert alert.type == "destination_demoted"
