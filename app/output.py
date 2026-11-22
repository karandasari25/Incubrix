from pathlib import Path
from typing import Any

from app.config import get_settings


class OutputStore:
    """Write simulation outputs locally; production can use the configured S3-compatible store."""

    def __init__(
        self,
        root: str | Path | None = None,
        simulation_mode: bool | None = None,
        bucket: str | None = None,
    ) -> None:
        settings = get_settings()
        self.root = Path(root or "outputs")
        self.simulation_mode = settings.simulation_mode if simulation_mode is None else simulation_mode
        self.bucket = bucket or settings.minio_bucket

    def save(self, key: str, content: bytes, content_type: str = "application/octet-stream") -> str:
        if self.simulation_mode:
            path = self.root / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            return f"simulation://{path.as_posix()}"
        raise RuntimeError("Production MinIO upload is not configured for this local path")
