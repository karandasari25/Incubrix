from typing import Any

ERROR_CODE_STATUS_MAP: dict[str, int] = {
    "DEST_SPEC_VIOLATION": 400,
    "DEST_RULE_FREQUENCY_CAP": 429,
    "CONNECTION_AUTH_EXPIRED": 401,
    "PLATFORM_RATE_LIMIT": 429,
    "PLATFORM_QUOTA_EXHAUSTED": 429,
    "PLATFORM_CONTENT_REJECTED": 422,
    "PLATFORM_UNAVAILABLE": 503,
    "CONNECTOR_DISABLED": 503,
    "CONNECTOR_METHOD_NOT_SUPPORTED": 400,
    "CONNECTOR_NOT_FOUND": 404,
}


class ConnectorError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        retryable: bool = False,
        details: Any = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}
        self.status_code = status_code or ERROR_CODE_STATUS_MAP.get(code, 400)
