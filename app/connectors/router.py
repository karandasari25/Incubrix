from typing import Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.connectors.errors import ConnectorError
from app.connectors.registry import get_registry


router = APIRouter(prefix="/connector/v1")


class ValidateRequest(BaseModel):
    rendition: dict = Field(default_factory=dict)
    destination: dict = Field(default_factory=dict)
    connection: dict = Field(default_factory=dict)


class PublishRequest(BaseModel):
    rendition: dict = Field(default_factory=dict)
    destination: dict = Field(default_factory=dict)
    connection: dict = Field(default_factory=dict)
    idempotency_key: str


class PostRequest(BaseModel):
    platform_post_id: str
    connection: dict = Field(default_factory=dict)


class MetricsRequest(BaseModel):
    platform_post_id: str
    connection: dict = Field(default_factory=dict)
    since: str = ""


class AuthRequest(BaseModel):
    connection: dict = Field(default_factory=dict)


class AssistRequest(BaseModel):
    rendition: dict = Field(default_factory=dict)
    destination: dict = Field(default_factory=dict)


def get_connector(connector_key: str):
    return get_registry().get_connector(connector_key)


def _handle_connector_call(connector_key: str, method: str, func, *args, **kwargs) -> Any:
    registry = get_registry()
    registry.check_enabled(connector_key)
    registry.verify_capability(connector_key, method)
    connector = registry.get_connector(connector_key)
    try:
        return func(connector, *args, **kwargs)
    except ConnectorError:
        raise
    except NotImplementedError as exc:
        raise ConnectorError(
            code="DEST_SPEC_VIOLATION",
            message=str(exc) or f"Method '{method}' is not implemented for '{connector_key}'",
            status_code=400,
        )
    except Exception as exc:
        raise ConnectorError(
            code="PLATFORM_UNAVAILABLE",
            message=f"Connector error: {exc}",
            retryable=True,
            status_code=503,
        )


@router.post("/{connector_key}/validate")
def validate(connector_key: str, payload: ValidateRequest):
    return _handle_connector_call(
        connector_key,
        "validate",
        lambda c: c.validate(payload.rendition, payload.destination, payload.connection),
    )


@router.post("/{connector_key}/publish")
def publish(connector_key: str, payload: PublishRequest):
    return _handle_connector_call(
        connector_key,
        "publish",
        lambda c: c.publish(
            payload.rendition,
            payload.destination,
            payload.connection,
            payload.idempotency_key,
        ),
    )


@router.post("/{connector_key}/get_status")
def get_status(connector_key: str, payload: PostRequest):
    return _handle_connector_call(
        connector_key,
        "get_status",
        lambda c: c.get_status(payload.platform_post_id, payload.connection),
    )


@router.post("/{connector_key}/delete")
def delete(connector_key: str, payload: PostRequest):
    return _handle_connector_call(
        connector_key,
        "delete",
        lambda c: c.delete(payload.platform_post_id, payload.connection),
    )


@router.post("/{connector_key}/fetch_metrics")
def fetch_metrics(connector_key: str, payload: MetricsRequest):
    return _handle_connector_call(
        connector_key,
        "fetch_metrics",
        lambda c: c.fetch_metrics(
            payload.platform_post_id, payload.connection, payload.since
        ),
    )


@router.post("/{connector_key}/refresh_auth")
def refresh_auth(connector_key: str, payload: AuthRequest):
    return _handle_connector_call(
        connector_key,
        "refresh_auth",
        lambda c: c.refresh_auth(payload.connection),
    )


@router.post("/{connector_key}/build_assist_pack")
def build_assist_pack(connector_key: str, payload: AssistRequest):
    return _handle_connector_call(
        connector_key,
        "build_assist_pack",
        lambda c: c.build_assist_pack(payload.rendition, payload.destination),
    )
