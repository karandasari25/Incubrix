from datetime import datetime, timezone
from typing import Any, Callable


class RetryPolicy:
    def __init__(self, base_seconds: int = 1, max_seconds: int = 60) -> None:
        self.base_seconds = base_seconds
        self.max_seconds = max_seconds

    def next_action(
        self,
        status: int,
        retry_after: str | None = None,
        reset_time: str | None = None,
        attempt: int = 1,
    ) -> dict[str, Any]:
        if status == 429:
            delay = self._parse_reset(retry_after, reset_time)
            return {"retry": True, "delay_seconds": delay, "code": "PLATFORM_RATE_LIMIT"}
        if status == 503:
            if attempt >= 5:
                return {"retry": False, "delay_seconds": 0,
                        "code": "PLATFORM_UNAVAILABLE"}
        if status in {408, 500, 502, 503, 504}:
            delay = min(self.base_seconds * (2 ** max(attempt - 1, 0)),
                        self.max_seconds)
            return {"retry": True, "delay_seconds": delay,
                    "code": "PLATFORM_UNAVAILABLE"}
        return {"retry": False, "delay_seconds": 0,
                "code": "PLATFORM_CONTENT_REJECTED"}

    def _parse_reset(self, retry_after: str | None, reset_time: str | None) -> int:
        if retry_after:
            try:
                return max(0, int(retry_after))
            except ValueError:
                pass
        if reset_time:
            try:
                reset = datetime.fromisoformat(reset_time.replace("Z", "+00:00"))
                if reset.tzinfo is None:
                    reset = reset.replace(tzinfo=timezone.utc)
                return max(0, int((reset - datetime.now(timezone.utc)).total_seconds()))
            except ValueError:
                pass
        return self.base_seconds


def reconcile_idempotent_publish(
    idempotency_key: str,
    marker: str,
    stored_platform_post_id: str | None,
    stored_marker: str | None,
    live_post_search: Callable[[str], str | None],
) -> dict[str, Any]:
    """Prefer stored identity; otherwise search by embedded marker."""
    if stored_platform_post_id and stored_marker == marker:
        return {
            "reconciled": True,
            "platform_post_id": stored_platform_post_id,
            "duplicate_created": False,
            "safe_to_publish": False,
            "warning": "Retry reconciled using the stored platform_post_id",
        }
    found = live_post_search(marker)
    if found:
        return {
            "reconciled": True,
            "platform_post_id": found,
            "duplicate_created": False,
            "safe_to_publish": False,
            "warning": "Retry reconciled using a marker found on the platform",
        }
    return {
        "reconciled": False,
        "platform_post_id": None,
        "duplicate_created": False,
        "safe_to_publish": True,
        "warning": "No existing marker found; publish may proceed once",
    }
