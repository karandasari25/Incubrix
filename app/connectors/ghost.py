from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
import jwt
import httpx

from app.config import get_settings
from app.connectors.base import ConnectorBase
from app.connectors.errors import ConnectorError
from app.connectors.http_client import map_status_to_connector_error
from app.connectors.simulation import SimulationConnector


class GhostConnector(ConnectorBase):
    """Real HTTPX Ghost Admin API connector with simulation fallback."""

    def __init__(self, client: httpx.Client | None = None, transport: httpx.BaseTransport | None = None) -> None:
        self._client = client
        self._transport = transport
        self._sim = SimulationConnector("ghost", title_max=300, body_max=100000)

    def _generate_token(self, admin_api_key: str) -> str:
        try:
            key_id, secret = admin_api_key.split(":")
            iat = int(datetime.now(timezone.utc).timestamp())
            headers = {"alg": "HS256", "typ": "JWT", "kid": key_id}
            payload = {
                "iat": iat,
                "exp": iat + 5 * 60,
                "aud": "/admin/",
            }
            return jwt.encode(payload, bytes.fromhex(secret), algorithm="HS256", headers=headers)
        except Exception:
            return admin_api_key

    def _get_client(self, connection: dict[str, Any]) -> httpx.Client:
        if self._client:
            return self._client
        headers = {}
        api_key = connection.get("admin_api_key") or connection.get("api_key")
        if api_key:
            token = self._generate_token(api_key)
            headers["Authorization"] = f"Ghost {token}"
        if connection.get("mock_fault"):
            headers["X-Mock-Fault"] = str(connection["mock_fault"])
        return httpx.Client(transport=self._transport, headers=headers, timeout=10.0)

    def validate(self, rendition: dict, destination: dict, connection: dict) -> dict:
        return self._sim.validate(rendition, destination, connection)

    def publish(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        base_url = (connection.get("instance_url") or connection.get("base_url") or destination.get("url") or "").rstrip("/")

        if get_settings().connector_mode == "simulation" and not self._transport:
            return self._sim.publish(rendition, destination, connection, idempotency_key)

        marker = sha256(idempotency_key.encode("utf-8")).hexdigest()[:16]
        title = rendition.get("title") or ""
        body = rendition.get("body") or ""
        tagged_body = f"<!-- incubrix_marker:{marker} -->\n<p>{body}</p>"

        payload = {
            "posts": [
                {
                    "title": title,
                    "html": tagged_body,
                    "status": "published",
                }
            ]
        }

        endpoint = f"{base_url}/ghost/api/admin/posts/?source=html"
        client = self._get_client(connection)
        try:
            resp = client.post(endpoint, json=payload)
            if resp.status_code >= 400:
                raise map_status_to_connector_error(resp.status_code, resp.text, headers=dict(resp.headers))
            data = resp.json()
            posts_list = data.get("posts", [{}])
            first_post = posts_list[0] if posts_list else {}
            post_id = str(data.get("platform_post_id") or first_post.get("id") or "")
            live_url = data.get("live_url") or first_post.get("url") or f"{base_url}/{post_id}"
            return {
                "platform_post_id": post_id,
                "live_url": live_url,
                "status": data.get("status", "published"),
            }
        except httpx.TimeoutException:
            raise ConnectorError(code="PLATFORM_UNAVAILABLE", message="Ghost request timed out", retryable=True, status_code=504)
        except httpx.HTTPStatusError as e:
            raise map_status_to_connector_error(e.response.status_code, e.response.text, headers=dict(e.response.headers))

    def get_status(self, platform_post_id: str, connection: dict[str, Any]) -> dict[str, Any]:
        base_url = (connection.get("instance_url") or connection.get("base_url") or "").rstrip("/")
        if get_settings().connector_mode == "simulation" and not self._transport:
            return self._sim.get_status(platform_post_id, connection)

        endpoint = f"{base_url}/ghost/api/admin/posts/{platform_post_id}/"
        client = self._get_client(connection)
        try:
            resp = client.get(endpoint)
            if resp.status_code == 404:
                return {"status": "not_found", "live_url": f"{base_url}/{platform_post_id}"}
            if resp.status_code >= 400:
                raise map_status_to_connector_error(resp.status_code, resp.text, headers=dict(resp.headers))
            data = resp.json()
            posts_list = data.get("posts", [{}])
            p = posts_list[0] if posts_list else {}
            return {
                "status": data.get("status") or p.get("status", "published"),
                "live_url": data.get("live_url") or p.get("url") or f"{base_url}/{platform_post_id}",
            }
        except httpx.TimeoutException:
            raise ConnectorError(code="PLATFORM_UNAVAILABLE", message="Ghost request timed out", retryable=True, status_code=504)

    def delete(self, platform_post_id: str, connection: dict[str, Any]) -> dict[str, Any]:
        base_url = (connection.get("instance_url") or connection.get("base_url") or "").rstrip("/")
        if get_settings().connector_mode == "simulation" and not self._transport:
            return self._sim.delete(platform_post_id, connection)

        endpoint = f"{base_url}/ghost/api/admin/posts/{platform_post_id}/"
        client = self._get_client(connection)
        try:
            resp = client.delete(endpoint)
            if resp.status_code in {204, 200}:
                return {"deleted": True}
            if resp.status_code == 404:
                return {"deleted": False}
            if resp.status_code >= 400:
                raise map_status_to_connector_error(resp.status_code, resp.text, headers=dict(resp.headers))
            return {"deleted": True}
        except httpx.TimeoutException:
            raise ConnectorError(code="PLATFORM_UNAVAILABLE", message="Ghost delete timed out", retryable=True, status_code=504)

    def fetch_metrics(self, platform_post_id: str, connection: dict, since: str) -> dict[str, Any]:
        return self._sim.fetch_metrics(platform_post_id, connection, since)
