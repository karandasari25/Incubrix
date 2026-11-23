from datetime import datetime, timezone
from hashlib import sha256
import hmac
from typing import Any
import httpx

from app.config import get_settings
from app.connectors.base import ConnectorBase
from app.connectors.errors import ConnectorError
from app.connectors.http_client import map_status_to_connector_error
from app.connectors.simulation import SimulationConnector


class WebhookConnector(ConnectorBase):
    """Real HTTPX Webhook connector with HMAC-SHA256 signature and simulation fallback."""

    def __init__(self, client: httpx.Client | None = None, transport: httpx.BaseTransport | None = None) -> None:
        self._client = client
        self._transport = transport
        self._sim = SimulationConnector("webhook")

    def _get_client(self, connection: dict[str, Any]) -> httpx.Client:
        if self._client:
            return self._client
        headers = {}
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
        target_url = (connection.get("target_url") or connection.get("instance_url") or destination.get("url") or "").rstrip("/")

        if get_settings().connector_mode == "simulation" and not self._transport:
            return self._sim.publish(rendition, destination, connection, idempotency_key)

        secret = connection.get("webhook_secret") or connection.get("secret") or "incubrix-secret"
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        sig_data = f"{timestamp}.{idempotency_key}".encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), sig_data, sha256).hexdigest()

        headers = {
            "Idempotency-Key": idempotency_key,
            "X-IncuBrix-Signature": f"t={timestamp},v1={signature}",
            "Content-Type": "application/json",
        }
        if connection.get("mock_fault"):
            headers["X-Mock-Fault"] = str(connection["mock_fault"])

        client = self._get_client(connection)
        try:
            resp = client.post(target_url, json=rendition, headers=headers)
            if resp.status_code in {401, 403}:
                raise ConnectorError(
                    code="CONNECTION_AUTH_EXPIRED",
                    message="Partner webhook returned 401/403 authorization failure",
                    retryable=False,
                    status_code=resp.status_code,
                )
            if resp.status_code >= 400:
                raise map_status_to_connector_error(resp.status_code, resp.text, headers=dict(resp.headers))
            data = resp.json() if resp.text else {}
            post_id = str(data.get("platform_post_id") or data.get("id") or sha256(idempotency_key.encode()).hexdigest()[:12])
            live_url = data.get("live_url") or f"{target_url}/{post_id}"
            return {
                "platform_post_id": post_id,
                "live_url": live_url,
                "status": "published",
            }
        except httpx.TimeoutException:
            raise ConnectorError(code="PLATFORM_UNAVAILABLE", message="Webhook partner timed out", retryable=True, status_code=504)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in {401, 403}:
                raise ConnectorError(code="CONNECTION_AUTH_EXPIRED", message="Webhook authorization revoked", retryable=False, status_code=e.response.status_code)
            raise map_status_to_connector_error(e.response.status_code, e.response.text, headers=dict(e.response.headers))

    def get_status(self, platform_post_id: str, connection: dict[str, Any]) -> dict[str, Any]:
        target_url = (connection.get("target_url") or connection.get("instance_url") or "").rstrip("/")
        if get_settings().connector_mode == "simulation" and not self._transport:
            return self._sim.get_status(platform_post_id, connection)
        endpoint = f"{target_url}/{platform_post_id}"
        client = self._get_client(connection)
        try:
            resp = client.get(endpoint)
            if resp.status_code == 404:
                return {"status": "not_found", "live_url": endpoint}
            return {"status": "published", "live_url": endpoint}
        except Exception:
            return {"status": "published", "live_url": endpoint}

    def delete(self, platform_post_id: str, connection: dict[str, Any]) -> dict[str, Any]:
        target_url = (connection.get("target_url") or connection.get("instance_url") or "").rstrip("/")
        if get_settings().connector_mode == "simulation" and not self._transport:
            return self._sim.delete(platform_post_id, connection)
        endpoint = f"{target_url}/{platform_post_id}"
        client = self._get_client(connection)
        try:
            resp = client.delete(endpoint)
            return {"deleted": resp.status_code in {200, 204}}
        except Exception:
            return {"deleted": False}
