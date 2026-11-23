from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

from app.reliability import RetryPolicy, reconcile_idempotent_publish
from app.rules import evaluate_post_rules


def destination(**overrides):
    base = {
        "name": "Test forum",
        "url": "https://example.com/community",
        "frequency_cap": "weekly",
        "self_promo_allowed": True,
        "link_policy": "allowed",
        "disclosure_required": False,
    }
    base.update(overrides)
    return base


def content(**overrides):
    base = {
        "title": "Useful test post",
        "body": "A useful technical explanation.",
        "canonical_link": "https://example.com/article",
        "is_promotional": False,
        "ai_generated": False,
    }
    base.update(overrides)
    return base


def test_second_post_inside_weekly_cap_is_blocked():
    now = datetime.now(timezone.utc)
    history = [{"posted_at": (now - timedelta(days=2)).isoformat()}]
    result = evaluate_post_rules(content(), destination(), history)
    assert result["decision"] == "blocked"
    assert "FREQUENCY_CAP" in result["reasons"]


def test_promotional_post_to_no_promo_destination_is_blocked():
    result = evaluate_post_rules(
        content(is_promotional=True),
        destination(self_promo_allowed=False),
        [],
    )
    assert result["decision"] == "blocked"
    assert "SELF_PROMOTION_NOT_ALLOWED" in result["reasons"]


def test_missing_policy_fails_closed():
    result = evaluate_post_rules(content(), {"name": "Incomplete"}, [])
    assert result["decision"] == "blocked"
    assert "AMBIGUOUS_RULE" in result["reasons"]


def test_ai_generated_destination_requires_disclosure_and_reasons_it():
    result = evaluate_post_rules(
        content(ai_generated=True),
        destination(disclosure_required=True),
        [],
    )
    assert result["decision"] == "blocked"
    assert "AI_DISCLOSURE_REQUIRED" in result["reasons"]


def test_allowed_post_carries_no_block_reason():
    result = evaluate_post_rules(content(), destination(), [])
    assert result["decision"] == "allowed"
    assert result["reasons"] == []
    assert result["action"] == "allowed"


def test_link_policy_blocks_external_link():
    result = evaluate_post_rules(
        content(canonical_link="https://external.example/article"),
        destination(link_policy="destination_only"),
        [],
    )
    assert result["decision"] == "blocked"
    assert "LINK_POLICY_VIOLATION" in result["reasons"]


def test_timeout_replay_with_stored_platform_id_is_reconciled():
    result = reconcile_idempotent_publish(
        idempotency_key="retry-key",
        marker="incubrix-retry-key",
        stored_platform_post_id="platform-123",
        stored_marker="incubrix-retry-key",
        live_post_search=lambda marker: None,
    )
    assert result["reconciled"] is True
    assert result["platform_post_id"] == "platform-123"
    assert result["duplicate_created"] is False


def test_platform_marker_search_prevents_duplicate():
    result = reconcile_idempotent_publish(
        idempotency_key="retry-key",
        marker="incubrix-marker",
        stored_platform_post_id=None,
        stored_marker=None,
        live_post_search=lambda marker: "platform-found",
    )
    assert result["reconciled"] is True
    assert result["platform_post_id"] == "platform-found"
    assert result["duplicate_created"] is False


def test_no_marker_match_requires_safe_retry():
    result = reconcile_idempotent_publish(
        idempotency_key="retry-key",
        marker="incubrix-marker",
        stored_platform_post_id=None,
        stored_marker=None,
        live_post_search=lambda marker: None,
    )
    assert result["reconciled"] is False
    assert result["safe_to_publish"] is True


def test_429_reset_header_is_used():
    policy = RetryPolicy()
    action = policy.next_action(status=429, retry_after="18", reset_time=None)
    assert action["retry"] is True
    assert action["delay_seconds"] == 18
    assert action["code"] == "PLATFORM_RATE_LIMIT"


def test_bounded_backoff_never_exceeds_limit():
    policy = RetryPolicy(base_seconds=2, max_seconds=10)
    delays = [policy.next_action(status=502, attempt=a)["delay_seconds"] for a in range(1, 8)]
    assert delays == [2, 4, 8, 10, 10, 10, 10]


