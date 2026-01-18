"""Replace RAEEntry with MilestoneRAE and update EVMSnapshot schema

Revision ID: f4380a6f5ffa
Revises: 62af69c6fc72
Create Date: 2026-01-17 13:06:55.735538

"""
from typing import Sequence

import sqlalchemy as sa
from alembic import op

from app.models import GUID, JSONB

CURRENT_TIMESTAMP = "(CURRENT_TIMESTAMP)"

# revision identifiers, used by Alembic.
revision = "f4380a6f5ffa"
down_revision = "62af69c6fc72"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    """Apply RAE replacement and EVMSnapshot schema updates."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    numeric_15_2 = sa.Numeric(precision=15, scale=2)
    numeric_10_4 = sa.Numeric(precision=10, scale=4)
    numeric_5_2 = sa.Numeric(precision=5, scale=2)

    if "rae_entries" in table_names:
        op.drop_table("rae_entries")

    if "milestone_rae" not in table_names:
        op.create_table(
            "milestone_rae",
            sa.Column("milestone_id", GUID(), nullable=False),
            sa.Column("date", sa.DateTime(), nullable=False),
            sa.Column("amount", numeric_15_2, nullable=False),
            sa.Column("comment", sa.String(length=500), nullable=True),
            sa.Column("details", JSONB(), nullable=True),
            sa.Column("updated_by", GUID(), nullable=False),
            sa.Column("id", GUID(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text(CURRENT_TIMESTAMP),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text(CURRENT_TIMESTAMP),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(
                ["milestone_id"],
                ["milestones.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "idx_milestone_rae_milestone_date",
            "milestone_rae",
            ["milestone_id", "date"],
            unique=False,
        )
        op.create_index(
            "idx_milestone_rae_date",
            "milestone_rae",
            ["date"],
            unique=False,
        )
        op.create_index(
            "ix_milestone_rae_milestone_id",
            "milestone_rae",
            ["milestone_id"],
            unique=False,
        )
        op.create_index(
            "ix_milestone_rae_updated_by",
            "milestone_rae",
            ["updated_by"],
            unique=False,
        )

    if "evm_snapshots" in table_names:
        with op.batch_alter_table("evm_snapshots", schema=None) as batch_op:
            batch_op.alter_column(
                "status_date",
                new_column_name="snapshot_date",
                existing_type=sa.Date(),
                existing_nullable=False,
            )
            batch_op.alter_column(
                "planned_value",
                new_column_name="pv",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "earned_value",
                new_column_name="ev_physical",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "actual_cost",
                new_column_name="ac",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "budget_at_completion",
                new_column_name="bac",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "estimate_at_completion",
                new_column_name="eac_plan_physical",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "estimate_to_complete",
                new_column_name="etc_physical",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "variance_at_completion",
                new_column_name="vac_physical",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "schedule_variance",
                new_column_name="sv_physical",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "cost_variance",
                new_column_name="cv_physical",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "schedule_performance_index",
                new_column_name="spi_physical",
                existing_type=numeric_10_4,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "cost_performance_index",
                new_column_name="cpi_physical",
                existing_type=numeric_10_4,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "to_complete_performance_index",
                new_column_name="tcpi_bac",
                existing_type=numeric_10_4,
                existing_nullable=True,
            )
            batch_op.add_column(
                sa.Column("ev_milestone", numeric_15_2, nullable=True)
            )
            batch_op.add_column(
                sa.Column("eac_cpi_physical", numeric_15_2, nullable=True)
            )
            batch_op.add_column(
                sa.Column("eac_cpispi_physical", numeric_15_2, nullable=True)
            )
            batch_op.add_column(
                sa.Column("percent_complete", numeric_5_2, nullable=True)
            )


def downgrade() -> None:
    """Revert RAE replacement and EVMSnapshot schema updates."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())

    numeric_15_2 = sa.Numeric(precision=15, scale=2)
    numeric_10_4 = sa.Numeric(precision=10, scale=4)

    if "evm_snapshots" in table_names:
        with op.batch_alter_table("evm_snapshots", schema=None) as batch_op:
            batch_op.drop_column("percent_complete")
            batch_op.drop_column("eac_cpispi_physical")
            batch_op.drop_column("eac_cpi_physical")
            batch_op.drop_column("ev_milestone")
            batch_op.alter_column(
                "tcpi_bac",
                new_column_name="to_complete_performance_index",
                existing_type=numeric_10_4,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "cpi_physical",
                new_column_name="cost_performance_index",
                existing_type=numeric_10_4,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "spi_physical",
                new_column_name="schedule_performance_index",
                existing_type=numeric_10_4,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "cv_physical",
                new_column_name="cost_variance",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "sv_physical",
                new_column_name="schedule_variance",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "vac_physical",
                new_column_name="variance_at_completion",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "etc_physical",
                new_column_name="estimate_to_complete",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "eac_plan_physical",
                new_column_name="estimate_at_completion",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "bac",
                new_column_name="budget_at_completion",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "ac",
                new_column_name="actual_cost",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "ev_physical",
                new_column_name="earned_value",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "pv",
                new_column_name="planned_value",
                existing_type=numeric_15_2,
                existing_nullable=True,
            )
            batch_op.alter_column(
                "snapshot_date",
                new_column_name="status_date",
                existing_type=sa.Date(),
                existing_nullable=False,
            )

    if "milestone_rae" in table_names:
        op.drop_index("ix_milestone_rae_updated_by", table_name="milestone_rae")
        op.drop_index(
            "ix_milestone_rae_milestone_id",
            table_name="milestone_rae",
        )
        op.drop_index("idx_milestone_rae_date", table_name="milestone_rae")
        op.drop_index(
            "idx_milestone_rae_milestone_date",
            table_name="milestone_rae",
        )
        op.drop_table("milestone_rae")

    if "rae_entries" not in table_names:
        op.create_table(
            "rae_entries",
            sa.Column("task_id", GUID(), nullable=False),
            sa.Column("type", sa.String(length=20), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=False),
            sa.Column("severity", sa.String(length=20), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("mitigation", sa.Text(), nullable=True),
            sa.Column("identified_date", sa.Date(), nullable=True),
            sa.Column("resolution_date", sa.Date(), nullable=True),
            sa.Column("details", JSONB(), nullable=True),
            sa.Column("id", GUID(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text(CURRENT_TIMESTAMP),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                server_default=sa.text(CURRENT_TIMESTAMP),
                nullable=False,
            ),
            sa.CheckConstraint(
                "category IN ('technical', 'financial', 'schedule', "
                "'resource', 'quality', 'other')",
                name="ck_rae_entries_category",
            ),
            sa.CheckConstraint(
                "severity IN ('low', 'medium', 'high', 'critical')",
                name="ck_rae_entries_severity",
            ),
            sa.CheckConstraint(
                "status IN ('open', 'mitigated', 'resolved', 'closed')",
                name="ck_rae_entries_status",
            ),
            sa.CheckConstraint(
                "type IN ('risk', 'assumption', 'exception')",
                name="ck_rae_entries_type",
            ),
            sa.ForeignKeyConstraint(
                ["task_id"],
                ["tasks.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_rae_entries_category",
            "rae_entries",
            ["category"],
            unique=False,
        )
        op.create_index(
            "ix_rae_entries_identified_date",
            "rae_entries",
            ["identified_date"],
            unique=False,
        )
        op.create_index(
            "ix_rae_entries_severity",
            "rae_entries",
            ["severity"],
            unique=False,
        )
        op.create_index(
            "ix_rae_entries_status",
            "rae_entries",
            ["status"],
            unique=False,
        )
        op.create_index(
            "ix_rae_entries_task_id",
            "rae_entries",
            ["task_id"],
            unique=False,
        )
        op.create_index(
            "ix_rae_entries_type",
            "rae_entries",
            ["type"],
            unique=False,
        )
