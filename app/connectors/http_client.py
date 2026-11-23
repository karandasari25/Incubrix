from typing import Any
import httpx

from app.connectors.errors import ConnectorError


def map_status_to_connector_error(
    status_code: int,
    response_text: str = "",
    error_map: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> ConnectorError:
    headers = headers or {}
    status_str = str(status_code)
    code = None
    if error_map and status_str in error_map:
        code = error_map[status_str]

    retryable = status_code in {429, 500, 502, 503, 504}
    details: dict[str, Any] = {"response": response_text[:500]}

    if status_code == 429:
        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if retry_after:
            try:
                details["retry_after"] = int(retry_after)
            except ValueError:
                details["retry_after"] = retry_after
        code = code or "PLATFORM_RATE_LIMIT"
    elif status_code in {401, 403}:
        code = code or "CONNECTION_AUTH_EXPIRED"
        retryable = False
    elif status_code in {400, 422}:
        code = code or "PLATFORM_CONTENT_REJECTED"
        retryable = False
    elif status_code in {500, 502, 503, 504}:
        code = code or "PLATFORM_UNAVAILABLE"
    else:
        code = code or "PLATFORM_CONTENT_REJECTED"

    return ConnectorError(
        code=code,
        message=f"Platform returned HTTP {status_code}: {response_text[:200]}",
        retryable=retryable,
        details=details,
        status_code=status_code,
    )
