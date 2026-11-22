from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any

current_correlation_id: ContextVar[str | None] = ContextVar("current_correlation_id", default=None)
current_job_id: ContextVar[str | None] = ContextVar("current_job_id", default=None)

TOKEN_PATTERN = re.compile(
    r"(?i)(authorization\s*:\s*(?:bearer\s+)?[^\s,;]+|"
    r"bearer\s+[A-Za-z0-9._~+/=-]+|"
    r"(?:api[_-]?key|access[_-]?key|secret|webhook_secret|token|password)\s*[=:]\s*[^\s,;]+)"
)


def redact(value: str) -> str:
    if not isinstance(value, str):
        return value
    return TOKEN_PATTERN.sub("[REDACTED]", value)


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: (redact(v) if isinstance(v, str) else v)
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, (list, tuple)):
                record.args = tuple(
                    redact(a) if isinstance(a, str) else a for a in record.args
                )
        elif isinstance(record.msg, str):
            record.msg = redact(record.msg)
        return True


class IncuBrixJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        job_id = getattr(record, "job_id", None) or current_job_id.get(None)
        correlation_id = getattr(record, "correlation_id", None) or current_correlation_id.get(None)
        try:
            msg = record.getMessage()
        except Exception:
            msg = str(record.msg)
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "job_id": job_id,
            "correlation_id": correlation_id,
            "message": redact(msg),
        }
        return json.dumps(payload)
