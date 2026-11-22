import hashlib
import hmac
from typing import Any

from app.connectors.simulation import SimulationConnector


class WebhookConnector(SimulationConnector):
    def __init__(self) -> None:
        super().__init__("webhook")

    def publish(self, rendition: dict, destination: dict, connection: dict,
                idempotency_key: str) -> dict:
        marker = hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]
        secret = connection.get("webhook_secret", "")
        signature = hmac.new(secret.encode(), idempotency_key.encode(), hashlib.sha256).hexdigest()
        return super().publish(
            {**rendition, "incubrix_signature": signature},
            destination,
            connection,
            idempotency_key,
        )
