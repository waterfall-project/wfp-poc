"""Align Project model with OpenAPI spec

Revision ID: 9d1ae3c65d7a
Revises: 6a6a7592913f
Create Date: 2026-01-11 19:25:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d1ae3c65d7a"
down_revision: str | None = "6a6a7592913f"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade database schema to align Project with OpenAPI spec."""
    op.execute(
        "UPDATE projects SET start_date = COALESCE(start_date, created_at, CURRENT_TIMESTAMP)"
    )
    op.execute(
        "UPDATE projects SET finish_date = COALESCE(finish_date, start_date, created_at, CURRENT_TIMESTAMP)"
    )

    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.alter_column(
            "start_date",
            existing_type=sa.Date(),
            type_=sa.DateTime(),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.alter_column(
            "finish_date",
            existing_type=sa.Date(),
            type_=sa.DateTime(),
            existing_nullable=True,
            nullable=False,
        )
        batch_op.alter_column(
            "budget_at_completion",
            new_column_name="budget",
            existing_type=sa.Float(),
            type_=sa.Numeric(18, 2),
            existing_nullable=True,
        )
        batch_op.add_column(sa.Column("title", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("planned_start_date", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("planned_finish_date", sa.DateTime(), nullable=True))
        batch_op.add_column(
            sa.Column(
                "currency_code", sa.String(length=3), server_default="EUR", nullable=False
            )
        )
        batch_op.add_column(sa.Column("ms_project_uid", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("ms_project_guid", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("ms_project_save_version", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("creation_date", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("last_saved_date", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("calendar_uid", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("minutes_per_day", sa.Integer(), server_default="420", nullable=False)
        )
        batch_op.add_column(
            sa.Column("minutes_per_week", sa.Integer(), server_default="2100", nullable=False)
        )
        batch_op.add_column(
            sa.Column("days_per_month", sa.Integer(), server_default="20", nullable=False)
        )
        batch_op.add_column(
            sa.Column("week_start_day", sa.Integer(), server_default="1", nullable=False)
        )
        batch_op.add_column(
            sa.Column("default_start_time", sa.Time(), server_default="09:00:00", nullable=False)
        )
        batch_op.add_column(
            sa.Column("default_finish_time", sa.Time(), server_default="18:00:00", nullable=False)
        )


def downgrade() -> None:
    """Downgrade database schema to previous state."""
    with op.batch_alter_table("projects", schema=None) as batch_op:
        batch_op.drop_column("default_finish_time")
        batch_op.drop_column("default_start_time")
        batch_op.drop_column("week_start_day")
        batch_op.drop_column("days_per_month")
        batch_op.drop_column("minutes_per_week")
        batch_op.drop_column("minutes_per_day")
        batch_op.drop_column("calendar_uid")
        batch_op.drop_column("last_saved_date")
        batch_op.drop_column("creation_date")
        batch_op.drop_column("ms_project_save_version")
        batch_op.drop_column("ms_project_guid")
        batch_op.drop_column("ms_project_uid")
        batch_op.drop_column("currency_code")
        batch_op.drop_column("planned_finish_date")
        batch_op.drop_column("planned_start_date")
        batch_op.drop_column("title")
        batch_op.alter_column(
            "budget",
            new_column_name="budget_at_completion",
            existing_type=sa.Numeric(18, 2),
            type_=sa.Float(),
            existing_nullable=True,
        )
        batch_op.alter_column(
            "finish_date",
            existing_type=sa.DateTime(),
            type_=sa.Date(),
            existing_nullable=False,
            nullable=True,
        )
        batch_op.alter_column(
            "start_date",
            existing_type=sa.DateTime(),
            type_=sa.Date(),
            existing_nullable=False,
            nullable=True,
        )
