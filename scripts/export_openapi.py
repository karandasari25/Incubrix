import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

import yaml
from app.main import app


def export_openapi() -> None:
    schema = app.openapi()
    path = root / "openapi.yaml"
    with open(path, "w", encoding="utf-8") as handle:
        yaml.dump(schema, handle, sort_keys=False)
    print(f"Exported OpenAPI schema to {path} with {len(schema.get('paths', {}))} paths.")


if __name__ == "__main__":
    export_openapi()
