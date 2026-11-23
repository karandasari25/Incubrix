import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app.certification import CertificationHarness
from app.catalogue import import_catalogue_csv
from app.connectors.registry import get_registry
from app.errors import APIError
from app.main import app
from app.reliability import RetryPolicy, reconcile_idempotent_publish
from app.rules import evaluate_post_rules


client = TestClient(app)


def test_hard_case_01_timeout_retry_same_key():
    headers = {"Idempotency-Key": "hard-case-key-01-timeout"}
    first = client.post(
        "/api/v1/publish",
        headers=headers,
        json={"destinations": ["discourse"], "title": "Timeout Test", "body": "Body"},
    )
    assert first.status_code == 202

    # Replay same key
    second = client.post(
        "/api/v1/publish",
        headers=headers,
        json={"destinations": ["discourse"], "title": "Timeout Test", "body": "Body"},
    )
    assert second.status_code == 202
    assert second.json()["replayed"] is True
    assert second.json()["job_id"] == first.json()["job_id"]


def test_hard_case_02_rate_limit_429_reset_header():
    policy = RetryPolicy()
    action = policy.next_action(status=429, retry_after="30")
    assert action["retry"] is True
    assert action["delay_seconds"] == 30
    assert action["code"] == "PLATFORM_RATE_LIMIT"


def test_hard_case_03_expired_token():
    connector = get_registry().get_connector("devto")
    manifest = get_registry().get_manifest("devto")
    assert manifest["error_map"].get("401") == "CONNECTION_AUTH_EXPIRED"
    error = APIError("CONNECTION_AUTH_EXPIRED", "Token expired", status_code=401, retryable=False)
    assert error.code == "CONNECTION_AUTH_EXPIRED"
    assert error.retryable is False


def test_hard_case_04_content_rejected():
    manifest = get_registry().get_manifest("discourse")
    assert manifest["error_map"].get("422") == "PLATFORM_CONTENT_REJECTED"


def test_hard_case_05_title_too_long():
    resp = client.post(
        "/connector/v1/discourse/validate",
        json={
            "rendition": {"title": "X" * 300, "body": "Normal body"},
            "destination": {},
            "connection": {},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert any(v["field"] == "title" for v in data["violations"])


def test_hard_case_06_unsupported_media():
    resp = client.post(
        "/connector/v1/discourse/validate",
        json={
            "rendition": {"title": "Valid Title", "body": "Body", "media": [{"url": "http://img.jpg"}]},
            "destination": {},
            "connection": {},
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is False
    assert any(v["field"] == "media" for v in data["violations"])


def test_hard_case_07_second_post_inside_weekly_cap():
    now = datetime.now(timezone.utc)
    history = [{"posted_at": (now - timedelta(days=1)).isoformat()}]
    dest = {
        "url": "https://example.com/forum",
        "frequency_cap": "weekly",
        "self_promo_allowed": True,
        "link_policy": "allowed",
        "disclosure_required": False,
    }
    content = {"title": "Post", "body": "Body", "canonical_link": None, "is_promotional": False, "ai_generated": False}
    result = evaluate_post_rules(content, dest, history)
    assert result["action"] == "rescheduled"
    assert result["decision"] == "blocked"
    assert "FREQUENCY_CAP" in result["reasons"]
    assert "scheduled_for" in result


def test_hard_case_08_promo_to_no_promo_destination():
    dest = {
        "url": "https://example.com/forum",
        "frequency_cap": "weekly",
        "self_promo_allowed": False,
        "link_policy": "allowed",
        "disclosure_required": False,
    }
    content = {"title": "Buy Now", "body": "Sale 50%", "canonical_link": None, "is_promotional": True, "ai_generated": False}
    result = evaluate_post_rules(content, dest, [])
    assert result["decision"] == "blocked"
    assert "SELF_PROMOTION_NOT_ALLOWED" in result["reasons"]


def test_hard_case_09_platform_field_rename_causes_demotion():
    harness = CertificationHarness(run_type="mock")
    # Simulate platform dropping live_url and returning postId instead of platform_post_id
    bad_publish = {"postId": "renamed-123", "status": "published"}
    evidence = harness.run(
        destination={"name": "Broken API", "url": "https://example.com", "connector_key": "discourse", "level": "L4"},
        rendition={"title": "Test", "body": "Body", "canonical_link": None, "media": [], "tags": [], "is_promotional": False, "ai_generated": False},
        connection={"instance_url": "http://mock-platforms:8080/discourse", "auth": {}},
        publish_override=bad_publish,
    )
    assert evidence["passed"] is False
    assert evidence["level"] == "L0"
    assert evidence["alert"]["type"] == "destination_demoted"


def test_hard_case_10_csv_duplicates_and_bad_urls(tmp_path):
    csv_file = tmp_path / "hard_test.csv"
    csv_file.write_text(
        "name,url,platform_key,surface,language\n"
        "Valid One,https://example.com/1,forum,topic,en\n"
        "Duplicate One,https://example.com/1,forum,topic,en\n"
        "Bad URL,not-a-url,forum,topic,en\n"
        "Missing Language,https://example.com/3,forum,topic,\n",
        encoding="utf-8",
    )
    report = import_catalogue_csv(csv_file)
    assert report["imported"] == 1
    assert report["duplicates"] == 1
    assert report["bad_rows"] == 2


def test_hard_case_11_partner_revokes_permission():
    manifest = get_registry().get_manifest("webhook")
    assert manifest["error_map"].get("403") == "CONNECTION_AUTH_EXPIRED"


def test_hard_case_12_non_english_community_preserved():
    dest = {
        "url": "https://communaute.fr",
        "frequency_cap": "weekly",
        "self_promo_allowed": True,
        "link_policy": "allowed",
        "disclosure_required": False,
        "language": "fr",
    }
    content = {
        "title": "Un titre français avec des accents: é, è, à",
        "body": "Texte explicatif préservé sans altération linguistique.",
        "canonical_link": None,
        "is_promotional": False,
        "ai_generated": False,
    }
    result = evaluate_post_rules(content, dest, [])
    assert result["decision"] == "allowed"
    assert result["reasons"] == []


def test_hard_case_13_destination_requires_ai_disclosure():
    dest = {
        "url": "https://example.com/forum",
        "frequency_cap": "weekly",
        "self_promo_allowed": True,
        "link_policy": "allowed",
        "disclosure_required": True,
    }
    content = {
        "title": "Generated Article",
        "body": "An article created by a synthetic automated model.",
        "canonical_link": None,
        "is_promotional": False,
        "ai_generated": True,
    }
    result = evaluate_post_rules(content, dest, [])
    assert result["decision"] == "blocked"
    assert "AI_DISCLOSURE_REQUIRED" in result["reasons"]
