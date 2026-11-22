import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

from app.database import Base, engine
from app.errors import APIError, error_body
from app.logging import IncuBrixJsonFormatter
from app.middleware import CorrelationAndIdempotencyMiddleware
from app.models import Job
from app.routes import router
from app.connectors.router import router as connector_router


handler = logging.StreamHandler()
handler.setFormatter(IncuBrixJsonFormatter())
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


@app.exception_handler(HTTPException)
async def standard_http_error(request: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return await http_exception_handler(request, exc)
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
