import csv
import re
from pathlib import Path
from urllib.parse import urlparse


def _normalize_url(value: str) -> tuple[str | None, str | None]:
    raw = (value or "").strip()
    if not re.match(r"(?i)^https?://", raw):
        return None, "URL must start with http:// or https://"
    parsed = urlparse(raw)
    if not parsed.hostname:
        return None, "URL has no valid hostname"
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower()
    port = f":{parsed.port}" if parsed.port and parsed.port not in {80, 443} else ""
    normalized = f"{scheme}://{host}{port}{parsed.path.rstrip('/')}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    return normalized, None


def import_catalogue_csv(path: str | Path) -> dict:
    rows_report = []
    seen = set()
    imported = duplicates = bad_rows = 0
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for index, row in enumerate(csv.DictReader(handle), start=2):
            errors = []
            normalized, url_error = _normalize_url(row.get("url", ""))
            if url_error:
                errors.append(url_error)
            language = (row.get("language") or "").strip().lower()
            if not language:
                errors.append("Language is required")
            if normalized:
                key = (row.get("platform_key") or "").strip().lower(), normalized
                if key in seen:
                    duplicates += 1
                    errors.append("Duplicate platform and URL")
                else:
                    seen.add(key)
            if "Duplicate platform and URL" in errors:
                rows_report.append({"row": index, "errors": ["Duplicate platform and URL"]})
            elif errors:
                bad_rows += 1
                rows_report.append({"row": index, "errors": errors})
            else:
                imported += 1
                rows_report.append({"row": index, "url": normalized, "errors": []})
    return {
        "imported": imported,
        "duplicates": duplicates,
        "bad_rows": bad_rows,
        "rows": rows_report,
    }
