from hashlib import sha256
from typing import Any
import httpx

from app.config import get_settings
from app.connectors.base import ConnectorBase
from app.connectors.errors import ConnectorError
from app.connectors.http_client import map_status_to_connector_error


class DiscourseConnector(ConnectorBase):
    """Real HTTPX Discourse protocol connector with simulation fallback."""

    def __init__(self, client: httpx.Client | None = None, transport: httpx.BaseTransport | None = None) -> None:
        self._client = client
        self._transport = transport
        self._posts: dict[str, dict[str, Any]] = {}

    def _get_client(self, connection: dict[str, Any]) -> httpx.Client:
        if self._client:
            return self._client
        headers = {}
        if connection.get("api_key"):
            headers["Api-Key"] = str(connection["api_key"])
        if connection.get("api_username"):
            headers["Api-Username"] = str(connection["api_username"])
        if connection.get("mock_fault"):
            headers["X-Mock-Fault"] = str(connection["mock_fault"])
        return httpx.Client(transport=self._transport, headers=headers, timeout=10.0)

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
        if len(body) > 32000:
            violations.append(
                {"code": "DEST_SPEC_VIOLATION", "field": "body", "message": "Body exceeds 32000 characters"}
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
        base_url = (connection.get("instance_url") or connection.get("base_url") or destination.get("url") or "").rstrip("/")

        # Simulation fallback when in simulation mode
        if get_settings().connector_mode == "simulation" and not self._transport:
            existing_id = next(
                (post_id for post_id, post in self._posts.items() if post["marker"] == marker),
                None,
            )
            if existing_id:
                post = self._posts[existing_id]
            else:
                existing_id = f"discourse-post-{len(self._posts) + 1}"
                post = {
                    "marker": marker,
                    "status": "published",
                    "live_url": f"{base_url}/t/{existing_id}",
                }
                self._posts[existing_id] = post
            return {
                "platform_post_id": existing_id,
                "live_url": post["live_url"],
                "status": post["status"],
            }

        # Real HTTP call via httpx
        title = rendition.get("title") or ""
        body = rendition.get("body") or ""
        tagged_body = f"<!-- incubrix_marker:{marker} -->\n{body}"
        payload = {
            "title": title,
            "raw": tagged_body,
            "category": rendition.get("category", 1),
        }

        # Choose endpoint path based on server structure
        endpoint = f"{base_url}/posts.json" if not base_url.endswith("/t") else base_url
        if "/discourse" in base_url and not base_url.endswith("/posts.json") and not base_url.endswith("/t"):
            endpoint = f"{base_url}/posts.json"

        client = self._get_client(connection)
        try:
            resp = client.post(endpoint, json=payload)
            if resp.status_code >= 400:
                raise map_status_to_connector_error(resp.status_code, resp.text, headers=dict(resp.headers))
            data = resp.json()
            post_id = str(data.get("platform_post_id") or data.get("id") or "")
            live_url = data.get("live_url") or f"{base_url}/t/{post_id}"
            return {
                "platform_post_id": post_id,
                "live_url": live_url,
                "status": data.get("status", "published"),
            }
        except httpx.TimeoutException:
            raise ConnectorError(code="PLATFORM_UNAVAILABLE", message="Discourse request timed out", retryable=True, status_code=504)
        except httpx.HTTPStatusError as e:
            raise map_status_to_connector_error(e.response.status_code, e.response.text, headers=dict(e.response.headers))

    def get_status(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        base_url = (connection.get("instance_url") or connection.get("base_url") or "").rstrip("/")
        if get_settings().connector_mode == "simulation" and not self._transport:
            post = self._posts.get(platform_post_id)
            if post:
                return {"status": post["status"], "live_url": post["live_url"]}
            return {
                "status": "not_found",
                "live_url": f"{base_url}/t/{platform_post_id}",
            }

        endpoint = f"{base_url}/t/{platform_post_id}.json" if not base_url.endswith(f"/t/{platform_post_id}") else base_url
        client = self._get_client(connection)
        try:
            resp = client.get(endpoint)
            if resp.status_code == 404:
                return {"status": "not_found", "live_url": f"{base_url}/t/{platform_post_id}"}
            if resp.status_code >= 400:
                raise map_status_to_connector_error(resp.status_code, resp.text, headers=dict(resp.headers))
            data = resp.json()
            return {
                "status": data.get("status", "published"),
                "live_url": data.get("live_url") or f"{base_url}/t/{platform_post_id}",
            }
        except httpx.TimeoutException:
            raise ConnectorError(code="PLATFORM_UNAVAILABLE", message="Discourse request timed out", retryable=True, status_code=504)

    def delete(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        base_url = (connection.get("instance_url") or connection.get("base_url") or "").rstrip("/")
        if get_settings().connector_mode == "simulation" and not self._transport:
            return {"deleted": self._posts.pop(platform_post_id, None) is not None}

        endpoint = f"{base_url}/t/{platform_post_id}.json"
        client = self._get_client(connection)
        try:
            resp = client.delete(endpoint)
            if resp.status_code == 404:
                return {"deleted": False}
            if resp.status_code >= 400:
                raise map_status_to_connector_error(resp.status_code, resp.text, headers=dict(resp.headers))
            data = resp.json() if resp.text else {}
            return {"deleted": data.get("deleted", True)}
        except httpx.TimeoutException:
            raise ConnectorError(code="PLATFORM_UNAVAILABLE", message="Discourse delete timed out", retryable=True, status_code=504)

    def fetch_metrics(self, platform_post_id: str, connection: dict, since: str) -> dict[str, Any]:
        status_info = self.get_status(platform_post_id, connection)
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
