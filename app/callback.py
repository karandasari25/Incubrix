import hashlib
import hmac
import json
from typing import Any

import httpx


def sign_callback(payload: dict[str, Any], secret: str) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def send_signed_callback(url: str, payload: dict[str, Any], secret: str) -> dict[str, Any]:
    signature = sign_callback(payload, secret)
    response = httpx.post(
        url,
        json=payload,
        headers={"X-IncuBrix-Signature": signature},
        timeout=10,
    )
    return {"status_code": response.status_code, "delivered": response.status_code < 400}
