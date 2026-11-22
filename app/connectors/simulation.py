from hashlib import sha256
from typing import Any

from app.connectors.base import ConnectorBase


class SimulationConnector(ConnectorBase):
    """In-memory implementation used for local/mock platform certification."""

    def __init__(self, key: str, title_max: int = 255, body_max: int = 60000) -> None:
        self.key = key
        self.title_max = title_max
        self.body_max = body_max
        self.posts: dict[str, dict[str, Any]] = {}

    def validate(self, rendition: dict, destination: dict, connection: dict) -> dict:
        violations = []
        title = rendition.get("title") or ""
        body = rendition.get("body") or ""
        if len(title) > self.title_max:
            violations.append({"code": "DEST_SPEC_VIOLATION", "field": "title",
                               "message": f"Title exceeds {self.title_max} characters"})
        if len(body) > self.body_max:
            violations.append({"code": "DEST_SPEC_VIOLATION", "field": "body",
                               "message": f"Body exceeds {self.body_max} characters"})
        if rendition.get("media") and self.key in {"lemmy", "ghost", "devto"}:
            violations.append({"code": "DEST_SPEC_VIOLATION", "field": "media",
                               "message": f"{self.key} media requires a configured upload flow"})
        return {"ok": not violations, "violations": violations}

    def publish(self, rendition: dict, destination: dict, connection: dict,
                idempotency_key: str) -> dict:
        marker = sha256(idempotency_key.encode()).hexdigest()[:16]
        existing_id = next((post_id for post_id, post in self.posts.items()
                            if post["marker"] == marker), None)
        if existing_id:
            post = self.posts[existing_id]
        else:
            existing_id = f"{self.key}-post-{len(self.posts) + 1}"
            base_url = connection.get("instance_url", destination.get("url", "")).rstrip("/")
            post = {
                "marker": marker,
                "status": "published",
                "live_url": f"{base_url}/p/{existing_id}",
            }
            self.posts[existing_id] = post
        return {"platform_post_id": existing_id, "live_url": post["live_url"],
                "status": post["status"]}

    def get_status(self, platform_post_id: str, connection: dict) -> dict:
        post = self.posts.get(platform_post_id)
        if post:
            return {"status": post["status"], "live_url": post["live_url"]}
        base_url = connection.get("instance_url", "").rstrip("/")
        return {"status": "not_found", "live_url": f"{base_url}/p/{platform_post_id}"}

    def delete(self, platform_post_id: str, connection: dict) -> dict:
        return {"deleted": self.posts.pop(platform_post_id, None) is not None}

    def fetch_metrics(
        self,
        platform_post_id: str,
        connection: dict,
        since: str,
    ) -> dict:
        if self.key not in {"discourse", "lemmy", "ghost"}:
            raise NotImplementedError(
                f"{self.key} does not advertise fetch_metrics in its manifest"
            )
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
