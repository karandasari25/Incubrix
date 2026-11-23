
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import Destination


def _normalize_url(value: str) -> tuple[str | None, str | None]:
    raw = (value or "").strip()

    if not re.match(r"(?i)^https?://", raw):
        return None, "URL must start with http:// or https://"

    try:
        parsed = urlparse(raw)

        if not parsed.hostname:
            return None, "URL has no valid hostname"

        scheme = parsed.scheme.lower()
        host = parsed.hostname.lower()
        port = (
            f":{parsed.port}"
            if parsed.port and parsed.port not in {80, 443}
            else ""
        )

        normalized = (
            f"{scheme}://{host}{port}{parsed.path.rstrip('/')}"
        )

        if parsed.query:
            normalized += f"?{parsed.query}"

        return normalized, None

    except ValueError:
        return None, "Invalid URL"


def _parse_bool(value, field, default=None):
    value = (value or "").strip().lower()

    if not value:
        return default

    if value in {"true", "1", "yes"}:
        return True

    if value in {"false", "0", "no"}:
        return False

    raise ValueError(f"Invalid boolean value for {field}")


def _parse_int(value, field):
    value = (value or "").strip()

    if not value:
        return None

    try:
        return int(value)
    except ValueError:
        raise ValueError(f"Invalid integer value for {field}")


def _parse_tags(value):
    value = (value or "").strip()

    if not value:
        return []

    try:
        tags = json.loads(value)
    except json.JSONDecodeError:
        raise ValueError("audience_tags must contain valid JSON")

    if not isinstance(tags, list):
        raise ValueError("audience_tags must be a JSON list")

    if not all(isinstance(tag, str) for tag in tags):
        raise ValueError("audience_tags must contain only strings")

    return tags


def _parse_datetime(value):
    value = (value or "").strip()

    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("Invalid last_certified_at datetime")


def import_catalogue_csv(
    path: str | Path,
    db: Session | None = None,
) -> dict:

    rows_report = []
    seen = set()

    imported = 0
    duplicates = 0
    bad_rows = 0

    required_headers = {
        "name",
        "url",
        "platform_key",
        "surface",
        "language",
    }

    with Path(path).open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:

        reader = csv.DictReader(handle)

        if not reader.fieldnames:
            raise ValueError("Catalogue CSV has no header row")

        missing = required_headers - set(reader.fieldnames)

        if missing:
            raise ValueError(
                f"Catalogue CSV missing columns: {sorted(missing)}"
            )

        existing = set()

        if db is not None:
            existing_rows = db.query(
                Destination.platform_key,
                Destination.url,
            ).all()

            for platform, url in existing_rows:
                normalized, error = _normalize_url(url)

                if normalized and not error:
                    existing.add(
                        (platform.strip().lower(), normalized)
                    )

        pending = []

        for index, row in enumerate(reader, start=2):

            errors = []

            # Detect unexpected extra CSV columns.
            if None in row:
                errors.append("Unexpected extra CSV columns")

            # Normalize URL.
            normalized, url_error = _normalize_url(
                row.get("url", "")
            )

            if url_error:
                errors.append(url_error)

            # Read required fields.
            name = (row.get("name") or "").strip()

            platform = (
                row.get("platform_key") or ""
            ).strip().lower()

            surface = (
                row.get("surface") or ""
            ).strip()

            # Older CSV files may not contain connector_key.
            connector = (
                row.get("connector_key")
                or row.get("platform_key")
                or ""
            ).strip().lower()

            language = (
                row.get("language") or ""
            ).strip().lower()

            required_values = {
                "name": name,
                "platform_key": platform,
                "surface": surface,
                "connector_key": connector,
                "language": language,
            }

            for field, value in required_values.items():
                if not value:
                    errors.append(f"{field} is required")

            # Duplicate detection.
            key = (
                (platform, normalized)
                if normalized
                else None
            )

            duplicate_found = False

            if key:
                if key in seen:
                    duplicate_found = True
                    errors.append("Duplicate platform and URL")
                else:
                    seen.add(key)

                if db is not None and key in existing:
                    duplicate_found = True
                    errors.append(
                        "Destination already exists in database"
                    )

            if duplicate_found:
                duplicates += 1
                rows_report.append({
                    "row": index,
                    "errors": errors,
                })
                continue

            if errors:
                bad_rows += 1

                rows_report.append({
                    "row": index,
                    "errors": errors,
                })

                continue

            try:
                data = {
                    "name": name,
                    "url": normalized,
                    "platform_key": platform,
                    "surface": surface,

                    "category": (
                        row.get("category") or ""
                    ).strip() or None,

                    "audience_tags": _parse_tags(
                        row.get("audience_tags")
                    ),

                    "language": language,

                    "geo": (
                        row.get("geo") or ""
                    ).strip() or None,

                    "est_audience": _parse_int(
                        row.get("est_audience"),
                        "est_audience",
                    ),

                    "rules_url": (
                        row.get("rules_url") or ""
                    ).strip() or None,

                    "frequency_cap": (
                        row.get("frequency_cap") or ""
                    ).strip() or None,

                    "self_promo_allowed": _parse_bool(
                        row.get("self_promo_allowed"),
                        "self_promo_allowed",
                    ),

                    "link_policy": (
                        row.get("link_policy") or ""
                    ).strip() or None,

                    "disclosure_required": _parse_bool(
                        row.get("disclosure_required"),
                        "disclosure_required",
                    ),

                    "automation_allowed": _parse_bool(
                        row.get("automation_allowed"),
                        "automation_allowed",
                    ),

                    "connector_key": connector,

                    "relevance_score": _parse_int(
                        row.get("relevance_score"),
                        "relevance_score",
                    ),

                    "relevance_reason": (
                        row.get("relevance_reason") or ""
                    ).strip() or None,

                    "level": (
                        row.get("level") or "L0"
                    ).strip(),

                    "last_certified_at": _parse_datetime(
                        row.get("last_certified_at")
                    ),

                    "rules_verified": _parse_bool(
                        row.get("rules_verified"),
                        "rules_verified",
                        False,
                    ),

                    "status": (
                        row.get("status") or "active"
                    ).strip(),

                    "excluded": _parse_bool(
                        row.get("excluded"),
                        "excluded",
                        False,
                    ),
                }

                score = data["relevance_score"]

                if score is not None and not 1 <= score <= 5:
                    raise ValueError(
                        "relevance_score must be between 1 and 5"
                    )

                # Create database record when a session is supplied.
                if db is not None:
                    pending.append(Destination(**data))

                imported += 1

                rows_report.append({
                    "row": index,
                    "url": normalized,
                    "errors": [],
                })

            except (ValueError, TypeError) as exc:
                bad_rows += 1

                rows_report.append({
                    "row": index,
                    "errors": [str(exc)],
                })

        # Save all valid records in one transaction.
        if db is not None and pending:
            try:
                db.add_all(pending)
                db.commit()

            except Exception:
                db.rollback()
                raise

    return {
        "imported": imported,
        "duplicates": duplicates,
        "bad_rows": bad_rows,
        "rows": rows_report,
    }
