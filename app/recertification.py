from datetime import datetime, timedelta, timezone
from typing import Any
from sqlalchemy.orm import Session

from app.certification import CertificationHarness
from app.models import AlertTicket, Destination


def recertification_due(
    last_certified_at: datetime | str | None,
    now: datetime | None = None,
    interval_days: int = 30,
) -> bool:
    now = now or datetime.now(timezone.utc)
    if last_certified_at is None:
        return True
    if isinstance(last_certified_at, str):
        last_certified_at = datetime.fromisoformat(
            last_certified_at.replace("Z", "+00:00")
        )
    if last_certified_at.tzinfo is None:
        last_certified_at = last_certified_at.replace(tzinfo=timezone.utc)
    return now - last_certified_at >= timedelta(days=interval_days)


def select_due_destinations(
    destinations: list[dict],
    now: datetime | None = None,
    interval_days: int = 30,
) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    return [
        destination
        for destination in destinations
        if recertification_due(
            destination.get("last_certified_at"),
            now,
            interval_days,
        )
    ]


def run_recertification_scheduler(
    db: Session,
    now: datetime | None = None,
    interval_days: int = 30,
    run_type: str = "mock",
) -> dict[str, Any]:
    """Execute scheduled recertification against due destinations, with automatic demotion on failure."""
    now = now or datetime.now(timezone.utc)
    destinations = db.query(Destination).all()
    due_destinations = [
        d for d in destinations
        if recertification_due(d.last_certified_at, now, interval_days)
    ]

    harness = CertificationHarness(run_type=run_type)
    results = []
    demoted_count = 0
    passed_count = 0

    for dest in due_destinations:
        dest_dict = {
            "id": dest.id,
            "name": dest.name,
            "connector_key": dest.connector_key,
            "url": dest.url,
            "surface": dest.surface,
            "level": dest.level,
        }
        rendition = {
            "title": "Scheduled Recertification Post",
            "body": "Automated verification test payload for recertification check.",
        }
        connection = {"instance_url": dest.url}

        cert_res = harness.run(dest_dict, rendition, connection)
        if cert_res["passed"]:
            dest.level = "L3"
            dest.last_certified_at = now
            dest.status = "active"
            passed_count += 1
        else:
            dest.level = "L0"
            dest.status = "demoted"
            dest.excluded = True
            demoted_count += 1
            alert = AlertTicket(
                destination_id=dest.id,
                type="destination_demoted",
                reason=cert_res["warnings"][0] if cert_res["warnings"] else "Recertification failed",
                details=cert_res.get("alert") or {},
                status="open",
            )
            db.add(alert)
        results.append(cert_res)

    db.commit()
    return {
        "total_due": len(due_destinations),
        "passed": passed_count,
        "demoted": demoted_count,
        "results": results,
    }
