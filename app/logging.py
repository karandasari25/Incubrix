import json
import logging
import re
from datetime import datetime, timezone


TOKEN_PATTERN = re.compile(
    r"(?i)(bearer\s+[A-Za-z0-9._~+/=-]+|"
    r"(?:api[_-]?key|access[_-]?key|secret|token)\s*[=:]\s*[^\s,;]+)"
)


def redact(value: str) -> str:
    return TOKEN_PATTERN.sub("[REDACTED]", value)


class IncuBrixJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "job_id": getattr(record, "job_id", None),
            "correlation_id": getattr(record, "correlation_id", None),
            "message": redact(record.getMessage()),
        }
        return json.dumps(payload)

