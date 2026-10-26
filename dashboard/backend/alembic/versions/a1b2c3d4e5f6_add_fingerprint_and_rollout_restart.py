"""add fingerprint to incidents and rollout_restart to actiontype

Revision ID: a1b2c3d4e5f6
Revises: d9f4c501aded
Create Date: 2026-10-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "d9f4c501aded"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add fingerprint column to incidents (nullable so existing rows don't break)
    op.add_column(
        "incidents",
        sa.Column("fingerprint", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_incidents_fingerprint", "incidents", ["fingerprint"], unique=True
    )
    # NOTE: actiontype is stored as VARCHAR (native_enum=False), not a real
    # Postgres enum — no ALTER TYPE needed. rollout_restart is handled by
    # the model enum class in enums.py only.


def downgrade() -> None:
    op.drop_index("ix_incidents_fingerprint", table_name="incidents")
    op.drop_column("incidents", "fingerprint")
    # NOTE: Postgres does not support removing enum values — downgrade
    # leaves rollout_restart in the enum; this is intentional.
