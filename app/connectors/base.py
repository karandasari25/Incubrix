from abc import ABC, abstractmethod
from typing import Any


class ConnectorBase(ABC):
    """Platform connector contract. Implementations must never access the database."""

    @abstractmethod
    def validate(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def publish(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
        connection: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def get_status(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def delete(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError

    def fetch_metrics(
        self,
        platform_post_id: str,
        connection: dict[str, Any],
        since: str,
    ) -> dict[str, Any]:
        raise NotImplementedError

    def refresh_auth(self, connection: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def build_assist_pack(
        self,
        rendition: dict[str, Any],
        destination: dict[str, Any],
    ) -> dict[str, Any]:
        raise NotImplementedError
