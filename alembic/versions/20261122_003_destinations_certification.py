"""add destinations and certification records

Revision ID: 20261122_003
Revises: 20261122_002
Create Date: 2026-11-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261122_003"
down_revision: Union[str, Sequence[str], None] = "20261122_002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "destinations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("platform_key", sa.String(length=100), nullable=False),
        sa.Column("surface", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=100)),
        sa.Column("audience_tags", sa.JSON(), nullable=False),
        sa.Column("language", sa.String(length=35)),
        sa.Column("geo", sa.String(length=100)),
        sa.Column("est_audience", sa.Integer()),
        sa.Column("rules_url", sa.String(length=2048)),
        sa.Column("frequency_cap", sa.String(length=50)),
        sa.Column("self_promo_allowed", sa.Boolean()),
        sa.Column("link_policy", sa.String(length=100)),
        sa.Column("disclosure_required", sa.Boolean()),
        sa.Column("automation_allowed", sa.Boolean()),
        sa.Column("connector_key", sa.String(length=100), nullable=False),
        sa.Column("relevance_score", sa.Integer()),
        sa.Column("relevance_reason", sa.String(length=2048)),
        sa.Column("level", sa.String(length=2), nullable=False),
        sa.Column("last_certified_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "certification_evidence",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("destination_id", sa.String(length=36), nullable=False),
        sa.Column("connector_key", sa.String(length=100), nullable=False),
        sa.Column("run_type", sa.String(length=10), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("level", sa.String(length=2), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("tested_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_certification_evidence_destination_id",
                    "certification_evidence", ["destination_id"])
    op.create_table(
        "alert_tickets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("destination_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=100), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alert_tickets_destination_id", "alert_tickets", ["destination_id"])


def downgrade() -> None:
    op.drop_index("ix_alert_tickets_destination_id", table_name="alert_tickets")
    op.drop_table("alert_tickets")
    op.drop_index("ix_certification_evidence_destination_id",
                  table_name="certification_evidence")
    op.drop_table("certification_evidence")
    op.drop_table("destinations")
