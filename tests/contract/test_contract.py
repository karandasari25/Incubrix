from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.connectors.loader import ConnectorLoader
from app.connectors.registry import get_registry
from app.main import app


client = TestClient(app)
REQUIRED_MANIFEST_FIELDS = {
    "key",
    "version",
    "tier",
    "auth",
    "surfaces",
    "rate_limits",
    "capabilities",
    "error_map",
    "instance_param",
}
VALID_TIERS = {"native", "protocol", "bridge", "feed", "assisted"}
VALID_AUTHS = {"oauth2", "api_key", "bot_token", "none"}
ALL_CONNECTOR_KEYS = [
    "discourse",
    "lemmy",
    "ghost",
    "devto",
    "webhook",
    "assisted",
    "mrss",
    "hashnode",
    "kit",
]


@pytest.mark.parametrize("key", ALL_CONNECTOR_KEYS)
def test_manifest_schema_conformance(key: str):
    loader = ConnectorLoader()
    manifest = loader.load(key)
    missing = REQUIRED_MANIFEST_FIELDS - set(manifest.keys())
    assert not missing, f"Manifest {key} missing required fields: {missing}"
    assert manifest["tier"] in VALID_TIERS, f"Invalid tier for {key}: {manifest['tier']}"
    assert manifest["auth"] in VALID_AUTHS, f"Invalid auth for {key}: {manifest['auth']}"
    assert isinstance(manifest["surfaces"], list) and len(manifest["surfaces"]) > 0

    surface = manifest["surfaces"][0]
    assert "key" in surface
    assert "content_types" in surface
    assert "spec" in surface
    spec = surface["spec"]
    assert "title_max_chars" in spec
    assert "body_max_chars" in spec
    assert "links_allowed" in spec

    rate_limits = manifest["rate_limits"]
    assert "per_connection" in rate_limits
    assert "requests" in rate_limits["per_connection"]
    assert "per_seconds" in rate_limits["per_connection"]

    caps = manifest["capabilities"]
    assert isinstance(caps, list)

    error_map = manifest["error_map"]
    assert isinstance(error_map, dict)
    assert error_map.get("429") == "PLATFORM_RATE_LIMIT"
    assert error_map.get("500") == "PLATFORM_UNAVAILABLE"


@pytest.mark.parametrize("key", ALL_CONNECTOR_KEYS)
def test_connector_instantiation_from_registry(key: str):
    registry = get_registry()
    connector = registry.get_connector(key)
    assert connector is not None
    manifest = registry.get_manifest(key)
    assert manifest["key"] == key


def test_validate_endpoint_contract():
    payload = {
        "rendition": {
            "title": "Contract validation test post",
            "body": "Body text for testing validation endpoint contract.",
            "canonical_link": None,
            "media": [],
            "tags": ["test"],
            "is_promotional": False,
            "ai_generated": False,
        },
        "destination": {
            "name": "Test Destination",
            "url": "http://example.com/dest",
            "surface": "topic",
        },
        "connection": {"instance_url": "http://example.com", "auth": {}},
    }
    for key in ALL_CONNECTOR_KEYS:
        resp = client.post(f"/connector/v1/{key}/validate", json=payload)
        assert resp.status_code == 200, f"Validate failed for {key}: {resp.text}"
        data = resp.json()
        assert "ok" in data
        assert isinstance(data["ok"], bool)
        assert "violations" in data
        assert isinstance(data["violations"], list)


def test_publish_and_status_contract():
    registry = get_registry()
    for key in ALL_CONNECTOR_KEYS:
        if not registry.has_capability(key, "publish"):
            continue
        pub_payload = {
            "rendition": {
                "title": f"Publish contract test for {key}",
                "body": "Test body content.",
                "canonical_link": None,
                "media": [],
                "tags": [],
                "is_promotional": False,
                "ai_generated": False,
            },
            "destination": {"name": f"Dest {key}", "url": f"http://example.com/{key}"},
            "connection": {"instance_url": f"http://example.com/{key}", "auth": {}},
            "idempotency_key": f"contract-pub-{key}-12345",
        }
        resp = client.post(f"/connector/v1/{key}/publish", json=pub_payload)
        assert resp.status_code == 200, f"Publish failed for {key}: {resp.text}"
        data = resp.json()
        assert "platform_post_id" in data
        assert "live_url" in data
        assert "status" in data

        post_id = data["platform_post_id"]

        # If get_status is supported
        if registry.has_capability(key, "status"):
            status_resp = client.post(
                f"/connector/v1/{key}/get_status",
                json={
                    "platform_post_id": post_id,
                    "connection": pub_payload["connection"],
                },
            )
            assert status_resp.status_code == 200
            status_data = status_resp.json()
            assert "status" in status_data
            assert "live_url" in status_data

        # If delete is supported
        if registry.has_capability(key, "delete"):
            del_resp = client.post(
                f"/connector/v1/{key}/delete",
                json={
                    "platform_post_id": post_id,
                    "connection": pub_payload["connection"],
                },
            )
            assert del_resp.status_code == 200
            del_data = del_resp.json()
            assert "deleted" in del_data
            assert isinstance(del_data["deleted"], bool)


def test_build_assist_pack_contract():
    payload = {
        "rendition": {
            "title": "Assisted Post Title",
            "body": "Detailed copy for manual posting.",
            "canonical_link": "https://example.com/source",
        },
        "destination": {
            "name": "Manual Community",
            "url": "https://example.com/submit",
        },
    }
    resp = client.post("/connector/v1/assisted/build_assist_pack", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert "files" in data
    assert "caption" in data
    assert "deep_link" in data
    assert "checklist" in data
    assert isinstance(data["checklist"], list)


def test_fetch_metrics_contract():
    # Discourse has metrics capability
    payload = {
        "platform_post_id": "test-post-metrics",
        "connection": {"instance_url": "http://discourse.example.com"},
        "since": "2026-01-01T00:00:00Z",
    }
    resp = client.post("/connector/v1/discourse/fetch_metrics", json=payload)
    assert resp.status_code == 200
    metrics = resp.json()
    for field in ["views", "likes", "comments", "shares", "saves", "watch_time_s", "clicks"]:
        assert field in metrics


def test_unsupported_method_returns_dest_spec_violation():
    # mrss connector does not have fetch_metrics capability
    resp = client.post(
        "/connector/v1/mrss/fetch_metrics",
        json={"platform_post_id": "p1", "connection": {}, "since": ""},
    )
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"]["code"] == "DEST_SPEC_VIOLATION"


def test_disabled_connector_kill_switch(monkeypatch):
    monkeypatch.setattr(
        get_settings(), "disabled_connectors", ["discourse", "lemmy"]
    )
    resp = client.post(
        "/connector/v1/discourse/validate",
        json={"rendition": {}, "destination": {}, "connection": {}},
    )
    assert resp.status_code == 503
    data = resp.json()
    assert data["error"]["code"] == "CONNECTOR_DISABLED"


def test_unknown_connector_returns_404():
    resp = client.post(
        "/connector/v1/nonexistent_connector/validate",
        json={"rendition": {}, "destination": {}, "connection": {}},
    )
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"]["code"] == "CONNECTOR_NOT_FOUND"
