from hashlib import sha256
from typing import Any
import httpx

from app.config import get_settings
from app.connectors.base import ConnectorBase
from app.connectors.errors import ConnectorError
from app.connectors.http_client import map_status_to_connector_error
from app.connectors.simulation import SimulationConnector


class DevToConnector(ConnectorBase):
    """Real HTTPX Dev.to bridge connector with unpublish-as-delete semantics."""

    def __init__(self, client: httpx.Client | None = None, transport: httpx.BaseTransport | None = None) -> None:
        self._client = client
        self._transport = transport
        self._sim = SimulationConnector("devto", title_max=255, body_max=70000)

    def _get_client(self, connection: dict[str, Any]) -> httpx.Client:
        if self._client:
            return self._client
        headers = {}
        api_key = connection.get("api_key")
        if api_key:
            headers["api-key"] = str(api_key)
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
        tagged_body = f"<!-- incubrix_marker:{marker} -->\n{body}"

        payload = {
            "article": {
                "title": title,
                "body_markdown": tagged_body,
                "published": True,
            }
        }

        endpoint = f"{base_url}/api/articles" if not base_url.endswith("/articles") else base_url
        client = self._get_client(connection)
        try:
            resp = client.post(endpoint, json=payload)
            if resp.status_code >= 400:
                raise map_status_to_connector_error(resp.status_code, resp.text, headers=dict(resp.headers))
            data = resp.json()
            post_id = str(data.get("platform_post_id") or data.get("id") or "")
            live_url = data.get("live_url") or data.get("url") or f"{base_url}/{post_id}"
            return {
                "platform_post_id": post_id,
                "live_url": live_url,
                "status": "published",
            }
        except httpx.TimeoutException:
            raise ConnectorError(code="PLATFORM_UNAVAILABLE", message="Dev.to request timed out", retryable=True, status_code=504)
        except httpx.HTTPStatusError as e:
            raise map_status_to_connector_error(e.response.status_code, e.response.text, headers=dict(e.response.headers))

    def get_status(self, platform_post_id: str, connection: dict[str, Any]) -> dict[str, Any]:
        base_url = (connection.get("instance_url") or connection.get("base_url") or "").rstrip("/")
        if get_settings().connector_mode == "simulation" and not self._transport:
            return self._sim.get_status(platform_post_id, connection)

        endpoint = f"{base_url}/api/articles/{platform_post_id}"
        client = self._get_client(connection)
        try:
            resp = client.get(endpoint)
            if resp.status_code == 404:
                return {"status": "not_found", "live_url": f"{base_url}/{platform_post_id}"}
            if resp.status_code >= 400:
                raise map_status_to_connector_error(resp.status_code, resp.text, headers=dict(resp.headers))
            data = resp.json()
            is_pub = data.get("published", True)
            return {
                "status": "published" if is_pub else "unpublished",
                "live_url": data.get("live_url") or data.get("url") or f"{base_url}/{platform_post_id}",
            }
        except httpx.TimeoutException:
            raise ConnectorError(code="PLATFORM_UNAVAILABLE", message="Dev.to request timed out", retryable=True, status_code=504)

    def delete(self, platform_post_id: str, connection: dict[str, Any]) -> dict[str, Any]:
        """Dev.to has no delete API endpoint; delete unpublishes the article."""
        base_url = (connection.get("instance_url") or connection.get("base_url") or "").rstrip("/")
        if get_settings().connector_mode == "simulation" and not self._transport:
            return {"deleted": False}

        endpoint = f"{base_url}/api/articles/{platform_post_id}"
        client = self._get_client(connection)
        try:
            resp = client.put(endpoint, json={"article": {"published": False}})
            if resp.status_code == 404:
                return {"deleted": False}
            if resp.status_code >= 400:
                raise map_status_to_connector_error(resp.status_code, resp.text, headers=dict(resp.headers))
            return {"deleted": False, "unpublished": True}
        except httpx.TimeoutException:
            raise ConnectorError(code="PLATFORM_UNAVAILABLE", message="Dev.to delete timed out", retryable=True, status_code=504)
