from app.certification import (
    CertificationHarness,
    validate_publish_response,
    validate_status_response,
)
from app.models import CertificationEvidence, Destination


def test_publish_response_shape_validation():
    assert validate_publish_response({
        "platform_post_id": "post-1",
        "live_url": "https://example.com/post-1",
        "status": "published",
    }) == []

    violations = validate_publish_response({
        "postId": "renamed-field",
        "liveUrl": "https://example.com/post-1",
    })
    assert "platform_post_id" in violations
    assert "live_url" in violations
    assert "status" in violations


def test_status_response_shape_validation():
    assert validate_status_response({
        "status": "published",
        "live_url": "https://example.com/post-1",
    }) == []
    assert validate_status_response({"post_status": "published"})


def test_mock_certification_passes_and_carries_run_type():
    harness = CertificationHarness(run_type="mock")
    evidence = harness.run(
        destination={"name": "Mock forum", "url": "https://example.com/forum",
                     "connector_key": "discourse", "level": "L3"},
        rendition={"title": "Certification test", "body": "Delete this post",
                   "canonical_link": "https://example.com/article",
                   "media": [], "tags": [], "is_promotional": False,
                   "ai_generated": False},
        connection={"instance_url": "http://mock-platforms:8080/discourse",
                    "auth": {}},
    )
    assert evidence["run_type"] == "mock"
    assert evidence["passed"] is True
    assert evidence["delete_verified"] is True
    assert evidence["level"] == "L3"


def test_renamed_field_demotes_destination_and_creates_alert():
    harness = CertificationHarness(run_type="mock")
    evidence = harness.run(
        destination={"name": "Changed API", "url": "https://example.com",
                     "connector_key": "discourse", "level": "L4"},
        rendition={"title": "Test", "body": "Test", "canonical_link": None,
                   "media": [], "tags": [], "is_promotional": False,
                   "ai_generated": False},
        connection={"instance_url": "http://mock-platforms:8080/discourse",
                    "auth": {}},
        publish_override={"postId": "renamed", "liveUrl": "https://example.com/renamed"},
    )
    assert evidence["passed"] is False
    assert evidence["level"] == "L0"
    assert evidence["alert"] is not None
    assert evidence["alert"]["type"] == "destination_demoted"


def test_live_run_type_is_never_inferred_from_mock():
    evidence = CertificationHarness(run_type="mock").run(
        destination={"name": "Mock", "url": "https://example.com",
                     "connector_key": "discourse", "level": "L2"},
        rendition={"title": "Test", "body": "Test", "canonical_link": None,
                   "media": [], "tags": [], "is_promotional": False,
                   "ai_generated": False},
        connection={"instance_url": "http://mock-platforms:8080/discourse",
                    "auth": {}},
    )
    assert evidence["run_type"] == "mock"
    assert evidence["run_type"] != "live"


def test_destination_and_evidence_records_exist():
    assert Destination.__tablename__ == "destinations"
    assert CertificationEvidence.__tablename__ == "certification_evidence"
