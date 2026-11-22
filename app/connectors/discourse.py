from hashlib import sha256
from typing import Any

from app.connectors.base import ConnectorBase


class DiscourseConnector(ConnectorBase):
    """A clean, simulation-first Discourse protocol implementation."""

    def __init__(self) -> None:
        self._posts: dict[str, dict[str, Any]] = {}

    def validate(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        violations = []
        title = rendition.get("title") or ""
        body = rendition.get("body") or ""
        if len(title) > 255:
            violations.append(
                {"code": "DEST_SPEC_VIOLATION", "field": "title", "message": "Title exceeds 255 characters"}
            )
        if len(body) > 60000:
            violations.append(
                {"code": "DEST_SPEC_VIOLATION", "field": "body", "message": "Body exceeds 60000 characters"}
            )
        if rendition.get("media"):
            violations.append(
                {"code": "DEST_SPEC_VIOLATION", "field": "media", "message": "Discourse topic surface does not accept direct media"}
            )
        return {"ok": not violations, "violations": violations}

    def publish(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        marker = sha256(idempotency_key.encode("utf-8")).hexdigest()[:16]
        existing_id = next(
            (
                post_id
                for post_id, post in self._posts.items()
                if post["marker"] == marker
            ),
            None,
        )
        if existing_id:
            post = self._posts[existing_id]
        else:
            existing_id = f"discourse-post-{len(self._posts) + 1}"
            instance_url = connection.get("instance_url", "").rstrip("/")
            post = {
                "marker": marker,
                "status": "published",
                "live_url": f"{instance_url}/t/{existing_id}",
            }
            self._posts[existing_id] = post
        return {
            "platform_post_id": existing_id,
            "live_url": post["live_url"],
            "status": post["status"],
        }

    def get_status(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        post = self._posts.get(platform_post_id)
        if post:
            return {"status": post["status"], "live_url": post["live_url"]}
        return {
            "status": "not_found",
            "live_url": f"{connection.get('instance_url', '').rstrip('/')}/t/{platform_post_id}",
        }

    def delete(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        return {"deleted": self._posts.pop(platform_post_id, None) is not None}

    def fetch_metrics(self, platform_post_id: str, connection: dict,
                      since: str) -> dict[str, Any]:
        seed = sum(ord(character) for character in platform_post_id)
        return {
            "views": seed * 3,
            "likes": seed,
            "comments": seed // 4,
            "shares": seed // 10,
            "saves": seed // 8,
            "watch_time_s": seed * 2,
            "clicks": seed // 6,
        }
