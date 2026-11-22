from datetime import datetime, timedelta, timezone


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
