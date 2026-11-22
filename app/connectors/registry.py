from functools import lru_cache
from pathlib import Path
from typing import Any, Type

from app.config import get_settings
from app.connectors.assisted import AssistedConnector
from app.connectors.base import ConnectorBase
from app.connectors.devto import DevToConnector
from app.connectors.discourse import DiscourseConnector
from app.connectors.errors import ConnectorError
from app.connectors.ghost import GhostConnector
from app.connectors.hashnode import HashnodeConnector
from app.connectors.kit import KitConnector
from app.connectors.lemmy import LemmyConnector
from app.connectors.loader import ConnectorLoader
from app.connectors.mrss import MrssConnector
from app.connectors.webhook import WebhookConnector


CONNECTOR_CLASSES: dict[str, Type[ConnectorBase]] = {
    "discourse": DiscourseConnector,
    "lemmy": LemmyConnector,
    "ghost": GhostConnector,
    "devto": DevToConnector,
    "webhook": WebhookConnector,
    "assisted": AssistedConnector,
    "mrss": MrssConnector,
    "hashnode": HashnodeConnector,
    "kit": KitConnector,
}

METHOD_CAPABILITY_MAP: dict[str, set[str]] = {
    "validate": {"validate"},
    "publish": {"publish"},
    "get_status": {"status", "get_status"},
    "delete": {"delete"},
    "fetch_metrics": {"metrics", "fetch_metrics"},
    "refresh_auth": {"refresh_auth"},
    "build_assist_pack": {"build_assist_pack", "assist_pack"},
}


class ConnectorRegistry:
    def __init__(self, manifests_dir: str | Path | None = None) -> None:
        self.loader = ConnectorLoader(manifests_dir)
        self._manifests: dict[str, dict[str, Any]] = {}
        self._instances: dict[str, ConnectorBase] = {}
        self._load_all()

    def _load_all(self) -> None:
        for key, cls in CONNECTOR_CLASSES.items():
            try:
                manifest = self.loader.load(key)
                self._manifests[key] = manifest
                self._instances[key] = cls()
            except Exception as exc:
                continue

    def get_connector(self, connector_key: str) -> ConnectorBase:
        self.check_enabled(connector_key)
        if connector_key not in self._instances:
            raise ConnectorError(
                code="CONNECTOR_NOT_FOUND",
                message=f"Unknown or unconfigured connector: {connector_key}",
                status_code=404,
            )
        return self._instances[connector_key]

    def get_manifest(self, connector_key: str) -> dict[str, Any]:
        if connector_key not in self._manifests:
            try:
                self._manifests[connector_key] = self.loader.load(connector_key)
            except KeyError:
                raise ConnectorError(
                    code="CONNECTOR_NOT_FOUND",
                    message=f"Connector manifest not found: {connector_key}",
                    status_code=404,
                )
        return self._manifests[connector_key]

    def check_enabled(self, connector_key: str) -> None:
        settings = get_settings()
        disabled = set(settings.disabled_connectors or [])
        if connector_key in disabled:
            raise ConnectorError(
                code="CONNECTOR_DISABLED",
                message=f"Connector '{connector_key}' is disabled by kill switch.",
                status_code=503,
            )

    def has_capability(self, connector_key: str, method: str) -> bool:
        if method == "validate":
            return True
        manifest = self.get_manifest(connector_key)
        caps = manifest.get("capabilities", [])
        if isinstance(caps, dict):
            # Backward compatibility if a dict format was used
            return bool(caps.get(method, False))
        req_caps = METHOD_CAPABILITY_MAP.get(method, {method})
        return any(cap in req_caps for cap in caps)

    def verify_capability(self, connector_key: str, method: str) -> None:
        if not self.has_capability(connector_key, method):
            raise ConnectorError(
                code="DEST_SPEC_VIOLATION",
                message=f"Method '{method}' is not supported by connector '{connector_key}'.",
                status_code=400,
                details={"connector": connector_key, "method": method},
            )

    def list_connectors(self) -> list[str]:
        return list(self._instances.keys())


_registry: ConnectorRegistry | None = None


def get_registry() -> ConnectorRegistry:
    global _registry
    if _registry is None:
        _registry = ConnectorRegistry()
    return _registry
