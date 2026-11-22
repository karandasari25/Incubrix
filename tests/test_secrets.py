import io
import json
import logging
from pathlib import Path
import re

from app.logging import redact, IncuBrixJsonFormatter, SecretRedactionFilter


TOKEN_PATTERNS = [
    re.compile(
        r"(?i)(?:token|secret|password)[ \t]*[=:][ \t]*(?![$<{])"
        r"[A-Za-z0-9_\-]{16,}"
    )
]


def test_repository_contains_no_embedded_token_assignments():
    root = Path(__file__).resolve().parents[1]
    for path in root.rglob("*"):
        if not path.is_file() or path.name == ".env":
            continue
        if any(part in {".git", ".venv", "__pycache__"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in TOKEN_PATTERNS:
            assert not pattern.search(text), f"Potential embedded token in {path}"


def test_log_redaction_removes_bearer_and_named_secrets():
    secret_name = "to" + "ken"
    secret_value = "very" + "-secret-" + "value"
    message = "Authorization: Bearer " + "abc123456789" + "; " + secret_name + "=" + secret_value
    redacted = redact(message)
    assert "abc123456789" not in redacted
    assert "very-secret-value" not in redacted


def test_captured_logs_contain_no_secrets():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(IncuBrixJsonFormatter())
    handler.addFilter(SecretRedactionFilter())

    logger = logging.getLogger("test_capture_secrets")
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    secret_key = "ghp_" + "1234567890abcdef"
    secret_val = "my_super_" + "secret"
    logger.info("Connecting with Authorization: Bearer %s and webhook_secret=%s", secret_key, secret_val)

    log_output = stream.getvalue()
    assert secret_key not in log_output
    assert secret_val not in log_output
    parsed = json.loads(log_output)
    assert "[REDACTED]" in parsed["message"]
