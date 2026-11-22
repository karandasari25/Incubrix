from fastapi.testclient import TestClient

from app.main import app
from app.connectors.loader import ConnectorLoader


client = TestClient(app)

CONNECTORS = ("discourse", "lemmy", "ghost", "devto", "webhook", "assisted")


def payload(key: str, method: str):
    base = {
        "rendition": {
            "title": "Phase 3 title",
            "body": "Phase 3 body",
            "canonical_link": "https://example.com/post",
            "media": [],
            "tags": ["test"],
            "is_promotional": False,
            "ai_generated": False,
        },
        "destination": {
            "name": f"Mock {key}",
            "url": f"http://mock-platforms:8080/{key}",
            "surface": "post",
            "category": "general",
            "language": "en",
            "frequency_cap": "weekly",
            "self_promo_allowed": True,
            "link_policy": "allowed",
            "disclosure_required": False,
        },
        "connection": {
            "instance_url": f"http://mock-platforms:8080/{key}",
            "auth": {},
            "webhook_url": "http://mock-platforms:8080/webhook/inbox",
            "webhook_secret": "test-secret",
        },
    }
    if method == "publish":
        base["idempotency_key"] = f"{key}-phase3-key"
    if method in {"get_status", "delete"}:
        base = {
            "platform_post_id": f"{key}-post-1",
            "connection": base["connection"],
        }
    return base


def call(key: str, method: str):
    return client.post(
        f"/connector/v1/{key}/{method}",
        json=payload(key, method),
        headers={"Idempotency-Key": f"{key}-contract-test"},
    )


def test_all_phase3_manifests_load():
    loader = ConnectorLoader()
    for key in CONNECTORS:
        manifest = loader.load(key)
        assert manifest["key"] == key
        assert set(("key", "version", "tier", "auth", "surfaces", "rate_limits",
                    "capabilities", "error_map", "instance_param")) == set(manifest)


def test_all_core_connectors_support_validate_publish_status_delete():
    for key in CONNECTORS:
        validate = call(key, "validate")
        assert validate.status_code == 200, (key, validate.text)
        assert set(validate.json()) == {"ok", "violations"}

        publish = call(key, "publish")
        assert publish.status_code == 200, (key, publish.text)
        assert set(("platform_post_id", "live_url", "status")) == set(publish.json())

        status = call(key, "get_status")
        assert status.status_code == 200
        assert set(status.json()) == {"status", "live_url"}

        delete = call(key, "delete")
        assert delete.status_code == 200
        assert set(delete.json()) == {"deleted"}


def test_assisted_connector_builds_pack():
    response = call("assisted", "build_assist_pack")
    assert response.status_code == 200
    body = response.json()
    assert set(("files", "caption", "deep_link", "checklist")) == set(body)
