from datetime import datetime, timezone
from typing import Any


def build_output_manifest(
    providers: dict[str, str],
    settings: dict[str, Any],
    seed: int,
    timings: dict[str, float],
    warnings: list[str],
    cost_estimate: float,
) -> dict[str, Any]:
    return {
        "providers": providers,
        "settings": settings,
        "seed": seed,
        "timings": timings,
        "cost_estimate": cost_estimate,
        "warnings": warnings,
        "licence_rights": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "policy": "Content licence and rights remain the responsibility of the submitter",
        },
    }
