"""add job reconciliation fields

Revision ID: 20261122_002
Revises: 20261122_001
Create Date: 2026-11-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261122_002"
down_revision: Union[str, Sequence[str], None] = "20261122_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("jobs", sa.Column("marker", sa.String(length=64), nullable=True))
    op.add_column("jobs", sa.Column("platform_post_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "platform_post_id")
    op.drop_column("jobs", "marker")
