"""add publications and rule_proposals

Revision ID: 20261122_004
Revises: 20261122_003
Create Date: 2026-11-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261122_004"
down_revision: Union[str, Sequence[str], None] = "20261122_003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "publications",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("destination_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="scheduled"),
        sa.Column("platform_post_id", sa.String(length=255), nullable=True),
        sa.Column("live_url", sa.String(length=2048), nullable=True),
        sa.Column("marker", sa.String(length=64), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_publications_job_id", "publications", ["job_id"])
    op.create_index("ix_publications_destination_id", "publications", ["destination_id"])

    op.create_table(
        "rule_proposals",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("destination_id", sa.String(length=36), nullable=False),
        sa.Column("proposed_rules", sa.JSON(), nullable=False),
        sa.Column("source_text", sa.String(length=4096), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending_confirmation"),
        sa.Column("confirmed_by", sa.String(length=255), nullable=True),
        sa.Column("ai_generated", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rule_proposals_destination_id", "rule_proposals", ["destination_id"])

    # Extra columns for destinations
    with op.batch_alter_table("destinations") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=20), server_default="active", nullable=False))
        batch_op.add_column(sa.Column("excluded", sa.Boolean(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("submit_url_template", sa.String(length=2048), nullable=True))
        batch_op.add_column(sa.Column("member_count", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("rules_verified", sa.Boolean(), server_default="0", nullable=False))


def downgrade() -> None:
    with op.batch_alter_table("destinations") as batch_op:
        batch_op.drop_column("rules_verified")
        batch_op.drop_column("member_count")
        batch_op.drop_column("submit_url_template")
        batch_op.drop_column("excluded")
        batch_op.drop_column("status")

    op.drop_index("ix_rule_proposals_destination_id", table_name="rule_proposals")
    op.drop_table("rule_proposals")
    op.drop_index("ix_publications_destination_id", table_name="publications")
    op.drop_index("ix_publications_job_id", table_name="publications")
    op.drop_table("publications")
