import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse

from app.database import Base, engine
from app.errors import APIError, error_body
from app.connectors.errors import ConnectorError
from app.logging import IncuBrixJsonFormatter, SecretRedactionFilter
from app.middleware import CorrelationAndIdempotencyMiddleware
from app.routes import router
from app.connectors.router import router as connector_router


handler = logging.StreamHandler()
handler.setFormatter(IncuBrixJsonFormatter())
handler.addFilter(SecretRedactionFilter())

root_logger = logging.getLogger()
root_logger.handlers.clear()
root_logger.addHandler(handler)
root_logger.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(application: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="IncuBrix", version="0.1.0", lifespan=lifespan)
app.add_middleware(CorrelationAndIdempotencyMiddleware)
app.include_router(router)
app.include_router(connector_router)


@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=error_body(exc))


@app.exception_handler(ConnectorError)
async def connector_error_handler(request: Request, exc: ConnectorError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "retryable": exc.retryable,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": {
                "code": "REQUEST_INVALID",
                "message": "Request validation failed",
                "retryable": False,
                "details": {"errors": exc.errors()},
            }
        },
    )


@app.exception_handler(HTTPException)
async def standard_http_error(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.detail.get("code", "REQUEST_INVALID"),
                    "message": exc.detail.get("message", "Error"),
                    "retryable": exc.detail.get("retryable", False),
                    "details": exc.detail.get("details", {}),
                }
            },
        )
    code = "RESOURCE_NOT_FOUND" if exc.status_code == 404 else "REQUEST_INVALID"
    body = {
        "error": {
            "code": code,
            "message": str(exc.detail),
            "retryable": False,
            "details": {},
        }
    }
    return JSONResponse(status_code=exc.status_code, content=body)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("app.main").error(f"Unhandled exception: {exc}")
    body = {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "An internal server error occurred.",
            "retryable": False,
            "details": {},
        }
    }
    return JSONResponse(status_code=500, content=body)
