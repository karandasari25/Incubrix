from datetime import datetime, timedelta, timezone
from typing import Any


def _cap_window_hours(frequency: str) -> int:
    return {"hourly": 1, "daily": 24, "weekly": 168, "monthly": 720}.get(frequency, 0)


def evaluate_post_rules(
    content: dict[str, Any],
    destination: dict[str, Any],
    post_history: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pure, fail-closed posting rules; no database or platform access."""
    required = ("frequency_cap", "self_promo_allowed", "link_policy",
                "disclosure_required")
    missing = [field for field in required if field not in destination
               or destination[field] is None]
    if missing:
        return {
            "action": "blocked",
            "decision": "blocked",
            "reasons": ["AMBIGUOUS_RULE"] + [f"MISSING:{field}" for field in missing],
        }

    reasons = []
    scheduled_for: str | None = None
    frequency = destination["frequency_cap"]
    if not isinstance(frequency, str) or not frequency:
        reasons.append("AMBIGUOUS_RULE:MISSING_FREQUENCY_CAP")
    elif frequency in {"hourly", "daily", "weekly", "monthly"}:
        hours = _cap_window_hours(frequency)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        for item in post_history:
            posted_at = item.get("posted_at")
            try:
                timestamp = datetime.fromisoformat(str(posted_at).replace("Z", "+00:00"))
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                reasons.append("AMBIGUOUS_RULE:INVALID_POST_HISTORY")
                continue
            if timestamp >= cutoff:
                reasons.append("FREQUENCY_CAP")
                # Schedule for the end of the cap window (when the cap expires)
                scheduled_for = (timestamp + timedelta(hours=hours)).isoformat()
                break
    else:
        reasons.append("AMBIGUOUS_RULE:UNKNOWN_FREQUENCY_CAP")

    if not isinstance(destination["self_promo_allowed"], bool):
        reasons.append("AMBIGUOUS_RULE:INVALID_SELF_PROMO_POLICY")
    elif content.get("is_promotional") and not destination["self_promo_allowed"]:
        reasons.append("SELF_PROMOTION_NOT_ALLOWED")

    link_policy = destination["link_policy"]
    canonical_link = content.get("canonical_link")
    if link_policy not in {"allowed", "forbidden", "destination_only"}:
        reasons.append("AMBIGUOUS_RULE:UNKNOWN_LINK_POLICY")
    elif link_policy == "forbidden" and canonical_link:
        reasons.append("LINK_POLICY_VIOLATION")
    elif link_policy == "destination_only":
        destination_url = str(destination.get("url") or "").rstrip("/")
        if canonical_link and destination_url and not str(canonical_link).startswith(destination_url):
            reasons.append("LINK_POLICY_VIOLATION")

    if not isinstance(destination["disclosure_required"], bool):
        reasons.append("AMBIGUOUS_RULE:INVALID_DISCLOSURE_POLICY")
    elif content.get("ai_generated") and destination["disclosure_required"]:
        disclosure_marker = "ai-generated" in str(content.get("body", "")).lower()
        if not disclosure_marker:
            reasons.append("AI_DISCLOSURE_REQUIRED")

    unique_reasons = list(dict.fromkeys(reasons))
    if not unique_reasons:
        return {"action": "allowed", "decision": "allowed", "reasons": []}

    # Frequency cap is reschedulable; all other blocks are hard blocks
    if unique_reasons == ["FREQUENCY_CAP"] and scheduled_for:
        return {
            "action": "rescheduled",
            "decision": "blocked",
            "reasons": unique_reasons,
            "scheduled_for": scheduled_for,
        }
    return {"action": "blocked", "decision": "blocked", "reasons": unique_reasons}
