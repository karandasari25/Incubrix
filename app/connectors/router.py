from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.connectors.discourse import DiscourseConnector
from app.connectors.lemmy import LemmyConnector
from app.connectors.ghost import GhostConnector
from app.connectors.devto import DevToConnector
from app.connectors.webhook import WebhookConnector
from app.connectors.assisted import AssistedConnector
from app.connectors.mrss import MrssConnector
from app.connectors.hashnode import HashnodeConnector
from app.connectors.kit import KitConnector


router = APIRouter(prefix="/connector/v1")
discourse = DiscourseConnector()
lemmy = LemmyConnector()
ghost = GhostConnector()
devto = DevToConnector()
webhook = WebhookConnector()
assisted = AssistedConnector()
mrss = MrssConnector()
hashnode = HashnodeConnector()
kit = KitConnector()


class ValidateRequest(BaseModel):
    rendition: dict
    destination: dict
    connection: dict


class PublishRequest(BaseModel):
    rendition: dict
    destination: dict
    connection: dict
    idempotency_key: str


class PostRequest(BaseModel):
    platform_post_id: str
    connection: dict


def get_connector(connector_key: str):
    connectors = {
        "discourse": discourse,
        "lemmy": lemmy,
        "ghost": ghost,
        "devto": devto,
        "webhook": webhook,
        "assisted": assisted,
        "mrss": mrss,
        "hashnode": hashnode,
        "kit": kit,
    }
    if connector_key in connectors:
        return connectors[connector_key]
    raise HTTPException(status_code=404, detail="Unknown connector")


@router.post("/{connector_key}/validate")
def validate(connector_key: str, payload: ValidateRequest):
    return get_connector(connector_key).validate(
        payload.rendition,
        payload.destination,
        payload.connection,
    )


@router.post("/{connector_key}/publish")
def publish(connector_key: str, payload: PublishRequest):
    return get_connector(connector_key).publish(
        payload.rendition,
        payload.destination,
        payload.connection,
        payload.idempotency_key,
    )


@router.post("/{connector_key}/get_status")
def get_status(connector_key: str, payload: PostRequest):
    return get_connector(connector_key).get_status(
        payload.platform_post_id,
        payload.connection,
    )


@router.post("/{connector_key}/delete")
def delete(connector_key: str, payload: PostRequest):
    return get_connector(connector_key).delete(
        payload.platform_post_id,
        payload.connection,
    )


class MetricsRequest(BaseModel):
    platform_post_id: str
    connection: dict
    since: str


class AuthRequest(BaseModel):
    connection: dict


class AssistRequest(BaseModel):
    rendition: dict
    destination: dict


@router.post("/{connector_key}/fetch_metrics")
def fetch_metrics(connector_key: str, payload: MetricsRequest):
    return get_connector(connector_key).fetch_metrics(
        payload.platform_post_id,
        payload.connection,
        payload.since,
    )


@router.post("/{connector_key}/refresh_auth")
def refresh_auth(connector_key: str, payload: AuthRequest):
    return get_connector(connector_key).refresh_auth(payload.connection)


@router.post("/{connector_key}/build_assist_pack")
def build_assist_pack(connector_key: str, payload: AssistRequest):
    return get_connector(connector_key).build_assist_pack(
        payload.rendition,
        payload.destination,
    )
