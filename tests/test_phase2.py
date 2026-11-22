from fastapi.testclient import TestClient

from app.main import app
from app.connectors.loader import ConnectorLoader


client = TestClient(app)


def discourse_payload(method: str, extra: dict | None = None):
    payload = {
        "rendition": {
            "title": "A useful IncuBrix discussion",
            "body": "Test post body for the local simulation.",
            "canonical_link": "https://example.com/article",
            "media": [],
            "tags": ["incubrix"],
            "is_promotional": False,
            "ai_generated": False,
        },
        "destination": {
            "name": "Mock Discourse",
            "url": "http://mock-platforms:8080/discourse",
            "surface": "topic",
            "category": "community",
            "language": "en",
            "frequency_cap": "weekly",
            "self_promo_allowed": True,
            "link_policy": "allowed",
            "disclosure_required": False,
        },
        "connection": {
            "instance_url": "http://mock-platforms:8080/discourse",
            "auth": {"bot_token": ""},
        },
    }
    if method == "publish":
        payload["idempotency_key"] = "discourse-test-idempotency-key"
    if method == "get_status":
        payload = {
            "platform_post_id": "discourse-post-1",
            "connection": payload["connection"],
        }
    if method == "delete":
        payload = {
            "platform_post_id": "discourse-post-1",
            "connection": payload["connection"],
        }
    if extra:
        payload.update(extra)
    return payload


def call(method: str, payload: dict):
    return client.post(
        f"/connector/v1/discourse/{method}",
        json=payload,
        headers={"Idempotency-Key": "connector-contract-test"},
    )


def test_manifest_has_exact_required_fields():
    loader = ConnectorLoader()
    manifest = loader.load("discourse")
    assert set(("key", "version", "tier", "auth", "surfaces", "rate_limits",
                "capabilities", "error_map", "instance_param")) == set(manifest)
    assert manifest["key"] == "discourse"
    assert manifest["tier"] in {"native", "protocol", "bridge", "feed", "assisted"}
    assert manifest["auth"] in {"oauth2", "api_key", "bot_token", "none"}


def test_validate_contract():
    response = call("validate", discourse_payload("validate"))
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.json()["violations"] == []


def test_publish_contract_and_idempotency_marker():
    payload = discourse_payload("publish")
    first = call("publish", payload)
    second = call("publish", payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["platform_post_id"] == second.json()["platform_post_id"]
    assert first.json()["live_url"].startswith("http://")
    assert first.json()["status"] in {"published", "pending", "succeeded"}


def test_get_status_contract():
    call("publish", discourse_payload("publish"))
    response = call("get_status", discourse_payload("get_status"))
    assert response.status_code == 200
    assert set(response.json()) == {"status", "live_url"}


def test_delete_contract():
    call("publish", discourse_payload("publish"))
    response = call("delete", discourse_payload("delete"))
    assert response.status_code == 200
    assert response.json() == {"deleted": True}
