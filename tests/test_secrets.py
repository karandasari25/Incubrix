from pathlib import Path
import re

from app.logging import redact


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
