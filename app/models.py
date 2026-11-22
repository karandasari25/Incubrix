from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result_links: Mapped[list] = mapped_column(JSON, default=list)
    marker: Mapped[str | None] = mapped_column(String(64), nullable=True)
    platform_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class Destination(Base):
    __tablename__ = "destinations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    platform_key: Mapped[str] = mapped_column(String(100), nullable=False)
    surface: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=True)
    audience_tags: Mapped[list] = mapped_column(JSON, default=list)
    language: Mapped[str] = mapped_column(String(35), nullable=True)
    geo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    est_audience: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rules_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    frequency_cap: Mapped[str | None] = mapped_column(String(50), nullable=True)
    self_promo_allowed: Mapped[bool | None] = mapped_column(nullable=True)
    link_policy: Mapped[str | None] = mapped_column(String(100), nullable=True)
    disclosure_required: Mapped[bool | None] = mapped_column(nullable=True)
    automation_allowed: Mapped[bool | None] = mapped_column(nullable=True)
    connector_key: Mapped[str] = mapped_column(String(100), nullable=False)
    relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    relevance_reason: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    level: Mapped[str] = mapped_column(String(2), default="L0")
    last_certified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CertificationEvidence(Base):
    __tablename__ = "certification_evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    destination_id: Mapped[str] = mapped_column(String(36), index=True)
    connector_key: Mapped[str] = mapped_column(String(100), nullable=False)
    run_type: Mapped[str] = mapped_column(String(10), nullable=False)
    passed: Mapped[bool] = mapped_column(nullable=False)
    level: Mapped[str] = mapped_column(String(2), nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, nullable=False)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    tested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AlertTicket(Base):
    __tablename__ = "alert_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    destination_id: Mapped[str] = mapped_column(String(36), index=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
