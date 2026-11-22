from uuid import uuid4

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.errors import APIError, error_body


class CorrelationAndIdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid4())
        request.state.correlation_id = correlation_id

        if request.method == "POST" and request.url.path.startswith("/api/v1/"):
            idempotency_key = request.headers.get("Idempotency-Key")
            if not idempotency_key:
                error = APIError(
                    code="IDEMPOTENCY_KEY_REQUIRED",
                    message="Every application POST requires an Idempotency-Key header.",
                    status_code=400,
                    retryable=False,
                    details={"header": "Idempotency-Key"},
                )
                response = JSONResponse(status_code=400, content=error_body(error))
                response.headers["X-Correlation-Id"] = correlation_id
                return response

            if len(idempotency_key.strip()) < 8:
                error = APIError(
                    code="IDEMPOTENCY_KEY_INVALID",
                    message="Idempotency-Key must contain at least 8 characters.",
                    status_code=400,
                    retryable=False,
                )
                response = JSONResponse(status_code=400, content=error_body(error))
                response.headers["X-Correlation-Id"] = correlation_id
                return response

        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        return response