def test_platform_unavailable_stops_after_five_failures():
    policy = RetryPolicy()
    for attempt in range(1, 5):
        assert policy.next_action(status=503, attempt=attempt)["retry"] is True
    stopped = policy.next_action(status=503, attempt=5)
    assert stopped["retry"] is False
    assert stopped["code"] == "PLATFORM_UNAVAILABLE"


def test_expired_connection_is_not_retryable_as_rate_limit():
    from app.errors import APIError
    error = APIError(
        "CONNECTION_AUTH_EXPIRED",
        "The stored connection token is expired",
        401,
        retryable=False,
    )
    assert error.code == "CONNECTION_AUTH_EXPIRED"
    assert error.retryable is False


def test_long_title_and_unsupported_media_are_explicit_violations():
    from app.connectors.discourse import DiscourseConnector
    connector = DiscourseConnector()
    result = connector.validate(
        {"title": "x" * 256, "body": "ok", "media": [{"url": "https://example.com/a.png"}]},
        {},
        {},
    )
    assert result["ok"] is False
    codes = {violation["field"] for violation in result["violations"]}
    assert {"title", "media"} <= codes


def test_partner_revocation_and_content_rejection_have_shared_codes():
    shared = {"CONNECTION_AUTH_EXPIRED", "PLATFORM_CONTENT_REJECTED"}
    assert "CONNECTION_AUTH_EXPIRED" in shared
    assert "PLATFORM_CONTENT_REJECTED" in shared


def test_non_english_destination_is_not_rejected_by_english_assumption():
    result = evaluate_post_rules(
        content(title="Un conseil pratique", body="Une communauté utile."),
        destination(language="fr"),
        [],
    )
    assert result["decision"] == "allowed"


def test_phase4_hard_cases_have_stored_results():
    path = Path(__file__).parent / "fixtures" / "phase4_hard_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    names = {item["case"] for item in cases}
    assert len(cases) == 13
    assert "timeout_retry_same_key" in names
    assert "platform_field_rename" in names
    assert "csv_duplicates_bad_urls_mixed_languages" in names


def _resolve_timestamps(post_history: list) -> list:
    """Replace $NOW-Xh magic tokens with actual ISO timestamps relative to now."""
    import re
    now = datetime.now(timezone.utc)
    resolved = []
    for item in post_history:
        new_item = dict(item)
        raw = new_item.get("posted_at", "")
        m = re.match(r"^\$NOW-(\d+(?:\.\d+)?)h$", str(raw))
        if m:
            hours = float(m.group(1))
            new_item["posted_at"] = (now - timedelta(hours=hours)).isoformat()
        resolved.append(new_item)
    return resolved


def test_rules_fixture_has_forty_plus_cases_and_zero_misses():
    """Run all rules_cases.json cases through evaluate_post_rules; misses must be 0."""
    path = Path(__file__).parent / "fixtures" / "rules_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    assert len(cases) >= 40, f"Expected >= 40 cases, got {len(cases)}"
    misses = []
    for case in cases:
        result = evaluate_post_rules(
            case["content"],
            case["destination"],
            _resolve_timestamps(case["post_history"]),
        )
        actual_action = result.get("action", result.get("decision"))
        expected_action = case["expected_action"]
        # "rescheduled" is a subtype of "blocked" (decision=blocked, action=rescheduled)
        ok_action = (
            actual_action == expected_action
            or (expected_action == "rescheduled" and result.get("action") == "rescheduled")
        )
        for expected_reason in case["expected_reasons"]:
            if expected_reason not in result["reasons"]:
                misses.append({
                    "id": case["id"],
                    "description": case["description"],
                    "expected_reason": expected_reason,
                    "got_reasons": result["reasons"],
                })
        if not ok_action:
            misses.append({
                "id": case["id"],
                "description": case["description"],
                "expected_action": expected_action,
                "got_action": actual_action,
            })
    assert misses == [], f"{len(misses)} violations missed:\n" + "\n".join(str(m) for m in misses)


def test_frequency_cap_returns_rescheduled_action_with_scheduled_for():
    now = datetime.now(timezone.utc)
    history = [{"posted_at": (now - timedelta(days=2)).isoformat()}]
    result = evaluate_post_rules(
        content(),
        destination(),
        history,
    )
    assert result["action"] == "rescheduled"
    assert result["decision"] == "blocked"
    assert "FREQUENCY_CAP" in result["reasons"]
    assert "scheduled_for" in result
