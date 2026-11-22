from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.connectors.router import get_connector


PUBLISH_FIELDS = ("platform_post_id", "live_url", "status")
STATUS_FIELDS = ("status", "live_url")


def validate_publish_response(response: dict[str, Any]) -> list[str]:
    return [field for field in PUBLISH_FIELDS if field not in response]


def validate_status_response(response: dict[str, Any]) -> list[str]:
    return [field for field in STATUS_FIELDS if field not in response]


class CertificationHarness:
    """Certify publish/status/delete while recording the required honesty label."""

    def __init__(self, run_type: str) -> None:
        if run_type not in {"mock", "local", "live"}:
            raise ValueError("run_type must be exactly mock, local, or live")
        self.run_type = run_type

    def run(
        self,
        destination: dict[str, Any],
        rendition: dict[str, Any],
        connection: dict[str, Any],
        publish_override: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        connector = get_connector(destination["connector_key"])
        steps = []

        validation = connector.validate(rendition, destination, connection)
        steps.append({"step": "validate", "result": validation})
        if not validation["ok"]:
            return self._failed(destination, steps, "destination_spec_violation")

        published = publish_override or connector.publish(
            rendition,
            destination,
            connection,
            f"cert-{destination['connector_key']}-{uuid4()}",
        )
        publish_violations = validate_publish_response(published)
        steps.append({"step": "publish", "result": published,
                      "shape_violations": publish_violations})
        if publish_violations:
            return self._failed(destination, steps, "response_shape_validation_failed",
                                publish_violations)

        status = connector.get_status(published["platform_post_id"], connection)
        status_violations = validate_status_response(status)
        steps.append({"step": "get_status", "result": status,
                      "shape_violations": status_violations})
        if status_violations:
            return self._failed(destination, steps, "status_shape_validation_failed",
                                status_violations)

        deleted = connector.delete(published["platform_post_id"], connection)
        steps.append({"step": "delete", "result": deleted})
        delete_verified = deleted.get("deleted") is True
        if not delete_verified:
            return self._failed(destination, steps, "delete_not_verified")

        return {
            "run_id": str(uuid4()),
            "run_type": self.run_type,
            "destination": destination["name"],
            "connector_key": destination["connector_key"],
            "passed": True,
            "level": "L3",
            "delete_verified": True,
            "live_url": published["live_url"],
            "platform_post_id": published["platform_post_id"],
            "steps": steps,
            "warnings": [],
            "alert": None,
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }

    def _failed(
        self,
        destination: dict[str, Any],
        steps: list[dict[str, Any]],
        reason: str,
        violations: list[str] | None = None,
    ) -> dict[str, Any]:
        alert = {
            "type": "destination_demoted",
            "reason": reason,
            "violations": violations or [],
        }
        return {
            "run_id": str(uuid4()),
            "run_type": self.run_type,
            "destination": destination["name"],
            "connector_key": destination["connector_key"],
            "passed": False,
            "level": "L0",
            "delete_verified": False,
            "live_url": None,
            "platform_post_id": None,
            "steps": steps,
            "warnings": [reason],
            "alert": alert,
            "tested_at": datetime.now(timezone.utc).isoformat(),
        }
