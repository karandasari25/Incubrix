from pathlib import Path
from typing import Any

import yaml


class ConnectorLoader:
    def __init__(self, manifests_dir: str | Path | None = None) -> None:
        if manifests_dir is None:
            manifests_dir = Path(__file__).resolve().parents[2] / "connectors"
        self.manifests_dir = Path(manifests_dir)

    def load(self, connector_key: str) -> dict[str, Any]:
        path = self.manifests_dir / f"{connector_key}.yaml"
        if not path.is_file():
            raise KeyError(f"Unknown connector: {connector_key}")
        with path.open("r", encoding="utf-8") as handle:
            manifest = yaml.safe_load(handle)
        required = {
            "key",
            "version",
            "tier",
            "auth",
            "surfaces",
            "rate_limits",
            "capabilities",
            "error_map",
            "instance_param",
        }
        missing = required.difference(manifest or {})
        if missing:
            raise ValueError(
                f"Connector manifest {connector_key} missing fields: {sorted(missing)}"
            )
        return manifest

